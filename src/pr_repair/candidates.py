# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_system_bundle
# engine: pr_repair
# layer: [planning, candidates]
# tags: [repair-candidates, approval, verification]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import hashlib
import json

from pr_repair.types import FindingCluster, RepairCandidate


def build_repair_candidates(
    *,
    clusters: list[FindingCluster],
    verification_command: list[str],
) -> list[RepairCandidate]:
    """Build bounded repair candidates from finding clusters."""
    candidates: list[RepairCandidate] = []
    for cluster in clusters:
        digest = hashlib.sha256(
            json.dumps([cluster.pr_number, cluster.cluster_id], sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        approval_required = cluster.repairability != "auto_repairable" or cluster.risk_level != "low"
        candidates.append(
            RepairCandidate(
                candidate_id=f"candidate-{digest}",
                pr_number=cluster.pr_number,
                cluster_ids=[cluster.cluster_id],
                target_files=cluster.files,
                risk_level=cluster.risk_level,
                approval_required=approval_required,
                verification_command=verification_command,
                justification=(
                    f"Cluster {cluster.cluster_id} groups {cluster.category} findings "
                    f"for PR #{cluster.pr_number}."
                ),
            )
        )
    return candidates
