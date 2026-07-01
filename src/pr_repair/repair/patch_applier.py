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
    modified = [_apply_one(instruction, root) for instruction in instructions]
    return sorted(set(modified))


def _apply_one(instruction: dict, root: Path) -> str:
    """Validate and apply a single ``replace_line`` instruction; return its path."""
    file_path, line_number, expected, replacement = _validated_replace_line(instruction)

    path = root / file_path
    if not path.exists():
        msg = f"target file does not exist: {file_path}"
        raise ValueError(msg)

    lines = path.read_text(encoding="utf-8").splitlines()
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return file_path


def _validated_replace_line(instruction: dict) -> tuple[str, int, str, str]:
    """Type-check a ``replace_line`` instruction, returning its coerced fields."""
    op = instruction.get("op")
    if op != "replace_line":
        msg = f"unsupported patch op: {op}"
        raise ValueError(msg)

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
    return file_path, line_number, expected, replacement
