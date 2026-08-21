import platform
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_binary_builder.conf import get_builder_settings
from django_binary_builder.context import create_build_context
from django_binary_builder.platforms.base import TargetPlatform


class Command(BaseCommand):
    help = "Build the current Django project as an installable application."

    def add_arguments(self, parser):
        parser.add_argument(
            "platform",
            choices=[
                TargetPlatform.WINDOWS.value,
                TargetPlatform.LINUX.value,
                TargetPlatform.MACOS.value,
            ],
            help="Target platform: windows, linux, or macos.",
        )

        parser.add_argument(
            "--check",
            action="store_true",
            help="Check the build environment without building.",
        )

        parser.add_argument(
            "--generate-only",
            action="store_true",
            help="Generate build files without running packaging tools.",
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
            "--version",
            help="Override the application version.",
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
            "--skip-installer",
            action="store_true",
            help="Build the application without creating an installer.",
        )

    def handle(self, *args, **options):
        target = TargetPlatform(options["platform"])
        config = get_builder_settings()

        self._apply_command_options(config, options)

        context = create_build_context(
            target_platform=target.value,
            config=config,
        )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Django Binary Builder"
            )
        )

        self.stdout.write(f"Target: {target.value}")
        self.stdout.write(f"Host: {sys.platform}")
        self.stdout.write(f"Python: {platform.python_version()}")
        self.stdout.write(
            f"Project root: {context.project_root}"
        )
        self.stdout.write(
            f"Django settings: {settings.SETTINGS_MODULE}"
        )
        self.stdout.write(
            f"Application name: {context.app_name}"
        )
        self.stdout.write(
            f"Application version: {context.app_version}"
        )

        self._validate_host_platform(target)

        if target == TargetPlatform.WINDOWS:
            self._handle_windows(context, options)
            return

        raise CommandError(
            f"Platform '{target.value}' is reserved "
            "but has not been implemented yet."
        )

    def _apply_command_options(
        self,
        config: dict,
        options: dict,
    ) -> None:
        if options["name"]:
            config["NAME"] = options["name"]

        if options["version"]:
            config["VERSION"] = options["version"]

        if options["output"]:
            output_dir = options["output"]

            if not output_dir.is_absolute():
                output_dir = (
                    config["PROJECT_ROOT"]
                    / output_dir
                )

            config["OUTPUT_DIR"] = output_dir.resolve()

        if options["console"]:
            config["BUILD"]["CONSOLE"] = True

        if options["clean"]:
            config["BUILD"]["CLEAN"] = True

    def _validate_host_platform(
        self,
        target: TargetPlatform,
    ) -> None:
        if target == TargetPlatform.WINDOWS:
            required_host = "win32"
        elif target == TargetPlatform.LINUX:
            required_host = "linux"
        elif target == TargetPlatform.MACOS:
            required_host = "darwin"
        else:
            raise CommandError(
                f"Unsupported platform: {target.value}"
            )

        if sys.platform != required_host:
            raise CommandError(
                f"Building for '{target.value}' must be performed "
                f"on '{required_host}'. "
                f"The current host is '{sys.platform}'."
            )

    def _handle_windows(
        self,
        context,
        options: dict,
    ) -> None:
        from django_binary_builder.platforms.windows import (
            build_windows,
            check_windows_environment,
        )

        check_windows_environment(
            context=context,
            stdout=self.stdout,
            require_inno=not options["skip_installer"],
        )

        if options["check"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "All Windows build checks passed."
                )
            )
            return

        build_windows(
            context=context,
            stdout=self.stdout,
            generate_only=options["generate_only"],
            skip_installer=options["skip_installer"],
        )