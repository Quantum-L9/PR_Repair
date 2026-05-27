from pathlib import Path
import sys

from pr_repair import cli


def test_cli_verify_runs_verification_and_writes_report(monkeypatch, tmp_path: Path) -> None:
    class DummyConfig:
        output_dir = tmp_path
        verify_command = ["make", "agent-check"]

    class DummyReport:
        success = True
        exit_code = 0

    monkeypatch.setattr(cli, "load_config", lambda: DummyConfig())
    monkeypatch.setattr(cli, "resolve_verify_command", lambda config: ["make", "agent-check"])
    monkeypatch.setattr(cli, "run_verification", lambda command: DummyReport())
    monkeypatch.setattr(cli, "build_verification_markdown", lambda report: "# Verification report")
    monkeypatch.setattr(sys, "argv", ["pr-repair", "verify"])

    result = cli.main()

    assert result == 0
    assert (tmp_path / "verification_report.md").exists()
