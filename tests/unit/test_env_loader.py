from pathlib import Path

from pr_repair.connectors.env_loader import load_dotenv_local


def test_load_dotenv_local_returns_non_null_values_only(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env.local"
    dotenv_path.write_text(
        "\n".join(
            [
                "GITHUB_TOKEN=test-token",
                "EMPTY_VALUE=",
                "GITHUB_REPOSITORY=owner/repo",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_dotenv_local(str(dotenv_path))

    assert loaded["GITHUB_TOKEN"] == "test-token"
    assert loaded["GITHUB_REPOSITORY"] == "owner/repo"
    assert "EMPTY_VALUE" not in loaded


def test_load_dotenv_local_missing_file_returns_empty_mapping(tmp_path: Path) -> None:
    loaded = load_dotenv_local(str(tmp_path / "missing.env"))
    assert loaded == {}
