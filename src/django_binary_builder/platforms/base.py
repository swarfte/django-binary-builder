"""Shared platform helpers."""

import sys
from dataclasses import dataclass

from django.core.management.base import CommandError

from django_binary_builder.enums import TargetPlatform

REQUIRED_HOST_PLATFORMS = {
    TargetPlatform.WINDOWS: "win32",
    TargetPlatform.LINUX: "linux",
    TargetPlatform.MACOS: "darwin",
}

PLATFORM_NOT_IMPLEMENTED = "Platform '{}' is reserved but has not been implemented yet."


@dataclass(slots=True)
class PipelineOptions:
    check: bool = False
    generate_only: bool = False
    skip_installer: bool = False


def validate_host_platform(target: TargetPlatform) -> None:
    """Ensure the build host matches the target platform."""

    required_host = REQUIRED_HOST_PLATFORMS[target]

    if sys.platform != required_host:
        raise CommandError(
            f"Building for '{target.value}' must be performed on "
            f"'{required_host}'. The current host is '{sys.platform}'."
        )
