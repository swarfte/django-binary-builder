"""Settings handling for django-binary-builder.

The library supports a single, minimal ``DJANGO_BINARY_BUILDER``
setting; everything else about the build is derived automatically
from the project and the current Python environment.
"""

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

SUPPORTED_KEYS = frozenset(
    {
        "NAME",
        "VERSION",
        "PUBLISHER",
        "EXECUTABLE_NAME",
        "ICON",
    }
)

DEFAULTS: dict[str, Any] = {
    "NAME": None,
    "VERSION": "0.1.0",
    "PUBLISHER": None,
    "EXECUTABLE_NAME": None,
    "ICON": None,
}

_EXECUTABLE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def get_builder_settings(
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the normalized builder settings for this build.

    Unknown keys are ignored and reported through the ``WARNINGS``
    entry so the management command can surface them.
    """

    user_settings = getattr(settings, "DJANGO_BINARY_BUILDER", None) or {}

    if not isinstance(user_settings, dict):
        raise CommandError("The DJANGO_BINARY_BUILDER setting must be a dictionary.")

    warnings = [
        f"Ignored unknown DJANGO_BINARY_BUILDER key: {key!r} "
        f"(supported keys: {', '.join(sorted(SUPPORTED_KEYS))})"
        for key in sorted(user_settings.keys() - SUPPORTED_KEYS)
    ]

    config = deepcopy(DEFAULTS)

    for key in SUPPORTED_KEYS:
        if user_settings.get(key) is not None:
            config[key] = user_settings[key]

    if overrides:
        for key, value in overrides.items():
            if key in SUPPORTED_KEYS:
                config[key] = value

    _normalize(config)

    config["WARNINGS"] = warnings

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

    if config["ICON"]:
        icon = Path(config["ICON"]).expanduser()

        if not icon.is_absolute():
            icon = project_root / icon

        config["ICON"] = icon

    if not config["NAME"]:
        config["NAME"] = project_root.name

    if not isinstance(config["VERSION"], str) or not config["VERSION"].strip():
        raise CommandError("VERSION must be a non-empty string.")

    if not config["PUBLISHER"]:
        config["PUBLISHER"] = config["NAME"]

    if not isinstance(config["PUBLISHER"], str):
        raise CommandError("PUBLISHER must be a string.")

    if not config["EXECUTABLE_NAME"]:
        config["EXECUTABLE_NAME"] = make_safe_filename(config["NAME"])

    validate_executable_name(config["EXECUTABLE_NAME"])

    settings_module = getattr(settings, "SETTINGS_MODULE", None) or os.environ.get(
        "DJANGO_SETTINGS_MODULE"
    )

    if not settings_module:
        raise CommandError("Could not determine DJANGO_SETTINGS_MODULE for the build.")

    config["SETTINGS_MODULE"] = settings_module
    config["WSGI_APPLICATION"] = getattr(settings, "WSGI_APPLICATION", None)
