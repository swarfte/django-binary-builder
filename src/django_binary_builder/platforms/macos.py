"""Reserved macOS pipeline (not implemented yet)."""

from django.core.management.base import CommandError

from django_binary_builder.platforms.base import PLATFORM_NOT_IMPLEMENTED


def run_macos_pipeline(**kwargs):
    raise CommandError(PLATFORM_NOT_IMPLEMENTED.format("macos"))
