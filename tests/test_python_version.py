"""Tests for ``.python-version`` handling."""

import sys

import pytest
from django.core.management.base import CommandError

from django_binary_builder.python_version import (
    current_python_version,
    resolve_python_version,
)


def test_missing_file_is_generated_with_current_version(tmp_path):
    version = resolve_python_version(tmp_path)

    assert version == current_python_version()

    pinned = (tmp_path / ".python-version").read_text(encoding="utf-8").strip()

    assert pinned == version
    assert version == f"{sys.version_info.major}.{sys.version_info.minor}"


def test_dry_run_does_not_write_the_file(tmp_path):
    resolve_python_version(tmp_path, dry_run=True)

    assert not (tmp_path / ".python-version").exists()


def test_existing_file_is_used_as_is(tmp_path):
    version_file = tmp_path / ".python-version"
    version_file.write_text(
        f"{sys.version_info.major}.{sys.version_info.minor}\n",
        encoding="utf-8",
    )

    version = resolve_python_version(tmp_path)

    assert version == f"{sys.version_info.major}.{sys.version_info.minor}"


def test_full_version_pin_matches_on_major_minor(tmp_path):
    version_file = tmp_path / ".python-version"
    version_file.write_text(
        f"{sys.version_info.major}.{sys.version_info.minor}.99",
        encoding="utf-8",
    )

    version = resolve_python_version(tmp_path)

    assert version.endswith(".99")


def test_version_mismatch_is_rejected(tmp_path):
    (tmp_path / ".python-version").write_text("3.7\n", encoding="utf-8")

    with pytest.raises(CommandError, match="pins Python 3.7"):
        resolve_python_version(tmp_path)


def test_empty_file_is_rejected(tmp_path):
    (tmp_path / ".python-version").write_text("   \n", encoding="utf-8")

    with pytest.raises(CommandError, match="empty"):
        resolve_python_version(tmp_path)


def test_invalid_content_is_rejected(tmp_path):
    (tmp_path / ".python-version").write_text("latest\n", encoding="utf-8")

    with pytest.raises(CommandError, match="Python version"):
        resolve_python_version(tmp_path)
