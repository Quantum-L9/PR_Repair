"""Path-injection guard tests for the review-ingest entrypoint.

Covers SonarCloud ``pythonsecurity:S8707`` ("LLMs running this code with faulty
CLI arguments can escape file system restrictions") on
``src/pr_repair/review_ingest.py``. The ``--context`` / ``--event-path`` /
``--output`` arguments are treated as untrusted; ``_safe_path`` canonicalizes
them and rejects anything outside the allowed IO roots (CWD, OS temp dir, and
``PR_REPAIR_IO_ROOT`` entries) before any read/write.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pr_repair import review_ingest
from pr_repair.review_ingest import ReviewIngestError, _load_json, _safe_path, _write_payload


def test_safe_path_allows_paths_inside_temp_root(tmp_path: Path) -> None:
    # pytest tmp_path lives under the OS temp dir, which is an allowed root.
    target = tmp_path / "artifacts" / "payload.json"
    resolved = _safe_path(str(target))
    assert resolved == target.resolve()


def test_safe_path_allows_cwd_relative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = _safe_path("sub/dir/file.json")
    assert resolved == (tmp_path / "sub" / "dir" / "file.json").resolve()


def test_safe_path_honors_explicit_extra_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extra = tmp_path / "staged"
    extra.mkdir()
    monkeypatch.setenv("PR_REPAIR_IO_ROOT", str(extra))
    resolved = _safe_path(str(extra / "in.json"))
    assert resolved == (extra / "in.json").resolve()


def test_safe_path_rejects_traversal_outside_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Confine allowed roots to an isolated dir so a system path is provably outside.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PR_REPAIR_IO_ROOT", str(tmp_path))
    # /etc/passwd is outside cwd and the configured root; temp dir is the only
    # other default root, and /etc is not under it on any supported platform.
    with pytest.raises(ReviewIngestError, match="refusing path outside allowed roots"):
        _safe_path("/etc/passwd")


def test_safe_path_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(ReviewIngestError, match="non-empty string"):
        _safe_path("")


def test_load_json_rejects_out_of_root_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PR_REPAIR_IO_ROOT", str(tmp_path))
    with pytest.raises(ReviewIngestError, match="refusing path outside allowed roots"):
        _load_json("/etc/hostname")


def test_write_payload_rejects_out_of_root_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PR_REPAIR_IO_ROOT", str(tmp_path))
    with pytest.raises(ReviewIngestError, match="refusing path outside allowed roots"):
        _write_payload("/etc/pwned.json", {"x": 1})


def test_run_still_reads_and_writes_valid_temp_paths(tmp_path: Path) -> None:
    """End-to-end: valid absolute temp paths (used by CI/tests) remain allowed."""
    ctx = tmp_path / "ctx.json"
    ctx.write_text("{ not json", encoding="utf-8")  # malformed -> fail closed, but path allowed
    out = tmp_path / "out.json"
    rc = review_ingest.run(output=str(out), context=str(ctx))
    # Path was accepted (no ReviewIngestError for path); failure is the JSON parse.
    assert rc == review_ingest.EXIT_FAILED


def test_out_of_root_output_returns_exit_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (M1): a valid input with an out-of-root --output must return
    EXIT_FAILED, not raise ReviewIngestError. Guards run()'s no-raise contract.
    """
    # Confine allowed roots to tmp_path so /etc is provably outside.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PR_REPAIR_IO_ROOT", str(tmp_path))
    ctx = tmp_path / "ctx.json"
    ctx.write_text("{}", encoding="utf-8")  # readable, in-root -> input path passes

    # Make the payload build + validation succeed so execution would otherwise
    # reach the write sink; the out-of-root output must be rejected as EXIT_FAILED.
    monkeypatch.setattr(
        review_ingest,
        "payload_from_context",
        lambda *a, **k: {"autofix_candidates": [], "manual_review_required": []},
    )
    monkeypatch.setattr(review_ingest, "_validate_payload", lambda payload: None)

    rc = review_ingest.run(output="/etc/pwned.json", context=str(ctx))
    assert rc == review_ingest.EXIT_FAILED
