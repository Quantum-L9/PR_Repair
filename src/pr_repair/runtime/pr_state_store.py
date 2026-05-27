# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [runtime, orchestration]
# tags: [pr-loop, state, persistence, guardrails]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


CIStatus = Literal["unknown", "pending", "success", "failure"]
ReviewStatus = Literal["unknown", "pending", "approved", "changes_requested"]
TerminalReason = Literal[
    "clean",
    "approval_gate_denied",
    "fork_pr_detected",
    "failed_tests_after_max_attempts",
    "max_attempts_reached",
    "merge_conflict",
    "protected_branch_direct_mutation",
    "repeated_same_failure",
    "unresolved_imports",
]


class PRRepairState(BaseModel):
    repo_full_name: str
    pr_number: int
    head_sha: str
    head_branch: str
    base_branch: str
    attempt: int = 0
    ci_status: CIStatus = "unknown"
    review_status: ReviewStatus = "unknown"
    last_failure_fingerprint: str | None = None
    last_repair_commit: str | None = None
    terminal_state: bool = False
    terminal_reason: str | None = None
    updated_at: str = Field(default_factory=utc_now_iso)

    @property
    def key(self) -> str:
        safe_repo = self.repo_full_name.replace("/", "__")
        return f"{safe_repo}__pr_{self.pr_number}.json"

    def mark_updated(self) -> None:
        self.updated_at = utc_now_iso()

    def mark_terminal(self, reason: TerminalReason | str) -> None:
        self.terminal_state = True
        self.terminal_reason = str(reason)
        self.mark_updated()

    def record_failure(self, fingerprint: str) -> bool:
        repeated = self.last_failure_fingerprint == fingerprint
        self.last_failure_fingerprint = fingerprint
        self.mark_updated()
        return repeated


class PRStateStore:
    """File-backed PR repair state store.

    The store is intentionally local-first. It persists one JSON file per PR and
    performs no network calls or background writes.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, repo_full_name: str, pr_number: int) -> PRRepairState | None:
        path = self._path(repo_full_name, pr_number)
        if not path.exists():
            return None
        return PRRepairState.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, state: PRRepairState) -> PRRepairState:
        state.mark_updated()
        path = self.root / state.key
        path.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return state

    def get_or_create(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        head_sha: str,
        head_branch: str,
        base_branch: str,
    ) -> PRRepairState:
        existing = self.load(repo_full_name, pr_number)
        if existing is not None:
            if existing.head_sha != head_sha:
                existing.head_sha = head_sha
                existing.attempt = 0
                existing.last_failure_fingerprint = None
                existing.terminal_state = False
                existing.terminal_reason = None
            existing.head_branch = head_branch
            existing.base_branch = base_branch
            return self.save(existing)
        return self.save(
            PRRepairState(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                head_sha=head_sha,
                head_branch=head_branch,
                base_branch=base_branch,
            )
        )

    def _path(self, repo_full_name: str, pr_number: int) -> Path:
        safe_repo = repo_full_name.replace("/", "__")
        return self.root / f"{safe_repo}__pr_{pr_number}.json"
