"""PyInstaller spec generation and execution."""

import subprocess
import sys
from pathlib import Path

from django.core.management.base import CommandError

from django_binary_builder.builders import render_template
from django_binary_builder.context import BuildContext
from django_binary_builder.discovery.database import (
    get_database_hidden_imports,
)
from django_binary_builder.discovery.django_project import (
    get_project_package_name,
    get_settings_database_engine,
    get_static_root,
    split_wsgi_application,
)

RUNTIME_DATA_DESTINATION = "runtime"
STATIC_DATA_DESTINATION = "static"

BUILD_ONLY_EXCLUDED_MODULES = (
    "django_binary_builder.builders",
    "django_binary_builder.management",
    "django_binary_builder.platforms",
    "django_binary_builder.templates",
)


def generate_pyinstaller_spec(context: BuildContext) -> Path:
    """Generate the PyInstaller spec file for the application."""

    build_config = context.config["BUILD"]
    wsgi_module, _ = split_wsgi_application(context.wsgi_application)

    extra_datas: list[tuple[str, str]] = []

    extra_datas.append(
        (
            str(context.runtime_environment_path),
            RUNTIME_DATA_DESTINATION,
        )
    )

    extra_datas.append(
        (
            str(context.runtime_defaults_path),
            RUNTIME_DATA_DESTINATION,
        )
    )

    if build_config["COLLECT_STATIC"]:
        static_root = get_static_root()

        if static_root is not None:
            extra_datas.append((str(static_root), STATIC_DATA_DESTINATION))

    sqlite_config = context.config["DATABASE"]["SQLITE"]

    if (
        context.uses_sqlite
        and sqlite_config["COPY_INITIAL_DATABASE"]
        and sqlite_config["INITIAL_DATABASE"]
    ):
        extra_datas.append(
            (
                str(Path(sqlite_config["INITIAL_DATABASE"])),
                RUNTIME_DATA_DESTINATION,
            )
        )

    extra_datas.extend(get_extra_data(context))

    driver_hidden_imports = []

    if context.uses_external_database:
        engine = get_settings_database_engine()
        driver_hidden_imports = get_database_hidden_imports(engine)

    excluded_modules = list(
        dict.fromkeys(
            [
                *build_config["EXCLUDED_MODULES"],
                *BUILD_ONLY_EXCLUDED_MODULES,
            ]
        )
    )

    return render_template(
        "application.spec.j2",
        output_path=context.spec_path,
        context={
            "project_root": str(context.project_root),
            "project_package": get_project_package_name(context.settings_module),
            "settings_module": context.settings_module,
            "wsgi_module": wsgi_module,
            "launcher_path": str(context.launcher_path),
            "executable_name": context.executable_name,
            "hidden_imports": build_config["HIDDEN_IMPORTS"],
            "driver_hidden_imports": driver_hidden_imports,
            "excluded_modules": excluded_modules,
            "extra_datas": extra_datas,
            "console": build_config["CONSOLE"],
            "icon": (str(context.config["ICON"]) if context.config["ICON"] else None),
        },
    )


def run_pyinstaller(context: BuildContext) -> None:
    """Run PyInstaller with the generated spec and verify artifacts."""

    if not context.spec_path.is_file():
        raise CommandError(f"PyInstaller spec file does not exist: {context.spec_path}")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        str(context.pyinstaller_build_dir),
        "--distpath",
        str(context.pyinstaller_dist_dir),
        str(context.spec_path),
    ]

    result = subprocess.run(
        command,
        cwd=context.project_root,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            f"PyInstaller build failed with exit code {result.returncode}."
        )

    verify_pyinstaller_artifacts(context)


def verify_pyinstaller_artifacts(context: BuildContext) -> None:
    """Verify that the expected onedir bundle exists."""

    if not context.bundle_dir.is_dir():
        raise CommandError(
            "PyInstaller completed, but the expected application "
            f"directory was not found: {context.bundle_dir}"
        )

    if not context.executable_path.is_file():
        raise CommandError(
            "PyInstaller completed, but the expected executable was "
            f"not found: {context.executable_path}"
        )


def get_extra_data(context: BuildContext) -> list[tuple[str, str]]:
    """Resolve and validate user-configured extra data entries."""

    extra_data: list[tuple[str, str]] = []

    for item in context.config["BUILD"]["EXTRA_DATA"]:
        if not isinstance(item, dict):
            raise CommandError("Each BUILD.EXTRA_DATA entry must be a dictionary.")

        source_value = item.get("source")

        if not source_value:
            raise CommandError(
                "Each BUILD.EXTRA_DATA entry must contain a 'source' value."
            )

        source = Path(source_value)

        if not source.is_absolute():
            source = context.project_root / source

        source = source.resolve()

        if not source.exists():
            raise CommandError(f"Extra data source does not exist: {source}")

        destination = item.get("destination", source.name)

        extra_data.append((str(source), str(destination)))

    return extra_data
