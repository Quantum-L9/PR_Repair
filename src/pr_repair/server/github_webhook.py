# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [server, orchestration]
# tags: [github, webhook, signature, events]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Literal


SUPPORTED_ACTIONS: dict[str, set[str]] = {
    "pull_request": {"opened", "synchronize"},
    "pull_request_review": {"submitted"},
    "check_suite": {"completed"},
    "check_run": {"completed"},
    "workflow_run": {"completed"},
}


@dataclass(frozen=True)
class NormalizedPREvent:
    event_name: str
    action: str
    trigger: Literal["pr_changed", "review_completed", "ci_completed", "ignored"]
    repo_full_name: str | None
    pr_number: int | None
    head_sha: str | None
    payload: dict[str, Any]

    @property
    def supported(self) -> bool:
        return self.trigger != "ignored" and self.repo_full_name is not None and self.pr_number is not None


class WebhookSignatureError(ValueError):
    pass


def verify_github_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    if not secret:
        raise WebhookSignatureError("webhook secret is required")
    if not signature_header or not signature_header.startswith("sha256="):
        raise WebhookSignatureError("missing or unsupported GitHub signature")
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise WebhookSignatureError("invalid GitHub webhook signature")
    return True


def parse_github_webhook(
    *,
    raw_body: bytes,
    headers: dict[str, str],
    secret: str,
) -> NormalizedPREvent:
    verify_github_signature(raw_body, _header(headers, "X-Hub-Signature-256"), secret)
    event_name = _header(headers, "X-GitHub-Event") or ""
    payload = json.loads(raw_body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub webhook payload must be a JSON object")
    action = str(payload.get("action", ""))
    if action not in SUPPORTED_ACTIONS.get(event_name, set()):
        return NormalizedPREvent(event_name, action, "ignored", None, None, None, payload)
    repo_full_name = _repo_full_name(payload)
    pr_number, head_sha = _pr_ref(event_name, payload)
    trigger: Literal["pr_changed", "review_completed", "ci_completed", "ignored"] = "ignored"
    if event_name == "pull_request":
        trigger = "pr_changed"
    elif event_name == "pull_request_review":
        trigger = "review_completed"
    elif event_name in {"check_suite", "check_run", "workflow_run"}:
        trigger = "ci_completed"
    return NormalizedPREvent(event_name, action, trigger, repo_full_name, pr_number, head_sha, payload)


def _header(headers: dict[str, str], name: str) -> str | None:
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


def _repo_full_name(payload: dict[str, Any]) -> str | None:
    repo = payload.get("repository")
    if isinstance(repo, dict) and isinstance(repo.get("full_name"), str):
        return repo["full_name"]
    return None


def _pr_ref(event_name: str, payload: dict[str, Any]) -> tuple[int | None, str | None]:
    if event_name in {"pull_request", "pull_request_review"}:
        pr = payload.get("pull_request")
        if not isinstance(pr, dict):
            return None, None
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        number = pr.get("number")
        return int(number) if isinstance(number, int) else None, str(head.get("sha")) if head.get("sha") else None
    prs = payload.get("pull_requests")
    if isinstance(prs, list) and prs and isinstance(prs[0], dict):
        pr = prs[0]
        number = pr.get("number")
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        return int(number) if isinstance(number, int) else None, str(head.get("sha")) if head.get("sha") else None
    workflow = payload.get("workflow_run")
    if isinstance(workflow, dict):
        prs = workflow.get("pull_requests")
        if isinstance(prs, list) and prs and isinstance(prs[0], dict):
            number = prs[0].get("number")
            head_sha = workflow.get("head_sha")
            return int(number) if isinstance(number, int) else None, str(head_sha) if head_sha else None
    return None, None
