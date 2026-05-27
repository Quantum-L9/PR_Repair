# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [workspace]
# tags: [git, worktree, safety]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import subprocess
from pathlib import Path


def ensure_clean_worktree(repo_root: Path | None = None) -> None:
    """
    Fail if the git worktree is dirty.
    """
    root = repo_root or Path.cwd()
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"git status failed: {result.stderr.strip() or result.stdout.strip()}"
        raise ValueError(msg)
    if result.stdout.strip():
        msg = "worktree is not clean"
        raise ValueError(msg)


def list_modified_files(repo_root: Path | None = None) -> list[str]:
    """
    Return modified tracked and untracked files in stable order.
    """
    root = repo_root or Path.cwd()
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"git status failed: {result.stderr.strip() or result.stdout.strip()}"
        raise ValueError(msg)

    files: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        files.append(line[3:].strip())
    return sorted(set(files))
