"""Remote database workflows."""

from __future__ import annotations

from pathlib import Path

from dbodoo.backup import build_backup_path, download_remote_backup
from dbodoo.config import BACKUP_REMOTE_FIELDS, ProjectConfig, validate_remote


def backup_remote(project_config: ProjectConfig, remote_name: str) -> Path:
    """Validate and download a remote database backup."""
    remote = validate_remote(
        remote_name,
        project_config.remotes[remote_name],
        BACKUP_REMOTE_FIELDS,
    )
    destination = build_backup_path(
        project_config.project_path,
        str(remote["dbname"]),
    )

    return download_remote_backup(remote, destination)
