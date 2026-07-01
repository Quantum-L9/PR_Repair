# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [orchestration]
# tags: [router, bifurcation, autofix, manual-review]
# owner: platform
# status: active
# --- /L9_META ---

"""Bifurcated actuator router.

Splits agent-review findings into two disjoint execution lanes:

- ``autofix``  -> deterministic Semgrep replacements. These carry an exact
  ``replacement_text`` and an exact line range. They bypass the planner/LLM
  entirely; ``patch_generator`` translates them by exact line-number mapping
  (no fuzzy matching).
- ``manual``   -> complex findings that require the LLM-assisted repair planner.

The split is driven solely by the upstream ``review_disposition`` stamped by the
PayloadParser, so routing is deterministic and never re-derived from text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pr_repair.logging import log_event
from pr_repair.types import Finding, ReviewDisposition


@dataclass(slots=True)
class RouteResult:
    """Disjoint partition of findings into deterministic vs. LLM-assisted lanes."""

    autofix: list[Finding] = field(default_factory=list)
    manual: list[Finding] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.autofix) + len(self.manual)


def route_findings(findings: list[Finding]) -> RouteResult:
    """Partition findings by their upstream review disposition."""
    result = RouteResult()
    for finding in findings:
        if finding.review_disposition is ReviewDisposition.autofix:
            result.autofix.append(finding)
        else:
            result.manual.append(finding)
    log_event(
        "findings_routed",
        autofix=len(result.autofix),
        manual=len(result.manual),
    )
    return result
