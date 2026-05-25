"""Project configuration helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, TypeAlias
from urllib.parse import urlsplit

REMOTES_FILENAME = ".remotes.json"
DoodbaMarker: TypeAlias = str
RemoteConfig: TypeAlias = dict[str, Any]
RemotesConfig: TypeAlias = dict[str, RemoteConfig]

DOODBA_MARKERS: tuple[DoodbaMarker, ...] = (
    "common.yaml",
    "docker-compose.yml",
    "odoo/custom/src",
)
REQUIRED_REMOTE_FIELDS: tuple[str, ...] = (
    "remote_address",
    "dbname",
    "password",
)
BACKUP_REMOTE_FIELDS: tuple[str, ...] = REQUIRED_REMOTE_FIELDS
RESTORE_REMOTE_FIELDS: tuple[str, ...] = ("dbname",)


class ConfigError(Exception):
    """Base error for project configuration problems."""


class RemotesFileNotFoundError(ConfigError):
    """Raised when .remotes.json cannot be found."""


class RemotesFileExistsError(ConfigError):
    """Raised when trying to create an existing .remotes.json."""


class InvalidRemotesConfigError(ConfigError):
    """Raised when .remotes.json has invalid content."""


class InvalidRemoteError(ConfigError):
    """Raised when a remote entry is incomplete or invalid."""


@dataclass(frozen=True)
class DoodbaDetection:
    """Result of Doodba project detection."""

    project_path: Path
    is_doodba: bool
    missing_markers: tuple[DoodbaMarker, ...]


@dataclass(frozen=True)
class ProjectConfig:
    """Configuration discovered from the current project directory."""

    project_path: Path
    remotes_path: Path
    remotes: RemotesConfig


def normalize_remote_address(address: str) -> str:
    """Normalize a remote address while preserving ports and valid subpaths."""
    stripped = address.strip()
    if not stripped:
        msg = "Remote address cannot be empty"
        raise InvalidRemoteError(msg)

    parsed = urlsplit(stripped)
    if parsed.scheme and parsed.netloc:
        normalized = f"{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized = f"{normalized}?{parsed.query}"
        if parsed.fragment:
            normalized = f"{normalized}#{parsed.fragment}"
    else:
        normalized = stripped

    return normalized.rstrip("/")


def detect_doodba(project_path: Path | None = None) -> DoodbaDetection:
    """Detect whether a path looks like a Doodba project root."""
    root_path = (project_path or Path.cwd()).resolve()
    missing_markers = tuple(
        marker for marker in DOODBA_MARKERS if not (root_path / marker).exists()
    )

    return DoodbaDetection(
        project_path=root_path,
        is_doodba=not missing_markers,
        missing_markers=missing_markers,
    )


def is_doodba_project(project_path: Path | None = None) -> bool:
    """Return whether a path looks like a Doodba project root."""
    return detect_doodba(project_path).is_doodba


def find_project_root(start_path: Path | None = None) -> Path:
    """Find the current project root from a starting path."""
    current_path = (start_path or Path.cwd()).resolve()
    if current_path.is_file():
        current_path = current_path.parent

    for candidate in (current_path, *current_path.parents):
        if (candidate / REMOTES_FILENAME).is_file():
            return candidate
        if is_doodba_project(candidate):
            return candidate

    return current_path


def find_remotes_file(project_path: Path | None = None) -> Path:
    """Return the .remotes.json path for a project, or raise if missing."""
    root_path = find_project_root(project_path)
    remotes_path = root_path / REMOTES_FILENAME

    if not remotes_path.is_file():
        msg = f"Configuration file {REMOTES_FILENAME} not found in {root_path}"
        raise RemotesFileNotFoundError(msg)

    return remotes_path


def get_remotes_file_path(project_path: Path | None = None) -> Path:
    """Return where .remotes.json should live for a project."""
    return find_project_root(project_path) / REMOTES_FILENAME


def validate_remote(
    name: str,
    remote: RemoteConfig,
    required_fields: tuple[str, ...] = (),
) -> RemoteConfig:
    """Validate and normalize one remote entry."""
    if not name.strip():
        msg = f"{REMOTES_FILENAME} contains an invalid remote name"
        raise InvalidRemoteError(msg)

    normalized: RemoteConfig = dict(remote)
    for field in required_fields:
        value = normalized.get(field)
        if not isinstance(value, str) or not value.strip():
            msg = f"Remote '{name}' is missing required field '{field}'"
            raise InvalidRemoteError(msg)
        normalized[field] = value.strip()

    remote_address = normalized.get("remote_address")
    if isinstance(remote_address, str) and remote_address.strip():
        normalized["remote_address"] = normalize_remote_address(remote_address)

    return normalized


def build_remote_config(
    dbname: str,
    remote_address: str | None = None,
    password: str | None = None,
) -> RemoteConfig:
    """Build a normalized remote config from user input."""
    remote: RemoteConfig = {"dbname": dbname.strip()}

    if remote_address and remote_address.strip():
        remote["remote_address"] = normalize_remote_address(remote_address)
    if password and password.strip():
        remote["password"] = password.strip()

    return validate_remote("remote", remote, RESTORE_REMOTE_FIELDS)


def write_remotes(
    project_path: Path,
    remotes: RemotesConfig,
    overwrite: bool = False,
) -> Path:
    """Write .remotes.json in a project root."""
    remotes_path = get_remotes_file_path(project_path)
    normalized_remotes = {
        name: validate_remote(name, remote, RESTORE_REMOTE_FIELDS)
        for name, remote in remotes.items()
    }

    if remotes_path.exists() and not overwrite:
        msg = f"Configuration file already exists: {remotes_path}"
        raise RemotesFileExistsError(msg)

    remotes_path.parent.mkdir(parents=True, exist_ok=True)
    with remotes_path.open("w", encoding="utf-8") as file_handle:
        json.dump(normalized_remotes, file_handle, indent=2)
        file_handle.write("\n")

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
        try:
            remotes[name] = validate_remote(name, remote)
        except InvalidRemoteError as error:
            raise InvalidRemotesConfigError(str(error)) from error

    if not remotes:
        msg = f"{REMOTES_FILENAME} does not define any remotes"
        raise InvalidRemotesConfigError(msg)

    return remotes


def load_project_config(project_path: Path) -> ProjectConfig:
    """Load dbodoo configuration from a project path."""
    root_path = find_project_root(project_path)
    remotes_path = find_remotes_file(root_path)
    remotes = load_remotes(root_path)

    return ProjectConfig(
        project_path=root_path,
        remotes_path=remotes_path,
        remotes=remotes,
    )
