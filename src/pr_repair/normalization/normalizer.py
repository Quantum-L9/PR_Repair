# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [normalization]
# tags: [canonicalization, findings, bundle]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from copy import deepcopy

from pr_repair.normalization.fingerprint import build_finding_fingerprint
from pr_repair.types import Finding, FindingBundle


def normalize_finding(raw: dict, source_name: str, source_priority: int) -> Finding:
    """
    Canonical normalization entrypoint for future raw-payload extensions.
    """
    normalized = Finding.model_validate(raw)
    return normalized.model_copy(
        update={
            "source_name": source_name,
            "source_priority": source_priority,
            "fingerprint": build_finding_fingerprint(normalized),
        }
    )


def normalize_bundle(bundle: FindingBundle) -> FindingBundle:
    """
    Recompute canonical fingerprints and root-cause keys for every finding.
    """
    normalized_bundle = deepcopy(bundle)
    all_groups = [
        normalized_bundle.agent_review_findings,
        normalized_bundle.github_check_findings,
        normalized_bundle.github_comment_findings,
    ]
    for group in all_groups:
        for index, finding in enumerate(group):
            normalized_group_finding = _normalize_existing_finding(finding)
            group[index] = normalized_group_finding
    normalized_bundle.merged_findings = []
    return normalized_bundle


def _normalize_existing_finding(finding: Finding) -> Finding:
    fingerprint = build_finding_fingerprint(finding)
    root_cause_key = f"{finding.category}:{finding.file_path or '<repo-wide>'}"
    classification_reason = finding.classification_reason or "normalized_canonical_finding"
    return finding.model_copy(
        update={
            "fingerprint": fingerprint,
            "root_cause_key": root_cause_key,
            "classification_reason": classification_reason,
        }
    )
