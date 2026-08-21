"""Template rendering and generation for build artifacts."""

from importlib.resources import as_file, files
from pathlib import Path

from django.core.management.base import CommandError
from jinja2 import Environment, FileSystemLoader


def render_template(
    template_name: str,
    *,
    output_path: Path,
    context: dict,
    encoding: str = "utf-8",
) -> Path:
    """Render a bundled Jinja template to ``output_path``."""

    template_resource = files("django_binary_builder").joinpath("templates")

    try:
        with as_file(template_resource) as template_directory:
            environment = Environment(
                loader=FileSystemLoader(str(template_directory)),
                autoescape=False,
                keep_trailing_newline=True,
            )

            template = environment.get_template(template_name)
            rendered = template.render(**context)
    except Exception as error:
        if isinstance(error, CommandError):
            raise

        raise CommandError(
            f"Failed to render template '{template_name}': {error}"
        ) from error

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(rendered, encoding=encoding)

    return output_path
