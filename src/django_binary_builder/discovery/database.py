"""Database backend and driver discovery."""

import importlib.util
from dataclasses import dataclass

INSTALL_HINTS = {
    "django.db.backends.postgresql": 'uv add "psycopg[binary]"',
    "django.db.backends.postgresql_psycopg2": 'uv add "psycopg[binary]"',
    "django.db.backends.mysql": "uv add mysqlclient",
    "django.db.backends.oracle": "uv add oracledb",
}


@dataclass(frozen=True)
class DatabaseDriver:
    backend: str
    driver_module: str | None
    hidden_imports: tuple[str, ...]


ENGINE_DRIVER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "django.db.backends.postgresql": ("psycopg", "psycopg2"),
    "django.db.backends.postgresql_psycopg2": ("psycopg2", "psycopg"),
    "django.db.backends.mysql": ("MySQLdb",),
    "django.db.backends.oracle": ("oracledb", "cx_Oracle"),
    "django.db.backends.sqlite3": (),
}


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ImportError, ValueError:
        return False


def resolve_database_driver(backend: str) -> DatabaseDriver:
    """Resolve the driver package for a Django database engine."""

    candidates = ENGINE_DRIVER_CANDIDATES.get(backend)

    if candidates is None:
        # Unknown or third-party backend (for example mssql via pyodbc).
        return DatabaseDriver(
            backend=backend,
            driver_module=None,
            hidden_imports=(),
        )

    for candidate in candidates:
        if _module_available(candidate):
            return DatabaseDriver(
                backend=backend,
                driver_module=candidate,
                hidden_imports=(candidate,),
            )

    return DatabaseDriver(
        backend=backend,
        driver_module=None,
        hidden_imports=(),
    )


def get_database_hidden_imports(backend: str) -> list[str]:
    return list(resolve_database_driver(backend).hidden_imports)


def driver_install_hint(backend: str) -> str:
    return INSTALL_HINTS.get(
        backend,
        "install the Python driver required by your database engine",
    )
