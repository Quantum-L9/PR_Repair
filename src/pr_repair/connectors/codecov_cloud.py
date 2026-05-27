# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [connectors]
# tags: [codecov, coverage, api]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from typing import Any

import requests


class CodecovCloudConnector:
    """
    Codecov Cloud transport adapter.

    Behavior:
    - if API key is absent, returns an empty list
    - missing routes or 404s degrade cleanly to []
    - adapter emits normalized raw finding dicts for ingestion
    """

    def __init__(self, api_key: str | None, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
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
        if not self._api_key:
            return []

        response = self._session.get(
            f"{self._base_url}/api/v2/github/{repo_owner}/repos/{repo_name}/pulls/{pr_number}",
            timeout=30,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("unexpected Codecov response payload")

        findings: list[dict[str, Any]] = []
        coverage = payload.get("coverage")
        url = payload.get("url")
        if coverage is not None:
            findings.append(
                {
                    "id": f"codecov-coverage-{pr_number}",
                    "severity": "medium",
                    "category": "codecov_patch_coverage_failure",
                    "message": f"Codecov reported coverage state: {coverage}",
                    "file_path": None,
                    "line_start": None,
                    "line_end": None,
                    "suggested_fix": "Add or strengthen tests covering changed code paths.",
                    "evidence_url": url if isinstance(url, str) else None,
                }
            )

        comparisons = payload.get("comparison")
        if isinstance(comparisons, dict):
            patch_coverage = comparisons.get("patch")
            if patch_coverage is not None:
                findings.append(
                    {
                        "id": f"codecov-patch-{pr_number}",
                        "severity": "medium",
                        "category": "codecov_missing_tests_for_changed_code",
                        "message": f"Codecov patch coverage state: {patch_coverage}",
                        "file_path": None,
                        "line_start": None,
                        "line_end": None,
                        "suggested_fix": "Increase patch coverage for changed files.",
                        "evidence_url": url if isinstance(url, str) else None,
                    }
                )
        return findings
