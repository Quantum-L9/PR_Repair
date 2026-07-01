# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [tools]
# tags: [registry, adapter, dispatch]
# owner: platform
# status: active
# --- /L9_META ---

"""Adapter registry: map a webhook event's originating tool to its adapter."""

from __future__ import annotations

from pr_repair.server.github_webhook import NormalizedPREvent
from pr_repair.tools.base import ToolAdapter
from pr_repair.tools.copilot import CopilotAdapter

# Concrete adapters, keyed by their canonical tool name. Phase 4 adds
# coderabbit / sonarcloud / gitguardian here.
_ADAPTERS: dict[str, ToolAdapter] = {
    CopilotAdapter.tool_name: CopilotAdapter(),
}


def adapter_for_tool(tool: str | None) -> ToolAdapter | None:
    if tool is None:
        return None
    return _ADAPTERS.get(tool)


def adapter_for_event(event: NormalizedPREvent) -> ToolAdapter | None:
    adapter = adapter_for_tool(event.tool)
    if adapter is not None and adapter.matches(event):
        return adapter
    return None
