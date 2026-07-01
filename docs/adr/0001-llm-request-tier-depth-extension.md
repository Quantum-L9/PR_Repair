# ADR 0001 — LLMRequest tier/depth/effort extension and shim pass-through

- Status: Accepted
- Date: 2026-07-01
- Scope: `src/pr_repair/llm/contract.py`, `router-shim/shim.mjs`, `@quantum-l9/llm-router`

## Context

The per-tool actuation layer selects the best-suited model tier + search depth
per finding complexity (the EIE `app/engines/search_optimizer.py` pattern),
resolved in `src/pr_repair/llm/model_router.py`. The resolved choice must reach
the shared LLM-Router without the Python bot owning the actual model call and
without the TypeScript shim owning routing logic.

## Decision

`LLMRequest` (the Python↔Node bridge contract) is extended with three **optional**
fields:

- `depth: str | None` — search/context depth (`low` | `medium` | `high`)
- `effort: str | None` — reasoning effort for reasoning-capable tiers
- `tier: str | None` — resolved model tier hint (e.g. `mistral-large`, `opus`)

`router-shim/shim.mjs` passes these fields through to `L9LLMRouter.execute` **as-is**.
The shim does not interpret, default, or override them beyond the existing
`complexity`/`task_type` mapping. It remains a thin, stateless pass-through.

`L9LLMRouter.execute` (in `@quantum-l9/llm-router`) is the **acceptance authority**:
it may honor the `tier`/`depth`/`effort` hints or resolve its own model within
policy. If the router does not recognize these fields it ignores them, and the
bot degrades to complexity-only routing — no breakage.

## Consequences

- Backward compatible: all three fields are optional; existing requests are unchanged.
- The routing *policy* (complexity → tier/depth) lives in PR_Repair (`model_router.py`
  + `contracts/fix_matrix.yaml`), auditable via `ResolvedLLMConfig.resolution_reason`.
  The *execution* stays in LLM-Router.
- Language boundary preserved: Python resolves, TS shim relays, router executes.
