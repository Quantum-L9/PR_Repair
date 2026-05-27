# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [classification]
# tags: [repo-aware, path-policy, contracts]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.classification.taxonomy import (
    APPROVAL_REQUIRED_CATEGORIES,
    AUTO_REPAIRABLE_CATEGORIES,
    CATEGORY_TO_CONTRACT_IDS,
    FINDING_CATEGORIES,
    NEVER_AUTO_REPAIR_CATEGORIES,
)
from pr_repair.repo_context.rules import classify_path_tier, is_protected_path, is_skip_review_path
from pr_repair.types import Finding, RepoContext, TierLevel


def classify_finding(finding: Finding, repo_context: RepoContext) -> Finding:
    """
    Enrich a finding with repo-aware classification and contract metadata.
    """
    file_path = finding.file_path or ""
    protected_path = bool(file_path) and is_protected_path(file_path, repo_context)
    skip_review_path = bool(file_path) and is_skip_review_path(file_path, repo_context)
    tier_impact = classify_path_tier(file_path, repo_context) if file_path else TierLevel.t0

    category = _infer_category(finding)
    if category not in FINDING_CATEGORIES:
        category = "validator_gap_signal"

    if protected_path:
        category = "protected_file_violation"
    elif _looks_like_architecture_boundary_violation(finding):
        category = "architecture_boundary_violation"

    repairable = category in AUTO_REPAIRABLE_CATEGORIES and not protected_path
    if category in NEVER_AUTO_REPAIR_CATEGORIES:
        repairable = False
    contract_ids = list(CATEGORY_TO_CONTRACT_IDS.get(category, []))
    repo_rule_sources = list(repo_context.source_documents)
    classification_reason = _build_reason(
        category=category,
        protected_path=protected_path,
        skip_review_path=skip_review_path,
        tier_impact=tier_impact,
    )
    root_cause_key = f"{category}:{file_path or '<repo-wide>'}"

    return finding.model_copy(
        update={
            "category": category,
            "repairable": repairable,
            "tier_impact": tier_impact,
            "protected_path": protected_path,
            "skip_review_path": skip_review_path,
            "contract_ids": contract_ids,
            "repo_rule_sources": repo_rule_sources,
            "root_cause_key": root_cause_key,
            "classification_reason": classification_reason,
        }
    )


def classify_findings(findings: list[Finding], repo_context: RepoContext) -> list[Finding]:
    return [classify_finding(finding, repo_context) for finding in findings]


def _infer_category(finding: Finding) -> str:
    message = finding.message.lower()
    source_name = finding.source_name.value

    if "coverage" in message:
        return "codecov_missing_tests_for_changed_code"
    if "mypy" in message or "type" in message:
        return "typing_failure"
    if "ruff" in message or "lint" in message or "format" in message or "unused import" in message:
        return "lint_failure"
    if "fastapi" in message and "engine" in message:
        return "architecture_boundary_violation"
    if "yaml.load" in message or "safe_load" in message:
        return "compliance_failure"
    if "credential" in message or "api key" in message or "token" in message:
        return "coderabbit_security_issue"
    if source_name == "github_checks":
        return "github_required_check_failure"
    if source_name == "codecov_cloud":
        return "codecov_patch_coverage_failure"
    if source_name == "coderabbit":
        return "coderabbit_style_violation"
    return finding.category or "ambiguous_comment"


def _looks_like_architecture_boundary_violation(finding: Finding) -> bool:
    message = finding.message.lower()
    return "fastapi" in message and "engine" in message


def _build_reason(
    *,
    category: str,
    protected_path: bool,
    skip_review_path: bool,
    tier_impact: TierLevel,
) -> str:
    return (
        f"category={category}; protected_path={protected_path}; "
        f"skip_review_path={skip_review_path}; tier_impact={tier_impact.value}"
    )



def requires_approval_for_category(category: str) -> bool:
    return category in APPROVAL_REQUIRED_CATEGORIES


def is_never_auto_repair(category: str) -> bool:
    return category in NEVER_AUTO_REPAIR_CATEGORIES
