# PR Repair Pipeline

Local-first, repo-aware PR repair pipeline for L9-governed repositories.

## Purpose

The pipeline ingests real PR signals in strict priority order:

1. CodeRabbit
2. Codecov Cloud
3. GitHub required checks
4. GitHub review comments
5. GitHub issue comments

It then normalizes, deduplicates, classifies, plans, verifies, and emits structured learning outputs without violating L9 repo safety boundaries.

## Design guarantees

- local-first execution
- no Docker required for default path
- tool findings always outrank comments
- protected-path and write-ceiling enforcement
- deterministic artifact generation
- review-only governance recommendations
- no direct mutation of `AGENT.md` or external validator systems
- deploy-safe, rollback-safe execution path

## Supported commands

### Dry run
```bash
make pr-fix-dry
```

Runs the full intake, interpretation, and planning path without mutating code.

### Propose only
```bash
make pr-fix-propose
```

Builds interpretation and planning outputs intended for review before any execution.

### Repair and verify
```bash
make pr-fix
```

Runs the execution path for approval-safe, write-ceiling-safe plans and verifies with the configured command.

### Verify only
```bash
make pr-fix-verify
```

Runs the pipeline in verification mode using the repo verification contract.

### Learn only
```bash
make pr-fix-learn
```

Builds governance recommendation packets from repair execution history.

## Environment

Required:

- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY` in `owner/repo` form

Optional:

- `CODERABBIT_API_KEY`
- `CODECOV_API_KEY`
- `CODERABBIT_API_BASE_URL`
- `CODECOV_API_BASE_URL`
- `PR_FIX_MAX_PRS`
- `PR_FIX_MODE`
- `PR_FIX_ALLOW_PUSH`
- `PR_FIX_OUTPUT_DIR`
- `PR_FIX_INCLUDE_DRAFTS`
- `PR_FIX_WRITE_CEILING`
- `PR_FIX_VERIFY_COMMAND`

## Runtime artifacts

The pipeline writes runtime artifacts under `runtime/pr_repair` by default.

Core artifacts:

- `runtime_state.json`
- `pr_inventory.json`
- `findings_normalized.json`
- `findings_deduped.json`
- `findings_classified.json`
- `findings_merged.json`
- `normalization_errors.json`
- `interpretation_report.md`
- `phase3_summary.md`

Learning and execution artifacts, when present:

- `verification_report.md`
- `pr_result_report.md`
- `learning_report.md`
- `AGENT_md_recommendations.yaml`
- `validator_recommendations.yaml`

Raw source payloads, when present:

- `raw/<pr_number>/coderabbit.json`
- `raw/<pr_number>/codecov.json`
- `raw/<pr_number>/github_checks.json`
- `raw/<pr_number>/github_review_comments.json`
- `raw/<pr_number>/github_issue_comments.json`

## Safety boundaries

- protected files and above-ceiling tiers require approval
- `make agent-check` remains the repo verification contract
- push requires explicit flagging and safe execution mode
- execution refuses dirty worktrees
- rollback occurs on verification failure

## Current phase coverage

Implemented:
- scaffold and repo context
- connectors and ingestion
- normalization, dedupe, taxonomy, classification
- repair planning and approval gate
- workspace, patch generation, patch application, verification
- learning outputs and structured PR commentary
- makefile, docs, runtime artifact contract, and test matrix hardening

Direct repo mutation of governance files is intentionally not implemented.
