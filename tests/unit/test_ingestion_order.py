import json

from pr_repair.config import AppConfig
from pr_repair.ingestion.comment_ingestor import ingest_comment_findings
from pr_repair.ingestion.tool_finding_ingestor import ingest_tool_findings
from pr_repair.types import PRRef


class FakeGitHubConnector:
    def get_check_runs(self, repo_owner: str, repo_name: str, head_sha: str) -> list[dict]:
        return [
            {
                "id": "check-1",
                "name": "ci-gate",
                "status": "completed",
                "conclusion": "failure",
                "html_url": "https://example.com/check-1",
            }
        ]

    def get_review_comments(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict]:
        return [
            {
                "id": "comment-1",
                "body": "Please tighten this assertion.",
                "path": "tests/test_example.py",
                "line": 10,
                "html_url": "https://example.com/comment-1",
                "user": {"login": "human-reviewer"},
            },
            {
                "id": "comment-2",
                "body": "CodeRabbit says this import is unsafe.",
                "path": "engine/example.py",
                "line": 5,
                "html_url": "https://example.com/comment-2",
                "user": {"login": "coderabbitai"},
            },
        ]

    def get_issue_comments(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict]:
        return []


class FakeCodeRabbitConnector:
    def get_pr_findings(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict]:
        return [
            {
                "id": "cr-1",
                "message": "Unused import detected.",
                "path": "engine/example.py",
                "start_line": 5,
                "end_line": 5,
                "severity": "medium",
                "category": "coderabbit_style_violation",
            }
        ]


class FakeCodecovConnector:
    def get_pr_findings(self, repo_owner: str, repo_name: str, pr_number: int) -> list[dict]:
        return [
            {
                "id": "cc-1",
                "message": "Changed code lacks patch coverage.",
                "path": "engine/example.py",
                "start_line": 20,
                "end_line": 30,
                "severity": "medium",
                "category": "codecov_patch_coverage_failure",
            }
        ]


def test_tool_findings_are_ingested_before_comments_and_raw_artifacts_are_written(tmp_path) -> None:
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["make", "agent-check"],
        mode="dry_run",
        output_dir=tmp_path,
    )
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=7,
        title="repair me",
        head_branch="feature/repair",
        base_branch="main",
        head_sha="sha-7",
        is_draft=False,
        author="dev",
        labels=[],
        changed_files=[],
    )

    bundle = ingest_tool_findings(
        config,
        pr,
        github_connector=FakeGitHubConnector(),
        coderabbit_connector=FakeCodeRabbitConnector(),
        codecov_connector=FakeCodecovConnector(),
    )
    assert len(bundle.coderabbit_findings) == 1
    assert len(bundle.codecov_findings) == 1
    assert len(bundle.github_check_findings) == 1
    assert bundle.github_comment_findings == []

    bundle = ingest_comment_findings(
        config,
        pr,
        bundle,
        github_connector=FakeGitHubConnector(),
    )
    assert len(bundle.github_comment_findings) == 1
    assert bundle.github_comment_findings[0].message == "Please tighten this assertion."

    raw_dir = tmp_path / "raw" / "7"
    assert (raw_dir / "coderabbit.json").exists()
    assert (raw_dir / "codecov.json").exists()
    assert (raw_dir / "github_checks.json").exists()
    assert (raw_dir / "github_review_comments.json").exists()

    coderabbit_payload = json.loads((raw_dir / "coderabbit.json").read_text(encoding="utf-8"))
    assert coderabbit_payload[0]["id"] == "cr-1"
