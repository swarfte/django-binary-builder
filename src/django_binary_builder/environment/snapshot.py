"""Runtime environment snapshot reading and writing."""

import json
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA_VERSION = 1


def build_snapshot_payload(variables: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "variables": dict(variables),
    }


def write_environment_snapshot(
    path: Path,
    variables: dict[str, str],
) -> Path:
    """Write the runtime environment snapshot to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_snapshot_payload(variables)

    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return path


def read_environment_snapshot(path: Path) -> dict[str, str]:
    """Return the variables stored in a snapshot file."""

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"Runtime environment snapshot is not a JSON object: {path}")

    variables = data.get("variables", {})

    if not isinstance(variables, dict):
        raise ValueError(f"Runtime environment snapshot has invalid variables: {path}")

    return {str(name): str(value) for name, value in variables.items()}
