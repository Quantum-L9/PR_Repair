from pathlib import Path
import subprocess

from pr_repair.workspace.worktree import ensure_clean_worktree, list_modified_files


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def test_ensure_clean_worktree_passes_for_clean_repo(tmp_path: Path) -> None:
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test User"], tmp_path)
    (tmp_path / "file.txt").write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "file.txt"], tmp_path)
    _run(["git", "commit", "-m", "init"], tmp_path)

    ensure_clean_worktree(tmp_path)


def test_list_modified_files_returns_dirty_paths(tmp_path: Path) -> None:
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test User"], tmp_path)
    (tmp_path / "file.txt").write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "file.txt"], tmp_path)
    _run(["git", "commit", "-m", "init"], tmp_path)
    (tmp_path / "file.txt").write_text("changed\n", encoding="utf-8")

    modified = list_modified_files(tmp_path)

    assert modified == ["file.txt"]
