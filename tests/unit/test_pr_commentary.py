from pr_repair.output.pr_commentary import build_pr_comment
from pr_repair.types import ExecutionMode, Finding, PRRef, RepairExecution, Severity, SourceName


def test_build_pr_comment_uses_contract_template_for_violation() -> None:
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=61,
        title="repair",
        head_branch="fix/repair",
        base_branch="main",
        head_sha="sha-61",
        is_draft=False,
        author="dev",
        labels=[],
    )
    execution = RepairExecution(
        execution_id="exec-61",
        pr_ref=pr,
        plan_id="plan-61",
        mode=ExecutionMode.dry_run,
        status="approval_required",
    )
    finding = Finding(
        finding_id="f-61",
        pr_number=61,
        source_name=SourceName.agent_review,
        source_priority=100,
        severity=Severity.high,
        category="architecture_boundary_violation",
        message="from fastapi import FastAPI in engine module",
        file_path="engine/module.py",
        line_start=8,
        line_end=8,
        suggested_fix="Remove FastAPI import from engine module.",
        confidence=0.9,
        fingerprint="fp-61",
        contract_ids=["C-01"],
        repo_rule_sources=["AGENT.md", "AI_AGENT_REVIEW_CHECKLIST.md"],
    )

    comment = build_pr_comment(execution, [finding])

    assert "CONTRACT C-01 VIOLATION" in comment
    assert "File: engine/module.py Line: 8" in comment
