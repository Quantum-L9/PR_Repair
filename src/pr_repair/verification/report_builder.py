# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [verification]
# tags: [reports, markdown, audit]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from pr_repair.types import RepairExecution, VerificationReport


def build_verification_markdown(report: VerificationReport) -> str:
    command = " ".join(report.command)
    return (
        "# Verification report\n\n"
        f"- Command: `{command}`\n"
        f"- Success: `{report.success}`\n"
        f"- Exit code: `{report.exit_code}`\n"
        f"- Started: `{report.started_at.isoformat()}`\n"
        f"- Finished: `{report.finished_at.isoformat()}`\n\n"
        "## Stdout\n\n"
        f"```text\n{report.stdout}\n```\n\n"
        "## Stderr\n\n"
        f"```text\n{report.stderr}\n```\n"
    )


def build_pr_result_markdown(execution: RepairExecution) -> str:
    verification = execution.verification_result
    verification_summary = "not-run"
    if verification is not None:
        verification_summary = f"success={verification.success} exit_code={verification.exit_code}"

    return (
        f"# PR repair execution {execution.execution_id}\n\n"
        f"- PR: `{execution.pr_ref.repo_full_name}#{execution.pr_ref.pr_number}`\n"
        f"- Plan ID: `{execution.plan_id}`\n"
        f"- Mode: `{execution.mode.value}`\n"
        f"- Status: `{execution.status}`\n"
        f"- Modified files: `{', '.join(execution.modified_files) if execution.modified_files else 'none'}`\n"
        f"- Verification: `{verification_summary}`\n"
        f"- Push result: `{execution.push_result or 'not-pushed'}`\n"
    )
