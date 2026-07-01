# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [llm]
# tags: [model-router, tier, depth, complexity, cost]
# owner: platform
# status: active
# --- /L9_META ---

"""Complexity -> (model tier, depth, effort) resolver.

A direct port of Enrichment.Inference.Engine's ``app/engines/search_optimizer.py``
(`SonarModel`/`SearchContextSize`/`FieldDifficulty`/`_pick_model`/
`_pick_context_size`/`_pick_reasoning_effort` -> `SonarConfig`), substituting the
LLM-repair domain for the Perplexity-search domain:

    SonarModel          -> ModelTier   (haiku | mistral-large | opus | opus-deep)
    SearchContextSize   -> Depth        (low | medium | high)
    FieldDifficulty     -> finding complexity (severity + category/tags)
    EntitySignals       -> FindingSignals
    SonarConfig         -> ResolvedLLMConfig (+ estimated_cost, resolution_reason)
    COST_PER_CALL[]     -> COST_PER_TIER[]

The concrete policy is data-driven from ``contracts/fix_matrix.yaml`` (a matched
strategy may pin tier/depth); the resolver applies it plus signal escalation
(bump a tier after repeated failed repairs, as EIE bumps effort on
``failed_matches >= 3``). Every ModelTier is reachable — the EIE dead-tier bug
(``SONAR_DEEP_RESEARCH`` defined but never returned) must not be inherited; see
``tests/unit/test_model_router_reachability.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pr_repair.llm.task_mapping import finding_complexity
from pr_repair.routing.fix_matrix import FixStrategy
from pr_repair.types import Finding


class ModelTier(StrEnum):
    HAIKU = "haiku"
    MISTRAL_LARGE = "mistral-large"
    OPUS = "opus"
    OPUS_DEEP = "opus-deep"


class Depth(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Cheapest -> most capable. Escalation walks up this ladder.
_TIER_LADDER: tuple[ModelTier, ...] = (
    ModelTier.HAIKU,
    ModelTier.MISTRAL_LARGE,
    ModelTier.OPUS,
    ModelTier.OPUS_DEEP,
)

# Reasoning-capable tiers receive an explicit effort level.
_REASONING_TIERS = {ModelTier.OPUS, ModelTier.OPUS_DEEP}

# Indicative per-call USD cost, mirroring EIE's COST_PER_CALL table.
COST_PER_TIER: dict[ModelTier, float] = {
    ModelTier.HAIKU: 0.0008,
    ModelTier.MISTRAL_LARGE: 0.003,
    ModelTier.OPUS: 0.015,
    ModelTier.OPUS_DEEP: 0.030,
}

_COMPLEXITY_TO_TIER: dict[str, ModelTier] = {
    "trivial": ModelTier.HAIKU,
    "low": ModelTier.HAIKU,
    "medium": ModelTier.MISTRAL_LARGE,
    "high": ModelTier.OPUS,
    "critical": ModelTier.OPUS_DEEP,
}

_COMPLEXITY_TO_DEPTH: dict[str, Depth] = {
    "trivial": Depth.LOW,
    "low": Depth.LOW,
    "medium": Depth.MEDIUM,
    "high": Depth.HIGH,
    "critical": Depth.HIGH,
}

_ESCALATION_THRESHOLD = 2


@dataclass(frozen=True)
class FindingSignals:
    """Runtime signals that can escalate the resolved tier/effort."""

    prior_failed_attempts: int = 0
    protected_path: bool = False
    contract_ids: tuple[str, ...] = ()
    tool: str | None = None


@dataclass(frozen=True)
class ResolvedLLMConfig:
    """Fully resolved LLM call parameters (mirrors EIE SonarConfig)."""

    tier: ModelTier
    model: str
    depth: Depth
    effort: str | None
    max_tokens: int
    temperature: float
    estimated_cost: float
    resolution_reason: str = ""


def resolve_for_finding(
    finding: Finding,
    strategy: FixStrategy | None = None,
    signals: FindingSignals | None = None,
) -> ResolvedLLMConfig:
    return resolve_llm_config(finding_complexity(finding), strategy, signals)


def resolve_llm_config(
    complexity: str,
    strategy: FixStrategy | None = None,
    signals: FindingSignals | None = None,
) -> ResolvedLLMConfig:
    signals = signals or FindingSignals()
    force_tier = _tier_from_str(strategy.tier) if strategy is not None else None
    force_depth = _depth_from_str(strategy.depth) if strategy is not None else None

    tier, reasons = _pick_tier(complexity, signals, force_tier)
    depth = _pick_depth(complexity, force_depth)
    effort = _pick_effort(tier, signals)
    cost = COST_PER_TIER[tier]
    reason = _build_resolution_reason(complexity, tier, depth, effort, reasons, cost)

    return ResolvedLLMConfig(
        tier=tier,
        model=tier.value,
        depth=depth,
        effort=effort,
        max_tokens=_max_tokens(depth),
        temperature=0.2,
        estimated_cost=cost,
        resolution_reason=reason,
    )


def _pick_tier(
    complexity: str, signals: FindingSignals, force_tier: ModelTier | None
) -> tuple[ModelTier, list[str]]:
    reasons: list[str] = []
    if force_tier is not None:
        tier = force_tier
        reasons.append(f"matrix pinned tier={tier.value}")
    else:
        tier = _COMPLEXITY_TO_TIER.get(complexity, ModelTier.MISTRAL_LARGE)
        reasons.append(f"complexity={complexity} -> {tier.value}")
    # Escalate up the ladder after repeated failed repairs (EIE-style bump).
    if signals.prior_failed_attempts >= _ESCALATION_THRESHOLD:
        escalated = _escalate(tier)
        if escalated is not tier:
            reasons.append(
                f"{signals.prior_failed_attempts} prior failed attempts -> escalate to {escalated.value}"
            )
            tier = escalated
    return tier, reasons


def _pick_depth(complexity: str, force_depth: Depth | None) -> Depth:
    if force_depth is not None:
        return force_depth
    return _COMPLEXITY_TO_DEPTH.get(complexity, Depth.MEDIUM)


def _pick_effort(tier: ModelTier, signals: FindingSignals) -> str | None:
    if tier not in _REASONING_TIERS:
        return None
    return "high" if signals.prior_failed_attempts >= 1 else "medium"


def _escalate(tier: ModelTier) -> ModelTier:
    index = _TIER_LADDER.index(tier)
    return _TIER_LADDER[min(index + 1, len(_TIER_LADDER) - 1)]


def _tier_from_str(value: str | None) -> ModelTier | None:
    if value is None:
        return None
    try:
        return ModelTier(value)
    except ValueError:
        return None


def _depth_from_str(value: str | None) -> Depth | None:
    if value is None:
        return None
    try:
        return Depth(value)
    except ValueError:
        return None


def _max_tokens(depth: Depth) -> int:
    return {Depth.LOW: 512, Depth.MEDIUM: 1024, Depth.HIGH: 2048}[depth]


def _build_resolution_reason(
    complexity: str,
    tier: ModelTier,
    depth: Depth,
    effort: str | None,
    reasons: list[str],
    cost: float,
) -> str:
    effort_note = f", effort={effort}" if effort else ""
    trail = "; ".join(reasons)
    return f"{trail} => model={tier.value}, depth={depth.value}{effort_note}, est_cost=${cost:.4f}"
