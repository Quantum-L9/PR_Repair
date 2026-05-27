# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_system_bundle
# engine: pr_repair
# layer: [planning, clustering]
# tags: [findings, clustering, candidates]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import hashlib
import json

from pr_repair.types import Finding, FindingCluster


def _risk_level(findings: list[Finding]) -> str:
    if any(finding.severity.value == "critical" for finding in findings):
        return "high"
    if any(finding.severity.value == "high" for finding in findings):
        return "medium"
    return "low"


def _repairability(findings: list[Finding]) -> str:
    if any(not finding.repairable for finding in findings):
        return "approval_required"
    return "auto_repairable"


def cluster_findings(findings: list[Finding]) -> list[FindingCluster]:
    """Group normalized findings into root-cause-oriented repair clusters."""
    groups: dict[tuple[int, str, str], list[Finding]] = {}
    for finding in findings:
        root_cause_key = finding.root_cause_key or finding.file_path or finding.category
        key = (finding.pr_number, finding.category, root_cause_key)
        groups.setdefault(key, []).append(finding)

    clusters: list[FindingCluster] = []
    for (pr_number, category, root_cause_key), items in groups.items():
        digest = hashlib.sha256(
            json.dumps([pr_number, category, root_cause_key], sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        files = sorted({item.file_path for item in items if item.file_path})
        clusters.append(
            FindingCluster(
                cluster_id=f"cluster-{digest}",
                pr_number=pr_number,
                category=category,
                root_cause_key=root_cause_key,
                files=files,
                finding_ids=[item.finding_id for item in items],
                risk_level=_risk_level(items),
                repairability=_repairability(items),
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.cluster_id)
