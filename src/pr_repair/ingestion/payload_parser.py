# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [ingestion]
# tags: [payload, deterministic, agent-review, contract]
# owner: platform
# status: active
# --- /L9_META ---

"""Deterministic ingestion for the canonical agent_review_payload.json contract.

This module is the single source of truth for how the Implementer Bot learns
what to fix. It replaces the legacy third-party review scrapers and comment
ingestion. Findings arrive pre-clustered and pre-deduplicated from the upstream
Audit Bot, split into deterministic ``autofix_candidates`` and
``manual_review_required`` buckets, and are validated against a versioned JSON
Schema before any repair is attempted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import BaseModel, Field

from pr_repair.errors import PayloadIngestionError
from pr_repair.normalization.fingerprint import build_finding_fingerprint
from pr_repair.priorities import SOURCE_PRIORITY
from pr_repair.types import (
    Finding,
    FindingBundle,
    PRRef,
    ReviewDisposition,
    Severity,
    SourceName,
)

DEFAULT_PAYLOAD_PATH = Path("artifacts/agent_review_payload.json")
SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "agent-review-payload.schema.json"
)


class ParsedPayload(BaseModel):
    """Structured, validated result of parsing agent_review_payload.json."""

    schema_version: str
    pr_ref: PRRef
    autofix_findings: list[Finding] = Field(default_factory=list)
    manual_review_findings: list[Finding] = Field(default_factory=list)

    @property
    def findings(self) -> list[Finding]:
        """All findings, autofix candidates first (highest determinism)."""
        return [*self.autofix_findings, *self.manual_review_findings]

    def to_bundle(self) -> FindingBundle:
        return FindingBundle(
            pr_ref=self.pr_ref,
            agent_review_findings=self.findings,
            merged_findings=self.findings,
        )


class PayloadParser:
    """Load, validate, and parse the canonical agent review payload.

    The parser fails closed: any missing file, malformed JSON, or schema
    violation raises :class:`PayloadIngestionError` rather than returning a
    partial or guessed result.
    """

    def __init__(
        self,
        payload_path: Path | str | None = None,
        schema_path: Path | str | None = None,
    ) -> None:
        self.payload_path = Path(payload_path) if payload_path is not None else DEFAULT_PAYLOAD_PATH
        self.schema_path = Path(schema_path) if schema_path is not None else SCHEMA_PATH

    def parse(self) -> ParsedPayload:
        raw = self._load_payload()
        self._validate(raw)
        pr_ref = self._build_pr_ref(raw["pr"])
        autofix = [
            self._to_finding(item, pr_ref, disposition=ReviewDisposition.autofix)
            for item in raw["autofix_candidates"]
        ]
        manual = [
            self._to_finding(item, pr_ref, disposition=ReviewDisposition.manual_review)
            for item in raw["manual_review_required"]
        ]
        return ParsedPayload(
            schema_version=str(raw["schema_version"]),
            pr_ref=pr_ref,
            autofix_findings=autofix,
            manual_review_findings=manual,
        )

    # -- loading & validation ------------------------------------------------

    def _load_payload(self) -> dict[str, Any]:
        if not self.payload_path.exists():
            msg = f"agent review payload not found at {self.payload_path}"
            raise PayloadIngestionError(msg)
        try:
            text = self.payload_path.read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"unable to read agent review payload at {self.payload_path}: {exc}"
            raise PayloadIngestionError(msg) from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            msg = f"agent review payload at {self.payload_path} is not valid JSON: {exc}"
            raise PayloadIngestionError(msg) from exc
        if not isinstance(parsed, dict):
            msg = "agent review payload must be a JSON object"
            raise PayloadIngestionError(msg)
        return parsed

    def _load_schema(self) -> dict[str, Any]:
        try:
            schema_text = self.schema_path.read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"unable to read payload schema at {self.schema_path}: {exc}"
            raise PayloadIngestionError(msg) from exc
        try:
            loaded = json.loads(schema_text)
        except json.JSONDecodeError as exc:
            msg = f"payload schema at {self.schema_path} is not valid JSON: {exc}"
            raise PayloadIngestionError(msg) from exc
        if not isinstance(loaded, dict):
            msg = f"payload schema at {self.schema_path} must be a JSON object"
            raise PayloadIngestionError(msg)
        return loaded

    def _validate(self, raw: dict[str, Any]) -> None:
        schema = self._load_schema()
        try:
            jsonschema.Draft202012Validator.check_schema(schema)
        except jsonschema.exceptions.SchemaError as exc:
            msg = f"payload schema at {self.schema_path} is not a valid JSON Schema: {exc}"
            raise PayloadIngestionError(msg) from exc
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(raw), key=lambda err: list(err.absolute_path))
        if errors:
            first = errors[0]
            location = "/".join(str(part) for part in first.absolute_path) or "<root>"
            msg = (
                f"agent review payload failed schema validation at '{location}': "
                f"{first.message}"
            )
            raise PayloadIngestionError(msg)

    # -- parsing -------------------------------------------------------------

    def _build_pr_ref(self, raw_pr: dict[str, Any]) -> PRRef:
        return PRRef(
            repo_owner=str(raw_pr["repo_owner"]),
            repo_name=str(raw_pr["repo_name"]),
            pr_number=int(raw_pr["pr_number"]),
            title=str(raw_pr["title"]),
            head_branch=str(raw_pr["head_branch"]),
            base_branch=str(raw_pr["base_branch"]),
            head_sha=str(raw_pr["head_sha"]),
            is_draft=bool(raw_pr.get("is_draft", False)),
            author=str(raw_pr["author"]),
            labels=list(raw_pr.get("labels", [])),
            changed_files=list(raw_pr.get("changed_files", [])),
        )

    def _to_finding(
        self,
        item: dict[str, Any],
        pr_ref: PRRef,
        *,
        disposition: ReviewDisposition,
    ) -> Finding:
        is_autofix = disposition is ReviewDisposition.autofix
        confidence = item.get("confidence")
        finding = Finding(
            finding_id=str(item["finding_id"]),
            pr_number=pr_ref.pr_number,
            source_name=SourceName.agent_review,
            source_priority=SOURCE_PRIORITY[SourceName.agent_review],
            severity=Severity(item["severity"]),
            category=str(item["category"]),
            message=str(item["message"]),
            file_path=item.get("file_path"),
            line_start=item.get("line_start"),
            line_end=item.get("line_end"),
            suggested_fix=item.get("suggested_fix"),
            replacement_text=item.get("replacement_text"),
            rule_id=item.get("rule_id"),
            review_disposition=disposition,
            evidence_url=item.get("evidence_url"),
            tags=list(item.get("tags", [])),
            tool=item.get("tool"),
            thread_id=item.get("thread_id"),
            comment_id=item.get("comment_id"),
            repairable=is_autofix,
            confidence=float(confidence) if confidence is not None else (1.0 if is_autofix else 0.7),
            fingerprint="pending",
        )
        return finding.model_copy(update={"fingerprint": build_finding_fingerprint(finding)})


def parse_payload(payload_path: Path | str | None = None) -> ParsedPayload:
    """Convenience wrapper for the common single-call parse path."""
    return PayloadParser(payload_path).parse()
