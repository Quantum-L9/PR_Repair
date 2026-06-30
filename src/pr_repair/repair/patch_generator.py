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

from pr_repair.types import Finding, RepairPlan


def generate_patch_instructions(
    plan: RepairPlan,
    repo_root: Path | None = None,
) -> list[dict]:
    """Translate targeted findings into exact, guarded patch instructions.

    Two lanes feed one applier:
    - autofix findings carry an exact Semgrep ``replacement_text`` and line range
      -> ``replace_line`` (single) or ``replace_range`` (span), with the on-disk
      content captured as the guard. No fuzzy matching.
    - legacy/LLM findings carry a ``suggested_fix`` -> single-line ``replace_line``.
    """
    root = repo_root or Path.cwd()
    instructions: list[dict] = []
    for finding in plan.targeted_findings:
        if not finding.file_path or finding.line_start is None:
            continue

        path = root / finding.file_path
        lines: list[str] | None = None
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()

        if finding.replacement_text is not None:
            instruction = _build_autofix_instruction(finding, lines)
        elif finding.suggested_fix:
            instruction = _build_suggested_fix_instruction(finding, lines)
        else:
            instruction = None

        if instruction is not None:
            instructions.append(instruction)
    return instructions


def _build_autofix_instruction(finding: Finding, lines: list[str] | None) -> dict[str, object] | None:
    assert finding.line_start is not None  # guarded by caller
    line_start = finding.line_start
    line_end = finding.line_end if finding.line_end is not None else line_start
    if lines is not None and (line_start < 1 or line_end > len(lines)):
        return None

    if line_end == line_start:
        expected = lines[line_start - 1] if lines is not None else finding.message
        return {
            "op": "replace_line",
            "file_path": finding.file_path,
            "line_number": line_start,
            "expected": expected,
            "replacement": finding.replacement_text,
            "finding_id": finding.finding_id,
            "rule_id": finding.rule_id,
            "category": finding.category,
        }

    expected_block = lines[line_start - 1 : line_end] if lines is not None else None
    return {
        "op": "replace_range",
        "file_path": finding.file_path,
        "line_start": line_start,
        "line_end": line_end,
        "expected_block": expected_block,
        "replacement": finding.replacement_text,
        "finding_id": finding.finding_id,
        "rule_id": finding.rule_id,
        "category": finding.category,
    }


def _build_suggested_fix_instruction(
    finding: Finding, lines: list[str] | None
) -> dict[str, object] | None:
    assert finding.line_start is not None  # guarded by caller
    expected = finding.message
    if lines is not None:
        if finding.line_start < 1 or finding.line_start > len(lines):
            return None
        expected = lines[finding.line_start - 1]
    return {
        "op": "replace_line",
        "file_path": finding.file_path,
        "line_number": finding.line_start,
        "expected": expected,
        "replacement": finding.suggested_fix,
        "finding_id": finding.finding_id,
        "category": finding.category,
    }
