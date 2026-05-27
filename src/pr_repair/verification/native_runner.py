# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [verification]
# tags: [native, subprocess, deterministic]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pr_repair.types import VerificationReport


def run_verification(command: list[str], repo_root: Path | None = None) -> VerificationReport:
    """
    Run the native verification command and capture a complete report.
    """
    root = repo_root or Path.cwd()
    started_at = datetime.now(tz=UTC)
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    finished_at = datetime.now(tz=UTC)
    return VerificationReport(
        command=list(command),
        success=completed.returncode == 0,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        started_at=started_at,
        finished_at=finished_at,
    )
