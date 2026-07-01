# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [planning]
# tags: [llm-router, manual-review, proposal]
# owner: platform
# status: active
# --- /L9_META ---

"""LLM-assisted proposals for manual-review findings.

The deterministic ``repair_planner`` stays untouched. This module handles the
complex lane: it asks the shared L9 LLM-Router (through the injected client) for a
bounded patch *proposal* per finding. Proposals are surfaced for human review --
the bot proposes, it does not auto-merge architectural changes. Protected-path
findings are never sent to the model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pr_repair.llm.client import LLMClient, LLMUnavailableError
from pr_repair.llm.contract import LLMResult, ProposedPatch
from pr_repair.llm.task_mapping import build_request
from pr_repair.logging import log_event
from pr_repair.types import Finding


def propose_repairs(
    manual_findings: list[Finding],
    llm_client: LLMClient,
    repo_root: Path,
    client_id: str,
    feedback: str | None = None,
    resolved_by_id: dict[str, Any] | None = None,
) -> list[ProposedPatch]:
    """Generate bounded patch proposals for manual-review findings.

    ``feedback`` (verification stderr from a failed attempt) is threaded into every
    request so the model can correct itself on the single allowed retry.
    ``resolved_by_id`` maps finding_id -> ResolvedLLMConfig (model_router tier/depth
    hints, ADR 0001); absent, the router routes on complexity alone.
    """
    eligible = [f for f in manual_findings if not f.protected_path]
    skipped = len(manual_findings) - len(eligible)
    if not eligible:
        if skipped:
            log_event("llm_proposals_skipped_protected", count=skipped)
        return []

    resolved_by_id = resolved_by_id or {}
    requests = [
        build_request(f, repo_root, client_id, feedback, resolved_by_id.get(f.finding_id))
        for f in eligible
    ]
    try:
        results = llm_client.generate(requests)
    except LLMUnavailableError as exc:
        log_event("llm_router_unavailable", error=str(exc))
        return [_unavailable_proposal(f, str(exc)) for f in eligible]

    results_by_id = {result.finding_id: result for result in results}
    proposals = [
        _to_proposal(finding, results_by_id.get(finding.finding_id))
        for finding in eligible
    ]
    log_event(
        "llm_proposals_complete",
        eligible=len(eligible),
        skipped_protected=skipped,
        actionable=sum(1 for p in proposals if not p.abstained),
    )
    return proposals


def _to_proposal(finding: Finding, result: LLMResult | None) -> ProposedPatch:
    if result is None:
        return ProposedPatch(
            finding_id=finding.finding_id,
            file_path=finding.file_path,
            abstained=True,
            diagnostics=["no router result returned for finding"],
        )
    if result.error:
        return ProposedPatch(
            finding_id=finding.finding_id,
            file_path=finding.file_path,
            model=result.model,
            cost=result.cost,
            abstained=True,
            diagnostics=[f"router error: {result.error}"],
        )
    if result.abstained:
        return ProposedPatch(
            finding_id=finding.finding_id,
            file_path=finding.file_path,
            model=result.model,
            cost=result.cost,
            abstained=True,
            diagnostics=["model abstained"],
        )
    return _parse_content(finding, result)


def _parse_content(finding: Finding, result: LLMResult) -> ProposedPatch:
    def abstain(diagnostic: str, rationale: str = "") -> ProposedPatch:
        return ProposedPatch(
            finding_id=finding.finding_id,
            file_path=finding.file_path,
            model=result.model,
            cost=result.cost,
            rationale=rationale,
            abstained=True,
            diagnostics=[diagnostic],
        )

    try:
        data = json.loads(result.content)
    except json.JSONDecodeError:
        return abstain("model returned non-JSON content")
    if not isinstance(data, dict):
        return abstain("model returned non-object content")
    if data.get("abstain") is True:
        return abstain("model abstained", rationale=str(data.get("rationale", "")))

    instruction = _build_instruction(finding, data)
    if instruction is None:
        return abstain("model patch did not match the required shape")
    return ProposedPatch(
        finding_id=finding.finding_id,
        file_path=finding.file_path,
        model=result.model,
        cost=result.cost,
        instruction=instruction,
        rationale=str(data.get("rationale", "")),
        abstained=False,
    )


def _build_instruction(finding: Finding, data: dict[str, object]) -> dict[str, object] | None:
    if data.get("op") != "replace_range":
        return None
    line_start = data.get("line_start")
    line_end = data.get("line_end")
    replacement = data.get("replacement")
    if not isinstance(line_start, int) or not isinstance(line_end, int):
        return None
    if line_start < 1 or line_end < line_start:
        return None
    if not isinstance(replacement, str):
        return None
    return {
        "op": "replace_range",
        "file_path": finding.file_path,
        "line_start": line_start,
        "line_end": line_end,
        "replacement": replacement,
        "finding_id": finding.finding_id,
        "category": finding.category,
        "source": "llm_router",
    }


def _unavailable_proposal(finding: Finding, error: str) -> ProposedPatch:
    return ProposedPatch(
        finding_id=finding.finding_id,
        file_path=finding.file_path,
        abstained=True,
        diagnostics=[f"router unavailable: {error}"],
    )
