from copy import deepcopy
from pathlib import Path
from typing import Any

from django.conf import settings

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


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    result = deepcopy(base)

    for key, value in override.items():
        existing_value = result.get(key)

        if isinstance(existing_value, dict) and isinstance(value, dict):
            result[key] = deep_merge(existing_value, value)
        else:
            result[key] = value

    return result


def get_builder_settings() -> dict[str, Any]:
    user_settings = getattr(
        settings,
        "DJANGO_BINARY_BUILDER",
        {},
    )

    config = deep_merge(DEFAULTS, user_settings)

    project_root = Path(settings.BASE_DIR).resolve()

    if not config["NAME"]:
        config["NAME"] = project_root.name

    if not config["EXECUTABLE_NAME"]:
        config["EXECUTABLE_NAME"] = make_safe_filename(
            config["NAME"]
        )

    output_dir = Path(config["OUTPUT_DIR"])

    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    work_dir = Path(config["WORK_DIR"])

    if not work_dir.is_absolute():
        work_dir = project_root / work_dir

    if config["ICON"]:
        icon_path = Path(config["ICON"])

        if not icon_path.is_absolute():
            icon_path = project_root / icon_path

        config["ICON"] = icon_path.resolve()

    config["PROJECT_ROOT"] = project_root
    config["OUTPUT_DIR"] = output_dir.resolve()
    config["WORK_DIR"] = work_dir.resolve()
    config["SETTINGS_MODULE"] = settings.SETTINGS_MODULE
    config["WSGI_APPLICATION"] = settings.WSGI_APPLICATION

    return config


def make_safe_filename(value: str) -> str:
    characters: list[str] = []

    for character in value.strip():
        if character.isalnum() or character in {"-", "_"}:
            characters.append(character)
        else:
            characters.append("-")

    normalized = "".join(characters)

    while "--" in normalized:
        normalized = normalized.replace("--", "-")

    normalized = normalized.strip("-")

    return normalized or "django-binary-builder"