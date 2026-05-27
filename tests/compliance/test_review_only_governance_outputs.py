from pr_repair.learning.agent_md_recommender import build_agent_md_recommendations
from pr_repair.learning.validator_recommender import build_validator_recommendations
from pr_repair.types import LearningPacket


def test_governance_outputs_are_review_only() -> None:
    packets = [
        LearningPacket(
            packet_id="lp-1",
            source_prs=[404],
            repeated_failures=["approval_required"],
            agent_md_recommendations=["Never auto-repair protected paths."],
            validator_recommendations=["Block protected-path execution."],
            confidence=0.8,
        )
    ]

    agent_payload = build_agent_md_recommendations(packets)
    validator_payload = build_validator_recommendations(packets)

    assert agent_payload["write_policy"] == "review_only_no_direct_mutation"
    assert validator_payload["write_policy"] == "review_only_no_direct_mutation"
