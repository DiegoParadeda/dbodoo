"""Backup workflow primitives."""

from __future__ import annotations

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


class BackupError(Exception):
    """Raised when a remote backup cannot be downloaded."""


def build_backup_path(project_path: Path, database: str) -> Path:
    """Return the default local backup path for a database."""
    return project_path.parent / f"{database}.zip"


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

    console.print(f"Connecting to [cyan]{remote_address}[/cyan]…")

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

    content_length = int(response.headers.get("content-length", 0)) or None
    destination.parent.mkdir(parents=True, exist_ok=True)

    with _make_progress() as progress:
        task = progress.add_task(
            f"Downloading [bold]{database}.zip[/bold]",
            total=content_length,
        )
        with destination.open("wb") as backup_file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    backup_file.write(chunk)
                    progress.advance(task, len(chunk))

    return destination
