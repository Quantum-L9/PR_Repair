# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [llm]
# tags: [llm-router, task-classification, prompt]
# owner: platform
# status: active
# --- /L9_META ---

"""Map a manual-review finding onto a bounded LLM-Router task + prompts.

The Implementer Bot declares task *type* and *complexity* only; the router picks
the model. Prompts are deliberately bounded: the model fixes complex logic, never
mechanical imports/formatting (those are deterministic autofixes), and never
touches protected paths or security boundaries.
"""

from __future__ import annotations

import json
from pathlib import Path

from pr_repair.llm.contract import LLMRequest
from pr_repair.types import Finding, Severity

_SEVERITY_TO_COMPLEXITY = {
    Severity.critical: "critical",
    Severity.high: "high",
    Severity.medium: "medium",
    Severity.low: "low",
}

_CONTEXT_RADIUS = 12

SYSTEM_PROMPT = (
    "You are the code-repair function of the L9 Implementer Bot. You fix a single "
    "complex architectural finding in one file.\n"
    "Hard rules:\n"
    "- Do NOT fix mechanical imports, formatting, or lint issues; those are handled "
    "deterministically elsewhere.\n"
    "- NEVER modify protected paths or security/auth boundaries.\n"
    "- Make the minimal change that resolves the finding.\n"
    "Return ONLY a single JSON object, no prose, in one of these two shapes:\n"
    '  {"op":"replace_range","line_start":<int>,"line_end":<int>,'
    '"replacement":"<new code>","rationale":"<why>"}\n'
    '  {"abstain":true,"rationale":"<why you cannot safely fix this>"}'
)


def finding_complexity(finding: Finding) -> str:
    return _SEVERITY_TO_COMPLEXITY.get(finding.severity, "medium")


def build_request(
    finding: Finding,
    repo_root: Path,
    client_id: str,
    feedback: str | None = None,
) -> LLMRequest:
    """Build a bounded code-repair request for a single manual-review finding.

    ``feedback`` carries the verification stderr from a failed prior attempt so the
    model can correct itself on the single allowed retry.
    """
    return LLMRequest(
        finding_id=finding.finding_id,
        task_type="code_generation",
        complexity=finding_complexity(finding),
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(finding, repo_root, feedback),
        client_id=client_id,
        expected_output_tokens=512,
    )


def _build_user_prompt(finding: Finding, repo_root: Path, feedback: str | None = None) -> str:
    payload: dict[str, object] = {
        "finding_id": finding.finding_id,
        "category": finding.category,
        "severity": finding.severity.value,
        "message": finding.message,
        "file_path": finding.file_path,
        "line_start": finding.line_start,
        "line_end": finding.line_end,
        "contract_ids": finding.contract_ids,
    }
    context = _file_context(finding, repo_root)
    if context is not None:
        payload["file_context"] = context
    if feedback:
        payload["prior_attempt_verification_failure"] = feedback[-4000:]
    return json.dumps(payload, indent=2, sort_keys=True)


def _file_context(finding: Finding, repo_root: Path) -> dict[str, object] | None:
    if not finding.file_path or finding.line_start is None:
        return None
    path = repo_root / finding.file_path
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(1, finding.line_start - _CONTEXT_RADIUS)
    end = min(len(lines), (finding.line_end or finding.line_start) + _CONTEXT_RADIUS)
    numbered = [f"{n}: {lines[n - 1]}" for n in range(start, end + 1)]
    return {"first_line": start, "last_line": end, "lines": numbered}
