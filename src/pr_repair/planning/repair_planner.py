# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [planning]
# tags: [repair-plan, repo-aware, risk]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import uuid
from typing import Literal

from pr_repair.classification.classifier import is_never_auto_repair, requires_approval_for_category
from pr_repair.config import AppConfig, resolve_verify_command
from pr_repair.priorities import TIER_ORDER, is_within_write_ceiling
from pr_repair.types import Finding, PRRef, RepairPlan, TierLevel


def build_repair_plan(pr: PRRef, findings: list[Finding], config: AppConfig) -> RepairPlan:
    """
    Build a deterministic PR-scoped repair plan from classified findings.

    Planning rules:
    - target only findings explicitly marked repairable
    - compute highest impacted tier from target files
    - block execution when plan exceeds write ceiling
    - block execution when protected paths are touched
    - require approval for non-low-risk or approval-gated categories
    """
    targetable_findings = [finding for finding in findings if finding.repairable]
    target_files = sorted({finding.file_path for finding in targetable_findings if finding.file_path})
    protected_paths_touched = any(finding.protected_path for finding in findings)
    target_tier = _max_tier(targetable_findings)
    verification_command = resolve_verify_command(config)
    risk_level = _risk_level(findings, protected_paths_touched, target_tier)
    approval_required = _approval_required(findings, protected_paths_touched, risk_level, target_tier)
    executable = _is_executable(
        targetable_findings=targetable_findings,
        protected_paths_touched=protected_paths_touched,
        target_tier=target_tier,
        config=config,
    )
    rationale = _build_rationale(
        pr=pr,
        targetable_findings=targetable_findings,
        protected_paths_touched=protected_paths_touched,
        target_tier=target_tier,
        risk_level=risk_level,
        approval_required=approval_required,
        executable=executable,
    )

    return RepairPlan(
        plan_id=str(uuid.uuid4()),
        pr_ref=pr,
        targeted_findings=targetable_findings,
        target_files=target_files,
        target_tier=target_tier,
        protected_paths_touched=protected_paths_touched,
        verification_command=verification_command,
        risk_level=risk_level,
        approval_required=approval_required,
        executable=executable,
        execution_mode=config.mode,
        rationale=rationale,
    )


def _max_tier(findings: list[Finding]) -> TierLevel:
    if not findings:
        return TierLevel.t0
    return max(findings, key=lambda item: TIER_ORDER[item.tier_impact]).tier_impact


def _risk_level(
    findings: list[Finding],
    protected_paths_touched: bool,
    target_tier: TierLevel,
) -> Literal["low", "medium", "high"]:
    if protected_paths_touched:
        return "high"
    if target_tier in {TierLevel.t4, TierLevel.t5}:
        return "high"
    if any(item.severity.value == "critical" for item in findings):
        return "high"
    if any(item.severity.value == "high" for item in findings):
        return "medium"
    if any(requires_approval_for_category(item.category) for item in findings):
        return "medium"
    return "low"


def _approval_required(
    findings: list[Finding],
    protected_paths_touched: bool,
    risk_level: str,
    target_tier: TierLevel,
) -> bool:
    if protected_paths_touched:
        return True
    if target_tier in {TierLevel.t3, TierLevel.t4, TierLevel.t5}:
        return True
    if risk_level != "low":
        return True
    return any(requires_approval_for_category(item.category) for item in findings)


def _is_executable(
    *,
    targetable_findings: list[Finding],
    protected_paths_touched: bool,
    target_tier: TierLevel,
    config: AppConfig,
) -> bool:
    if not targetable_findings:
        return False
    if protected_paths_touched:
        return False
    if not is_within_write_ceiling(target_tier, config.write_ceiling):
        return False
    if any(is_never_auto_repair(item.category) for item in targetable_findings):
        return False
    return True


def _build_rationale(
    *,
    pr: PRRef,
    targetable_findings: list[Finding],
    protected_paths_touched: bool,
    target_tier: TierLevel,
    risk_level: str,
    approval_required: bool,
    executable: bool,
) -> str:
    return (
        f"pr={pr.pr_number}; "
        f"repairable_findings={len(targetable_findings)}; "
        f"protected_paths_touched={protected_paths_touched}; "
        f"target_tier={target_tier.value}; "
        f"risk_level={risk_level}; "
        f"approval_required={approval_required}; "
        f"executable={executable}"
    )
