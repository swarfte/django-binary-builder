import shutil
import subprocess
import uuid
from importlib.resources import as_file, files
from pathlib import Path

from django.core.management.base import CommandError
from jinja2 import Environment, FileSystemLoader

from django_binary_builder.context import BuildContext

DEFAULT_INNO_PATHS = [
    Path(
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    ),
    Path(
        r"C:\Program Files\Inno Setup 6\ISCC.exe"
    ),
]


def find_inno_setup(
    context: BuildContext,
) -> Path | None:
    """
    Find the Inno Setup command-line compiler.
    """

    configured_path = context.config["WINDOWS"].get(
        "INNO_SETUP_COMPILER"
    )

    if configured_path:
        candidate = Path(
            configured_path
        ).expanduser()

        if candidate.is_file():
            return candidate.resolve()

        return None

    path_from_environment = shutil.which(
        "ISCC.exe"
    )

    if path_from_environment:
        return Path(
            path_from_environment
        ).resolve()

    for candidate in DEFAULT_INNO_PATHS:
        if candidate.is_file():
            return candidate.resolve()

    return None


def generate_inno_script(
    context: BuildContext,
) -> None:
    """
    Generate installer.iss from installer.iss.j2.
    """

    template_resource = files(
        "django_binary_builder"
    ).joinpath("templates")

    with as_file(template_resource) as template_directory:
        environment = Environment(
            loader=FileSystemLoader(
                str(template_directory)
            ),
            autoescape=False,
            keep_trailing_newline=True,
        )

        template = environment.get_template(
            "installer.iss.j2"
        )

        publisher = (
            context.publisher
            or "Unknown Publisher"
        )

        installer_filename = (
            f"{context.executable_name}-"
            f"{context.app_version}-Setup"
        )

        app_id = generate_app_id(
            publisher=publisher,
            app_name=context.app_name,
        )

        windows_config = context.config[
            "WINDOWS"
        ]

        rendered_content = template.render(
            app_name=escape_inno_value(
                context.app_name
            ),
            app_version=escape_inno_value(
                context.app_version
            ),
            publisher=escape_inno_value(
                publisher
            ),
            executable_name=escape_inno_value(
                context.executable_name
            ),
            app_id=app_id,
            bundle_dir=str(
                context.bundle_dir
            ),
            release_dir=str(
                context.release_dir
            ),
            installer_filename=installer_filename,
            privileges=windows_config[
                "PRIVILEGES"
            ],
            architecture=windows_config[
                "ARCHITECTURE"
            ],
            create_desktop_shortcut=windows_config[
                "CREATE_DESKTOP_SHORTCUT"
            ],
            create_start_menu_shortcut=windows_config[
                "CREATE_START_MENU_SHORTCUT"
            ],
            icon=(
                str(context.config["ICON"])
                if context.config["ICON"]
                else None
            ),
        )

    context.generated_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    context.inno_script_path.write_text(
        rendered_content,
        encoding="utf-8-sig",
    )


def run_inno_setup(
    context: BuildContext,
) -> Path:
    """
    Compile installer.iss into a Setup.exe file.
    """

    compiler_path = find_inno_setup(
        context
    )

    if compiler_path is None:
        raise CommandError(
            "Inno Setup compiler was not found. "
            "Install Inno Setup 6 or configure "
            "WINDOWS.INNO_SETUP_COMPILER."
        )

    if not context.inno_script_path.is_file():
        raise CommandError(
            "Inno Setup script does not exist: "
            f"{context.inno_script_path}"
        )

    if not context.bundle_dir.is_dir():
        raise CommandError(
            "Application bundle does not exist: "
            f"{context.bundle_dir}"
        )

    context.release_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = subprocess.run(
        [
            str(compiler_path),
            str(context.inno_script_path),
        ],
        cwd=context.project_root,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            "Inno Setup compilation failed with "
            f"exit code {result.returncode}."
        )

    installer_path = (
        context.release_dir
        / (
            f"{context.executable_name}-"
            f"{context.app_version}-Setup.exe"
        )
    )

    if not installer_path.is_file():
        raise CommandError(
            "Inno Setup completed, but the expected "
            "installer was not found: "
            f"{installer_path}"
        )

    return installer_path


def generate_app_id(
    *,
    publisher: str,
    app_name: str,
) -> str:
    """
    Generate a stable Inno Setup AppId.

    The same publisher and application name will always
    produce the same AppId.
    """

    namespace = uuid.UUID(
        "f487346d-7877-4d7a-86a4-b143ddf81462"
    )

    generated_uuid = uuid.uuid5(
        namespace,
        f"{publisher}:{app_name}",
    )

    return (
        "{"
        + str(generated_uuid).upper()
        + "}"
    )


def escape_inno_value(
    value: str,
) -> str:
    """
    Escape double quotes for Inno Setup preprocessor strings.
    """

    return str(value).replace(
        '"',
        '""',
    )