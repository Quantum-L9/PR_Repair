# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [corpus]
# tags: [highway, corpus, public-api]
# owner: platform
# status: active
# --- /L9_META ---
"""L9 Corpus Highway integration for PR_Repair.

Provides bidirectional data flow between PR_Repair and the L9
constellation via the .l9/corpus/ shared filesystem convention.
"""
from pr_repair.corpus.corpus_reader import (
    read_compiled_rules,
    read_hitl_matrix,
    read_protected_paths,
    read_scanner_rules,
)
from pr_repair.corpus.corpus_writer import (
    write_findings,
    write_learning_packets,
    write_telemetry,
)

__all__ = [
    "read_compiled_rules",
    "read_hitl_matrix",
    "read_protected_paths",
    "read_scanner_rules",
    "write_findings",
    "write_learning_packets",
    "write_telemetry",
]
