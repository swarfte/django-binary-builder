"""Bundled runtime environment and defaults loading.

This module runs inside the packaged application before Django is
set up, so it must not import ``django`` at module level.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

RUNTIME_MARKER = "DJANGO_BINARY_RUNTIME"
SETTINGS_MODULE_VARIABLE = "DJANGO_SETTINGS_MODULE"

RUNTIME_DATA_DESTINATION = "runtime"


def find_bundled_file(
    filename: str,
    *,
    local_dir: Path | None = None,
) -> Path | None:
    """Locate a data file bundled by PyInstaller or generated locally."""

    candidates: list[Path] = []

    bundle_root = getattr(sys, "_MEIPASS", None)

    if bundle_root:
        base = Path(bundle_root)
        candidates.append(base / RUNTIME_DATA_DESTINATION / filename)
        candidates.append(base / filename)

    if local_dir is not None:
        candidates.append(Path(local_dir) / filename)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def apply_bundled_environment(
    settings_module: str,
    *,
    snapshot_filename: str = "runtime-environment.json",
    local_dir: Path | None = None,
) -> list[str]:
    """Apply the bundled environment snapshot before Django loads.

    Values are only set for names that are not already present in the
    process environment, so runtime environment overrides win.
    """

    applied: list[str] = []
    snapshot_path = find_bundled_file(
        snapshot_filename,
        local_dir=local_dir,
    )

    if snapshot_path is not None:
        variables = _read_snapshot_variables(snapshot_path)

        for name, value in variables.items():
            if name not in os.environ:
                os.environ[name] = value
                applied.append(name)

    os.environ.setdefault(SETTINGS_MODULE_VARIABLE, settings_module)
    os.environ[RUNTIME_MARKER] = "1"

    return applied


def load_runtime_defaults(
    *,
    defaults_filename: str = "runtime-defaults.json",
    local_dir: Path | None = None,
) -> dict[str, Any]:
    """Load the runtime defaults generated at build time."""

    defaults_path = find_bundled_file(
        defaults_filename,
        local_dir=local_dir,
    )

    if defaults_path is None:
        return {}

    try:
        defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
    except ValueError:
        return {}

    return defaults if isinstance(defaults, dict) else {}


def _read_snapshot_variables(snapshot_path: Path) -> dict[str, str]:
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except ValueError:
        return {}

    if not isinstance(payload, dict):
        return {}

    variables = payload.get("variables", {})

    if not isinstance(variables, dict):
        return {}

    return {str(name): str(value) for name, value in variables.items()}
