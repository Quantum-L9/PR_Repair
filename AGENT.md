# AGENT.md — L9 Implementer Bot Governance

> This document is the governance contract for the **L9 Implementer Bot**
> (`pr_repair`). It is a required repo-context document: the pipeline refuses to
> run if it is absent (`load_repo_context` raises `RepoContextError`). It defines
> what the bot may touch, how far it may go, and how it must report.

## 1. Identity and authority

The Implementer Bot is the **actuator** in the L9 CI constellation. It consumes a
validated `agent_review_payload.json` (emitted upstream by the Audit Bot / l9-ci)
and turns findings into repairs or proposals.

- **It has write access. It does NOT have merge authority.** The bot may modify
  files, commit, and (only when explicitly enabled) push to the PR branch. It
  never merges, never approves, and never overrides a human or another bot.
- **It is deterministic first.** Findings are pre-classified upstream; the bot
  never re-derives intent from free-text comments.
- **It fails closed.** A missing, malformed, or schema-invalid payload aborts the
  run with a non-zero exit code and produces no repairs.

## 2. Tier model and write ceiling

Every target is assigned a tier. The bot may only act at or below its configured
**write ceiling** (`PR_FIX_WRITE_CEILING`, default **T1**).

| Tier | Meaning | Default authority |
| --- | --- | --- |
| T0 | Formatting / whitespace / comments | auto |
| T1 | Local, mechanical, single-file fixes (lint, rename, import order) | auto (ceiling) |
| T2 | Multi-line / multi-file deterministic fixes | auto only if within ceiling |
| T3 | Behavioral changes requiring judgement | **proposal only** |
| T4 | Architectural / contract-level changes | **proposal only** |
| T5 | Security-sensitive or irreversible changes | **proposal only, human required** |

Anything above the write ceiling is downgraded to a **proposal** — surfaced for
human review, never auto-applied.

## 3. Protected and skip-review paths

Protected paths are **never auto-edited**, regardless of tier. A finding that
targets one is forced to `repairable=False` and can only ever be a proposal.
The current policy (see `repo_context/path_policy.py`) protects:

- `app/engines/chassis_contract.py`, `app/engines/handlers.py`,
  `app/engines/graph_sync_client.py`, `app/models/**`, `kb/**`
- `.github/workflows/**`
- Governance docs: `GUARDRAILS.md`, `AGENTS.md`, `CLAUDE.md`
- Build/runtime: `Dockerfile`, `docker-compose*.yml`

Skip-review paths (`docs/**`, `reports/**`, `*.json`, `coverage.xml`, …) are
treated as non-actionable noise.

## 4. Bifurcated execution lanes

The router splits findings into two disjoint lanes by the upstream
`review_disposition` — never by re-reading text:

- **Autofix lane** — deterministic Semgrep replacements carrying an exact
  `replacement_text` and an exact line range. Applied by exact line-number and
  on-disk-block matching (**no fuzzy matching, ever**). If the on-disk guard
  cannot be captured, the patch is skipped, not guessed.
- **Manual lane** — complex findings routed to the shared **`@quantum-l9/llm-router`**
  for a *bounded patch proposal*. Proposals are surfaced for review; they are
  only applied (behind `PR_FIX_LLM_APPLY`, default off) through the same
  verification + rollback rails as the autofix lane, and never for protected
  paths, never-auto-repair categories, or targets above the write ceiling.

## 5. Trust but verify

No change is kept unless it verifies. Every applied repair runs the required
verification command (`make agent-check` by default) and is **rolled back** on
failure via a git snapshot. The bot only keeps what passes.

## 6. Operating modes

Selected by `PR_FIX_MODE`:

| Mode | Applies patches? | Pushes? |
| --- | --- | --- |
| `dry_run` | no | no |
| `propose_only` | no (report + proposals only) | no |
| `repair_and_verify` | yes (verified, rolled back on failure) | no |
| `repair_verify_and_push` | yes | yes (with `PR_FIX_ALLOW_PUSH=1`) |
| `learn_only` | no (emits learning packets) | no |

**`propose_only`** is the safe, read-only lane: it parses the validated payload,
routes findings, records telemetry and an auditable trace, and posts the single
governance comment — **without mutating the repository**. Run it with
`pr-repair report` (or `PR_FIX_MODE=propose_only`).

## 7. Trio Governance output

The bot maintains **exactly one** comment per PR, keyed on the persistent marker
`<!-- L9:IMPLEMENTER_BOT -->`, rendered as a fixed four-column status table so it
never collides with the Audit or Validator bots. Update-or-create only; a body
without the marker is refused.

## 8. Auditability

Every run leaves:

- `run_trace.json` — the ordered structured-event timeline, written **even on a
  fail-closed exit**.
- `prs/pr_<n>/autofix_telemetry.json` — per-Semgrep-rule outcomes feeding the CI
  shadow→blocking promotion cycle.
- `prs/pr_<n>/proposal_report.json` (propose_only) or the repair/execution
  artifacts (repair modes).

Secrets must be redacted before they reach any log, artifact, or comment.
