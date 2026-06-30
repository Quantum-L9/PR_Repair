# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [llm]
# tags: [llm-router, bridge, contract]
# owner: platform
# status: active
# --- /L9_META ---

"""Cross-language bridge contract between the Python Implementer Bot and the
TypeScript ``@quantum-l9/llm-router`` (the shared L9 routing layer).

The Implementer Bot declares a *task* (type + complexity) and prompts; the
router owns model selection and budget. The Implementer never picks a model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """One repair request handed to the router shim."""

    finding_id: str
    task_type: str = "code_generation"
    complexity: str = "medium"
    system_prompt: str
    user_prompt: str
    client_id: str = "implementer-bot"
    expected_output_tokens: int | None = None


class LLMResult(BaseModel):
    """The router's response for a single request (mirrors LLMResponse)."""

    finding_id: str
    content: str = ""
    model: str = ""
    provider: str = ""
    total_tokens: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    abstained: bool = False
    error: str | None = None


class ProposedPatch(BaseModel):
    """A bounded, structured repair proposal derived from an LLM result.

    Proposals are surfaced for human review; the bot proposes, it does not
    auto-merge architectural changes.
    """

    finding_id: str
    file_path: str | None = None
    instruction: dict[str, object] | None = None
    rationale: str = ""
    model: str = ""
    cost: float = 0.0
    abstained: bool = True
    diagnostics: list[str] = Field(default_factory=list)
