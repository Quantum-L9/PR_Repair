from pr_repair.learning.pattern_extractor import extract_learning_packets
from pr_repair.types import ExecutionMode, PRRef, RepairExecution, VerificationReport


def test_extract_learning_packets_groups_failures_by_pr() -> None:
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=31,
        title="repair",
        head_branch="fix/repair",
        base_branch="main",
        head_sha="sha-31",
        is_draft=False,
        author="dev",
        labels=[],
    )
    execution = RepairExecution(
        execution_id="exec-1",
        pr_ref=pr,
        plan_id="plan-1",
        mode=ExecutionMode.repair_and_verify,
        verification_result=VerificationReport(
            command=["make", "agent-check"],
            success=False,
            exit_code=2,
            stdout="",
            stderr="failed",
        ),
        status="rolled_back_verification_failed",
    )

    packets = extract_learning_packets([execution])

    assert len(packets) == 1
    assert packets[0].source_prs == [31]
    assert "rolled_back_verification_failed" in packets[0].repeated_failures
    assert "verification_make_agent_check_failure" in packets[0].repeated_failures
