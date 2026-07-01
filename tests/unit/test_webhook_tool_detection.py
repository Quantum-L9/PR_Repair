import hashlib
import hmac
import json

from pr_repair.server.github_webhook import detect_tool, parse_github_webhook

_SECRET = "secret"


def _event(event_name: str, payload: dict) -> object:
    body = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return parse_github_webhook(
        raw_body=body,
        headers={"X-GitHub-Event": event_name, "X-Hub-Signature-256": sig},
        secret=_SECRET,
    )


def test_detects_copilot_from_review_author() -> None:
    payload = {
        "action": "submitted",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 7, "head": {"sha": "abc"}},
        "review": {"user": {"login": "copilot-pull-request-reviewer[bot]"}},
    }
    event = _event("pull_request_review", payload)
    assert event.trigger == "review_completed"
    assert event.tool == "copilot"


def test_detects_coderabbit_from_review_author() -> None:
    payload = {
        "action": "submitted",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 7, "head": {"sha": "abc"}},
        "review": {"user": {"login": "coderabbitai[bot]"}},
    }
    assert _event("pull_request_review", payload).tool == "coderabbit"


def test_detects_sonar_from_check_run_name() -> None:
    payload = {
        "action": "completed",
        "repository": {"full_name": "owner/repo"},
        "check_run": {
            "name": "SonarCloud Code Analysis",
            "app": {"slug": "sonarcloud"},
            "pull_requests": [{"number": 7, "head": {"sha": "abc"}}],
        },
    }
    event = _event("check_run", payload)
    assert event.trigger == "ci_completed"
    assert event.tool == "sonarcloud"


def test_detects_gitguardian_from_app_slug() -> None:
    payload = {
        "action": "completed",
        "repository": {"full_name": "owner/repo"},
        "check_run": {
            "name": "GitGuardian Security Checks",
            "app": {"slug": "gitguardian"},
            "pull_requests": [{"number": 7, "head": {"sha": "abc"}}],
        },
    }
    assert _event("check_run", payload).tool == "gitguardian"


def test_generic_review_has_no_tool() -> None:
    payload = {
        "action": "submitted",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 7, "head": {"sha": "abc"}},
        "review": {"user": {"login": "a-human-reviewer"}},
    }
    assert _event("pull_request_review", payload).tool is None


def test_detect_tool_is_pure_and_handles_missing_nodes() -> None:
    # No review/check nodes at all -> None, no exception.
    assert detect_tool("pull_request", {"pull_request": {"number": 1}}) is None
