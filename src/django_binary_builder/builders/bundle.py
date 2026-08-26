"""Assemble the ``bundle/app`` directory: the Django project copy,
collected static files, the bundled ``.env`` and the generated
launcher.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError

from django_binary_builder.builders import render_template
from django_binary_builder.context import BuildContext

EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "ENV",
        "node_modules",
        ".django-binary-builder",
        "release",
        "staticfiles",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        ".hypothesis",
        "htmlcov",
        ".idea",
        ".vscode",
        "build",
        "dist",
    }
)

EXCLUDED_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
)

EXCLUDED_FILE_NAMES = frozenset(
    {
        ".coverage",
        "db.sqlite3-journal",
    }
)


def assemble_project_bundle(
    context: BuildContext,
    *,
    emit: Callable[[str], None],
) -> Path:
    """Copy the project, collect static files and add the launcher."""

    copy_project(context)

    emit(f"Project copied: {context.app_dir}")

    copy_builder_library(context)

    emit("django-binary-builder library copied into the bundle")

    collect_static_files(context)

    emit(f"Static files collected: {context.static_dir}")

    generate_launcher(context)

    emit(f"Launcher generated: {context.app_dir / 'launcher.py'}")

    environment_file = bundled_environment_file(context)

    if environment_file is not None:
        emit(f"Bundled environment file: {environment_file}")

    database_file = bundled_database_file(context)

    if database_file is not None:
        emit(
            "Bundled SQLite database will seed the application on first "
            f"run: {database_file}"
        )

    return context.app_dir


def copy_project(context: BuildContext) -> None:
    """Copy the project source tree into ``bundle/app``."""

    if context.app_dir.exists():
        shutil.rmtree(context.app_dir)

    shutil.copytree(
        context.project_root,
        context.app_dir,
        ignore=_ignore_project_entry,
    )


def copy_builder_library(context: BuildContext) -> None:
    """Copy django-binary-builder next to the project.

    Projects must list the library in ``INSTALLED_APPS`` to run the
    ``binary`` command, so the packaged application needs the package
    importable at runtime.
    """

    import django_binary_builder

    source = Path(django_binary_builder.__file__).resolve().parent
    target = context.app_dir / "django_binary_builder"

    if target.exists():
        shutil.rmtree(target)

    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def collect_static_files(context: BuildContext) -> None:
    """Collect static files into the bundle, zero configuration.

    ``STATIC_ROOT`` is always pointed at the bundle's own
    ``staticfiles`` directory for the collection so the packaged
    application has a deterministic location to serve from, regardless
    of how (or whether) the project configured it.
    """

    from django.conf import settings as django_settings

    static_root = context.static_dir

    if static_root.exists():
        shutil.rmtree(static_root)

    django_settings.STATIC_ROOT = static_root

    try:
        call_command(
            "collectstatic",
            interactive=False,
            verbosity=0,
            clear=True,
        )
    except Exception as error:
        raise CommandError(f"collectstatic failed: {error}") from error


def generate_launcher(context: BuildContext) -> Path:
    """Render the self-contained launcher into ``bundle/app``."""

    return render_template(
        "launcher.py.j2",
        output_path=context.app_dir / "launcher.py",
        context={
            "app_name": context.app_name,
            "publisher": context.publisher,
            "settings_module": context.settings_module,
            "wsgi_application": context.wsgi_application or "",
        },
    )


def _ignore_project_entry(directory: str, entries: list[str]) -> set[str]:
    ignored = {
        entry
        for entry in entries
        if entry in EXCLUDED_DIRECTORIES
        or entry in EXCLUDED_FILE_NAMES
        or entry.endswith(EXCLUDED_FILE_SUFFIXES)
    }

    return ignored


def bundled_environment_file(context: BuildContext) -> Path | None:
    """Return the bundled ``.env`` path when the project ships one."""

    environment_file = context.app_dir / ".env"

    if environment_file.is_file():
        return environment_file

    return None


def bundled_database_file(context: BuildContext) -> Path | None:
    """Return the bundled SQLite database path when present."""

    database_file = context.app_dir / "db.sqlite3"

    if database_file.is_file():
        return database_file

    return None
