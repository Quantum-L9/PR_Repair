from pr_repair.config import AppConfig, resolve_verify_command
from pr_repair.types import ExecutionMode, TierLevel


def test_resolve_verify_command_returns_configured_command(tmp_path) -> None:
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["make", "agent-check"],
        mode=ExecutionMode.dry_run,
        output_dir=tmp_path,
        write_ceiling=TierLevel.t1,
    )

    command = resolve_verify_command(config)

    assert command == ["make", "agent-check"]
