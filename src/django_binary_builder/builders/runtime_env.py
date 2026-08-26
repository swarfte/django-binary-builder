"""Portable Python runtime construction.

The bundle ships a full copy of the build machine's CPython
installation plus every project dependency installed with pip. No
code is frozen, so any library that works in the development
environment works in the packaged application.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from django.core.management.base import CommandError

from django_binary_builder.context import BuildContext

COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.pyo",
)


def build_portable_runtime(
    context: BuildContext,
    *,
    emit: Callable[[str], None],
) -> Path:
    """Create ``bundle/runtime`` with Python and all requirements."""

    runtime_dir = context.runtime_dir

    copy_python_runtime(context, runtime_dir, emit=emit)

    bootstrap_pip(runtime_dir, emit=emit)

    install_requirements(context, runtime_dir, emit=emit)

    return runtime_dir


def copy_python_runtime(
    context: BuildContext,
    runtime_dir: Path,
    *,
    emit: Callable[[str], None],
) -> None:
    """Copy the base CPython installation into the bundle."""

    base_prefix = Path(sys.base_prefix).resolve()

    _validate_base_prefix(base_prefix)

    emit(f"Copying Python runtime: {base_prefix}")

    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)

    shutil.copytree(
        base_prefix,
        runtime_dir,
        ignore=COPY_IGNORE,
        symlinks=False,
    )

    python_exe = runtime_dir / "python.exe"

    if not python_exe.is_file():
        raise CommandError(
            f"The copied Python runtime is missing python.exe: {python_exe}"
        )

    site_packages = _site_packages_dir(runtime_dir)

    if site_packages.exists():
        # Start from a clean site-packages so the bundle only
        # contains what the project actually needs.
        shutil.rmtree(site_packages)

    site_packages.mkdir(parents=True, exist_ok=True)

    _remove_stale_venv_markers(runtime_dir)
    _remove_externally_managed_marker(runtime_dir)

    emit(f"Python runtime copied: {runtime_dir}")


def bootstrap_pip(
    runtime_dir: Path,
    *,
    emit: Callable[[str], None],
) -> None:
    """Install pip into the copied runtime using the bundled wheels."""

    python_exe = runtime_dir / "python.exe"

    emit("Bootstrapping pip (ensurepip)...")

    result = subprocess.run(
        [
            str(python_exe),
            "-m",
            "ensurepip",
            "--upgrade",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            "ensurepip failed inside the portable runtime:\n"
            f"{result.stderr or result.stdout}"
        )


def install_requirements(
    context: BuildContext,
    runtime_dir: Path,
    *,
    emit: Callable[[str], None],
) -> None:
    """pip install the resolved requirements into the runtime."""

    requirements_path = context.requirements_path

    if requirements_path is None or not requirements_path.is_file():
        raise CommandError(
            "The resolved requirements file is missing; the build cannot "
            "install dependencies."
        )

    python_exe = runtime_dir / "python.exe"

    emit(f"Installing dependencies from {requirements_path} ...")

    result = subprocess.run(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "--no-warn-script-location",
            "--disable-pip-version-check",
            "-r",
            str(requirements_path),
        ],
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            "pip install failed inside the portable runtime with exit "
            f"code {result.returncode}."
        )

    emit("Dependencies installed.")


def verify_runtime(context: BuildContext) -> None:
    """Verify the runtime can execute and import Django."""

    python_exe = context.runtime_dir / "python.exe"

    result = subprocess.run(
        [str(python_exe), "-c", "import django, waitress, webview, dotenv"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            "The portable runtime failed its import check:\n"
            f"{result.stderr or result.stdout}"
        )


def _site_packages_dir(runtime_dir: Path) -> Path:
    return runtime_dir / "Lib" / "site-packages"


def _remove_stale_venv_markers(runtime_dir: Path) -> None:
    # The base installation itself is never a venv, but a stale
    # pyvenv.cfg next to a copied interpreter would break it.
    pyvenv_cfg = runtime_dir / "pyvenv.cfg"

    if pyvenv_cfg.exists():
        pyvenv_cfg.unlink()


def _remove_externally_managed_marker(runtime_dir: Path) -> None:
    # uv and system installations are marked PEP 668 "externally
    # managed", which makes pip refuse every operation. The copy in
    # the bundle is managed by the build, not by uv, so the marker is
    # removed to let ensurepip and pip work.
    for candidate in (
        runtime_dir / "Lib" / "EXTERNALLY-MANAGED",
        runtime_dir / "EXTERNALLY-MANAGED",
    ):
        if candidate.is_file():
            candidate.unlink()


def _validate_base_prefix(base_prefix: Path) -> None:
    if not (base_prefix / "python.exe").is_file():
        raise CommandError(
            "The current Python installation cannot be copied "
            f"(python.exe not found in {base_prefix})."
        )

    if "WindowsApps" in base_prefix.parts:
        raise CommandError(
            "The Microsoft Store Python cannot be packaged. Install "
            "Python from python.org (or via uv) and rebuild from its "
            "virtual environment."
        )
