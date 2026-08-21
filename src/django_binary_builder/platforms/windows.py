import importlib.util
import shutil
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from django_binary_builder.builders.inno_setup import (
    find_inno_setup,
    generate_inno_script,
    run_inno_setup,
)
from django_binary_builder.builders.launcher import (
    generate_launcher,
)
from django_binary_builder.builders.pyinstaller import (
    generate_pyinstaller_spec,
    run_pyinstaller,
)
from django_binary_builder.context import BuildContext


def check_windows_environment(
    *,
    context: BuildContext,
    stdout: Any,
    require_inno: bool,
) -> None:
    """
    Validate all requirements for a Windows build.
    """

    check_python_module("PyInstaller")
    check_python_module("jinja2")
    check_python_module("waitress")

    stdout.write(
        "[OK] Required Python packages are installed."
    )

    wsgi_application = getattr(
        settings,
        "WSGI_APPLICATION",
        None,
    )

    if not wsgi_application:
        raise CommandError(
            "WSGI_APPLICATION is not configured "
            "in Django settings."
        )

    stdout.write(
        "[OK] WSGI application: "
        f"{wsgi_application}"
    )

    if context.config["BUILD"]["COLLECT_STATIC"]:
        static_root = getattr(
            settings,
            "STATIC_ROOT",
            None,
        )

        if not static_root:
            raise CommandError(
                "STATIC_ROOT must be configured because "
                "BUILD.COLLECT_STATIC is enabled."
            )

        stdout.write(
            f"[OK] STATIC_ROOT: {static_root}"
        )

    icon = context.config.get("ICON")

    if icon:
        icon_path = Path(icon)

        if not icon_path.is_file():
            raise CommandError(
                "Windows icon file was not found: "
                f"{icon_path}"
            )

        if icon_path.suffix.lower() != ".ico":
            raise CommandError(
                "The Windows application icon must "
                "use the .ico file format."
            )

        stdout.write(
            f"[OK] Windows icon: {icon_path}"
        )

    if require_inno:
        inno_compiler = find_inno_setup(
            context
        )

        if inno_compiler is None:
            raise CommandError(
                "Inno Setup 6 was not found. "
                "Install Inno Setup 6 or configure "
                "DJANGO_BINARY_BUILDER['WINDOWS']"
                "['INNO_SETUP_COMPILER']."
            )

        stdout.write(
            f"[OK] Inno Setup: {inno_compiler}"
        )


def build_windows(
    *,
    context: BuildContext,
    stdout: Any,
    generate_only: bool,
    skip_installer: bool,
) -> None:
    """
    Execute the complete Windows build pipeline.
    """

    prepare_directories(context)

    stdout.write(
        "Running Django system checks..."
    )

    call_command(
        "check",
        verbosity=1,
    )

    if context.config["BUILD"]["COLLECT_STATIC"]:
        stdout.write(
            "Collecting static files..."
        )

        call_command(
            "collectstatic",
            interactive=False,
            verbosity=1,
        )

    stdout.write(
        "Generating launcher..."
    )

    generate_launcher(context)

    stdout.write(
        f"Launcher generated: {context.launcher_path}"
    )

    stdout.write(
        "Generating PyInstaller spec..."
    )

    generate_pyinstaller_spec(context)

    stdout.write(
        f"PyInstaller spec generated: "
        f"{context.spec_path}"
    )

    if not skip_installer:
        stdout.write(
            "Generating Inno Setup script..."
        )

        generate_inno_script(context)

        stdout.write(
            f"Inno Setup script generated: "
            f"{context.inno_script_path}"
        )

    if generate_only:
        stdout.write(
            "Build files generated successfully."
        )
        return

    stdout.write(
        "Running PyInstaller..."
    )

    run_pyinstaller(context)

    stdout.write(
        "Application bundle created: "
        f"{context.bundle_dir}"
    )

    if skip_installer:
        stdout.write(
            "Installer creation was skipped."
        )
        return

    stdout.write(
        "Running Inno Setup..."
    )

    installer_path = run_inno_setup(
        context
    )

    stdout.write(
        "Windows installer created: "
        f"{installer_path}"
    )


def prepare_directories(
    context: BuildContext,
) -> None:
    """
    Prepare working and output directories.
    """

    clean_enabled = context.config["BUILD"][
        "CLEAN"
    ]

    if clean_enabled and context.work_dir.exists():
        shutil.rmtree(
            context.work_dir
        )

    context.generated_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    context.pyinstaller_build_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    context.pyinstaller_dist_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    context.release_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


def check_python_module(
    module_name: str,
) -> None:
    """
    Check whether a required Python module is installed.
    """

    module_spec = importlib.util.find_spec(
        module_name
    )

    if module_spec is None:
        raise CommandError(
            "Required Python module is missing: "
            f"{module_name}"
        )