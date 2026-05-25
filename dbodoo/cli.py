"""Command-line interface for dbodoo."""

from __future__ import annotations

from pathlib import Path

import typer

from dbodoo import __version__
from dbodoo.ui import console
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


if __name__ == "__main__":
    app()
