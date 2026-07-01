# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [tools]
# tags: [responder, reply, resolve, governance]
# owner: platform
# status: active
# --- /L9_META ---

"""Per-thread responder.

For each finding routed from a tool thread, post a canonical reply — "Fixed in
<sha>" (with a report reference), a proposal note, or a justification for not
acting — then resolve the thread. All writes go through GitHubConnector; the
responder owns no HTTP. Gated by ``config.post_comment``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pr_repair.logging import log_event
from pr_repair.types import Finding, PRRef

Outcome = Literal["fixed", "proposed", "justified_skip"]


@dataclass(frozen=True)
class ResponderResult:
    finding_id: str
    replied: bool
    resolved: bool
    body: str


class ToolThreadResponder:
    """Replies to and resolves review threads via the connector only."""

    def __init__(self, connector: Any, *, post_comment: bool) -> None:
        self._connector = connector
        self._post_comment = post_comment

    def respond(
        self,
        pr_ref: PRRef,
        finding: Finding,
        outcome: Outcome,
        *,
        commit_sha: str | None = None,
        detail: str = "",
    ) -> ResponderResult:
        body = self._build_body(outcome, commit_sha=commit_sha, detail=detail)
        replied = False
        resolved = False

        # Resolving a fixed thread is only honest once the fix has landed. A
        # justified skip replies but leaves the thread open for a human.
        if self._post_comment:
            if finding.comment_id is not None:
                self._connector.reply_to_review_comment(
                    pr_ref.repo_owner, pr_ref.repo_name, pr_ref.pr_number, finding.comment_id, body
                )
                replied = True
            if finding.thread_id is not None and outcome == "fixed":
                self._connector.resolve_review_thread(finding.thread_id)
                resolved = True

        log_event(
            "tool_thread_response",
            finding_id=finding.finding_id,
            tool=finding.tool,
            outcome=outcome,
            replied=replied,
            resolved=resolved,
        )
        return ResponderResult(finding.finding_id, replied, resolved, body)

    def _build_body(self, outcome: Outcome, *, commit_sha: str | None, detail: str) -> str:
        if outcome == "fixed":
            where = f" in `{commit_sha}`" if commit_sha else ""
            base = f"**Fixed**{where} by the L9 Implementer Bot."
        elif outcome == "proposed":
            base = "**Proposal** prepared for review by the L9 Implementer Bot."
        else:
            base = "**Acknowledged — not auto-applied** by the L9 Implementer Bot."
        if detail:
            base = f"{base}\n\n{detail}"
        return f"{base}\n\n---\n_Automated via the per-tool review actuation layer._"
