# PR Repair Pipeline Runbook

## Purpose

This runbook defines the operational path for safely running, validating, and debugging the PR Repair Pipeline in an L9-governed repo.

## Standard operating modes

### 1. Dry run
Use when:
- onboarding a repo
- validating signal ingestion
- checking path/tier classification
- confirming runtime artifact generation

Command:
```bash
make pr-fix-dry
```

Expected outcome:
- no repo mutation
- runtime artifacts generated
- clear inventory of findings and classification state

### 2. Propose only
Use when:
- you want repair plans but no mutation
- approval may be needed
- planning logic needs inspection before write path

Command:
```bash
make pr-fix-propose
```

Expected outcome:
- repair plans generated
- approval gating visible
- no file changes

### 3. Repair and verify
Use when:
- findings are T1 or safe T2
- no protected paths are touched
- approval gate passes
- repo verification command is valid

Command:
```bash
make pr-fix
```

Expected outcome:
- exact-match patches applied
- verification runs
- rollback occurs if verification fails

### 4. Learn only
Use when:
- execution history already exists
- you want recommendation packets
- governance guidance needs review

Command:
```bash
make pr-fix-learn
```

Expected outcome:
- recommendation packets written
- no repo mutation

## Preflight checklist

- repo has clean worktree
- `.env.local` exists or shell env is configured
- `GITHUB_TOKEN` is valid
- `GITHUB_REPOSITORY` is valid
- `make agent-check` resolves in this repo
- protected path policy is current
- write ceiling is set intentionally
- push is disabled unless explicitly required

## Failure handling

### Dirty worktree
Symptom:
- execution fails before patching

Action:
- run `git status`
- commit, stash, or discard unrelated local changes
- rerun

### Missing or degraded external API
Symptom:
- CodeRabbit or Codecov findings absent

Action:
- confirm API keys
- confirm base URLs
- if missing by design, allow graceful degradation and rely on GitHub-derived signals

### Exact-match patch failure
Symptom:
- patch applier rejects expected line mismatch

Action:
- inspect current file contents
- inspect generated instruction
- rerun dry mode to understand stale signal vs. changed source mismatch

### Verification failure
Symptom:
- patch applied, `make agent-check` fails, rollback occurs

Action:
- inspect `verification_report.md`
- inspect `pr_result_report.md`
- inspect runtime findings and plan rationale
- rerun in propose-only mode before further attempts

### Approval gate block
Symptom:
- execution returns `approval_required`

Action:
- inspect classification and target tier
- inspect protected-path status
- either lower scope or escalate for human review

## Operational notes

- The service is deterministic only when inputs are stable.
- The patch path is intentionally narrow. It does not attempt semantic rewrites.
- Learning outputs are advisory. They are not auto-applied to governance docs or validators.
- `repair_verify_and_push` should remain exceptional, not default.

## Definition of healthy operation

A healthy run shows:
- expected PR inventory
- correct source ordering
- stable fingerprints
- sane classification
- correct protected-path detection
- executable plans only for safe findings
- verification results consistent with repo contract
