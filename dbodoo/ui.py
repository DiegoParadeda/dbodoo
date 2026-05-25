"""Rich console helpers and interactive prompts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

import questionary
from rich.console import Console

console = Console()
error_console = Console(stderr=True)

# Remote wizard modes
MODE_BACKUP_RESTORE = "backup_restore"
MODE_RESTORE_ONLY = "restore_only"


class SelectionCancelledError(Exception):
    """Raised when the user cancels an interactive selection."""


class RemoteAnswers(NamedTuple):
    """Answers collected for one remote config."""

    name: str
    dbname: str
    remote_address: str | None
    password: str | None


def _ask_required_text(message: str, default: str | None = None) -> str:
    answer = questionary.text(message, default=default or "").ask()
    if answer is None:
        msg = "Prompt cancelled"
        raise SelectionCancelledError(msg)
    if not answer.strip():
        msg = f"{message} is required"
        raise ValueError(msg)
    return answer.strip()


def _ask_optional_text(message: str, password: bool = False) -> str | None:
    prompt = questionary.password(message) if password else questionary.text(message)
    answer = prompt.ask()
    if answer is None:
        msg = "Prompt cancelled"
        raise SelectionCancelledError(msg)
    stripped = answer.strip()
    return stripped or None


def ask_remote_mode() -> str:
    """Ask the user which mode they want for the remote config.

    Returns:
        ``MODE_BACKUP_RESTORE`` or ``MODE_RESTORE_ONLY``.
    """
    answer = questionary.select(
        "What will this remote be used for?",
        choices=[
            questionary.Choice(
                "Backup + Restore  (requires URL and master password)",
                value=MODE_BACKUP_RESTORE,
            ),
            questionary.Choice(
                "Restore only  (only needs the database name)",
                value=MODE_RESTORE_ONLY,
            ),
        ],
        use_indicator=True,
    ).ask()

    if answer is None:
        msg = "Mode selection cancelled"
        raise SelectionCancelledError(msg)

    return str(answer)


def ask_add_or_overwrite() -> str:
    """Ask whether to add a new remote or overwrite the whole config.

    Returns:
        ``'add'`` or ``'overwrite'``.
    """
    answer = questionary.select(
        ".remotes.json already exists — what would you like to do?",
        choices=[
            questionary.Choice("Add another remote to the existing file", value="add"),
            questionary.Choice("Overwrite — replace the entire file", value="overwrite"),
        ],
        use_indicator=True,
    ).ask()

    if answer is None:
        msg = "Action selection cancelled"
        raise SelectionCancelledError(msg)

    return str(answer)


def ask_remote_config(mode: str = MODE_BACKUP_RESTORE) -> RemoteAnswers:
    """Ask for remote configuration values.

    In *backup_restore* mode both ``remote_address`` and ``password`` are
    required.  In *restore_only* mode they are skipped entirely.

    Args:
        mode: One of :data:`MODE_BACKUP_RESTORE` or :data:`MODE_RESTORE_ONLY`.
    """
    name = _ask_required_text("Remote name:", default="prod")
    dbname = _ask_required_text("Database name:", default=name)

    if mode == MODE_BACKUP_RESTORE:
        remote_address = _ask_optional_text("Remote URL/address:")
        if not remote_address:
            # keep asking until the user provides a value
            remote_address = _ask_required_text("Remote URL/address (required for backup):")
        password = _ask_optional_text(
            "Master password:",
            password=True,
        )
        if not password:
            password = _ask_required_text("Master password (required for backup):")
    else:
        remote_address = None
        password = None

    return RemoteAnswers(
        name=name,
        dbname=dbname,
        remote_address=remote_address,
        password=password,
    )


def choose_remote_name(remotes: Mapping[str, Any]) -> str:
    """Choose a remote name from loaded remotes."""
    remote_names = list(remotes.keys())

    if not remote_names:
        msg = "No remotes available"
        raise ValueError(msg)

    if len(remote_names) == 1:
        selected = remote_names[0]
        error_console.print(f"Only one remote available: {selected}")
        return selected

    selected = questionary.select(
        "Select a remote:",
        choices=remote_names,
        use_indicator=True,
    ).ask()

    if selected is None:
        msg = "Remote selection cancelled"
        raise SelectionCancelledError(msg)

    return str(selected)
