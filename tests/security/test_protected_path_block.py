from pr_repair.config import AppConfig
from pr_repair.planning.repair_planner import build_repair_plan
from pr_repair.types import ExecutionMode, Finding, PRRef, Severity, SourceName, TierLevel


def test_protected_path_finding_blocks_execution(tmp_path) -> None:
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["make", "agent-check"],
        mode=ExecutionMode.repair_and_verify,
        output_dir=tmp_path,
        write_ceiling=TierLevel.t1,
    )
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=303,
        title="schema touch",
        head_branch="fix/schema",
        base_branch="main",
        head_sha="sha-303",
        is_draft=False,
        author="dev",
        labels=[],
    )
    findings = [
        Finding(
            finding_id="f-303",
            pr_number=303,
            source_name=SourceName.agent_review,
            source_priority=100,
            severity=Severity.high,
            category="protected_file_violation",
            message="Protected schema file touched.",
            file_path="app/models/entity.py",
            line_start=1,
            line_end=1,
            repairable=False,
            confidence=0.9,
            fingerprint="fp-303",
            tier_impact=TierLevel.t5,
            protected_path=True,
        )
    ]

    plan = build_repair_plan(pr, findings, config)

    assert plan.executable is False
    assert plan.approval_required is True
    assert plan.risk_level == "high"
