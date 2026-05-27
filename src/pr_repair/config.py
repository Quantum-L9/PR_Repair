# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [config]
# tags: [config, env, runtime]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import os
import shlex
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

from pr_repair.types import ExecutionMode, TierLevel


class AppConfig(BaseModel):
    github_token: str
    github_repository: str
    coderabbit_api_key: str | None = None
    codecov_api_key: str | None = None
    coderabbit_api_base_url: str | None = None
    codecov_api_base_url: str = "https://api.codecov.io"
    max_prs: int = 5
    verify_command: list[str] = Field(default_factory=lambda: ["make", "agent-check"])
    mode: ExecutionMode = ExecutionMode.dry_run
    allow_push: bool = False
    output_dir: Path = Path("runtime/pr_repair")
    include_drafts: bool = False
    write_ceiling: TierLevel = TierLevel.t1

    @field_validator("github_repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if "/" not in value or value.count("/") != 1:
            msg = "GITHUB_REPOSITORY must be in owner/repo form"
            raise ValueError(msg)
        return value

    @field_validator("max_prs")
    @classmethod
    def validate_max_prs(cls, value: int) -> int:
        if value < 1:
            msg = "PR_FIX_MAX_PRS must be >= 1"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_config(self) -> "AppConfig":
        if self.allow_push and self.mode is not ExecutionMode.repair_verify_and_push:
            msg = "PR_FIX_ALLOW_PUSH requires mode=repair_verify_and_push"
            raise ValueError(msg)
        return self

    @property
    def repo_owner(self) -> str:
        return self.github_repository.split("/")[0]

    @property
    def repo_name(self) -> str:
        return self.github_repository.split("/")[1]


def load_config(dotenv_path: str = ".env.local") -> AppConfig:
    if Path(dotenv_path).exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)

    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")
    if not github_token:
        msg = "Missing GITHUB_TOKEN"
        raise ValueError(msg)
    if not github_repository:
        msg = "Missing GITHUB_REPOSITORY"
        raise ValueError(msg)

    verify_command = resolve_verify_command_from_env(os.getenv("PR_FIX_VERIFY_COMMAND", "make agent-check"))
    mode = ExecutionMode(os.getenv("PR_FIX_MODE", ExecutionMode.dry_run.value))
    write_ceiling = TierLevel(os.getenv("PR_FIX_WRITE_CEILING", TierLevel.t1.value))

    return AppConfig(
        github_token=github_token,
        github_repository=github_repository,
        coderabbit_api_key=os.getenv("CODERABBIT_API_KEY"),
        codecov_api_key=os.getenv("CODECOV_API_KEY"),
        coderabbit_api_base_url=os.getenv("CODERABBIT_API_BASE_URL"),
        codecov_api_base_url=os.getenv("CODECOV_API_BASE_URL", "https://api.codecov.io"),
        max_prs=int(os.getenv("PR_FIX_MAX_PRS", "5")),
        verify_command=verify_command,
        mode=mode,
        allow_push=os.getenv("PR_FIX_ALLOW_PUSH", "0") == "1",
        output_dir=Path(os.getenv("PR_FIX_OUTPUT_DIR", "runtime/pr_repair")),
        include_drafts=os.getenv("PR_FIX_INCLUDE_DRAFTS", "0") == "1",
        write_ceiling=write_ceiling,
    )


def resolve_verify_command(config: AppConfig) -> list[str]:
    return list(config.verify_command)


def resolve_verify_command_from_env(raw_command: str) -> list[str]:
    parsed = shlex.split(raw_command)
    if not parsed:
        msg = "PR_FIX_VERIFY_COMMAND must not be empty"
        raise ValueError(msg)
    return parsed
