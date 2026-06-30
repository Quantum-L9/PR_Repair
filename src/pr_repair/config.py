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
    payload_path: Path = Path("artifacts/agent_review_payload.json")
    post_comment: bool = False
    llm_enabled: bool = False
    llm_client_id: str = "implementer-bot"
    llm_shim_path: Path = Path("router-shim/shim.mjs")
    llm_node_bin: str = "node"
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
        payload_path=Path(
            os.getenv("PR_FIX_PAYLOAD_PATH", "artifacts/agent_review_payload.json")
        ),
        post_comment=os.getenv("PR_FIX_POST_COMMENT", "0") == "1",
        llm_enabled=os.getenv("PR_FIX_LLM_ENABLED", "0") == "1",
        llm_client_id=os.getenv("PR_FIX_LLM_CLIENT_ID", "implementer-bot"),
        llm_shim_path=Path(os.getenv("PR_FIX_LLM_SHIM_PATH", "router-shim/shim.mjs")),
        llm_node_bin=os.getenv("PR_FIX_LLM_NODE_BIN", "node"),
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
