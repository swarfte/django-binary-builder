import subprocess
from types import SimpleNamespace

import pytest
from django.core.management.base import CommandError

from django_binary_builder.builders.pyinstaller import (
    generate_pyinstaller_spec,
    run_pyinstaller,
)


def test_spec_contains_required_elements(build_context, settings):
    settings.STATIC_ROOT = settings.BASE_DIR / "staticroot"

    context = build_context()

    spec_path = generate_pyinstaller_spec(context)

    content = spec_path.read_text(encoding="utf-8")

    assert 'collect_all("django")' in content
    assert 'collect_all(\n    "waitress"\n)' in content
    assert "upx=False" in content
    assert "upx=True" not in content
    assert "analysis = Analysis(" in content
    assert "PYZ(" in content
    assert "EXE(" in content
    assert "COLLECT(" in content
    assert "console=False" in content

    assert str(context.runtime_environment_path) in content
    assert str(context.runtime_defaults_path) in content
    assert '"runtime"' in content

    assert "django_binary_builder.builders" in content
    assert "django_binary_builder.management" in content
    assert "django_binary_builder.platforms" in content


def test_spec_includes_static_root(build_context, settings, tmp_path):
    static_root = tmp_path / "staticfiles"
    static_root.mkdir()
    settings.STATIC_ROOT = static_root

    context = build_context()

    content = generate_pyinstaller_spec(context).read_text(encoding="utf-8")

    assert str(static_root) in content
    assert '"static"' in content


def test_spec_includes_seed_database(build_context, settings, tmp_path):
    seed = tmp_path / "seed.sqlite3"
    seed.write_bytes(b"seed")

    context = build_context(
        DATABASE={
            "SQLITE": {
                "COPY_INITIAL_DATABASE": True,
                "INITIAL_DATABASE": seed,
            },
        },
    )

    content = generate_pyinstaller_spec(context).read_text(encoding="utf-8")

    assert str(seed) in content


def test_run_pyinstaller_failure_raises_command_error(
    build_context,
    monkeypatch,
):
    context = build_context()

    spec_file = context.spec_path
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# spec", encoding="utf-8")

    def failing_run(command, **kwargs):
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(subprocess, "run", failing_run)

    with pytest.raises(CommandError) as error:
        run_pyinstaller(context)

    assert "exit code 1" in str(error.value)


def test_run_pyinstaller_missing_spec_raises(build_context):
    context = build_context()

    with pytest.raises(CommandError):
        run_pyinstaller(context)


def test_artifact_validation_detects_missing_bundle(build_context):
    from django_binary_builder.builders.pyinstaller import (
        verify_pyinstaller_artifacts,
    )

    context = build_context()

    with pytest.raises(CommandError) as error:
        verify_pyinstaller_artifacts(context)

    assert "was not found" in str(error.value)


def test_artifact_validation_detects_missing_executable(build_context):
    from django_binary_builder.builders.pyinstaller import (
        verify_pyinstaller_artifacts,
    )

    context = build_context()

    context.bundle_dir.mkdir(parents=True)

    with pytest.raises(CommandError):
        verify_pyinstaller_artifacts(context)


def test_run_pyinstaller_uses_argument_list(build_context, monkeypatch):
    context = build_context()

    spec_file = context.spec_path
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# spec", encoding="utf-8")

    context.bundle_dir.mkdir(parents=True)
    context.executable_path.write_bytes(b"exe")

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_pyinstaller(context)

    command = commands[0]

    assert isinstance(command, list)
    assert "-m" in command
    assert "PyInstaller" in command
    assert "--noconfirm" in command
    assert "--clean" in command
    assert str(context.spec_path) in command
