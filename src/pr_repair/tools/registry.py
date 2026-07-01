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

from collections.abc import Set as AbstractSet

from pr_repair.server.github_webhook import NormalizedPREvent
from pr_repair.tools.base import ToolAdapter
from pr_repair.tools.coderabbit import CodeRabbitAdapter
from pr_repair.tools.copilot import CopilotAdapter
from pr_repair.tools.gitguardian import GitGuardianAdapter
from pr_repair.tools.sonar import SonarAdapter

# Concrete adapters, keyed by their canonical tool name.
_ADAPTERS: dict[str, ToolAdapter] = {
    CopilotAdapter.tool_name: CopilotAdapter(),
    CodeRabbitAdapter.tool_name: CodeRabbitAdapter(),
    SonarAdapter.tool_name: SonarAdapter(),
    GitGuardianAdapter.tool_name: GitGuardianAdapter(),
}


def adapter_for_tool(
    tool: str | None, enabled: AbstractSet[str] | None = None
) -> ToolAdapter | None:
    if tool is None:
        return None
    if enabled is not None and tool not in enabled:
        return None
    return _ADAPTERS.get(tool)


def adapter_for_event(
    event: NormalizedPREvent, enabled: AbstractSet[str] | None = None
) -> ToolAdapter | None:
    adapter = adapter_for_tool(event.tool, enabled)
    if adapter is not None and adapter.matches(event):
        return adapter
    return None
