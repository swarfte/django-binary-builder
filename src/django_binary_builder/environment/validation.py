"""Validation and redaction helpers for environment handling."""

import re
from collections.abc import Iterable, Mapping

from django.core.management.base import CommandError

from django_binary_builder.environment.policy import (
    REDACTED,
    matches_any,
)

SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|private[_-]?key)\b"
    r"\s*[=:]\s*('([^']*)'|\"([^\"]*)\"|[^\s,;)}\]]+)"
)


def validate_required_variables(
    pool: Mapping[str, str],
    required: Iterable[str],
) -> None:
    missing = [
        name
        for name in required
        if not str(pool.get(name, "")).strip() or "${" in str(pool.get(name, ""))
    ]

    if missing:
        raise CommandError(
            "Required environment variables are missing or unresolved: "
            + ", ".join(sorted(missing))
        )


def verify_snapshot_selection(
    variables: Mapping[str, str],
    exclude: Iterable[str],
) -> None:
    excluded = sorted(name for name in variables if matches_any(name, list(exclude)))

    if excluded:
        raise CommandError(
            "The environment snapshot must not contain excluded "
            "variables: " + ", ".join(excluded)
        )


def redact_text(text: str, secret_values: Iterable[str] = ()) -> str:
    """Redact secret values and ``key=value`` style secrets in text."""

    redacted = SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        str(text),
    )

    for value in secret_values:
        if value and str(value) in redacted:
            redacted = redacted.replace(str(value), REDACTED)

    return redacted


def summarize_variables(variables: Mapping[str, str]) -> str:
    """Summarize variables as names with redacted values."""

    if not variables:
        return "none"

    return ", ".join(f"{name}={REDACTED}" for name in sorted(variables))
