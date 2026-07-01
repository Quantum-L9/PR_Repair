# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [repair]
# tags: [patch, apply, filesystem]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pathlib import Path


def apply_patch_instructions(
    instructions: list[dict],
    repo_root: Path | None = None,
) -> list[str]:
    """
    Apply supported patch instructions and return modified file paths.
    """
    root = repo_root or Path.cwd()
    modified: list[str] = []

    for instruction in instructions:
        op = instruction.get("op")
        if op == "replace_line":
            file_path = _apply_replace_line(instruction, root)
        elif op == "replace_range":
            file_path = _apply_replace_range(instruction, root)
        else:
            msg = f"unsupported patch op: {op}"
            raise ValueError(msg)
        modified.append(file_path)

    return sorted(set(modified))


def _apply_replace_line(instruction: dict[str, object], root: Path) -> str:
    file_path = instruction.get("file_path")
    line_number = instruction.get("line_number")
    expected = instruction.get("expected")
    replacement = instruction.get("replacement")
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("instruction missing file_path")
    if not isinstance(line_number, int) or line_number < 1:
        raise ValueError("instruction missing valid line_number")
    if not isinstance(expected, str):
        raise ValueError("instruction missing expected content")
    if not isinstance(replacement, str):
        raise ValueError("instruction missing replacement content")

    path = root / file_path
    lines = _read_lines(path, file_path)
    if line_number > len(lines):
        msg = f"line_number {line_number} out of range for {file_path}"
        raise ValueError(msg)
    current = lines[line_number - 1]
    if current != expected:
        msg = (
            f"expected line mismatch for {file_path}:{line_number}; "
            f"found={current!r} expected={expected!r}"
        )
        raise ValueError(msg)

    lines[line_number - 1] = replacement
    _write_lines(path, lines)
    return file_path


def _apply_replace_range(instruction: dict[str, object], root: Path) -> str:
    file_path = instruction.get("file_path")
    line_start = instruction.get("line_start")
    line_end = instruction.get("line_end")
    expected_block = instruction.get("expected_block")
    replacement = instruction.get("replacement")
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("instruction missing file_path")
    if not isinstance(line_start, int) or line_start < 1:
        raise ValueError("instruction missing valid line_start")
    if not isinstance(line_end, int) or line_end < line_start:
        raise ValueError("instruction missing valid line_end")
    if not isinstance(replacement, str):
        raise ValueError("instruction missing replacement content")

    path = root / file_path
    lines = _read_lines(path, file_path)
    if line_end > len(lines):
        msg = f"line range {line_start}-{line_end} out of range for {file_path}"
        raise ValueError(msg)

    # Exact-match guard: the on-disk block must match what the finding was generated
    # against. No fuzzy matching -- drift aborts the patch.
    if expected_block is not None:
        if not isinstance(expected_block, list):
            raise ValueError("expected_block must be a list of lines")
        current_block = lines[line_start - 1 : line_end]
        if current_block != expected_block:
            msg = (
                f"expected block mismatch for {file_path}:{line_start}-{line_end}; "
                f"found={current_block!r} expected={expected_block!r}"
            )
            raise ValueError(msg)

    lines[line_start - 1 : line_end] = replacement.split("\n")
    _write_lines(path, lines)
    return file_path


def _read_lines(path: Path, file_path: str) -> list[str]:
    if not path.exists():
        msg = f"target file does not exist: {file_path}"
        raise ValueError(msg)
    return path.read_text(encoding="utf-8").splitlines()


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
