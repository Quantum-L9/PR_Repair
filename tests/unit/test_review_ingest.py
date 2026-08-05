"""Tests for the review->agent_review_payload.json runtime entrypoint.

Covers both input modes (offline --context and live --event-path), the three
exit-code outcomes (produced/skipped/failed), and downstream compatibility: a
produced payload must parse+validate through the real PayloadParser the pipeline
uses. Failure and skip paths must never leave a payload file behind.
"""

import json

from pr_repair import review_ingest
from pr_repair.ingestion.payload_parser import PayloadParser

FIXED_TS = "2026-07-01T00:00:00+00:00"

_PR = {
    "repo_owner": "owner",
    "repo_name": "repo",
    "pr_number": 7,
    "title": "Add feature",
    "head_branch": "fix",
    "base_branch": "main",
    "head_sha": "abc123",
    "author": "dev",
    "is_draft": False,
    "labels": [],
}


def _thread(body, *, resolved=False, login="copilot-pull-request-reviewer[bot]", tid="PRRT_1", cid=5001):
    return {
        "id": tid,
        "isResolved": resolved,
        "path": "engine.py",
        "line": 2,
        "comments": {
            "nodes": [
                {"id": "PRRC_1", "databaseId": cid, "body": body, "author": {"login": login}, "url": "https://x"}
            ]
        },
    }


class _FakeConn:
    """Serves fixed review threads; matches GitHubConnector.get_review_threads."""

    def __init__(self, threads):
        self._threads = threads

    def get_review_threads(self, owner, repo, pr):
        return self._threads


def _event(*, review_login="copilot-pull-request-reviewer[bot]", with_pr=True):
    event = {
        "repository": {"name": "repo", "owner": {"login": "owner"}, "full_name": "owner/repo"},
        "review": {"user": {"login": review_login}},
    }
    if with_pr:
        event["pull_request"] = {
            "number": 7,
            "title": "Add feature",
            "draft": False,
            "labels": [{"name": "bug"}],
            "head": {"ref": "fix", "sha": "abc123"},
            "base": {"ref": "main"},
            "user": {"login": "dev"},
        }
    return event


# --- offline --context mode ------------------------------------------------

def test_context_produces_schema_valid_payload(tmp_path):
    ctx = {
        "tool": "copilot",
        "pr": _PR,
        "threads": [
            _thread("Rename it.\n```suggestion\nTransportPacket\n```"),
            _thread("This crosses an architecture boundary.", tid="PRRT_2", cid=5002),
        ],
    }
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps(ctx), encoding="utf-8")
    out = tmp_path / "artifacts" / "agent_review_payload.json"

    rc = review_ingest.run(output=str(out), context=str(ctx_path), generated_at=FIXED_TS)

    assert rc == review_ingest.EXIT_PRODUCED
    assert out.exists()
    # Downstream compatibility: the real parser the pipeline uses must accept it.
    parsed = PayloadParser(out).parse()
    assert [f.finding_id for f in parsed.autofix_findings] == ["copilot-5001"]
    assert [f.finding_id for f in parsed.manual_review_findings] == ["copilot-5002"]
    # The suggestion became an exact autofix; the plain comment did not.
    assert parsed.autofix_findings[0].replacement_text == "TransportPacket"
    assert parsed.manual_review_findings[0].replacement_text is None


def test_empty_but_valid_review_is_produced_not_faked(tmp_path):
    # A recognized tool that left no actionable threads yields a valid payload
    # with empty arrays. This is legitimate (input was valid), not a fake success.
    ctx = {"tool": "copilot", "pr": _PR, "threads": []}
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps(ctx), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(output=str(out), context=str(ctx_path), generated_at=FIXED_TS)

    assert rc == review_ingest.EXIT_PRODUCED
    parsed = PayloadParser(out).parse()
    assert parsed.autofix_findings == []
    assert parsed.manual_review_findings == []


def test_missing_required_pr_field_fails_closed(tmp_path):
    bad_pr = dict(_PR)
    del bad_pr["head_sha"]
    ctx = {"tool": "copilot", "pr": bad_pr, "threads": []}
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps(ctx), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(output=str(out), context=str(ctx_path), generated_at=FIXED_TS)

    assert rc == review_ingest.EXIT_FAILED
    assert not out.exists()  # no payload left behind on failure


def test_malformed_json_fails_closed(tmp_path):
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text("{ this is not valid json", encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(output=str(out), context=str(ctx_path))

    assert rc == review_ingest.EXIT_FAILED
    assert not out.exists()


def test_unknown_tool_in_context_fails(tmp_path):
    ctx = {"tool": "acme-linter", "pr": _PR, "threads": []}
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps(ctx), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(output=str(out), context=str(ctx_path))

    assert rc == review_ingest.EXIT_FAILED
    assert not out.exists()


def test_missing_input_file_fails(tmp_path):
    rc = review_ingest.run(output=str(tmp_path / "p.json"), context=str(tmp_path / "nope.json"))
    assert rc == review_ingest.EXIT_FAILED


# --- live --event-path mode ------------------------------------------------

def test_collect_from_event_produces_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_event()), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(
        output=str(out),
        event_path=str(event_path),
        generated_at=FIXED_TS,
        connector_factory=lambda token: _FakeConn([_thread("Fix.\n```suggestion\nok\n```")]),
    )

    assert rc == review_ingest.EXIT_PRODUCED
    parsed = PayloadParser(out).parse()
    assert parsed.pr_ref.repo_owner == "owner"
    assert parsed.pr_ref.pr_number == 7
    assert parsed.pr_ref.head_sha == "abc123"
    assert [f.finding_id for f in parsed.autofix_findings] == ["copilot-5001"]


def test_human_review_skips_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_event(review_login="a-human-dev")), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(
        output=str(out),
        event_path=str(event_path),
        connector_factory=lambda token: _FakeConn([]),
    )

    assert rc == review_ingest.EXIT_SKIPPED
    assert not out.exists()  # skip must not produce a payload


def test_event_without_pull_request_skips(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_event(with_pr=False)), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(
        output=str(out),
        event_path=str(event_path),
        connector_factory=lambda token: _FakeConn([]),
    )

    assert rc == review_ingest.EXIT_SKIPPED
    assert not out.exists()


def test_event_mode_requires_token(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_event()), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.run(
        output=str(out),
        event_path=str(event_path),
        connector_factory=lambda token: _FakeConn([]),
    )

    assert rc == review_ingest.EXIT_FAILED
    assert not out.exists()


def test_no_input_source_fails(tmp_path):
    rc = review_ingest.run(output=str(tmp_path / "p.json"))
    assert rc == review_ingest.EXIT_FAILED


# --- CLI surface -----------------------------------------------------------

def test_main_entrypoint_runs_context_mode(tmp_path):
    ctx = {"tool": "copilot", "pr": _PR, "threads": []}
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps(ctx), encoding="utf-8")
    out = tmp_path / "payload.json"

    rc = review_ingest.main(["--output", str(out), "--context", str(ctx_path)])

    assert rc == review_ingest.EXIT_PRODUCED
    assert out.exists()


def test_cli_exposes_ingest_review_subcommand():
    from pr_repair.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["ingest-review", "--output", "p.json", "--context", "c.json"])
    assert args.command == "ingest-review"
    assert args.output == "p.json"
    assert args.context == "c.json"


def test_output_json_is_deterministic(tmp_path):
    ctx = {"tool": "copilot", "pr": _PR, "threads": [_thread("plain comment")]}
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps(ctx), encoding="utf-8")
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"

    review_ingest.run(output=str(first), context=str(ctx_path), generated_at=FIXED_TS)
    review_ingest.run(output=str(second), context=str(ctx_path), generated_at=FIXED_TS)

    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
