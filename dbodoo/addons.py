"""Odoo addon install and update operations via Docker Compose."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dbodoo.docker import detect_compose_command
from dbodoo.ui import console, error_console


class AddonsError(Exception):
    """Raised when an addon install/update operation fails."""


def _uid_env() -> dict[str, str]:
    """Return the UID/GID environment variables that doodba containers expect.

    Mirrors the ``UID_ENV`` dict from invoke/tasks.py so that files written
    inside the container are owned by the correct host user.
    """
    gid = str(os.environ.get("DOODBA_GID", os.getgid()))
    uid = str(os.environ.get("DOODBA_UID", os.getuid()))
    return {
        **os.environ,  # pass the full environment through
        "GID": gid,
        "UID": uid,
        "DOODBA_UMASK": os.environ.get("DOODBA_UMASK", "27"),
        "DOODBA_GITAGGREGATE_GID": os.environ.get("DOODBA_GITAGGREGATE_GID", gid),
        "DOODBA_GITAGGREGATE_UID": os.environ.get("DOODBA_GITAGGREGATE_UID", uid),
    }


def _stop_odoo(compose_cmd: list[str], project_path: Path) -> None:
    """Stop the odoo container before an install/update run.

    Non-fatal: if the container is already stopped the command exits 0 anyway.
    Output is suppressed so only our own messages are shown.
    """
    console.print("Stopping [bold]odoo[/bold]…")
    subprocess.run(
        [*compose_cmd, "stop", "odoo"],
        cwd=project_path,
        capture_output=True,
    )


def run_addons(
    project_path: Path,
    modules: str,
    mode: str,
    *,
    db: str | None = None,
) -> None:
    """Install or update specific Odoo addons via docker compose.

    Stops the odoo container first, then runs ``addons {mode}`` from
    click-odoo-contrib inside the container.  The database is inferred from
    the container's own ``odoo.conf`` (same behaviour as invoke's install
    task); pass *db* to override explicitly.

    Args:
        project_path: Root of the Doodba project (where docker-compose.yml is).
        modules: Comma-separated list of addon names, e.g. ``"sale,stock"``.
        mode: ``"init"`` to install, ``"update"`` to update.
        db: Database name.  When *None* the container default is used.

    Raises:
        DockerError: if Docker Compose is not available.
        AddonsError: if the ``addons`` command exits with a non-zero code.
    """
    compose_cmd = detect_compose_command()
    _stop_odoo(compose_cmd, project_path)

    verb = "Installing" if mode == "init" else "Updating"
    db_label = f" on [cyan]{db}[/cyan]" if db else ""
    console.print(f"{verb} [bold cyan]{modules}[/bold cyan]{db_label}…")

    cmd: list[str] = [
        *compose_cmd,
        "run", "--rm",
        "odoo",
        "addons", mode,
        "-w", modules,
    ]
    if db:
        cmd.extend(["-d", db])

    result = subprocess.run(cmd, cwd=project_path, env=_uid_env())
    if result.returncode != 0:
        action = "install" if mode == "init" else "update"
        msg = (
            f"addons {action} exited with code {result.returncode}. "
            "Check the Docker Compose output above for details."
        )
        raise AddonsError(msg)
