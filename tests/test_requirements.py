"""Tests for dependency resolution."""

from types import SimpleNamespace

from django_binary_builder.requirements import (
    FREEZE_EXCLUDED_PACKAGES,
    LAUNCHER_REQUIREMENTS,
    freeze_current_environment,
    requirement_name,
    resolve_requirements,
)


def _write(path, content):
    path.write_text(content, encoding="utf-8")


def test_existing_requirements_file_is_used(tmp_path):
    _write(
        tmp_path / "requirements.txt",
        "# comment\nDjango>=6.0\n\nwhitenoise==6.9\n",
    )

    result = resolve_requirements(tmp_path)

    assert result.source == "requirements.txt"
    assert "Django>=6.0" in result.lines
    assert "whitenoise==6.9" in result.lines
    assert "# comment" not in result.lines
    assert result.generated_file is None


def test_pyproject_dependencies_are_used_when_requirements_missing(tmp_path):
    _write(
        tmp_path / "pyproject.toml",
        '[project]\nname = "demo"\ndependencies = ["Django>=6.0", "pillow"]\n',
    )

    result = resolve_requirements(tmp_path)

    assert "pyproject.toml" in result.source
    assert "Django>=6.0" in result.lines
    assert "pillow" in result.lines


def test_pyproject_without_dependencies_falls_back_to_freeze(tmp_path, monkeypatch):
    _write(tmp_path / "pyproject.toml", '[project]\nname = "demo"\n')

    monkeypatch.setattr(
        "django_binary_builder.requirements.freeze_current_environment",
        lambda: ["Django==6.1"],
    )

    result = resolve_requirements(tmp_path)

    assert result.source.startswith("generated")
    assert "Django==6.1" in result.lines
    assert (tmp_path / "requirements.txt").is_file()


def test_freeze_generates_requirements_file_in_project_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "django_binary_builder.requirements.freeze_current_environment",
        lambda: ["Django==6.1"],
    )

    result = resolve_requirements(tmp_path)

    assert result.generated_file == tmp_path / "requirements.txt"
    assert result.generated_file.read_text(encoding="utf-8") == "Django==6.1\n"


def test_dry_run_does_not_write_requirements_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "django_binary_builder.requirements.freeze_current_environment",
        lambda: ["Django==6.1"],
    )

    resolve_requirements(tmp_path, dry_run=True)

    assert not (tmp_path / "requirements.txt").exists()


def test_launcher_requirements_are_appended_when_missing(tmp_path):
    _write(tmp_path / "requirements.txt", "Django>=6.0\n")

    result = resolve_requirements(tmp_path)

    for requirement in LAUNCHER_REQUIREMENTS:
        assert requirement in result.lines


def test_launcher_requirements_are_not_duplicated(tmp_path):
    _write(
        tmp_path / "requirements.txt",
        "Django>=6.0\nwaitress>=3.0.2\npywebview>=5.1\npython-dotenv>=1.1\n",
    )

    result = resolve_requirements(tmp_path)

    assert len(result.lines) == 4


def test_freeze_current_environment_filters_build_tooling(monkeypatch):
    def fake_distributions():
        return [
            SimpleNamespace(
                metadata={"Name": "Django"},
                version="6.1",
            ),
            SimpleNamespace(
                metadata={"Name": "django-binary-builder"},
                version="0.2.0",
            ),
            SimpleNamespace(
                metadata={"Name": "pip"},
                version="25.0",
            ),
            SimpleNamespace(
                metadata={"Name": "setuptools"},
                version="75.0",
            ),
            SimpleNamespace(
                metadata={"Name": None},
                version="1.0",
            ),
        ]

    monkeypatch.setattr(
        "django_binary_builder.requirements.distributions",
        fake_distributions,
    )

    lines = freeze_current_environment()

    assert lines == ["Django==6.1"]
    assert FREEZE_EXCLUDED_PACKAGES


def test_requirement_name_normalizes_variants():
    assert requirement_name("Django>=6.0,<7.0") == "django"
    assert requirement_name("python_dotenv==1.1") == "python-dotenv"
    assert requirement_name("pywebview [cef] >=5.1") == "pywebview"
    assert requirement_name("!!invalid") == ""
