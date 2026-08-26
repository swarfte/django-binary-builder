"""Entry executable construction.

The bundle's ``<EXECUTABLE_NAME>.exe`` is a dependency-free PyInstaller
stub: it only starts the portable runtime bundled next to it. No
project code is ever frozen, which keeps PyInstaller usage limited to
its most reliable form.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from django.core.management.base import CommandError

from django_binary_builder.builders import render_template
from django_binary_builder.context import BuildContext


def build_stub(
    context: BuildContext,
    *,
    emit: Callable[[str], None],
) -> Path:
    """Generate, compile and place the entry executable."""

    stub_path = render_template(
        "stub.py.j2",
        output_path=context.generated_dir / "stub.py",
        context={},
    )

    emit("Building the entry executable with PyInstaller...")

    _run_pyinstaller(context, stub_path)

    _place_stub_into_bundle(context)

    if not context.executable_path.is_file():
        raise CommandError(
            "The entry executable was not created: "
            f"{context.executable_path}"
        )

    emit(f"Entry executable created: {context.executable_path}")

    return context.executable_path


def _run_pyinstaller(context: BuildContext, stub_path: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        context.executable_name,
        "--workpath",
        str(context.work_dir / "stub-build"),
        "--distpath",
        str(context.work_dir / "stub-dist"),
        "--specpath",
        str(context.generated_dir),
        str(stub_path),
    ]

    if context.icon:
        command.extend(["--icon", str(context.icon)])

    result = subprocess.run(
        command,
        cwd=context.project_root,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            f"PyInstaller failed with exit code {result.returncode}."
        )


def _place_stub_into_bundle(context: BuildContext) -> None:
    """Move the PyInstaller output to the bundle root.

    PyInstaller always creates a ``<name>`` subdirectory below the
    dist path; the executable and its ``_internal`` directory are
    moved up one level so the bundle root holds ``AppName.exe``,
    ``_internal/``, ``runtime/`` and ``app/`` side by side.
    """

    stub_output = context.work_dir / "stub-dist" / context.executable_name

    if not stub_output.is_dir():
        raise CommandError(
            f"PyInstaller output directory was not found: {stub_output}"
        )

    context.bundle_dir.mkdir(parents=True, exist_ok=True)

    for entry in stub_output.iterdir():
        target = context.bundle_dir / entry.name

        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

        shutil.move(str(entry), str(target))

    shutil.rmtree(context.work_dir / "stub-dist", ignore_errors=True)
