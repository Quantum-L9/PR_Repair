from __future__ import annotations

from pathlib import Path


def derive_path_policy(repo_root: Path) -> dict[str, list[str]]:
    """
    Return machine-readable protected and skip-review path policies.

    These defaults are refined from the uploaded repo governance files and
    intentionally favor safety over aggressive automation.
    """
    _ = repo_root  # repo_root reserved for future on-disk repo-specific overrides

    protected_paths = [
        "app/engines/chassis_contract.py",
        "app/engines/handlers.py",
        "app/engines/graph_sync_client.py",
        "app/models/**",
        "kb/**",
        ".github/workflows/**",
        "GUARDRAILS.md",
        "AGENTS.md",
        "CLAUDE.md",
        "Dockerfile",
        "docker-compose*.yml",
    ]
    skip_review_paths = [
        "docs/**",
        "readme/**",
        "reports/**",
        "*.json",
        "htmlcov/**",
        "coverage.xml",
    ]
    return {
        "protected_paths": protected_paths,
        "skip_review_paths": skip_review_paths,
    }
