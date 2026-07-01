# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [classification]
# tags: [taxonomy, contracts, repairability]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

FINDING_CATEGORIES = {
    "contract_violation",
    "style_violation",
    "bug_risk",
    "security_issue",
    "patch_coverage_failure",
    "missing_tests_for_changed_code",
    "github_required_check_failure",
    "lint_failure",
    "typing_failure",
    "docs_consistency_failure",
    "compliance_failure",
    "architecture_boundary_violation",
    "protected_file_violation",
    "ambiguous_comment",
    "validator_gap_signal",
    "agent_instruction_gap",
}

AUTO_REPAIRABLE_CATEGORIES = {
    "lint_failure",
    "typing_failure",
    "missing_tests_for_changed_code",
}

APPROVAL_REQUIRED_CATEGORIES = {
    "docs_consistency_failure",
    "compliance_failure",
    "style_violation",
    "architecture_boundary_violation",
    "protected_file_violation",
    "security_issue",
    "contract_violation",
    "github_required_check_failure",
}

NEVER_AUTO_REPAIR_CATEGORIES = {
    "architecture_boundary_violation",
    "protected_file_violation",
    "security_issue",
    "contract_violation",
}

CATEGORY_TO_CONTRACT_IDS = {
    "architecture_boundary_violation": ["C-01", "ARCH-001"],
    "contract_violation": ["C-01", "C-04", "C-05", "C-06", "C-08", "C-12", "C-17", "C-20"],
    "security_issue": ["C-06", "C-07", "C-08", "C-10"],
    "lint_failure": ["C-04", "C-05", "C-17"],
    "typing_failure": ["C-05", "C-17"],
    "protected_file_violation": ["T4", "T5"],
    "github_required_check_failure": ["C-15"],
    "missing_tests_for_changed_code": ["C-15"],
    "docs_consistency_failure": ["C-20"],
}
