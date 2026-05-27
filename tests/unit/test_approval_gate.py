from pr_repair.config import AppConfig
from pr_repair.planning.approval_gate import requires_human_approval
from pr_repair.types import ExecutionMode, PRRef, RepairPlan, TierLevel


def test_requires_human_approval_returns_false_for_safe_t1_plan(tmp_path) -> None:
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["make", "agent-check"],
        mode=ExecutionMode.dry_run,
        output_dir=tmp_path,
        write_ceiling=TierLevel.t1,
    )
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=11,
        title="Safe plan",
        head_branch="fix/safe",
        base_branch="main",
        head_sha="sha-11",
        is_draft=False,
        author="dev",
        labels=[],
    )
    plan = RepairPlan(
        plan_id="plan-1",
        pr_ref=pr,
        targeted_findings=[],
        target_files=["scripts/example.py"],
        target_tier=TierLevel.t1,
        protected_paths_touched=False,
        verification_command=["make", "agent-check"],
        risk_level="low",
        approval_required=False,
        executable=True,
        execution_mode=ExecutionMode.dry_run,
        rationale="safe",
    )

    assert requires_human_approval(plan, config) is False


def test_requires_human_approval_returns_true_when_tier_exceeds_ceiling(tmp_path) -> None:
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["make", "agent-check"],
        mode=ExecutionMode.dry_run,
        output_dir=tmp_path,
        write_ceiling=TierLevel.t1,
    )
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=12,
        title="Unsafe plan",
        head_branch="fix/unsafe",
        base_branch="main",
        head_sha="sha-12",
        is_draft=False,
        author="dev",
        labels=[],
    )
    plan = RepairPlan(
        plan_id="plan-2",
        pr_ref=pr,
        targeted_findings=[],
        target_files=["app/services/client.py"],
        target_tier=TierLevel.t3,
        protected_paths_touched=False,
        verification_command=["make", "agent-check"],
        risk_level="medium",
        approval_required=True,
        executable=False,
        execution_mode=ExecutionMode.dry_run,
        rationale="unsafe",
    )

    assert requires_human_approval(plan, config) is True
