# Runtime Model

## Runtime state

Runtime state is represented through typed models, plans, execution results, verification reports, and emitted artifacts. State transitions MUST be deterministic for the same inputs and configuration.

## Artifact emission stages

Artifacts MAY be emitted after:

- signal collection
- normalized finding construction
- deduplication and clustering
- repair planning
- repair execution
- verification
- learning and governance recommendation generation

## Deterministic execution contract

- The system MUST use explicit input findings, configuration, and repository context.
- The system MUST preserve stable priority order for competing findings.
- The system MUST use exact patch instructions.
- The system MUST not silently mutate protected paths.
- The system MUST report approval-required and rollback states explicitly.

## Rollback model

Repair execution creates a backup ref before mutation. Verification failure or execution exception MUST call rollback to the backup ref. Rollback behavior is implemented in `workspace.git_ops` and exposed through `rollback`.

## Learning loop

Only completed or failed/rolled-back executions provide evidence for learning outputs. Learning artifacts MUST remain recommendations and MUST NOT rewrite governance policy directly.

## PR Repair State Machine

States:

- `waiting_for_signals`
- `ready_to_repair`
- `repair_planned`
- `approval_required`
- `patch_committed`
- `waiting_for_ci_rerun`
- `clean`
- `blocked`
- `max_attempts_reached`

Per-PR state is stored locally in JSON by `PRStateStore` with these required fields:

- `repo_full_name`
- `pr_number`
- `head_sha`
- `head_branch`
- `base_branch`
- `attempt`
- `ci_status`
- `review_status`
- `last_failure_fingerprint`
- `last_repair_commit`
- `terminal_state`
- `terminal_reason`
- `updated_at`

Terminal conditions:

- `clean`
- `approval_gate_denied`
- `fork_pr_detected`
- `failed_tests_after_max_attempts`
- `max_attempts_reached`
- `merge_conflict`
- `protected_branch_direct_mutation`
- `repeated_same_failure`
- `unresolved_imports`

The loop exits deterministically on terminal state and resets attempts when the PR head SHA changes.
