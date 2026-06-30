# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [pipeline]
# tags: [orchestration, end-to-end, runtime]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pathlib import Path

from pr_repair.classification.classifier import classify_findings
from pr_repair.config import AppConfig
from pr_repair.errors import PayloadIngestionError
from pr_repair.ingestion.payload_parser import PayloadParser
from pr_repair.learning.agent_md_recommender import build_agent_md_recommendations
from pr_repair.learning.pattern_extractor import extract_learning_packets
from pr_repair.learning.validator_recommender import build_validator_recommendations
from pr_repair.llm import build_llm_client
from pr_repair.llm.client import LLMClient
from pr_repair.llm.contract import ProposedPatch
from pr_repair.logging import configure_logging, log_event
from pr_repair.orchestration.router import route_findings
from pr_repair.planning.llm_proposer import propose_repairs
from pr_repair.repair.llm_apply import Proposal, apply_llm_proposals, is_apply_eligible
from pr_repair.output.artifact_writer import (
    write_learning_artifacts,
    write_pr_artifacts,
    write_run_artifacts,
)
from pr_repair.output.pr_commentary import build_pr_comment, upsert_implementer_comment
from pr_repair.planning.approval_gate import requires_human_approval
from pr_repair.planning.repair_planner import build_repair_plan
from pr_repair.repo_context.loader import load_repo_context
from pr_repair.runtime import RuntimeManager
from pr_repair.state_store import StateStore
from pr_repair.telemetry import TraceRecorder, build_autofix_telemetry
from pr_repair.types import (
    ExecutionMode,
    Finding,
    PRRef,
    RepairExecution,
    RepoContext,
    RuntimeState,
)
from pr_repair.repair.repair_executor import execute_repair_plan


def run_pipeline(config: AppConfig) -> int:
    """Run the Implementer Bot pipeline from the canonical agent review payload.

    Ingestion is fully deterministic: the bot reads ``agent_review_payload.json``
    (no third-party scraping). If the payload is missing or malformed the run
    fails closed with a non-zero exit code and attempts no repairs.
    """
    configure_logging()
    repo_root = Path.cwd()
    repo_context = load_repo_context(repo_root, write_ceiling=config.write_ceiling)
    store = StateStore(config.output_dir)
    runtime_manager = RuntimeManager(config.output_dir)
    run_state = runtime_manager.create_run(
        repo=config.github_repository,
        mode=config.mode,
        current_phase="parse_payload",
    )

    # Record the full structured-event timeline for this run, written even on a
    # fail-closed exit so every run leaves an auditable trace.
    recorder = TraceRecorder()
    recorder.start()
    try:
        return _run_pipeline_traced(config, repo_root, repo_context, store, runtime_manager, run_state)
    finally:
        recorder.stop()
        try:
            store.write_json("run_trace.json", recorder.to_list())
        except OSError:
            log_event("run_trace_write_failed")


def _run_pipeline_traced(
    config: AppConfig,
    repo_root: Path,
    repo_context: RepoContext,
    store: StateStore,
    runtime_manager: RuntimeManager,
    run_state: RuntimeState,
) -> int:
    try:
        parsed = PayloadParser(config.payload_path).parse()
    except PayloadIngestionError as exc:
        log_event(
            "payload_ingestion_failed",
            payload_path=str(config.payload_path),
            error=str(exc),
        )
        runtime_manager.fail(run_state)
        return 2

    pr = parsed.pr_ref
    run_state = run_state.model_copy(update={"pr_numbers": [pr.pr_number]})
    store.write_runtime_state(run_state)
    log_event(
        "payload_ingested",
        pr_number=pr.pr_number,
        schema_version=parsed.schema_version,
        autofix_candidates=len(parsed.autofix_findings),
        manual_review_required=len(parsed.manual_review_findings),
    )

    run_state = runtime_manager.update_phase(run_state, f"process_pr_{pr.pr_number}")
    bundle = parsed.to_bundle()
    findings = parsed.findings
    classified_findings = classify_findings(findings, repo_context)
    bundle = bundle.model_copy(update={"merged_findings": findings})

    # Bifurcate: deterministic autofix candidates bypass the LLM planner; complex
    # findings are reserved for LLM-assisted manual review.
    route = route_findings(classified_findings)
    log_event(
        "pipeline_routing",
        pr_number=pr.pr_number,
        autofix=len(route.autofix),
        manual=len(route.manual),
    )

    # Manual lane: ask the shared L9 LLM-Router for bounded patch proposals.
    # Proposals are surfaced for human review, never auto-applied. With the
    # default NullLLMClient this is a no-op (every finding abstains).
    llm_client = build_llm_client(config)
    proposals = propose_repairs(route.manual, llm_client, repo_root, config.llm_client_id)
    if proposals:
        store.write_json(
            f"prs/pr_{pr.pr_number}/llm_proposals.json",
            [proposal.model_dump(mode="json") for proposal in proposals],
        )

    # The execution plan covers ONLY the deterministic autofix lane. Manual-review
    # findings are handled by the proposal lane (above) and must not raise the
    # plan's risk/approval gate -- a high-severity architectural finding in the PR
    # cannot block an unrelated, deterministic Semgrep autofix.
    plan = build_repair_plan(pr, route.autofix, config)

    execution: RepairExecution | None = None
    needs_approval = requires_human_approval(plan, config)
    if config.mode in {ExecutionMode.repair_and_verify, ExecutionMode.repair_verify_and_push}:
        execution = execute_repair_plan(plan, config, repo_root)
    elif config.mode is ExecutionMode.learn_only or needs_approval:
        execution = RepairExecution(
            execution_id=f"planned-{pr.pr_number}",
            pr_ref=pr,
            plan_id=plan.plan_id,
            mode=config.mode,
            status="approval_required" if needs_approval else "planned_only",
        )

    executions: list[RepairExecution] = []
    if execution is not None:
        executions.append(execution)

    # Manual lane closure (default-off): apply eligible LLM proposals through the
    # same verify/rollback rails, after the deterministic autofix.
    llm_execution = _maybe_apply_llm_proposals(
        config, pr, route.manual, proposals, llm_client, repo_root
    )
    if llm_execution is not None:
        executions.append(llm_execution)
        store.write_json(
            f"prs/pr_{pr.pr_number}/llm_repair_execution.json",
            llm_execution.model_dump(mode="json"),
        )

    pr_comment = build_pr_comment(
        execution or _planned_execution_stub(plan), classified_findings, proposals
    )
    if config.post_comment:
        _post_implementer_comment(config, pr, pr_comment)
    report = write_pr_artifacts(
        store=store,
        bundle=bundle,
        deduped_findings=findings,
        classified_findings=classified_findings,
        plan=plan,
        execution=execution,
        pr_comment=pr_comment,
    )
    log_event(
        "pr_pipeline_complete",
        pr_number=pr.pr_number,
        plan_id=plan.plan_id,
        mode=config.mode.value,
        execution_status=execution.status if execution is not None else "not_executed",
    )

    write_run_artifacts(
        store=store,
        candidate_prs=[pr.model_dump(mode="json")],
        merged_findings=classified_findings,
        plans=[plan],
        executions=executions,
        reports=[report],
    )

    # Per-rule autofix telemetry feeds the CI shadow->blocking promotion cycle.
    autofix_telemetry = build_autofix_telemetry(route.autofix, executions)
    store.write_json(f"prs/pr_{pr.pr_number}/autofix_telemetry.json", autofix_telemetry)
    log_event(
        "autofix_telemetry_emitted",
        pr_number=pr.pr_number,
        promotion_candidates=autofix_telemetry["promotion_candidates"],
        false_positive_rules=autofix_telemetry["false_positive_rules"],
    )

    packets = extract_learning_packets(executions)
    agent_payload = build_agent_md_recommendations(packets)
    validator_payload = build_validator_recommendations(packets)
    write_learning_artifacts(store, packets, agent_payload, validator_payload)

    runtime_manager.complete(run_state)
    return 0


def _maybe_apply_llm_proposals(
    config: AppConfig,
    pr: PRRef,
    manual_findings: list[Finding],
    proposals: list[ProposedPatch],
    llm_client: LLMClient,
    repo_root: Path,
) -> RepairExecution | None:
    """Run the LLM apply-loop when explicitly enabled and there is eligible work."""
    if not config.llm_apply:
        return None
    if config.mode not in {ExecutionMode.repair_and_verify, ExecutionMode.repair_verify_and_push}:
        return None

    def select(by_id: dict[str, ProposedPatch]) -> list[Proposal]:
        return [
            (finding, by_id[finding.finding_id])
            for finding in manual_findings
            if finding.finding_id in by_id
            and is_apply_eligible(finding, by_id[finding.finding_id], config.write_ceiling)
        ]

    applicable = select({proposal.finding_id: proposal for proposal in proposals})
    if not applicable:
        return None

    def regenerate(stderr: str) -> list[Proposal]:
        retry = propose_repairs(
            manual_findings, llm_client, repo_root, config.llm_client_id, feedback=stderr
        )
        return select({proposal.finding_id: proposal for proposal in retry})

    return apply_llm_proposals(pr, applicable, config, repo_root, regenerate)


def _post_implementer_comment(config: AppConfig, pr: PRRef, body: str) -> None:
    """Post/refresh the single marker-keyed Implementer Bot comment on the PR."""
    from pr_repair.connectors.github import GitHubConnector

    try:
        connector = GitHubConnector(config.github_token)
        upsert_implementer_comment(connector, pr, body)
        log_event("implementer_comment_upserted", pr_number=pr.pr_number)
    except Exception as exc:  # posting must never break the local repair pipeline
        log_event("implementer_comment_failed", pr_number=pr.pr_number, error=str(exc))


def _planned_execution_stub(plan) -> RepairExecution:
    return RepairExecution(
        execution_id=f"plan-{plan.pr_ref.pr_number}",
        pr_ref=plan.pr_ref,
        plan_id=plan.plan_id,
        mode=plan.execution_mode,
        status="planned_only",
    )
