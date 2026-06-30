from __future__ import annotations

from pr_repair.types import Severity, SourceName, TierLevel

SOURCE_PRIORITY = {
    SourceName.agent_review: 110,
    SourceName.coderabbit: 100,
    SourceName.codecov_cloud: 90,
    SourceName.github_checks: 80,
    SourceName.github_review_comments: 50,
    SourceName.github_issue_comments: 40,
}

SEVERITY_PRIORITY = {
    Severity.critical: 4,
    Severity.high: 3,
    Severity.medium: 2,
    Severity.low: 1,
}

TIER_ORDER = {
    TierLevel.t0: 0,
    TierLevel.t1: 1,
    TierLevel.t2: 2,
    TierLevel.t3: 3,
    TierLevel.t4: 4,
    TierLevel.t5: 5,
}


def is_within_write_ceiling(target_tier: TierLevel, write_ceiling: TierLevel) -> bool:
    return TIER_ORDER[target_tier] <= TIER_ORDER[write_ceiling]
