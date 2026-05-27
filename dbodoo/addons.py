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
    db: str = "devel",
    stop_after_init: bool = True,
) -> None:
    """Install or update specific Odoo addons via docker compose.

    Stops the odoo container first, then runs the ``odoo`` binary directly
    inside the container — equivalent to:

    .. code-block:: bash

        docker compose run --rm odoo odoo {-i|-u} modules -d db --stop-after-init

    Args:
        project_path: Root of the Doodba project (where docker-compose.yml is).
        modules: Comma-separated list of addon names, e.g. ``"sale,stock"``.
        mode: ``"init"`` to install (``-i``), ``"update"`` to update (``-u``).
        db: Database name (default: ``"devel"``).
        stop_after_init: Pass ``--stop-after-init`` to prevent Odoo from
            starting as a server after the operation (default: ``True``).

    Raises:
        DockerError: if Docker Compose is not available.
        AddonsError: if the odoo command exits with a non-zero code.
    """
    compose_cmd = detect_compose_command()
    _stop_odoo(compose_cmd, project_path)

    flag = "-i" if mode == "init" else "-u"
    verb = "Installing" if mode == "init" else "Updating"
    console.print(
        f"{verb} [bold cyan]{modules}[/bold cyan] "
        f"on database [cyan]{db}[/cyan]…"
    )

    cmd: list[str] = [
        *compose_cmd,
        "run", "--rm",
        "odoo",
        "odoo",
        flag, modules,
        "-d", db,
    ]
    if stop_after_init:
        cmd.append("--stop-after-init")

    result = subprocess.run(cmd, cwd=project_path, env=_uid_env())
    if result.returncode != 0:
        action = "install" if mode == "init" else "update"
        msg = (
            f"odoo {action} exited with code {result.returncode}. "
            "Check the Docker Compose output above for details."
        )
        raise AddonsError(msg)
