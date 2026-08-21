"""Central, non-secret build metadata and paths."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

RUNTIME_DEFAULTS_FILENAME = "runtime-defaults.json"
INSTALLER_SUFFIX = "-Setup.exe"


@dataclass(slots=True)
class BuildContext:
    target_platform: str
    app_name: str
    app_version: str
    publisher: str | None
    executable_name: str
    database_mode: str
    runtime_company_directory: str
    runtime_application_directory: str
    project_root: Path
    work_dir: Path
    generated_dir: Path
    pyinstaller_build_dir: Path
    pyinstaller_dist_dir: Path
    release_dir: Path
    settings_module: str
    wsgi_application: str
    config: dict[str, Any]

    @property
    def launcher_path(self) -> Path:
        return self.generated_dir / "launcher.py"

    @property
    def spec_path(self) -> Path:
        return self.generated_dir / "application.spec"

    @property
    def inno_script_path(self) -> Path:
        return self.generated_dir / "installer.iss"

    @property
    def runtime_environment_path(self) -> Path:
        filename = self.config["ENVIRONMENT"]["SNAPSHOT_FILENAME"]
        return self.generated_dir / filename

    @property
    def runtime_defaults_path(self) -> Path:
        return self.generated_dir / RUNTIME_DEFAULTS_FILENAME

    @property
    def bundle_dir(self) -> Path:
        return self.pyinstaller_dist_dir / self.executable_name

    @property
    def executable_path(self) -> Path:
        return self.bundle_dir / f"{self.executable_name}.exe"

    @property
    def installer_filename(self) -> str:
        return f"{self.executable_name}-{self.app_version}{INSTALLER_SUFFIX}"

    @property
    def installer_path(self) -> Path:
        return self.release_dir / self.installer_filename

    @property
    def uses_sqlite(self) -> bool:
        return self.database_mode == "sqlite"

    @property
    def uses_external_database(self) -> bool:
        return self.database_mode == "external"


def create_build_context(
    *,
    target_platform: str,
    config: dict[str, Any],
) -> BuildContext:
    platform_work_dir = config["WORK_DIR"] / target_platform
    release_dir = config["OUTPUT_DIR"] / target_platform
    runtime_config = config["RUNTIME"]

    return BuildContext(
        target_platform=target_platform,
        app_name=config["NAME"],
        app_version=config["VERSION"],
        publisher=config["PUBLISHER"],
        executable_name=config["EXECUTABLE_NAME"],
        database_mode=config["DATABASE"]["MODE"],
        runtime_company_directory=runtime_config["COMPANY_DIRECTORY"],
        runtime_application_directory=runtime_config["APPLICATION_DIRECTORY"],
        project_root=config["PROJECT_ROOT"],
        work_dir=platform_work_dir,
        generated_dir=platform_work_dir / "generated",
        pyinstaller_build_dir=platform_work_dir / "build",
        pyinstaller_dist_dir=platform_work_dir / "dist",
        release_dir=release_dir,
        settings_module=config["SETTINGS_MODULE"],
        wsgi_application=config["WSGI_APPLICATION"],
        config=config,
    )
