"""Tests for Inno Setup helpers and build context paths."""

from django_binary_builder.builders.inno_setup import (
    escape_inno_value,
    generate_app_id,
)
from django_binary_builder.context import create_build_context


def make_config(tmp_path, **overrides):
    config = {
        "NAME": "Example Project",
        "VERSION": "0.1.1",
        "PUBLISHER": "Example Company",
        "EXECUTABLE_NAME": "example-project",
        "ICON": None,
        "PROJECT_ROOT": tmp_path,
        "SETTINGS_MODULE": "myproject.settings",
        "WSGI_APPLICATION": "myproject.wsgi.application",
    }

    config.update(overrides)

    return config


def test_escape_inno_value_doubles_quotes():
    assert escape_inno_value('say "hi"') == 'say ""hi""'
    assert escape_inno_value("plain") == "plain"


def test_generate_app_id_is_stable():
    first = generate_app_id(publisher="Example Company", app_name="Example Project")
    second = generate_app_id(publisher="Example Company", app_name="Example Project")
    other = generate_app_id(publisher="Example Company", app_name="Other App")

    assert first == second
    assert first != other
    assert first.startswith("{") and first.endswith("}")


def test_build_context_paths(tmp_path):
    context = create_build_context(
        target_platform="windows",
        config=make_config(tmp_path),
    )

    assert context.work_dir == tmp_path / ".django-binary-builder" / "windows"
    assert context.bundle_dir == context.work_dir / "bundle"
    assert context.app_dir == context.bundle_dir / "app"
    assert context.runtime_dir == context.bundle_dir / "runtime"
    assert context.static_dir == context.app_dir / "staticfiles"
    assert context.release_dir == tmp_path / "release" / "windows"
    assert context.executable_path == context.bundle_dir / "example-project.exe"
    assert context.installer_path.name == "example-project-0.1.1-Setup.exe"
    assert context.inno_script_path.name == "installer.iss"


def test_build_context_honors_output_dir(tmp_path):
    context = create_build_context(
        target_platform="windows",
        config=make_config(tmp_path, OUTPUT_DIR=tmp_path / "out"),
    )

    assert context.release_dir == tmp_path / "out" / "windows"
