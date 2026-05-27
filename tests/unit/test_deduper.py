from pr_repair.normalization.deduper import dedupe_findings
from pr_repair.types import Finding, Severity, SourceName


def test_dedupe_findings_prefers_higher_priority_source() -> None:
    low = Finding(
        finding_id="f-low",
        pr_number=10,
        source_name=SourceName.github_review_comments,
        source_priority=50,
        severity=Severity.medium,
        category="ambiguous_comment",
        message="Unused import detected.",
        file_path="engine/example.py",
        line_start=5,
        line_end=5,
        fingerprint="same",
    )
    high = Finding(
        finding_id="f-high",
        pr_number=10,
        source_name=SourceName.coderabbit,
        source_priority=100,
        severity=Severity.medium,
        category="coderabbit_style_violation",
        message="Unused import detected.",
        file_path="engine/example.py",
        line_start=5,
        line_end=5,
        fingerprint="same",
    )

    deduped = dedupe_findings([low, high])

    assert len(deduped) == 1
    assert deduped[0].source_name is SourceName.coderabbit
