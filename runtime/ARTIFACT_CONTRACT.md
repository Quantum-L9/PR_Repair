# Runtime Artifact Contract

This document defines the required runtime artifacts for the PR Repair Pipeline.

## Contract rules

- all artifacts must be written under the configured runtime output directory
- JSON artifacts must be UTF-8, pretty-printed, and schema-consistent
- Markdown artifacts must be human-reviewable and deterministic
- raw source payloads must be persisted before transformation
- governance recommendation artifacts are review-only, never auto-applied

## Contracted artifacts

### Core run state
- `runtime_state.json`

### Intake and interpretation
- `pr_inventory.json`
- `findings_normalized.json`
- `findings_deduped.json`
- `findings_classified.json`
- `findings_merged.json`
- `normalization_errors.json`
- `interpretation_report.md`
- `phase3_summary.md`

### Execution and verification
- `verification_report.md`
- `pr_result_report.md`

### Learning and governance
- `learning_report.md`
- `AGENT_md_recommendations.yaml`
- `validator_recommendations.yaml`

### Raw source payloads
Per PR directory:
- `raw/<pr_number>/coderabbit.json`
- `raw/<pr_number>/codecov.json`
- `raw/<pr_number>/github_checks.json`
- `raw/<pr_number>/github_review_comments.json`
- `raw/<pr_number>/github_issue_comments.json`

## Write policy

- missing optional artifacts are allowed when the corresponding phase did not run
- required artifacts for an executed phase must exist before the phase is considered complete
- artifact writes must be idempotent for repeated dry runs against unchanged inputs
