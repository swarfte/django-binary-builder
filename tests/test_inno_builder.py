import codecs
import subprocess
from types import SimpleNamespace

import pytest
from django.core.management.base import CommandError

from django_binary_builder.builders.inno_setup import (
    DEFAULT_INNO_PATHS,
    find_inno_setup,
    generate_app_id,
    generate_inno_script,
    run_inno_setup,
)


class TestIsccDiscovery:
    def test_configured_path_wins(self, build_context, tmp_path):
        compiler = tmp_path / "custom" / "ISCC.exe"
        compiler.parent.mkdir(parents=True)
        compiler.write_bytes(b"exe")

        context = build_context(
            WINDOWS={"INNO_SETUP_COMPILER": compiler},
        )

        assert find_inno_setup(context) == compiler.resolve()

    def test_configured_missing_path_returns_none(self, build_context):
        context = build_context(
            WINDOWS={"INNO_SETUP_COMPILER": "C:/missing/ISCC.exe"},
        )

        assert find_inno_setup(context) is None

    def test_which_fallback(
        self,
        build_context,
        monkeypatch,
        tmp_path,
    ):
        compiler = tmp_path / "ISCC.exe"
        compiler.write_bytes(b"exe")

        monkeypatch.setattr(
            "django_binary_builder.builders.inno_setup.DEFAULT_INNO_PATHS",
            (),
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(returncode=0),
        )

        import shutil

        monkeypatch.setattr(
            shutil,
            "which",
            lambda name: str(compiler) if name == "ISCC.exe" else None,
        )

        context = build_context()

        assert find_inno_setup(context) == compiler.resolve()

    def test_default_paths_fallback(
        self,
        build_context,
        monkeypatch,
        tmp_path,
    ):
        fake_default = tmp_path / "ISCC.exe"
        fake_default.write_bytes(b"exe")

        import shutil

        monkeypatch.setattr(shutil, "which", lambda name: None)
        monkeypatch.setattr(
            "django_binary_builder.builders.inno_setup.DEFAULT_INNO_PATHS",
            (fake_default,),
        )

        context = build_context()

        assert find_inno_setup(context) == fake_default.resolve()

    def test_returns_none_when_not_found(self, build_context, monkeypatch):
        import shutil

        monkeypatch.setattr(shutil, "which", lambda name: None)
        monkeypatch.setattr(
            "django_binary_builder.builders.inno_setup.DEFAULT_INNO_PATHS",
            (),
        )

        context = build_context()

        assert find_inno_setup(context) is None


class TestAppId:
    def test_app_id_is_stable(self):
        first = generate_app_id(
            publisher="Example Company",
            app_name="My Application",
        )
        second = generate_app_id(
            publisher="Example Company",
            app_name="My Application",
        )

        assert first == second
        assert first.startswith("{")
        assert first.endswith("}")

    def test_app_id_ignores_version(self):
        base = generate_app_id(
            publisher="Example Company",
            app_name="My Application",
        )

        assert base == generate_app_id(
            publisher="Example Company",
            app_name="My Application",
        )

    def test_app_id_changes_with_name(self):
        base = generate_app_id(
            publisher="Example Company",
            app_name="My Application",
        )
        other = generate_app_id(
            publisher="Example Company",
            app_name="Other Application",
        )

        assert base != other


class TestScriptGeneration:
    def test_script_is_utf8_with_bom(self, build_context):
        context = build_context()

        script_path = generate_inno_script(context)

        raw = script_path.read_bytes()

        assert raw.startswith(codecs.BOM_UTF8)

    def test_script_contains_expected_directives(self, build_context):
        context = build_context()

        content = generate_inno_script(context).read_text(encoding="utf-8-sig")

        assert "PrivilegesRequired=lowest" in content
        assert "DefaultDirName={localappdata}\\Programs" in content
        assert "recursesubdirs" in content
        assert (
            f"OutputBaseFilename={context.installer_filename.removesuffix('.exe')}"
            in content
        )
        assert str(context.bundle_dir) in content

        assert "[UninstallDelete]" not in content


class TestCompilation:
    def test_missing_compiler_raises(self, build_context, monkeypatch):
        import shutil

        monkeypatch.setattr(shutil, "which", lambda name: None)
        monkeypatch.setattr(
            "django_binary_builder.builders.inno_setup.DEFAULT_INNO_PATHS",
            (),
        )

        context = build_context()

        with pytest.raises(CommandError):
            run_inno_setup(context)

    def test_missing_bundle_raises(
        self,
        build_context,
        tmp_path,
        monkeypatch,
    ):
        compiler = tmp_path / "ISCC.exe"
        compiler.write_bytes(b"exe")

        context = build_context(
            WINDOWS={"INNO_SETUP_COMPILER": compiler},
        )

        context.inno_script_path.parent.mkdir(parents=True)
        context.inno_script_path.write_text("; empty", encoding="utf-8")

        with pytest.raises(CommandError):
            run_inno_setup(context)

    def test_failed_compilation_raises(
        self,
        build_context,
        tmp_path,
        monkeypatch,
    ):
        compiler = tmp_path / "ISCC.exe"
        compiler.write_bytes(b"exe")

        context = build_context(
            WINDOWS={"INNO_SETUP_COMPILER": compiler},
        )

        context.inno_script_path.parent.mkdir(parents=True)
        context.inno_script_path.write_text("; empty", encoding="utf-8")
        context.bundle_dir.mkdir(parents=True)

        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(returncode=2),
        )

        with pytest.raises(CommandError) as error:
            run_inno_setup(context)

        assert "exit code 2" in str(error.value)

    def test_missing_installer_artifact_raises(
        self,
        build_context,
        tmp_path,
        monkeypatch,
    ):
        compiler = tmp_path / "ISCC.exe"
        compiler.write_bytes(b"exe")

        context = build_context(
            WINDOWS={"INNO_SETUP_COMPILER": compiler},
        )

        context.inno_script_path.parent.mkdir(parents=True)
        context.inno_script_path.write_text("; empty", encoding="utf-8")
        context.bundle_dir.mkdir(parents=True)

        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(returncode=0),
        )

        with pytest.raises(CommandError) as error:
            run_inno_setup(context)

        assert "installer was not found" in str(error.value)


def test_default_inno_paths_match_spec():
    from pathlib import Path

    assert DEFAULT_INNO_PATHS[0] == Path(
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    )
    assert DEFAULT_INNO_PATHS[1] == Path(r"C:\Program Files\Inno Setup 6\ISCC.exe")
