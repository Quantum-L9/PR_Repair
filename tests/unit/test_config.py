from pr_repair.config import AppConfig, resolve_verify_command_from_env
from pr_repair.types import ExecutionMode, TierLevel


def test_app_config_validates_repository_and_verify_command(tmp_path) -> None:
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=resolve_verify_command_from_env("make agent-check"),
        mode=ExecutionMode.dry_run,
        output_dir=tmp_path,
        write_ceiling=TierLevel.t1,
    )

    assert config.repo_owner == "owner"
    assert config.repo_name == "repo"
    assert config.verify_command == ["make", "agent-check"]


def test_resolve_verify_command_from_env_rejects_empty_command() -> None:
    try:
        resolve_verify_command_from_env("")
    except ValueError as exc:
        assert "must not be empty" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty verify command")
