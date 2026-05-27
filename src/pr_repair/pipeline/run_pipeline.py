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
from pr_repair.ingestion.comment_ingestor import ingest_comment_findings
from pr_repair.ingestion.pr_collector import collect_candidate_prs
from pr_repair.ingestion.tool_finding_ingestor import ingest_tool_findings
from pr_repair.learning.agent_md_recommender import build_agent_md_recommendations
from pr_repair.learning.pattern_extractor import extract_learning_packets
from pr_repair.learning.validator_recommender import build_validator_recommendations
from pr_repair.logging import configure_logging, log_event
from pr_repair.normalization.deduper import dedupe_findings
from pr_repair.normalization.normalizer import normalize_bundle
from pr_repair.output.artifact_writer import (
    write_learning_artifacts,
    write_pr_artifacts,
    write_run_artifacts,
)
from pr_repair.output.pr_commentary import build_pr_comment
from pr_repair.planning.approval_gate import requires_human_approval
from pr_repair.planning.repair_planner import build_repair_plan
from pr_repair.repo_context.loader import load_repo_context
from pr_repair.runtime import RuntimeManager
from pr_repair.state_store import StateStore
from pr_repair.types import ExecutionMode, RepairExecution
from pr_repair.repair.repair_executor import execute_repair_plan


def run_pipeline(config: AppConfig) -> int:
    configure_logging()
    repo_root = Path.cwd()
    repo_context = load_repo_context(repo_root, write_ceiling=config.write_ceiling)
    store = StateStore(config.output_dir)
    runtime_manager = RuntimeManager(config.output_dir)
    run_state = runtime_manager.create_run(
        repo=config.github_repository,
        mode=config.mode,
        current_phase="collect_candidate_prs",
    )

    candidate_prs = collect_candidate_prs(config)
    run_state = run_state.model_copy(update={"pr_numbers": [pr.pr_number for pr in candidate_prs]})
    store.write_runtime_state(run_state)

    merged_findings = []
    plans = []
    executions: list[RepairExecution] = []
    reports = []

    for pr in candidate_prs:
        run_state = runtime_manager.update_phase(run_state, f"process_pr_{pr.pr_number}")
        bundle = ingest_tool_findings(config, pr, state_store=store)
        bundle = ingest_comment_findings(config, pr, bundle, state_store=store)
        bundle = normalize_bundle(bundle)

        normalized_findings = (
            bundle.coderabbit_findings
            + bundle.codecov_findings
            + bundle.github_check_findings
            + bundle.github_comment_findings
        )
        deduped_findings = dedupe_findings(normalized_findings)
        classified_findings = classify_findings(deduped_findings, repo_context)
        bundle = bundle.model_copy(update={"merged_findings": normalized_findings})
        merged_findings.extend(classified_findings)

        plan = build_repair_plan(pr, classified_findings, config)
        plans.append(plan)

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

        if execution is not None:
            executions.append(execution)

        pr_comment = build_pr_comment(execution or _planned_execution_stub(plan), classified_findings)
        report = write_pr_artifacts(
            store=store,
            bundle=bundle,
            deduped_findings=deduped_findings,
            classified_findings=classified_findings,
            plan=plan,
            execution=execution,
            pr_comment=pr_comment,
        )
        reports.append(report)
        log_event(
            "pr_pipeline_complete",
            pr_number=pr.pr_number,
            plan_id=plan.plan_id,
            mode=config.mode.value,
            execution_status=execution.status if execution is not None else "not_executed",
        )

    write_run_artifacts(
        store=store,
        candidate_prs=[pr.model_dump(mode="json") for pr in candidate_prs],
        merged_findings=merged_findings,
        plans=plans,
        executions=executions,
        reports=reports,
    )

    packets = extract_learning_packets(executions)
    agent_payload = build_agent_md_recommendations(packets)
    validator_payload = build_validator_recommendations(packets)
    write_learning_artifacts(store, packets, agent_payload, validator_payload)

    runtime_manager.complete(run_state)
    return 0


def _planned_execution_stub(plan) -> RepairExecution:
    return RepairExecution(
        execution_id=f"plan-{plan.pr_ref.pr_number}",
        pr_ref=plan.pr_ref,
        plan_id=plan.plan_id,
        mode=plan.execution_mode,
        status="planned_only",
    )
