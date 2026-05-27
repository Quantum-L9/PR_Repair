from pr_repair.repair.patch_generator import generate_patch_instructions
from pr_repair.types import ExecutionMode, Finding, PRRef, RepairPlan, Severity, SourceName, TierLevel


def test_generate_patch_instructions_only_emits_line_bound_suggested_repairs() -> None:
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=1,
        title="fix",
        head_branch="fix",
        base_branch="main",
        head_sha="sha",
        is_draft=False,
        author="dev",
        labels=[],
    )
    plan = RepairPlan(
        plan_id="plan",
        pr_ref=pr,
        targeted_findings=[
            Finding(
                finding_id="f-1",
                pr_number=1,
                source_name=SourceName.coderabbit,
                source_priority=100,
                severity=Severity.medium,
                category="lint_failure",
                message="bad line",
                file_path="script.py",
                line_start=2,
                line_end=2,
                suggested_fix="good line",
                repairable=True,
                confidence=0.9,
                fingerprint="fp-1",
                tier_impact=TierLevel.t1,
            ),
            Finding(
                finding_id="f-2",
                pr_number=1,
                source_name=SourceName.coderabbit,
                source_priority=100,
                severity=Severity.medium,
                category="lint_failure",
                message="ignored",
                repairable=True,
                confidence=0.9,
                fingerprint="fp-2",
                tier_impact=TierLevel.t1,
            ),
        ],
        target_files=["script.py"],
        target_tier=TierLevel.t1,
        protected_paths_touched=False,
        verification_command=["make", "agent-check"],
        risk_level="low",
        approval_required=False,
        executable=True,
        execution_mode=ExecutionMode.repair_and_verify,
        rationale="ok",
    )

    instructions = generate_patch_instructions(plan)

    assert instructions == [
        {
            "op": "replace_line",
            "file_path": "script.py",
            "line_number": 2,
            "expected": "bad line",
            "replacement": "good line",
            "finding_id": "f-1",
            "category": "lint_failure",
        }
    ]
