# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [normalization]
# tags: [fingerprint, dedupe, deterministic]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import hashlib
import json

from pr_repair.types import Finding


def build_finding_fingerprint(finding: Finding) -> str:
    """
    Build a stable, source-aware fingerprint for a finding.

    The fingerprint intentionally ignores evidence_url and suggested_fix so the same
    underlying issue can dedupe across sources with differing metadata wrappers.
    """
    payload = {
        "pr_number": finding.pr_number,
        "file_path": finding.file_path,
        "line_start": finding.line_start,
        "line_end": finding.line_end,
        "message": finding.message.strip(),
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
