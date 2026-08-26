"""Tests for the generated launcher and entry stub templates."""

from pathlib import Path

from django_binary_builder.builders import render_template


def render_launcher(tmp_path, **overrides):
    context = {
        "app_name": "Example Project",
        "publisher": "Example Company",
        "settings_module": "myproject.settings",
        "wsgi_application": "myproject.wsgi.application",
    }

    context.update(overrides)

    return render_template(
        "launcher.py.j2",
        output_path=tmp_path / "launcher.py",
        context=context,
    )


def test_launcher_renders_valid_python(tmp_path):
    launcher_path = render_launcher(tmp_path)

    source = launcher_path.read_text(encoding="utf-8")

    assert "{{" not in source
    assert "{%" not in source

    compile(source, str(launcher_path), "exec")


def test_launcher_embeds_the_application_metadata(tmp_path):
    launcher_path = render_launcher(tmp_path)

    source = launcher_path.read_text(encoding="utf-8")

    assert '"Example Project"' in source
    assert '"myproject.settings"' in source
    assert '"myproject.wsgi.application"' in source


def test_launcher_escapes_quotes_in_names(tmp_path):
    launcher_path = render_launcher(tmp_path, app_name='Evil "Name"')

    source = launcher_path.read_text(encoding="utf-8")

    compile(source, str(launcher_path), "exec")


def test_stub_renders_valid_python(tmp_path):
    stub_path = render_template(
        "stub.py.j2",
        output_path=tmp_path / "stub.py",
        context={},
    )

    source = stub_path.read_text(encoding="utf-8")

    assert "{{" not in source

    compile(source, str(stub_path), "exec")


def load_launcher_module(tmp_path):
    launcher_path = render_launcher(tmp_path)

    namespace = {"__name__": "generated_launcher"}

    exec(  # noqa: S102 - trusted generated code
        compile(
            launcher_path.read_text(encoding="utf-8"),
            str(launcher_path),
            "exec",
        ),
        namespace,
    )

    return namespace


def test_launcher_normalizes_url_prefixes(tmp_path):
    launcher = load_launcher_module(tmp_path)

    assert launcher["url_path_prefix"]("static/") == "/static/"
    assert launcher["url_path_prefix"]("/static/") == "/static/"
    assert launcher["url_path_prefix"]("https://cdn.example.com/assets") == "/assets/"


def test_launcher_rejects_root_file_mounts(tmp_path):
    launcher = load_launcher_module(tmp_path)

    mounts = []

    launcher["_append_mount"](mounts, "/", Path("C:/somewhere"))
    launcher["_append_mount"](mounts, "/media/", Path("C:/media"))

    # Django 6.1 defaults MEDIA_URL to "/", which must never become a
    # catch-all file mount.
    assert mounts == [("/media/", Path("C:/media"))]
