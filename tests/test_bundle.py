"""Tests for the project bundling rules."""

from django_binary_builder.builders.bundle import (
    _ignore_project_entry,
    bundled_icon_path,
)
from django_binary_builder.context import create_build_context


def test_ignore_project_entry_filters_build_artifacts():
    ignored = _ignore_project_entry(
        "some-directory",
        [
            ".git",
            "__pycache__",
            ".venv",
            "node_modules",
            "staticfiles",
            "release",
            ".django-binary-builder",
            "module.pyc",
            ".coverage",
            "db.sqlite3-journal",
        ],
    )

    assert ignored == {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        "staticfiles",
        "release",
        ".django-binary-builder",
        "module.pyc",
        ".coverage",
        "db.sqlite3-journal",
    }


def test_ignore_project_entry_keeps_project_files():
    kept = _ignore_project_entry(
        "some-directory",
        [
            "manage.py",
            "myproject",
            "db.sqlite3",
            ".env",
            "requirements.txt",
            "assets",
            "templates",
        ],
    )

    assert kept == set()


def make_context(tmp_path, *, icon=None, project_root=None):
    config = {
        "NAME": "Example Project",
        "VERSION": "0.1.1",
        "PUBLISHER": "Example Company",
        "EXECUTABLE_NAME": "example-project",
        "ICON": icon,
        "PROJECT_ROOT": project_root or tmp_path,
        "SETTINGS_MODULE": "myproject.settings",
        "WSGI_APPLICATION": "myproject.wsgi.application",
    }

    return create_build_context(target_platform="windows", config=config)


def write_icon(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-icon")


def test_bundled_icon_path_without_an_icon(tmp_path):
    context = make_context(tmp_path)

    assert bundled_icon_path(context) is None


def test_bundled_icon_path_inside_the_project(tmp_path):
    icon = tmp_path / "assets" / "icon.ico"

    write_icon(icon)

    context = make_context(tmp_path, icon=icon)

    relative = bundled_icon_path(context)

    assert relative == "assets/icon.ico"
    assert (context.app_dir / relative).is_file()


def test_bundled_icon_path_copies_icons_from_outside_the_project(tmp_path):
    icon = tmp_path / "external" / "brand.ico"

    write_icon(icon)

    context = make_context(
        tmp_path,
        icon=icon,
        project_root=tmp_path / "project",
    )

    relative = bundled_icon_path(context)

    assert relative == "assets/icon.ico"
    assert (context.app_dir / relative).is_file()
