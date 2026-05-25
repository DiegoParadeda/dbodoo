"""General utility helpers."""

from __future__ import annotations

from pathlib import Path


def current_project_path() -> Path:
    """Return the current working directory as the active project path."""
    return Path.cwd().resolve()
