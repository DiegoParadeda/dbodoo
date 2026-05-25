"""Rich console helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

import questionary
from rich.console import Console

console = Console()
error_console = Console(stderr=True)


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


def ask_remote_config() -> RemoteAnswers:
    """Ask for remote configuration values."""
    name = _ask_required_text("Remote name:", default="prod")
    dbname = _ask_required_text("Database name:", default=name)
    remote_address = _ask_optional_text("Remote URL/address (optional for restore):")
    password = _ask_optional_text(
        "Master password (optional for restore):",
        password=True,
    )

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
