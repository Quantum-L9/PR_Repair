from pathlib import Path

from pr_repair.output.artifact_writer import write_interpretation_artifacts
from pr_repair.state_store import StateStore
from pr_repair.types import Finding, FindingBundle, PRRef, Severity, SourceName


def test_phase3_artifacts_are_written(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=55,
        title="interpret",
        head_branch="feature/interpret",
        base_branch="main",
        head_sha="sha-55",
        is_draft=False,
        author="dev",
        labels=[],
    )
    finding = Finding(
        finding_id="f-55",
        pr_number=55,
        source_name=SourceName.github_checks,
        source_priority=80,
        severity=Severity.high,
        category="github_required_check_failure",
        message="Required check failed: ci-gate",
        fingerprint="fp-55",
    )
    bundle = FindingBundle(pr_ref=pr, merged_findings=[finding])
    write_interpretation_artifacts(store, bundle, [finding], [finding])

    assert (tmp_path / "findings_normalized.json").exists()
    assert (tmp_path / "findings_deduped.json").exists()
    assert (tmp_path / "findings_classified.json").exists()
    assert (tmp_path / "normalization_errors.json").exists()
    assert (tmp_path / "interpretation_report.md").exists()
