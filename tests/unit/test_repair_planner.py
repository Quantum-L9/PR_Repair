from pr_repair.config import AppConfig
from pr_repair.planning.repair_planner import build_repair_plan
from pr_repair.types import ExecutionMode, Finding, PRRef, Severity, SourceName, TierLevel


def test_build_repair_plan_marks_low_risk_t1_plan_executable(tmp_path) -> None:
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
        pr_number=9,
        title="Fix lint",
        head_branch="fix/lint",
        base_branch="main",
        head_sha="sha-9",
        is_draft=False,
        author="dev",
        labels=[],
    )
    findings = [
        Finding(
            finding_id="f-1",
            pr_number=9,
            source_name=SourceName.agent_review,
            source_priority=100,
            severity=Severity.medium,
            category="lint_failure",
            message="Unused import detected.",
            file_path="scripts/example.py",
            line_start=3,
            line_end=3,
            repairable=True,
            confidence=0.9,
            fingerprint="fp-1",
            tier_impact=TierLevel.t1,
            protected_path=False,
            skip_review_path=False,
            classification_reason="category=lint_failure",
        )
    ]

    plan = build_repair_plan(pr, findings, config)

    assert plan.executable is True
    assert plan.approval_required is False
    assert plan.risk_level == "low"
    assert plan.target_tier is TierLevel.t1
    assert plan.target_files == ["scripts/example.py"]


def test_build_repair_plan_blocks_protected_path_execution(tmp_path) -> None:
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
        pr_number=10,
        title="Touch schema",
        head_branch="fix/schema",
        base_branch="main",
        head_sha="sha-10",
        is_draft=False,
        author="dev",
        labels=[],
    )
    findings = [
        Finding(
            finding_id="f-2",
            pr_number=10,
            source_name=SourceName.agent_review,
            source_priority=100,
            severity=Severity.high,
            category="protected_file_violation",
            message="Protected schema file touched.",
            file_path="app/models/entity.py",
            line_start=5,
            line_end=5,
            repairable=False,
            confidence=0.9,
            fingerprint="fp-2",
            tier_impact=TierLevel.t5,
            protected_path=True,
            skip_review_path=False,
            contract_ids=["T5"],
            classification_reason="category=protected_file_violation",
        )
    ]

    plan = build_repair_plan(pr, findings, config)

    assert plan.executable is False
    assert plan.approval_required is True
    assert plan.risk_level == "high"
