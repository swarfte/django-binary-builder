import json
import os

import pytest
from django.core.management.base import CommandError

from django_binary_builder.environment import prepare_build_environment
from django_binary_builder.environment.policy import (
    is_secret_name,
    select_variables,
)
from django_binary_builder.environment.snapshot import (
    read_environment_snapshot,
    write_environment_snapshot,
)
from django_binary_builder.environment.validation import (
    redact_text,
    summarize_variables,
    validate_required_variables,
    verify_snapshot_selection,
)
from django_binary_builder.runtime.environment import (
    apply_bundled_environment,
)


def make_config(**environment_overrides):
    environment = {
        "ENABLED": True,
        "FILES": [],
        "INCLUDE": [],
        "EXCLUDE": [],
        "REQUIRED": [],
        "ALLOW_SECRETS": False,
        "OVERRIDE_PROCESS_ENV": False,
    }
    environment.update(environment_overrides)

    return {"ENVIRONMENT": environment}


def write_env_file(tmp_path, content):
    path = tmp_path / ".env"
    path.write_text(content, encoding="utf-8")
    return path


class TestSelectVariables:
    def test_include_glob_pattern(self):
        pool = {
            "APP_FEATURE_A": "1",
            "APP_FEATURE_B": "2",
            "OTHER": "3",
        }

        selected = select_variables(
            pool,
            include=["APP_FEATURE_*"],
            exclude=[],
        )

        assert selected == {"APP_FEATURE_A": "1", "APP_FEATURE_B": "2"}

    def test_empty_include_selects_nothing(self):
        selected = select_variables(
            {"A": "1"},
            include=[],
            exclude=[],
        )

        assert selected == {}

    def test_star_include_selects_everything(self):
        selected = select_variables(
            {"A": "1", "B": "2"},
            include=["*"],
            exclude=[],
        )

        assert selected == {"A": "1", "B": "2"}

    def test_exclude_wins_over_include(self):
        selected = select_variables(
            {"A": "1", "SECRET_B": "2"},
            include=["*"],
            exclude=["SECRET_*"],
        )

        assert selected == {"A": "1"}


class TestSecretNames:
    @pytest.mark.parametrize(
        "name",
        [
            "DJANGO_SECRET_KEY",
            "MY_PASSWORD",
            "API_TOKEN",
            "SERVICE_API_KEY",
            "PRIVATE_KEY_PATH",
            "DATABASE_URL",
            "DB_PASSWORD",
        ],
    )
    def test_secret_patterns(self, name):
        assert is_secret_name(name) is True

    def test_normal_names_are_not_secret(self):
        assert is_secret_name("DJANGO_ALLOWED_HOSTS") is False


class TestPrepareBuildEnvironment:
    def test_secret_blocked_when_not_allowed(self, tmp_path):
        write_env_file(tmp_path, "MY_API_TOKEN=supersecret\n")

        with pytest.raises(CommandError) as error:
            prepare_build_environment(
                config=make_config(INCLUDE=["*"]),
                project_root=tmp_path,
            )

        assert "ALLOW_SECRETS" in str(error.value)
        assert "MY_API_TOKEN" in str(error.value)
        assert "supersecret" not in str(error.value)

    def test_secret_allowed_with_warning_and_no_value_in_output(
        self,
        tmp_path,
    ):
        write_env_file(tmp_path, "MY_API_TOKEN=supersecret\n")

        messages = []

        result = prepare_build_environment(
            config=make_config(INCLUDE=["*"], ALLOW_SECRETS=True),
            project_root=tmp_path,
            emit_warning=messages.append,
        )

        assert result.secret_names == ["MY_API_TOKEN"]
        assert result.variables == {"MY_API_TOKEN": "supersecret"}

        joined = "\n".join(messages)

        assert "MY_API_TOKEN" in joined
        assert "supersecret" not in joined

    def test_required_variable_missing(self, tmp_path):
        write_env_file(tmp_path, "OTHER=1\n")

        with pytest.raises(CommandError) as error:
            prepare_build_environment(
                config=make_config(REQUIRED=["DJANGO_SECRET_KEY"]),
                project_root=tmp_path,
            )

        assert "DJANGO_SECRET_KEY" in str(error.value)

    def test_disabled_environment_returns_empty(self, tmp_path):
        result = prepare_build_environment(
            config=make_config(ENABLED=False),
            project_root=tmp_path,
        )

        assert result.enabled is False
        assert result.variables == {}

    def test_excluded_variables_not_selected(self, tmp_path):
        write_env_file(
            tmp_path,
            "KEEP=1\nMY_TOKEN=secret\n",
        )

        result = prepare_build_environment(
            config=make_config(
                INCLUDE=["*"],
                EXCLUDE=["MY_*"],
            ),
            project_root=tmp_path,
        )

        assert result.variables == {"KEEP": "1"}


class TestSnapshot:
    def test_snapshot_round_trip(self, tmp_path):
        path = tmp_path / "runtime-environment.json"

        write_environment_snapshot(path, {"A": "1", "B": "2"})

        payload = json.loads(path.read_text(encoding="utf-8"))

        assert payload["schema_version"] == 1
        assert payload["variables"] == {"A": "1", "B": "2"}

        assert read_environment_snapshot(path) == {"A": "1", "B": "2"}

    def test_snapshot_has_no_source_paths(self, tmp_path):
        env_file = write_env_file(tmp_path, "A=1\n")
        path = tmp_path / "runtime-environment.json"

        result = prepare_build_environment(
            config=make_config(INCLUDE=["*"]),
            project_root=tmp_path,
        )

        write_environment_snapshot(path, result.variables)

        content = path.read_text(encoding="utf-8")

        assert str(env_file) not in content
        assert str(tmp_path) not in content


class TestRuntimeLoading:
    def test_process_environment_overrides_snapshot(
        self,
        tmp_path,
        monkeypatch,
    ):
        snapshot = write_environment_snapshot(
            tmp_path / "runtime-environment.json",
            {
                "DBB_TEST_RUNTIME_VAR": "from-snapshot",
                "DBB_TEST_RUNTIME_ONLY": "snapshot-value",
            },
        )

        monkeypatch.setenv("DBB_TEST_RUNTIME_VAR", "from-process")
        monkeypatch.delenv("DBB_TEST_RUNTIME_ONLY", raising=False)

        applied = apply_bundled_environment(
            "tests.test_project.settings",
            snapshot_filename=snapshot.name,
            local_dir=tmp_path,
        )

        assert os.environ["DBB_TEST_RUNTIME_VAR"] == "from-process"
        assert os.environ["DBB_TEST_RUNTIME_ONLY"] == "snapshot-value"
        assert "DBB_TEST_RUNTIME_ONLY" in applied

        monkeypatch.delenv("DBB_TEST_RUNTIME_VAR")
        monkeypatch.delenv("DBB_TEST_RUNTIME_ONLY")

    def test_runtime_marker_and_settings_module(
        self,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)

        apply_bundled_environment(
            "some.module.settings",
            local_dir=tmp_path,
        )

        assert os.environ["DJANGO_BINARY_RUNTIME"] == "1"
        assert os.environ["DJANGO_SETTINGS_MODULE"] == ("some.module.settings")

        monkeypatch.delenv("DJANGO_BINARY_RUNTIME")


class TestRedaction:
    def test_redact_known_values(self):
        redacted = redact_text(
            "connection failed with password=hunter2",
            secret_values=["hunter2"],
        )

        assert "hunter2" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_key_value_patterns(self):
        redacted = redact_text("error: password='abc123' token=xyz789")

        assert "abc123" not in redacted
        assert "xyz789" not in redacted
        assert "[REDACTED]" in redacted

    def test_summarize_variables_never_shows_values(self):
        summary = summarize_variables({"SECRET_A": "value-a", "B": "v"})

        assert "value-a" not in summary
        assert "SECRET_A=[REDACTED]" in summary
        assert "B=[REDACTED]" in summary

    def test_verify_snapshot_selection(self):
        with pytest.raises(CommandError):
            verify_snapshot_selection(
                {"BAD_VAR": "1"},
                exclude=["BAD_*"],
            )

        verify_snapshot_selection({"GOOD": "1"}, exclude=["BAD_*"])

    def test_validate_required_empty_value_counts_as_missing(self):
        with pytest.raises(CommandError):
            validate_required_variables({"A": ""}, required=["A"])
