"""Backup workflow primitives."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

DEFAULT_TIMEOUT = 1000
CHUNK_SIZE = 8192


class BackupError(Exception):
    """Raised when a remote backup cannot be downloaded."""


def build_backup_path(project_path: Path, database: str) -> Path:
    """Return the default local backup path for a database."""
    return project_path.parent / f"{database}.zip"


def download_remote_backup(
    remote: dict[str, Any],
    destination: Path,
    timeout: int = DEFAULT_TIMEOUT,
) -> Path:
    """Download a remote Odoo database backup as a ZIP file."""
    remote_address = str(remote["remote_address"])
    database = str(remote["dbname"])
    password = str(remote["password"])

    url = f"https://{remote_address}/web/database/backup"
    payload = {
        "master_pwd": password,
        "backup_format": "zip",
        "name": database,
    }

    try:
        response = requests.post(
            url,
            data=payload,
            stream=True,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        msg = f"Could not download backup from {remote_address}: {error}"
        raise BackupError(msg) from error

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as backup_file:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                backup_file.write(chunk)

    return destination
