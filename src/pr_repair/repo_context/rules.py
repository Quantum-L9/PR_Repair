from __future__ import annotations

from pathlib import Path

from pr_repair.types import RepoContext, TierLevel


def classify_path_tier(path: str, repo_context: RepoContext) -> TierLevel:
    """
    Classify a repo path into the highest-risk tier implied by governance.
    """
    path_obj = Path(path)

    protected_exact = {
        "app/engines/chassis_contract.py": TierLevel.t4,
        "app/engines/handlers.py": TierLevel.t4,
        "app/engines/graph_sync_client.py": TierLevel.t4,
        "GUARDRAILS.md": TierLevel.t4,
        "AGENTS.md": TierLevel.t4,
        "CLAUDE.md": TierLevel.t4,
    }

    if path in protected_exact:
        return protected_exact[path]

    if path_obj.parts[:2] == ("app", "models") or path.startswith("kb/"):
        return TierLevel.t5
    if path.startswith(".github/workflows/"):
        return TierLevel.t2
    if path.startswith("tests/") or path.startswith("tools/"):
        return TierLevel.t2
    if path.startswith("app/engines/") or path.startswith("app/score/") or path.startswith("app/health/") or path.startswith("app/services/"):
        return TierLevel.t3
    if path.startswith("app/api/") or path == "app/main.py":
        return TierLevel.t3
    if _matches_any(path, repo_context.protected_paths):
        return TierLevel.t4
    return TierLevel.t1


def is_protected_path(path: str, repo_context: RepoContext) -> bool:
    return _matches_any(path, repo_context.protected_paths)


def is_skip_review_path(path: str, repo_context: RepoContext) -> bool:
    return _matches_any(path, repo_context.skip_review_paths)


def _matches_any(path: str, patterns: list[str]) -> bool:
    path_obj = Path(path)
    for pattern in patterns:
        if path_obj.match(pattern):
            return True
    return False
