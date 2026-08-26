"""The ``binary`` management command."""

import platform as python_platform
import sys
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from django_binary_builder.conf import get_builder_settings
from django_binary_builder.context import create_build_context
from django_binary_builder.enums import TargetPlatform
from django_binary_builder.platforms.base import (
    PipelineOptions,
    validate_host_platform,
)


class Command(BaseCommand):
    help = (
        "Build the current Django project as a portable, installable "
        "desktop application."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "platform",
            choices=[member.value for member in TargetPlatform],
            help="Target platform (only 'windows' is implemented).",
        )

        parser.add_argument(
            "--check",
            action="store_true",
            help="Run preflight checks without building anything.",
        )

        parser.add_argument(
            "--skip-installer",
            action="store_true",
            help="Build the application bundle without creating the installer.",
        )

        parser.add_argument(
            "--output",
            type=Path,
            help="Override the output directory (default: release/).",
        )

    def handle(self, *args, **options):
        target = TargetPlatform(options["platform"])

        overrides: dict[str, Any] = {}

        if options.get("output"):
            overrides["OUTPUT_DIR"] = Path(options["output"])

        config = get_builder_settings(overrides)

        context = create_build_context(
            target_platform=target.value,
            config=config,
        )

        self._print_banner(context, target)

        validate_host_platform(target)

        from django_binary_builder.platforms.windows import (
            run_windows_pipeline,
        )

        run_windows_pipeline(
            context=context,
            stdout=self.stdout,
            style=self.style,
            options=PipelineOptions(
                check=options["check"],
                skip_installer=options["skip_installer"],
            ),
        )

    def _print_banner(self, context, target: TargetPlatform) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("Django Binary Builder"))

        self.stdout.write(f"Target: {target.value}")
        self.stdout.write(f"Host: {sys.platform}")
        self.stdout.write(f"Python: {python_platform.python_version()}")
        self.stdout.write(f"Project root: {context.project_root}")
        self.stdout.write(f"Django settings: {context.settings_module}")
        self.stdout.write(f"Application: {context.app_name}")
        self.stdout.write(f"Application version: {context.app_version}")
