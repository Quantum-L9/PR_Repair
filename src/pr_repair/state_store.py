# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [runtime]
# tags: [artifacts, persistence, audit]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from pr_repair.errors import StateStoreError
from pr_repair.types import RuntimeState


class StateStore:
    """
    Runtime artifact persistence for pipeline state and structured outputs.
    """

    def __init__(self, artifact_dir: Path) -> None:
        self._artifact_dir = artifact_dir
        self._artifact_dir.mkdir(parents=True, exist_ok=True)

    @property
    def artifact_dir(self) -> Path:
        return self._artifact_dir

    def ensure_subdir(self, relative_path: str) -> Path:
        path = self._artifact_dir / relative_path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_runtime_state(self, runtime_state: RuntimeState) -> Path:
        return self.write_json("runtime_state.json", runtime_state.model_dump(mode="json"))

    def write_json(self, name: str, payload: Any) -> Path:
        path = self._artifact_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            msg = f"failed to write JSON artifact {path}"
            raise StateStoreError(msg) from exc
        return path

    def write_yaml(self, name: str, payload: Any) -> Path:
        path = self._artifact_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        except OSError as exc:
            msg = f"failed to write YAML artifact {path}"
            raise StateStoreError(msg) from exc
        return path

    def write_markdown(self, name: str, content: str) -> Path:
        path = self._artifact_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            msg = f"failed to write Markdown artifact {path}"
            raise StateStoreError(msg) from exc
        return path
