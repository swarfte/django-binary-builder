import sys
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_binary_builder.enums import TargetPlatform


def _build_options(**overrides):
    options = {
        "name": None,
        "app_version": None,
        "output": None,
        "console": False,
        "clean": False,
        "no_collectstatic": False,
        "env_file": None,
        "no_env": False,
    }
    options.update(overrides)
    return options


def test_parser_has_no_version_conflict():
    from django_binary_builder.management.commands.binary import Command

    parser = Command().create_parser("manage.py", "binary")
    help_text = parser.format_help()

    assert "--app-version" in help_text
    assert "--generate-only" in help_text
    assert "--skip-installer" in help_text
    assert "--no-collectstatic" in help_text
    assert "--env-file" in help_text
    assert "--no-env" in help_text

    version_actions = [
        action for action in parser._actions if "--version" in action.option_strings
    ]

    assert len(version_actions) == 1

    parsed = parser.parse_args(["windows", "--app-version", "9.9.9"])

    assert parsed.platform == "windows"
    assert parsed.app_version == "9.9.9"


def test_platform_choices_match_spec():
    from django_binary_builder.management.commands.binary import Command

    parser = Command().create_parser("manage.py", "binary")

    platform_action = next(
        action for action in parser._actions if action.dest == "platform"
    )

    assert sorted(platform_action.choices) == [
        "linux",
        "macos",
        "windows",
    ]


def test_app_version_override_applies_to_config(settings):
    from django_binary_builder.conf import get_builder_settings
    from django_binary_builder.management.commands.binary import Command

    settings.DJANGO_BINARY_BUILDER = {"VERSION": "1.2.3"}

    command = Command()
    overrides = command._build_config_overrides(_build_options(app_version="9.9.9"))

    config = get_builder_settings(overrides)

    assert config["VERSION"] == "9.9.9"


def test_name_override_rederives_executable_name(settings):
    from django_binary_builder.management.commands.binary import Command

    settings.DJANGO_BINARY_BUILDER = {}

    command = Command()
    overrides = command._build_config_overrides(_build_options(name="My Cool App"))

    assert overrides["NAME"] == "My Cool App"
    assert overrides["EXECUTABLE_NAME"] is None


def test_name_override_keeps_explicit_executable_name(settings):
    from django_binary_builder.management.commands.binary import Command

    settings.DJANGO_BINARY_BUILDER = {
        "EXECUTABLE_NAME": "custom-name",
    }

    command = Command()
    overrides = command._build_config_overrides(_build_options(name="My Cool App"))

    assert overrides["NAME"] == "My Cool App"
    assert "EXECUTABLE_NAME" not in overrides


def test_no_env_disables_environment(settings):
    from django_binary_builder.management.commands.binary import Command

    command = Command()
    overrides = command._build_config_overrides(_build_options(no_env=True))

    assert overrides["ENVIRONMENT"]["ENABLED"] is False


def test_env_file_appends_after_configured_files(settings):
    from django_binary_builder.management.commands.binary import Command

    settings.DJANGO_BINARY_BUILDER = {
        "ENVIRONMENT": {"FILES": [".env.common"]},
    }

    command = Command()
    overrides = command._build_config_overrides(_build_options(env_file=".env.local"))

    assert overrides["ENVIRONMENT"]["FILES"] == [
        ".env.common",
        Path(".env.local"),
    ]


def test_host_validation_rejects_mismatched_host(monkeypatch):
    from django_binary_builder.platforms.base import (
        validate_host_platform,
    )

    monkeypatch.setattr(sys, "platform", "linux")

    with pytest.raises(CommandError) as error:
        validate_host_platform(TargetPlatform.WINDOWS)

    assert "must be performed on 'win32'" in str(error.value)


def test_host_validation_accepts_matching_host(monkeypatch):
    from django_binary_builder.platforms.base import (
        validate_host_platform,
    )

    monkeypatch.setattr(sys, "platform", "win32")

    validate_host_platform(TargetPlatform.WINDOWS)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows host required",
)
def test_check_skip_installer_runs_end_to_end(
    settings,
    capsys,
    tmp_path,
):
    settings.DJANGO_BINARY_BUILDER = {
        "ENVIRONMENT": {"ENABLED": False},
        "OUTPUT_DIR": tmp_path / "release",
        "WORK_DIR": tmp_path / "work",
        "BUILD": {"COLLECT_STATIC": False},
    }

    call_command(
        "binary",
        "windows",
        "--check",
        "--skip-installer",
    )

    output = capsys.readouterr().out

    assert "All Windows build checks passed." in output
