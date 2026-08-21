"""Discovery of Django project facts needed at build time."""

import importlib.util
from pathlib import Path

from django.apps import apps
from django.conf import settings


def get_project_root() -> Path:
    return Path(settings.BASE_DIR).resolve()


def get_settings_module() -> str:
    return settings.SETTINGS_MODULE


def get_wsgi_application() -> str | None:
    return getattr(settings, "WSGI_APPLICATION", None)


def split_wsgi_application(wsgi_application: str) -> tuple[str, str]:
    try:
        module_name, object_name = wsgi_application.rsplit(".", 1)
    except ValueError as error:
        raise ValueError(
            f"Invalid WSGI_APPLICATION value: {wsgi_application!r}"
        ) from error

    if not module_name or not object_name:
        raise ValueError(f"Invalid WSGI_APPLICATION value: {wsgi_application!r}")

    return module_name, object_name


def module_is_importable(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ImportError, ValueError:
        return False


def get_installed_app_names() -> list[str]:
    return sorted({config.name for config in apps.get_app_configs()})


def get_static_root() -> Path | None:
    static_root = getattr(settings, "STATIC_ROOT", None)

    if not static_root:
        return None

    return Path(static_root)


def get_settings_database_engine() -> str:
    return str(settings.DATABASES.get("default", {}).get("ENGINE", ""))


def get_project_package_name(settings_module: str) -> str | None:
    root_package = settings_module.split(".")[0]

    if "." not in settings_module:
        return None

    return root_package if module_is_importable(root_package) else None
