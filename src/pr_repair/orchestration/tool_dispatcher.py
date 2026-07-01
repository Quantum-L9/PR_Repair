# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [orchestration]
# tags: [per-tool, dispatch, actuation]
# owner: platform
# status: active
# --- /L9_META ---

"""Per-tool actuation dispatcher.

Ties a tool adapter to the existing bifurcated pipeline without modifying the
PRLoopOrchestrator state machine:

    adapter.read_findings → adapter.to_payload_findings → Finding
      → classify → route → (autofix: plan+execute | manual: propose)
      → ToolThreadResponder replies + resolves per thread.

Read-only unless ``config.mode`` permits repair; the responder only writes when
``config.post_comment`` is set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pr_repair.classification.classifier import classify_findings
from pr_repair.config import AppConfig
from pr_repair.llm import build_llm_client
from pr_repair.llm.model_router import FindingSignals, resolve_for_finding
from pr_repair.logging import log_event
from pr_repair.normalization.fingerprint import build_finding_fingerprint
from pr_repair.planning.llm_proposer import propose_repairs
from pr_repair.planning.repair_planner import build_repair_plan
from pr_repair.priorities import SOURCE_PRIORITY
from pr_repair.repair.repair_executor import execute_repair_plan
from pr_repair.routing.fix_matrix import FixStrategy, FixStrategyRegistry, load_fix_matrix
from pr_repair.repo_context.loader import load_repo_context
from pr_repair.state_store import StateStore
from pr_repair.tools.base import ToolAdapter
from pr_repair.tools.responder import ResponderResult, ToolThreadResponder
from pr_repair.types import (
    ExecutionMode,
    Finding,
    PRRef,
    ReviewDisposition,
    Severity,
    SourceName,
)

_REPAIR_MODES = {ExecutionMode.repair_and_verify, ExecutionMode.repair_verify_and_push}


@dataclass(frozen=True)
class _Route:
    autofix: list[Finding]
    manual: list[Finding]


@dataclass
class DispatchResult:
    handled: bool
    tool: str | None = None
    autofix: int = 0
    manual: int = 0
    responses: list[ResponderResult] = field(default_factory=list)


def run_tool_actuation(
    adapter: ToolAdapter,
    pr_ref: PRRef,
    config: AppConfig,
    connector: Any,
    repo_root: Path,
    responder: ToolThreadResponder | None = None,
    registry: FixStrategyRegistry | None = None,
) -> DispatchResult:
    """Run one tool's findings through the pipeline and respond per thread."""
    repo_context = load_repo_context(repo_root, write_ceiling=config.write_ceiling)
    responder = responder or ToolThreadResponder(connector, post_comment=config.post_comment)
    registry = registry or load_fix_matrix(config.fix_matrix_path)
    store = StateStore(config.output_dir)

    items = adapter.to_payload_findings(adapter.read_findings(pr_ref, connector))
    findings = [_to_finding(item, pr_ref) for item in items]
    if not findings:
        return DispatchResult(handled=True, tool=adapter.tool_name)

    classified = classify_findings(findings, repo_context)

    # The fix matrix resolves each finding to a strategy (deterministic handler
    # or an LLM tier/depth descriptor). Lane selection: a finding with an exact
    # replacement runs the deterministic lane; everything else is manual, where
    # the strategy carries the model tier/depth honored in Phase 3.
    strategies = {f.finding_id: registry.resolve(f) for f in classified}
    autofix_findings = [f for f in classified if f.replacement_text is not None]
    manual_findings = [f for f in classified if f.replacement_text is None]
    route = _Route(autofix_findings, manual_findings)
    log_event(
        "tool_actuation_routed",
        tool=adapter.tool_name,
        pr_number=pr_ref.pr_number,
        autofix=len(route.autofix),
        manual=len(route.manual),
        matrix_version=registry.version,
    )

    responses: list[ResponderResult] = []

    # Deterministic autofix lane: plan + execute (verify/rollback) when permitted.
    if route.autofix:
        plan = build_repair_plan(pr_ref, route.autofix, config)
        execution = execute_repair_plan(plan, config, repo_root) if config.mode in _REPAIR_MODES else None
        applied = set(execution.modified_files) if execution is not None else set()
        commit_sha = _commit_sha(execution.push_result) if execution is not None else None
        for finding in route.autofix:
            strategy = strategies[finding.finding_id]
            if execution is not None and execution.status == "completed" and finding.file_path in applied:
                result = responder.respond(pr_ref, finding, "fixed", commit_sha=commit_sha)
            else:
                result = responder.respond(
                    pr_ref, finding, "justified_skip",
                    detail="Deterministic autofix did not apply (gated or verification failed); left for review.",
                )
            responses.append(result)
            _write_fix_report(
                store, pr_ref, finding, result, strategy,
                resolved=None, execution=execution, commit_sha=commit_sha,
            )

    # Manual lane: resolve each finding to a model tier/depth (EIE-style), emit an
    # auditable model_resolved trace event, then request bounded LLM proposals.
    if route.manual:
        resolved_by_id = {}
        for finding in route.manual:
            resolved = resolve_for_finding(
                finding,
                strategies[finding.finding_id],
                FindingSignals(
                    protected_path=finding.protected_path,
                    contract_ids=tuple(finding.contract_ids),
                    tool=finding.tool,
                ),
            )
            resolved_by_id[finding.finding_id] = resolved
            log_event(
                "model_resolved",
                finding_id=finding.finding_id,
                tier=resolved.tier.value,
                depth=resolved.depth.value,
                effort=resolved.effort,
                estimated_cost=resolved.estimated_cost,
                resolution_reason=resolved.resolution_reason,
            )
        proposals = propose_repairs(
            route.manual, build_llm_client(config), repo_root, config.llm_client_id,
            resolved_by_id=resolved_by_id,
        )
        by_id = {p.finding_id: p for p in proposals}
        for finding in route.manual:
            proposal = by_id.get(finding.finding_id)
            resolved = resolved_by_id[finding.finding_id]
            if proposal is not None and not proposal.abstained:
                tier_note = f" (router tier: {resolved.tier.value}, depth: {resolved.depth.value})"
                result = responder.respond(
                    pr_ref, finding, "proposed", detail=f"{proposal.rationale}{tier_note}"
                )
            else:
                result = responder.respond(
                    pr_ref, finding, "justified_skip",
                    detail="No bounded automated fix available; needs human review.",
                )
            responses.append(result)
            _write_fix_report(
                store, pr_ref, finding, result, strategies[finding.finding_id],
                resolved=resolved, execution=None, commit_sha=None,
            )

    return DispatchResult(
        handled=True,
        tool=adapter.tool_name,
        autofix=len(route.autofix),
        manual=len(route.manual),
        responses=responses,
    )


def _to_finding(item: dict[str, Any], pr_ref: PRRef) -> Finding:
    disposition = (
        ReviewDisposition.autofix
        if item.get("_disposition") == "autofix"
        else ReviewDisposition.manual_review
    )
    is_autofix = disposition is ReviewDisposition.autofix
    finding = Finding(
        finding_id=str(item["finding_id"]),
        pr_number=pr_ref.pr_number,
        source_name=SourceName.agent_review,
        source_priority=SOURCE_PRIORITY[SourceName.agent_review],
        severity=Severity(item.get("severity", "medium")),
        category=str(item.get("category", "review_comment")),
        message=str(item["message"]),
        file_path=item.get("file_path"),
        line_start=item.get("line_start"),
        line_end=item.get("line_end"),
        replacement_text=item.get("replacement_text"),
        rule_id=item.get("rule_id"),
        review_disposition=disposition,
        evidence_url=item.get("evidence_url"),
        tags=list(item.get("tags", [])),
        tool=item.get("tool"),
        thread_id=item.get("thread_id"),
        comment_id=item.get("comment_id"),
        repairable=is_autofix,
        confidence=1.0 if is_autofix else 0.7,
        fingerprint="pending",
    )
    return finding.model_copy(update={"fingerprint": build_finding_fingerprint(finding)})


def _commit_sha(push_result: str | None) -> str | None:
    if push_result and push_result.startswith("pushed:"):
        return push_result.split(":", 1)[1]
    return None


def _write_fix_report(
    store: StateStore,
    pr_ref: PRRef,
    finding: Finding,
    result: ResponderResult,
    strategy: FixStrategy,
    *,
    resolved: Any,
    execution: Any,
    commit_sha: str | None,
) -> None:
    """Emit the auditable per-finding fix record: prs/pr_<n>/fixes/<id>.json.

    Captures the change, the strategy (deterministic handler or resolved LLM
    tier/depth + resolution_reason), verification, the thread reply, and outcome.
    """
    report: dict[str, Any] = {
        "finding_id": finding.finding_id,
        "tool": finding.tool,
        "category": finding.category,
        "file_path": finding.file_path,
        "line_start": finding.line_start,
        "line_end": finding.line_end,
        "outcome": "fixed" if result.resolved else ("proposed" if "Proposal" in result.body else "justified_skip"),
        "strategy": {
            "kind": strategy.kind,
            "handler": strategy.handler,
            "matched_by": strategy.matched_by,
        },
        "change": {"replacement_text": finding.replacement_text} if finding.replacement_text else None,
        "commit_sha": commit_sha,
        "thread": {
            "thread_id": finding.thread_id,
            "comment_id": finding.comment_id,
            "replied": result.replied,
            "resolved": result.resolved,
            "reply_body": result.body,
        },
    }
    if resolved is not None:
        report["resolved_llm"] = {
            "tier": resolved.tier.value,
            "model": resolved.model,
            "depth": resolved.depth.value,
            "effort": resolved.effort,
            "estimated_cost": resolved.estimated_cost,
            "resolution_reason": resolved.resolution_reason,
        }
    if execution is not None and execution.verification_result is not None:
        report["verification"] = {
            "success": execution.verification_result.success,
            "exit_code": execution.verification_result.exit_code,
        }
    store.write_json(f"prs/pr_{pr_ref.pr_number}/fixes/{finding.finding_id}.json", report)
