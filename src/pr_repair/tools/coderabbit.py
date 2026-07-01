# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [tools]
# tags: [coderabbit, adapter, review-actuation]
# owner: platform
# status: active
# --- /L9_META ---

"""CodeRabbit review adapter.

CodeRabbit posts inline PR review comments (author ``coderabbitai[bot]``), often
with a ```suggestion block. A suggestion with a concrete location becomes a
deterministic autofix; everything else is a manual/LLM proposal.
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

_CODERABBIT_LOGIN_MARKERS = ("coderabbit",)


class CodeRabbitAdapter:
    tool_name = "coderabbit"

    def matches(self, event: NormalizedPREvent) -> bool:
        return event.tool == self.tool_name

    def read_findings(self, pr_ref: PRRef, connector: Any) -> list[RawThread]:
        threads = connector.get_review_threads(
            pr_ref.repo_owner, pr_ref.repo_name, pr_ref.pr_number
        )
        return [
            t
            for t in threads
            if isinstance(t, dict) and not t.get("isResolved", False) and self._is_coderabbit(t)
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
                "finding_id": f"coderabbit-{comment.get('databaseId', thread.get('id'))}",
                "category": _infer_category(body),
                "severity": "medium",
                "message": body,
                "tool": self.tool_name,
                "tags": ["coderabbit"],
                "thread_id": thread.get("id"),
                "comment_id": comment.get("databaseId"),
                "evidence_url": comment.get("url"),
            }
            if path is not None:
                item["file_path"] = path
            if isinstance(line, int):
                item["line_start"] = line
                item["line_end"] = line
            if suggestion is not None and path is not None and isinstance(line, int):
                item["replacement_text"] = suggestion
                item["_disposition"] = "autofix"
            else:
                item["_disposition"] = "manual_review"
            findings.append(item)
        return findings

    def _is_coderabbit(self, thread: RawThread) -> bool:
        return any(
            marker in login
            for login in thread_author_logins(thread)
            for marker in _CODERABBIT_LOGIN_MARKERS
        )


def _infer_category(body: str) -> str:
    text = body.lower()
    if "security" in text or "injection" in text or "credential" in text:
        return "security_issue"
    if "type" in text or "mypy" in text:
        return "typing_failure"
    if "lint" in text or "unused" in text or "format" in text or "style" in text:
        return "lint_failure"
    if "architecture" in text or "boundary" in text:
        return "architecture_boundary_violation"
    return "review_comment"
