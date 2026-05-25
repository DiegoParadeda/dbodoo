"""Command-line interface for dbodoo."""

from __future__ import annotations

from pathlib import Path

import typer

from dbodoo import __version__
from dbodoo.config import ConfigError, load_project_config
from dbodoo.ui import SelectionCancelledError, choose_remote_name, console, error_console
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


if __name__ == "__main__":
    app()
