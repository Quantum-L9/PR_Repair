import json
from pathlib import Path

from pr_repair.config import AppConfig
from pr_repair.pipeline import run_pipeline
from pr_repair.types import ExecutionMode, RepairExecution, TierLevel


def _write_payload(path: Path, pr_number: int) -> None:
    payload = {
        "schema_version": "1.0.0",
        "pr": {
            "repo_owner": "owner",
            "repo_name": "repo",
            "pr_number": pr_number,
            "title": "repair",
            "head_branch": f"fix-{pr_number}",
            "base_branch": "main",
            "head_sha": f"sha-{pr_number}",
            "is_draft": False,
            "author": "dev",
            "labels": [],
            "changed_files": ["scripts/example.py"],
        },
        "autofix_candidates": [
            {
                "finding_id": f"af-{pr_number}",
                "category": "lint_failure",
                "severity": "medium",
                "message": "Unused import detected.",
                "file_path": "scripts/example.py",
                "line_start": 1,
                "line_end": 1,
                "replacement_text": "import os",
                "rule_id": "py.unused-import",
            }
        ],
        "manual_review_required": [
            {
                "finding_id": f"mr-{pr_number}",
                "category": "architecture_boundary_violation",
                "severity": "high",
                "message": "FastAPI imported inside engine layer.",
                "file_path": "engine/example.py",
                "line_start": 3,
                "line_end": 3,
                "suggested_fix": None,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_pipeline_repair_mode_writes_execution_and_learning_artifacts(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "AGENT.md").write_text("# AGENT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    payload_path = tmp_path / "agent_review_payload.json"
    _write_payload(payload_path, pr_number=11)

    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        payload_path=payload_path,
        verify_command=["python", "-c", "print('ok')"],
        mode=ExecutionMode.repair_and_verify,
        output_dir=tmp_path / "runtime",
        write_ceiling=TierLevel.t1,
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
    # W6: telemetry + trace artifacts
    assert (tmp_path / "runtime" / "prs" / "pr_11" / "autofix_telemetry.json").exists()
    trace_path = tmp_path / "runtime" / "run_trace.json"
    assert trace_path.exists()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    events = [entry["event"] for entry in trace]
    assert "payload_ingested" in events
    assert "pipeline_routing" in events
    assert "autofix_telemetry_emitted" in events


def test_run_pipeline_fails_closed_when_payload_missing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "AGENT.md").write_text("# AGENT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        payload_path=tmp_path / "does_not_exist.json",
        verify_command=["python", "-c", "print('ok')"],
        mode=ExecutionMode.dry_run,
        output_dir=tmp_path / "runtime",
        write_ceiling=TierLevel.t1,
    )

    result = run_pipeline(config)

    assert result == 2
    # Fail-closed: no per-PR repair artifacts are written.
    assert not (tmp_path / "runtime" / "prs").exists()
    # ...but the run trace is still emitted, capturing the failure.
    trace_path = tmp_path / "runtime" / "run_trace.json"
    assert trace_path.exists()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert "payload_ingestion_failed" in [entry["event"] for entry in trace]
