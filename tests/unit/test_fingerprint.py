from pr_repair.normalization.fingerprint import build_finding_fingerprint
from pr_repair.types import Finding, Severity, SourceName


def test_build_finding_fingerprint_is_deterministic() -> None:
    finding = Finding(
        finding_id="f-1",
        pr_number=10,
        source_name=SourceName.coderabbit,
        source_priority=100,
        severity=Severity.medium,
        category="coderabbit_style_violation",
        message="Unused import detected.",
        file_path="engine/example.py",
        line_start=5,
        line_end=5,
        fingerprint="temp",
    )
    first = build_finding_fingerprint(finding)
    second = build_finding_fingerprint(finding)
    assert first == second
