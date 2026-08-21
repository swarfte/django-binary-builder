import os

import pytest
from django.core.management.base import CommandError

from django_binary_builder.environment.loader import (
    interpolate_variables,
    load_environment_files,
    merge_with_process_environment,
    resolve_environment_files,
)


def write_env(path, content):
    path.write_text(content, encoding="utf-8")
    return path


class TestResolveEnvironmentFiles:
    def test_configured_and_extra_files_are_ordered(self, tmp_path):
        configured = write_env(tmp_path / "a.env", "A=1\n")
        extra = write_env(tmp_path / "b.env", "B=2\n")

        files = resolve_environment_files(
            configured=[configured],
            extra=extra,
            project_root=tmp_path,
        )

        assert files == [configured, extra]

    def test_missing_extra_file_raises(self, tmp_path):
        existing = write_env(tmp_path / ".env", "A=1\n")

        with pytest.raises(CommandError):
            resolve_environment_files(
                configured=[existing],
                extra=tmp_path / "missing.env",
                project_root=tmp_path,
            )

    def test_missing_explicit_file_raises(self, tmp_path):
        with pytest.raises(CommandError) as error:
            resolve_environment_files(
                configured=[tmp_path / "nope.env"],
                extra=None,
                project_root=tmp_path,
            )

        assert "was not found" in str(error.value)

    def test_default_env_used_when_nothing_configured(self, tmp_path):
        write_env(tmp_path / ".env", "A=1\n")

        files = resolve_environment_files(
            configured=[],
            extra=None,
            project_root=tmp_path,
        )

        assert files == [tmp_path / ".env"]

    def test_missing_default_env_is_ignored(self, tmp_path):
        files = resolve_environment_files(
            configured=[],
            extra=None,
            project_root=tmp_path,
        )

        assert files == []


class TestLoadEnvironmentFiles:
    def test_later_files_override_earlier_files(self, tmp_path):
        first = write_env(tmp_path / "a.env", "X=1\nY=first\n")
        second = write_env(tmp_path / "b.env", "X=2\nZ=3\n")

        merged = load_environment_files([first, second])

        assert merged == {"X": "2", "Y": "first", "Z": "3"}

    def test_extra_file_loads_after_configured_files(self, tmp_path):
        configured = write_env(tmp_path / "a.env", "X=from-configured\n")
        extra = write_env(tmp_path / "b.env", "X=from-extra\n")

        merged = load_environment_files([configured, extra])

        assert merged["X"] == "from-extra"


class TestInterpolation:
    def test_simple_interpolation(self):
        values = {"A": "${B}", "B": "hello"}

        resolved, unresolved = interpolate_variables(
            values,
            environment={},
        )

        assert resolved["A"] == "hello"
        assert unresolved == []

    def test_interpolation_falls_back_to_process_environment(self):
        resolved, _ = interpolate_variables(
            {"A": "${SOME_TEST_VAR}"},
            environment={"SOME_TEST_VAR": "from-env"},
        )

        assert resolved["A"] == "from-env"

    def test_unresolved_reference_is_reported(self):
        resolved, unresolved = interpolate_variables(
            {"A": "${MISSING}"},
            environment={},
        )

        assert resolved["A"] == "${MISSING}"
        assert unresolved == ["A"]

    def test_circular_reference_raises(self):
        with pytest.raises(CommandError) as error:
            interpolate_variables(
                {"A": "${B}", "B": "${A}"},
                environment={},
            )

        assert "Circular" in str(error.value)

    def test_self_reference_raises(self):
        with pytest.raises(CommandError):
            interpolate_variables(
                {"A": "prefix-${A}"},
                environment={},
            )


class TestProcessEnvironmentPrecedence:
    def test_process_env_wins_by_default(self, monkeypatch):
        monkeypatch.setenv("DBB_TEST_PRECEDENCE", "from-process")

        merged = merge_with_process_environment(
            {"DBB_TEST_PRECEDENCE": "from-file", "ONLY_FILE": "1"},
            override_process_env=False,
            environment=dict(os.environ),
        )

        assert merged["DBB_TEST_PRECEDENCE"] == "from-process"
        assert merged["ONLY_FILE"] == "1"

    def test_file_wins_when_override_enabled(self, monkeypatch):
        monkeypatch.setenv("DBB_TEST_PRECEDENCE", "from-process")

        merged = merge_with_process_environment(
            {"DBB_TEST_PRECEDENCE": "from-file"},
            override_process_env=True,
            environment=dict(os.environ),
        )

        assert merged["DBB_TEST_PRECEDENCE"] == "from-file"

    def test_os_environ_is_never_modified(self, monkeypatch):
        monkeypatch.delenv("DBB_TEST_NEVER_SET", raising=False)

        merge_with_process_environment(
            {"DBB_TEST_NEVER_SET": "value"},
            override_process_env=False,
        )

        assert "DBB_TEST_NEVER_SET" not in os.environ
