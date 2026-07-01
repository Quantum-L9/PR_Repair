# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [llm]
# tags: [exports, llm-router]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.config import AppConfig
from pr_repair.llm.client import LLMClient, NullLLMClient, RouterClient
from pr_repair.llm.contract import LLMRequest, LLMResult, ProposedPatch

__all__ = [
    "LLMClient",
    "NullLLMClient",
    "RouterClient",
    "LLMRequest",
    "LLMResult",
    "ProposedPatch",
    "build_llm_client",
]


def build_llm_client(config: AppConfig) -> LLMClient:
    """Return the configured LLM client.

    Defaults to the offline :class:`NullLLMClient`; only constructs a live
    :class:`RouterClient` when ``llm_enabled`` is set. This keeps CI and tests
    deterministic and key-free unless explicitly opted in.
    """
    if not config.llm_enabled:
        return NullLLMClient()
    return RouterClient(shim_path=config.llm_shim_path, node_bin=config.llm_node_bin)
