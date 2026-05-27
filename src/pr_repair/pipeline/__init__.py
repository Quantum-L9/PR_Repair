# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [pipeline]
# tags: [exports, orchestration, compatibility]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.pipeline import run_pipeline as _run_pipeline_module


def run_pipeline(config):
    """Package-level callable wrapper that preserves monkeypatchable orchestration seams."""
    for name in (
        "collect_candidate_prs",
        "ingest_tool_findings",
        "ingest_comment_findings",
        "execute_repair_plan",
    ):
        if hasattr(run_pipeline, name):
            setattr(_run_pipeline_module, name, getattr(run_pipeline, name))
    return _run_pipeline_module.run_pipeline(config)


for _name in (
    "collect_candidate_prs",
    "ingest_tool_findings",
    "ingest_comment_findings",
    "execute_repair_plan",
):
    setattr(run_pipeline, _name, getattr(_run_pipeline_module, _name))

__all__ = ["run_pipeline"]
