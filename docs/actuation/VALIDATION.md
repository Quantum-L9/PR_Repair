# Per-Tool Review Actuation Layer — Validation & Delta

## Summary

Ships the full Per-Tool Review Actuation Layer across Phases 0–5 as six stacked
PRs (#8–#12 + Phase 5). After a review tool finishes on a PR, a tool-aligned
adapter reads its findings, normalizes them into the canonical payload, routes
them (deterministic vs LLM by the fix matrix), fixes or proposes through the
existing verify/rollback rails, and replies + resolves the thread — leaving a
per-fix audit artifact and an auditable trace.

Final status: **IMPROVED_EXECUTION_READY**. `uv run pytest -q` → **171 passed**;
ruff clean; `node --check router-shim/shim.mjs` OK. mypy --strict advisory
(pre-existing unstubbed-lib baseline; no new error classes).

## Delta (what changed vs the pre-actuation core)

| Area | Before | After |
| --- | --- | --- |
| Ingestion | Single upstream `agent_review_payload.json` | + per-tool adapters normalizing live tool findings into the same contract |
| Lane selection | Implicit (`review_disposition`) | Data-driven `contracts/fix_matrix.yaml` (`rule_id>tag>category>wildcard`) |
| Model choice | Router picks from complexity | PR_Repair resolves tier/depth/effort (`model_router.py`, EIE-ported); router executes |
| Reply loop | Single governance comment | + threaded reply + resolve per finding (connector only) |
| Audit | Run trace + telemetry | + `model_resolved` (cost + reason) + per-finding `fixes/<id>.json` |
| Tools | Copilot (manual) | Copilot, CodeRabbit, Sonar, GitGuardian (per-tool toggles) |

## Boundaries preserved

- `connectors/github.py` is the only transport authority; `ToolThreadResponder`
  owns no HTTP.
- `router-shim/shim.mjs` stays a pass-through (ADR 0001); `model_router.py` is the
  Python resolver; `L9LLMRouter.execute` is the acceptance authority.
- `PRLoopOrchestrator` unchanged; deterministic lane keeps exact-guarded patching.
- Secrets are never auto-patched; protected paths and never-auto-repair categories
  stay proposal-only.

## Residual risks

See `validation_report.yaml` → `unresolved_risks` (external router hint acceptance;
Sonar/GitGuardian live payload shape confirmation).
