from __future__ import annotations

from pathlib import Path

from pr_repair.errors import RepoContextError
from pr_repair.repo_context.path_policy import derive_path_policy
from pr_repair.types import RepoContext, TierLevel


def load_repo_context(repo_root: Path, write_ceiling: TierLevel = TierLevel.t1) -> RepoContext:
    """
    Load repo-aware governance context from known docs when present.
    """
    agent_md_path = repo_root / "AGENT.md"
    repo_map_path = repo_root / "REPO_MAP.md"

    if not agent_md_path.exists():
        msg = f"missing required governance document: {agent_md_path}"
        raise RepoContextError(msg)

    policy = derive_path_policy(repo_root)
    source_documents = [str(path) for path in [agent_md_path, repo_map_path] if path.exists()]

    return RepoContext(
        protected_paths=policy["protected_paths"],
        skip_review_paths=policy["skip_review_paths"],
        write_ceiling=write_ceiling,
        required_verification_command=["make", "agent-check"],
        source_documents=source_documents,
        repo_map_path=repo_map_path if repo_map_path.exists() else None,
        agent_md_path=agent_md_path,
    )
