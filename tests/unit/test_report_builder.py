from pr_repair.types import ExecutionMode, PRRef, RepairExecution, VerificationReport
from pr_repair.verification.report_builder import (
    build_pr_result_markdown,
    build_verification_markdown,
)


def test_build_verification_markdown_contains_expected_sections() -> None:
    report = VerificationReport(
        command=["make", "agent-check"],
        success=True,
        exit_code=0,
        stdout="ok",
        stderr="",
    )

    content = build_verification_markdown(report)

    assert "# Verification report" in content
    assert "make agent-check" in content
    assert "```text" in content


def test_build_pr_result_markdown_contains_execution_summary() -> None:
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=91,
        title="repair",
        head_branch="fix/repair",
        base_branch="main",
        head_sha="sha-91",
        is_draft=False,
        author="dev",
        labels=[],
    )
    execution = RepairExecution(
        execution_id="exec-91",
        pr_ref=pr,
        plan_id="plan-91",
        mode=ExecutionMode.repair_and_verify,
        status="completed",
    )

    content = build_pr_result_markdown(execution)

    assert "owner/repo#91" in content
    assert "plan-91" in content
    assert "completed" in content
