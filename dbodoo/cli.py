"""Command-line interface for dbodoo."""

from __future__ import annotations

from pathlib import Path

import typer

from dbodoo import __version__
from dbodoo.admin import AdminError, reset_admin
from dbodoo.neutralize.mail import neutralize_mail
from dbodoo.neutralize.utils import NeutralizeError
from dbodoo.addons import AddonsError, run_addons
from dbodoo.backup import BackupError, BackupFormat
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
    ask_local_db,
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

admin_app = typer.Typer(
    help="Odoo admin user operations.",
    no_args_is_help=True,
)
app.add_typer(admin_app, name="admin")

neutralize_app = typer.Typer(
    help="Neutralize local database settings to prevent accidents.",
    no_args_is_help=True,
)
app.add_typer(neutralize_app, name="neutralize")


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


@app.command("odoo")
def odoo_cmd(
    install: str | None = typer.Option(
        None,
        "-i",
        "--install",
        help="Comma-separated list of addons to install (runs 'addons init').",
        show_default=False,
    ),
    update: str | None = typer.Option(
        None,
        "-u",
        "--update",
        help="Comma-separated list of addons to update (runs 'addons update').",
        show_default=False,
    ),
    db: str | None = typer.Option(
        None,
        "--db",
        "-d",
        help=(
            "Database name. Omit to use the container's default "
            "(set in odoo.conf — usually 'devel')."
        ),
        show_default=False,
    ),
) -> None:
    """Install or update Odoo addons in the local Doodba environment.

    Stops the odoo container before running, so it is safe to use even
    while the instance is up.  Both flags can be combined: install runs
    first, update second.

    \b
    Examples:
      dbodoo odoo -i my_addon            Install an addon
      dbodoo odoo -u my_addon            Update an addon
      dbodoo odoo -i addon1,addon2       Install multiple addons
      dbodoo odoo -u addon1,addon2       Update multiple addons
      dbodoo odoo -i base                Safe — unlike invoke, works fine
      dbodoo odoo -i sale -u stock       Install sale, then update stock
      dbodoo odoo -u my_addon --db prod  Target a specific database
    """
    if not install and not update:
        error_console.print(
            "[bold red]Error:[/bold red] Provide at least one of "
            "[cyan]-i[/cyan] (install) or [cyan]-u[/cyan] (update)."
        )
        raise typer.Exit(code=1)

    project_path: Path = current_project_path()

    try:
        if install:
            run_addons(project_path, install, "init", db=db)
            console.print(
                f"[bold green]✓[/bold green] Installed [cyan]{install}[/cyan]."
            )
        if update:
            run_addons(project_path, update, "update", db=db)
            console.print(
                f"[bold green]✓[/bold green] Updated [cyan]{update}[/cyan]."
            )
    except AddonsError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except DockerError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error


@app.command()
def remote(
    backup: bool = typer.Option(
        False,
        "--backup",
        "-b",
        help="Download a remote database backup.",
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
    backup_format: BackupFormat = typer.Option(
        BackupFormat.zip,
        "--format",
        "-f",
        help=(
            "Backup format: 'zip' (full backup with filestore, default) "
            "or 'dump' (SQL-only pg_dump, no filestore)."
        ),
        show_default=True,
    ),
) -> None:
    """Run remote database workflows.

    \b
    Examples:
      dbodoo remote -b              Download ZIP backup from remote
      dbodoo remote -b -f dump      Download SQL-only dump from remote
      dbodoo remote -r              Restore last downloaded ZIP backup
      dbodoo remote -r -f dump      Restore last downloaded dump
      dbodoo remote -b -r           Download ZIP backup and restore in one step
      dbodoo remote -b -r -f dump   Download dump and restore in one step
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
                backup_format=backup_format,
            )
            console.print(
                f"[bold green]✓[/bold green] Backup + restore complete. "
                f"File: {backup_path}"
            )

        elif do_backup:
            backup_path = backup_remote(
                project_config,
                selected,
                backup_format=backup_format,
            )
            console.print(f"[bold green]✓[/bold green] Backup saved to {backup_path}")

        else:  # restore only
            backup_path = restore_remote(
                project_config,
                selected,
                destination_db=destination_db,
                backup_format=backup_format,
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


@admin_app.command("reset")
def admin_reset(
    login: str = typer.Option(
        "admin",
        "--login",
        help="New login (default: admin).",
    ),
    password: str = typer.Option(
        "admin",
        "--password",
        help="New password (default: admin).",
    ),
    user_id: int = typer.Option(
        2,
        "--user-id",
        help="Database id of the user to reset (default: 2).",
    ),
    db: str = typer.Option(
        "devel",
        "--db",
        help="Local database name to connect to (default: devel).",
    ),
    disable_2fa: bool = typer.Option(
        True,
        "--disable-2fa/--keep-2fa",
        help="Disable TOTP 2FA (default: --disable-2fa).",
    ),
) -> None:
    """Reset an Odoo admin user: login, password, 2FA, and active status.

    \b
    Examples:
      dbodoo admin reset                       Reset to defaults (login=admin, password=admin)
      dbodoo admin reset --login myuser        Set a custom login
      dbodoo admin reset --password secret     Set a custom password
      dbodoo admin reset --user-id 3           Reset the user with id=3
      dbodoo admin reset --db mydb             Target a specific local database
      dbodoo admin reset --keep-2fa            Leave 2FA settings untouched
    """
    project_path: Path = current_project_path()

    try:
        confirmed_db = ask_local_db(default=db)
        reset_admin(
            project_path=project_path,
            dbname=confirmed_db,
            login=login,
            password=password,
            user_id=user_id,
            disable_2fa=disable_2fa,
        )
    except AdminError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except DockerError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Cancelled.")
        raise typer.Exit(code=1) from error


@neutralize_app.command("mail")
def neutralize_mail_cmd(
    db: str = typer.Option(
        "devel",
        "--db",
        help="Local database name (default: devel).",
    ),
) -> None:
    """Disable all outgoing mail servers to prevent accidental email delivery.

    Sets active=False on every ir.mail_server record.

    \b
    Examples:
      dbodoo neutralize mail            Neutralize the 'devel' database
      dbodoo neutralize mail --db prod  Neutralize a specific database
    """
    project_path: Path = current_project_path()

    try:
        confirmed_db = ask_local_db(default=db)
        neutralize_mail(project_path=project_path, dbname=confirmed_db)
    except NeutralizeError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except DockerError as error:
        error_console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except SelectionCancelledError as error:
        error_console.print("Cancelled.")
        raise typer.Exit(code=1) from error


if __name__ == "__main__":
    app()
