# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [learning]
# tags: [agent-md, recommendations, governance]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.types import LearningPacket


def build_agent_md_recommendations(packets: list[LearningPacket]) -> dict:
    """
    Build a reviewable AGENT.md recommendation packet.

    This function never mutates AGENT.md directly.
    """
    recurring_mistakes: list[str] = []
    stronger_preflight_rules: list[str] = []
    repo_specific_do_not_repeat_rules: list[str] = []
    common_test_requirements: list[str] = []
    comment_handling_priorities: list[str] = []

    for packet in packets:
        recurring_mistakes.extend(packet.repeated_failures)
        stronger_preflight_rules.extend(packet.agent_md_recommendations)

    unique_recurring = list(dict.fromkeys(recurring_mistakes))
    unique_rules = list(dict.fromkeys(stronger_preflight_rules))

    if any(item == "approval_required" for item in unique_recurring):
        repo_specific_do_not_repeat_rules.append(
            "Do not attempt automatic repairs on protected or above-ceiling paths without human approval."
        )
    if any(item.startswith("verification_") for item in unique_recurring):
        common_test_requirements.append(
            "All proposed repairs must be validated against `make agent-check` before they are marked ready."
        )
    comment_handling_priorities.extend(
        [
            "Tool findings must remain higher priority than comments.",
            "Comments may refine but must not silently override higher-priority tool blockers.",
        ]
    )

    return {
        "target_document": "AGENT.md",
        "write_policy": "review_only_no_direct_mutation",
        "sections": {
            "recurring_mistakes": unique_recurring,
            "stronger_preflight_rules": unique_rules,
            "repo_specific_do_not_repeat_rules": list(dict.fromkeys(repo_specific_do_not_repeat_rules)),
            "common_test_requirements": list(dict.fromkeys(common_test_requirements)),
            "comment_handling_priorities": list(dict.fromkeys(comment_handling_priorities)),
        },
        "packet_count": len(packets),
    }
