"""Backup workflow primitives."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from dbodoo.ui import console

DEFAULT_TIMEOUT = 1000  # seconds — large databases can take a while
CHUNK_SIZE = 8192


class BackupFormat(str, Enum):
    """Odoo backup formats accepted by /web/database/backup.

    zip  — full backup: SQL dump + filestore in a ZIP archive.
    dump — SQL-only pg_dump (no filestore); smaller and faster to transfer.
    """

    zip = "zip"
    dump = "dump"


class BackupError(Exception):
    """Raised when a remote backup cannot be downloaded."""


def build_backup_path(
    project_path: Path,
    database: str,
    backup_format: BackupFormat = BackupFormat.zip,
) -> Path:
    """Return the default local backup path for a database."""
    return project_path.parent / f"{database}.{backup_format.value}"


def _check_response_for_auth_error(response: requests.Response, remote_address: str) -> None:
    """Raise BackupError if the response looks like an authentication failure."""
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        msg = (
            f"Authentication failed for '{remote_address}'. "
            "The server returned an HTML page instead of a ZIP. "
            "Check the master password."
        )
        raise BackupError(msg)


def _make_progress() -> Progress:
    """Return a Rich Progress instance for download display."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )


def download_remote_backup(
    remote: dict[str, Any],
    destination: Path,
    backup_format: BackupFormat = BackupFormat.zip,
    timeout: int = DEFAULT_TIMEOUT,
) -> Path:
    """Download a remote Odoo database backup.

    Args:
        remote: Validated remote config dict (must contain remote_address,
                dbname, and password).
        destination: Local path where the backup file will be written.
        backup_format: ``zip`` (full backup with filestore, default) or
                       ``dump`` (SQL-only pg_dump, no filestore).
        timeout: HTTP request timeout in seconds.

    Returns:
        Path to the downloaded backup file.
    """
    remote_address = str(remote["remote_address"])
    database = str(remote["dbname"])
    password = str(remote["password"])

    url = f"https://{remote_address}/web/database/backup"
    payload = {
        "master_pwd": password,
        "backup_format": backup_format.value,
        "name": database,
    }

    console.print(
        f"Connecting to [cyan]{remote_address}[/cyan]… "
        f"(format: [bold]{backup_format.value}[/bold])"
    )

    try:
        response = requests.post(
            url,
            data=payload,
            stream=True,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        msg = f"Connection timed out after {timeout}s reaching '{remote_address}'."
        raise BackupError(msg) from None
    except requests.exceptions.ConnectionError as error:
        msg = f"Cannot connect to '{remote_address}': {error}"
        raise BackupError(msg) from error
    except requests.RequestException as error:
        msg = f"Request error from '{remote_address}': {error}"
        raise BackupError(msg) from error

    if response.status_code == 403:
        msg = f"Access denied (HTTP 403) from '{remote_address}'. Check the master password."
        raise BackupError(msg)

    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        msg = f"HTTP {response.status_code} from '{remote_address}': {error}"
        raise BackupError(msg) from error

    _check_response_for_auth_error(response, remote_address)

    filename = destination.name
    content_length = int(response.headers.get("content-length", 0)) or None
    destination.parent.mkdir(parents=True, exist_ok=True)

    with _make_progress() as progress:
        task = progress.add_task(
            f"Downloading [bold]{filename}[/bold]",
            total=content_length,
        )
        with destination.open("wb") as backup_file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    backup_file.write(chunk)
                    progress.advance(task, len(chunk))

    file_size = destination.stat().st_size
    console.print(
        f"[bold green]✓[/bold green] Downloaded [bold]{filename}[/bold] "
        f"([cyan]{_fmt_size(file_size)}[/cyan])"
    )

    return destination


def _fmt_size(n_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if n_bytes < 1024:
            return f"{n_bytes:.1f} {unit}" if unit != "B" else f"{n_bytes} B"
        n_bytes /= 1024  # type: ignore[assignment]
    return f"{n_bytes:.1f} TB"
