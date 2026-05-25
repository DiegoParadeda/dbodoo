"""Shared utilities for neutralize sub-commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dbodoo.docker import detect_compose_command


class NeutralizeError(Exception):
    """Raised when a neutralize operation fails."""


def run_odoo_shell_script(
    project_path: Path,
    dbname: str,
    script_content: str,
) -> None:
    """Pipe a Python script to ``odoo shell`` inside the Docker Compose ``odoo`` service.

    Uses ``docker compose run --rm -T`` (no TTY) so that stdin piping works
    without the *"the input device is not a TTY"* error.  The script receives
    the standard Odoo shell ``env`` / ``self`` globals and must call
    ``env.cr.commit()`` explicitly — the shell never auto-commits.

    Args:
        project_path: Root of the Doodba project (where ``docker-compose.yml`` lives).
        dbname: Name of the local Odoo database to connect to.
        script_content: Python source code to execute in the Odoo environment.

    Raises:
        DockerError: if Docker Compose is not available.
        NeutralizeError: if ``odoo shell`` exits with a non-zero return code.
    """
    compose_cmd = detect_compose_command()  # raises DockerError if not found

    cmd = [
        *compose_cmd,
        "run",
        "--rm",
        "-T",       # disable TTY allocation — required for stdin piping
        "odoo",
        "shell",
        "-d",
        dbname,
    ]

    result = subprocess.run(
        cmd,
        input=script_content,
        text=True,
        encoding="utf-8",
        cwd=project_path,
    )

    if result.returncode != 0:
        msg = (
            f"odoo shell exited with code {result.returncode}. "
            "Check the Docker Compose output above for details.\n"
            "Make sure the database exists and the odoo service is configured."
        )
        raise NeutralizeError(msg)
