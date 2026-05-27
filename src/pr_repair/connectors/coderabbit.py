# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [connectors]
# tags: [coderabbit, api, findings]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from typing import Any

import requests


class CodeRabbitConnector:
    """
    CodeRabbit transport adapter.

    Behavior:
    - if API key or base URL is absent, returns an empty list
    - missing routes or 404s degrade cleanly to []
    - non-404 API errors surface immediately
    """

    def __init__(self, api_key: str | None, base_url: str | None) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else None
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "pr-repair/0.4.0",
            }
        )
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

    def get_pr_findings(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
        if not self._api_key or not self._base_url:
            return []

        response = self._session.get(
            f"{self._base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/findings",
            timeout=30,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()

        payload = response.json()
        if isinstance(payload, dict):
            findings = payload.get("findings", [])
            return [item for item in findings if isinstance(item, dict)]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        raise ValueError("unexpected CodeRabbit response payload")
