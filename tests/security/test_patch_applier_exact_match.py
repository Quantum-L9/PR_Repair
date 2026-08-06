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


def test_replace_line_applies_on_exact_match(tmp_path: Path) -> None:
    path = tmp_path / "script.py"
    path.write_text("a\nPacketEnvelope\nc\n", encoding="utf-8")

    modified = apply_patch_instructions(
        [
            {
                "op": "replace_line",
                "file_path": "script.py",
                "line_number": 2,
                "expected": "PacketEnvelope",
                "replacement": "TransportPacket",
            }
        ],
        tmp_path,
    )

    assert modified == ["script.py"]
    assert path.read_text(encoding="utf-8") == "a\nTransportPacket\nc\n"


def test_replace_range_applies_with_matching_block(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text("h\nold1\nold2\nt\n", encoding="utf-8")

    modified = apply_patch_instructions(
        [
            {
                "op": "replace_range",
                "file_path": "mod.py",
                "line_start": 2,
                "line_end": 3,
                "expected_block": ["old1", "old2"],
                "replacement": "new1\nnew2\nnew3",
            }
        ],
        tmp_path,
    )

    assert modified == ["mod.py"]
    assert path.read_text(encoding="utf-8") == "h\nnew1\nnew2\nnew3\nt\n"


def test_replace_range_rejects_block_drift(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text("h\nold1\nDRIFTED\nt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected block mismatch"):
        apply_patch_instructions(
            [
                {
                    "op": "replace_range",
                    "file_path": "mod.py",
                    "line_start": 2,
                    "line_end": 3,
                    "expected_block": ["old1", "old2"],
                    "replacement": "x",
                }
            ],
            tmp_path,
        )


def test_unsupported_op_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported patch op"):
        apply_patch_instructions([{"op": "delete_file", "file_path": "x"}], tmp_path)


# --- Path-containment guard (SonarCloud pythonsecurity:S2083) ---------------


def test_valid_repo_relative_path_is_patched(tmp_path: Path) -> None:
    """A normal repo-relative file inside root is still patchable (no regression)."""
    nested = tmp_path / "pkg" / "mod.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("a\nold\nc\n", encoding="utf-8")

    modified = apply_patch_instructions(
        [
            {
                "op": "replace_line",
                "file_path": "pkg/mod.py",
                "line_number": 2,
                "expected": "old",
                "replacement": "new",
            }
        ],
        tmp_path,
    )

    assert modified == ["pkg/mod.py"]
    assert nested.read_text(encoding="utf-8") == "a\nnew\nc\n"


def test_relative_traversal_outside_root_is_rejected(tmp_path: Path) -> None:
    """A ``../`` path escaping the repo root is rejected before any write."""
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("do-not-touch\n", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes repository root"):
        apply_patch_instructions(
            [
                {
                    "op": "replace_line",
                    "file_path": "../secret.txt",
                    "line_number": 1,
                    "expected": "do-not-touch",
                    "replacement": "pwned",
                }
            ],
            root,
        )
    assert outside.read_text(encoding="utf-8") == "do-not-touch\n"


def test_absolute_outside_root_path_is_rejected(tmp_path: Path) -> None:
    """An absolute path pointing outside the repo root is rejected."""
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep\n", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes repository root"):
        apply_patch_instructions(
            [
                {
                    "op": "replace_range",
                    "file_path": str(outside),
                    "line_start": 1,
                    "line_end": 1,
                    "expected_block": ["keep"],
                    "replacement": "pwned",
                }
            ],
            root,
        )
    assert outside.read_text(encoding="utf-8") == "keep\n"
