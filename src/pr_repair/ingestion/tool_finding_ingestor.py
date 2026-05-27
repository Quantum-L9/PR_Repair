from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pr_repair.config import AppConfig
from pr_repair.connectors.codecov_cloud import CodecovCloudConnector
from pr_repair.connectors.coderabbit import CodeRabbitConnector
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


def ingest_tool_findings(
    config: AppConfig,
    pr: PRRef,
    github_connector: GitHubConnector | None = None,
    coderabbit_connector: CodeRabbitConnector | None = None,
    codecov_connector: CodecovCloudConnector | None = None,
    state_store: StateStore | None = None,
) -> FindingBundle:
    """
    Ingest CodeRabbit, Codecov, and GitHub check findings in strict priority order.

    The function persists raw payloads before producing typed findings so later
    phases can inspect source truth without re-hitting APIs.
    """
    github = github_connector or GitHubConnector(config.github_token)
    coderabbit = coderabbit_connector or CodeRabbitConnector(
        config.coderabbit_api_key,
        config.coderabbit_api_base_url,
    )
    codecov = codecov_connector or CodecovCloudConnector(
        config.codecov_api_key,
        config.codecov_api_base_url,
    )
    store = state_store or StateStore(config.output_dir)
    raw_dir = config.output_dir / "raw" / str(pr.pr_number)
    raw_dir.mkdir(parents=True, exist_ok=True)

    coderabbit_raw = coderabbit.get_pr_findings(pr.repo_owner, pr.repo_name, pr.pr_number)
    codecov_raw = codecov.get_pr_findings(pr.repo_owner, pr.repo_name, pr.pr_number)
    github_checks_raw = github.get_check_runs(pr.repo_owner, pr.repo_name, pr.head_sha)

    _write_raw_payload(store, raw_dir, "coderabbit.json", coderabbit_raw)
    _write_raw_payload(store, raw_dir, "codecov.json", codecov_raw)
    _write_raw_payload(store, raw_dir, "github_checks.json", github_checks_raw)

    normalization_errors: list[NormalizationError] = []
    coderabbit_findings = _normalize_external_findings(
        pr=pr,
        raw_items=coderabbit_raw,
        source_name=SourceName.coderabbit,
        fallback_category="coderabbit_style_violation",
        normalization_errors=normalization_errors,
    )
    codecov_findings = _normalize_external_findings(
        pr=pr,
        raw_items=codecov_raw,
        source_name=SourceName.codecov_cloud,
        fallback_category="codecov_patch_coverage_failure",
        normalization_errors=normalization_errors,
    )
    github_check_findings = _normalize_check_run_findings(
        pr=pr,
        raw_items=github_checks_raw,
        normalization_errors=normalization_errors,
    )

    log_event(
        "tool_findings_ingested",
        repo=pr.repo_full_name,
        pr_number=pr.pr_number,
        coderabbit_count=len(coderabbit_findings),
        codecov_count=len(codecov_findings),
        github_check_count=len(github_check_findings),
        normalization_errors=len(normalization_errors),
    )

    return FindingBundle(
        pr_ref=pr,
        coderabbit_findings=coderabbit_findings,
        codecov_findings=codecov_findings,
        github_check_findings=github_check_findings,
        github_comment_findings=[],
        normalization_errors=normalization_errors,
        merged_findings=[],
    )


def _write_raw_payload(store: StateStore, raw_dir: Path, name: str, payload: Any) -> None:
    # StateStore owns error handling and deterministic formatting.
    relative_name = str(raw_dir.relative_to(store._artifact_dir) / name)  # type: ignore[attr-defined]
    store.write_json(relative_name, payload)


def _normalize_external_findings(
    *,
    pr: PRRef,
    raw_items: list[dict[str, Any]],
    source_name: SourceName,
    fallback_category: str,
    normalization_errors: list[NormalizationError],
) -> list[Finding]:
    findings: list[Finding] = []
    for raw_item in raw_items:
        try:
            message = _as_message(raw_item)
            category = _as_string(raw_item.get("category")) or fallback_category
            file_path = _as_string(raw_item.get("file_path") or raw_item.get("path"))
            line_start = _as_positive_int(raw_item.get("line_start") or raw_item.get("start_line"))
            line_end = _as_positive_int(raw_item.get("line_end") or raw_item.get("end_line"))
            severity = _parse_severity(raw_item.get("severity"))
            suggested_fix = _as_string(raw_item.get("suggested_fix"))
            evidence_url = _as_string(raw_item.get("evidence_url") or raw_item.get("url"))

            finding = Finding(
                finding_id=_as_string(raw_item.get("id")) or _deterministic_id(source_name.value, message),
                pr_number=pr.pr_number,
                source_name=source_name,
                source_priority=SOURCE_PRIORITY[source_name],
                severity=severity,
                category=category,
                message=message,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                suggested_fix=suggested_fix,
                evidence_url=evidence_url,
                repairable=False,
                confidence=0.9 if source_name is SourceName.coderabbit else 0.85,
                fingerprint=_fingerprint(
                    source_name=source_name.value,
                    message=message,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                ),
                tier_impact=TierLevel.t0,
                protected_path=False,
                skip_review_path=False,
            )
            findings.append(finding)
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
    return findings


def _normalize_check_run_findings(
    *,
    pr: PRRef,
    raw_items: list[dict[str, Any]],
    normalization_errors: list[NormalizationError],
) -> list[Finding]:
    findings: list[Finding] = []
    for raw_item in raw_items:
        try:
            conclusion = _as_string(raw_item.get("conclusion")) or "unknown"
            status = _as_string(raw_item.get("status")) or "unknown"
            if conclusion == "success":
                continue

            name = _as_string(raw_item.get("name")) or "unknown-check"
            message = f"Required check failed: {name} ({status}/{conclusion})"
            findings.append(
                Finding(
                    finding_id=_as_string(raw_item.get("id")) or _deterministic_id("github_checks", message),
                    pr_number=pr.pr_number,
                    source_name=SourceName.github_checks,
                    source_priority=SOURCE_PRIORITY[SourceName.github_checks],
                    severity=Severity.high,
                    category="github_required_check_failure",
                    message=message,
                    file_path=None,
                    line_start=None,
                    line_end=None,
                    suggested_fix=None,
                    evidence_url=_as_string(raw_item.get("html_url")),
                    repairable=False,
                    confidence=0.8,
                    fingerprint=_fingerprint(
                        source_name=SourceName.github_checks.value,
                        message=message,
                        file_path=None,
                        line_start=None,
                        line_end=None,
                    ),
                    tier_impact=TierLevel.t0,
                    protected_path=False,
                    skip_review_path=False,
                )
            )
        except ValueError as exc:
            normalization_errors.append(
                NormalizationError(
                    source_name=SourceName.github_checks.value,
                    pr_number=pr.pr_number,
                    error_type="normalization_error",
                    error_message=str(exc),
                    payload_excerpt=_excerpt_payload(raw_item),
                )
            )
    return findings


def _as_message(raw_item: dict[str, Any]) -> str:
    message = (
        _as_string(raw_item.get("message"))
        or _as_string(raw_item.get("body"))
        or _as_string(raw_item.get("summary"))
    )
    if not message:
        msg = "missing required finding message"
        raise ValueError(msg)
    return message


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _as_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def _parse_severity(value: Any) -> Severity:
    text = _as_string(value) or "medium"
    normalized = text.lower()
    if normalized in {"critical", "high", "medium", "low"}:
        return Severity(normalized)
    if normalized in {"error", "failed"}:
        return Severity.high
    if normalized == "warning":
        return Severity.medium
    return Severity.medium


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
    for key in ("id", "name", "path", "file_path", "message", "summary", "severity"):
        if key in raw_item:
            excerpt[key] = raw_item[key]
    return excerpt
