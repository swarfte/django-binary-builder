"""Runtime initialization state persistence."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_SCHEMA_VERSION = 1

INITIALIZATION_STATE_FILENAME = "initialization.json"
INITIALIZATION_LOCK_FILENAME = "initialization.lock"


def state_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / INITIALIZATION_STATE_FILENAME


def lock_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / INITIALIZATION_LOCK_FILENAME


def build_initialization_state(
    *,
    app_version: str,
    database_mode: str,
    migrations_completed: bool,
    initial_admin: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "application_version": app_version,
        "database_mode": database_mode,
        "migrations_completed": migrations_completed,
        "initial_admin_status": initial_admin.get("status", "disabled"),
        "initial_admin_username": initial_admin.get("username"),
        "initial_admin_password_change_required": bool(
            initial_admin.get("password_change_required", False)
        ),
        "initialized_at": datetime.now(UTC).isoformat(),
    }


def write_initialization_state(
    path: Path,
    state: dict[str, Any],
) -> Path:
    """Write the state file atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_name(path.name + ".tmp")

    temporary_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    os.replace(temporary_path, path)

    return path


def read_initialization_state(path: Path) -> dict[str, Any] | None:
    """Read the state file, returning ``None`` when unavailable."""

    if not path.is_file():
        return None

    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None

    return state if isinstance(state, dict) else None
