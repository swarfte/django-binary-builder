"""Runtime data directory resolution.

This module is imported by the packaged application before Django is
set up, so it must not import ``django`` at module level.
"""

import os
from pathlib import Path
from typing import Any

DATA_DIRECTORY_NAME = "data"
STATE_DIRECTORY_NAME = "state"

DATA_DIRECTORY_ENVIRONMENT_VARIABLE = "DJANGO_BINARY_DATA_DIR"


def resolve_runtime_root(defaults: dict[str, Any]) -> Path:
    """Resolve the persistent runtime data root.

    Precedence: ``DJANGO_BINARY_DATA_DIR`` environment variable,
    then ``RUNTIME.DATA_DIRECTORY``, then the per-user operating
    system default.
    """

    override = os.environ.get(DATA_DIRECTORY_ENVIRONMENT_VARIABLE)

    if override:
        return Path(override).expanduser().resolve()

    runtime_config = defaults.get("runtime", {})
    configured = runtime_config.get("data_directory")

    if configured:
        return Path(configured).expanduser().resolve()

    company = runtime_config.get("company_directory") or "DjangoBinaryBuilder"
    application = runtime_config.get("application_directory") or "Application"

    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        return (
            Path(local_app_data)
            / _safe_directory(company)
            / _safe_directory(application)
        )

    return (
        Path.home()
        / ".local"
        / "share"
        / _safe_directory(company)
        / _safe_directory(application)
    )


def create_runtime_directories(
    runtime_root: Path,
    defaults: dict[str, Any],
) -> dict[str, Path]:
    """Create and return the writable runtime directories."""

    runtime_config = defaults.get("runtime", {})

    directories = {
        "root": runtime_root,
        "data": runtime_root / DATA_DIRECTORY_NAME,
        "state": runtime_root / STATE_DIRECTORY_NAME,
        "config": runtime_root
        / _safe_directory(runtime_config.get("config_directory") or "config"),
        "media": runtime_root
        / _safe_directory(runtime_config.get("media_directory") or "media"),
        "logs": runtime_root
        / _safe_directory(runtime_config.get("log_directory") or "logs"),
    }

    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    return directories


def _safe_directory(name: Any) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in str(name).strip()
    ).strip("-")

    return cleaned or "DjangoBinaryBuilder"
