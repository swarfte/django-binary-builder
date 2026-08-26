"""Dependency resolution for the portable runtime.

Resolution order, matching the documented behaviour:

1. an existing ``requirements.txt`` is used as-is;
2. otherwise ``pyproject.toml`` ``[project] dependencies`` are used;
3. otherwise ``requirements.txt`` is generated from the currently
   active environment (the equivalent of ``pip freeze``).
"""

import re
from dataclasses import dataclass
from importlib.metadata import distributions
from pathlib import Path

from django.core.management.base import CommandError

REQUIREMENTS_FILENAME = "requirements.txt"
PYPROJECT_FILENAME = "pyproject.toml"

# Packages that must never end up in the generated requirements file.
FREEZE_EXCLUDED_PACKAGES = frozenset(
    {
        "pip",
        "setuptools",
        "wheel",
        "django-binary-builder",
    }
)

# Runtime dependencies the generated launcher relies on; appended to
# every resolved requirements list when not already present.
LAUNCHER_REQUIREMENTS = (
    "waitress>=3.0.2",
    "pywebview>=5.1",
    "python-dotenv>=1.1",
)

_REQUIREMENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


@dataclass(slots=True)
class RequirementsResult:
    """The resolved dependency list for the portable runtime."""

    lines: list[str]
    source: str
    generated_file: Path | None = None


def resolve_requirements(
    project_root: Path,
    *,
    dry_run: bool = False,
) -> RequirementsResult:
    """Resolve the project's dependencies following the documented order.

    ``dry_run`` skips writing the generated ``requirements.txt`` into
    the project root (used by ``--check``).
    """

    requirements_file = project_root / REQUIREMENTS_FILENAME
    pyproject_file = project_root / PYPROJECT_FILENAME

    if requirements_file.is_file():
        lines = _read_requirements_file(requirements_file)
        source = REQUIREMENTS_FILENAME
        return RequirementsResult(
            lines=_ensure_launcher_requirements(lines),
            source=source,
        )

    if pyproject_file.is_file():
        lines = _read_pyproject_dependencies(pyproject_file)

        if lines:
            return RequirementsResult(
                lines=_ensure_launcher_requirements(lines),
                source=f"{PYPROJECT_FILENAME} [project] dependencies",
            )

    generated = freeze_current_environment()

    if not dry_run:
        requirements_file.write_text(
            "\n".join(generated) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    return RequirementsResult(
        lines=_ensure_launcher_requirements(generated),
        source="generated from the current environment (pip freeze)",
        generated_file=requirements_file,
    )


def freeze_current_environment() -> list[str]:
    """Return ``name==version`` lines for every installed distribution.

    Uses ``importlib.metadata`` so it works in environments without
    pip installed (for example uv-managed virtual environments).
    """

    entries: list[tuple[str, str]] = []

    excluded = {_normalize_name(item) for item in FREEZE_EXCLUDED_PACKAGES}

    for distribution in distributions():
        name = distribution.metadata.get("Name")

        if not name or _normalize_name(name) in excluded:
            continue

        version = distribution.version

        if version:
            entries.append((name, version))

    return [
        f"{name}=={version}"
        for name, version in sorted(entries, key=lambda entry: entry[0].lower())
    ]


def requirement_name(line: str) -> str:
    """Return the normalized distribution name of a requirement line."""

    line = line.strip()

    match = _REQUIREMENT_NAME_PATTERN.match(line)

    if not match:
        return ""

    return _normalize_name(match.group(0))


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def _read_requirements_file(path: Path) -> list[str]:
    lines = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if line and not line.startswith("#"):
            lines.append(line)

    return lines


def _read_pyproject_dependencies(path: Path) -> list[str]:
    import tomllib

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as error:
        raise CommandError(
            f"Could not parse {PYPROJECT_FILENAME}: {error}"
        ) from error

    dependencies = (data.get("project") or {}).get("dependencies") or []

    if not isinstance(dependencies, list):
        raise CommandError(
            "The [project] dependencies in pyproject.toml must be a list "
            "of requirement strings."
        )

    return [str(item) for item in dependencies if str(item).strip()]


def _ensure_launcher_requirements(lines: list[str]) -> list[str]:
    existing = {requirement_name(line) for line in lines}

    result = list(lines)

    for requirement in LAUNCHER_REQUIREMENTS:
        if requirement_name(requirement) not in existing:
            result.append(requirement)

    return result
