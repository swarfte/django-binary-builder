import json

import pytest
from django.test import override_settings

from django_binary_builder.exceptions import RuntimeInitializationError
from django_binary_builder.runtime.database import (
    apply_environment_overrides,
    configure_runtime_database,
    validate_sqlite_filename,
)


class TestSqliteFilenameValidation:
    @pytest.mark.parametrize(
        "filename",
        ["db.sqlite3", "app.sqlite", "data.db"],
    )
    def test_valid_filenames(self, filename):
        assert validate_sqlite_filename(filename) == filename

    @pytest.mark.parametrize(
        "filename",
        [
            "db.txt",
            "folder/db.sqlite3",
            "../db.sqlite3",
            "C:\\data\\db.sqlite3",
            "",
            "db",
        ],
    )
    def test_invalid_filenames(self, filename):
        with pytest.raises(ValueError):
            validate_sqlite_filename(filename)


class TestSqliteConfiguration:
    def test_sqlite_database_moves_to_runtime_data_directory(
        self,
        tmp_path,
        settings,
    ):
        defaults = {
            "database": {
                "mode": "sqlite",
                "sqlite": {"filename": "runtime.sqlite3"},
            }
        }

        database = configure_runtime_database(
            defaults,
            runtime_root=tmp_path,
        )

        assert database["ENGINE"] == "django.db.backends.sqlite3"
        assert database["NAME"] == str(tmp_path / "data" / "runtime.sqlite3")
        assert database["NAME"].startswith(str(tmp_path))

    def test_resulting_config_keeps_standard_keys(self, tmp_path, settings):
        defaults = {
            "database": {
                "mode": "sqlite",
                "sqlite": {"filename": "runtime.sqlite3"},
            }
        }

        database = configure_runtime_database(
            defaults,
            runtime_root=tmp_path,
        )

        # Django's request handler requires these keys to exist.
        assert "ATOMIC_REQUESTS" in database
        assert "AUTOCOMMIT" in database
        assert "OPTIONS" in database


class TestExternalConfiguration:
    def test_project_settings_are_used_by_default(self, tmp_path, settings):
        defaults = {
            "database": {
                "mode": "external",
                "external": {"use_project_settings": True},
            }
        }

        with override_settings(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": "project-db",
                }
            }
        ):
            database = configure_runtime_database(
                defaults,
                runtime_root=tmp_path,
            )

        assert database["ENGINE"] == "django.db.backends.postgresql"
        assert database["NAME"] == "project-db"

    def test_database_json_overrides_project_settings(
        self,
        tmp_path,
        settings,
    ):
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        (config_dir / "database.json").write_text(
            json.dumps(
                {
                    "engine": "django.db.backends.mysql",
                    "name": "json-db",
                    "host": "json-host",
                }
            ),
            encoding="utf-8",
        )

        defaults = {
            "database": {
                "mode": "external",
                "external": {"use_project_settings": False},
            }
        }

        with override_settings(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": "project-db",
                    "HOST": "project-host",
                }
            }
        ):
            database = configure_runtime_database(
                defaults,
                runtime_root=tmp_path,
            )

        assert database["ENGINE"] == "django.db.backends.mysql"
        assert database["NAME"] == "json-db"
        assert database["HOST"] == "json-host"

    def test_environment_wins_over_database_json(
        self,
        tmp_path,
        settings,
        monkeypatch,
    ):
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        (config_dir / "database.json").write_text(
            json.dumps({"engine": "django.db.backends.mysql", "name": "json-db"}),
            encoding="utf-8",
        )

        defaults = {
            "database": {
                "mode": "external",
                "external": {"use_project_settings": False},
            }
        }

        monkeypatch.setenv("DJANGO_BINARY_DB_NAME", "env-db")
        monkeypatch.setenv("DJANGO_BINARY_DB_HOST", "env-host")

        database = configure_runtime_database(
            defaults,
            runtime_root=tmp_path,
        )

        assert database["NAME"] == "env-db"
        assert database["HOST"] == "env-host"
        assert database["ENGINE"] == "django.db.backends.mysql"

    def test_missing_database_json_raises(self, tmp_path, settings):
        defaults = {
            "database": {
                "mode": "external",
                "external": {"use_project_settings": False},
            }
        }

        with pytest.raises(RuntimeInitializationError) as error:
            configure_runtime_database(defaults, runtime_root=tmp_path)

        assert "database.json" in str(error.value)

    def test_invalid_json_raises(self, tmp_path, settings):
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        (config_dir / "database.json").write_text(
            "not json",
            encoding="utf-8",
        )

        defaults = {
            "database": {
                "mode": "external",
                "external": {"use_project_settings": False},
            }
        }

        with pytest.raises(RuntimeInitializationError):
            configure_runtime_database(defaults, runtime_root=tmp_path)

    def test_environment_overrides_apply_directly(self, monkeypatch):
        monkeypatch.setenv("DJANGO_BINARY_DB_USER", "env-user")
        monkeypatch.setenv("DJANGO_BINARY_DB_PORT", "5433")

        result = apply_environment_overrides(
            {"ENGINE": "x", "USER": "json-user", "PORT": 5432},
        )

        assert result["USER"] == "env-user"
        assert result["PORT"] == 5433

        monkeypatch.delenv("DJANGO_BINARY_DB_USER")
        monkeypatch.delenv("DJANGO_BINARY_DB_PORT")

    def test_invalid_mode_raises(self, tmp_path, settings):
        defaults = {"database": {"mode": "surprise"}}

        with pytest.raises(RuntimeInitializationError):
            configure_runtime_database(defaults, runtime_root=tmp_path)

    def test_invalid_sqlite_filename_raises_at_runtime(
        self,
        tmp_path,
        settings,
    ):
        defaults = {
            "database": {
                "mode": "sqlite",
                "sqlite": {"filename": "../bad.sqlite3"},
            }
        }

        with pytest.raises(RuntimeInitializationError):
            configure_runtime_database(defaults, runtime_root=tmp_path)
