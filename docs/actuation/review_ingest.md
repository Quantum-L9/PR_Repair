# Review ingestion runtime entrypoint

Closes the wiring gap between the per-tool review adapters (`pr_repair.tools`) and
the deterministic pipeline (`pr-repair run`), which consumes a canonical
`agent_review_payload.json`. Previously the adapters could turn a tool's native
review threads into canonical findings, but nothing turned a **live PR review**
into the on-disk payload — so the actuation workflow could only skip. The
`pr-repair ingest-review` command is that missing producer.

## Command

```
pr-repair ingest-review --event-path "$GITHUB_EVENT_PATH" --output artifacts/agent_review_payload.json
# or, offline / reproducible:
pr-repair ingest-review --context review_context.json --output artifacts/agent_review_payload.json
```

Also runnable as a module: `python -m pr_repair.review_ingest ...`.

### Inputs

- `--event-path <file>` — **live mode.** The GitHub Actions event JSON
  (`pull_request_review`). The entrypoint detects the originating review tool
  (Copilot / CodeRabbit / SonarCloud / GitGuardian), fetches that tool's
  *unresolved* threads via the GitHub API (`GITHUB_TOKEN` required), normalizes
  them through the matching adapter, and writes the payload.
- `--context <file>` — **offline mode.** A captured
  `{"tool", "pr", "threads"}` review context. No network; used by tests and by
  re-runs from a captured event. The same adapter filtering (unresolved +
  authorship) runs, so the offline path is faithful to the live one.
- `--output <file>` — where to write `agent_review_payload.json`.

Exactly one of `--event-path` / `--context` is required.

## Output

A schema-valid `agent_review_payload.json` conforming to
[`contracts/agent-review-payload.schema.json`](../../contracts/agent-review-payload.schema.json):
findings are partitioned into deterministic `autofix_candidates` (a review
`suggestion` block with an exact file + line) and `manual_review_required`
(everything else). The output is validated against the schema **before** it is
written, and re-validates cleanly through the same `PayloadParser` the pipeline
uses.

## Exit contract (the workflow branches on these)

| Exit | Meaning | Workflow behavior |
|------|---------|-------------------|
| `0`  | Payload produced | Run downstream `pr-repair run` |
| `3`  | Skipped — no PR / no recognized review tool (genuinely absent source) | Skip downstream **cleanly** |
| `1`  | Failed — review context existed but is malformed / un-normalizable / failed schema validation | **Block** downstream actuation |

The entrypoint never fabricates review data and never leaves a payload file
behind on a skip or failure. A recognized tool that left *no* actionable threads
is a legitimate produced payload with empty arrays (exit `0`), not a skip.

## Workflow data flow (`.github/workflows/pr-repair.yml`)

```
pull_request_review event ($GITHUB_EVENT_PATH)
  -> pr-repair ingest-review   (detect tool -> fetch threads -> normalize -> validate)
  -> artifacts/agent_review_payload.json
  -> pr-repair run             (deterministic actuation; dry-run + write-gates off by default)
```

The downstream `pr-repair run` step runs only when ingestion reports `produced`,
and re-asserts the payload is present and non-empty before invoking the bot — so
the bot never runs on a missing payload. There is **no** dependency on a
pre-existing upstream payload.

## Logging / secret hygiene

Only finding **counts** and the output path are logged. Review bodies (which may
quote secrets) and tokens are never printed.

## Unknowns / follow-ups

- `changed_files` is intentionally omitted from the `pr` block here (optional in
  the schema); the downstream collector derives changed files itself.
- Non-Copilot adapters (CodeRabbit / Sonar / GitGuardian) share the same
  `get_review_threads` read path and are wired, but their live native shapes
  should be confirmed against real fixtures before enabling those tools in
  `config.py`.
