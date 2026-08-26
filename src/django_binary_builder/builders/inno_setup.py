"""Inno Setup script generation and compilation."""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from django.core.management.base import CommandError

from django_binary_builder.builders import render_template
from django_binary_builder.context import BuildContext

DEFAULT_INNO_PATHS = (
    Path(r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
)

COMPILER_ENVIRONMENT_VARIABLE = "DJANGO_BINARY_INNO_COMPILER"

APP_ID_NAMESPACE = uuid.UUID("f487346d-7877-4d7a-86a4-b143ddf81462")


def find_inno_setup() -> Path | None:
    """Find the Inno Setup command-line compiler."""

    configured = os.environ.get(COMPILER_ENVIRONMENT_VARIABLE)

    if configured:
        candidate = Path(configured).expanduser()

        if candidate.is_file():
            return candidate.resolve()

        return None

    path_from_environment = shutil.which("ISCC.exe")

    if path_from_environment:
        return Path(path_from_environment).resolve()

    for candidate in DEFAULT_INNO_PATHS:
        if candidate.is_file():
            return candidate.resolve()

    return None


def generate_inno_script(context: BuildContext) -> Path:
    """Generate ``installer.iss`` from the bundled template."""

    publisher = context.publisher or "Unknown Publisher"

    return render_template(
        "installer.iss.j2",
        output_path=context.inno_script_path,
        encoding="utf-8-sig",
        context={
            "app_name": escape_inno_value(context.app_name),
            "app_version": escape_inno_value(context.app_version),
            "publisher": escape_inno_value(publisher),
            "executable_name": escape_inno_value(context.executable_name),
            "app_id": generate_app_id(
                publisher=publisher,
                app_name=context.app_name,
            ),
            "bundle_dir": str(context.bundle_dir),
            "release_dir": str(context.release_dir),
            "installer_filename": context.installer_filename.removesuffix(".exe"),
            "icon": (str(context.icon) if context.icon else None),
        },
    )


def run_inno_setup(context: BuildContext) -> Path:
    """Compile the installer script and verify the Setup.exe output."""

    compiler_path = find_inno_setup()

    if compiler_path is None:
        raise CommandError(
            "Inno Setup compiler was not found. Install Inno Setup 7 or "
            f"set the {COMPILER_ENVIRONMENT_VARIABLE} environment variable."
        )

    if not context.inno_script_path.is_file():
        raise CommandError(
            f"Inno Setup script does not exist: {context.inno_script_path}"
        )

    if not context.bundle_dir.is_dir():
        raise CommandError(f"Application bundle does not exist: {context.bundle_dir}")

    result = subprocess.run(
        [str(compiler_path), str(context.inno_script_path)],
        cwd=context.project_root,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            f"Inno Setup compilation failed with exit code {result.returncode}."
        )

    return verify_installer_artifact(context)


def verify_installer_artifact(context: BuildContext) -> Path:
    """Verify that the expected installer file exists."""

    installer_path = context.installer_path

    if not installer_path.is_file():
        raise CommandError(
            "Inno Setup completed, but the expected installer was not "
            f"found: {installer_path}"
        )

    return installer_path


def generate_app_id(
    *,
    publisher: str,
    app_name: str,
) -> str:
    """Generate a stable Inno Setup AppId.

    The same publisher and application name always produce the same
    AppId; the application version never affects it.
    """

    generated_uuid = uuid.uuid5(
        APP_ID_NAMESPACE,
        f"{publisher}:{app_name}",
    )

    return "{" + str(generated_uuid).upper() + "}"


def escape_inno_value(value: str) -> str:
    """Escape double quotes for Inno Setup define strings."""

    return str(value).replace('"', '""')
