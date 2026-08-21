"""``.env`` discovery, parsing, interpolation and merge rules."""

import os
import re
from collections.abc import Mapping
from pathlib import Path

from django.core.management.base import CommandError
from dotenv import dotenv_values

INTERPOLATION_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

DEFAULT_ENV_FILENAME = ".env"


def resolve_environment_files(
    *,
    configured: list[Path],
    extra: Path | None,
    project_root: Path,
) -> list[Path]:
    """Return the ordered list of ``.env`` files to load.

    A missing automatic default ``.env`` is ignored, but an explicitly
    configured or requested file that does not exist is an error.
    """

    files = [Path(item) for item in configured]

    if extra is not None:
        files.append(Path(extra))

    if not files:
        default_file = project_root / DEFAULT_ENV_FILENAME

        if default_file.is_file():
            return [default_file]

        return []

    for candidate in files:
        if not candidate.is_file():
            raise CommandError(f"Configured .env file was not found: {candidate}")

    return files


def load_environment_files(files: list[Path]) -> dict[str, str]:
    """Parse ``files`` in order; later files override earlier ones."""

    merged: dict[str, str] = {}

    for path in files:
        values = dotenv_values(path, interpolate=False)

        for name, value in values.items():
            if value is not None:
                merged[name] = value

    return merged


def interpolate_variables(
    values: Mapping[str, str],
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Resolve ``${NAME}`` references.

    Returns the resolved values and the list of variable names that
    still contain unresolved references. Circular references raise a
    ``CommandError``.
    """

    if environment is None:
        environment = os.environ

    lookup: dict[str, str] = dict(environment)
    lookup.update(values)

    resolved: dict[str, str] = {}
    unresolved: list[str] = []

    for name in values:
        stack = {name}
        value = values[name]
        expanded = _expand_value(value, lookup, stack)
        resolved[name] = expanded

        if INTERPOLATION_PATTERN.search(expanded):
            unresolved.append(name)

    return resolved, unresolved


def _expand_value(
    value: str,
    lookup: Mapping[str, str],
    stack: set[str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        reference = match.group(1)

        if reference in stack:
            raise CommandError(
                f"Circular .env interpolation detected involving '{reference}'."
            )

        if reference not in lookup:
            return match.group(0)

        return _expand_value(
            lookup[reference],
            lookup,
            stack | {reference},
        )

    return INTERPOLATION_PATTERN.sub(replace, value)


def merge_with_process_environment(
    values: Mapping[str, str],
    *,
    override_process_env: bool,
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Layer the process environment on top of the ``.env`` values.

    Only names defined in the ``.env`` sources are candidates for the
    snapshot, so the whole process environment is never packaged.
    When ``override_process_env`` is False the process environment
    value wins for those names; when it is True the ``.env`` values
    win. The process environment itself is never modified.
    """

    if environment is None:
        environment = os.environ

    if override_process_env:
        return dict(values)

    return {name: environment.get(name, value) for name, value in values.items()}
