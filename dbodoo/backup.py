"""Backup workflow primitives."""

from __future__ import annotations

from pathlib import Path


def build_backup_path(project_path: Path, database: str) -> Path:
    """Return the default local backup path for a database."""
    return project_path / "backups" / f"{database}.zip"
