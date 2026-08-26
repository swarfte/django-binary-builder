# Rebuild django-binary-builder around a portable Python runtime bundle

## Problem with the current design

PyInstaller freezes the Django project and its dependencies, so any additional library (especially native/C-extension or dynamic-import packages) breaks the build with hidden-import errors. The config surface is also huge (~60 keys across 9 sections).

## New architecture (what you asked for)

Replace "PyInstaller freezes everything" with "**ship a real, portable Python runtime + pip-installed dependencies**":

```
read 5-key config → read .env → resolve requirements.txt
→ resolve/generate .python-version → build portable runtime (copy current
Python + pip install requirements) → copy project + generate self-contained
launcher → tiny entry .exe stub → Inno Setup installer → Setup.exe
```

At app start: `AppName.exe` → `runtime\pythonw.exe app\launcher.py` → waitress serves Django on 127.0.0.1 in a background thread → pywebview window opens → close window = app exits. Because Django and ALL project libraries run from a genuine pip-installed environment, **any library that works in your dev venv works in the bundle** — size is traded for compatibility, per your priority.

## 1. Simplified config (the only settings)

```python
DJANGO_BINARY_BUILDER = {
    "NAME": "Example Project",
    "VERSION": "0.1.1",
    "PUBLISHER": "Example Company",
    "EXECUTABLE_NAME": "example-project",
    "ICON": BASE_DIR / "assets" / "icon.ico",
}
```

- All 5 keys optional with sane defaults (NAME ← project folder name, EXECUTABLE_NAME ← safe(NAME), VERSION ← `0.1.0`, PUBLISHER ← NAME, ICON ← none).
- Unknown keys → warning + ignore (catches typos without blocking builds).
- `conf.py` rewritten small (~100 lines); delete the giant validation tree.

## 2. Requirements resolution (`requirements.py`, new)

Priority order, exactly as you specified:
1. `requirements.txt` exists → use it.
2. Else `pyproject.toml` exists → extract `[project] dependencies` via `tomllib` and use those.
3. Else → `pip freeze` the current environment (dropping `django-binary-builder` itself and `-e ...` editable lines) and **write `requirements.txt` into the project root**.
- Always ensure the launcher runtime deps (`waitress`, `pywebview`, `python-dotenv`) are appended if missing.
- The resolved list is also written to the work dir for transparency.

## 3. `.python-version` handling (`python_version.py`, new)

- If `<project>/.python-version` is missing → write the current interpreter's `major.minor` (e.g. `3.14`).
- If it exists → use as-is; if the current interpreter's `major.minor` differs, fail with a clear "activate a 3.14 venv" error (reproducible bundles).

## 4. Portable runtime builder (`builders/runtime_env.py`, new)

- Copy `sys.base_prefix` (the real CPython install, e.g. the uv-managed 3.14.6) into `<work>/windows/bundle/runtime/`. A copied CPython directory is self-contained on Windows (resolves paths relative to its own location, no registry). Microsoft-Store Pythons are detected and rejected with a clear message.
- Wipe the copied `Lib/site-packages` for a clean slate, bootstrap pip with `runtime\python.exe -m ensurepip` (offline), then `runtime\python.exe -m pip install -r requirements.txt` (uses the normal pip cache; needs internet on first build).
- **No PyInstaller is involved for your Django code — this is the fix for additional libraries.**

## 5. Project bundle (`builders/bundle.py`, new)

- Copy project source → `bundle/app/` (exclude `.git`, venvs, `__pycache__`, work/release dirs, `*.pyc`; keep `.env` and `db.sqlite3`).
- `collectstatic`: if `STATIC_ROOT` isn't configured, temporarily set it to `bundle/app/staticfiles` before collecting — zero-config static files.
- Copy `.env` into `app/` (auto-read; bundled values are overridable by real env vars at runtime).
- Generate `app/launcher.py` — **self-contained, no imports from django_binary_builder**:
  - stdio → `%LOCALAPPDATA%\...\logs\startup.log` (pythonw has no console)
  - load `.env` (process env wins), honor `DJANGO_SETTINGS_MODULE` override from it
  - `django.setup()`, then: append `127.0.0.1`/`localhost` to `ALLOWED_HOSTS`; relocate SQLite DB to the writable data dir (`%LOCALAPPDATA%\<Publisher>\<Name>\data\`, overridable via `DJANGO_BINARY_DATA_DIR`), auto-seeding from the bundled `db.sqlite3` on first run; run `migrate`; create initial `admin` superuser if none exists (password from `DJANGO_BINARY_ADMIN_PASSWORD` env or `admin1234`, with log warning)
  - auto-serve `/static/` (bundled staticfiles) and `/media/` (data dir) via a small pure-WSGI wrapper — admin styling works under waitress with zero project changes
  - waitress on `127.0.0.1:<first free port from 8765>` in a daemon thread
  - open pywebview window (title = NAME, 1200×800); fallback to default browser if pywebview unavailable; closing the window shuts the server down and exits

## 6. Entry executable (`builders/stub.py`, new)

`bundle/<EXECUTABLE_NAME>.exe` is built by PyInstaller as a **zero-dependency windowed onedir stub** whose only job is to spawn `runtime\pythonw.exe app\launcher.py` and propagate its exit code. Using PyInstaller for a stdlib-only stub is its most reliable mode, keeps the app icon, and no project code is ever frozen.

## 7. Installer (keep, adapt)

`inno_setup.py` + `installer.iss.j2` stay (per-user install to `{localappdata}\Programs\<Name>`, desktop + start-menu shortcuts, lzma2, data dir untouched on uninstall). Only the bundle layout fed into it changes.

## 8. CLI (simplified `binary` command)

`manage.py binary windows` with: `--skip-installer`, `--clean`, `--check` (preflight only), `--output`. All other flags removed.

## 9. Files deleted

`builders/pyinstaller.py`, `builders/launcher.py`, `discovery/*`, `environment/*` (snapshot/policy machinery), `runtime/*` (replaced by the self-contained launcher), `templates/application.spec.j2`, `templates/runtime-defaults.json.j2`, `platforms/linux.py`, `platforms/macos.py`. Keep: `builders/__init__.py` (render_template), `inno_setup.py`, `apps.py`, `enums.py` (trimmed), `platforms/base.py`+`windows.py` (rewritten).

## 10. Project housekeeping

- `pyproject.toml`: dependencies → Django, jinja2, pyinstaller, python-dotenv (pywebview/waitress now only installed into the bundle); refresh pytest config for new tests.
- New lean test suite (old one already deleted): requirements resolution (all 3 paths + filtering), `.python-version` logic, conf merge/validation, launcher template renders + `compile()` smoke test, Inno escaping.
- Add `examples/requirements.txt` (Django) for a clean demo; example keeps its 5-key config unchanged.
- Rewrite `README.md` for the new flow.

## Decisions I made (flag now if you disagree)

- `.python-version` mismatch = hard error (reproducibility) rather than silently using the current interpreter.
- Auto-seed the runtime SQLite from a bundled project `db.sqlite3` on first run (delete the file from the project to ship an empty DB).
- Initial admin (`admin`/`admin1234`, env-overridable) is created automatically when the auth app is installed and no superuser exists — no config section.
- Bundle layout: `AppName.exe`, `_internal/` (stub), `runtime/` (Python + packages), `app/` (your project).

## Verification

1. Fresh pytest suite green + ruff clean.
2. Full end-to-end build of `examples/` (`manage.py binary windows`) — freeze/pyproject path unit-tested; example uses the requirements.txt path. Inno Setup 7 is installed, so a real `Setup.exe` is produced.
3. Launch the built app once and verify server + webview startup log, then terminate.