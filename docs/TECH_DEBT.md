# Tech Debt

Actionable, non-blocking follow-ups. Each item is intentionally deferred (not a
merge blocker) and carries enough context to be picked up independently.

## From PR #18 security review (path guards + dependency pin)

Context: PR #18 resolved issues #14 (immutable router pin) and #16 (SonarCloud
path-injection findings S8707/S2083). The blocking bug (M1 — out-of-root
`--output` raised uncaught from `run()`) was fixed in that PR. The items below
are the remaining lower-tier findings from the manual review. None are security
regressions; every observed failure mode fails **closed**.

### L1 — Narrow / opt-in the always-allowed temp root *(Low, hardening)*
- **Where:** `src/pr_repair/review_ingest.py` → `_allowed_io_roots()`
- **Issue:** the OS temp dir is unconditionally an allowed IO root, so
  `/tmp/<anything>` is readable/writable via `--context`/`--event-path`/`--output`.
  On shared or self-hosted runners `/tmp` is world-writable, widening the
  attack surface (symlink-in-`/tmp` tricks, clobbering another job's scratch).
- **Action:** scope the temp root to the job (e.g. `RUNNER_TEMP` / `$TMPDIR`) or
  make it opt-in via `PR_REPAIR_IO_ROOT` instead of a default. Document that
  `PR_REPAIR_IO_ROOT=/` fully disables the guard (verified) as a known foot-gun.

### L2 — Unify the two path-containment guards *(Low, consistency)*
- **Where:** `review_ingest._safe_path` (cwd + temp + env roots) vs
  `repair/patch_applier._resolve_within_root` (repo-root only).
- **Issue:** two guards with different containment models and separate
  implementations invite drift and reviewer confusion.
- **Action:** extract one shared `contains(root, target)` helper (e.g.
  `pr_repair/security/paths.py`) and express both guards in terms of it. No
  behavior change intended.

### L3 — Reject the root directory as a patch target *(Low, defense-in-depth)*
- **Where:** `repair/patch_applier._resolve_within_root`
- **Issue:** `file_path == ""` or `"."` resolves to the root dir and passes the
  guard. Not exploitable today (callers reject falsy `file_path`; `_read_lines`
  fails on a directory), but the guard should be safe independent of caller order.
- **Action:** reject `target == root_resolved` directly in the guard.

### L4 — Reproducible router-shim build *(Low, supply chain; out of #14 scope)*
- **Where:** `router-shim/setup.sh`, `router-shim/package.json`
- **Issue:** the `@quantum-l9/llm-router` **source ref** is now an immutable SHA
  (#14 satisfied), but `setup.sh` runs `npm install` (no committed
  `package-lock.json` / not `npm ci`), so transitive deps still float and the
  full build is not reproducible.
- **Action:** commit a lockfile and switch to `npm ci`. Longer term, publish a
  versioned prebuilt `@quantum-l9/llm-router` to a registry to remove
  build-at-install and its lifecycle-script exposure.

### N1 — Move `import tempfile` to module top *(Nit)*
- **Where:** `review_ingest._allowed_io_roots()` imports `tempfile` in-body.
- **Action:** hoist to module-level imports unless the deferred import is
  deliberate.

### N2 — Lock symlink-escape behavior with an explicit test *(Nit, coverage)*
- **Where:** `tests/security/` for `repair/patch_applier._resolve_within_root`
- **Issue:** `.resolve()` correctly dereferences symlinks before the containment
  check (verified empirically — file and directory symlink escapes are blocked),
  but there is no regression test pinning this behavior.
- **Action:** add an explicit symlink-escape test (file symlink and directory
  symlink) so a future refactor to a non-resolving check is caught.

### Related (baseline, follow-up)
- Other GitHub Actions in `.github/workflows/pr-checks.yml` remain pinned to
  moving tags (only `astral-sh/setup-uv@v5` was pinned to a SHA in #18 to clear
  the new-code `githubactions:S7637` finding). Pin the rest to full commit SHAs
  for consistency when convenient.
