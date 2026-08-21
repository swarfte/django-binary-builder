from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class BuildContext:
    target_platform: str
    app_name: str
    app_version: str
    publisher: str | None
    executable_name: str
    project_root: Path
    work_dir: Path
    generated_dir: Path
    pyinstaller_build_dir: Path
    pyinstaller_dist_dir: Path
    release_dir: Path
    settings_module: str
    wsgi_application: str
    config: dict

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
    def bundle_dir(self) -> Path:
        return self.pyinstaller_dist_dir / self.executable_name

    @property
    def executable_path(self) -> Path:
        return self.bundle_dir / f"{self.executable_name}.exe"


def create_build_context(
    *,
    target_platform: str,
    config: dict,
) -> BuildContext:
    platform_work_dir = (
        config["WORK_DIR"]
        / target_platform
    )

    release_dir = (
        config["OUTPUT_DIR"]
        / target_platform
    )

    return BuildContext(
        target_platform=target_platform,
        app_name=config["NAME"],
        app_version=config["VERSION"],
        publisher=config["PUBLISHER"],
        executable_name=config["EXECUTABLE_NAME"],
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