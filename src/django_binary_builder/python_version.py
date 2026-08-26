"""``.python-version`` pin handling.

The file records the Python version the portable runtime is built
from. It is generated from the currently active interpreter when
missing; an existing file is always used as-is so builds stay
reproducible.
"""

import sys
from pathlib import Path

from django.core.management.base import CommandError

PYTHON_VERSION_FILENAME = ".python-version"


def current_python_version() -> str:
    """Return the current interpreter version as ``major.minor``."""

    return f"{sys.version_info.major}.{sys.version_info.minor}"


def resolve_python_version(project_root: Path, *, dry_run: bool = False) -> str:
    """Return the pinned Python version for the project.

    Writes the file with the current interpreter's ``major.minor``
    version when it does not exist yet; otherwise verifies that the
    current interpreter matches the pin. ``dry_run`` skips writing.
    """

    version_file = project_root / PYTHON_VERSION_FILENAME

    if not version_file.is_file():
        version = current_python_version()

        if not dry_run:
            version_file.write_text(
                version + "\n",
                encoding="ascii",
                newline="\n",
            )

        return version

    pinned = version_file.read_text(encoding="utf-8").strip()

    if not pinned:
        raise CommandError(
            f"{PYTHON_VERSION_FILENAME} is empty; remove the file so it "
            "can be regenerated, or write the expected Python version "
            "into it (for example '3.14')."
        )

    _verify_matches_current(pinned)

    return pinned


def _verify_matches_current(pinned: str) -> None:
    parts = pinned.split(".")

    if len(parts) < 2 or not all(part.isdigit() for part in parts):
        raise CommandError(
            f"{PYTHON_VERSION_FILENAME} must contain a Python version such "
            f"as '3.14' (got {pinned!r})."
        )

    pinned_major_minor = (int(parts[0]), int(parts[1]))
    current = (sys.version_info.major, sys.version_info.minor)

    if pinned_major_minor != current:
        pinned_display = ".".join(str(part) for part in pinned_major_minor)
        current_display = ".".join(str(part) for part in current)

        raise CommandError(
            f"{PYTHON_VERSION_FILENAME} pins Python {pinned_display} but "
            f"the current interpreter is Python {current_display}. Activate "
            f"a Python {pinned_display} virtual environment and rebuild."
        )
