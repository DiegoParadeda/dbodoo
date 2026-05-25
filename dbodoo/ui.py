"""Rich console helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import questionary
from rich.console import Console

console = Console()
error_console = Console(stderr=True)


class SelectionCancelledError(Exception):
    """Raised when the user cancels an interactive selection."""


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
