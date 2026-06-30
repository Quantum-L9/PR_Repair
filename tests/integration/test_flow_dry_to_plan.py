from pr_repair.classification.classifier import classify_findings
from pr_repair.config import AppConfig
from pr_repair.normalization.normalizer import normalize_bundle
from pr_repair.planning.repair_planner import build_repair_plan
from pr_repair.types import (
    ExecutionMode,
    Finding,
    FindingBundle,
    PRRef,
    RepoContext,
    Severity,
    SourceName,
    TierLevel,
)


def test_flow_dry_to_plan_produces_safe_t1_plan(tmp_path) -> None:
    config = AppConfig(
        github_token="token",
        github_repository="owner/repo",
        verify_command=["make", "agent-check"],
        mode=ExecutionMode.dry_run,
        output_dir=tmp_path,
        write_ceiling=TierLevel.t1,
    )
    repo_context = RepoContext(
        protected_paths=["app/models/**"],
        skip_review_paths=["docs/**"],
        write_ceiling=TierLevel.t1,
        source_documents=["AGENT.md", "REPO_MAP.md"],
    )
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=101,
        title="repair lint",
        head_branch="fix/lint",
        base_branch="main",
        head_sha="sha-101",
        is_draft=False,
        author="dev",
        labels=[],
    )
    bundle = FindingBundle(
        pr_ref=pr,
        agent_review_findings=[
            Finding(
                finding_id="f-101",
                pr_number=101,
                source_name=SourceName.agent_review,
                source_priority=100,
                severity=Severity.medium,
                category="style_violation",
                message="Unused import detected.",
                file_path="scripts/example.py",
                line_start=4,
                line_end=4,
                suggested_fix="import os",
                repairable=False,
                confidence=0.9,
                fingerprint="temp-101",
            )
        ],
    )

    normalized = normalize_bundle(bundle)
    merged = normalized.agent_review_findings
    classified = classify_findings(merged, repo_context)
    plan = build_repair_plan(pr, classified, config)

    assert plan.target_tier is TierLevel.t1
    assert plan.protected_paths_touched is False
    assert plan.risk_level in {"low", "medium"}
