from pathlib import Path

import yaml

from pr_repair.learning.agent_md_recommender import build_agent_md_recommendations
from pr_repair.learning.pattern_extractor import extract_learning_packets
from pr_repair.learning.validator_recommender import build_validator_recommendations
from pr_repair.state_store import StateStore
from pr_repair.types import ExecutionMode, PRRef, RepairExecution, VerificationReport


def test_learning_outputs_are_writable_review_only_packets(tmp_path: Path) -> None:
    pr = PRRef(
        repo_owner="owner",
        repo_name="repo",
        pr_number=81,
        title="repair",
        head_branch="fix/repair",
        base_branch="main",
        head_sha="sha-81",
        is_draft=False,
        author="dev",
        labels=[],
    )
    execution = RepairExecution(
        execution_id="exec-81",
        pr_ref=pr,
        plan_id="plan-81",
        mode=ExecutionMode.repair_and_verify,
        verification_result=VerificationReport(
            command=["make", "agent-check"],
            success=False,
            exit_code=2,
            stdout="",
            stderr="failed",
        ),
        status="rolled_back_verification_failed",
    )

    packets = extract_learning_packets([execution])
    agent_payload = build_agent_md_recommendations(packets)
    validator_payload = build_validator_recommendations(packets)

    store = StateStore(tmp_path)
    agent_path = store.write_yaml("AGENT_md_recommendations.yaml", agent_payload)
    validator_path = store.write_yaml("validator_recommendations.yaml", validator_payload)

    loaded_agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    loaded_validator = yaml.safe_load(validator_path.read_text(encoding="utf-8"))

    assert loaded_agent["write_policy"] == "review_only_no_direct_mutation"
    assert loaded_validator["write_policy"] == "review_only_no_direct_mutation"
