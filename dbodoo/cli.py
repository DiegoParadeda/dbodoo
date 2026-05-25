"""Command-line interface for dbodoo."""

from __future__ import annotations

from pathlib import Path

import typer

from dbodoo import __version__
from dbodoo.backup import BackupError
from dbodoo.config import (
    ConfigError,
    RemotesFileNotFoundError,
    ProjectConfig,
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
    MODE_BACKUP_ONLY,
    MODE_BACKUP_RESTORE,
    MODE_LABELS,
    MODE_RESTORE_ONLY,
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


# ── Internal helpers ──────────────────────────────────────────────────────────

def _wizard_init(project_path: Path, mode: str | None = None) -> Path:
    """Run the interactive init wizard and return the path to .remotes.json.

    Args:
        project_path: Root directory of the project.
        mode: When provided the mode selection step is skipped and this value
              is used directly (e.g. inferred from the calling command).

    Handles both the "create new" and "add to existing" flows.
    Raises :exc:`SelectionCancelledError` or :exc:`ConfigError` on failure.
    """
    remotes_file = get_remotes_file_path(project_path)
    file_exists = remotes_file.exists()

    if file_exists:
        action = ask_add_or_overwrite()
    else:
        action = "create"

    if mode is None:
        mode = ask_remote_mode()
    else:
        label = MODE_LABELS.get(mode, mode)
        console.print(f"  Modo: [cyan]{label}[/cyan] (pré-selecionado)\n")

    answers = ask_remote_config(mode=mode)
    remote_cfg = build_remote_config(
        dbname=answers.dbname,
        remote_address=answers.remote_address,
        password=answers.password,
    )

    if action == "overwrite":
        remotes_path = write_remotes(project_path, {answers.name: remote_cfg}, overwrite=True)
    else:
        remotes_path = add_remote(
            project_path,
            answers.name,
            remote_cfg,
            overwrite_existing_name=False,
        )

    return remotes_path


def _ensure_project_config(project_path: Path, mode: str | None = None) -> ProjectConfig:
    """Load project config, running the init wizard automatically if missing.

    When ``.remotes.json`` does not exist the user is informed and the
    interactive wizard starts immediately — no need to run ``dbodoo init``
    first.

    Args:
        project_path: Root directory of the project.
        mode: Passed to :func:`_wizard_init` to skip the mode-selection step.

    Raises:
        ConfigError: for any config problem other than a missing file.
        SelectionCancelledError: if the user cancels the wizard.
    """
    try:
        return load_project_config(project_path)
    except RemotesFileNotFoundError:
        console.print(
            "[yellow]Nenhuma configuração encontrada.[/yellow] "
            "Vamos criar o [cyan].remotes.json[/cyan] agora:\n"
        )
        remotes_path = _wizard_init(project_path, mode=mode)
        console.print(f"\n[bold green]✓[/bold green] Configuração salva em {remotes_path}\n")
        return load_project_config(project_path)


# ── Commands ──────────────────────────────────────────────────────────────────

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
    remotes_file = get_remotes_file_path(project_path)
    file_exists = remotes_file.exists()

    try:
        # ── Non-interactive path (all flags provided) ──────────────────────
        if name is not None and dbname is not None:
            remote_cfg = build_remote_config(
                dbname=dbname,
                remote_address=remote_address,
                password=password,
            )
            if force:
                remotes_path = write_remotes(project_path, {name: remote_cfg}, overwrite=True)
            else:
                remotes_path = add_remote(project_path, name, remote_cfg)
            console.print(f"[bold green]✓[/bold green] Saved {remotes_path}")
            return

        # ── Interactive path ───────────────────────────────────────────────
        if force and file_exists:
            # --force skips the add/overwrite question
            mode = ask_remote_mode()
            answers = ask_remote_config(mode=mode)
            remote_cfg = build_remote_config(
                dbname=answers.dbname,
                remote_address=answers.remote_address,
                password=answers.password,
            )
            remotes_path = write_remotes(
                project_path, {answers.name: remote_cfg}, overwrite=True
            )
        else:
            remotes_path = _wizard_init(project_path)

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

    # Infer the wizard mode from which flags were passed so the user is not
    # asked to confirm something we already know.
    if do_both:
        inferred_mode = MODE_BACKUP_RESTORE
    elif do_backup:
        inferred_mode = MODE_BACKUP_ONLY
    else:
        inferred_mode = MODE_RESTORE_ONLY

    try:
        project_config = _ensure_project_config(project_path, mode=inferred_mode)
        selected = choose_remote_name(project_config.remotes)

        if do_both:
            backup_path = backup_and_restore_remote(
                project_config,
                selected,
                destination_db=destination_db,
            )
            console.print(
                f"[bold green]✓[/bold green] Backup + restore complete. ZIP: {backup_path}"
            )

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

    except ConfigError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        error_console.print(
            "Update .remotes.json with the fields required for this operation."
        )
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Cancelled.")
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
