# Governance

## Pipeline role in constellation v0.1

```yaml
pipeline_role: standalone_pr_assistant
debt_pipeline_authority: false
remote_mutation_default: false
verification_authority: local_only
resolver_delegation_implemented: false
```

`PR_Repair` is a standalone pull-request repair assistant. It is **not** part of
the L9 debt pipeline in v0.1, and it is not the debt pipeline's repair owner —
`l9-ci-debt-resolver` is.

This has to be stated because two systems were each built as the organisation's
repair owner. `l9-ci-debt-resolver` defines a bounded delegation protocol,
`l9.pr-repair-request/v1` and `l9.pr-repair-proposal/v1`, in which a delegate
may propose and never conclude. **This repository does not implement it.**
Neither token appears anywhere in this tree. Instead it runs a complete parallel
loop: its own finding model, clustering, classification, approval gate,
protected-path policy, worktree isolation, patch generation and application,
verification, learning, and rollback.

The two loops never run together, so this is duplicate authority by design
intent rather than a live split brain. v0.1 resolves it by scope: the resolver
keeps debt-pipeline repair, and this repository stays a separate product. See
`l9-ci-debt-resolver`'s `docs/repair-authority-v0.1.md` for the matching
statement.

Consequences that hold for v0.1:

- **Verification here is local and self-contained.** This loop runs a command,
  builds its own `VerificationReport`, and writes its own result. That is not an
  independent admission, and it must not be described as one. `l9-assurance` is
  the constellation's only evidence-admission authority, and this repository
  does not report to it.
- **No corpus emission.** `l9-ci-debt-intelligence` declares a
  `l9.repair-learning-packet/v1` input attributed to this repository. Nothing
  here emits it; that declaration is marked `planned` upstream.
- **Remote mutation stays off by default.** The shipped workflow requires
  `vars.PR_REPAIR_ENABLED == 'true'`, defaults to `dry_run`, hardcodes
  `PR_FIX_ALLOW_PUSH: '0'`, refuses fork PRs, and holds `contents: read`.
  Enabling push is a reviewed workflow edit, not a configuration convenience.

Changing this means picking one of two outcomes deliberately: implement the
resolver's request/proposal protocol here and drop this repository's executor,
verification, and push path — or have the resolver retire its delegation phase.
Leaving both systems claiming repair ownership is what v0.1 rules out.

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
