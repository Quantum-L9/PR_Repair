"""Rollback adapter for canonical pipeline imports."""

from pr_repair.workspace.git_ops import rollback_to_backup

__all__ = ["rollback_to_backup"]
