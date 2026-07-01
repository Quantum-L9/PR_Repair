# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [tools]
# tags: [gitguardian, secrets, adapter, review-actuation]
# owner: platform
# status: active
# --- /L9_META ---

"""GitGuardian secret-scan adapter.

GitGuardian reports leaked secrets (author slug contains ``gitguardian`` /
``ggshield``). Secrets are **never auto-fixed** — a leaked credential must be
rotated by a human — so every finding is high-severity, manual-review, and the
responder replies with a rotation justification rather than resolving the thread.
"""

from __future__ import annotations

from typing import Any

from pr_repair.server.github_webhook import NormalizedPREvent
from pr_repair.tools.base import RawThread, first_comment, thread_author_logins
from pr_repair.types import PRRef

_GG_LOGIN_MARKERS = ("gitguardian", "ggshield")


class GitGuardianAdapter:
    tool_name = "gitguardian"

    def matches(self, event: NormalizedPREvent) -> bool:
        return event.tool == self.tool_name

    def read_findings(self, pr_ref: PRRef, connector: Any) -> list[RawThread]:
        threads = connector.get_review_threads(
            pr_ref.repo_owner, pr_ref.repo_name, pr_ref.pr_number
        )
        return [
            t
            for t in threads
            if isinstance(t, dict) and not t.get("isResolved", False) and self._is_gitguardian(t)
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
            item: dict[str, Any] = {
                "finding_id": f"gitguardian-{comment.get('databaseId', thread.get('id'))}",
                "category": "security_issue",
                "severity": "critical",  # a leaked secret is always top-severity
                "message": body,
                "tool": self.tool_name,
                "tags": ["gitguardian", "secret"],
                "thread_id": thread.get("id"),
                "comment_id": comment.get("databaseId"),
                "evidence_url": comment.get("url"),
                "_disposition": "manual_review",  # secrets are rotated by humans, never patched
            }
            if path is not None:
                item["file_path"] = path
            if isinstance(line, int):
                item["line_start"] = line
                item["line_end"] = line
            findings.append(item)
        return findings

    def _is_gitguardian(self, thread: RawThread) -> bool:
        return any(
            marker in login
            for login in thread_author_logins(thread)
            for marker in _GG_LOGIN_MARKERS
        )
