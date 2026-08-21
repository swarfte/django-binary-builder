import json
import logging
from contextlib import contextmanager

import pytest
from django.contrib.auth import get_user_model

from django_binary_builder.exceptions import RuntimeInitializationError
from django_binary_builder.runtime.initialization import (
    initialize_application,
    prepare_sqlite_database,
)
from django_binary_builder.runtime.locks import initialization_lock
from django_binary_builder.runtime.state import state_path

pytestmark = pytest.mark.django_db(transaction=True)


def make_defaults(**database_overrides):
    database = {
        "mode": "sqlite",
        "run_migrations": True,
        "migration_timeout": 300,
        "sqlite": {
            "filename": "db.sqlite3",
            "copy_initial_database": False,
            "initial_database": None,
        },
    }
    database.update(database_overrides)

    return {
        "app_version": "1.4.2",
        "database": database,
        "initial_admin": {
            "enabled": True,
            "sqlite_only": True,
            "username": "admin",
            "password": "admin1234",
            "email": "admin@localhost",
            "extra_fields": {},
            "require_password_change": True,
        },
    }


@contextmanager
def runtime_database(name: object):
    """Point the live default connection at another SQLite database.

    ``override_settings`` cannot be used here because Django caches
    the connection; mutating ``settings_dict`` and forcing a reconnect
    is the supported way to retarget it inside a running process.
    """

    from django.db import connections

    connection = connections["default"]
    original_name = connection.settings_dict["NAME"]

    connection.settings_dict["NAME"] = str(name)
    connection.close()
    connection.connection = None

    try:
        yield
    finally:
        connection.settings_dict["NAME"] = original_name
        connection.close()
        connection.connection = None


def test_first_start_creates_database_migrations_and_admin(tmp_path):
    defaults = make_defaults()
    database_path = tmp_path / "data" / "db.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with runtime_database(database_path):
        state = initialize_application(defaults, runtime_root=tmp_path)

    assert database_path.is_file()

    assert state["schema_version"] == 1
    assert state["application_version"] == "1.4.2"
    assert state["database_mode"] == "sqlite"
    assert state["migrations_completed"] is True
    assert state["initial_admin_status"] == "created"
    assert state["initial_admin_username"] == "admin"
    assert state["initial_admin_password_change_required"] is True

    from django_binary_builder.runtime.state import (
        read_initialization_state,
    )

    saved = read_initialization_state(state_path(tmp_path))

    assert saved == state

    with runtime_database(database_path):
        user_model = get_user_model()

        assert user_model._default_manager.filter(username="admin").exists()


def test_second_start_preserves_password(tmp_path):
    defaults = make_defaults()
    database_path = tmp_path / "data" / "db.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with runtime_database(database_path):
        initialize_application(defaults, runtime_root=tmp_path)

        user_model = get_user_model()
        user = user_model._default_manager.get(username="admin")
        user.set_password("rotated-password")
        user.save()

        state = initialize_application(defaults, runtime_root=tmp_path)

        user.refresh_from_db()

        assert state["initial_admin_status"] == "already_exists"
        assert state["initial_admin_password_change_required"] is False
        assert user.check_password("rotated-password")
        assert not user.check_password("admin1234")


def test_database_failure_does_not_write_state(tmp_path):
    defaults = make_defaults()
    defaults["database"]["run_migrations"] = False
    defaults["initial_admin"]["enabled"] = False

    # A path whose parent is a regular file can never be opened.
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("not a directory", encoding="utf-8")
    broken_name = blocker / "nested" / "db.sqlite3"

    with runtime_database(broken_name):
        with pytest.raises(RuntimeInitializationError):
            initialize_application(defaults, runtime_root=tmp_path)

    assert not state_path(tmp_path).exists()


def test_lock_removes_stale_lock(tmp_path):
    lock_file = tmp_path / "state" / "initialization.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text("123", encoding="ascii")

    import os

    old_mtime = lock_file.stat().st_mtime - 7200
    os.utime(lock_file, (old_mtime, old_mtime))

    with initialization_lock(lock_file, timeout=0.1):
        pass

    assert not lock_file.exists()


def test_lock_times_out_when_held(tmp_path):
    lock_file = tmp_path / "state" / "initialization.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text("123", encoding="ascii")

    with pytest.raises(RuntimeInitializationError):
        with initialization_lock(lock_file, timeout=0.1):
            pass


def test_seed_database_is_copied_when_configured(tmp_path):
    from django.core.management import call_command

    seed = tmp_path / "seed.sqlite3"

    # Build a seed database with tables and a marker user that only
    # exists when the seed is actually copied into the runtime path.
    with runtime_database(seed):
        call_command("migrate", verbosity=0, interactive=False)

        get_user_model()._default_manager.create_superuser(
            username="seedadmin",
            password="seed-password",
        )

    defaults = make_defaults(
        sqlite={
            "filename": "seeded.sqlite3",
            "copy_initial_database": True,
            "initial_database": str(seed),
        },
    )

    database_path = tmp_path / "data" / "seeded.sqlite3"

    with runtime_database(database_path):
        state = initialize_application(defaults, runtime_root=tmp_path)

        marker_exists = (
            get_user_model()._default_manager.filter(username="seedadmin").exists()
        )

    assert database_path.is_file()
    assert state["migrations_completed"] is True

    # The seed content (marker user) survived into the runtime database.
    assert marker_exists is True


def test_existing_database_is_never_overwritten_by_seed(tmp_path):
    existing = tmp_path / "data" / "db.sqlite3"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing user data")

    seed = tmp_path / "seed.sqlite3"
    seed.write_bytes(b"seed data")

    defaults = {
        "database": {
            "sqlite": {
                "filename": "db.sqlite3",
                "copy_initial_database": True,
                "initial_database": str(seed),
            }
        }
    }

    result = prepare_sqlite_database(defaults, runtime_root=tmp_path)

    assert result == existing
    assert existing.read_bytes() == b"existing user data"


def test_password_change_reminder_logged(tmp_path, caplog):
    defaults = make_defaults()
    database_path = tmp_path / "data" / "db.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with runtime_database(database_path):
        with caplog.at_level(
            logging.WARNING,
            logger="django_binary_builder.runtime",
        ):
            initialize_application(defaults, runtime_root=tmp_path)

    reminders = [
        record
        for record in caplog.records
        if "publicly documented" in record.getMessage()
    ]

    assert reminders


def test_state_file_contains_no_secrets(tmp_path):
    defaults = make_defaults()
    database_path = tmp_path / "data" / "db.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with runtime_database(database_path):
        initialize_application(defaults, runtime_root=tmp_path)

    content = state_path(tmp_path).read_text(encoding="utf-8")

    assert "admin1234" not in content

    payload = json.loads(content)

    for key in payload:
        assert "password" not in key or key == (
            "initial_admin_password_change_required"
        ), key


def test_runtime_database_helper_restores_original_database(tmp_path):
    from django.db import connections

    original_name = connections["default"].settings_dict["NAME"]

    database_path = tmp_path / "data" / "helper.sqlite3"
    database_path.parent.mkdir(parents=True)

    with runtime_database(database_path):
        assert connections["default"].settings_dict["NAME"] == str(database_path)

    assert connections["default"].settings_dict["NAME"] == original_name
