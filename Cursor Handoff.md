PR Repair System - Cursor Handoff

Context

This is my first time opening and running this repository.

The repository is a local-first, governance-first autonomous PR repair system that watches GitHub PRs, waits for CI/review signals, plans bounded fixes, applies patches safely, pushes commits back to the same PR branch, and loops until clean or blocked.

The system:

* MUST NOT create pull requests
* MUST NOT auto-merge
* MUST enforce approval and governance gates
* MUST support same-repo PR branches only for MVP
* MUST operate in deterministic bounded loops
* MUST preserve rollback safety

Current build:

* pr_repair_github_pr_loop_pack_v4
* pytest passing: 58
* import compile checks passing
* PR loop orchestrator implemented
* webhook receiver implemented
* branch patch commit support implemented

My Immediate Goal

I want to:

1. Run the system locally inside Cursor
2. Connect it to GitHub
3. Test it against a low-value real GitHub repo
4. Use a real PR flow
5. Observe the repair loop end-to-end
6. Keep risk extremely low

This is NOT a sandbox simulation.
This is a controlled low-risk real-world test.

Priority

The priority is:

* safe setup
* visibility
* deterministic behavior
* understanding the runtime
* observing guardrails
* preventing accidental destructive behavior

NOT:

* speed
* automation scale
* production deployment
* Dockerization
* hosted orchestration

What I Need From You

Guide me step-by-step through:

* environment setup
* dependency installation
* GitHub token setup
* webhook setup
* local runtime startup
* dry-run verification
* enabling push mode safely
* selecting a low-risk test repo
* creating a deliberately broken PR
* observing the repair lifecycle
* verifying rollback and approval behavior
* troubleshooting runtime errors

Hard Constraints

You MUST:

* explain before making major changes
* avoid hidden automation
* preserve local-first execution
* preserve governance gates
* preserve approval requirements
* keep all behavior observable
* use explicit commands
* assume I am new to this repo
* stop before destructive actions
* prefer dry-run before live mutation

You MUST NOT:

* deploy Docker unless explicitly requested
* introduce new architecture
* bypass approval gates
* auto-enable autonomous mutation
* auto-enable production behavior
* auto-merge PRs
* create new PRs
* mutate protected branches

Current Intended Flow

PR opened
  ↓
CI runs
  ↓
Review signals arrive
  ↓
System ingests findings
  ↓
Normalization + dedupe
  ↓
Repair planning
  ↓
Approval gate
  ↓
Patch commit pushed to same PR branch
  ↓
CI reruns
  ↓
Loop until clean or blocked

Initial Runtime Mode

Start in:

PR_FIX_MODE: dry_run
PR_FIX_ALLOW_PUSH: 0

Only enable real branch mutation after:

* dry-run behavior looks correct
* webhook flow is verified
* approval gates are confirmed
* repair planning artifacts look sane

Testing Preference

Use:

* a disposable low-value GitHub repo
* a same-repo branch PR
* intentionally failing tests
* intentionally simple repair cases first

Avoid:

* forks
* protected branches
* dependency upgrades
* migrations
* auth/security changes
* workflow mutations

Expected Assistant Behavior

I want operational guidance, not high-level summaries.

Prefer:

* exact commands
* exact file edits
* exact runtime steps
* exact debugging steps
* explicit explanations of what each component is doing

Assume the repo is unfamiliar territory and I am trying to safely taxi the aircraft before takeoff.