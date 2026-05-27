"""Rollback boundary for governed repair execution.

This module exposes the validated rollback primitive implemented by the
workspace git operations layer. It does not add new behavior; it makes the
rollback layer explicit in the canonical package structure.
"""

from pr_repair.workspace.git_ops import rollback_to_backup

__all__ = ["rollback_to_backup"]
