"""Restore workflow primitives."""

from __future__ import annotations

from pathlib import Path


def validate_backup_file(path: Path) -> Path:
    """Return a resolved backup path if it exists."""
    backup_path = path.expanduser().resolve()
    if not backup_path.is_file():
        msg = f"Backup file not found: {backup_path}"
        raise FileNotFoundError(msg)
    return backup_path
