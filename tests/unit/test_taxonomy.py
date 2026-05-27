from pr_repair.classification.taxonomy import (
    APPROVAL_REQUIRED_CATEGORIES,
    AUTO_REPAIRABLE_CATEGORIES,
    CATEGORY_TO_CONTRACT_IDS,
    FINDING_CATEGORIES,
)


def test_taxonomy_contains_required_categories() -> None:
    assert "architecture_boundary_violation" in FINDING_CATEGORIES
    assert "lint_failure" in FINDING_CATEGORIES
    assert "typing_failure" in FINDING_CATEGORIES
    assert "lint_failure" in AUTO_REPAIRABLE_CATEGORIES
    assert "architecture_boundary_violation" in APPROVAL_REQUIRED_CATEGORIES
    assert CATEGORY_TO_CONTRACT_IDS["architecture_boundary_violation"] == ["C-01", "ARCH-001"]
