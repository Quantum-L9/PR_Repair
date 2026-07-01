# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [ingestion, entrypoint]
# tags: [review, normalize, agent-review-payload, runtime]
# owner: platform
# status: active
# --- /L9_META ---

"""Runtime entrypoint: normalize live PR review context into ``agent_review_payload.json``.

This closes the wiring gap between the per-tool review adapters (``pr_repair.tools``)
and the deterministic pipeline (``pr-repair run``), which consumes the canonical
``agent_review_payload.json``. The adapters knew how to turn a tool's native review
threads into canonical findings, but nothing turned a *live* PR review into the
on-disk payload the bot actuates from — so the workflow could only skip.

Two input modes, one output contract:

* ``--event-path`` (live): read the GitHub Actions event JSON, detect the
  originating review tool, fetch that tool's unresolved threads via the GitHub
  connector, normalize, and write the payload.
* ``--context`` (offline/deterministic): read a captured review-context JSON
  (``{"tool", "pr", "threads"}``) and normalize it without any network. This is
  the reproducible path exercised by tests and by re-runs from a captured event.

Exit codes are the workflow's contract:

* ``0`` — a schema-valid payload was written (actuation should proceed).
* ``3`` — genuinely no actionable review source (no PR / no recognized tool):
  the workflow skips downstream actuation *cleanly*.
* ``1`` — review context existed but could not be normalized or failed schema
  validation: the workflow fails closed and blocks downstream actuation.

The entrypoint never fabricates review data and never emits a payload it could
not schema-validate. Review bodies (which may quote secrets) are never logged;
only counts and the output path are printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

from pr_repair.connectors.github import GitHubConnector
from pr_repair.ingestion.payload_parser import SCHEMA_PATH
from pr_repair.server.github_webhook import detect_tool
from pr_repair.tools.registry import adapter_for_tool
from pr_repair.types import PRRef

# The payload contract version this entrypoint emits (matches the schema's
# semver pattern; the pipeline validates the value, not a specific number).
PAYLOAD_SCHEMA_VERSION = "1.0.0"

# Exit codes — the workflow branches on these.
EXIT_PRODUCED = 0
EXIT_FAILED = 1
EXIT_SKIPPED = 3

# Schema-allowed keys, mirroring contracts/agent-review-payload.schema.json
# (``additionalProperties: false`` there means we must project, not pass through).
_PR_REQUIRED = (
    "repo_owner", "repo_name", "pr_number", "title",
    "head_branch", "base_branch", "head_sha", "author",
)
_PR_KEYS = (*_PR_REQUIRED, "is_draft", "labels", "changed_files")
_AUTOFIX_KEYS = (
    "finding_id", "category", "severity", "message", "file_path",
    "line_start", "line_end", "replacement_text", "rule_id", "evidence_url",
    "confidence", "tags", "tool", "thread_id", "comment_id",
)
_MANUAL_KEYS = (
    "finding_id", "category", "severity", "message", "file_path",
    "line_start", "line_end", "suggested_fix", "rule_id", "evidence_url",
    "confidence", "tags", "tool", "thread_id", "comment_id",
)


class ReviewIngestError(Exception):
    """Review context existed but is malformed or un-normalizable (fail closed)."""


def _allowed_io_roots() -> tuple[Path, ...]:
    """Return the canonical directories this entrypoint may read from / write to.

    Defaults to the current working directory (the repo/actuation root) plus the
    OS temp dir (used by tests and by workflow scratch space). Operators can add
    further roots via ``PR_REPAIR_IO_ROOT`` (os.pathsep-separated) for callers
    that legitimately stage inputs/outputs outside the CWD. Anything outside all
    allowed roots is rejected before any filesystem access, which breaks the
    path-injection taint flow flagged by SonarCloud ``pythonsecurity:S8707``
    ("LLMs running this code with faulty CLI arguments can escape file system
    restrictions") without blocking valid repo-relative or staged paths.
    """
    import tempfile

    roots = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    extra = os.getenv("PR_REPAIR_IO_ROOT", "")
    for part in extra.split(os.pathsep):
        part = part.strip()
        if part:
            roots.append(Path(part).resolve())
    return tuple(roots)


def _safe_path(path: str) -> Path:
    """Canonicalize ``path`` and assert it stays within an allowed IO root.

    Raises :class:`ReviewIngestError` on traversal outside every allowed root,
    so a malicious/faulty CLI argument (e.g. ``../../etc/passwd`` or an absolute
    path pointing outside the sandbox) cannot escape the filesystem restriction.
    """
    if not isinstance(path, str) or not path:
        raise ReviewIngestError("path argument must be a non-empty string")
    resolved = Path(path).resolve()
    roots = _allowed_io_roots()
    for root in roots:
        if resolved == root or root in resolved.parents:
            return resolved
    allowed = ", ".join(str(r) for r in roots)
    raise ReviewIngestError(
        f"refusing path outside allowed roots ({allowed}): {path}"
    )


class ReviewSkipped(Exception):
    """No actionable review source is present (clean skip, not a failure)."""


class _StaticConnector:
    """Serves a fixed set of raw review threads (offline ``--context`` mode).

    Every adapter reads through ``get_review_threads``; serving the captured
    threads here runs the adapter's real filtering (unresolved + authorship) so
    the offline path is faithful to the live one.
    """

    def __init__(self, threads: list[dict[str, Any]]) -> None:
        self._threads = threads

    def get_review_threads(self, owner: str, repo: str, pr: int) -> list[dict[str, Any]]:
        return self._threads


def _project(item: dict[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    """Whitelist ``item`` to schema-allowed, present, non-null keys."""
    return {key: item[key] for key in keys if item.get(key) is not None}


def _nested(node: Any, *path: str) -> Any:
    """Walk a chain of dict keys, returning None if any level is missing."""
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def build_payload(
    pr: dict[str, Any],
    findings: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble a schema-shaped payload from a PR block and normalized findings.

    Findings are partitioned by the adapter-stamped ``_disposition`` into
    deterministic ``autofix_candidates`` vs ``manual_review_required`` and
    projected onto the schema's allowed keys. Missing required PR fields fail
    closed here; a mis-stamped autofix finding (missing file/line/replacement)
    is caught later by schema validation.
    """
    pr_block = _project(pr, _PR_KEYS)
    missing = [key for key in _PR_REQUIRED if key not in pr_block]
    if missing:
        raise ReviewIngestError(
            f"review context 'pr' missing required field(s): {', '.join(missing)}"
        )

    autofix: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []
    for finding in findings:
        if finding.get("_disposition") == "autofix":
            autofix.append(_project(finding, _AUTOFIX_KEYS))
        else:
            manual.append(_project(finding, _MANUAL_KEYS))

    payload: dict[str, Any] = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "pr": pr_block,
        "autofix_candidates": autofix,
        "manual_review_required": manual,
    }
    if generated_at is not None:
        payload["generated_at"] = generated_at
    return payload


def payload_from_context(
    context: dict[str, Any], *, generated_at: str | None = None
) -> dict[str, Any]:
    """Normalize a captured ``{"tool", "pr", "threads"}`` context (offline mode)."""
    if not isinstance(context, dict):
        raise ReviewIngestError("review context must be a JSON object")
    tool = context.get("tool")
    if not isinstance(tool, str) or not tool:
        raise ReviewIngestError("review context missing 'tool'")
    pr = context.get("pr")
    if not isinstance(pr, dict):
        raise ReviewIngestError("review context missing 'pr' object")
    threads = context.get("threads")
    if not isinstance(threads, list):
        raise ReviewIngestError("review context missing 'threads' array")

    adapter = adapter_for_tool(tool)
    if adapter is None:
        raise ReviewIngestError(f"no adapter registered for tool '{tool}'")

    pr_ref = _pr_ref_for_read(pr)
    raw = adapter.read_findings(pr_ref, _StaticConnector(threads))
    findings = adapter.to_payload_findings(raw)
    return build_payload(pr, findings, generated_at=generated_at)


def collect_payload(
    event: dict[str, Any],
    connector: Any,
    *,
    event_name: str = "pull_request_review",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Normalize a live GitHub Actions review event into a payload.

    Raises :class:`ReviewSkipped` when the event carries no PR or no recognized
    review tool (a clean skip), and :class:`ReviewIngestError` when a tool *is*
    recognized but its data cannot be normalized (fail closed).
    """
    if not isinstance(event, dict):
        raise ReviewIngestError("event payload must be a JSON object")
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        raise ReviewSkipped("event carries no pull_request")

    tool = detect_tool(event_name, event)
    if tool is None:
        raise ReviewSkipped("no recognized review tool attributed to this event")
    adapter = adapter_for_tool(tool)
    if adapter is None:
        raise ReviewSkipped(f"no adapter registered for tool '{tool}'")

    pr_block = _pr_block_from_event(event, pr)
    pr_ref = _pr_ref_for_read(pr_block)
    raw = adapter.read_findings(pr_ref, connector)
    findings = adapter.to_payload_findings(raw)
    return build_payload(pr_block, findings, generated_at=generated_at)


def _pr_block_from_event(event: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any]:
    """Extract the canonical ``pr`` block from a GitHub event's pull_request."""
    repo = event.get("repository") if isinstance(event.get("repository"), dict) else {}
    labels = [
        label["name"]
        for label in pr.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    ]
    block: dict[str, Any] = {
        "repo_owner": _nested(repo, "owner", "login") or _nested(pr, "base", "repo", "owner", "login"),
        "repo_name": repo.get("name") if isinstance(repo, dict) else None,
        "pr_number": pr.get("number"),
        "title": pr.get("title"),
        "head_branch": _nested(pr, "head", "ref"),
        "base_branch": _nested(pr, "base", "ref"),
        "head_sha": _nested(pr, "head", "sha"),
        "author": _nested(pr, "user", "login"),
        "is_draft": bool(pr.get("draft", False)),
        "labels": labels,
    }
    # Drop keys that came back None so build_payload reports precise missing fields.
    return {key: value for key, value in block.items() if value is not None}


def _pr_ref_for_read(pr: dict[str, Any]) -> PRRef:
    """A minimal PRRef for adapter.read_findings (only owner/repo/number are used)."""
    return PRRef(
        repo_owner=str(pr.get("repo_owner", "")),
        repo_name=str(pr.get("repo_name", "")),
        pr_number=int(pr.get("pr_number", 0) or 0),
        title=str(pr.get("title", "")),
        head_branch=str(pr.get("head_branch", "") or "unknown"),
        base_branch=str(pr.get("base_branch", "") or "unknown"),
        head_sha=str(pr.get("head_sha", "") or "unknown"),
        is_draft=bool(pr.get("is_draft", False)),
        author=str(pr.get("author", "") or "unknown"),
        labels=list(pr.get("labels", [])),
    )


def _validate_payload(payload: dict[str, Any]) -> None:
    """Validate against the canonical schema; raise on the first violation."""
    try:
        schema = json.loads(Path(SCHEMA_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewIngestError(f"unable to load payload schema at {SCHEMA_PATH}: {exc}") from exc
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise ReviewIngestError(f"payload failed schema validation at '{location}': {first.message}")


def _load_json(path: str) -> Any:
    file_path = _safe_path(path)
    if not file_path.exists():
        raise ReviewIngestError(f"input file not found: {path}")
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewIngestError(f"input file {path} is not valid JSON: {exc}") from exc


def _write_payload(output: str, payload: dict[str, Any]) -> None:
    out_path = _safe_path(output)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run(
    *,
    output: str,
    context: str | None = None,
    event_path: str | None = None,
    event_name: str = "pull_request_review",
    generated_at: str | None = None,
    connector_factory: Callable[[str], Any] = GitHubConnector,
) -> int:
    """Orchestrate one ingestion; return the workflow-facing exit code.

    Never raises for the normal skip/fail cases — those map to exit codes so the
    caller (CLI or workflow) can branch deterministically.
    """
    if generated_at is None:
        generated_at = datetime.now(UTC).isoformat()

    try:
        if context is not None:
            payload = payload_from_context(_load_json_dict(context), generated_at=generated_at)
        elif event_path is not None:
            event = _load_json_dict(event_path)
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                raise ReviewIngestError("GITHUB_TOKEN is required for live (--event-path) ingestion")
            connector = connector_factory(token)
            payload = collect_payload(
                event, connector, event_name=event_name, generated_at=generated_at
            )
        else:
            raise ReviewIngestError("one of --context or --event-path is required")
        _validate_payload(payload)
    except ReviewSkipped as exc:
        print(f"[ingest-review] skipped: {exc}", file=sys.stderr)
        return EXIT_SKIPPED
    except ReviewIngestError as exc:
        print(f"[ingest-review] error: {exc}", file=sys.stderr)
        return EXIT_FAILED

    _write_payload(output, payload)
    # Log counts + path only — never review bodies (may quote secrets).
    print(
        f"[ingest-review] wrote {output}: "
        f"{len(payload['autofix_candidates'])} autofix candidate(s), "
        f"{len(payload['manual_review_required'])} manual finding(s)",
        file=sys.stderr,
    )
    return EXIT_PRODUCED


def _load_json_dict(path: str) -> dict[str, Any]:
    loaded = _load_json(path)
    if not isinstance(loaded, dict):
        raise ReviewIngestError(f"input file {path} must contain a JSON object")
    return loaded


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-repair ingest-review",
        description="Normalize a PR review into agent_review_payload.json.",
    )
    parser.add_argument("--output", required=True, help="Path to write agent_review_payload.json.")
    parser.add_argument("--context", default=None, help="Captured review-context JSON (offline mode).")
    parser.add_argument("--event-path", default=None, help="GitHub Actions event JSON (live mode).")
    parser.add_argument(
        "--event-name",
        default=os.getenv("GITHUB_EVENT_NAME", "pull_request_review"),
        help="GitHub event name (default: $GITHUB_EVENT_NAME or pull_request_review).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(
        output=args.output,
        context=args.context,
        event_path=args.event_path,
        event_name=args.event_name,
    )


if __name__ == "__main__":
    raise SystemExit(main())
