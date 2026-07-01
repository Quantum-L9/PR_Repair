# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [reporting]
# tags: [propose-only, report, governance, telemetry, trace]
# owner: platform
# status: active
# --- /L9_META ---

"""Proposal-only reporter.

The read-only sibling of ``run_pipeline``. It consumes the validated
``agent_review_payload.json``, routes findings into the deterministic autofix and
LLM-assisted manual lanes, records per-rule telemetry and an auditable run trace,
and posts the single Trio Governance comment -- **without ever mutating the
repository**. No patch is applied, no branch is pushed.

This backs ``pr-repair report`` and ``PR_FIX_MODE=propose_only``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from pr_repair.classification.classifier import classify_findings
from pr_repair.config import AppConfig
from pr_repair.errors import PayloadIngestionError, StateStoreError
from pr_repair.ingestion.payload_parser import PayloadParser
from pr_repair.llm.contract import ProposedPatch
from pr_repair.logging import configure_logging, log_event
from pr_repair.orchestration.router import RouteResult, route_findings
from pr_repair.output.pr_commentary import build_pr_comment
from pr_repair.planning.llm_proposer import propose_repairs
from pr_repair.repo_context.loader import load_repo_context
from pr_repair.state_store import StateStore
from pr_repair.telemetry import TraceRecorder, build_autofix_telemetry
from pr_repair.types import ExecutionMode, PRRef, RepairExecution, RepoContext


class AutofixCandidate(BaseModel):
    """A deterministic autofix the actuator *would* apply (never applied here)."""

    finding_id: str
    rule_id: str | None = None
    category: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    replacement_text: str | None = None


class ManualProposal(BaseModel):
    """A bounded LLM proposal for a manual-review finding (surfaced, not applied)."""

    finding_id: str
    file_path: str | None = None
    category: str
    actionable: bool = False
    rationale: str = ""
    model: str = ""
    diagnostics: list[str] = Field(default_factory=list)


class ProposalReport(BaseModel):
    """The deterministic, audit-ready summary of a propose-only run."""

    pr_number: int
    repo: str
    mode: str = ExecutionMode.propose_only.value
    schema_version: str
    autofix_candidate_count: int
    manual_finding_count: int
    actionable_proposal_count: int
    autofix_candidates: list[AutofixCandidate] = Field(default_factory=list)
    manual_proposals: list[ManualProposal] = Field(default_factory=list)


def run_report(config: AppConfig) -> int:
    """Run the proposal-only reporter. Returns 0 on success, 2 on fail-closed.

    Read-only: parses the payload, routes findings, writes telemetry + trace, and
    posts the governance comment. Applies nothing.
    """
    configure_logging()
    repo_root = Path.cwd()
    repo_context = load_repo_context(repo_root, write_ceiling=config.write_ceiling)
    store = StateStore(config.output_dir)

    # Capture the full structured-event timeline, written even on a fail-closed
    # exit so every report leaves an auditable trace.
    recorder = TraceRecorder()
    recorder.start()
    try:
        return _run_report_traced(config, repo_root, repo_context, store)
    finally:
        recorder.stop()
        try:
            store.write_json("run_trace.json", recorder.to_list())
        except (StateStoreError, OSError):
            # Trace emission is best-effort and must never change the exit code.
            log_event("run_trace_write_failed")


def _run_report_traced(
    config: AppConfig,
    repo_root: Path,
    repo_context: RepoContext,
    store: StateStore,
) -> int:
    try:
        parsed = PayloadParser(config.payload_path).parse()
    except PayloadIngestionError as exc:
        log_event(
            "payload_ingestion_failed",
            payload_path=str(config.payload_path),
            error=str(exc),
        )
        return 2

    pr = parsed.pr_ref
    log_event(
        "payload_ingested",
        pr_number=pr.pr_number,
        schema_version=parsed.schema_version,
        autofix_candidates=len(parsed.autofix_findings),
        manual_review_required=len(parsed.manual_review_findings),
    )

    findings = parsed.findings
    classified = classify_findings(findings, repo_context)
    route = route_findings(classified)
    log_event(
        "pipeline_routing",
        pr_number=pr.pr_number,
        autofix=len(route.autofix),
        manual=len(route.manual),
    )

    # Manual lane: ask the shared L9 LLM-Router for bounded proposals. With the
    # default NullLLMClient every finding abstains; nothing is ever applied here.
    from pr_repair.llm import build_llm_client

    llm_client = build_llm_client(config)
    proposals = propose_repairs(route.manual, llm_client, repo_root, config.llm_client_id)

    report = build_proposal_report(pr, route, proposals, schema_version=parsed.schema_version)
    store.write_json(
        f"prs/pr_{pr.pr_number}/proposal_report.json",
        report.model_dump(mode="json"),
    )

    # Per-rule telemetry with no executions == a candidate inventory (attempted
    # counts, nothing verified) that still feeds the promotion signal.
    telemetry = build_autofix_telemetry(route.autofix, [])
    store.write_json(f"prs/pr_{pr.pr_number}/autofix_telemetry.json", telemetry)
    log_event(
        "autofix_telemetry_emitted",
        pr_number=pr.pr_number,
        promotion_candidates=telemetry["promotion_candidates"],
        false_positive_rules=telemetry["false_positive_rules"],
    )

    # Single Trio Governance comment. A propose-only run applies nothing, so the
    # stub execution is 'planned_only' -> autofix rows render as planned, manual
    # rows as proposed/manual.
    comment_body = build_pr_comment(_report_execution_stub(pr), classified, proposals)
    store.write_markdown(f"prs/pr_{pr.pr_number}/implementer_comment.md", comment_body)
    if config.post_comment:
        _post_implementer_comment(config, pr, comment_body)

    log_event(
        "report_complete",
        pr_number=pr.pr_number,
        autofix_candidates=report.autofix_candidate_count,
        manual_findings=report.manual_finding_count,
        actionable_proposals=report.actionable_proposal_count,
    )
    return 0


def build_proposal_report(
    pr: PRRef,
    route: RouteResult,
    proposals: list[ProposedPatch],
    schema_version: str,
) -> ProposalReport:
    """Assemble the proposal-only report from the routed lanes and proposals."""
    autofix_candidates = [
        AutofixCandidate(
            finding_id=finding.finding_id,
            rule_id=finding.rule_id,
            category=finding.category,
            file_path=finding.file_path,
            line_start=finding.line_start,
            line_end=finding.line_end,
            replacement_text=finding.replacement_text,
        )
        for finding in route.autofix
    ]

    category_by_id = {finding.finding_id: finding.category for finding in route.manual}
    manual_proposals = [
        ManualProposal(
            finding_id=proposal.finding_id,
            file_path=proposal.file_path,
            category=category_by_id.get(proposal.finding_id, "unknown"),
            actionable=not proposal.abstained and proposal.instruction is not None,
            rationale=proposal.rationale,
            model=proposal.model,
            diagnostics=proposal.diagnostics,
        )
        for proposal in proposals
    ]

    return ProposalReport(
        pr_number=pr.pr_number,
        repo=pr.repo_full_name,
        schema_version=schema_version,
        autofix_candidate_count=len(autofix_candidates),
        manual_finding_count=len(route.manual),
        actionable_proposal_count=sum(1 for p in manual_proposals if p.actionable),
        autofix_candidates=autofix_candidates,
        manual_proposals=manual_proposals,
    )


def _report_execution_stub(pr: PRRef) -> RepairExecution:
    """A non-executing stand-in so the governance table renders 'planned' rows."""
    return RepairExecution(
        execution_id=f"report-{pr.pr_number}",
        pr_ref=pr,
        plan_id=f"report-{pr.pr_number}",
        mode=ExecutionMode.propose_only,
        status="planned_only",
    )


def _post_implementer_comment(config: AppConfig, pr: PRRef, body: str) -> None:
    """Post/refresh the single marker-keyed Implementer Bot comment (gated)."""
    from pr_repair.connectors.github import GitHubConnector
    from pr_repair.output.pr_commentary import upsert_implementer_comment

    try:
        connector = GitHubConnector(config.github_token)
        upsert_implementer_comment(connector, pr, body)
        log_event("implementer_comment_upserted", pr_number=pr.pr_number)
    except Exception as exc:  # posting must never break the local report
        log_event("implementer_comment_failed", pr_number=pr.pr_number, error=str(exc))
