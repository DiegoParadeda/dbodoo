"""Docker Compose helpers for Doodba restore operations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dbodoo.config import DoodbaDetection

from dbodoo.ui import console, error_console


class DockerError(Exception):
    """Raised when a Docker Compose operation fails."""


def detect_compose_command() -> list[str]:
    """Return the docker compose command to use (v2 preferred, v1 fallback).

    Raises:
        DockerError: if neither 'docker compose' nor 'docker-compose' is available.
    """
    if shutil.which("docker"):
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return ["docker", "compose"]

    if shutil.which("docker-compose"):
        return ["docker-compose"]

    msg = (
        "Docker Compose not found. "
        "Install Docker with the Compose plugin (v2) or 'docker-compose' (v1)."
    )
    raise DockerError(msg)


def restore_database(
    project_path: Path,
    backup_path: Path,
    destination_db: str = "devel",
    doodba: DoodbaDetection | None = None,
) -> None:
    """Restore a Doodba database from a ZIP backup using click-odoo-restoredb.

    The backup file is bind-mounted into the container as read-only so that
    click-odoo-restoredb can access it without any extra volume configuration.

    Args:
        project_path: Root of the Doodba project (where docker-compose.yml lives).
        backup_path: Absolute path to the local backup ZIP.
        destination_db: Name of the database to restore into (default: 'devel').
        doodba: Optional detection result used to emit a warning when the
                project does not look like a Doodba project.
    """
    if doodba is not None and not doodba.is_doodba:
        markers = ", ".join(doodba.missing_markers)
        error_console.print(
            f"[bold yellow]Warning:[/bold yellow] This directory does not look like a "
            f"Doodba project (missing: {markers}). "
            "The Docker restore may not work as expected."
        )

    compose_cmd = detect_compose_command()
    backup_abs = backup_path.resolve()
    mount_target = f"/mnt/{backup_abs.name}"

    cmd = [
        *compose_cmd,
        "run",
        "--rm",
        "-v",
        f"{backup_abs}:{mount_target}:ro",
        "odoo",
        "click-odoo-restoredb",
        destination_db,
        mount_target,
        "--force",
    ]

    console.print(
        f"Restoring [bold]{backup_abs.name}[/bold] → "
        f"[cyan]{destination_db}[/cyan] via Docker Compose…"
    )

    result = subprocess.run(cmd, cwd=project_path)

    if result.returncode != 0:
        msg = (
            f"click-odoo-restoredb exited with code {result.returncode}. "
            "Check the Docker Compose output above for details."
        )
        raise DockerError(msg)

    console.print(f"[bold green]✓[/bold green] Database restored as [cyan]{destination_db}[/cyan].")
