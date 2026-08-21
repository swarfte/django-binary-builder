"""Build dependency availability checks."""

import importlib.util
from collections.abc import Callable

from django.core.management.base import CommandError

REQUIRED_BUILD_MODULES = (
    "PyInstaller",
    "jinja2",
    "waitress",
    "dotenv",
    "webview",
)


def is_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def check_build_dependencies(
    emit: Callable[[str], None] = lambda message: None,
) -> None:
    missing = [
        module_name
        for module_name in REQUIRED_BUILD_MODULES
        if not is_module_available(module_name)
    ]

    if missing:
        raise CommandError(
            "Required Python packages are missing: "
            + ", ".join(missing)
            + ". Install the django-binary-builder dependencies "
            "(uv sync)."
        )

    emit("[OK] Required Python packages are installed.")
