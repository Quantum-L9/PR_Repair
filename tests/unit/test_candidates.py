from pr_repair.candidates import build_repair_candidates
from pr_repair.types import FindingCluster


def test_build_repair_candidates_requires_approval_for_medium_risk() -> None:
    cluster = FindingCluster(
        cluster_id="cluster-1",
        pr_number=7,
        category="test_failure",
        root_cause_key="src/a.py",
        files=["src/a.py"],
        finding_ids=["f1"],
        risk_level="medium",
        repairability="auto_repairable",
    )
    candidates = build_repair_candidates(clusters=[cluster], verification_command=["pytest"])
    assert len(candidates) == 1
    assert candidates[0].approval_required is True
    assert candidates[0].target_files == ["src/a.py"]
