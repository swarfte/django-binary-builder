"""Runtime application initialization.

Runs inside the packaged application, after Django is set up and the
runtime database is configured: acquire the initialization lock,
prepare the SQLite database, test the connection, run migrations,
create the initial administrator and record the state file.
"""

import logging
import shutil
import time
from pathlib import Path
from typing import Any

from django_binary_builder.exceptions import RuntimeInitializationError
from django_binary_builder.runtime.admin import create_initial_admin
from django_binary_builder.runtime.database import validate_sqlite_filename
from django_binary_builder.runtime.environment import find_bundled_file
from django_binary_builder.runtime.locks import initialization_lock
from django_binary_builder.runtime.state import (
    build_initialization_state,
    lock_path,
    read_initialization_state,
    state_path,
    write_initialization_state,
)

RUNTIME_LOGGER_NAME = "django_binary_builder.runtime"

PASSWORD_CHANGE_REMINDER = (
    "The initial administrator password is publicly documented; "
    "change it after the first login."
)


def configure_runtime_logging(
    directories: dict[str, Path],
    defaults: dict[str, Any] | None = None,
) -> logging.Logger:
    """Log to the console and to the runtime ``logs`` directory."""

    logger = logging.getLogger(RUNTIME_LOGGER_NAME)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_directory = directories.get("logs")

    if log_directory is not None:
        log_directory.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            log_directory / "application.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def initialize_application(
    defaults: dict[str, Any],
    *,
    runtime_root: Path,
    local_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Run the full first-startup initialization sequence."""

    logger = logger or logging.getLogger(RUNTIME_LOGGER_NAME)

    database_config = defaults.get("database", {})
    mode = database_config.get("mode", "sqlite")

    with initialization_lock(lock_path(runtime_root)):
        if mode == "sqlite":
            prepare_sqlite_database(
                defaults,
                runtime_root=runtime_root,
                local_dir=local_dir,
                logger=logger,
            )

        skip_connection_test = mode == "external" and not database_config.get(
            "external", {}
        ).get(
            "test_connection_on_startup",
            True,
        )

        if not skip_connection_test:
            test_database_connection(logger=logger)

        migrations_completed = False

        if database_config.get("run_migrations", True):
            migrations_completed = run_runtime_migrations(
                defaults,
                logger=logger,
            )

        initial_admin = create_initial_admin(defaults, database_mode=mode)

        state = build_initialization_state(
            app_version=str(defaults.get("app_version", "")),
            database_mode=mode,
            migrations_completed=migrations_completed,
            initial_admin=initial_admin,
        )

        write_initialization_state(state_path(runtime_root), state)

    _remind_password_change(runtime_root, logger)

    return state


def prepare_sqlite_database(
    defaults: dict[str, Any],
    *,
    runtime_root: Path,
    local_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    """Return the runtime SQLite path, seeding it when configured.

    An existing runtime database is never overwritten.
    """

    sqlite_config = defaults.get("database", {}).get("sqlite", {})
    filename = sqlite_config.get("filename", "db.sqlite3")

    try:
        filename = validate_sqlite_filename(filename)
    except ValueError as error:
        raise RuntimeInitializationError(str(error)) from error

    database_path = runtime_root / "data" / filename

    if database_path.exists():
        return database_path

    if sqlite_config.get("copy_initial_database"):
        seed_source = _resolve_seed_database(sqlite_config, local_dir)

        if seed_source is not None:
            database_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(seed_source, database_path)

            if logger is not None:
                logger.info(
                    "Seeded the runtime database from the bundled initial database."
                )

    return database_path


def _resolve_seed_database(
    sqlite_config: dict[str, Any],
    local_dir: Path | None,
) -> Path | None:
    configured = sqlite_config.get("initial_database")

    if not configured:
        return None

    configured_path = Path(configured)
    bundled = find_bundled_file(
        configured_path.name,
        local_dir=local_dir,
    )

    if bundled is not None:
        return bundled

    return configured_path if configured_path.is_file() else None


def test_database_connection(
    *,
    logger: logging.Logger | None = None,
) -> None:
    """Ensure the default database connection can be established."""

    from django.db import connections

    connection = connections["default"]

    try:
        connection.ensure_connection()
    except Exception as error:
        raise RuntimeInitializationError(
            f"Database connection failed: {_sanitize_error_message(error)}"
        ) from error


def run_runtime_migrations(
    defaults: dict[str, Any],
    *,
    logger: logging.Logger | None = None,
) -> bool:
    """Run ``migrate`` non-interactively with elapsed-time warnings."""

    from django.core.management import call_command

    database_config = defaults.get("database", {})
    timeout = database_config.get("migration_timeout", 300)

    started = time.monotonic()

    try:
        call_command(
            "migrate",
            interactive=False,
            verbosity=1,
        )
    except Exception as error:
        raise RuntimeInitializationError(
            f"Runtime migrations failed: {_sanitize_error_message(error)}"
        ) from error

    elapsed = time.monotonic() - started

    if elapsed > timeout and logger is not None:
        logger.warning(
            "Migrations completed in %.1fs, exceeding the configured "
            "timeout of %ss. The application will continue, but "
            "startup was slower than expected.",
            elapsed,
            timeout,
        )

    return True


def _remind_password_change(
    runtime_root: Path,
    logger: logging.Logger,
) -> None:
    state = read_initialization_state(state_path(runtime_root))

    if state is None:
        return

    if state.get("initial_admin_password_change_required"):
        logger.warning(PASSWORD_CHANGE_REMINDER)


def _sanitize_error_message(error: BaseException) -> str:
    from django_binary_builder.environment.validation import redact_text

    return redact_text(str(error), _collect_secret_values())


def _collect_secret_values() -> list[str]:
    values: list[str] = []

    try:
        from django.conf import settings
    except Exception:
        return values

    for database in settings.DATABASES.values():
        password = database.get("PASSWORD")

        if password:
            values.append(str(password))

    return values
