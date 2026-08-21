"""Launcher and runtime defaults generation."""

from pathlib import Path
from typing import Any

from django.core.management.base import CommandError

from django_binary_builder.builders import render_template
from django_binary_builder.context import BuildContext
from django_binary_builder.discovery.django_project import (
    split_wsgi_application,
)
from django_binary_builder.runtime.state import STATE_SCHEMA_VERSION


def generate_launcher(context: BuildContext) -> Path:
    """Generate the Python entry point used by PyInstaller."""

    if not context.wsgi_application:
        raise CommandError("WSGI_APPLICATION is not configured in Django settings.")

    try:
        wsgi_module, wsgi_object = split_wsgi_application(context.wsgi_application)
    except ValueError as error:
        raise CommandError(str(error)) from error

    return render_template(
        "launcher.py.j2",
        output_path=context.launcher_path,
        context={
            "project_root": str(context.project_root),
            "settings_module": context.settings_module,
            "wsgi_module": wsgi_module,
            "wsgi_object": wsgi_object,
            "snapshot_filename": context.config["ENVIRONMENT"]["SNAPSHOT_FILENAME"],
        },
    )


def generate_runtime_defaults(context: BuildContext) -> Path:
    """Generate the runtime defaults bundled with the application."""

    defaults = build_runtime_defaults(context)

    return render_template(
        "runtime-defaults.json.j2",
        output_path=context.runtime_defaults_path,
        context={"defaults": defaults},
    )


def build_runtime_defaults(context: BuildContext) -> dict[str, Any]:
    """Build the runtime defaults payload from the build settings."""

    config = context.config

    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "app_name": context.app_name,
        "app_version": context.app_version,
        "server": {
            "host": config["SERVER"]["HOST"],
            "port": config["SERVER"]["PORT"],
            "threads": config["SERVER"]["THREADS"],
            "open_browser": config["SERVER"]["OPEN_BROWSER"],
        },
        "database": {
            "mode": config["DATABASE"]["MODE"],
            "run_migrations": config["DATABASE"]["RUN_MIGRATIONS"],
            "migration_timeout": config["DATABASE"]["MIGRATION_TIMEOUT"],
            "sqlite": {
                "filename": config["DATABASE"]["SQLITE"]["FILENAME"],
                "copy_initial_database": config["DATABASE"]["SQLITE"][
                    "COPY_INITIAL_DATABASE"
                ],
                "initial_database": _optional_str(
                    config["DATABASE"]["SQLITE"]["INITIAL_DATABASE"]
                ),
            },
            "external": {
                "use_project_settings": config["DATABASE"]["EXTERNAL"][
                    "USE_PROJECT_SETTINGS"
                ],
                "config_file": config["DATABASE"]["EXTERNAL"]["CONFIG_FILE"],
                "allow_environment_variables": config["DATABASE"]["EXTERNAL"][
                    "ALLOW_ENVIRONMENT_VARIABLES"
                ],
                "test_connection_on_startup": config["DATABASE"]["EXTERNAL"][
                    "TEST_CONNECTION_ON_STARTUP"
                ],
            },
        },
        "initial_admin": {
            "enabled": config["INITIAL_ADMIN"]["ENABLED"],
            "sqlite_only": config["INITIAL_ADMIN"]["SQLITE_ONLY"],
            "username": config["INITIAL_ADMIN"]["USERNAME"],
            "password": config["INITIAL_ADMIN"]["PASSWORD"],
            "email": config["INITIAL_ADMIN"]["EMAIL"],
            "extra_fields": config["INITIAL_ADMIN"]["EXTRA_FIELDS"],
            "require_password_change": config["INITIAL_ADMIN"][
                "REQUIRE_PASSWORD_CHANGE"
            ],
            "reset_password_if_user_exists": config["INITIAL_ADMIN"][
                "RESET_PASSWORD_IF_USER_EXISTS"
            ],
        },
        "runtime": {
            "company_directory": context.runtime_company_directory,
            "application_directory": context.runtime_application_directory,
            "data_directory": _optional_str(config["RUNTIME"]["DATA_DIRECTORY"]),
            "log_directory": config["RUNTIME"]["LOG_DIRECTORY"],
            "media_directory": config["RUNTIME"]["MEDIA_DIRECTORY"],
            "config_directory": config["RUNTIME"]["CONFIG_DIRECTORY"],
        },
    }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None

    return str(value)
