from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PRRepairError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class ConfigError(PRRepairError):
    pass


@dataclass(slots=True)
class RepoContextError(PRRepairError):
    pass


@dataclass(slots=True)
class StateStoreError(PRRepairError):
    pass


@dataclass(slots=True)
class ExecutionFlowError(PRRepairError):
    pass


@dataclass(slots=True)
class PayloadIngestionError(PRRepairError):
    """Raised when the agent review payload is missing, unreadable, or invalid.

    The pipeline treats this as a fail-closed signal: no repairs are attempted
    when the canonical payload contract cannot be satisfied.
    """

    pass
