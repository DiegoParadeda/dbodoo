"""Remote database workflows (orchestration layer)."""

from __future__ import annotations

from pathlib import Path

from dbodoo.backup import build_backup_path, download_remote_backup
from dbodoo.config import (
    BACKUP_REMOTE_FIELDS,
    RESTORE_REMOTE_FIELDS,
    ProjectConfig,
    detect_doodba,
    validate_remote,
)
from dbodoo.docker import DockerError, restore_database
from dbodoo.restore import RestoreError, locate_backup


def backup_remote(project_config: ProjectConfig, remote_name: str) -> Path:
    """Validate and download a remote database backup.

    Args:
        project_config: Loaded project configuration.
        remote_name: Key of the remote to back up.

    Returns:
        Path to the downloaded ZIP file.
    """
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


def restore_remote(
    project_config: ProjectConfig,
    remote_name: str,
    destination_db: str = "devel",
) -> Path:
    """Locate a previously downloaded backup ZIP and restore it locally.

    The ZIP is expected at ``<project_path>/../<dbname>.zip`` — the same
    location where :func:`backup_remote` writes it.  Only *dbname* is
    required in the remote config; credentials are not needed for restore.

    Args:
        project_config: Loaded project configuration.
        remote_name: Key of the remote whose backup to restore.
        destination_db: Name of the local database to restore into.

    Returns:
        Path to the backup ZIP that was restored.
    """
    remote = validate_remote(
        remote_name,
        project_config.remotes[remote_name],
        RESTORE_REMOTE_FIELDS,
    )
    database = str(remote["dbname"])
    backup_path = locate_backup(project_config.project_path, database)
    doodba = detect_doodba(project_config.project_path)
    restore_database(
        project_config.project_path,
        backup_path,
        destination_db=destination_db,
        doodba=doodba,
    )
    return backup_path


def backup_and_restore_remote(
    project_config: ProjectConfig,
    remote_name: str,
    destination_db: str = "devel",
) -> Path:
    """Download a remote backup and immediately restore it locally.

    Runs :func:`backup_remote` first; if it fails the restore is never
    attempted.  This avoids restoring a stale or partial ZIP.

    Args:
        project_config: Loaded project configuration.
        remote_name: Key of the remote to use.
        destination_db: Name of the local database to restore into.

    Returns:
        Path to the backup ZIP that was downloaded and restored.
    """
    backup_path = backup_remote(project_config, remote_name)

    doodba = detect_doodba(project_config.project_path)
    restore_database(
        project_config.project_path,
        backup_path,
        destination_db=destination_db,
        doodba=doodba,
    )
    return backup_path
