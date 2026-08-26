# django-binary-builder

Build Django projects as installable desktop applications for
Windows.

`django-binary-builder` turns any Django project into a standalone
`Setup.exe` in one command. The packaged application ships a
**portable Python runtime** with your project and every dependency
installed by pip — no code is frozen, so **any library that works in
your development virtual environment (including native/C-extension
packages) works in the packaged application**. Size is traded for
compatibility on purpose.

When the user starts the installed app, Django is served by waitress
on a loopback port in the background and the application opens in a
native desktop window (via
[pywebview](https://pywebview.flowrl.com/)); closing the window shuts
the server down and exits the process. If pywebview is unavailable,
the default browser is used as a fallback.

## Quick start

### 1. Check the prerequisites

- **Python 3.10+** — any full CPython build (the python.org
  installer, `uv`, ...). The Microsoft Store Python cannot be
  packaged.
- **Django 5.0 or newer** project with `WSGI_APPLICATION`
  configured (the `startproject` default).
- **Windows 10 or 11** — installers must be built on a Windows host.
- **[Inno Setup 7](https://jrsoftware.org/isinfo.php)** — only
  needed for the final `Setup.exe`; skip it with `--skip-installer`
  while iterating.
- **Internet access** on the build machine the first time
  dependencies are installed into the runtime (pip uses its normal
  cache afterwards).

> Always build from the virtual environment you develop in: it
> defines both the Python runtime that gets copied and the fallback
> dependency list.

### 2. Install and register the app

Use whichever workflow you already use for the project — plain `pip`
or `uv`. Both install the library into the project's virtual
environment.

**With pip** (run inside your project's virtual environment):

```powershell
pip install django-binary-builder
```

**With uv:**

```powershell
uv add django-binary-builder
```

Then register the app:

```python
# settings.py
INSTALLED_APPS = [
    # ... your apps
    "django_binary_builder",
]
```

### 3. (Optional) add the five-key setting

Every key is optional — with no setting at all, the project folder
name becomes the application name:

```python
# settings.py
from pathlib import Path

DJANGO_BINARY_BUILDER = {
    "NAME": "Example Project",
    "VERSION": "0.1.1",
    "PUBLISHER": "Example Company",
    "EXECUTABLE_NAME": "example-project",
    "ICON": BASE_DIR / "assets" / "icon.ico",
}
```

### 4. Build

Run the build from the same (activated) virtual environment you
develop in.

**With pip** (virtual environment activated):

```powershell
python manage.py binary windows
```

**With uv:**

```powershell
uv run python manage.py binary windows
```

The installer is written to:

```text
release/windows/<executable-name>-<version>-Setup.exe
```

Users install it per-user (no admin rights needed), get a desktop
and start-menu shortcut, and your app runs completely offline.

## CLI

```text
python manage.py binary PLATFORM [OPTIONS]
```

`PLATFORM` accepts `windows` (implemented), or `linux` / `macos`
(reserved, not implemented yet). uv users prefix the command with
`uv run` (for example `uv run python manage.py binary windows`) so
it executes inside the project environment.

| Option               | Behaviour                                                           |
| -------------------- | ------------------------------------------------------------------- |
| `--check`          | Run preflight checks only; create no files.                         |
| `--skip-installer` | Build the runnable application bundle without requiring Inno Setup. |
| `--output PATH`    | Override the output directory (default:`release/`).               |

## The complete configuration

`DJANGO_BINARY_BUILDER` is the entire configuration surface — five
optional keys:

| Key                 | Meaning                                                 | Default when omitted                    |
| ------------------- | ------------------------------------------------------- | --------------------------------------- |
| `NAME`            | Display name (window title, installer name, start menu) | the project folder name                 |
| `VERSION`         | Application version                                     | `"0.1.0"`                             |
| `PUBLISHER`       | Publisher name (installer metadata, data directory)     | `NAME`                                |
| `EXECUTABLE_NAME` | Safe name for the`.exe` file                          | `NAME`, converted to a safe file name |
| `ICON`            | Application icon, must be an`.ico` file               | no custom icon                          |

Unknown keys are ignored with a warning, so typos surface without
blocking builds.

## How the build works

```text
Read the 5-key DJANGO_BINARY_BUILDER setting
→ Bundle .env as-is (the process environment wins at runtime)
→ Resolve dependencies: requirements.txt → pyproject.toml → pip freeze
→ Resolve the Python pin (.python-version)
→ Copy the current CPython installation into bundle/runtime
→ pip install every dependency into the portable runtime
→ Copy the project + the library, collect static files, generate the launcher
→ Build a dependency-free entry executable (PyInstaller stub)
→ Package everything with Inno Setup into a Setup.exe
```

The entry executable is an intentionally dependency-free PyInstaller
stub: its only job is to start `runtime\pythonw.exe app\launcher.py`
and forward the exit code. Your Django code is never frozen — that
is what makes any pip-installable library work out of the box.

### Dependency resolution

1. If `requirements.txt` exists in the project root, it is used
   as-is.
2. Otherwise, if `pyproject.toml` exists, its `[project] dependencies` are used.
3. Otherwise `requirements.txt` is **generated from the current
   environment** (the equivalent of `pip freeze`, with
   `django-binary-builder`, `pip`, `setuptools` and `wheel`
   excluded) and written into the project root.

The launcher's runtime dependencies (`waitress`, `pywebview`,
`python-dotenv`) are appended automatically when missing.

### `.python-version`

The build generates `.python-version` in the project root
containing the current interpreter's version (for example `3.14`).
If the file already exists it is used as-is, and the build fails
when the current interpreter does not match it — activate the right
virtual environment to build reproducible bundles.

### Bundle layout

```text
<install dir>                        %LOCALAPPDATA%\Programs\Example Project
├── example-project.exe              entry stub (starts the runtime)
├── _internal/                       PyInstaller support files for the stub
├── runtime/                         complete portable CPython + site-packages
└── app/                             your project
    ├── manage.py, myproject/, ...
    ├── django_binary_builder/       the library itself (bundled import)
    ├── staticfiles/                 collected by the build
    ├── .env                         bundled when present
    ├── db.sqlite3                   bundled when present (first-run seed)
    └── launcher.py                  generated entry point
```

## Runtime behaviour

- **Server**: waitress serves the WSGI application on `127.0.0.1`
  (first free port from 8765) in a background thread.
- **Window**: a 1200×800 pywebview window titled `NAME`; the default
  browser is the fallback. Closing the window exits the app.
- **Environment**: the bundled `.env` is applied at startup with
  `python-dotenv`; variables already present in the process
  environment always win, so deployments can override anything —
  including `DJANGO_SETTINGS_MODULE`.
- **Database**:
  - SQLite databases are relocated on first start to a writable
    per-user data directory, seeded from the bundled copy and never
    overwritten on upgrades:

    ```text
    %LOCALAPPDATA%/<Publisher>/<Name>/     (names sanitized: spaces → dashes)
    ├── data/db.sqlite3
    ├── logs/application.log
    ├── logs/startup.log
    └── media/
    ```

    Override the root with the `DJANGO_BINARY_DATA_DIR` environment
    variable. Delete `db.sqlite3` from the project before building
    to ship an empty database.
  - External databases (PostgreSQL, MySQL, ...) keep the project's
    `DATABASES` settings — install the driver in your build
    environment (for example `pip install "psycopg[binary]"` or
    `uv add "psycopg[binary]"`) so it lands in the packaged runtime.
- **Migrations** run automatically on every startup.
- **Initial admin**: when `django.contrib.auth` is installed and no
  superuser exists, one is created with username `admin` and the
  password from `DJANGO_BINARY_ADMIN_PASSWORD` (default
  `admin1234`; `DJANGO_BINARY_ADMIN_USERNAME` overrides the
  username). **Change it immediately after the first login.**
- **Static files**: `/static/` is served from the bundled
  `staticfiles/` directory — no web server or whitenoise
  configuration needed.
- **Media files**: served at the `MEDIA_URL` prefix when it is a
  real sub-path (for example `/media/`). Django 6.1 defaults
  `MEDIA_URL` to `/`, which is deliberately not mounted because it
  would shadow every route — set `MEDIA_URL = "/media/"` to enable
  media serving.
- `127.0.0.1` and `localhost` are appended to `ALLOWED_HOSTS`
  automatically.

## Security notes

- A bundled `.env` or SQLite database can be extracted by anyone
  with file access — never package real secrets. Provide sensitive
  values through the environment on the deployment machine instead.
- The initial administrator uses a publicly documented default
  password; it is only a convenience for first-run setups.

## Troubleshooting

- **`pins Python 3.x but the current interpreter is ...`** — the
  `.python-version` file records the build Python; activate a
  matching virtual environment (or update the file) and rebuild.
- **`pip install failed inside the portable runtime`** — check
  internet access and the dependency specifiers; pip's output is
  printed during the build.
- **`The Microsoft Store Python cannot be packaged`** — install
  Python from python.org or via `uv` and rebuild from its virtual
  environment.
- **`Inno Setup 7 was not found`** — install Inno Setup 7, add
  `ISCC.exe` to `PATH`, set the `DJANGO_BINARY_INNO_COMPILER`
  environment variable, or build with `--skip-installer`.
- **The installed app does not start** — check
  `%LOCALAPPDATA%\<Publisher>\<Name>\logs\application.log` and
  `startup.log`; all output goes there because the packaged app has
  no console.
- **Port 8765 is busy** — the launcher automatically picks the next
  available port.

## Known limitations

- Windows only (`linux`/`macos` targets are reserved but not
  implemented); no cross-compilation.
- WSGI only — no ASGI, Django Channels or WebSocket support.
- No Celery worker/beat, no bundled or auto-installed database
  servers.
- No Windows Service support, no automatic updater, no code signing.
- The bundle is large (hundreds of MB) by design: the complete
  Python runtime is shipped inside the installer.

## Example

See the [`examples`](examples) directory for a complete project
demonstrating the five-key configuration, a custom icon, a bundled
SQLite database and a `requirements.txt`.
