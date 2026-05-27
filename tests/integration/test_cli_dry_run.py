import sys

from pr_repair import cli
from pr_repair.types import ExecutionMode


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
