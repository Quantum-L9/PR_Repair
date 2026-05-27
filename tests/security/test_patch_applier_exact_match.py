from pathlib import Path

import pytest

from pr_repair.repair.patch_applier import apply_patch_instructions


def test_patch_applier_rejects_non_exact_match(tmp_path: Path) -> None:
    path = tmp_path / "script.py"
    path.write_text("line1\nactual line\nline3\n", encoding="utf-8")

    instructions = [
        {
            "op": "replace_line",
            "file_path": "script.py",
            "line_number": 2,
            "expected": "different line",
            "replacement": "new line",
        }
    ]

    with pytest.raises(ValueError):
        apply_patch_instructions(instructions, tmp_path)
