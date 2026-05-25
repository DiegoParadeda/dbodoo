"""Restore workflow primitives."""

from __future__ import annotations

from pathlib import Path

from dbodoo.backup import build_backup_path


class RestoreError(Exception):
    """Raised when a local restore cannot be performed."""


def validate_backup_file(path: Path) -> Path:
    """Return a resolved backup path if it exists."""
    backup_path = path.expanduser().resolve()
    if not backup_path.is_file():
        msg = f"Backup file not found: {backup_path}"
        raise FileNotFoundError(msg)
    return backup_path


def locate_backup(project_path: Path, database: str) -> Path:
    """Return the expected backup ZIP path, raising RestoreError if missing.

    The expected location is ``<project_path>/../<database>.zip``, which is
    the same path that :func:`~dbodoo.backup.build_backup_path` writes to.

    Args:
        project_path: Root of the Doodba project.
        database: Name of the Odoo database whose backup to locate.

    Raises:
        RestoreError: if the ZIP file does not exist at the expected path.
    """
    backup_path = build_backup_path(project_path, database)
    if not backup_path.is_file():
        msg = (
            f"Backup ZIP not found at {backup_path}. "
            "Run [cyan]dbodoo remote -b[/cyan] first to download it."
        )
        raise RestoreError(msg)
    return backup_path
