# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [learning]
# tags: [validator, recommendations, telemetry]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.types import LearningPacket


def build_validator_recommendations(packets: list[LearningPacket]) -> dict:
    """
    Build a reviewable validator recommendation packet.

    This function emits structured suggestions for external validator/review
    systems and never mutates them directly.
    """
    new_rule_candidates: list[str] = []
    false_positive_candidates: list[str] = []
    severity_adjustments: list[str] = []
    missing_check_candidates: list[str] = []

    for packet in packets:
        new_rule_candidates.extend(packet.validator_recommendations)
        for failure in packet.repeated_failures:
            if failure == "approval_required":
                severity_adjustments.append(
                    "Escalate protected-path and write-ceiling violations to blocking severity."
                )
            if failure == "rolled_back_verification_failed":
                missing_check_candidates.append(
                    "Add a pre-mutation validator simulation for patch instruction applicability."
                )
            if failure.startswith("verification_exit_"):
                false_positive_candidates.append(
                    f"Review whether validator classification missed root causes behind `{failure}`."
                )

    return {
        "target_system": "external_validator_suite",
        "write_policy": "review_only_no_direct_mutation",
        "sections": {
            "new_rule_candidates": list(dict.fromkeys(new_rule_candidates)),
            "false_positive_candidates": list(dict.fromkeys(false_positive_candidates)),
            "severity_adjustments": list(dict.fromkeys(severity_adjustments)),
            "missing_check_candidates": list(dict.fromkeys(missing_check_candidates)),
        },
        "packet_count": len(packets),
    }
