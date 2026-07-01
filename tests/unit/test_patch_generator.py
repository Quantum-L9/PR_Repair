from pathlib import Path

from pr_repair.repair.patch_generator import generate_patch_instructions
from pr_repair.types import (
    ExecutionMode,
    Finding,
    PRRef,
    RepairPlan,
    ReviewDisposition,
    Severity,
    SourceName,
    TierLevel,
)


def _pr() -> PRRef:
    return PRRef(
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


def _plan(findings: list[Finding]) -> RepairPlan:
    return RepairPlan(
        plan_id="plan",
        pr_ref=_pr(),
        targeted_findings=findings,
        target_files=sorted({f.file_path for f in findings if f.file_path}),
        target_tier=TierLevel.t1,
        protected_paths_touched=False,
        verification_command=["make", "agent-check"],
        risk_level="low",
        approval_required=False,
        executable=True,
        execution_mode=ExecutionMode.repair_and_verify,
        rationale="ok",
    )


def test_autofix_replacement_text_takes_precedence_over_suggested_fix(tmp_path: Path) -> None:
    (tmp_path / "engine.py").write_text("a\nPacketEnvelope\nc\n", encoding="utf-8")
    finding = Finding(
        finding_id="af-1",
        pr_number=1,
        source_name=SourceName.agent_review,
        source_priority=110,
        severity=Severity.medium,
        category="lint_failure",
        message="legacy contract",
        file_path="engine.py",
        line_start=2,
        line_end=2,
        suggested_fix="SHOULD_BE_IGNORED",
        replacement_text="TransportPacket",
        rule_id="l9-forbid-packet-envelope",
        review_disposition=ReviewDisposition.autofix,
        repairable=True,
        fingerprint="fp-af-1",
    )

    instructions = generate_patch_instructions(_plan([finding]), tmp_path)

    assert instructions == [
        {
            "op": "replace_line",
            "file_path": "engine.py",
            "line_number": 2,
            "expected": "PacketEnvelope",
            "replacement": "TransportPacket",
            "finding_id": "af-1",
            "rule_id": "l9-forbid-packet-envelope",
            "category": "lint_failure",
        }
    ]


def test_autofix_single_line_skips_when_file_unreadable(tmp_path: Path) -> None:
    # Missing file -> no on-disk guard can be captured -> emit nothing (never fall
    # back to finding.message as the exact-match guard).
    finding = Finding(
        finding_id="af-missing-1",
        pr_number=1,
        source_name=SourceName.agent_review,
        source_priority=110,
        severity=Severity.medium,
        category="lint_failure",
        message="some human readable message",
        file_path="does_not_exist.py",
        line_start=2,
        line_end=2,
        replacement_text="import os",
        review_disposition=ReviewDisposition.autofix,
        repairable=True,
        fingerprint="fp-af-missing-1",
    )

    assert generate_patch_instructions(_plan([finding]), tmp_path) == []


def test_autofix_multiline_skips_when_file_unreadable(tmp_path: Path) -> None:
    # File does not exist -> the on-disk block guard cannot be captured, so no
    # guard-less range patch is emitted.
    finding = Finding(
        finding_id="af-missing",
        pr_number=1,
        source_name=SourceName.agent_review,
        source_priority=110,
        severity=Severity.medium,
        category="lint_failure",
        message="span",
        file_path="does_not_exist.py",
        line_start=2,
        line_end=3,
        replacement_text="y1\ny2",
        review_disposition=ReviewDisposition.autofix,
        repairable=True,
        fingerprint="fp-af-missing",
    )

    assert generate_patch_instructions(_plan([finding]), tmp_path) == []


def test_autofix_multiline_emits_replace_range_with_block_guard(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("h\nx1\nx2\nt\n", encoding="utf-8")
    finding = Finding(
        finding_id="af-2",
        pr_number=1,
        source_name=SourceName.agent_review,
        source_priority=110,
        severity=Severity.medium,
        category="lint_failure",
        message="span",
        file_path="m.py",
        line_start=2,
        line_end=3,
        replacement_text="y1\ny2",
        review_disposition=ReviewDisposition.autofix,
        repairable=True,
        fingerprint="fp-af-2",
    )

    instructions = generate_patch_instructions(_plan([finding]), tmp_path)

    assert instructions == [
        {
            "op": "replace_range",
            "file_path": "m.py",
            "line_start": 2,
            "line_end": 3,
            "expected_block": ["x1", "x2"],
            "replacement": "y1\ny2",
            "finding_id": "af-2",
            "rule_id": None,
            "category": "lint_failure",
        }
    ]


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
                source_name=SourceName.agent_review,
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
                source_name=SourceName.agent_review,
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
