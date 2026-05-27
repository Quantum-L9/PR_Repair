from pathlib import Path

from pr_repair.verification.native_runner import run_verification


def test_run_verification_captures_success(tmp_path: Path) -> None:
    report = run_verification(["python", "-c", "print('ok')"], tmp_path)

    assert report.success is True
    assert report.exit_code == 0
    assert "ok" in report.stdout
