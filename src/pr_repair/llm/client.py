# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [llm]
# tags: [llm-router, bridge, subprocess]
# owner: platform
# status: active
# --- /L9_META ---

"""LLM client seam.

``LLMClient`` is the only surface the rest of the bot depends on. Two
implementations:

- ``NullLLMClient`` -- the offline default. Abstains on every request so the
  whole pipeline (and the test suite) runs deterministically with no keys.
- ``RouterClient`` -- delegates to the TypeScript ``@quantum-l9/llm-router`` via
  a stateless Node subprocess shim. The transport is injectable so the bridge is
  unit-testable without Node.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from pr_repair.errors import PRRepairError
from pr_repair.llm.contract import LLMRequest, LLMResult
from pr_repair.logging import log_event

# A transport maps a batch of serialized requests to a batch of serialized results.
Transport = Callable[[list[dict[str, object]]], list[dict[str, object]]]


class LLMUnavailableError(PRRepairError):
    """Raised when the router bridge cannot be reached or returns garbage."""


@runtime_checkable
class LLMClient(Protocol):
    def generate(self, requests: list[LLMRequest]) -> list[LLMResult]: ...


class NullLLMClient:
    """Default client: abstains on everything. No network, no keys, no cost."""

    def generate(self, requests: list[LLMRequest]) -> list[LLMResult]:
        return [
            LLMResult(finding_id=request.finding_id, abstained=True)
            for request in requests
        ]


class RouterClient:
    """Bridge to the shared L9 LLM-Router via a Node subprocess shim."""

    def __init__(
        self,
        *,
        shim_path: Path,
        node_bin: str = "node",
        transport: Transport | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self._shim_path = shim_path
        self._node_bin = node_bin
        self._timeout = timeout_seconds
        self._transport = transport or self._subprocess_transport

    def generate(self, requests: list[LLMRequest]) -> list[LLMResult]:
        if not requests:
            return []
        payload = [request.model_dump() for request in requests]
        raw = self._transport(payload)
        results = [LLMResult.model_validate(item) for item in raw]
        log_event(
            "llm_router_batch_complete",
            requested=len(requests),
            returned=len(results),
            total_cost=round(sum(r.cost for r in results), 6),
        )
        return results

    def _subprocess_transport(
        self, payload: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        if not self._shim_path.exists():
            msg = f"router shim not found at {self._shim_path}"
            raise LLMUnavailableError(msg)
        try:
            completed = subprocess.run(
                [self._node_bin, str(self._shim_path)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            msg = f"node binary not found: {self._node_bin}"
            raise LLMUnavailableError(msg) from exc
        except subprocess.TimeoutExpired as exc:
            msg = f"router shim timed out after {self._timeout}s"
            raise LLMUnavailableError(msg) from exc
        if completed.returncode != 0:
            msg = f"router shim failed (exit {completed.returncode}): {completed.stderr.strip()}"
            raise LLMUnavailableError(msg)
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            msg = "router shim returned invalid JSON"
            raise LLMUnavailableError(msg) from exc
        if not isinstance(parsed, list):
            msg = "router shim must return a JSON array"
            raise LLMUnavailableError(msg)
        return parsed
