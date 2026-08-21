"""Settings handling for django-binary-builder.

This module defines library defaults, deep-merges the project's
``DJANGO_BINARY_BUILDER`` setting, normalizes paths, and validates
setting types. It never executes a build and never moves secret
values into dedicated fields.
"""

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

from django_binary_builder.runtime.database import validate_sqlite_filename

DEFAULTS: dict[str, Any] = {
    "NAME": None,
    "VERSION": "0.1.0",
    "PUBLISHER": None,
    "EXECUTABLE_NAME": None,
    "ICON": None,
    "OUTPUT_DIR": "release",
    "WORK_DIR": ".django-binary-builder",
    "SERVER": {
        "HOST": "127.0.0.1",
        "PORT": 8765,
        "THREADS": 8,
        "OPEN_BROWSER": True,
    },
    "ENVIRONMENT": {
        "ENABLED": True,
        "FILES": [],
        "OVERRIDE_PROCESS_ENV": False,
        "INCLUDE": [],
        "EXCLUDE": [
            "DJANGO_BINARY_ADMIN_PASSWORD",
            "DJANGO_BINARY_DB_PASSWORD",
        ],
        "REQUIRED": [],
        "PACKAGE_MODE": "snapshot",
        "SNAPSHOT_FILENAME": "runtime-environment.json",
        "ALLOW_SECRETS": False,
        "WARN_ON_SECRET_NAMES": True,
    },
    "DATABASE": {
        "MODE": "sqlite",
        "RUN_MIGRATIONS": True,
        "MIGRATION_TIMEOUT": 300,
        "SQLITE": {
            "FILENAME": "db.sqlite3",
            "COPY_INITIAL_DATABASE": False,
            "INITIAL_DATABASE": None,
        },
        "EXTERNAL": {
            "USE_PROJECT_SETTINGS": True,
            "CONFIG_FILE": "database.json",
            "ALLOW_ENVIRONMENT_VARIABLES": True,
            "TEST_CONNECTION_ON_STARTUP": True,
        },
    },
    "INITIAL_ADMIN": {
        "ENABLED": True,
        "SQLITE_ONLY": True,
        "USERNAME": "admin",
        "PASSWORD": "admin1234",
        "EMAIL": "admin@localhost",
        "EXTRA_FIELDS": {},
        "REQUIRE_PASSWORD_CHANGE": True,
        "RESET_PASSWORD_IF_USER_EXISTS": False,
    },
    "RUNTIME": {
        "COMPANY_DIRECTORY": None,
        "APPLICATION_DIRECTORY": None,
        "DATA_DIRECTORY": None,
        "LOG_DIRECTORY": "logs",
        "MEDIA_DIRECTORY": "media",
        "CONFIG_DIRECTORY": "config",
    },
    "BUILD": {
        "MODE": "onedir",
        "CONSOLE": False,
        "CLEAN": True,
        "COLLECT_STATIC": True,
        "HIDDEN_IMPORTS": [],
        "EXCLUDED_MODULES": [],
        "EXTRA_DATA": [],
    },
    "WINDOWS": {
        "INNO_SETUP_COMPILER": None,
        "PRIVILEGES": "lowest",
        "ARCHITECTURE": "x64compatible",
        "CREATE_DESKTOP_SHORTCUT": True,
        "CREATE_START_MENU_SHORTCUT": True,
    },
}

_VALID_PRIVILEGES = {"lowest", "admin"}
_VALID_DATABASE_MODES = {"sqlite", "external"}
_EXECUTABLE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Return a deep merge of ``override`` on top of ``base``."""

    result = deepcopy(base)

    for key, value in override.items():
        existing_value = result.get(key)

        if isinstance(existing_value, dict) and isinstance(value, dict):
            result[key] = deep_merge(existing_value, value)
        else:
            result[key] = deepcopy(value)

    return result


def get_builder_settings(
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the merged, normalized and validated builder settings."""

    user_settings = getattr(settings, "DJANGO_BINARY_BUILDER", None) or {}

    if not isinstance(user_settings, dict):
        raise CommandError("The DJANGO_BINARY_BUILDER setting must be a dictionary.")

    config = deep_merge(DEFAULTS, user_settings)

    if overrides:
        config = deep_merge(config, overrides)

    _normalize(config)
    _validate(config)

    return config


def make_safe_filename(value: str) -> str:
    """Convert ``value`` into a safe file or directory name."""

    characters: list[str] = []

    for character in str(value).strip():
        if character.isalnum() or character in {"-", "_"}:
            characters.append(character)
        else:
            characters.append("-")

    normalized = "".join(characters)

    while "--" in normalized:
        normalized = normalized.replace("--", "-")

    normalized = normalized.strip("-")

    return normalized or "django-binary-builder"


def validate_executable_name(name: Any) -> str:
    """Validate an executable name safe for Windows."""

    if not isinstance(name, str) or not name:
        raise CommandError("EXECUTABLE_NAME must be a non-empty string.")

    if len(name) > 100 or not _EXECUTABLE_NAME_PATTERN.fullmatch(name):
        raise CommandError(
            "EXECUTABLE_NAME must only contain letters, digits, "
            "'-' and '_', and must start with a letter or digit: "
            f"{name!r}."
        )

    if name.upper() in _RESERVED_WINDOWS_NAMES:
        raise CommandError(
            f"EXECUTABLE_NAME must not use a reserved Windows device name: {name!r}."
        )

    return name


def _normalize(config: dict[str, Any]) -> None:
    project_root = Path(settings.BASE_DIR).resolve()
    config["PROJECT_ROOT"] = project_root

    for key in ("OUTPUT_DIR", "WORK_DIR"):
        path = _resolve_against(project_root, config[key])
        config[key] = path

    if config["ICON"]:
        config["ICON"] = _resolve_against(project_root, config["ICON"])

    environment_config = config["ENVIRONMENT"]
    environment_config["FILES"] = [
        _resolve_against(project_root, item) for item in environment_config["FILES"]
    ]

    sqlite_config = config["DATABASE"]["SQLITE"]

    if sqlite_config["INITIAL_DATABASE"]:
        sqlite_config["INITIAL_DATABASE"] = _resolve_against(
            project_root,
            sqlite_config["INITIAL_DATABASE"],
        )

    if not config["NAME"]:
        config["NAME"] = project_root.name

    if not config["EXECUTABLE_NAME"]:
        config["EXECUTABLE_NAME"] = make_safe_filename(config["NAME"])

    runtime_config = config["RUNTIME"]

    if not runtime_config["COMPANY_DIRECTORY"]:
        runtime_config["COMPANY_DIRECTORY"] = make_safe_filename(
            config["PUBLISHER"] or config["NAME"]
        )

    if not runtime_config["APPLICATION_DIRECTORY"]:
        runtime_config["APPLICATION_DIRECTORY"] = make_safe_filename(config["NAME"])

    settings_module = getattr(settings, "SETTINGS_MODULE", None) or os.environ.get(
        "DJANGO_SETTINGS_MODULE"
    )

    if not settings_module:
        raise CommandError("Could not determine DJANGO_SETTINGS_MODULE for the build.")

    config["SETTINGS_MODULE"] = settings_module
    config["WSGI_APPLICATION"] = getattr(
        settings,
        "WSGI_APPLICATION",
        None,
    )


def _resolve_against(project_root: Path, value: Any) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = project_root / path

    return path.resolve()


def _validate(config: dict[str, Any]) -> None:
    _expect_type(config, "NAME", str, allow_none=False, non_empty=True)
    _expect_type(config, "VERSION", str, non_empty=True)
    _expect_type(config, "PUBLISHER", str, allow_none=True)
    validate_executable_name(config["EXECUTABLE_NAME"])

    server = _expect_section(config, "SERVER")
    _expect_type(server, "SERVER.HOST", str, non_empty=True)
    _expect_type(server, "SERVER.PORT", int)

    if not 1 <= server["PORT"] <= 65535:
        raise CommandError(
            f"SERVER.PORT must be between 1 and 65535: {server['PORT']!r}."
        )

    _expect_type(server, "SERVER.THREADS", int)

    if server["THREADS"] < 1:
        raise CommandError("SERVER.THREADS must be at least 1.")

    _expect_type(server, "SERVER.OPEN_BROWSER", bool)

    environment = _expect_section(config, "ENVIRONMENT")
    _expect_type(environment, "ENVIRONMENT.ENABLED", bool)
    _expect_type(environment, "ENVIRONMENT.OVERRIDE_PROCESS_ENV", bool)
    _expect_type(environment, "ENVIRONMENT.ALLOW_SECRETS", bool)
    _expect_type(environment, "ENVIRONMENT.WARN_ON_SECRET_NAMES", bool)

    _expect_type(environment, "ENVIRONMENT.FILES", list)

    for item in environment["FILES"]:
        _expect_value_type(
            item,
            (str, Path),
            "ENVIRONMENT.FILES entries",
        )

    for key in ("INCLUDE", "EXCLUDE", "REQUIRED"):
        _expect_type(environment, f"ENVIRONMENT.{key}", list)

        for item in environment[key]:
            _expect_value_type(
                item,
                str,
                f"ENVIRONMENT.{key} entries",
            )

    if environment["PACKAGE_MODE"] != "snapshot":
        raise CommandError(
            "ENVIRONMENT.PACKAGE_MODE must be 'snapshot' in this version."
        )

    _validate_plain_filename(
        environment["SNAPSHOT_FILENAME"],
        "ENVIRONMENT.SNAPSHOT_FILENAME",
    )

    database = _expect_section(config, "DATABASE")

    if database["MODE"] not in _VALID_DATABASE_MODES:
        raise CommandError(
            "DATABASE.MODE must be one of: "
            + ", ".join(sorted(_VALID_DATABASE_MODES))
            + f" (got {database['MODE']!r})."
        )

    _expect_type(database, "DATABASE.RUN_MIGRATIONS", bool)
    _expect_type(database, "DATABASE.MIGRATION_TIMEOUT", int)

    if database["MIGRATION_TIMEOUT"] < 1:
        raise CommandError("DATABASE.MIGRATION_TIMEOUT must be at least 1.")

    sqlite = _expect_section(database, "DATABASE.SQLITE")
    _expect_type(sqlite, "DATABASE.SQLITE.COPY_INITIAL_DATABASE", bool)
    _expect_type(
        sqlite,
        "DATABASE.SQLITE.INITIAL_DATABASE",
        (str, Path),
        allow_none=True,
    )

    try:
        validate_sqlite_filename(sqlite["FILENAME"])
    except ValueError as error:
        raise CommandError(
            f"Invalid DATABASE.SQLITE.FILENAME setting: {error}"
        ) from error

    if sqlite["COPY_INITIAL_DATABASE"] and not sqlite["INITIAL_DATABASE"]:
        raise CommandError(
            "DATABASE.SQLITE.INITIAL_DATABASE must be set when "
            "COPY_INITIAL_DATABASE is enabled."
        )

    external = _expect_section(database, "DATABASE.EXTERNAL")
    _expect_type(external, "DATABASE.EXTERNAL.USE_PROJECT_SETTINGS", bool)
    _expect_type(external, "DATABASE.EXTERNAL.CONFIG_FILE", str)
    _expect_type(
        external,
        "DATABASE.EXTERNAL.ALLOW_ENVIRONMENT_VARIABLES",
        bool,
    )
    _expect_type(
        external,
        "DATABASE.EXTERNAL.TEST_CONNECTION_ON_STARTUP",
        bool,
    )

    admin = _expect_section(config, "INITIAL_ADMIN")
    _expect_type(admin, "INITIAL_ADMIN.ENABLED", bool)
    _expect_type(admin, "INITIAL_ADMIN.SQLITE_ONLY", bool)
    _expect_type(admin, "INITIAL_ADMIN.USERNAME", str, non_empty=True)
    _expect_type(admin, "INITIAL_ADMIN.PASSWORD", str, non_empty=True)
    _expect_type(admin, "INITIAL_ADMIN.EMAIL", str)
    _expect_type(admin, "INITIAL_ADMIN.REQUIRE_PASSWORD_CHANGE", bool)
    _expect_type(admin, "INITIAL_ADMIN.RESET_PASSWORD_IF_USER_EXISTS", bool)
    _expect_type(admin, "INITIAL_ADMIN.EXTRA_FIELDS", dict)

    runtime = _expect_section(config, "RUNTIME")

    for key in (
        "COMPANY_DIRECTORY",
        "APPLICATION_DIRECTORY",
        "DATA_DIRECTORY",
    ):
        _expect_type(runtime, f"RUNTIME.{key}", (str, Path), allow_none=True)

    for key in ("LOG_DIRECTORY", "MEDIA_DIRECTORY", "CONFIG_DIRECTORY"):
        _validate_plain_filename(runtime[key], f"RUNTIME.{key}")

    build = _expect_section(config, "BUILD")

    if build["MODE"] != "onedir":
        raise CommandError(
            "Only the 'onedir' build mode is supported in this "
            f"version (got {build['MODE']!r})."
        )

    for key in ("CONSOLE", "CLEAN", "COLLECT_STATIC"):
        _expect_type(build, f"BUILD.{key}", bool)

    for key in ("HIDDEN_IMPORTS", "EXCLUDED_MODULES"):
        _expect_type(build, f"BUILD.{key}", list)

        for item in build[key]:
            _expect_value_type(item, str, f"BUILD.{key} entries")

    _expect_type(build, "BUILD.EXTRA_DATA", list)

    for item in build["EXTRA_DATA"]:
        if not isinstance(item, dict):
            raise CommandError(
                "Each BUILD.EXTRA_DATA entry must be a dictionary with "
                "'source' and optional 'destination' keys."
            )

        if not item.get("source"):
            raise CommandError(
                "Each BUILD.EXTRA_DATA entry must contain a 'source' value."
            )

        if not isinstance(item.get("source"), (str, Path)):
            raise CommandError("BUILD.EXTRA_DATA 'source' must be a string or path.")

        if "destination" in item and not isinstance(
            item["destination"],
            (str, Path),
        ):
            raise CommandError(
                "BUILD.EXTRA_DATA 'destination' must be a string or path."
            )

    windows = _expect_section(config, "WINDOWS")
    _expect_type(
        windows,
        "WINDOWS.INNO_SETUP_COMPILER",
        (str, Path),
        allow_none=True,
    )

    if windows["PRIVILEGES"] not in _VALID_PRIVILEGES:
        raise CommandError(
            "WINDOWS.PRIVILEGES must be one of: "
            + ", ".join(sorted(_VALID_PRIVILEGES))
            + f" (got {windows['PRIVILEGES']!r})."
        )

    _expect_type(windows, "WINDOWS.ARCHITECTURE", str, non_empty=True)
    _expect_type(windows, "WINDOWS.CREATE_DESKTOP_SHORTCUT", bool)
    _expect_type(windows, "WINDOWS.CREATE_START_MENU_SHORTCUT", bool)


def _expect_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    section = config.get(key.split(".")[-1])

    if not isinstance(section, dict):
        raise CommandError(f"The {key} setting must be a dictionary.")

    return section


def _expect_type(
    section: dict[str, Any],
    key: str,
    expected: type | tuple[type, ...],
    *,
    allow_none: bool = False,
    non_empty: bool = False,
) -> None:
    name = key.split(".")[-1]
    value = section.get(name)

    if value is None and allow_none:
        return

    if not isinstance(value, expected):
        raise CommandError(
            f"Invalid {key} setting: expected "
            f"{getattr(expected, '__name__', str(expected))}, got "
            f"{type(value).__name__}."
        )

    if non_empty and not str(value).strip():
        raise CommandError(f"The {key} setting must not be empty.")


def _expect_value_type(
    value: Any,
    expected: type | tuple[type, ...],
    label: str,
) -> None:
    if not isinstance(value, expected):
        raise CommandError(
            f"{label} must be "
            f"{getattr(expected, '__name__', str(expected))}, got "
            f"{type(value).__name__}."
        )


def _validate_plain_filename(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"The {label} setting must be a non-empty string.")

    candidate = Path(value)

    if candidate.is_absolute() or candidate.name != value or ".." in candidate.parts:
        raise CommandError(
            f"The {label} setting must be a plain filename without "
            f"directories: {value!r}."
        )
