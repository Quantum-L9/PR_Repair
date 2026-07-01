# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [tools]
# tags: [copilot, adapter, review-actuation]
# owner: platform
# status: active
# --- /L9_META ---

"""Copilot review adapter.

Reads GitHub Copilot's PR review threads and normalizes them into canonical
findings. A Copilot comment carrying a ```suggestion block becomes a
deterministic autofix (exact replacement, exact line range); everything else is
routed to the manual/LLM lane as a proposal.
"""

from __future__ import annotations

from typing import Any

from pr_repair.server.github_webhook import NormalizedPREvent
from pr_repair.tools.base import (
    RawThread,
    extract_suggestion,
    first_comment,
    thread_author_logins,
)
from pr_repair.types import PRRef

_COPILOT_LOGIN_MARKERS = ("copilot",)


class CopilotAdapter:
    tool_name = "copilot"

    def matches(self, event: NormalizedPREvent) -> bool:
        return event.tool == self.tool_name

    def read_findings(self, pr_ref: PRRef, connector: Any) -> list[RawThread]:
        threads = connector.get_review_threads(
            pr_ref.repo_owner, pr_ref.repo_name, pr_ref.pr_number
        )
        return [
            thread
            for thread in threads
            if isinstance(thread, dict)
            and not thread.get("isResolved", False)
            and self._is_copilot_thread(thread)
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
            suggestion = extract_suggestion(body)

            item: dict[str, Any] = {
                "finding_id": self._finding_id(thread, comment),
                "category": _infer_category(body),
                "severity": "medium",
                "message": body,
                "tool": self.tool_name,
                "tags": ["copilot"],
                "thread_id": thread.get("id"),
                "comment_id": comment.get("databaseId"),
                "evidence_url": comment.get("url"),
            }
            if path is not None:
                item["file_path"] = path
            if isinstance(line, int):
                item["line_start"] = line
                item["line_end"] = line

            # A suggestion block with a concrete location is a deterministic autofix.
            if suggestion is not None and path is not None and isinstance(line, int):
                item["replacement_text"] = suggestion
                item["_disposition"] = "autofix"
            else:
                item["_disposition"] = "manual_review"
            findings.append(item)
        return findings

    def _is_copilot_thread(self, thread: RawThread) -> bool:
        return any(
            marker in login
            for login in thread_author_logins(thread)
            for marker in _COPILOT_LOGIN_MARKERS
        )

    def _finding_id(self, thread: RawThread, comment: dict[str, Any]) -> str:
        database_id = comment.get("databaseId")
        if database_id is not None:
            return f"copilot-{database_id}"
        return f"copilot-{thread.get('id', 'unknown')}"


def _infer_category(body: str) -> str:
    text = body.lower()
    if "type" in text or "mypy" in text:
        return "typing_failure"
    if "lint" in text or "unused" in text or "format" in text:
        return "lint_failure"
    if "security" in text or "credential" in text or "injection" in text:
        return "security_issue"
    if "architecture" in text or "boundary" in text or "layer" in text:
        return "architecture_boundary_violation"
    return "review_comment"
