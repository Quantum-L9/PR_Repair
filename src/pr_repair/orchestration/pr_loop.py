# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [orchestration]
# tags: [pr-loop, ci, review, guarded-repair]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from pr_repair.config import AppConfig
from pr_repair.planning.approval_gate import requires_human_approval
from pr_repair.planning.repair_planner import build_repair_plan
from pr_repair.repair.repair_executor import execute_repair_plan
from pr_repair.runtime.pr_state_store import PRRepairState, PRStateStore
from pr_repair.types import Finding, PRRef, RepairExecution, RepairPlan


class PRLoopState(str, Enum):
    waiting_for_signals = "waiting_for_signals"
    ready_to_repair = "ready_to_repair"
    repair_planned = "repair_planned"
    approval_required = "approval_required"
    patch_committed = "patch_committed"
    waiting_for_ci_rerun = "waiting_for_ci_rerun"
    clean = "clean"
    blocked = "blocked"
    max_attempts_reached = "max_attempts_reached"


class TerminalBlocker(str, Enum):
    approval_gate_denied = "approval_gate_denied"
    fork_pr_detected = "fork_pr_detected"
    failed_tests_after_max_attempts = "failed_tests_after_max_attempts"
    max_attempts_reached = "max_attempts_reached"
    merge_conflict = "merge_conflict"
    protected_branch_direct_mutation = "protected_branch_direct_mutation"
    repeated_same_failure = "repeated_same_failure"
    unresolved_imports = "unresolved_imports"


@dataclass(frozen=True)
class PRLoopConfig:
    max_repair_attempts: int = 3
    require_human_approval_for: tuple[str, ...] = (
        "protected_paths",
        "dependency_files",
        "migrations",
        "auth_files",
        "security_files",
        "workflow_files",
    )
    same_repo_branches_only: bool = True


@dataclass(frozen=True)
class PRLoopResult:
    state: PRLoopState
    persisted_state: PRRepairState
    plan: RepairPlan | None = None
    execution: RepairExecution | None = None
    reason: str | None = None


class FindingProvider(Protocol):
    def __call__(self, pr_ref: PRRef) -> list[Finding]: ...


class SignalProvider(Protocol):
    def __call__(self, pr_ref: PRRef) -> tuple[str, str]: ...


class PRLoopOrchestrator:
    """Deterministic PR repair loop for same-repo existing PR branches.

    The orchestrator owns lifecycle decisions only. It does not create PRs, merge
    PRs, or bypass approval gates. Mutation is delegated to the existing repair
    executor after approval checks pass.
    """

    def __init__(
        self,
        *,
        app_config: AppConfig,
        state_store: PRStateStore,
        finding_provider: FindingProvider,
        signal_provider: SignalProvider | None = None,
        repair_executor: Callable[[RepairPlan, AppConfig, Path | None], RepairExecution] = execute_repair_plan,
        loop_config: PRLoopConfig | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self.app_config = app_config
        self.state_store = state_store
        self.finding_provider = finding_provider
        self.signal_provider = signal_provider or (lambda _pr: ("unknown", "unknown"))
        self.repair_executor = repair_executor
        self.loop_config = loop_config or PRLoopConfig()
        self.repo_root = repo_root

    def on_pr_event(self, pr_ref: PRRef, *, head_repo_full_name: str | None = None) -> PRLoopResult:
        state = self.state_store.get_or_create(
            repo_full_name=pr_ref.repo_full_name,
            pr_number=pr_ref.pr_number,
            head_sha=pr_ref.head_sha,
            head_branch=pr_ref.head_branch,
            base_branch=pr_ref.base_branch,
        )
        if self._is_fork_pr(pr_ref, head_repo_full_name):
            return self._block(state, TerminalBlocker.fork_pr_detected)
        if self._is_protected_branch_direct_mutation(pr_ref):
            return self._block(state, TerminalBlocker.protected_branch_direct_mutation)
        state.ci_status, state.review_status = self.signal_provider(pr_ref)
        if state.ci_status == "success" and state.review_status in {"approved", "unknown"}:
            state.mark_terminal("clean")
            self.state_store.save(state)
            return PRLoopResult(PRLoopState.clean, state, reason="ci_success")
        if state.ci_status in {"unknown", "pending"} or state.review_status == "pending":
            self.state_store.save(state)
            return PRLoopResult(PRLoopState.waiting_for_signals, state)
        return self._attempt_repair(pr_ref, state)

    def on_signals_completed(self, pr_ref: PRRef, *, head_repo_full_name: str | None = None) -> PRLoopResult:
        return self.on_pr_event(pr_ref, head_repo_full_name=head_repo_full_name)

    def _attempt_repair(self, pr_ref: PRRef, state: PRRepairState) -> PRLoopResult:
        if state.attempt >= self.loop_config.max_repair_attempts:
            return self._block(state, TerminalBlocker.max_attempts_reached, PRLoopState.max_attempts_reached)
        findings = self.finding_provider(pr_ref)
        if not findings:
            state.mark_terminal("clean")
            self.state_store.save(state)
            return PRLoopResult(PRLoopState.clean, state, reason="no_findings")
        failure_fingerprint = fingerprint_findings(findings)
        if state.record_failure(failure_fingerprint):
            return self._block(state, TerminalBlocker.repeated_same_failure)
        plan = build_repair_plan(pr_ref, findings, self.app_config)
        self.state_store.save(state)
        if requires_human_approval(plan, self.app_config):
            state.mark_terminal(TerminalBlocker.approval_gate_denied.value)
            self.state_store.save(state)
            return PRLoopResult(PRLoopState.approval_required, state, plan=plan, reason="approval_required")
        if not plan.executable:
            return self._block(state, "plan_not_executable")
        state.attempt += 1
        self.state_store.save(state)
        execution = self.repair_executor(plan, self.app_config, self.repo_root)
        if execution.status == "completed":
            state.last_repair_commit = execution.push_result
            self.state_store.save(state)
            return PRLoopResult(PRLoopState.waiting_for_ci_rerun, state, plan=plan, execution=execution)
        if execution.status == "approval_required":
            state.mark_terminal(TerminalBlocker.approval_gate_denied.value)
            self.state_store.save(state)
            return PRLoopResult(PRLoopState.approval_required, state, plan=plan, execution=execution)
        if state.attempt >= self.loop_config.max_repair_attempts:
            return self._block(state, TerminalBlocker.failed_tests_after_max_attempts, PRLoopState.max_attempts_reached)
        self.state_store.save(state)
        return PRLoopResult(PRLoopState.blocked, state, plan=plan, execution=execution, reason=execution.status)

    def _block(
        self,
        state: PRRepairState,
        reason: TerminalBlocker | str,
        loop_state: PRLoopState = PRLoopState.blocked,
    ) -> PRLoopResult:
        state.mark_terminal(reason.value if isinstance(reason, TerminalBlocker) else reason)
        self.state_store.save(state)
        return PRLoopResult(loop_state, state, reason=state.terminal_reason)

    def _is_fork_pr(self, pr_ref: PRRef, head_repo_full_name: str | None) -> bool:
        return self.loop_config.same_repo_branches_only and head_repo_full_name not in {None, pr_ref.repo_full_name}

    def _is_protected_branch_direct_mutation(self, pr_ref: PRRef) -> bool:
        return pr_ref.head_branch == pr_ref.base_branch


def fingerprint_findings(findings: Sequence[Finding]) -> str:
    material = "\n".join(
        sorted(
            f"{finding.fingerprint}|{finding.file_path}|{finding.line_start}|{finding.message}"
            for finding in findings
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
