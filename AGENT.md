# AGENT.md — L9 Implementer Bot Governance

> Required repo-context document. `load_repo_context` fails closed without it.
> Defines the bot's authority, tiers, protected paths, and the per-tool review
> actuation layer.

## Authority

The Implementer Bot is the **actuator**: it may edit files, commit, and (only when
explicitly enabled) push to a PR branch. **It never merges, approves, or overrides
a human or another bot.** It fails closed on missing/invalid input.

## Tier model and write ceiling

Targets are tiered T0–T5; the bot acts only at or below its **write ceiling**
(`PR_FIX_WRITE_CEILING`, default **T1**). T3+ and protected paths are proposal-only.

## Protected / skip-review paths

Protected paths (never auto-edited; see `repo_context/path_policy.py`): `app/engines/*`,
`app/models/**`, `kb/**`, `.github/workflows/**`, `GUARDRAILS.md`, `AGENTS.md`,
`CLAUDE.md`, `Dockerfile`, `docker-compose*.yml`.

## Bifurcated lanes + trust-but-verify

Deterministic autofix (exact `replacement_text`, exact lines, no fuzzy matching)
vs LLM-assisted manual proposals via the shared `@quantum-l9/llm-router`. Every
applied repair runs `make agent-check` and is **rolled back on failure**.

## Per-tool review actuation layer

After a review tool finishes on a PR, a tool-aligned adapter reads its findings,
normalizes them into the canonical payload, routes them (deterministic vs LLM by
the fix matrix), fixes or proposes, and **replies + resolves the thread**. Secrets
(GitGuardian) are never auto-patched — the bot justifies and leaves the thread for
human rotation.

### key_module_map (actuation layer)

| Module | Responsibility |
| --- | --- |
| `server/github_webhook.py` | Normalize events; attribute originating tool (`NormalizedPREvent.tool`) |
| `tools/base.py` | `ToolAdapter` protocol + suggestion/thread helpers |
| `tools/{copilot,coderabbit,sonar,gitguardian}.py` | Concrete per-tool adapters (own login/slug/shape) |
| `tools/registry.py` | Event → adapter, gated by `config.enabled_tools` |
| `tools/responder.py` | Reply "Fixed"/proposal/justification + resolve (connector only) |
| `routing/fix_matrix.py` + `contracts/fix_matrix.yaml` | `(tool, rule_id\|tag\|category, complexity) → FixStrategy` |
| `llm/model_router.py` | Complexity → `ModelTier`/`Depth`/effort (`ResolvedLLMConfig`, EIE-ported) |
| `orchestration/tool_dispatcher.py` | Adapter → classify → route → fix/propose → respond; emits `fixes/<id>.json` |
| `connectors/github.py` | Only transport authority: reply/resolve/comment; no merge/push/branch mutation |

## Auditability

Every run leaves `run_trace.json` (incl. `model_resolved` with `resolution_reason`
+ `estimated_cost`), `prs/pr_<n>/autofix_telemetry.json`, and per-finding
`prs/pr_<n>/fixes/<finding_id>.json` (diff/change, strategy, resolved tier/depth,
verification, thread reply, outcome). Secrets are redacted before any log/artifact.
