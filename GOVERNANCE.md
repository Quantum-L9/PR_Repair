# Governance

## Write ceilings

The system MUST respect configured ceilings for repair execution. Plans exceeding configured risk or write bounds MUST require approval.

## Protected paths

Protected-path rules MUST be evaluated before write behavior. Protected paths MUST NOT be mutated without explicit approval.

## Approval gates

Approval gates MUST return a deterministic decision from the repair plan and configuration. Approval-required status MUST stop mutation.

## Rollback safety

A backup ref MUST be created before patch application. Verification failure MUST rollback to the backup ref. Execution exceptions after backup creation MUST rollback before surfacing the error.

## Auditability

The system MUST emit artifacts sufficient to inspect findings, plans, execution status, verification result, and recommendation output.

## No uncontrolled mutation

The system MUST NOT perform uncontrolled repository mutation. Connectors collect signals. Planning creates bounded intent. Repair execution applies exact instructions. Verification gates success. Rollback handles failure.

## Existing PR Branch Mutation Guardrails

The GitHub PR loop may modify only existing same-repo PR branches.

MUST:

- verify webhook signatures before accepting events
- reject unsigned or invalid webhook payloads
- block fork PRs for MVP
- block direct mutation when head branch equals base branch
- run approval gate before mutation
- stop after max repair attempts
- stop on repeated same failure fingerprint
- preserve rollback behavior on failed verification
- emit local PR state before and after lifecycle transitions

MUST NOT:

- create new pull requests
- auto-merge pull requests
- mutate protected paths without approval
- bypass `approval_gate.py`
- weaken verification to force a repair commit
- perform uncontrolled autonomous writes
