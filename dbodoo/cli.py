"""Command-line interface for dbodoo."""

from __future__ import annotations

from pathlib import Path

import typer

from dbodoo import __version__
from dbodoo.backup import BackupError
from dbodoo.config import (
    ConfigError,
    RemotesFileExistsError,
    RemotesFileNotFoundError,
    add_remote,
    build_remote_config,
    get_remotes_file_path,
    load_project_config,
    write_remotes,
)
from dbodoo.docker import DockerError
from dbodoo.remote import backup_and_restore_remote, backup_remote, restore_remote
from dbodoo.restore import RestoreError
from dbodoo.ui import (
    MODE_BACKUP_RESTORE,
    SelectionCancelledError,
    ask_add_or_overwrite,
    ask_remote_config,
    ask_remote_mode,
    choose_remote_name,
    console,
    error_console,
)
from dbodoo.utils import current_project_path

app = typer.Typer(
    name="dbodoo",
    help="Database workflow helper for Odoo/Doodba projects.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print the package version and exit."""
    if value:
        console.print(f"dbodoo {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show the installed dbodoo version.",
    ),
) -> None:
    """Run dbodoo commands from the current project directory."""


@app.command()
def hello() -> None:
    """Show the detected project path."""
    project_path: Path = current_project_path()
    console.print("[bold green]Hello from dbodoo![/bold green]")
    console.print(f"Project path: [cyan]{project_path}[/cyan]")


@app.command()
def init(
    name: str | None = typer.Option(
        None,
        "--name",
        help="Remote name (skips the wizard).",
    ),
    dbname: str | None = typer.Option(
        None,
        "--dbname",
        help="Database name (skips the wizard).",
    ),
    remote_address: str | None = typer.Option(
        None,
        "--remote-address",
        help="Remote URL/address. Optional for restore-only configs.",
    ),
    password: str | None = typer.Option(
        None,
        "--password",
        help="Master password. Optional for restore-only configs.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing .remotes.json without asking.",
    ),
) -> None:
    """Create or update .remotes.json with an interactive wizard."""
    project_path: Path = current_project_path()

    try:
        # ── Non-interactive path (all flags provided) ──────────────────────
        if name is not None and dbname is not None:
            remote = build_remote_config(
                dbname=dbname,
                remote_address=remote_address,
                password=password,
            )
            if force:
                remotes_path = write_remotes(project_path, {name: remote}, overwrite=True)
            else:
                remotes_path = add_remote(project_path, name, remote)
            console.print(f"[bold green]✓[/bold green] Saved {remotes_path}")
            return

        # ── Interactive path ───────────────────────────────────────────────
        remotes_file = get_remotes_file_path(project_path)
        file_exists = remotes_file.exists()

        action: str
        if file_exists and not force:
            action = ask_add_or_overwrite()
        elif force:
            action = "overwrite"
        else:
            action = "create"

        mode = ask_remote_mode()
        answers = ask_remote_config(mode=mode)
        remote = build_remote_config(
            dbname=answers.dbname,
            remote_address=answers.remote_address,
            password=answers.password,
        )

        if action == "overwrite":
            remotes_path = write_remotes(
                project_path,
                {answers.name: remote},
                overwrite=True,
            )
        else:
            # "add" or "create"
            remotes_path = add_remote(
                project_path,
                answers.name,
                remote,
                overwrite_existing_name=False,
            )

    except (ConfigError, ValueError) as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Configuration wizard cancelled.")
        raise typer.Exit(code=1) from error

    verb = "Updated" if file_exists else "Created"
    console.print(f"[bold green]✓[/bold green] {verb} {remotes_path}")


@app.command()
def choose() -> None:
    """Choose a remote from .remotes.json."""
    project_path: Path = current_project_path()

    try:
        project_config = load_project_config(project_path)
        selected = choose_remote_name(project_config.remotes)
    except ConfigError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Remote selection cancelled.")
        raise typer.Exit(code=1) from error

    console.print(selected)


@app.command()
def remote(
    backup: bool = typer.Option(
        False,
        "--backup",
        "-b",
        help="Download a remote database backup ZIP.",
    ),
    restore: bool = typer.Option(
        False,
        "--restore",
        "-r",
        help="Restore a previously downloaded backup into the local Doodba database.",
    ),
    destination_db: str = typer.Option(
        "devel",
        "--destination-db",
        "-d",
        help="Local database name to restore into (default: devel).",
    ),
) -> None:
    """Run remote database workflows.

    \b
    Examples:
      dbodoo remote -b          Download backup from remote
      dbodoo remote -r          Restore last downloaded backup
      dbodoo remote -b -r       Download backup and restore in one step
    """
    do_backup = backup
    do_restore = restore
    do_both = do_backup and do_restore

    if not do_backup and not do_restore:
        error_console.print(
            "[bold red]Error:[/bold red] Choose an operation: "
            "[cyan]-b[/cyan] (backup), [cyan]-r[/cyan] (restore), "
            "or [cyan]-b -r[/cyan] (both)."
        )
        raise typer.Exit(code=1)

    project_path: Path = current_project_path()

    try:
        project_config = load_project_config(project_path)
        selected = choose_remote_name(project_config.remotes)

        if do_both:
            backup_path = backup_and_restore_remote(
                project_config,
                selected,
                destination_db=destination_db,
            )
            console.print(f"[bold green]✓[/bold green] Backup + restore complete. ZIP: {backup_path}")

        elif do_backup:
            backup_path = backup_remote(project_config, selected)
            console.print(f"[bold green]✓[/bold green] Backup saved to {backup_path}")

        else:  # restore only
            backup_path = restore_remote(
                project_config,
                selected,
                destination_db=destination_db,
            )
            console.print(
                f"[bold green]✓[/bold green] Restored {backup_path.name} "
                f"→ [cyan]{destination_db}[/cyan]"
            )

    except RemotesFileNotFoundError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        error_console.print("Run [cyan]dbodoo init[/cyan] to create .remotes.json.")
        raise typer.Exit(code=1) from error
    except ConfigError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        error_console.print(
            "Update .remotes.json with the fields required for this operation."
        )
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Remote selection cancelled.")
        raise typer.Exit(code=1) from error
    except BackupError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except RestoreError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except DockerError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error


if __name__ == "__main__":
    app()
