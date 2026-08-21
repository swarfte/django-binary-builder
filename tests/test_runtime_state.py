import json
from datetime import datetime

from django_binary_builder.runtime.state import (
    build_initialization_state,
    read_initialization_state,
    state_path,
    write_initialization_state,
)


def make_state(**overrides):
    payload = {
        "app_version": "1.0.0",
        "database_mode": "sqlite",
        "migrations_completed": True,
        "initial_admin": {
            "status": "created",
            "username": "admin",
            "password_change_required": True,
        },
    }
    payload.update(overrides)

    return build_initialization_state(**payload)


def test_state_round_trip(tmp_path):
    state = make_state()

    path = write_initialization_state(
        tmp_path / "state" / "initialization.json",
        state,
    )

    loaded = read_initialization_state(path)

    assert loaded == state


def test_state_schema_fields(tmp_path):
    state = make_state()

    path = write_initialization_state(
        state_path(tmp_path),
        state,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["application_version"] == "1.0.0"
    assert payload["database_mode"] == "sqlite"
    assert payload["migrations_completed"] is True
    assert payload["initial_admin_status"] == "created"
    assert payload["initial_admin_username"] == "admin"
    assert payload["initial_admin_password_change_required"] is True

    datetime.fromisoformat(payload["initialized_at"])


def test_state_never_contains_secrets(tmp_path):
    state = make_state(
        initial_admin={
            "status": "created",
            "username": "admin",
            "password_change_required": True,
        },
    )

    path = write_initialization_state(state_path(tmp_path), state)

    content = path.read_text(encoding="utf-8")

    for forbidden in (
        "password",
        "admin1234",
        "secret",
        "token",
    ):
        assert forbidden not in content.lower().replace(
            "password_change_required",
            "",
        ).replace("password_change", ""), content


def test_read_state_returns_none_for_missing_file(tmp_path):
    assert read_initialization_state(state_path(tmp_path)) is None


def test_read_state_returns_none_for_invalid_json(tmp_path):
    path = state_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")

    assert read_initialization_state(path) is None
