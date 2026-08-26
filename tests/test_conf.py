"""Tests for the simplified builder configuration."""

from pathlib import Path

import pytest
from django.core.management.base import CommandError
from django.test import override_settings

from django_binary_builder.conf import get_builder_settings


@override_settings(DJANGO_BINARY_BUILDER={})
def test_defaults_are_derived_from_the_project():
    config = get_builder_settings()

    assert config["NAME"] == "tests"
    assert config["EXECUTABLE_NAME"] == "tests"
    assert config["VERSION"] == "0.1.0"
    assert config["PUBLISHER"] == "tests"
    assert config["ICON"] is None
    assert config["SETTINGS_MODULE"] == "tests.settings"


def test_user_settings_are_applied(settings):
    settings.DJANGO_BINARY_BUILDER = {
        "NAME": "Example Project",
        "VERSION": "0.1.1",
        "PUBLISHER": "Example Company",
        "EXECUTABLE_NAME": "example-project",
        "ICON": Path("assets") / "icon.ico",
    }

    config = get_builder_settings()

    assert config["NAME"] == "Example Project"
    assert config["VERSION"] == "0.1.1"
    assert config["PUBLISHER"] == "Example Company"
    assert config["EXECUTABLE_NAME"] == "example-project"
    assert config["ICON"] == Path(settings.BASE_DIR) / "assets" / "icon.ico"


def test_unknown_keys_are_ignored_with_a_warning(settings):
    settings.DJANGO_BINARY_BUILDER = {"NAME": "App", "TYPO_KEY": 1}

    config = get_builder_settings()

    assert config["NAME"] == "App"
    assert len(config["WARNINGS"]) == 1
    assert "TYPO_KEY" in config["WARNINGS"][0]


def test_overrides_win_over_user_settings(settings):
    settings.DJANGO_BINARY_BUILDER = {"NAME": "From settings"}

    config = get_builder_settings({"NAME": "From override"})

    assert config["NAME"] == "From override"


def test_invalid_executable_name_is_rejected(settings):
    settings.DJANGO_BINARY_BUILDER = {"EXECUTABLE_NAME": "not valid!"}

    with pytest.raises(CommandError, match="EXECUTABLE_NAME"):
        get_builder_settings()


def test_invalid_version_is_rejected(settings):
    settings.DJANGO_BINARY_BUILDER = {"VERSION": 12}

    with pytest.raises(CommandError, match="VERSION"):
        get_builder_settings()


def test_missing_settings_module_is_rejected(settings, monkeypatch):
    settings.DJANGO_BINARY_BUILDER = {}
    settings.SETTINGS_MODULE = None
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)

    with pytest.raises(CommandError, match="DJANGO_SETTINGS_MODULE"):
        get_builder_settings()
