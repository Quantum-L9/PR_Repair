# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [normalization]
# tags: [dedupe, precedence, findings]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.priorities import SEVERITY_PRIORITY
from pr_repair.types import Finding


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """
    Deduplicate findings by fingerprint while preserving highest-value signal.
    """
    deduped: dict[str, Finding] = {}
    for finding in findings:
        existing = deduped.get(finding.fingerprint)
        if existing is None or _should_replace(existing, finding):
            deduped[finding.fingerprint] = finding

    ordered = list(deduped.values())
    ordered.sort(
        key=lambda item: (item.source_priority, SEVERITY_PRIORITY[item.severity]),
        reverse=True,
    )
    return ordered


def _should_replace(existing: Finding, candidate: Finding) -> bool:
    if candidate.source_priority != existing.source_priority:
        return candidate.source_priority > existing.source_priority
    if candidate.severity != existing.severity:
        return SEVERITY_PRIORITY[candidate.severity] > SEVERITY_PRIORITY[existing.severity]
    return _richness_score(candidate) > _richness_score(existing)


def _richness_score(finding: Finding) -> int:
    score = 0
    if finding.file_path:
        score += 1
    if finding.line_start is not None:
        score += 1
    if finding.line_end is not None:
        score += 1
    if finding.suggested_fix:
        score += 1
    if finding.evidence_url:
        score += 1
    return score
