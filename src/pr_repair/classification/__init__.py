# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [classification]
# tags: [exports, taxonomy, classifier]
# owner: platform
# status: active
# --- /L9_META ---

from pr_repair.classification.classifier import (
    classify_finding,
    classify_findings,
    is_never_auto_repair,
    requires_approval_for_category,
)
from pr_repair.classification.taxonomy import (
    APPROVAL_REQUIRED_CATEGORIES,
    AUTO_REPAIRABLE_CATEGORIES,
    CATEGORY_TO_CONTRACT_IDS,
    FINDING_CATEGORIES,
    NEVER_AUTO_REPAIR_CATEGORIES,
)

__all__ = [
    "classify_finding",
    "classify_findings",
    "FINDING_CATEGORIES",
    "AUTO_REPAIRABLE_CATEGORIES",
    "APPROVAL_REQUIRED_CATEGORIES",
    "NEVER_AUTO_REPAIR_CATEGORIES",
    "CATEGORY_TO_CONTRACT_IDS",
]
