"""Central build metadata and bundle paths."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

INSTALLER_SUFFIX = "-Setup.exe"

WORK_DIR_NAME = ".django-binary-builder"
OUTPUT_DIR_NAME = "release"


@dataclass(slots=True)
class BuildContext:
    """Everything the builders need, resolved once per build."""

    target_platform: str
    app_name: str
    app_version: str
    publisher: str
    executable_name: str
    icon: Path | None
    project_root: Path
    work_dir: Path
    generated_dir: Path
    release_dir: Path
    settings_module: str
    wsgi_application: str | None
    python_version: str = ""
    requirements: list[str] = field(default_factory=list)
    requirements_path: Path | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def bundle_dir(self) -> Path:
        return self.work_dir / "bundle"

    @property
    def app_dir(self) -> Path:
        return self.bundle_dir / "app"

    @property
    def runtime_dir(self) -> Path:
        return self.bundle_dir / "runtime"

    @property
    def static_dir(self) -> Path:
        return self.app_dir / "staticfiles"

    @property
    def inno_script_path(self) -> Path:
        return self.generated_dir / "installer.iss"

    @property
    def executable_path(self) -> Path:
        return self.bundle_dir / f"{self.executable_name}.exe"

    @property
    def installer_filename(self) -> str:
        return f"{self.executable_name}-{self.app_version}{INSTALLER_SUFFIX}"

    @property
    def installer_path(self) -> Path:
        return self.release_dir / self.installer_filename


def create_build_context(
    *,
    target_platform: str,
    config: dict[str, Any],
) -> BuildContext:
    work_dir = config["PROJECT_ROOT"] / WORK_DIR_NAME / target_platform

    release_dir = config["PROJECT_ROOT"] / OUTPUT_DIR_NAME / target_platform

    if config.get("OUTPUT_DIR"):
        release_dir = Path(config["OUTPUT_DIR"]) / target_platform

    return BuildContext(
        target_platform=target_platform,
        app_name=config["NAME"],
        app_version=config["VERSION"],
        publisher=config["PUBLISHER"],
        executable_name=config["EXECUTABLE_NAME"],
        icon=config.get("ICON"),
        project_root=config["PROJECT_ROOT"],
        work_dir=work_dir,
        generated_dir=work_dir / "generated",
        release_dir=release_dir,
        settings_module=config["SETTINGS_MODULE"],
        wsgi_application=config.get("WSGI_APPLICATION"),
        config=config,
    )
