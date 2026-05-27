# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [planning]
# tags: [approval, safety, governance]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.config import AppConfig
from pr_repair.priorities import is_within_write_ceiling
from pr_repair.types import RepairPlan, TierLevel


def requires_human_approval(plan: RepairPlan, config: AppConfig) -> bool:
    """
    Decide whether a repair plan requires human approval before execution.

    Approval is required when:
    - the plan itself says so
    - executable is false
    - the target tier exceeds the configured write ceiling
    - protected paths are touched
    - high-risk plans are present
    - repair-and-push is requested outside T1/T2 safe ceiling
    """
    if plan.approval_required:
        return True
    if not plan.executable:
        return True
    if plan.protected_paths_touched:
        return True
    if not is_within_write_ceiling(plan.target_tier, config.write_ceiling):
        return True
    if plan.risk_level == "high":
        return True
    if config.allow_push and plan.target_tier not in {TierLevel.t1, TierLevel.t2}:
        return True
    return False
