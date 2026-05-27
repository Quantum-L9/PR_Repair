from pathlib import Path

from pr_repair.classification.classifier import classify_findings
from pr_repair.normalization.deduper import dedupe_findings
from pr_repair.normalization.normalizer import normalize_bundle
from pr_repair.types import Finding, FindingBundle, PRRef, RepoContext, Severity, SourceName, TierLevel


def test_pipeline_signal_order_preserves_higher_priority_sources(tmp_path: Path) -> None:
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=44,
        title="fix",
        head_branch="feature/fix",
        base_branch="main",
        head_sha="sha-44",
        is_draft=False,
        author="dev",
        labels=[],
    )
    bundle = FindingBundle(
        pr_ref=pr,
        coderabbit_findings=[
            Finding(
                finding_id="cr-1",
                pr_number=44,
                source_name=SourceName.coderabbit,
                source_priority=100,
                severity=Severity.medium,
                category="coderabbit_style_violation",
                message="Unused import detected.",
                file_path="engine/module.py",
                line_start=4,
                line_end=4,
                fingerprint="temp-a",
            )
        ],
        github_comment_findings=[
            Finding(
                finding_id="gh-1",
                pr_number=44,
                source_name=SourceName.github_review_comments,
                source_priority=50,
                severity=Severity.medium,
                category="ambiguous_comment",
                message="Unused import detected.",
                file_path="engine/module.py",
                line_start=4,
                line_end=4,
                fingerprint="temp-b",
            )
        ],
    )

    repo_context = RepoContext(
        protected_paths=[],
        skip_review_paths=[],
        write_ceiling=TierLevel.t1,
        source_documents=["AGENT.md"],
    )

    normalized = normalize_bundle(bundle)
    merged = normalized.coderabbit_findings + normalized.github_comment_findings
    deduped = dedupe_findings(merged)
    classified = classify_findings(deduped, repo_context)

    assert len(classified) == 1
    assert classified[0].source_name is SourceName.coderabbit
