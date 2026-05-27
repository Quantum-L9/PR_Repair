from pathlib import Path

from pr_repair.config import AppConfig
from pr_repair.pipeline import run_pipeline
from pr_repair.types import (
    ExecutionMode,
    Finding,
    FindingBundle,
    PRRef,
    RepairExecution,
    Severity,
    SourceName,
    TierLevel,
)


def test_run_pipeline_repair_mode_writes_execution_and_learning_artifacts(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "AGENT.md").write_text("# AGENT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=11,
        title="repair",
        head_branch="fix-11",
        base_branch="main",
        head_sha="sha-11",
        is_draft=False,
        author="dev",
        labels=[],
    )
    finding = Finding(
        finding_id="f-11",
        pr_number=11,
        source_name=SourceName.coderabbit,
        source_priority=100,
        severity=Severity.medium,
        category="lint_failure",
        message="Unused import detected.",
        file_path="scripts/example.py",
        line_start=1,
        line_end=1,
        suggested_fix="import os",
        repairable=True,
        confidence=0.9,
        fingerprint="fp-11",
        tier_impact=TierLevel.t1,
    )
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["python", "-c", "print('ok')"],
        mode=ExecutionMode.repair_and_verify,
        output_dir=tmp_path / "runtime",
        write_ceiling=TierLevel.t1,
    )

    monkeypatch.setattr("pr_repair.pipeline.run_pipeline.collect_candidate_prs", lambda cfg: [pr])
    monkeypatch.setattr(
        "pr_repair.pipeline.run_pipeline.ingest_tool_findings",
        lambda cfg, pr_obj, state_store=None: FindingBundle(pr_ref=pr_obj, coderabbit_findings=[finding]),
    )
    monkeypatch.setattr(
        "pr_repair.pipeline.run_pipeline.ingest_comment_findings",
        lambda cfg, pr_obj, bundle, state_store=None: bundle,
    )
    monkeypatch.setattr(
        "pr_repair.pipeline.run_pipeline.execute_repair_plan",
        lambda plan, cfg, repo_root=None: RepairExecution(
            execution_id="exec-11",
            pr_ref=plan.pr_ref,
            plan_id=plan.plan_id,
            mode=plan.execution_mode,
            status="completed",
        ),
    )

    result = run_pipeline(config)

    assert result == 0
    assert (tmp_path / "runtime" / "pr_inventory.json").exists()
    assert (tmp_path / "runtime" / "repair_plans.yaml").exists()
    assert (tmp_path / "runtime" / "learning_report.md").exists()
    assert (tmp_path / "runtime" / "prs" / "pr_11" / "repair_plan.json").exists()


def test_run_pipeline_multi_pr_does_not_overwrite_per_pr_artifacts(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "AGENT.md").write_text("# AGENT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    pr1 = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=21,
        title="repair1",
        head_branch="fix-21",
        base_branch="main",
        head_sha="sha-21",
        is_draft=False,
        author="dev",
        labels=[],
    )
    pr2 = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=22,
        title="repair2",
        head_branch="fix-22",
        base_branch="main",
        head_sha="sha-22",
        is_draft=False,
        author="dev",
        labels=[],
    )
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["python", "-c", "print('ok')"],
        mode=ExecutionMode.dry_run,
        output_dir=tmp_path / "runtime",
        write_ceiling=TierLevel.t1,
    )

    def fake_ingest(cfg, pr_obj, state_store=None):
        finding = Finding(
            finding_id=f"f-{pr_obj.pr_number}",
            pr_number=pr_obj.pr_number,
            source_name=SourceName.coderabbit,
            source_priority=100,
            severity=Severity.medium,
            category="lint_failure",
            message="Unused import detected.",
            file_path="scripts/example.py",
            line_start=1,
            line_end=1,
            suggested_fix="import os",
            repairable=True,
            confidence=0.9,
            fingerprint=f"fp-{pr_obj.pr_number}",
            tier_impact=TierLevel.t1,
        )
        return FindingBundle(pr_ref=pr_obj, coderabbit_findings=[finding])

    monkeypatch.setattr("pr_repair.pipeline.run_pipeline.collect_candidate_prs", lambda cfg: [pr1, pr2])
    monkeypatch.setattr("pr_repair.pipeline.run_pipeline.ingest_tool_findings", fake_ingest)
    monkeypatch.setattr(
        "pr_repair.pipeline.run_pipeline.ingest_comment_findings",
        lambda cfg, pr_obj, bundle, state_store=None: bundle,
    )

    result = run_pipeline(config)

    assert result == 0
    assert (tmp_path / "runtime" / "prs" / "pr_21" / "repair_plan.json").exists()
    assert (tmp_path / "runtime" / "prs" / "pr_22" / "repair_plan.json").exists()
