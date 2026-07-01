from __future__ import annotations

from pr_repair.config import AppConfig
from pr_repair.connectors.github import GitHubConnector
from pr_repair.logging import log_event
from pr_repair.types import PRRef


_PRIORITY_LABEL_WEIGHTS = {
    "requested-changes": 60,
    "bug": 40,
    "high-priority": 35,
    "security": 50,
    "ci-failing": 30,
    "needs-fix": 25,
}


def collect_candidate_prs(
    config: AppConfig,
    github_connector: GitHubConnector | None = None,
) -> list[PRRef]:
    """
    Discover and deterministically prioritize candidate PRs for repair.

    Rules:
    - open PRs only
    - drafts excluded unless config explicitly opts in
    - highest score first, PR number ascending as stable tiebreaker
    - changed_files are attached when the connector exposes that capability
    """
    connector = github_connector or GitHubConnector(config.github_token)
    include_drafts = bool(getattr(config, "include_drafts", False))

    prs = connector.list_open_prs(
        repo_owner=config.repo_owner,
        repo_name=config.repo_name,
        include_drafts=include_drafts,
    )

    filtered_prs = [pr for pr in prs if include_drafts or not pr.is_draft]

    enriched: list[PRRef] = []
    for pr in filtered_prs:
        changed_files = _load_changed_files_if_supported(connector, pr)
        enriched.append(pr.model_copy(update={"changed_files": changed_files}))

    prioritized = sorted(
        enriched,
        key=lambda item: (-_score_pr(item), item.pr_number),
    )
    limited = prioritized[: config.max_prs]

    log_event(
        "candidate_prs_collected",
        repo=config.github_repository,
        include_drafts=include_drafts,
        total=len(prioritized),
        selected=[pr.pr_number for pr in limited],
    )
    return limited


def _load_changed_files_if_supported(
    github_connector: GitHubConnector,
    pr: PRRef,
) -> list[str]:
    if not hasattr(github_connector, "get_pr_changed_files"):
        return []

    raw_files = github_connector.get_pr_changed_files(
        pr.repo_owner,
        pr.repo_name,
        pr.pr_number,
    )
    changed_files: list[str] = []
    for raw_file in raw_files:
        filename = raw_file.get("filename")
        if isinstance(filename, str) and filename:
            changed_files.append(filename)
    return changed_files


def _score_pr(pr: PRRef) -> int:
    score = 0
    for label in pr.labels:
        score += _PRIORITY_LABEL_WEIGHTS.get(label.lower(), 0)
    if not pr.is_draft:
        score += 10
    if pr.changed_files:
        score += min(len(pr.changed_files), 20)
    return score
