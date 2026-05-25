"""Command-line interface for dbodoo."""

from __future__ import annotations

from pathlib import Path

import typer

from dbodoo import __version__
from dbodoo.backup import BackupError
from dbodoo.config import (
    ConfigError,
    RemotesFileNotFoundError,
    build_remote_config,
    load_project_config,
    write_remotes,
)
from dbodoo.remote import backup_remote
from dbodoo.ui import (
    SelectionCancelledError,
    ask_remote_config,
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
        help="Remote name to write without prompting.",
    ),
    dbname: str | None = typer.Option(
        None,
        "--dbname",
        help="Database name to write without prompting.",
    ),
    remote_address: str | None = typer.Option(
        None,
        "--remote-address",
        help="Remote URL/address. Optional for restore-only configs.",
    ),
    password: str | None = typer.Option(
        None,
        "--password",
        help="Remote master password. Optional for restore-only configs.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing .remotes.json.",
    ),
) -> None:
    """Create a local .remotes.json file."""
    project_path: Path = current_project_path()

    try:
        if name is None or dbname is None:
            answers = ask_remote_config()
            name = answers.name
            dbname = answers.dbname
            remote_address = remote_address or answers.remote_address
            password = password or answers.password

        remote = build_remote_config(
            dbname=dbname,
            remote_address=remote_address,
            password=password,
        )
        remotes_path = write_remotes(
            project_path,
            {name: remote},
            overwrite=force,
        )
    except (ConfigError, ValueError) as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Configuration wizard cancelled")
        raise typer.Exit(code=1) from error

    console.print(f"Created {remotes_path}")


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
        error_console.print("Remote selection cancelled")
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
) -> None:
    """Run remote database workflows."""
    if not backup:
        error_console.print("[bold red]Error:[/bold red] choose an operation, e.g. -b")
        raise typer.Exit(code=1)

    project_path: Path = current_project_path()

    try:
        project_config = load_project_config(project_path)
        selected = choose_remote_name(project_config.remotes)
        backup_path = backup_remote(project_config, selected)
    except RemotesFileNotFoundError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        error_console.print("Run [cyan]dbodoo init[/cyan] to create .remotes.json.")
        raise typer.Exit(code=1) from error
    except ConfigError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        error_console.print("Update .remotes.json with the fields required by backup.")
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Remote selection cancelled")
        raise typer.Exit(code=1) from error
    except BackupError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    console.print(f"Backup saved to {backup_path}")


if __name__ == "__main__":
    app()
