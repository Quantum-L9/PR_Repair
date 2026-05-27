from pr_repair.clustering import cluster_findings
from pr_repair.types import Finding, Severity, SourceName


def test_cluster_by_category_and_file() -> None:
    findings = [
        Finding(
            finding_id="1",
            pr_number=5,
            source_name=SourceName.coderabbit,
            source_priority=100,
            severity=Severity.medium,
            category="lint_failure",
            message="A",
            file_path="src/a.py",
            fingerprint="a",
            repairable=True,
        ),
        Finding(
            finding_id="2",
            pr_number=5,
            source_name=SourceName.codecov_cloud,
            source_priority=90,
            severity=Severity.medium,
            category="lint_failure",
            message="B",
            file_path="src/a.py",
            fingerprint="b",
            repairable=True,
        ),
    ]
    clusters = cluster_findings(findings)
    assert len(clusters) == 1
    assert clusters[0].files == ["src/a.py"]
