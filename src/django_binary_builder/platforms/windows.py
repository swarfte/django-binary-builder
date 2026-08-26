"""Windows build pipeline orchestration.

Pipeline overview:

1. resolve the Python pin (``.python-version``) and the dependency
   list (``requirements.txt`` / ``pyproject.toml`` / ``pip freeze``);
2. preflight-validate the project, icon and tooling;
3. build a portable Python runtime with every dependency installed;
4. assemble the project bundle (source, static files, ``.env``,
   self-contained launcher);
5. build the dependency-free entry executable stub;
6. package everything with Inno Setup into a ``Setup.exe``.
"""

import importlib.util
import shutil
from typing import Any

from django.core.management.base import CommandError, OutputWrapper

from django_binary_builder.builders.bundle import assemble_project_bundle
from django_binary_builder.builders.inno_setup import (
    find_inno_setup,
    generate_inno_script,
    run_inno_setup,
)
from django_binary_builder.builders.runtime_env import (
    build_portable_runtime,
    verify_runtime,
)
from django_binary_builder.builders.stub import build_stub
from django_binary_builder.context import BuildContext
from django_binary_builder.platforms.base import PipelineOptions
from django_binary_builder.python_version import resolve_python_version
from django_binary_builder.requirements import resolve_requirements


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

    for warning in context.config.get("WARNINGS", []):
        stdout.write(style.WARNING(warning))

    resolve_environment_inputs(context, say=say, dry_run=options.check)

    run_windows_preflight(
        context=context,
        stdout=stdout,
        require_inno=not options.skip_installer,
    )

    if options.check:
        stdout.write(style.SUCCESS("All Windows build checks passed."))
        return None

    prepare_directories(context)

    write_requirements_file(context)

    build_portable_runtime(context, emit=say)

    verify_runtime(context)

    ok(f"Portable runtime ready: {context.runtime_dir}")

    assemble_project_bundle(context, emit=say)

    build_stub(context, emit=say)

    if options.skip_installer:
        stdout.write(
            style.SUCCESS(
                "Application bundle created successfully (--skip-installer)."
            )
        )
        say(f"Bundle: {context.bundle_dir}")
        say(f"Executable: {context.executable_path}")
        return None

    say("Generating Inno Setup script...")

    generate_inno_script(context)

    ok(f"Inno Setup script generated: {context.inno_script_path}")

    say("Running Inno Setup (this can take a while)...")

    installer_path = run_inno_setup(context)

    ok(f"Windows installer created: {installer_path}")

    print_build_summary(context, stdout=stdout, style=style)

    return installer_path


def resolve_environment_inputs(
    context: BuildContext,
    *,
    say: Any,
    dry_run: bool = False,
) -> None:
    """Resolve the ``.python-version`` pin and the dependency list."""

    context.python_version = resolve_python_version(
        context.project_root,
        dry_run=dry_run,
    )

    say(f"Python version pin: {context.python_version}")

    result = resolve_requirements(context.project_root, dry_run=dry_run)

    context.requirements = result.lines

    say(f"Dependencies resolved from: {result.source}")

    if result.generated_file is not None and not dry_run:
        say(f"Generated {result.generated_file}")


def write_requirements_file(context: BuildContext) -> None:
    """Write the resolved dependency list next to the build files."""

    requirements_path = context.generated_dir / "requirements.txt"

    requirements_path.write_text(
        "\n".join(context.requirements) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    context.requirements_path = requirements_path


def run_windows_preflight(
    *,
    context: BuildContext,
    stdout: OutputWrapper,
    require_inno: bool,
) -> None:
    """Validate every requirement before building."""

    def ok(message: str) -> None:
        stdout.write(f"[OK] {message}")

    if not context.project_root.is_dir():
        raise CommandError(f"Project root does not exist: {context.project_root}")

    ok(f"Project root: {context.project_root}")

    if not context.settings_module or not _module_is_importable(
        context.settings_module
    ):
        raise CommandError(
            f"The Django settings module is not importable: {context.settings_module}"
        )

    if not context.wsgi_application:
        raise CommandError("WSGI_APPLICATION is not configured in Django settings.")

    ok(f"Settings module: {context.settings_module}")
    ok(f"WSGI application: {context.wsgi_application}")

    icon = context.icon

    if icon:
        if not icon.is_file():
            raise CommandError(f"Windows icon file was not found: {icon}")

        if icon.suffix.lower() != ".ico":
            raise CommandError("The Windows application icon must use the .ico format.")

        ok(f"Windows icon: {icon}")

    ok(
        f"Application: {context.app_name} "
        f"{context.app_version} "
        f"({context.executable_name})"
    )

    _check_output_parent_writable(context.release_dir)

    if require_inno:
        inno_compiler = find_inno_setup()

        if inno_compiler is None:
            raise CommandError(
                "Inno Setup 7 was not found. Install Inno Setup 7, add "
                "ISCC.exe to PATH, set the DJANGO_BINARY_INNO_COMPILER "
                "environment variable, or build with --skip-installer."
            )

        ok(f"Inno Setup: {inno_compiler}")


def prepare_directories(context: BuildContext) -> None:
    """Recreate the build working directories."""

    if context.work_dir.exists():
        shutil.rmtree(context.work_dir)

    for directory in (
        context.generated_dir,
        context.bundle_dir,
        context.release_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def print_build_summary(
    context: BuildContext,
    *,
    stdout: OutputWrapper,
    style: Any,
) -> None:
    """Print the final build summary."""

    stdout.write(style.MIGRATE_HEADING("Build summary"))

    stdout.write(f"  Bundle: {context.bundle_dir}")
    stdout.write(f"  Executable: {context.executable_path}")
    stdout.write(f"  Installer: {context.installer_path}")
    stdout.write(f"  Python runtime: {context.runtime_dir}")
    stdout.write(f"  Python version: {context.python_version}")
    stdout.write(f"  Dependencies: {len(context.requirements)} requirements")

    stdout.write(style.SUCCESS(f"Build completed: {context.installer_path}"))


def _module_is_importable(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _check_output_parent_writable(release_dir) -> None:
    import os

    candidate = release_dir

    while not candidate.exists():
        candidate = candidate.parent

    if not os.access(candidate, os.W_OK):
        raise CommandError(f"The output directory is not writable: {release_dir}")
