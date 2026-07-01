# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [routing]
# tags: [fix-matrix, strategy, dispatch]
# owner: platform
# status: active
# --- /L9_META ---

"""Data-driven fix-strategy matrix.

Resolves each finding to a concrete :class:`FixStrategy` from a committed YAML
matrix. Match priority (most specific wins): ``rule_id`` > ``tag`` > ``category``
> wildcard; ``tool``/``complexity`` are additional constraints. Unmatched
findings fall through to the matrix ``no_match_behavior`` (``propose_only``),
so nothing is ever auto-applied by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from pr_repair.errors import RepoContextError
from pr_repair.llm.task_mapping import finding_complexity
from pr_repair.types import Finding

DEFAULT_MATRIX_PATH = Path(__file__).resolve().parents[3] / "contracts" / "fix_matrix.yaml"

StrategyKind = Literal["deterministic", "llm", "propose_only"]

# Specificity weights for match dimensions (most specific wins).
_RULE_ID_WEIGHT = 100
_TAG_WEIGHT = 10
_CATEGORY_WEIGHT = 5
_WILDCARD_WEIGHT = 1


@dataclass(frozen=True)
class FixStrategy:
    """A resolved handling decision for one finding."""

    kind: StrategyKind
    handler: str | None = None            # deterministic handler name
    task_type: str | None = None          # llm
    tier: str | None = None               # llm model/tier hint
    depth: str | None = None              # llm search/context depth
    risk: str | None = None
    matched_by: str = "no_match"          # audit: which dimension matched


_PROPOSE_ONLY = FixStrategy(kind="propose_only", matched_by="no_match")


class FixStrategyRegistry:
    """Resolves findings to fix strategies from a loaded matrix."""

    def __init__(self, version: int, no_match_behavior: str, rules: list[dict[str, Any]]) -> None:
        self.version = version
        self.no_match_behavior = no_match_behavior
        self._rules = rules

    def resolve(self, finding: Finding) -> FixStrategy:
        complexity = finding_complexity(finding)
        best: tuple[int, FixStrategy] | None = None
        for rule in self._rules:
            match = rule.get("match", {})
            score = _match_score(match, finding, complexity)
            if score is None:
                continue
            strategy = _build_strategy(rule.get("strategy", {}), matched_by=_matched_by(match))
            if best is None or score > best[0]:
                best = (score, strategy)
        if best is not None:
            return best[1]
        if self.no_match_behavior == "propose_only":
            return _PROPOSE_ONLY
        return FixStrategy(kind="propose_only", matched_by="no_match")


def load_fix_matrix(path: Path | str | None = None) -> FixStrategyRegistry:
    matrix_path = Path(path) if path is not None else DEFAULT_MATRIX_PATH
    # A cwd-relative config path (e.g. "contracts/fix_matrix.yaml") only resolves
    # when running inside the PR_Repair checkout. When the bot runs against another
    # repo, fall back to the matrix packaged with the install.
    if not matrix_path.exists() and matrix_path != DEFAULT_MATRIX_PATH:
        matrix_path = DEFAULT_MATRIX_PATH
    try:
        raw = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"unable to read fix matrix at {matrix_path}: {exc}"
        raise RepoContextError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"fix matrix at {matrix_path} must be a mapping"
        raise RepoContextError(msg)
    version = raw.get("version")
    if not isinstance(version, int):
        msg = f"fix matrix at {matrix_path} is missing an integer 'version'"
        raise RepoContextError(msg)
    rules = raw.get("rules", [])
    if not isinstance(rules, list):
        msg = f"fix matrix at {matrix_path} 'rules' must be a list"
        raise RepoContextError(msg)
    return FixStrategyRegistry(
        version=version,
        no_match_behavior=str(raw.get("no_match_behavior", "propose_only")),
        rules=[r for r in rules if isinstance(r, dict)],
    )


def _match_score(match: dict[str, Any], finding: Finding, complexity: str) -> int | None:
    """Return a specificity score if the rule matches the finding, else None."""
    if match.get("*") is True:
        return _WILDCARD_WEIGHT
    score = 0
    # Additional constraints — must match when present, contribute little weight.
    if "tool" in match:
        if finding.tool != match["tool"]:
            return None
        score += 2
    if "complexity" in match:
        if complexity != match["complexity"]:
            return None
        score += 2
    # Primary dimensions — most specific present decides the base weight.
    if "rule_id" in match:
        if finding.rule_id != match["rule_id"]:
            return None
        score += _RULE_ID_WEIGHT
    if "tag" in match:
        if match["tag"] not in finding.tags:
            return None
        score += _TAG_WEIGHT
    if "category" in match:
        if finding.category != match["category"]:
            return None
        score += _CATEGORY_WEIGHT
    # A rule with only tool/complexity constraints (no primary dimension) still
    # matches, but ranks below any primary-dimension rule.
    return score if score > 0 else None


def _matched_by(match: dict[str, Any]) -> str:
    for key in ("rule_id", "tag", "category"):
        if key in match:
            return key
    if match.get("*") is True:
        return "wildcard"
    return "constraint"


def _build_strategy(spec: dict[str, Any], *, matched_by: str) -> FixStrategy:
    kind = str(spec.get("kind", "propose_only"))
    if kind not in ("deterministic", "llm", "propose_only"):
        kind = "propose_only"
    return FixStrategy(
        kind=kind,  # type: ignore[arg-type]
        handler=spec.get("handler"),
        task_type=spec.get("task_type"),
        tier=spec.get("tier"),
        depth=spec.get("depth"),
        risk=spec.get("risk"),
        matched_by=matched_by,
    )
