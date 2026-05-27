# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [workspace]
# tags: [git, branch, rollback]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import uuid4

from pr_repair.types import PRRef


def checkout_pr_branch(pr: PRRef, repo_root: Path | None = None) -> None:
    """
    Checkout the PR head branch without altering remote refs.
    """
    root = repo_root or Path.cwd()
    _run_git(["checkout", pr.head_branch], root)


def create_backup_ref(pr: PRRef, repo_root: Path | None = None) -> str:
    """
    Create a lightweight backup branch pointing at current HEAD for rollback.
    """
    root = repo_root or Path.cwd()
    ref_name = f"pr-repair-backup/pr-{pr.pr_number}-{uuid4().hex[:8]}"
    _run_git(["branch", ref_name, "HEAD"], root)
    return ref_name


def commit_changes(message: str, repo_root: Path | None = None) -> str:
    """
    Stage all current changes and create a commit. Returns the new commit SHA.
    """
    root = repo_root or Path.cwd()
    _run_git(["add", "-A"], root)
    _run_git(["commit", "-m", message], root)
    result = _run_git(["rev-parse", "HEAD"], root)
    return result.stdout.strip()


def push_changes(branch: str, repo_root: Path | None = None) -> None:
    """
    Push to origin without force. Deploy-safe by default.
    """
    root = repo_root or Path.cwd()
    _run_git(["push", "origin", branch], root)


def rollback_to_backup(ref_name: str, repo_root: Path | None = None) -> None:
    """
    Hard-reset working tree to the backup ref created earlier.
    """
    root = repo_root or Path.cwd()
    _run_git(["reset", "--hard", ref_name], root)


def _run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        raise ValueError(msg)
    return result
