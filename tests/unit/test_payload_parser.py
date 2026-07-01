import json
from pathlib import Path

import pytest

from pr_repair.errors import PayloadIngestionError
from pr_repair.ingestion.payload_parser import PayloadParser, parse_payload
from pr_repair.types import ReviewDisposition, Severity, SourceName


def _valid_payload() -> dict:
    return {
        "schema_version": "1.0.0",
        "generated_at": "2026-06-30T00:00:00Z",
        "pr": {
            "repo_owner": "quantum-l9",
            "repo_name": "pr_repair",
            "pr_number": 42,
            "title": "Rename TransportPacket",
            "head_branch": "feature/rename",
            "base_branch": "main",
            "head_sha": "abc123",
            "is_draft": False,
            "author": "audit-bot",
            "labels": ["l9"],
            "changed_files": ["engine/transport.py"],
        },
        "autofix_candidates": [
            {
                "finding_id": "af-1",
                "category": "lint_failure",
                "severity": "medium",
                "message": "Rename TransportPacket to Packet.",
                "file_path": "engine/transport.py",
                "line_start": 10,
                "line_end": 10,
                "replacement_text": "Packet",
                "rule_id": "l9.transport-packet-rename",
                "evidence_url": "https://example.com/af-1",
            }
        ],
        "manual_review_required": [
            {
                "finding_id": "mr-1",
                "category": "architecture_boundary_violation",
                "severity": "high",
                "message": "FastAPI imported inside the engine layer.",
                "file_path": "engine/server.py",
                "line_start": 3,
                "line_end": 3,
                "suggested_fix": None,
            }
        ],
    }


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "agent_review_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_parses_pr_and_both_finding_buckets(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_payload())

    parsed = PayloadParser(path).parse()

    assert parsed.schema_version == "1.0.0"
    assert parsed.pr_ref.pr_number == 42
    assert parsed.pr_ref.repo_full_name == "quantum-l9/pr_repair"
    assert len(parsed.autofix_findings) == 1
    assert len(parsed.manual_review_findings) == 1
    # findings property orders autofix candidates first.
    assert parsed.findings[0].finding_id == "af-1"


def test_autofix_finding_is_repairable_and_carries_replacement(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_payload())

    af = PayloadParser(path).parse().autofix_findings[0]

    assert af.source_name is SourceName.agent_review
    assert af.review_disposition is ReviewDisposition.autofix
    assert af.repairable is True
    assert af.replacement_text == "Packet"
    assert af.rule_id == "l9.transport-packet-rename"
    assert af.severity is Severity.medium
    assert af.fingerprint and af.fingerprint != "pending"


def test_tool_actuation_fields_are_parsed(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["autofix_candidates"][0].update(
        {"tags": ["style", "auto"], "tool": "coderabbit", "thread_id": "PRRT_x", "comment_id": 555}
    )
    path = _write(tmp_path, payload)

    af = PayloadParser(path).parse().autofix_findings[0]

    assert af.tags == ["style", "auto"]
    assert af.tool == "coderabbit"
    assert af.thread_id == "PRRT_x"
    assert af.comment_id == 555


def test_tool_actuation_fields_default_empty_when_absent(tmp_path: Path) -> None:
    mr = PayloadParser(_write(tmp_path, _valid_payload())).parse().manual_review_findings[0]

    assert mr.tags == []
    assert mr.tool is None
    assert mr.thread_id is None
    assert mr.comment_id is None


def test_manual_finding_is_not_repairable(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_payload())

    mr = PayloadParser(path).parse().manual_review_findings[0]

    assert mr.review_disposition is ReviewDisposition.manual_review
    assert mr.repairable is False
    assert mr.replacement_text is None


def test_fingerprints_are_deterministic(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_payload())

    first = PayloadParser(path).parse().findings
    second = PayloadParser(path).parse().findings

    assert [f.fingerprint for f in first] == [f.fingerprint for f in second]


def test_to_bundle_collects_all_findings(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_payload())

    bundle = PayloadParser(path).parse().to_bundle()

    assert len(bundle.agent_review_findings) == 2
    assert len(bundle.merged_findings) == 2
    assert bundle.github_check_findings == []


def test_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(PayloadIngestionError, match="not found"):
        PayloadParser(tmp_path / "missing.json").parse()


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "agent_review_payload.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(PayloadIngestionError, match="not valid JSON"):
        PayloadParser(path).parse()


def test_non_object_payload_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "agent_review_payload.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(PayloadIngestionError, match="must be a JSON object"):
        PayloadParser(path).parse()


def test_invalid_schema_document_fails_closed(tmp_path: Path) -> None:
    payload_path = _write(tmp_path, _valid_payload())
    schema_path = tmp_path / "broken-schema.json"
    # A structurally-valid JSON object that is not a valid JSON Schema:
    # ``type`` must be a string or array of strings, never an integer.
    schema_path.write_text(json.dumps({"type": 123}), encoding="utf-8")

    with pytest.raises(PayloadIngestionError, match="not a valid JSON Schema"):
        PayloadParser(payload_path, schema_path=schema_path).parse()


def test_missing_required_top_level_key_fails_schema(tmp_path: Path) -> None:
    payload = _valid_payload()
    del payload["autofix_candidates"]
    path = _write(tmp_path, payload)

    with pytest.raises(PayloadIngestionError, match="schema validation"):
        PayloadParser(path).parse()


def test_autofix_candidate_without_replacement_text_fails_schema(tmp_path: Path) -> None:
    payload = _valid_payload()
    del payload["autofix_candidates"][0]["replacement_text"]
    path = _write(tmp_path, payload)

    with pytest.raises(PayloadIngestionError, match="schema validation"):
        PayloadParser(path).parse()


def test_invalid_severity_fails_schema(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["manual_review_required"][0]["severity"] = "blocker"
    path = _write(tmp_path, payload)

    with pytest.raises(PayloadIngestionError, match="schema validation"):
        PayloadParser(path).parse()


def test_bad_schema_version_format_fails_schema(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["schema_version"] = "v1"
    path = _write(tmp_path, payload)

    with pytest.raises(PayloadIngestionError, match="schema validation"):
        PayloadParser(path).parse()


def test_empty_finding_buckets_are_allowed(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["autofix_candidates"] = []
    payload["manual_review_required"] = []
    path = _write(tmp_path, payload)

    parsed = PayloadParser(path).parse()

    assert parsed.findings == []


def test_parse_payload_convenience_wrapper(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_payload())

    parsed = parse_payload(path)

    assert parsed.pr_ref.pr_number == 42


def test_corrupt_schema_fails_closed(tmp_path: Path) -> None:
    payload_path = _write(tmp_path, _valid_payload())
    bad_schema = tmp_path / "schema.json"
    bad_schema.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(PayloadIngestionError, match="schema .* is not valid JSON"):
        PayloadParser(payload_path, schema_path=bad_schema).parse()


def test_non_object_schema_fails_closed(tmp_path: Path) -> None:
    payload_path = _write(tmp_path, _valid_payload())
    bad_schema = tmp_path / "schema.json"
    bad_schema.write_text("[]", encoding="utf-8")

    with pytest.raises(PayloadIngestionError, match="schema .* must be a JSON object"):
        PayloadParser(payload_path, schema_path=bad_schema).parse()
