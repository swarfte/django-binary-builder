import subprocess
import sys
from importlib.resources import as_file, files
from pathlib import Path

from django.apps import apps
from django.core.management.base import CommandError
from jinja2 import Environment, FileSystemLoader

from django_binary_builder.context import BuildContext


def generate_pyinstaller_spec(
    context: BuildContext,
) -> None:
    """
    Generate a PyInstaller spec file from application.spec.j2.
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
            "application.spec.j2"
        )

        installed_apps = get_installed_app_packages()
        extra_data = get_extra_data(context)

        rendered_content = template.render(
            launcher_path=str(
                context.launcher_path
            ),
            project_root=str(
                context.project_root
            ),
            executable_name=context.executable_name,
            installed_apps=installed_apps,
            hidden_imports=context.config["BUILD"][
                "HIDDEN_IMPORTS"
            ],
            excluded_modules=context.config["BUILD"][
                "EXCLUDED_MODULES"
            ],
            extra_data=extra_data,
            console=context.config["BUILD"]["CONSOLE"],
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

    context.spec_path.write_text(
        rendered_content,
        encoding="utf-8",
    )


def run_pyinstaller(
    context: BuildContext,
) -> None:
    """
    Run PyInstaller with the generated spec file.
    """

    if not context.spec_path.is_file():
        raise CommandError(
            "PyInstaller spec file does not exist: "
            f"{context.spec_path}"
        )

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        str(context.pyinstaller_build_dir),
        "--distpath",
        str(context.pyinstaller_dist_dir),
        str(context.spec_path),
    ]

    result = subprocess.run(
        command,
        cwd=context.project_root,
        check=False,
    )

    if result.returncode != 0:
        raise CommandError(
            "PyInstaller build failed with exit code "
            f"{result.returncode}."
        )

    if not context.bundle_dir.is_dir():
        raise CommandError(
            "PyInstaller completed, but the expected "
            "application directory was not found: "
            f"{context.bundle_dir}"
        )

    if not context.executable_path.is_file():
        raise CommandError(
            "PyInstaller completed, but the expected "
            "executable was not found: "
            f"{context.executable_path}"
        )


def get_installed_app_packages() -> list:
    """
    Return the import names of all installed Django apps.

    Examples:
        django.contrib.auth
        django.contrib.contenttypes
        my_application
    """

    package_names: list[str] = []

    for app_config in apps.get_app_configs():
        package_names.append(
            app_config.name
        )

    return sorted(set(package_names))


def get_extra_data(
    context: BuildContext,
) -> list[tuple[str, str]]:
    """
    Resolve user-defined extra data paths.

    Expected configuration format:

    DJANGO_BINARY_BUILDER = {
        "BUILD": {
            "EXTRA_DATA": [
                {
                    "source": "templates",
                    "destination": "templates",
                },
            ],
        },
    }
    """

    extra_data: list[tuple[str, str]] = []

    configured_items = context.config["BUILD"][
        "EXTRA_DATA"
    ]

    for item in configured_items:
        if not isinstance(item, dict):
            raise CommandError(
                "Each BUILD.EXTRA_DATA entry must "
                "be a dictionary."
            )

        if "source" not in item:
            raise CommandError(
                "Each BUILD.EXTRA_DATA entry must "
                "contain a 'source' value."
            )

        source = Path(item["source"])

        if not source.is_absolute():
            source = (
                context.project_root
                / source
            )

        source = source.resolve()

        if not source.exists():
            raise CommandError(
                "Extra data source does not exist: "
                f"{source}"
            )

        destination = item.get(
            "destination",
            source.name,
        )

        extra_data.append(
            (
                str(source),
                str(destination),
            )
        )

    return extra_data