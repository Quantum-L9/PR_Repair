# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [telemetry]
# tags: [telemetry, autofix, semgrep, promotion]
# owner: platform
# status: active
# --- /L9_META ---

"""Per-rule autofix telemetry.

Turns the success/failure of each deterministic Semgrep autofix into the data
the CI platform needs for its shadow->blocking promotion cycle: a rule that
autofixes cleanly every time is safe to promote; a rule whose autofix breaks
verification is a false-positive candidate to demote.
"""

from __future__ import annotations

from pydantic import BaseModel

from pr_repair.types import Finding, RepairExecution


class RuleTelemetry(BaseModel):
    rule_id: str
    attempted: int = 0
    applied: int = 0
    verified: int = 0
    rolled_back: int = 0
    false_positive: int = 0
    success_rate: float = 0.0
    promotable: bool = False


def build_autofix_telemetry(
    autofix_findings: list[Finding],
    executions: list[RepairExecution],
) -> dict[str, object]:
    """Aggregate deterministic autofix outcomes per Semgrep rule id."""
    exec_by_pr = {execution.pr_ref.pr_number: execution for execution in executions}
    by_rule: dict[str, RuleTelemetry] = {}

    for finding in autofix_findings:
        rule_id = finding.rule_id
        if not rule_id:
            continue
        stats = by_rule.setdefault(rule_id, RuleTelemetry(rule_id=rule_id))
        stats.attempted += 1

        execution = exec_by_pr.get(finding.pr_number)
        if execution is None:
            continue
        if rule_id in execution.false_positive_rules:
            stats.false_positive += 1
            stats.rolled_back += 1
        elif execution.status == "completed" and finding.file_path in execution.modified_files:
            stats.applied += 1
            stats.verified += 1

    rules = []
    totals = {"attempted": 0, "applied": 0, "verified": 0, "rolled_back": 0, "false_positive": 0}
    promotion_candidates: list[str] = []
    for rule_id in sorted(by_rule):
        stats = by_rule[rule_id]
        stats.success_rate = round(stats.verified / stats.attempted, 4) if stats.attempted else 0.0
        stats.promotable = stats.attempted > 0 and stats.verified == stats.attempted and stats.false_positive == 0
        if stats.promotable:
            promotion_candidates.append(rule_id)
        for key in totals:
            totals[key] += getattr(stats, key)
        rules.append(stats.model_dump(mode="json"))

    return {
        "rules": rules,
        "totals": totals,
        "promotion_candidates": promotion_candidates,
        "false_positive_rules": sorted(
            {r["rule_id"] for r in rules if r["false_positive"] > 0}
        ),
    }
