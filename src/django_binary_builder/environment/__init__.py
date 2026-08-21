"""Build-time ``.env`` loading, policy enforcement and snapshots."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.core.management.base import CommandError

from django_binary_builder.environment.loader import (
    interpolate_variables,
    load_environment_files,
    merge_with_process_environment,
    resolve_environment_files,
)
from django_binary_builder.environment.policy import (
    find_secret_names,
    select_variables,
)
from django_binary_builder.environment.validation import (
    validate_required_variables,
)

WarningEmitter = Callable[[str], None]


@dataclass(slots=True)
class EnvironmentResult:
    enabled: bool
    files: list[Path] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    secret_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def prepare_build_environment(
    *,
    config: dict[str, Any],
    project_root: Path,
    extra_file: Path | None = None,
    emit_warning: WarningEmitter | None = None,
) -> EnvironmentResult:
    """Load, merge and validate ``.env`` sources for a build.

    Nothing is written and ``os.environ`` is never modified. Secrets
    are never included in messages; only variable names are reported.
    """

    emit: WarningEmitter = emit_warning or (lambda message: None)
    environment_config = config.get("ENVIRONMENT", {})
    warnings: list[str] = []

    if not environment_config.get("ENABLED", True):
        return EnvironmentResult(enabled=False, warnings=warnings)

    files = resolve_environment_files(
        configured=list(environment_config.get("FILES", [])),
        extra=extra_file,
        project_root=project_root,
    )

    file_values = load_environment_files(files)
    interpolated, unresolved = interpolate_variables(file_values)

    if unresolved:
        message = (
            "Unresolved .env interpolation references remain in: "
            + ", ".join(sorted(unresolved))
            + "."
        )
        warnings.append(message)
        emit(message)

    pool = merge_with_process_environment(
        interpolated,
        override_process_env=environment_config.get(
            "OVERRIDE_PROCESS_ENV",
            False,
        ),
    )

    validate_required_variables(pool, environment_config.get("REQUIRED", []))

    selected = select_variables(
        pool,
        include=list(environment_config.get("INCLUDE", [])),
        exclude=list(environment_config.get("EXCLUDE", [])),
    )

    secret_names = find_secret_names(selected)

    if secret_names and not environment_config.get("ALLOW_SECRETS", False):
        raise CommandError(_secret_blocked_message(secret_names))

    if secret_names:
        message = (
            "High risk: sensitive environment variables will be embedded "
            "in plain text inside the application bundle: "
            + ", ".join(secret_names)
            + ". Anyone with access to the installed files can extract "
            "them. Set ENVIRONMENT.ALLOW_SECRETS=False to block this."
        )
        warnings.append(message)

        if environment_config.get("WARN_ON_SECRET_NAMES", True):
            emit(message)

    return EnvironmentResult(
        enabled=True,
        files=files,
        variables=selected,
        secret_names=secret_names,
        warnings=warnings,
    )


def _secret_blocked_message(secret_names: list[str]) -> str:
    return (
        "Sensitive environment variables were selected for packaging, "
        "but ENVIRONMENT.ALLOW_SECRETS is False: "
        + ", ".join(secret_names)
        + ". Remove them from INCLUDE, or set ALLOW_SECRETS=True to "
        "explicitly accept the risk that bundled values can be "
        "extracted by anyone with file access."
    )
