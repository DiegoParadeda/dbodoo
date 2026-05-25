"""Project configuration helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REMOTES_FILENAME = ".remotes.json"


@dataclass(frozen=True)
class ProjectConfig:
    """Configuration discovered from the current project directory."""

    project_path: Path
    remotes_path: Path
    remotes: dict[str, Any]


def load_project_config(project_path: Path) -> ProjectConfig:
    """Load dbodoo configuration from a project path."""
    remotes_path = project_path / REMOTES_FILENAME
    remotes: dict[str, Any] = {}

    if remotes_path.is_file():
        with remotes_path.open("r", encoding="utf-8") as file_handle:
            loaded = json.load(file_handle)
        if isinstance(loaded, dict):
            remotes = loaded
        else:
            msg = f"{REMOTES_FILENAME} must contain a JSON object"
            raise ValueError(msg)

    return ProjectConfig(
        project_path=project_path,
        remotes_path=remotes_path,
        remotes=remotes,
    )
