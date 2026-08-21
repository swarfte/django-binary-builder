"""The ``binary`` management command."""

import platform as python_platform
import sys
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_binary_builder.conf import get_builder_settings
from django_binary_builder.context import create_build_context
from django_binary_builder.enums import TargetPlatform
from django_binary_builder.platforms.base import (
    PLATFORM_NOT_IMPLEMENTED,
    PipelineOptions,
    validate_host_platform,
)


class Command(BaseCommand):
    help = "Build the current Django project as an installable desktop application."

    def add_arguments(self, parser):
        parser.add_argument(
            "platform",
            choices=[member.value for member in TargetPlatform],
            help="Target platform: windows, linux, or macos.",
        )

        parser.add_argument(
            "--check",
            action="store_true",
            help="Run preflight checks without building anything.",
        )

        parser.add_argument(
            "--generate-only",
            action="store_true",
            help=("Generate build files without running packaging tools."),
        )

        parser.add_argument(
            "--skip-installer",
            action="store_true",
            help=("Build the application bundle without creating the installer."),
        )

        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete existing build files before building.",
        )

        parser.add_argument(
            "--name",
            help="Override the application display name.",
        )

        parser.add_argument(
            "--app-version",
            help="Override the packaged application version.",
        )

        parser.add_argument(
            "--output",
            type=Path,
            help="Override the output directory.",
        )

        parser.add_argument(
            "--console",
            action="store_true",
            help="Show the console window when the application runs.",
        )

        parser.add_argument(
            "--no-collectstatic",
            action="store_true",
            help="Skip collecting static files.",
        )

        parser.add_argument(
            "--env-file",
            type=Path,
            help=(
                "Load an additional .env file after the configured "
                "ENVIRONMENT.FILES entries."
            ),
        )

        parser.add_argument(
            "--no-env",
            action="store_true",
            help=("Disable .env loading and the runtime environment snapshot."),
        )

    def handle(self, *args, **options):
        target = TargetPlatform(options["platform"])

        overrides = self._build_config_overrides(options)

        config = get_builder_settings(overrides)

        context = create_build_context(
            target_platform=target.value,
            config=config,
        )

        self._print_banner(context, target)

        validate_host_platform(target)

        if target is not TargetPlatform.WINDOWS:
            raise CommandError(PLATFORM_NOT_IMPLEMENTED.format(target.value))

        from django_binary_builder.platforms.windows import (
            run_windows_pipeline,
        )

        run_windows_pipeline(
            context=context,
            stdout=self.stdout,
            style=self.style,
            options=PipelineOptions(
                check=options["check"],
                generate_only=options["generate_only"],
                skip_installer=options["skip_installer"],
            ),
        )

    def _build_config_overrides(
        self,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Translate CLI options into configuration overrides."""

        overrides: dict[str, Any] = {}

        if options.get("name"):
            overrides["NAME"] = options["name"]

            user_settings = getattr(settings, "DJANGO_BINARY_BUILDER", None) or {}

            if not user_settings.get("EXECUTABLE_NAME"):
                overrides["EXECUTABLE_NAME"] = None

        if options.get("app_version"):
            overrides["VERSION"] = options["app_version"]

        if options.get("output"):
            overrides["OUTPUT_DIR"] = Path(options["output"])

        build_overrides: dict[str, Any] = {}

        if options.get("console"):
            build_overrides["CONSOLE"] = True

        if options.get("clean"):
            build_overrides["CLEAN"] = True

        if options.get("no_collectstatic"):
            build_overrides["COLLECT_STATIC"] = False

        if build_overrides:
            overrides["BUILD"] = build_overrides

        environment_overrides: dict[str, Any] = {}

        if options.get("env_file"):
            user_settings = getattr(settings, "DJANGO_BINARY_BUILDER", None) or {}

            configured_files = list(
                (user_settings.get("ENVIRONMENT") or {}).get("FILES", [])
            )

            environment_overrides["FILES"] = [
                *configured_files,
                Path(options["env_file"]),
            ]

        if options.get("no_env"):
            environment_overrides["ENABLED"] = False

        if environment_overrides:
            overrides["ENVIRONMENT"] = environment_overrides

        return overrides

    def _print_banner(self, context, target: TargetPlatform) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("Django Binary Builder"))

        self.stdout.write(f"Target: {target.value}")
        self.stdout.write(f"Host: {sys.platform}")
        self.stdout.write(f"Python: {python_platform.python_version()}")
        self.stdout.write(f"Project root: {context.project_root}")
        self.stdout.write(f"Django settings: {context.settings_module}")
        self.stdout.write(f"Application name: {context.app_name}")
        self.stdout.write(f"Application version: {context.app_version}")
        self.stdout.write(f"Database mode: {context.database_mode}")
