"""Project configuration helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, TypeAlias

REMOTES_FILENAME = ".remotes.json"
RemoteConfig: TypeAlias = dict[str, Any]
RemotesConfig: TypeAlias = dict[str, RemoteConfig]


class ConfigError(Exception):
    """Base error for project configuration problems."""


class RemotesFileNotFoundError(ConfigError):
    """Raised when .remotes.json cannot be found."""


class InvalidRemotesConfigError(ConfigError):
    """Raised when .remotes.json has invalid content."""


@dataclass(frozen=True)
class ProjectConfig:
    """Configuration discovered from the current project directory."""

    project_path: Path
    remotes_path: Path
    remotes: RemotesConfig


def find_remotes_file(project_path: Path | None = None) -> Path:
    """Return the .remotes.json path for a project, or raise if missing."""
    root_path = (project_path or Path.cwd()).resolve()
    remotes_path = root_path / REMOTES_FILENAME

    if not remotes_path.is_file():
        msg = f"Configuration file {REMOTES_FILENAME} not found in {root_path}"
        raise RemotesFileNotFoundError(msg)

    return remotes_path


def load_remotes(project_path: Path | None = None) -> RemotesConfig:
    """Load and validate remotes from .remotes.json."""
    remotes_path = find_remotes_file(project_path)

    try:
        with remotes_path.open("r", encoding="utf-8") as file_handle:
            loaded = json.load(file_handle)
    except JSONDecodeError as error:
        msg = f"Invalid JSON in {remotes_path}: {error.msg}"
        raise InvalidRemotesConfigError(msg) from error

    if not isinstance(loaded, dict):
        msg = f"{REMOTES_FILENAME} must contain a JSON object"
        raise InvalidRemotesConfigError(msg)

    remotes: RemotesConfig = {}
    for name, remote in loaded.items():
        if not isinstance(name, str) or not name.strip():
            msg = f"{REMOTES_FILENAME} contains an invalid remote name"
            raise InvalidRemotesConfigError(msg)
        if not isinstance(remote, dict):
            msg = f"Remote '{name}' must be a JSON object"
            raise InvalidRemotesConfigError(msg)
        remotes[name] = remote

    if not remotes:
        msg = f"{REMOTES_FILENAME} does not define any remotes"
        raise InvalidRemotesConfigError(msg)

    return remotes


def load_project_config(project_path: Path) -> ProjectConfig:
    """Load dbodoo configuration from a project path."""
    remotes_path = find_remotes_file(project_path)
    remotes = load_remotes(project_path)

    return ProjectConfig(
        project_path=project_path.resolve(),
        remotes_path=remotes_path,
        remotes=remotes,
    )
