from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.core.management.base import CommandError

from django_binary_builder.conf import (
    DEFAULTS,
    deep_merge,
    get_builder_settings,
    make_safe_filename,
    validate_executable_name,
)


def test_deep_merge_preserves_untouched_keys():
    base = {"A": 1, "NESTED": {"X": 1, "Y": 2}}
    override = {"NESTED": {"Y": 3, "Z": 4}}

    result = deep_merge(base, override)

    assert result == {"A": 1, "NESTED": {"X": 1, "Y": 3, "Z": 4}}
    assert base["NESTED"]["Y"] == 2


def test_deep_merge_overrides_scalars():
    result = deep_merge({"A": 1, "B": 2}, {"B": 3})

    assert result == {"A": 1, "B": 3}


def test_deep_merge_replaces_mismatched_types():
    result = deep_merge({"A": {"X": 1}}, {"A": "scalar"})

    assert result["A"] == "scalar"


def test_defaults_are_applied(settings):
    settings.DJANGO_BINARY_BUILDER = {}

    config = get_builder_settings()

    assert config["SERVER"]["PORT"] == DEFAULTS["SERVER"]["PORT"]
    assert config["DATABASE"]["MODE"] == "sqlite"
    assert config["INITIAL_ADMIN"]["USERNAME"] == "admin"
    assert config["ENVIRONMENT"]["SNAPSHOT_FILENAME"] == ("runtime-environment.json")


def test_relative_paths_normalize_under_project_root(settings, tmp_path):
    settings.DJANGO_BINARY_BUILDER = {
        "OUTPUT_DIR": "dist-output",
        "WORK_DIR": tmp_path / "absolute-work",
    }

    config = get_builder_settings()

    project_root = Path(django_settings.BASE_DIR).resolve()

    assert config["OUTPUT_DIR"] == project_root / "dist-output"
    assert config["WORK_DIR"] == Path(tmp_path / "absolute-work").resolve()


def test_name_defaults_to_project_root_name(settings):
    settings.DJANGO_BINARY_BUILDER = {}

    config = get_builder_settings()

    project_root = Path(django_settings.BASE_DIR).resolve()

    assert config["NAME"] == project_root.name


def test_executable_name_derives_from_name(settings):
    settings.DJANGO_BINARY_BUILDER = {"NAME": "My Cool App!"}

    config = get_builder_settings()

    assert config["EXECUTABLE_NAME"] == "My-Cool-App"


def test_make_safe_filename_handles_unsafe_characters():
    assert make_safe_filename("My App: v2.0!!") == "My-App-v2-0"
    assert make_safe_filename("///") == "django-binary-builder"
    assert make_safe_filename("  spaced  name  ") == "spaced-name"


@pytest.mark.parametrize(
    "bad_name",
    ["", ".hidden", "has space", "slash/name", "CON", "a" * 101],
)
def test_validate_executable_name_rejects_invalid_names(bad_name):
    with pytest.raises(CommandError):
        validate_executable_name(bad_name)


def test_validate_executable_name_accepts_valid_names():
    assert validate_executable_name("my-app_2") == "my-app_2"


def test_invalid_port_type_raises(settings):
    settings.DJANGO_BINARY_BUILDER = {"SERVER": {"PORT": "8765"}}

    with pytest.raises(CommandError) as error:
        get_builder_settings()

    assert "SERVER.PORT" in str(error.value)


def test_invalid_database_mode_raises(settings):
    settings.DJANGO_BINARY_BUILDER = {"DATABASE": {"MODE": "mongo"}}

    with pytest.raises(CommandError):
        get_builder_settings()


def test_onefile_mode_rejected(settings):
    settings.DJANGO_BINARY_BUILDER = {"BUILD": {"MODE": "onefile"}}

    with pytest.raises(CommandError) as error:
        get_builder_settings()

    assert "onedir" in str(error.value)


def test_invalid_sqlite_filename_raises(settings):
    settings.DJANGO_BINARY_BUILDER = {
        "DATABASE": {
            "SQLITE": {"FILENAME": "../escape.sqlite3"},
        }
    }

    with pytest.raises(CommandError) as error:
        get_builder_settings()

    assert "FILENAME" in str(error.value)


def test_runtime_directories_derive_from_publisher(settings):
    settings.DJANGO_BINARY_BUILDER = {
        "NAME": "My Application",
        "PUBLISHER": "Example Company",
    }

    config = get_builder_settings()

    assert config["RUNTIME"]["COMPANY_DIRECTORY"] == "Example-Company"
    assert config["RUNTIME"]["APPLICATION_DIRECTORY"] == "My-Application"


def test_copy_initial_database_requires_source(settings):
    settings.DJANGO_BINARY_BUILDER = {
        "DATABASE": {
            "SQLITE": {
                "COPY_INITIAL_DATABASE": True,
                "INITIAL_DATABASE": None,
            },
        }
    }

    with pytest.raises(CommandError):
        get_builder_settings()


def test_invalid_privileges_raises(settings):
    settings.DJANGO_BINARY_BUILDER = {
        "WINDOWS": {"PRIVILEGES": "powers"},
    }

    with pytest.raises(CommandError):
        get_builder_settings()


def test_server_mode_defaults_to_webview(settings):
    settings.DJANGO_BINARY_BUILDER = {}

    config = get_builder_settings()

    assert config["SERVER"]["MODE"] == "webview"


def test_invalid_server_mode_raises(settings):
    settings.DJANGO_BINARY_BUILDER = {"SERVER": {"MODE": "popup"}}

    with pytest.raises(CommandError) as error:
        get_builder_settings()

    assert "SERVER.MODE" in str(error.value)


def test_webview_title_defaults_to_name(settings):
    settings.DJANGO_BINARY_BUILDER = {"NAME": "My Cool App"}

    config = get_builder_settings()

    assert config["WEBVIEW"]["TITLE"] == "My Cool App"
    assert config["WEBVIEW"]["WIDTH"] == 1200
    assert config["WEBVIEW"]["HEIGHT"] == 800
    assert config["WEBVIEW"]["RESIZABLE"] is True


def test_invalid_webview_width_raises(settings):
    settings.DJANGO_BINARY_BUILDER = {"WEBVIEW": {"WIDTH": 0}}

    with pytest.raises(CommandError):
        get_builder_settings()
