# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`django-binary-builder` is a reusable Django app/library (import name `django_binary_builder`) that packages
a Django project into a standalone, installable Windows desktop application. It adds a `binary` management
command that orchestrates: read settings/`.env` → validate build environment → collect static files → generate
a runtime config snapshot → generate `launcher.py` → generate a PyInstaller spec → build a PyInstaller `onedir`
bundle → generate an Inno Setup script → build `Setup.exe`.

It targets Python 3.14 and Django 6.x, Windows-only for now (`linux`/`macos` are reserved CLI values with
stub modules, not implemented). `library_spec.md` at the repo root is the full authoritative design spec
(module responsibilities, data formats, security rules, milestones) — consult it for anything not covered
here, especially before changing `.env`/secret handling, runtime initialization order, or database precedence
rules.

## Commands

Run from the repo root using `uv`:

```powershell
uv sync                        # install deps (dev group includes pytest, ruff)
uv run pytest                  # run the full test suite
uv run pytest tests/test_conf.py::test_name   # run a single test
uv run ruff check .            # lint
uv run ruff format .           # format
uv build                       # build the distributable package
```

Exercising the library against the example project (`examples/basic_project`):

```powershell
uv run python examples\basic_project\manage.py check
uv run python examples\basic_project\manage.py help binary
uv run python examples\basic_project\manage.py binary windows --check --skip-installer
uv run python examples\basic_project\manage.py binary windows --generate-only --skip-installer
```

Tests use `pytest-django` with `DJANGO_SETTINGS_MODULE=tests.test_project.settings` (configured in
`pyproject.toml`; also set via `os.environ.setdefault` in `tests/conftest.py`). The `build_context` fixture in
`tests/conftest.py` is the standard way to get a populated `BuildContext` in tests — prefer it over
constructing one by hand.

## Architecture

The pipeline is split into strictly separated modules under `src/django_binary_builder/`; a change to one
concern should not require touching unrelated ones:

- **`conf.py`** — defines defaults, deep-merges the `DJANGO_BINARY_BUILDER` Django setting, normalizes paths,
  validates types, derives a safe executable name. Never executes a build, never puts secrets into the context.
- **`context.py`** — `BuildContext`, a slots dataclass holding non-secret build metadata and derived paths
  (`launcher_path`, `spec_path`, `bundle_dir`, `executable_path`, etc.). Must never hold plaintext passwords,
  secrets, or full database URLs.
- **`enums.py`** — `TargetPlatform` (`windows`/`linux`/`macos`) and `DatabaseMode` (`sqlite`/`external`).
- **`management/commands/binary.py`** — CLI entry point only: parses args, loads config, applies CLI
  overrides, builds the `BuildContext`, validates host/target, dispatches to the platform implementation. Does
  *not* render templates or invoke PyInstaller/Inno Setup directly. Deliberately does not register
  `--version` (Django's `BaseCommand` already provides it) — use `--app-version` instead.
- **`discovery/`** — inspects the target Django project: project root, settings module, WSGI app, installed
  apps, static root, database backend/driver.
- **`environment/`** (`loader.py`, `policy.py`, `snapshot.py`, `validation.py`) — all `.env` handling: finds
  and parses `.env` files, merges with the process environment (process env wins unless
  `OVERRIDE_PROCESS_ENV=True`), applies include/exclude glob policy and secret-name detection, builds the
  redacted `runtime-environment.json` snapshot. Never copies a raw `.env` into the bundle.
- **`platforms/`** — per-OS pipeline orchestration (`windows.py` is implemented; `linux.py`/`macos.py` are
  reserved stubs). Calls into `builders/` but contains no Jinja template details itself.
- **`builders/`** — `launcher.py` (generates the launcher entry point), `pyinstaller.py` (generates the spec,
  runs PyInstaller, verifies the bundle), `inno_setup.py` (locates `ISCC.exe`, generates `.iss`, runs it,
  verifies `Setup.exe`). External processes are always invoked as argument lists, never `shell=True`.
- **`runtime/`** — code that only runs *inside* the packaged application at startup: loads the environment
  snapshot, creates persistent runtime directories, applies the database mode, runs migrations, creates the
  initial admin, manages initialization state/locks (`state.py`, `locks.py`). Keep this importable without the
  build-time dependencies (Jinja2, PyInstaller) since it ships inside the frozen app.
- **`templates/`** — Jinja2 templates for `launcher.py`, the PyInstaller `.spec`, the Inno Setup `.iss`, and
  runtime defaults JSON.

### Key invariants to preserve

- **Build / install / runtime-data separation**: build artifacts live under `.django-binary-builder/windows/`
  in the project repo; installed app files go to `{localappdata}\Programs\<AppName>`; writable runtime data
  (SQLite DB, media, logs, state) lives under `%LOCALAPPDATA%/<Company>/<App>/` and is never touched by
  install/upgrade/uninstall.
- **Secret handling**: variable names matching `*SECRET*`, `*PASSWORD*`, `*TOKEN*`, `*API_KEY*`,
  `*PRIVATE_KEY*`, `*DATABASE_URL*`, `*DB_PASSWORD*` are treated as sensitive. Including one fails the build
  unless `ENVIRONMENT.ALLOW_SECRETS=True`; logs/summaries only ever show `[REDACTED]`, never values.
- **Runtime env precedence**: process environment always wins over the bundled snapshot, so the snapshot only
  fills in *unset* names at launcher startup (before Django settings import).
- **Config precedence** overall: CLI override → process environment → later `.env` file → earlier `.env` file
  → `DJANGO_BINARY_BUILDER` setting → library defaults.
- **SQLite is never overwritten** on upgrade/reinstall; the initial admin (`admin`/`admin1234` by default) is
  created once and never reset/reprovisioned on subsequent startups.
- **External DB config precedence**: runtime process environment → `config/database.json` → project
  `DATABASES`. The external DB password is never written to the snapshot by default.
- Runtime startup order matters and is fixed: load snapshot → set `DJANGO_BINARY_RUNTIME=1` → set
  `DJANGO_SETTINGS_MODULE` → create runtime dirs → `django.setup()` → acquire init lock → test DB connection →
  migrate → create initial admin → write state → release lock → import WSGI app → pick a port → start Waitress
  (background thread) → show the UI. Any failure in this sequence must prevent Waitress from starting.
- PyInstaller is always `onedir` (no `onefile`); Waitress is the runtime WSGI server (no `runserver`, no
  autoreload, binds `127.0.0.1` only).
- **UI mode (`SERVER.MODE`)**: defaults to `"webview"` — the launcher opens a native desktop window via
  `pywebview` (`builders/launcher.py`'s `webview` runtime-defaults block, rendered into
  `templates/launcher.py.j2`'s `_run_webview()`); closing that window calls `server.close()` and exits the
  whole process. `SERVER.MODE = "browser"` opens the system default browser instead and leaves the process
  running until externally killed (the old behavior). If `pywebview` fails to import at runtime, the launcher
  falls back to browser mode with a logged warning rather than crashing. `templates/application.spec.j2` must
  keep collecting `webview`'s data/binaries/hidden imports (`collect_all("webview")`) alongside Django and
  Waitress for this to survive freezing.

## Example project

`examples/basic_project` is a working Django project used to exercise the library end-to-end (SQLite mode,
`.env.example`, `ENVIRONMENT.INCLUDE`, static root, `CONSOLE=True`). Treat it as a live integration fixture,
not sample code to copy blindly — running the `binary` management command against it (see Commands above) is
the primary way to manually verify pipeline changes.
