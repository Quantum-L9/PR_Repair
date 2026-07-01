# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [output]
# tags: [commentary, pr, trio-governance, marker]
# owner: platform
# status: active
# --- /L9_META ---

"""Trio Governance PR output contract.

Every Implementer Bot comment is keyed on a single persistent marker and renders
a fixed four-column status table so the constellation's other bots (Audit,
Validator) never collide with it. The bot maintains exactly ONE comment per PR
via update-or-create.
"""

from __future__ import annotations

from typing import Protocol

from pr_repair.llm.contract import ProposedPatch
from pr_repair.types import Finding, PRRef, RepairExecution, ReviewDisposition

MARKER = "<!-- L9:IMPLEMENTER_BOT -->"
_TABLE_HEADER = "| Finding | Source | Patch Applied | Verification Status |"
_TABLE_DIVIDER = "| --- | --- | --- | --- |"


class _CommentConnector(Protocol):
    def get_issue_comments(
        self, repo_owner: str, repo_name: str, pr_number: int
    ) -> list[dict[str, object]]: ...

    def post_pr_comment(
        self, repo_owner: str, repo_name: str, pr_number: int, body: str
    ) -> dict[str, object]: ...

    def update_issue_comment(
        self, repo_owner: str, repo_name: str, comment_id: int, body: str
    ) -> dict[str, object]: ...

    def delete_issue_comment(
        self, repo_owner: str, repo_name: str, comment_id: int
    ) -> None: ...


def build_pr_comment(
    execution: RepairExecution,
    findings: list[Finding] | None = None,
    proposals: list[ProposedPatch] | None = None,
) -> str:
    """Render the single Trio Governance status comment.

    Always carries the persistent marker, a four-column status table, and a
    details section for contract-tagged findings.
    """
    findings = findings or []
    proposals_by_id = {p.finding_id: p for p in (proposals or [])}
    verification = _verification_summary(execution)

    lines = [
        MARKER,
        "## L9 Implementer Bot",
        "",
        f"Status: `{execution.status}` · Verification: {verification}",
        "",
        _TABLE_HEADER,
        _TABLE_DIVIDER,
    ]
    if findings:
        for finding in findings:
            lines.append(_table_row(finding, execution, proposals_by_id.get(finding.finding_id)))
    else:
        lines.append("| _no findings_ | — | — | — |")

    detail_blocks = [block for finding in findings for block in [_build_violation_block(finding)] if block]
    if detail_blocks:
        lines.extend(["", "### Contract violations", ""])
        lines.extend(detail_blocks)

    return "\n".join(lines) + "\n"


def upsert_implementer_comment(
    connector: _CommentConnector, pr: PRRef, body: str
) -> dict[str, object]:
    """Maintain exactly one marker-keyed comment per PR: update if present, else create."""
    # The marker must LEAD the body (Trio Governance protocol). Requiring it at the
    # start prevents collisions with comments that merely quote the marker.
    if not body.startswith(MARKER):
        msg = "implementer comment body must start with the L9 marker"
        raise ValueError(msg)

    existing = connector.get_issue_comments(pr.repo_owner, pr.repo_name, pr.pr_number)
    marker_ids: list[int] = []
    for comment in existing:
        body_value = comment.get("body")
        id_value = comment.get("id")
        if isinstance(body_value, str) and body_value.startswith(MARKER) and isinstance(id_value, int):
            marker_ids.append(id_value)
    if not marker_ids:
        return connector.post_pr_comment(pr.repo_owner, pr.repo_name, pr.pr_number, body)

    # Converge to exactly one: update the first marker comment and delete any
    # historical duplicates so the "single marker-keyed comment" contract holds.
    primary_id, *duplicate_ids = marker_ids
    for duplicate_id in duplicate_ids:
        connector.delete_issue_comment(pr.repo_owner, pr.repo_name, duplicate_id)
    return connector.update_issue_comment(pr.repo_owner, pr.repo_name, primary_id, body)


def _table_row(
    finding: Finding, execution: RepairExecution, proposal: ProposedPatch | None
) -> str:
    name = f"`{finding.finding_id}` {finding.category}"
    source = _source_label(finding)
    patch = _patch_status(finding, execution, proposal)
    verification = _verification_summary(execution)
    return f"| {name} | {source} | {patch} | {verification} |"


def _source_label(finding: Finding) -> str:
    if finding.review_disposition is ReviewDisposition.autofix:
        return "agent_review · autofix"
    if finding.review_disposition is ReviewDisposition.manual_review:
        return "agent_review · manual"
    return finding.source_name.value


def _patch_status(
    finding: Finding, execution: RepairExecution, proposal: ProposedPatch | None
) -> str:
    if finding.review_disposition is ReviewDisposition.autofix:
        if execution.status == "completed" and finding.file_path in execution.modified_files:
            return "✅ applied"
        if execution.status == "rolled_back_verification_failed":
            return "↩️ rolled back"
        if execution.status in {"approval_required", "planned_only"}:
            return "⏳ planned"
        return "—"
    if finding.review_disposition is ReviewDisposition.manual_review:
        if proposal is not None and not proposal.abstained:
            return "📝 proposed"
        return "👤 manual"
    return "—"


def _verification_summary(execution: RepairExecution) -> str:
    if execution.verification_result is None:
        return "not run"
    if execution.verification_result.success:
        return "✅ passing"
    return f"❌ failed (exit {execution.verification_result.exit_code})"


def _build_violation_block(finding: Finding) -> str | None:
    if not finding.contract_ids:
        return None
    contract_id = finding.contract_ids[0]
    line = finding.line_start if finding.line_start is not None else "unknown"
    path = finding.file_path or "<repo-wide>"
    required = finding.suggested_fix or "manual review required"
    evidence = ", ".join(finding.repo_rule_sources) if finding.repo_rule_sources else "repo governance context"
    return (
        f"CONTRACT {contract_id} VIOLATION — {finding.category}\n"
        f"File: {path} Line: {line}\n"
        f"Found: {finding.message}\n"
        f"Required: {required}\n"
        f"Evidence: {evidence}"
    )
