from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pr_repair.config import AppConfig
from pr_repair.connectors.github import GitHubConnector
from pr_repair.logging import log_event
from pr_repair.priorities import SOURCE_PRIORITY
from pr_repair.state_store import StateStore
from pr_repair.types import (
    Finding,
    FindingBundle,
    NormalizationError,
    PRRef,
    Severity,
    SourceName,
    TierLevel,
)


def ingest_comment_findings(
    config: AppConfig,
    pr: PRRef,
    bundle: FindingBundle,
    github_connector: GitHubConnector | None = None,
    state_store: StateStore | None = None,
) -> FindingBundle:
    """
    Append GitHub review and issue comment findings only after tool findings exist.

    CodeRabbit-authored comments are ignored here to preserve the source-priority
    contract and avoid duplicating tool-originated findings.
    """
    if bundle.pr_ref.pr_number != pr.pr_number:
        msg = "bundle PR does not match requested PR"
        raise ValueError(msg)

    github = github_connector or GitHubConnector(config.github_token)
    store = state_store or StateStore(config.output_dir)
    raw_dir = config.output_dir / "raw" / str(pr.pr_number)
    raw_dir.mkdir(parents=True, exist_ok=True)

    review_comments_raw = github.get_review_comments(pr.repo_owner, pr.repo_name, pr.pr_number)
    issue_comments_raw = github.get_issue_comments(pr.repo_owner, pr.repo_name, pr.pr_number)

    _write_raw_payload(store, raw_dir, "github_review_comments.json", review_comments_raw)
    _write_raw_payload(store, raw_dir, "github_issue_comments.json", issue_comments_raw)

    normalization_errors = list(bundle.normalization_errors)
    findings: list[Finding] = list(bundle.github_comment_findings)

    for raw_item in review_comments_raw:
        if _is_coderabbit_comment(raw_item):
            continue
        finding = _normalize_comment(
            pr=pr,
            raw_item=raw_item,
            source_name=SourceName.github_review_comments,
            normalization_errors=normalization_errors,
        )
        if finding is not None:
            findings.append(finding)

    for raw_item in issue_comments_raw:
        if _is_coderabbit_comment(raw_item):
            continue
        finding = _normalize_comment(
            pr=pr,
            raw_item=raw_item,
            source_name=SourceName.github_issue_comments,
            normalization_errors=normalization_errors,
        )
        if finding is not None:
            findings.append(finding)

    log_event(
        "comment_findings_ingested",
        repo=pr.repo_full_name,
        pr_number=pr.pr_number,
        count=len(findings),
        skipped_coderabbit_duplicates=True,
    )

    return bundle.model_copy(
        update={
            "github_comment_findings": findings,
            "normalization_errors": normalization_errors,
        }
    )


def _write_raw_payload(store: StateStore, raw_dir: Path, name: str, payload: Any) -> None:
    relative_name = str(raw_dir.relative_to(store._artifact_dir) / name)  # type: ignore[attr-defined]
    store.write_json(relative_name, payload)


def _normalize_comment(
    *,
    pr: PRRef,
    raw_item: dict[str, Any],
    source_name: SourceName,
    normalization_errors: list[NormalizationError],
) -> Finding | None:
    try:
        body = _as_string(raw_item.get("body"))
        if not body:
            msg = "missing required comment body"
            raise ValueError(msg)
        path = _as_string(raw_item.get("path"))
        line = _as_positive_int(raw_item.get("line"))
        finding_id = _as_string(raw_item.get("id")) or _deterministic_id(source_name.value, body)
        return Finding(
            finding_id=finding_id,
            pr_number=pr.pr_number,
            source_name=source_name,
            source_priority=SOURCE_PRIORITY[source_name],
            severity=Severity.medium,
            category="ambiguous_comment",
            message=body,
            file_path=path,
            line_start=line,
            line_end=line,
            suggested_fix=None,
            evidence_url=_as_string(raw_item.get("html_url")),
            repairable=False,
            confidence=0.55,
            fingerprint=_fingerprint(
                source_name=source_name.value,
                message=body,
                file_path=path,
                line_start=line,
                line_end=line,
            ),
            tier_impact=TierLevel.t0,
            protected_path=False,
            skip_review_path=False,
        )
    except ValueError as exc:
        normalization_errors.append(
            NormalizationError(
                source_name=source_name.value,
                pr_number=pr.pr_number,
                error_type="normalization_error",
                error_message=str(exc),
                payload_excerpt=_excerpt_payload(raw_item),
            )
        )
        return None


def _is_coderabbit_comment(raw_item: dict[str, Any]) -> bool:
    user = raw_item.get("user", {})
    login = _as_string(user.get("login")) or ""
    body = _as_string(raw_item.get("body")) or ""
    lowered_login = login.lower()
    lowered_body = body.lower()
    return "coderabbit" in lowered_login or "coderabbit" in lowered_body


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, int):
        return str(value)
    return None


def _as_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def _deterministic_id(prefix: str, message: str) -> str:
    digest = hashlib.sha256(f"{prefix}:{message}".encode("utf-8")).hexdigest()
    return digest[:16]


def _fingerprint(
    *,
    source_name: str,
    message: str,
    file_path: str | None,
    line_start: int | None,
    line_end: int | None,
) -> str:
    payload = json.dumps(
        {
            "source_name": source_name,
            "message": message,
            "file_path": file_path,
            "line_start": line_start,
            "line_end": line_end,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _excerpt_payload(raw_item: dict[str, Any]) -> dict[str, Any]:
    excerpt: dict[str, Any] = {}
    for key in ("id", "path", "body", "line", "html_url"):
        if key in raw_item:
            excerpt[key] = raw_item[key]
    return excerpt
