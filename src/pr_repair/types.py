# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [models]
# tags: [contracts, typed-models, runtime]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class ExecutionMode(str, Enum):
    dry_run = "dry_run"
    propose_only = "propose_only"
    repair_and_verify = "repair_and_verify"
    repair_verify_and_push = "repair_verify_and_push"
    learn_only = "learn_only"


class SourceName(str, Enum):
    agent_review = "agent_review"
    github_checks = "github_checks"
    github_review_comments = "github_review_comments"
    github_issue_comments = "github_issue_comments"


class ReviewDisposition(str, Enum):
    """How the upstream agent review routed a finding."""

    autofix = "autofix"
    manual_review = "manual_review"


class TierLevel(str, Enum):
    t0 = "T0"
    t1 = "T1"
    t2 = "T2"
    t3 = "T3"
    t4 = "T4"
    t5 = "T5"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class PRRef(BaseModel):
    repo_owner: str
    repo_name: str
    pr_number: int
    title: str
    head_branch: str
    base_branch: str
    head_sha: str
    is_draft: bool
    author: str
    labels: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)

    @property
    def repo_full_name(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"


class Finding(BaseModel):
    finding_id: str
    pr_number: int
    source_name: SourceName
    source_priority: int
    severity: Severity
    category: str
    message: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    suggested_fix: str | None = None
    replacement_text: str | None = None
    rule_id: str | None = None
    review_disposition: ReviewDisposition | None = None
    evidence_url: str | None = None
    repairable: bool = False
    confidence: float = 0.0
    fingerprint: str
    tier_impact: TierLevel = TierLevel.t0
    protected_path: bool = False
    skip_review_path: bool = False
    contract_ids: list[str] = Field(default_factory=list)
    repo_rule_sources: list[str] = Field(default_factory=list)
    root_cause_key: str | None = None
    classification_reason: str = ""

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "confidence must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_line_range(self) -> "Finding":
        if self.line_start is not None and self.line_start < 1:
            msg = "line_start must be >= 1"
            raise ValueError(msg)
        if self.line_end is not None and self.line_end < 1:
            msg = "line_end must be >= 1"
            raise ValueError(msg)
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            msg = "line_end must be >= line_start"
            raise ValueError(msg)
        return self


class NormalizationError(BaseModel):
    source_name: str
    pr_number: int
    error_type: str
    error_message: str
    payload_excerpt: dict[str, Any]


class FindingBundle(BaseModel):
    pr_ref: PRRef
    agent_review_findings: list[Finding] = Field(default_factory=list)
    github_check_findings: list[Finding] = Field(default_factory=list)
    github_comment_findings: list[Finding] = Field(default_factory=list)
    merged_findings: list[Finding] = Field(default_factory=list)
    normalization_errors: list[NormalizationError] = Field(default_factory=list)


class RepairPlan(BaseModel):
    plan_id: str
    pr_ref: PRRef
    targeted_findings: list[Finding]
    target_files: list[str]
    target_tier: TierLevel
    protected_paths_touched: bool
    verification_command: list[str]
    risk_level: Literal["low", "medium", "high"]
    approval_required: bool
    executable: bool
    execution_mode: ExecutionMode
    rationale: str


class VerificationReport(BaseModel):
    command: list[str]
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime = Field(default_factory=utc_now)


class RepairExecution(BaseModel):
    execution_id: str
    pr_ref: PRRef
    plan_id: str
    mode: ExecutionMode
    modified_files: list[str] = Field(default_factory=list)
    verification_result: VerificationReport | None = None
    push_result: str | None = None
    review_comment_payload: str | None = None
    status: str


class LearningPacket(BaseModel):
    packet_id: str
    source_prs: list[int]
    repeated_failures: list[str]
    agent_md_recommendations: list[str]
    validator_recommendations: list[str]
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("confidence")
    @classmethod
    def validate_learning_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "confidence must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value


class RuntimeState(BaseModel):
    run_id: str
    mode: ExecutionMode
    repo: str
    started_at: datetime = Field(default_factory=utc_now)
    current_phase: str
    completed_phases: list[str] = Field(default_factory=list)
    pr_numbers: list[int] = Field(default_factory=list)
    artifact_dir: Path
    status: Literal["running", "completed", "failed"] = "running"


class RepoContext(BaseModel):
    protected_paths: list[str] = Field(default_factory=list)
    skip_review_paths: list[str] = Field(default_factory=list)
    write_ceiling: TierLevel = TierLevel.t1
    required_verification_command: list[str] = Field(
        default_factory=lambda: ["make", "agent-check"]
    )
    source_documents: list[str] = Field(default_factory=list)
    repo_map_path: Path | None = None
    agent_md_path: Path | None = None


class InterpretationReport(BaseModel):
    pr_number: int
    raw_count: int
    normalized_count: int
    deduped_count: int
    protected_path_findings: int
    contract_violation_findings: int
    repairable_count: int
    escalation_required_count: int
    normalization_error_count: int

class FindingCluster(BaseModel):
    cluster_id: str
    pr_number: int
    category: str
    root_cause_key: str
    files: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"]
    repairability: Literal["auto_repairable", "approval_required", "never_auto"]


class RepairCandidate(BaseModel):
    candidate_id: str
    pr_number: int
    cluster_ids: list[str]
    target_files: list[str]
    risk_level: Literal["low", "medium", "high"]
    approval_required: bool
    verification_command: list[str]
    justification: str
