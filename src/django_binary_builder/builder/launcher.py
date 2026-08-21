from importlib.resources import as_file, files

from django.core.management.base import CommandError
from jinja2 import Environment, FileSystemLoader

from django_binary_builder.context import BuildContext


def generate_launcher(
    context: BuildContext,
) -> None:
    """
    Generate the Python entry point used by PyInstaller.
    """

    if not context.wsgi_application:
        raise CommandError(
            "WSGI application is not configured."
        )

    try:
        wsgi_module, wsgi_object = (
            context.wsgi_application.rsplit(
                ".",
                1,
            )
        )
    except ValueError as error:
        raise CommandError(
            "Invalid WSGI_APPLICATION value: "
            f"{context.wsgi_application}"
        ) from error

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
            "launcher.py.j2"
        )

        server_config = context.config[
            "SERVER"
        ]

        rendered_content = template.render(
            settings_module=context.settings_module,
            wsgi_module=wsgi_module,
            wsgi_object=wsgi_object,
            host=server_config["HOST"],
            port=server_config["PORT"],
            threads=server_config["THREADS"],
            open_browser=server_config[
                "OPEN_BROWSER"
            ],
        )

    context.generated_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    context.launcher_path.write_text(
        rendered_content,
        encoding="utf-8",
    )