"""Windows build pipeline orchestration.

This module coordinates the builders; it contains no Jinja template
details.
"""

import os
import shutil
import sys
from typing import Any

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError, OutputWrapper

from django_binary_builder.builders.inno_setup import (
    find_inno_setup,
    generate_inno_script,
    run_inno_setup,
)
from django_binary_builder.builders.launcher import (
    generate_launcher,
    generate_runtime_defaults,
)
from django_binary_builder.builders.pyinstaller import (
    generate_pyinstaller_spec,
    get_extra_data,
    run_pyinstaller,
)
from django_binary_builder.context import BuildContext
from django_binary_builder.discovery.database import (
    driver_install_hint,
    resolve_database_driver,
)
from django_binary_builder.discovery.dependencies import (
    check_build_dependencies,
)
from django_binary_builder.discovery.django_project import (
    get_settings_database_engine,
    get_static_root,
    module_is_importable,
    split_wsgi_application,
)
from django_binary_builder.environment import prepare_build_environment
from django_binary_builder.environment.snapshot import (
    write_environment_snapshot,
)
from django_binary_builder.environment.validation import (
    summarize_variables,
    verify_snapshot_selection,
)
from django_binary_builder.platforms.base import PipelineOptions


def run_windows_pipeline(
    *,
    context: BuildContext,
    stdout: OutputWrapper,
    style: Any,
    options: PipelineOptions,
) -> Any | None:
    """Execute the complete Windows build pipeline."""

    def say(message: str) -> None:
        stdout.write(message)

    def ok(message: str) -> None:
        stdout.write(f"[OK] {message}")

    def warn(message: str) -> None:
        stdout.write(style.WARNING(message))

    say(style.MIGRATE_HEADING("Loading build environment..."))

    env_result = prepare_build_environment(
        config=context.config,
        project_root=context.project_root,
        emit_warning=warn,
    )

    run_windows_preflight(
        context=context,
        stdout=stdout,
        env_result=env_result,
        require_inno=not options.skip_installer,
    )

    if options.check:
        stdout.write(style.SUCCESS("All Windows build checks passed."))
        return None

    prepare_directories(context)

    # The snapshot is written after directory preparation because a
    # clean build removes the working directory.
    write_environment_snapshot(
        context.runtime_environment_path,
        env_result.variables,
    )

    say("Running Django system checks...")

    try:
        call_command("check", verbosity=0)
    except Exception as error:
        raise CommandError(f"Django system check failed: {error}") from error

    if context.config["BUILD"]["COLLECT_STATIC"]:
        say("Collecting static files...")

        call_command(
            "collectstatic",
            interactive=False,
            verbosity=0,
            clear=True,
        )

        static_root = get_static_root()

        if static_root is not None:
            ok(f"Static files collected: {static_root}")

    say("Generating runtime defaults...")

    generate_runtime_defaults(context)

    ok(f"Runtime defaults generated: {context.runtime_defaults_path}")

    say("Generating launcher...")

    generate_launcher(context)

    ok(f"Launcher generated: {context.launcher_path}")

    say("Generating PyInstaller spec...")

    generate_pyinstaller_spec(context)

    ok(f"PyInstaller spec generated: {context.spec_path}")

    if not options.skip_installer:
        say("Generating Inno Setup script...")

        generate_inno_script(context)

        ok(f"Inno Setup script generated: {context.inno_script_path}")

    if options.generate_only:
        stdout.write(
            style.SUCCESS("Build files generated successfully (--generate-only).")
        )
        return None

    say("Running PyInstaller...")

    run_pyinstaller(context)

    ok(f"Application bundle created: {context.bundle_dir}")

    if options.skip_installer:
        stdout.write(
            style.SUCCESS("Application bundle created successfully (--skip-installer).")
        )
        return None

    say("Running Inno Setup...")

    installer_path = run_inno_setup(context)

    ok(f"Windows installer created: {installer_path}")

    print_build_summary(
        context,
        stdout=stdout,
        style=style,
        env_result=env_result,
    )

    return installer_path


def run_windows_preflight(
    *,
    context: BuildContext,
    stdout: OutputWrapper,
    env_result: Any,
    require_inno: bool,
) -> None:
    """Validate every requirement before building."""

    def ok(message: str) -> None:
        stdout.write(f"[OK] {message}")

    if sys.platform != "win32":
        raise CommandError("Windows builds must be performed on a Windows host.")

    check_build_dependencies(stdout.write)

    if not context.project_root.is_dir():
        raise CommandError(f"Project root does not exist: {context.project_root}")

    ok(f"Project root: {context.project_root}")

    if not context.settings_module or not module_is_importable(context.settings_module):
        raise CommandError(
            f"The Django settings module is not importable: {context.settings_module}"
        )

    if not context.wsgi_application:
        raise CommandError("WSGI_APPLICATION is not configured in Django settings.")

    try:
        wsgi_module, _ = split_wsgi_application(context.wsgi_application)
    except ValueError as error:
        raise CommandError(str(error)) from error

    if not module_is_importable(wsgi_module):
        raise CommandError(
            f"The WSGI application module is not importable: {wsgi_module}"
        )

    ok(f"WSGI application: {context.wsgi_application}")

    build_config = context.config["BUILD"]

    if build_config["MODE"] != "onedir":
        raise CommandError("Only the 'onedir' build mode is supported in this version.")

    if build_config["COLLECT_STATIC"]:
        static_root = get_static_root()

        if static_root is None:
            raise CommandError(
                "STATIC_ROOT must be configured because "
                "BUILD.COLLECT_STATIC is enabled."
            )

        if static_root.is_file():
            raise CommandError(f"STATIC_ROOT must be a directory: {static_root}")

        ok(f"STATIC_ROOT: {static_root}")

    icon = context.config.get("ICON")

    if icon:
        icon_path = icon

        if not icon_path.is_file():
            raise CommandError(f"Windows icon file was not found: {icon_path}")

        if icon_path.suffix.lower() != ".ico":
            raise CommandError("The Windows application icon must use the .ico format.")

        ok(f"Windows icon: {icon_path}")

    if not context.app_version:
        raise CommandError("The application version must not be empty.")

    ok(
        f"Application: {context.app_name} "
        f"{context.app_version} "
        f"({context.executable_name})"
    )

    _check_output_parent_writable(context.release_dir)

    environment_config = context.config["ENVIRONMENT"]

    verify_snapshot_selection(
        env_result.variables,
        environment_config["EXCLUDE"],
    )

    ok(
        "Environment variables selected for packaging: "
        + summarize_variables(env_result.variables)
    )

    database_config = context.config["DATABASE"]

    if database_config["MODE"] not in {"sqlite", "external"}:
        raise CommandError("DATABASE.MODE must be 'sqlite' or 'external'.")

    sqlite_config = database_config["SQLITE"]

    if (
        context.uses_sqlite
        and sqlite_config["COPY_INITIAL_DATABASE"]
        and sqlite_config["INITIAL_DATABASE"]
        and not sqlite_config["INITIAL_DATABASE"].is_file()
    ):
        raise CommandError(
            "DATABASE.SQLITE.INITIAL_DATABASE does not exist: "
            f"{sqlite_config['INITIAL_DATABASE']}"
        )

    admin_config = context.config["INITIAL_ADMIN"]

    if admin_config["ENABLED"] and (
        context.uses_sqlite or not admin_config["SQLITE_ONLY"]
    ):
        for required_app in ("django.contrib.auth", "django.contrib.contenttypes"):
            if not apps.is_installed(required_app):
                raise CommandError(
                    f"'{required_app}' must be in INSTALLED_APPS when "
                    "INITIAL_ADMIN is enabled."
                )

        ok("Initial administrator creation is enabled.")

    if context.uses_external_database:
        engine = get_settings_database_engine()
        driver = resolve_database_driver(engine)

        if driver.driver_module is None and engine not in (
            "django.db.backends.sqlite3",
        ):
            raise CommandError(
                f"The database driver for '{engine}' is not installed. "
                f"Install it with: {driver_install_hint(engine)}"
            )

        if driver.driver_module:
            ok(f"Database driver: {driver.driver_module} ({engine})")

    get_extra_data(context)

    ok("Extra data entries are valid.")

    if require_inno:
        inno_compiler = find_inno_setup(context)

        if inno_compiler is None:
            raise CommandError(
                "Inno Setup 7 was not found. Install Inno Setup 7 or "
                "configure DJANGO_BINARY_BUILDER['WINDOWS']"
                "['INNO_SETUP_COMPILER']."
            )

        ok(f"Inno Setup: {inno_compiler}")


def prepare_directories(context: BuildContext) -> None:
    """Clean and create the build working directories."""

    if context.config["BUILD"]["CLEAN"] and context.work_dir.exists():
        shutil.rmtree(context.work_dir)

    for directory in (
        context.generated_dir,
        context.pyinstaller_build_dir,
        context.pyinstaller_dist_dir,
        context.release_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def print_build_summary(
    context: BuildContext,
    *,
    stdout: OutputWrapper,
    style: Any,
    env_result: Any,
) -> None:
    """Print a sanitized build summary; no secret values are shown."""

    stdout.write(style.MIGRATE_HEADING("Build summary"))

    stdout.write(f"  Bundle: {context.bundle_dir}")
    stdout.write(f"  Executable: {context.executable_path}")
    stdout.write(f"  Installer: {context.installer_path}")

    if env_result.enabled:
        stdout.write(
            "  Environment variables packaged: "
            + summarize_variables(env_result.variables)
        )
    else:
        stdout.write(
            "  Environment variables packaged: none (--no-env or "
            "ENVIRONMENT.ENABLED=False)"
        )

    if env_result.secret_names:
        stdout.write(
            style.WARNING(
                "  High risk: sensitive variables are embedded in "
                "plain text: " + ", ".join(env_result.secret_names)
            )
        )

    if context.config["INITIAL_ADMIN"]["ENABLED"] and context.uses_sqlite:
        stdout.write(
            style.WARNING(
                "  An initial administrator will be created on first "
                "run using a publicly documented default password. "
                "Change it immediately after the first login."
            )
        )

    stdout.write(style.SUCCESS(f"Build completed: {context.installer_path}"))


def _check_output_parent_writable(release_dir) -> None:
    candidate = release_dir

    while not candidate.exists():
        candidate = candidate.parent

    if not os.access(candidate, os.W_OK):
        raise CommandError(f"The output directory is not writable: {release_dir}")
