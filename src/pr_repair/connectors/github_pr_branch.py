# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [connectors]
# tags: [github, branch, push, guarded-write]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import subprocess
from pathlib import Path

from pr_repair.types import PRRef


class GitHubPRBranchConnector:
    """Commits already-applied local changes to an existing same-repo PR branch.

    This adapter intentionally exposes no method that creates PRs or merges PRs.
    """

    def __init__(self, repo_root: Path | str | None = None, remote: str = "origin") -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
        self.remote = remote

    def commit_patch_to_pr_branch(
        self,
        *,
        pr_ref: PRRef,
        modified_files: list[str],
        commit_message: str,
        allow_push: bool,
    ) -> str:
        if not allow_push:
            raise PermissionError("branch mutation requires allow_push=True")
        if not modified_files:
            raise ValueError("no modified files supplied for PR branch commit")
        self._run(["git", "checkout", pr_ref.head_branch])
        self._run(["git", "add", *modified_files])
        commit_sha = self._run(["git", "commit", "-m", commit_message, "--porcelain"]).strip()
        self._run(["git", "push", self.remote, f"HEAD:{pr_ref.head_branch}"])
        return commit_sha or self._run(["git", "rev-parse", "HEAD"]).strip()

    def _run(self, command: list[str]) -> str:
        result = subprocess.run(
            command,
            cwd=self.repo_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout
