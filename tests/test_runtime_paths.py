from django_binary_builder.runtime.paths import (
    create_runtime_directories,
    resolve_runtime_root,
)


def make_defaults(**runtime_overrides):
    runtime = {
        "company_directory": "ExampleCompany",
        "application_directory": "MyApplication",
        "log_directory": "logs",
        "media_directory": "media",
        "config_directory": "config",
    }
    runtime.update(runtime_overrides)

    return {"runtime": runtime}


def test_environment_override_wins(tmp_path, monkeypatch):
    override = tmp_path / "override-data"
    override.mkdir()

    monkeypatch.setenv("DJANGO_BINARY_DATA_DIR", str(override))

    root = resolve_runtime_root(make_defaults(data_directory="other"))

    assert root == override

    monkeypatch.delenv("DJANGO_BINARY_DATA_DIR")


def test_configured_data_directory_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("DJANGO_BINARY_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    configured = tmp_path / "configured-data"

    root = resolve_runtime_root(
        make_defaults(data_directory=str(configured)),
    )

    assert root == configured


def test_localappdata_default(tmp_path, monkeypatch):
    monkeypatch.delenv("DJANGO_BINARY_DATA_DIR", raising=False)

    local_app_data = tmp_path / "appdata-local"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    root = resolve_runtime_root(make_defaults())

    assert root == (local_app_data / "ExampleCompany" / "MyApplication")


def test_create_runtime_directories(tmp_path, monkeypatch):
    monkeypatch.delenv("DJANGO_BINARY_DATA_DIR", raising=False)

    local_app_data = tmp_path / "appdata-local"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    root = resolve_runtime_root(make_defaults())

    directories = create_runtime_directories(root, make_defaults())

    assert directories["root"] == root
    assert directories["data"] == root / "data"
    assert directories["state"] == root / "state"
    assert directories["config"] == root / "config"
    assert directories["media"] == root / "media"
    assert directories["logs"] == root / "logs"

    for name, directory in directories.items():
        assert directory.is_dir(), name


def test_directory_names_are_configurable(tmp_path, monkeypatch):
    monkeypatch.delenv("DJANGO_BINARY_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    defaults = make_defaults(
        log_directory="log-files",
        media_directory="uploads",
        config_directory="settings",
    )

    root = resolve_runtime_root(defaults)
    directories = create_runtime_directories(root, defaults)

    assert directories["logs"] == root / "log-files"
    assert directories["media"] == root / "uploads"
    assert directories["config"] == root / "settings"
