"""Tests for the project bundling rules."""

from django_binary_builder.builders.bundle import _ignore_project_entry


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
