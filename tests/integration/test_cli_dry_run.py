import sys

from pr_repair import cli
from pr_repair.types import ExecutionMode


class _DummyConfig:
    def __init__(self, mode: ExecutionMode = ExecutionMode.dry_run) -> None:
        self.mode = mode
        self.payload_path = None

    def model_copy(self, update: dict) -> "_DummyConfig":
        clone = _DummyConfig(update.get("mode", self.mode))
        clone.payload_path = update.get("payload_path", self.payload_path)
        return clone


def test_cli_report_dispatches_to_reporter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_report(config) -> int:
        captured["reporter"] = config.mode
        return 0

    def fake_pipeline(config) -> int:
        captured["pipeline"] = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: _DummyConfig())
    monkeypatch.setattr(cli, "run_report", fake_report)
    monkeypatch.setattr(cli, "run_pipeline", fake_pipeline)
    monkeypatch.setattr(sys, "argv", ["pr-repair", "report"])

    assert cli.main() == 0
    assert captured["reporter"] is ExecutionMode.propose_only
    assert "pipeline" not in captured  # reporter, never the actuator


def test_cli_run_propose_only_routes_to_reporter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_report(config) -> int:
        captured["reporter"] = config.mode
        return 0

    def fake_pipeline(config) -> int:
        captured["pipeline"] = True
        return 0

    monkeypatch.setattr(cli, "load_config", lambda: _DummyConfig())
    monkeypatch.setattr(cli, "run_report", fake_report)
    monkeypatch.setattr(cli, "run_pipeline", fake_pipeline)
    monkeypatch.setattr(sys, "argv", ["pr-repair", "run", "--mode", "propose_only"])

    assert cli.main() == 0
    assert captured["reporter"] is ExecutionMode.propose_only
    assert "pipeline" not in captured


def test_cli_dry_run_dispatches_to_pipeline(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class DummyConfig:
        mode = ExecutionMode.dry_run

        def model_copy(self, update: dict) -> "DummyConfig":
            clone = DummyConfig()
            clone.mode = update.get("mode", self.mode)
            return clone

    def fake_load_config():
        return DummyConfig()

    def fake_run_pipeline(config):
        captured["mode"] = config.mode
        return 0

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(sys, "argv", ["pr-repair", "run", "--mode", "dry_run"])

    result = cli.main()

    assert result == 0
    assert captured["mode"] == "dry_run"
