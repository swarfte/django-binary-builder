"""Runtime database configuration.

This module is imported by the packaged application before Django is
fully set up, so it must not import ``django`` at module level.
"""

import json
import os
from pathlib import Path
from typing import Any

from django_binary_builder.exceptions import RuntimeInitializationError

ALLOWED_SQLITE_SUFFIXES = {".sqlite3", ".sqlite", ".db"}

EXTERNAL_ENVIRONMENT_OVERRIDES = {
    "DJANGO_BINARY_DB_ENGINE": "ENGINE",
    "DJANGO_BINARY_DB_NAME": "NAME",
    "DJANGO_BINARY_DB_USER": "USER",
    "DJANGO_BINARY_DB_PASSWORD": "PASSWORD",
    "DJANGO_BINARY_DB_HOST": "HOST",
    "DJANGO_BINARY_DB_PORT": "PORT",
}

EXTERNAL_CONFIG_KEYS = {
    "engine": "ENGINE",
    "name": "NAME",
    "user": "USER",
    "password": "PASSWORD",
    "host": "HOST",
    "port": "PORT",
}

DATABASE_SETTING_DEFAULTS: dict[str, Any] = {
    "ATOMIC_REQUESTS": False,
    "AUTOCOMMIT": True,
    "CONN_MAX_AGE": 0,
    "CONN_HEALTH_CHECKS": False,
    "TIME_ZONE": None,
    "OPTIONS": {},
    "USER": "",
    "PASSWORD": "",
    "HOST": "",
    "PORT": "",
}


def validate_sqlite_filename(filename: Any) -> str:
    """Return ``filename`` when it is a plain, safe SQLite filename."""

    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("SQLite filename must be a non-empty string.")

    candidate = Path(filename)

    if candidate.is_absolute() or candidate.name != filename:
        raise ValueError(
            "SQLite filename must be a plain filename without "
            f"directories: {filename!r}."
        )

    if ".." in candidate.parts:
        raise ValueError(f"SQLite filename must not contain '..': {filename!r}.")

    if candidate.suffix.lower() not in ALLOWED_SQLITE_SUFFIXES:
        raise ValueError(
            "SQLite filename must end with one of: "
            + ", ".join(sorted(ALLOWED_SQLITE_SUFFIXES))
            + f" (got {filename!r})."
        )

    return candidate.name


def configure_runtime_database(
    defaults: dict[str, Any],
    *,
    runtime_root: Path,
) -> dict[str, Any]:
    """Apply the configured runtime database mode to Django settings."""

    from django.conf import settings

    database_config = defaults.get("database", {})
    mode = database_config.get("mode", "sqlite")

    if mode == "sqlite":
        database = _build_sqlite_database(database_config, runtime_root)
    elif mode == "external":
        database = _build_external_database(database_config, runtime_root)
    else:
        raise RuntimeInitializationError(
            f"Unsupported runtime database mode: {mode!r}."
        )

    # Update in place so keys the project already configured (for
    # example OPTIONS or ATOMIC_REQUESTS) are preserved and Django's
    # request handler always sees a complete configuration.
    settings.DATABASES.setdefault("default", dict(DATABASE_SETTING_DEFAULTS))
    settings.DATABASES["default"].update(database)

    return settings.DATABASES["default"]


def _build_sqlite_database(
    database_config: dict[str, Any],
    runtime_root: Path,
) -> dict[str, Any]:
    sqlite_config = database_config.get("sqlite", {})
    filename = sqlite_config.get("filename", "db.sqlite3")

    try:
        filename = validate_sqlite_filename(filename)
    except ValueError as error:
        raise RuntimeInitializationError(str(error)) from error

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(runtime_root / "data" / filename),
    }


def _build_external_database(
    database_config: dict[str, Any],
    runtime_root: Path,
) -> dict[str, Any]:
    from django.conf import settings

    external_config = database_config.get("external", {})

    if external_config.get("use_project_settings", True):
        database = dict(settings.DATABASES.get("default", {}))
    else:
        config_file = external_config.get("config_file", "database.json")
        config_path = runtime_root / "config" / config_file
        database = _load_external_config_file(config_path)

    if external_config.get("allow_environment_variables", True):
        database = apply_environment_overrides(database)

    if not database.get("ENGINE"):
        raise RuntimeInitializationError(
            "The external database configuration does not define an engine."
        )

    return database


def _load_external_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise RuntimeInitializationError(
            "External database configuration file was not found: "
            f"{config_path}. Provide the file or set "
            "DATABASE.EXTERNAL.USE_PROJECT_SETTINGS=True."
        )

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise RuntimeInitializationError(
            f"External database configuration is not valid JSON: {config_path}."
        ) from error

    if not isinstance(raw, dict):
        raise RuntimeInitializationError(
            f"External database configuration must be a JSON object: {config_path}."
        )

    database: dict[str, Any] = {}

    for key, value in raw.items():
        normalized = str(key).lower()

        if value is None:
            continue

        setting = EXTERNAL_CONFIG_KEYS.get(normalized)

        if setting is None:
            continue

        if setting == "PORT" and isinstance(value, str) and value.isdigit():
            value = int(value)

        database[setting] = value

    completed = dict(DATABASE_SETTING_DEFAULTS)
    completed.update(database)

    return completed


def apply_environment_overrides(
    database: dict[str, Any],
) -> dict[str, Any]:
    """Apply ``DJANGO_BINARY_DB_*`` overrides to a database mapping."""

    result = dict(database)

    for env_name, setting in EXTERNAL_ENVIRONMENT_OVERRIDES.items():
        value = os.environ.get(env_name)

        if value is None:
            continue

        if setting == "PORT" and value.isdigit():
            value = int(value)

        result[setting] = value

    return result
