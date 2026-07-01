import json
from pathlib import Path

from pr_repair.config import AppConfig
from pr_repair.reporting import run_report
from pr_repair.types import ExecutionMode, TierLevel


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


def _config(tmp_path: Path, payload_path: Path) -> AppConfig:
    return AppConfig(
        github_token="token",
        github_repository="owner/repo",
        payload_path=payload_path,
        mode=ExecutionMode.propose_only,
        output_dir=tmp_path / "runtime",
        write_ceiling=TierLevel.t1,
    )


def test_report_writes_proposal_telemetry_trace_and_comment(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "AGENT.md").write_text("# AGENT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    payload_path = tmp_path / "agent_review_payload.json"
    _write_payload(payload_path, pr_number=21)

    assert run_report(_config(tmp_path, payload_path)) == 0

    runtime = tmp_path / "runtime"
    pr_dir = runtime / "prs" / "pr_21"

    # Proposal report captures the autofix candidate and the manual finding.
    report = json.loads((pr_dir / "proposal_report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "propose_only"
    assert report["autofix_candidate_count"] == 1
    assert report["manual_finding_count"] == 1
    assert report["autofix_candidates"][0]["rule_id"] == "py.unused-import"
    # Default NullLLMClient abstains -> no actionable proposal.
    assert report["actionable_proposal_count"] == 0

    # Telemetry inventory (attempted, nothing verified in propose-only).
    telemetry = json.loads((pr_dir / "autofix_telemetry.json").read_text(encoding="utf-8"))
    assert telemetry["totals"]["attempted"] == 1
    assert telemetry["totals"]["verified"] == 0
    assert telemetry["promotion_candidates"] == []

    # Governance comment carries the marker and is written to disk.
    comment = (pr_dir / "implementer_comment.md").read_text(encoding="utf-8")
    assert "<!-- L9:IMPLEMENTER_BOT -->" in comment
    assert "⏳ planned" in comment  # autofix candidate rendered as planned, not applied

    # Auditable trace, including the report-specific completion event.
    trace = json.loads((runtime / "run_trace.json").read_text(encoding="utf-8"))
    events = [entry["event"] for entry in trace]
    assert "payload_ingested" in events
    assert "pipeline_routing" in events
    assert "autofix_telemetry_emitted" in events
    assert "report_complete" in events


def test_report_applies_nothing_to_the_working_tree(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "AGENT.md").write_text("# AGENT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "scripts" / "example.py"
    target.parent.mkdir(parents=True)
    original = "import sys\nprint(sys.argv)\n"
    target.write_text(original, encoding="utf-8")

    payload_path = tmp_path / "agent_review_payload.json"
    _write_payload(payload_path, pr_number=22)

    assert run_report(_config(tmp_path, payload_path)) == 0

    # Proposal-only: the on-disk file is byte-for-byte unchanged.
    assert target.read_text(encoding="utf-8") == original


def test_report_fails_closed_on_missing_payload(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "AGENT.md").write_text("# AGENT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config = _config(tmp_path, tmp_path / "does_not_exist.json")

    assert run_report(config) == 2

    # Even a fail-closed run leaves an auditable trace with the failure event.
    trace = json.loads((tmp_path / "runtime" / "run_trace.json").read_text(encoding="utf-8"))
    events = [entry["event"] for entry in trace]
    assert "payload_ingestion_failed" in events
