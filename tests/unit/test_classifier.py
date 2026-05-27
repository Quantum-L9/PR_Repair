from pr_repair.classification.classifier import classify_finding
from pr_repair.types import Finding, RepoContext, Severity, SourceName, TierLevel


def test_classifier_marks_protected_path_and_contracts() -> None:
    repo_context = RepoContext(
        protected_paths=["app/models/**"],
        skip_review_paths=["docs/**"],
        write_ceiling=TierLevel.t1,
        source_documents=["AGENT.md", "REPO_MAP.md"],
    )
    finding = Finding(
        finding_id="f-1",
        pr_number=22,
        source_name=SourceName.coderabbit,
        source_priority=100,
        severity=Severity.medium,
        category="coderabbit_style_violation",
        message="Model field uses camelCase naming.",
        file_path="app/models/entity.py",
        line_start=9,
        line_end=9,
        fingerprint="fp-1",
    )

    classified = classify_finding(finding, repo_context)

    assert classified.protected_path is True
    assert classified.category == "protected_file_violation"
    assert "T4" in classified.contract_ids or "T5" in classified.contract_ids
