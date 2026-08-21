from pathlib import Path

from django.conf import settings

from django_binary_builder.conf import get_builder_settings
from django_binary_builder.context import create_build_context


def make_context(tmp_path, **overrides):
    builder_settings = {
        "NAME": "Test App",
        "VERSION": "2.5.1",
        "PUBLISHER": "Test Publisher",
        "EXECUTABLE_NAME": "test-app",
        "OUTPUT_DIR": tmp_path / "release",
        "WORK_DIR": tmp_path / "work",
    }
    builder_settings.update(overrides)

    settings.DJANGO_BINARY_BUILDER = builder_settings

    config = get_builder_settings()

    return create_build_context(
        target_platform="windows",
        config=config,
    )


def test_build_context_paths(tmp_path, settings):
    context = make_context(tmp_path)

    assert context.work_dir == (tmp_path / "work" / "windows").resolve()
    assert context.generated_dir == context.work_dir / "generated"
    assert context.pyinstaller_build_dir == context.work_dir / "build"
    assert context.pyinstaller_dist_dir == context.work_dir / "dist"
    assert context.release_dir == (tmp_path / "release" / "windows").resolve()


def test_build_context_artifact_paths(tmp_path, settings):
    context = make_context(tmp_path)

    assert context.launcher_path == context.generated_dir / "launcher.py"
    assert context.spec_path == context.generated_dir / "application.spec"
    assert context.inno_script_path == context.generated_dir / "installer.iss"
    assert (
        context.runtime_environment_path
        == context.generated_dir / "runtime-environment.json"
    )
    assert (
        context.runtime_defaults_path == context.generated_dir / "runtime-defaults.json"
    )
    assert context.bundle_dir == context.pyinstaller_dist_dir / "test-app"
    assert context.executable_path == context.bundle_dir / "test-app.exe"
    assert context.installer_filename == "test-app-2.5.1-Setup.exe"
    assert context.installer_path == context.release_dir / "test-app-2.5.1-Setup.exe"


def test_build_context_database_mode_flags(tmp_path, settings):
    sqlite_context = make_context(tmp_path)

    assert sqlite_context.uses_sqlite is True
    assert sqlite_context.uses_external_database is False
    assert sqlite_context.database_mode == "sqlite"

    external_context = make_context(
        tmp_path,
        DATABASE={"MODE": "external"},
    )

    assert external_context.uses_sqlite is False
    assert external_context.uses_external_database is True


def test_build_context_runtime_directories(tmp_path, settings):
    context = make_context(
        tmp_path,
        RUNTIME={
            "COMPANY_DIRECTORY": "Company",
            "APPLICATION_DIRECTORY": "App",
        },
    )

    assert context.runtime_company_directory == "Company"
    assert context.runtime_application_directory == "App"


def test_build_context_project_root(tmp_path, settings):
    context = make_context(tmp_path)

    assert context.project_root == Path(settings.BASE_DIR).resolve()
