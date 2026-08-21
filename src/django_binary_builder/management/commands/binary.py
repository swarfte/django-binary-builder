import platform
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Build this Django project as an installable Windows application"

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            help="Application display name",
        )
        parser.add_argument(
            "--output",
            default="release",
            help="Output directory",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove previous build output",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Only validate the build environment",
        )
        parser.add_argument(
            "--console",
            action="store_true",
            help="Show the Windows console",
        )
        parser.add_argument(
            "--skip-installer",
            action="store_true",
            help="Build the application without creating an installer",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Django Binary Builder"
            )
        )

        if sys.platform != "win32":
            raise CommandError(
                "Windows installers must currently be built on Windows."
            )

        project_root = Path(settings.BASE_DIR).resolve()
        settings_module = settings.SETTINGS_MODULE

        app_name = (
            options["name"]
            or getattr(settings, "DJANGO_BINARY_BUILDER", {}).get(
                "NAME",
                project_root.name,
            )
        )

        self.stdout.write(f"Platform: {platform.platform()}")
        self.stdout.write(f"Project root: {project_root}")
        self.stdout.write(f"Settings module: {settings_module}")
        self.stdout.write(f"Application name: {app_name}")
        self.stdout.write(f"Output: {options['output']}")

        if options["check"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "Build environment check completed."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "Build pipeline has not been implemented yet."
            )
        )