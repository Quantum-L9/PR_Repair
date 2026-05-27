# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [repair]
# tags: [patch, generation, deterministic]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pathlib import Path

from pr_repair.types import RepairPlan


def generate_patch_instructions(
    plan: RepairPlan,
    repo_root: Path | None = None,
) -> list[dict]:
    root = repo_root or Path.cwd()
    instructions: list[dict] = []
    for finding in plan.targeted_findings:
        if not finding.file_path or finding.line_start is None:
            continue
        if not finding.suggested_fix:
            continue

        expected = finding.message
        path = root / finding.file_path
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if finding.line_start < 1 or finding.line_start > len(lines):
                continue
            expected = lines[finding.line_start - 1]

        instructions.append(
            {
                "op": "replace_line",
                "file_path": finding.file_path,
                "line_number": finding.line_start,
                "expected": expected,
                "replacement": finding.suggested_fix,
                "finding_id": finding.finding_id,
                "category": finding.category,
            }
        )
    return instructions
