# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [connectors]
# tags: [github, api, pull_requests]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from typing import Any

import requests

from pr_repair.types import PRRef


class GitHubConnector:
    """
    GitHub transport adapter for PR-centric operations.

    Design notes:
    - read operations are safe by default
    - write actions are limited to PR commentary and review-thread lifecycle:
      post_pr_comment, update_issue_comment, reply_to_review_comment, and
      resolve/unresolve_review_thread. No merge, no push, no branch mutation.
    - all requests are bounded and fail fast on non-2xx responses
    """

    def __init__(self, token: str, base_url: str = "https://api.github.com") -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "pr-repair/0.4.0",
            }
        )

    def list_open_prs(
        self,
        repo_owner: str,
        repo_name: str,
        include_drafts: bool = False,
    ) -> list[PRRef]:
        payload = self._get(
            f"/repos/{repo_owner}/{repo_name}/pulls",
            params={"state": "open", "per_page": 100},
        )
        items: list[PRRef] = []
        for raw in payload:
            is_draft = bool(raw.get("draft", False))
            if is_draft and not include_drafts:
                continue
            items.append(
                PRRef(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    pr_number=int(raw["number"]),
                    title=str(raw.get("title", "")),
                    head_branch=str(raw["head"]["ref"]),
                    base_branch=str(raw["base"]["ref"]),
                    head_sha=str(raw["head"]["sha"]),
                    is_draft=is_draft,
                    author=str(raw["user"]["login"]),
                    labels=[str(label["name"]) for label in raw.get("labels", [])],
                    changed_files=[],
                )
            )
        return items

    def get_pr_changed_files(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
        payload = self._get(
            f"/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/files",
            params={"per_page": 100},
        )
        return [item for item in payload if isinstance(item, dict)]

    def get_pr_check_runs(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
        pr_payload = self._get(f"/repos/{repo_owner}/{repo_name}/pulls/{pr_number}")
        head_sha = str(pr_payload["head"]["sha"])
        return self.get_check_runs(repo_owner, repo_name, head_sha)

    def get_check_runs(self, repo_owner: str, repo_name: str, head_sha: str) -> list[dict[str, Any]]:
        payload = self._get(f"/repos/{repo_owner}/{repo_name}/commits/{head_sha}/check-runs")
        runs = payload.get("check_runs", [])
        if not isinstance(runs, list):
            return []
        return [item for item in runs if isinstance(item, dict)]

    def get_review_comments(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
        payload = self._get(f"/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/comments")
        return [item for item in payload if isinstance(item, dict)]

    def get_review_threads(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
        query = """
        query($owner: String!, $repo: String!, $pr: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $pr) {
              reviewThreads(first: 100) {
                nodes {
                  id
                  isResolved
                  path
                  line
                  comments(first: 20) {
                    nodes {
                      id
                      body
                      author { login }
                      url
                    }
                  }
                }
              }
            }
          }
        }
        """
        payload = self._graphql(
            query=query,
            variables={"owner": repo_owner, "repo": repo_name, "pr": pr_number},
        )
        nodes = (
            payload.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("reviewThreads", {})
            .get("nodes", [])
        )
        if not isinstance(nodes, list):
            return []
        return [item for item in nodes if isinstance(item, dict)]

    def get_issue_comments(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
        payload = self._get(f"/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments")
        return [item for item in payload if isinstance(item, dict)]

    def post_pr_comment(self, repo_owner: str, repo_name: str, pr_number: int, body: str) -> dict[str, Any]:
        response = self._session.post(
            f"{self._base_url}/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments",
            json={"body": body},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("unexpected GitHub comment response payload")
        return payload

    def update_issue_comment(
        self, repo_owner: str, repo_name: str, comment_id: int, body: str
    ) -> dict[str, Any]:
        response = self._session.patch(
            f"{self._base_url}/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}",
            json={"body": body},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("unexpected GitHub comment response payload")
        return payload

    def reply_to_review_comment(
        self, repo_owner: str, repo_name: str, pr_number: int, comment_id: int, body: str
    ) -> dict[str, Any]:
        """Post a threaded reply to an existing PR review comment.

        Uses the REST replies endpoint so the reply is nested under the original
        comment's thread rather than posted as a new top-level comment.
        """
        response = self._session.post(
            f"{self._base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
            f"/comments/{comment_id}/replies",
            json={"body": body},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("unexpected GitHub reply response payload")
        return payload

    def resolve_review_thread(self, thread_id: str) -> dict[str, Any]:
        """Mark a review thread resolved (GraphQL node id from get_review_threads)."""
        return self._resolve_review_thread(thread_id, resolve=True)

    def unresolve_review_thread(self, thread_id: str) -> dict[str, Any]:
        """Re-open a previously resolved review thread."""
        return self._resolve_review_thread(thread_id, resolve=False)

    def _resolve_review_thread(self, thread_id: str, *, resolve: bool) -> dict[str, Any]:
        mutation_name = "resolveReviewThread" if resolve else "unresolveReviewThread"
        query = (
            "mutation($threadId: ID!) {\n"
            f"  {mutation_name}(input: {{threadId: $threadId}}) {{\n"
            "    thread { id isResolved }\n"
            "  }\n"
            "}"
        )
        payload = self._graphql(query=query, variables={"threadId": thread_id})
        thread = payload.get("data", {}).get(mutation_name, {}).get("thread", {})
        if not isinstance(thread, dict):
            raise ValueError("unexpected GitHub GraphQL thread payload")
        return thread

    def _get(self, path: str, params: dict[str, object] | None = None) -> Any:
        response = self._session.get(f"{self._base_url}{path}", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, (list, dict)):
            raise ValueError("unexpected GitHub API response payload")
        return payload

    def _graphql(self, query: str, variables: dict[str, object]) -> dict[str, Any]:
        response = self._session.post(
            f"{self._base_url}/graphql",
            json={"query": query, "variables": variables},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("unexpected GitHub GraphQL response payload")
        if "errors" in payload:
            raise ValueError(f"GitHub GraphQL returned errors: {payload['errors']}")
        return payload
