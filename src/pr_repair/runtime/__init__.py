from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pr_repair.state_store import StateStore
from pr_repair.types import ExecutionMode, RuntimeState


class RuntimeManager:
    """
    Coordinates run-scoped state for deterministic pipeline execution.
    """

    def __init__(self, artifact_dir: Path) -> None:
        self._artifact_dir = artifact_dir
        self._store = StateStore(artifact_dir)

    def create_run(self, repo: str, mode: ExecutionMode, current_phase: str) -> RuntimeState:
        run_state = RuntimeState(
            run_id=str(uuid4()),
            mode=mode,
            repo=repo,
            current_phase=current_phase,
            artifact_dir=self._artifact_dir,
        )
        self._store.write_runtime_state(run_state)
        return run_state

    def update_phase(self, run_state: RuntimeState, new_phase: str) -> RuntimeState:
        completed = list(run_state.completed_phases)
        if run_state.current_phase not in completed:
            completed.append(run_state.current_phase)
        updated = run_state.model_copy(
            update={
                "current_phase": new_phase,
                "completed_phases": completed,
            }
        )
        self._store.write_runtime_state(updated)
        return updated

    def complete(self, run_state: RuntimeState) -> RuntimeState:
        completed = list(run_state.completed_phases)
        if run_state.current_phase not in completed:
            completed.append(run_state.current_phase)
        updated = run_state.model_copy(update={"completed_phases": completed, "status": "completed"})
        self._store.write_runtime_state(updated)
        return updated

    def fail(self, run_state: RuntimeState) -> RuntimeState:
        completed = list(run_state.completed_phases)
        updated = run_state.model_copy(update={"completed_phases": completed, "status": "failed"})
        self._store.write_runtime_state(updated)
        return updated
