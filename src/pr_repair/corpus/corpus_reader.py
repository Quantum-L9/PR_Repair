# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [corpus, integration]
# tags: [highway, corpus, sync, input]
# owner: platform
# status: active
# --- /L9_META ---
"""Corpus Highway Reader — ingests harness policy and rules from .l9/corpus/ channels.

This module reads policy (scanner-rules, HITL matrix) and compiled rules
from the shared corpus directory, enabling PR_Repair to respect harness
governance without manual configuration.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CORPUS_DIR = ".l9/corpus"


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON file, returning None if it doesn't exist or is malformed."""
    if not path.exists():
        log.debug("corpus: %s not found, skipping", path)
        return None
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            log.warning("corpus: %s is not a JSON object, skipping", path)
            return None
        return data
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("corpus: failed to read %s: %s", path, exc)
        return None


def _read_yaml(path: Path) -> dict[str, Any] | None:
    """Read a YAML file, returning None if it doesn't exist or is malformed."""
    if not path.exists():
        log.debug("corpus: %s not found, skipping", path)
        return None
    try:
        import yaml  # noqa: PLC0415
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            log.warning("corpus: %s is not a YAML mapping, skipping", path)
            return None
        return data
    except Exception as exc:
        log.warning("corpus: failed to read %s: %s", path, exc)
        return None


def read_compiled_rules(repo_root: Path) -> list[dict[str, Any]]:
    """Read compiled rules from the rules channel.

    Returns:
        List of rule dicts conforming to compiled_rules.schema.json,
        or empty list if no rules are available.
    """
    rules_path = repo_root / CORPUS_DIR / "rules" / "compiled_rules.json"
    data = _read_json(rules_path)
    if data is None:
        return []

    rules = data.get("rules", data.get("payload", {}).get("rules", []))
    if not isinstance(rules, list):
        log.warning("corpus: rules channel has no valid rules array")
        return []

    log.info("corpus: loaded %d compiled rules from highway", len(rules))
    return rules


def read_scanner_rules(repo_root: Path) -> list[dict[str, Any]]:
    """Read scanner rules from the policy channel.

    Returns:
        List of scanner rule dicts, or empty list if unavailable.
    """
    policy_path = repo_root / CORPUS_DIR / "policy" / "scanner-rules.yaml"
    data = _read_yaml(policy_path)
    if data is None:
        return []

    rules = data.get("rules", [])
    if not isinstance(rules, list):
        return []

    log.info("corpus: loaded %d scanner rules from harness policy", len(rules))
    return rules


def read_hitl_matrix(repo_root: Path) -> dict[str, Any]:
    """Read the HITL matrix from the policy channel.

    Returns:
        HITL matrix dict with tiers and protected_paths,
        or empty dict if unavailable.
    """
    hitl_path = repo_root / CORPUS_DIR / "policy" / "hitl-matrix.yaml"
    data = _read_yaml(hitl_path)
    if data is None:
        return {}

    log.info("corpus: loaded HITL matrix with %d tiers", len(data.get("tiers", {})))
    return data


def read_protected_paths(repo_root: Path) -> list[str]:
    """Read protected paths from the HITL matrix.

    Returns:
        List of glob patterns for protected paths, or empty list.
    """
    matrix = read_hitl_matrix(repo_root)
    paths = matrix.get("protected_paths", [])
    if not isinstance(paths, list):
        return []
    return paths
