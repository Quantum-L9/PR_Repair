# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [tools]
# tags: [per-tool, adapter, review-actuation]
# owner: platform
# status: active
# --- /L9_META ---

"""Per-tool adapter protocol and shared normalization helpers.

Each review tool (Copilot, CodeRabbit, SonarCloud, GitGuardian) gets a concrete
adapter that knows *only* its own native output shape and normalizes it into the
canonical ``agent_review_payload`` finding contract. Downstream, the existing
bifurcated pipeline (classify → route → repair/verify/rollback) handles every
tool uniformly.
"""

from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

from pr_repair.server.github_webhook import NormalizedPREvent
from pr_repair.types import PRRef

# A raw review thread as returned by GitHubConnector.get_review_threads (GraphQL):
# {id, isResolved, path, line, comments: {nodes: [{id, databaseId, body, author, url}]}}
RawThread = dict[str, Any]

# Matches a GitHub ```suggestion ... ``` block (an exact replacement the tool proposes).
_SUGGESTION_RE = re.compile(r"```suggestion\n(?P<body>.*?)```", re.DOTALL)


@runtime_checkable
class ToolAdapter(Protocol):
    """Contract every per-tool adapter implements."""

    tool_name: str

    def matches(self, event: NormalizedPREvent) -> bool:
        """True if this adapter owns the given webhook event."""
        ...

    def read_findings(self, pr_ref: PRRef, connector: Any) -> list[RawThread]:
        """Read this tool's native, unresolved findings for the PR."""
        ...

    def to_payload_findings(self, raw: list[RawThread]) -> list[dict[str, Any]]:
        """Normalize native findings into canonical agent_review_payload items."""
        ...


def thread_author_logins(thread: RawThread) -> list[str]:
    """All comment author logins on a thread (lowercased)."""
    logins: list[str] = []
    for comment in _comment_nodes(thread):
        author = comment.get("author")
        if isinstance(author, dict) and author.get("login"):
            logins.append(str(author["login"]).lower())
    return logins


def first_comment(thread: RawThread) -> dict[str, Any]:
    nodes = _comment_nodes(thread)
    return nodes[0] if nodes else {}


def extract_suggestion(body: str) -> str | None:
    """Return the exact replacement text from a ```suggestion block, if present."""
    match = _SUGGESTION_RE.search(body or "")
    if match is None:
        return None
    # Strip a single trailing newline the fence introduces; keep interior lines.
    return match.group("body").rstrip("\n")


def _comment_nodes(thread: RawThread) -> list[dict[str, Any]]:
    comments = thread.get("comments")
    if not isinstance(comments, dict):
        return []
    nodes = comments.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [node for node in nodes if isinstance(node, dict)]
