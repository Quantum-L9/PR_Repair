# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [tools]
# tags: [sonar, sonarcloud, adapter, review-actuation]
# owner: platform
# status: active
# --- /L9_META ---

"""SonarQube/SonarCloud review adapter.

Sonar surfaces new-code issues as inline review comments (author slug contains
``sonar``), each carrying a rule key such as ``python:S1192``. Sonar does not
emit ``suggestion`` blocks, so its findings are always routed to the manual/LLM
lane — never auto-applied.
"""

from __future__ import annotations

import re
from typing import Any

from pr_repair.server.github_webhook import NormalizedPREvent
from pr_repair.tools.base import RawThread, first_comment, thread_author_logins
from pr_repair.types import PRRef

_SONAR_LOGIN_MARKERS = ("sonar",)
# Sonar rule keys: "python:S1192", "javascript:S1234", "secrets:S6290", ...
_RULE_RE = re.compile(r"\b([a-z]+:S\d{3,5})\b", re.IGNORECASE)


class SonarAdapter:
    tool_name = "sonarcloud"

    def matches(self, event: NormalizedPREvent) -> bool:
        return event.tool == self.tool_name

    def read_findings(self, pr_ref: PRRef, connector: Any) -> list[RawThread]:
        threads = connector.get_review_threads(
            pr_ref.repo_owner, pr_ref.repo_name, pr_ref.pr_number
        )
        return [
            t
            for t in threads
            if isinstance(t, dict) and not t.get("isResolved", False) and self._is_sonar(t)
        ]

    def to_payload_findings(self, raw: list[RawThread]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for thread in raw:
            comment = first_comment(thread)
            body = str(comment.get("body", "")).strip()
            if not body:
                continue
            path = thread.get("path")
            line = thread.get("line")
            rule_id = _extract_rule(body)
            item: dict[str, Any] = {
                "finding_id": f"sonar-{comment.get('databaseId', thread.get('id'))}",
                "category": _category_for_rule(rule_id, body),
                "severity": "medium",
                "message": body,
                "tool": self.tool_name,
                "tags": ["sonar"],
                "rule_id": rule_id,
                "thread_id": thread.get("id"),
                "comment_id": comment.get("databaseId"),
                "evidence_url": comment.get("url"),
                "_disposition": "manual_review",  # Sonar never emits an exact fix
            }
            if path is not None:
                item["file_path"] = path
            if isinstance(line, int):
                item["line_start"] = line
                item["line_end"] = line
            findings.append(item)
        return findings

    def _is_sonar(self, thread: RawThread) -> bool:
        return any(
            marker in login
            for login in thread_author_logins(thread)
            for marker in _SONAR_LOGIN_MARKERS
        )


def _extract_rule(body: str) -> str | None:
    match = _RULE_RE.search(body)
    return match.group(1) if match else None


def _category_for_rule(rule_id: str | None, body: str) -> str:
    key = (rule_id or "").lower()
    text = body.lower()
    if key.startswith("secrets:") or "vulnerability" in text or "security" in text:
        return "security_issue"
    if "bug" in text:
        return "bug_risk"
    return "lint_failure"
