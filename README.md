# django-binary-builder

Build Django projects as installable desktop applications.

`django-binary-builder` is a reusable Django build library. Install it
into an existing Django project, add it to `INSTALLED_APPS`, and use
the `binary` management command to package the project into a
standalone, installable desktop application for Windows.

By default the packaged application opens as a native desktop window
(via [`pywebview`](https://pywebview.flowrl.com/)) rather than a
browser tab — Django and Waitress still run in the background on
`127.0.0.1`, but the user only ever sees an app window. Closing that
window shuts the server down and exits the process. Set
`SERVER.MODE = "browser"` to open the default system browser instead.

```text
Read Django settings and .env
→ Validate the build environment
→ Collect static files
→ Generate a runtime configuration snapshot
→ Generate launcher.py
→ Generate a PyInstaller spec
→ Build an onedir bundle with PyInstaller
→ Generate an Inno Setup script
→ Build a Setup.exe with Inno Setup
```

## Requirements

- Python 3.14
- Django 6.x
- Windows 10 or Windows 11 (Windows installers must be built on a
  Windows host; `linux` and `macos` targets are reserved for future
  versions)
- PyInstaller 6.x (`onedir` mode only)
- Inno Setup 7 (only needed when building an installer)

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

Build a Windows installer:

```powershell
uv run python manage.py binary windows
```

The final output is written to:

```text
release/windows/<executable-name>-<version>-Setup.exe
```

## CLI

```text
python manage.py binary PLATFORM [OPTIONS]
```

`PLATFORM` accepts `windows`, `linux`, or `macos` (only `windows` is
implemented).

| Option | Behaviour |
| --- | --- |
| `--check` | Run preflight checks only; create no files. |
| `--generate-only` | Generate launcher, spec, runtime metadata and (optionally) `.iss` without running packaging tools. |
| `--skip-installer` | Run PyInstaller but do not require Inno Setup. |
| `--clean` | Delete existing build files before building. |
| `--name VALUE` | Override the application display name. |
| `--app-version VALUE` | Override the packaged application version. |
| `--output PATH` | Override the output directory. |
| `--console` | Show the console window when the application runs. |
| `--no-collectstatic` | Skip collecting static files. |
| `--env-file PATH` | Load an extra `.env` file after the configured files. |
| `--no-env` | Disable `.env` loading and the environment snapshot. |

## Full settings example

All keys are optional; the block below shows the available options
with their default values:

```python
from pathlib import Path

DJANGO_BINARY_BUILDER = {
    "NAME": "My Application",
    "VERSION": "1.0.0",
    "PUBLISHER": "Example Company",
    "EXECUTABLE_NAME": "my-application",
    "ICON": Path("assets/application.ico"),  # optional .ico file
    "OUTPUT_DIR": Path("release"),
    "WORK_DIR": Path(".django-binary-builder"),
    "SERVER": {
        "HOST": "127.0.0.1",  # runtime binds loopback only
        "PORT": 8765,
        "THREADS": 8,
        "MODE": "webview",  # "webview" (native window) or "browser"
        "OPEN_BROWSER": True,  # only used when MODE = "browser"
    },
    "WEBVIEW": {
        "TITLE": None,  # defaults to NAME
        "WIDTH": 1200,
        "HEIGHT": 800,
        "RESIZABLE": True,
    },
    "ENVIRONMENT": {
        "ENABLED": True,
        "FILES": [Path(".env")],
        "OVERRIDE_PROCESS_ENV": False,  # process env wins by default
        "INCLUDE": ["DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "APP_FEATURE_*"],
        "EXCLUDE": ["DJANGO_BINARY_ADMIN_PASSWORD", "DJANGO_BINARY_DB_PASSWORD"],
        "REQUIRED": [],
        "PACKAGE_MODE": "snapshot",
        "SNAPSHOT_FILENAME": "runtime-environment.json",
        "ALLOW_SECRETS": False,  # opt-in for sensitive names
        "WARN_ON_SECRET_NAMES": True,
    },
    "DATABASE": {
        "MODE": "sqlite",  # or "external"
        "RUN_MIGRATIONS": True,
        "MIGRATION_TIMEOUT": 300,
        "SQLITE": {
            "FILENAME": "db.sqlite3",  # plain filename only
            "COPY_INITIAL_DATABASE": False,
            "INITIAL_DATABASE": None,  # seed database to copy on first run
        },
        "EXTERNAL": {
            "USE_PROJECT_SETTINGS": True,
            "CONFIG_FILE": "database.json",
            "ALLOW_ENVIRONMENT_VARIABLES": True,
            "TEST_CONNECTION_ON_STARTUP": True,
        },
    },
    "INITIAL_ADMIN": {
        "ENABLED": True,
        "SQLITE_ONLY": True,
        "USERNAME": "admin",
        "PASSWORD": "admin1234",
        "EMAIL": "admin@localhost",
        "EXTRA_FIELDS": {},
        "REQUIRE_PASSWORD_CHANGE": True,
        "RESET_PASSWORD_IF_USER_EXISTS": False,  # not implemented; warns
    },
    "RUNTIME": {
        "COMPANY_DIRECTORY": "ExampleCompany",
        "APPLICATION_DIRECTORY": "MyApplication",
        "DATA_DIRECTORY": None,  # override for %LOCALAPPDATA% default
        "LOG_DIRECTORY": "logs",
        "MEDIA_DIRECTORY": "media",
        "CONFIG_DIRECTORY": "config",
    },
    "BUILD": {
        "MODE": "onedir",  # onefile is not supported
        "CONSOLE": False,
        "CLEAN": True,
        "COLLECT_STATIC": True,
        "HIDDEN_IMPORTS": [],
        "EXCLUDED_MODULES": [],
        "EXTRA_DATA": [],  # [{"source": ..., "destination": ...}]
    },
    "WINDOWS": {
        "INNO_SETUP_COMPILER": None,  # explicit ISCC.exe path
        "PRIVILEGES": "lowest",
        "ARCHITECTURE": "x64compatible",
        "CREATE_DESKTOP_SHORTCUT": True,
        "CREATE_START_MENU_SHORTCUT": True,
    },
}
```

## Windows build prerequisites

1. Build on a Windows 10 or Windows 11 host (no cross-compilation).
2. Install [Inno Setup 7](https://jrsoftware.org/isinfo.php) — the
   default install locations and `PATH` are searched automatically, or
   set `WINDOWS.INNO_SETUP_COMPILER` to the full `ISCC.exe` path. Use
   `--skip-installer` while iterating to skip this requirement.
3. Configure `STATIC_ROOT` in your Django settings when
   `BUILD.COLLECT_STATIC` is enabled.

## `.env` snapshot handling

At build time the library reads your `.env` files (configured list,
then `--env-file`, then `<project root>/.env` by default), merges them
with the process environment (process environment wins unless
`OVERRIDE_PROCESS_ENV=True`), applies `INCLUDE`/`EXCLUDE` glob
patterns (`EXCLUDE` always wins; an empty `INCLUDE` selects nothing;
use `*` to include everything), and writes the selected variables to a
`runtime-environment.json` snapshot bundled with the application.

**Security warning:** a PyInstaller bundle or Windows installer cannot
safely hide embedded secrets. Any password, API key or Django secret
packaged into a client-side application can be extracted by anyone
with file access. `ALLOW_SECRETS=True` means you explicitly accept
this risk — it does **not** mean the values are encrypted or
protected. Variable names matching `*SECRET*`, `*PASSWORD*`,
`*TOKEN*`, `*API_KEY*`, `*PRIVATE_KEY*`, `*DATABASE_URL*` or
`*DB_PASSWORD*` are treated as sensitive: the build fails unless
`ALLOW_SECRETS=True`, and the build log only ever shows variable names
with `[REDACTED]` values.

At runtime the process environment always wins over the snapshot, so
IT administrators can override any bundled value (including the
`DJANGO_BINARY_DB_*` and `DJANGO_BINARY_ADMIN_*` variables below).

## External database

`DATABASE.MODE = "external"` keeps your project's `DATABASES`
settings (`USE_PROJECT_SETTINGS=True`) or reads a
`config/database.json` file in the runtime data directory:

```json
{
  "engine": "django.db.backends.postgresql",
  "name": "mydb",
  "user": "myuser",
  "password": "changeme",
  "host": "localhost",
  "port": 5432
}
```

Precedence: runtime process environment → `database.json` → project
`DATABASES`. The supported environment variables are
`DJANGO_BINARY_DB_ENGINE`, `DJANGO_BINARY_DB_NAME`,
`DJANGO_BINARY_DB_USER`, `DJANGO_BINARY_DB_PASSWORD`,
`DJANGO_BINARY_DB_HOST` and `DJANGO_BINARY_DB_PORT`.

Install the driver yourself — the builder does not install database
servers or drivers:

```powershell
uv add "psycopg[binary]"     # PostgreSQL
uv add mysqlclient           # MySQL / MariaDB
uv add oracledb              # Oracle
```

Preflight verifies the driver for your engine and adds the matching
hidden imports to the PyInstaller build. The database password is
never written to the snapshot by default — provide it through the
environment or `database.json` on the deployment machine instead.

## SQLite runtime location

With `DATABASE.MODE = "sqlite"` the packaged application stores its
database in a persistent, per-user runtime directory:

```text
%LOCALAPPDATA%/<CompanyDirectory>/<ApplicationDirectory>/
├── data/db.sqlite3
├── config/database.json
├── media/
├── logs/application.log
└── state/initialization.json
```

Override the root with the `DJANGO_BINARY_DATA_DIR` environment
variable or `RUNTIME.DATA_DIRECTORY`. The installer never deletes
this directory, and an existing user database is **never overwritten**
during upgrades or reinstalls.

## Initial administrator (security warning)

On first startup in SQLite mode the packaged application creates an
initial administrator using **publicly documented default
credentials**: username `admin`, password `admin1234`. Build and
runtime logs display warnings about this credential without ever
printing the password. **Change the password immediately after the
first login.**

Override the credentials at runtime with
`DJANGO_BINARY_ADMIN_USERNAME`, `DJANGO_BINARY_ADMIN_PASSWORD` and
`DJANGO_BINARY_ADMIN_EMAIL` (process environment wins). On later
startups the account is left completely untouched — the password is
never reset, the email is never changed, and existing users are never
promoted. `INITIAL_ADMIN.RESET_PASSWORD_IF_USER_EXISTS=True` is not
implemented and only produces a warning.

`REQUIRE_PASSWORD_CHANGE=True` records a reminder in the state file
and keeps logging a warning; it does **not** technically force a
password change unless you add your own middleware or login flow.

## Build, install and runtime data separation

- **Build time** happens on your development machine: static files
  are collected, artifacts are generated under
  `.django-binary-builder/windows/`, and packaging tools run there.
- **Install time** copies the onedir bundle to
  `{localappdata}\Programs\<ApplicationName>` with per-user privileges.
- **Runtime data** (SQLite database, media, logs, state) lives in
  `%LOCALAPPDATA%` and survives upgrades and uninstalls.

## Troubleshooting

- **`--version` conflict / CLI errors** — the command deliberately
  does not register `--version`; use `--app-version`.
- **`STATIC_ROOT must be configured`** — set `STATIC_ROOT` or pass
  `--no-collectstatic`.
- **`Inno Setup 7 was not found`** — install Inno Setup 7, add
  `ISCC.exe` to `PATH`, set `WINDOWS.INNO_SETUP_COMPILER`, or build
  with `--skip-installer`.
- **`Sensitive environment variables were selected ...`** — remove the
  variable from `ENVIRONMENT.INCLUDE`, or set
  `ENVIRONMENT.ALLOW_SECRETS = True` to accept the risk.
- **The packaged app cannot connect to an external database** — check
  `DJANGO_BINARY_DB_*` environment variables and
  `config/database.json`; the connection error messages are redacted.
- **Port 8765 is busy** — the launcher automatically picks the next
  available port and opens the browser at the actual URL.
- **Migrations are slow on startup** — migrations run on every
  startup; `DATABASE.MIGRATION_TIMEOUT` only controls a warning
  threshold, it does not abort.

## Known limitations

- Windows only (`linux`/`macos` targets are reserved but not
  implemented); no cross-compilation.
- PyInstaller `onedir` only; no `onefile`.
- WSGI only — no ASGI, Django Channels or WebSocket support.
- No Celery worker/beat, no bundled or auto-installed database
  servers.
- No Windows Service support, no automatic updater, no code signing.
- Bundled secrets are not encrypted and can be extracted.
- `INITIAL_ADMIN.RESET_PASSWORD_IF_USER_EXISTS` is not implemented.
- Native Python packages may require manual `BUILD.HIDDEN_IMPORTS`
  entries.

## Example

See [`examples/basic_project`](examples/basic_project) for a complete
project demonstrating SQLite mode, `.env.example`,
`ENVIRONMENT.INCLUDE`, runtime settings integration, the Django admin
URL, `STATIC_ROOT` and `CONSOLE=True`.
