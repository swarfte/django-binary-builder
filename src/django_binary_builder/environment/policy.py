"""Include, exclude and secret-name policies for the snapshot."""

from collections.abc import Mapping
from fnmatch import fnmatch

SECRET_NAME_PATTERNS = (
    "*SECRET*",
    "*PASSWORD*",
    "*TOKEN*",
    "*API_KEY*",
    "*PRIVATE_KEY*",
    "*DATABASE_URL*",
    "*DB_PASSWORD*",
)

REDACTED = "[REDACTED]"


def matches_any(name: str, patterns: list[str] | tuple[str, ...]) -> bool:
    return any(fnmatch(name.upper(), pattern.upper()) for pattern in patterns)


def is_secret_name(name: str) -> bool:
    return matches_any(name, SECRET_NAME_PATTERNS)


def select_variables(
    pool: Mapping[str, str],
    *,
    include: list[str],
    exclude: list[str],
) -> dict[str, str]:
    """Apply include and exclude patterns.

    An empty include list selects nothing; ``*`` selects everything.
    Exclude always wins over include.
    """

    selected = {
        name: value for name, value in pool.items() if matches_any(name, include)
    }

    return {
        name: value
        for name, value in selected.items()
        if not matches_any(name, exclude)
    }


def find_secret_names(names) -> list[str]:
    return sorted(name for name in names if is_secret_name(name))
