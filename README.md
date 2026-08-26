# django-binary-builder

Build Django projects as installable desktop applications.

`django-binary-builder` is a reusable Django build library. Install it
into an existing Django project, add it to `INSTALLED_APPS`, and use
the `binary` management command to package the project into a
standalone, installable desktop application for Windows.

The packaged application ships a **portable Python runtime** with your
project and every dependency installed by pip — no code is frozen, so
any library that works in your development virtual environment
(including native/C-extension packages) works in the packaged
application. Size is traded for compatibility on purpose.

When the user starts the app, Django is served by waitress on a
loopback port in the background and the application opens in a native
desktop window (via
[`pywebview`](https://pywebview.flowrl.com/)); closing the window
shuts the server down and exits the process. If pywebview is
unavailable the default browser is used as a fallback.

```text
Read the 5-key DJANGO_BINARY_BUILDER setting
→ Read .env (bundled as-is; the process environment wins at runtime)
→ Resolve dependencies: requirements.txt → pyproject.toml → pip freeze
→ Resolve the Python pin (.python-version)
→ Copy the current CPython installation into bundle/runtime
→ pip install every dependency into the portable runtime
→ Copy the project, collect static files, generate the launcher
→ Build a dependency-free entry executable (PyInstaller stub)
→ Package everything with Inno Setup into a Setup.exe
```

## Requirements

- Python 3.14 (any full CPython build — python.org installer, `uv`,
  etc.; the Microsoft Store Python cannot be packaged)
- Django 6.x
- Windows 10 or Windows 11 (Windows installers must be built on a
  Windows host; `linux` and `macos` targets are reserved for future
  versions)
- Inno Setup 7 (only needed when building an installer; skip it with
  `--skip-installer`)
- Internet access on the build machine the first time dependencies
  are installed into the runtime (pip uses its normal cache
  afterwards)

## Installation

```powershell
uv add django-binary-builder
```

Add the app to your Django settings:

```python
INSTALLED_APPS = [
    # Existing apps
    "django_binary_builder",
]
```

## The complete configuration

This is the entire configuration surface — five optional keys:

```python
from pathlib import Path

DJANGO_BINARY_BUILDER = {
    "NAME": "Example Project",
    "VERSION": "0.1.1",
    "PUBLISHER": "Example Company",
    "EXECUTABLE_NAME": "example-project",
    "ICON": BASE_DIR / "assets" / "icon.ico",
}
```

| Key | Default when omitted |
| --- | --- |
| `NAME` | the project folder name |
| `VERSION` | `"0.1.0"` |
| `PUBLISHER` | `NAME` |
| `EXECUTABLE_NAME` | `NAME` converted to a safe file name |
| `ICON` | no icon (any `.ico` file) |

Unknown keys are ignored with a warning so typos surface without
blocking builds.

## Build

```powershell
uv run python manage.py binary windows
```

The final output is written to:

```text
release/windows/<executable-name>-<version>-Setup.exe
```

Options:

| Option | Behaviour |
| --- | --- |
| `--check` | Run preflight checks only; create no files. |
| `--skip-installer` | Build the application bundle without running Inno Setup. |
| `--output PATH` | Override the output directory (default: `release/`). |

## How dependencies are resolved

1. If `requirements.txt` exists in the project root it is used as-is.
2. Otherwise, if `pyproject.toml` exists, its `[project]
   dependencies` are used.
3. Otherwise `requirements.txt` is **generated from the current
   environment** (the equivalent of `pip freeze`, with
   `django-binary-builder`, `pip`, `setuptools` and `wheel` excluded)
   and written into the project root.

The launcher's runtime dependencies (`waitress`, `pywebview`,
`python-dotenv`) are appended automatically when missing. The first
build machine therefore defines the application's dependency set —
run the build from the virtual environment you actually develop in.

## `.python-version`

The build generates `.python-version` in the project root containing
the current interpreter's version (for example `3.14`). If the file
already exists it is used as-is, and the build fails when the current
interpreter does not match it — activate the right virtual
environment to build reproducible bundles.

## What the bundle contains

```text
<install dir>
├── example-project.exe     ← entry stub (starts the runtime)
├── _internal/              ← PyInstaller support files for the stub
├── runtime/                ← complete portable CPython + site-packages
└── app/                    ← your project
    ├── manage.py, myproject/, ...
    ├── django_binary_builder/  (the library itself)
    ├── staticfiles/         ← collected by the build
    ├── .env                 ← bundled when present
    ├── db.sqlite3           ← bundled when present (first-run seed)
    └── launcher.py          ← generated entry point
```

The entry executable is an intentionally dependency-free PyInstaller
stub: its only job is to start `runtime\pythonw.exe app\launcher.py`
and forward the exit code. Your Django code is never frozen.

## Runtime behaviour

- **Server**: waitress serves the WSGI application on `127.0.0.1`
  (first free port from 8765) in a background thread.
- **Window**: pywebview opens a 1200×800 window titled `NAME`; the
  default browser is the fallback. Closing the window exits the app.
- **Environment**: the bundled `.env` is applied at startup with
  `python-dotenv`; variables already present in the process
  environment always win, so deployments can override anything
  (`DJANGO_SETTINGS_MODULE` included).
- **Database**: SQLite databases are relocated to a writable per-user
  data directory on first start:

  ```text
  %LOCALAPPDATA%/<Publisher>/<Name>/
  ├── data/db.sqlite3     (seeded from the bundled copy, never overwritten)
  ├── logs/application.log
  └── media/
  ```

  Override the root with the `DJANGO_BINARY_DATA_DIR` environment
  variable. External databases (PostgreSQL, MySQL, ...) keep the
  project's `DATABASES` settings — just install the driver in your
  build environment so it lands in the runtime.
- **Migrations** run automatically on every startup.
- **Initial admin**: when `django.contrib.auth` is installed and no
  superuser exists, one is created with username `admin` and password
  from `DJANGO_BINARY_ADMIN_PASSWORD` (default `admin1234`).
  **Change it immediately after the first login.**
- **Static files**: `/static/` is served from the bundled
  `staticfiles/` directory and `/media/` from the data directory —
  no web server or whitenoise configuration needed.
- `127.0.0.1` and `localhost` are appended to `ALLOWED_HOSTS`
  automatically.

## Security notes

- A bundled `.env` or SQLite database can be extracted by anyone with
  file access — never package real secrets. Provide sensitive values
  through the environment on the deployment machine instead.
- The initial administrator uses a publicly documented default
  password and is only a convenience for first-run setups.

## Troubleshooting

- **`pins Python 3.x but the current interpreter is ...`** — the
  `.python-version` file records the build Python; activate a
  matching virtual environment (or update the file) and rebuild.
- **`pip install failed inside the portable runtime`** — check
  internet access and the dependency specifiers; the install log is
  printed during the build.
- **`The Microsoft Store Python cannot be packaged`** — install
  Python from python.org or via `uv` and rebuild from its virtual
  environment.
- **`Inno Setup 7 was not found`** — install Inno Setup 7, add
  `ISCC.exe` to `PATH`, set `DJANGO_BINARY_INNO_COMPILER`, or build
  with `--skip-installer`.
- **The app does not start** — check
  `%LOCALAPPDATA%\<Publisher>\<Name>\logs\application.log` and
  `startup.log` next to it; all output is logged there because the
  packaged app has no console.
- **Port 8765 is busy** — the launcher automatically picks the next
  available port.

## Known limitations

- Windows only (`linux`/`macos` targets are reserved but not
  implemented); no cross-compilation.
- WSGI only — no ASGI, Django Channels or WebSocket support.
- No Celery worker/beat, no bundled or auto-installed database
  servers.
- No Windows Service support, no automatic updater, no code signing.
- The bundle is large (hundreds of MB) by design: the complete Python
  runtime is shipped uncompressed on disk inside the installer.

## Example

See the [`examples`](examples) directory for a complete project
demonstrating the five-key configuration, a custom icon, a bundled
SQLite database and a `requirements.txt`.
