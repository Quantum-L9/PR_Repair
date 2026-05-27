# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [output]
# tags: [commentary, pr, review-template]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.types import Finding, RepairExecution


def build_pr_comment(execution: RepairExecution, findings: list[Finding] | None = None) -> str:
    """
    Build repo-aligned PR commentary.

    Rules:
    - contract-tagged findings use structured contract violation format
    - clean executions use a concise status summary
    - output is review-safe and can be posted later by an integration layer
    """
    findings = findings or []
    violation_blocks = [block for finding in findings for block in [_build_violation_block(finding)] if block]
    if violation_blocks:
        return "\n\n".join(violation_blocks)

    verification_summary = "not-run"
    if execution.verification_result is not None:
        verification_summary = (
            "confirmed passing"
            if execution.verification_result.success
            else f"failed exit_code={execution.verification_result.exit_code}"
        )

    return (
        f"PR repair execution summary\n"
        f"Status: {execution.status}\n"
        f"Tier assessment: T1-T2 safe execution path only\n"
        f"make agent-check gates: {verification_summary}\n"
    )


def _build_violation_block(finding: Finding) -> str | None:
    if not finding.contract_ids:
        return None
    contract_id = finding.contract_ids[0]
    line = finding.line_start if finding.line_start is not None else "unknown"
    path = finding.file_path or "<repo-wide>"
    required = finding.suggested_fix or "manual review required"
    return (
        f"CONTRACT {contract_id} VIOLATION — {finding.category}\n"
        f"File: {path} Line: {line}\n"
        f"Found: {finding.message}\n"
        f"Required: {required}\n"
        f"Evidence: {', '.join(finding.repo_rule_sources) if finding.repo_rule_sources else 'repo governance context'}"
    )
