# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [telemetry]
# tags: [trace, audit, events]
# owner: platform
# status: active
# --- /L9_META ---

"""Run trace recorder.

Captures the ordered structured-event stream the pipeline already emits via
``log_event`` into a deterministic, auditable timeline (``run_trace.json``). The
recorder registers itself as an event sink for the duration of a run, so every
decision -- ingestion, routing, patch application, verification, rollback,
proposal, comment upsert -- lands in the trace with no extra instrumentation.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

from pydantic import BaseModel, Field

from pr_repair.logging import add_event_sink, remove_event_sink


class TraceEvent(BaseModel):
    seq: int
    event: str
    fields: dict[str, Any] = Field(default_factory=dict)


class TraceRecorder:
    """Collects structured events in order. Usable as a context manager."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []
        self._seq = 0

    def record(self, event: str, fields: dict[str, Any]) -> None:
        self._seq += 1
        self._events.append(
            TraceEvent(seq=self._seq, event=event, fields=_json_safe(fields))
        )

    def events(self) -> list[TraceEvent]:
        return list(self._events)

    def to_list(self) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in self._events]

    def start(self) -> None:
        add_event_sink(self.record)

    def stop(self) -> None:
        remove_event_sink(self.record)

    def __enter__(self) -> "TraceRecorder":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()


def _json_safe(fields: dict[str, Any]) -> dict[str, Any]:
    """Coerce field values to JSON-serializable forms (best-effort, never raises)."""
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, (list, tuple)):
            safe[key] = [v if isinstance(v, (str, int, float, bool)) or v is None else str(v) for v in value]
        else:
            safe[key] = str(value)
    return safe
