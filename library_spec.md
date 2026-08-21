# Django Binary Builder 完整技術規格

## 1. 文件資訊

- 專案名稱：`django-binary-builder`
- Python package：`django_binary_builder`
- Django management command：`python manage.py binary <platform>`
- 第一階段目標平台：Windows 10、Windows 11
- Python 基準版本：Python 3.14
- Django 支援版本：Django 6.x
- 文件狀態：MVP implementation specification

## 2. 專案目的

`django-binary-builder` 是一個可重用的 Django build library。使用者將它安裝到現有 Django 專案並加入 `INSTALLED_APPS`，即可透過 Django management command 將專案封裝為獨立、可安裝的桌面應用程式。

Windows 的完整流程如下：

```text
讀取 Django 設定與 .env
→ 驗證 build environment
→ 收集 static files
→ 產生 runtime configuration snapshot
→ 產生 launcher.py
→ 產生 PyInstaller spec
→ 以 PyInstaller 建立 onedir bundle
→ 產生 Inno Setup script
→ 以 Inno Setup 建立 Setup.exe
```

基本使用方式：

```powershell
uv add django-binary-builder
```

```python
INSTALLED_APPS = [
    # Existing apps
    "django_binary_builder",
]
```

```powershell
uv run python manage.py binary windows
```

最終輸出：

```text
release/windows/<executable-name>-<version>-Setup.exe
```

## 3. 核心設計原則

1. Library 只負責 orchestration，不重寫 PyInstaller 或 Inno Setup。
2. Build time、install time、first-run time 必須分離。
3. Application files 與可寫入的 runtime data 必須分離。
4. Windows installer 必須在 Windows host 上建立。
5. 第一版固定使用 PyInstaller `onedir`。
6. 不使用 Django `runserver`，runtime 使用 Waitress。
7. Runtime server 預設只綁定 `127.0.0.1`。
8. SQLite、media、logs、runtime config 不得放在安裝目錄。
9. 使用者修改過的 SQLite database 不得在升級或重裝時被覆寫。
10. Build log 不得輸出秘密值。
11. 所有 external process 均使用 argument list，不使用 `shell=True`。
12. CLI、設定解析、平台流程、模板生成及 runtime 初始化必須分模組實作。

## 4. 支援範圍

### 4.1 MVP 支援

- Python 3.14
- Django 6.x
- Windows 10、Windows 11
- PyInstaller 6.x
- PyInstaller `onedir`
- Inno Setup 7
- Waitress WSGI server
- WSGI Django projects
- Django static files
- Django templates 及 package data
- 額外 data files
- 額外 hidden imports
- Windows `.ico`
- `.env` build-time loading
- 經 allowlist 選取的環境變數 snapshot
- 內置 SQLite runtime database
- 外部 PostgreSQL、MySQL、MariaDB、Oracle 或其他 Django backend
- Runtime migrations
- SQLite 模式首次建立初始管理員
- 自訂 Django user model 的基本支援
- 可持久化 runtime data directory
- Editable installation 及 wheel installation

### 4.2 預留但尚未實作

CLI 預留：

```bash
python manage.py binary linux
python manage.py binary macos
```

對應平台模組預留：

```text
platforms/linux.py
platforms/macos.py
```

### 4.3 MVP 不支援

- Cross-compilation
- PyInstaller `onefile`
- ASGI、Django Channels、WebSocket
- Celery worker 與 Celery Beat
- 自帶 PostgreSQL、MySQL、MariaDB、Oracle server
- 自動安裝 database server
- 自動建立外部 database 或 database user
- 自動設定 database firewall
- Windows Service
- Linux AppImage、deb、rpm
- macOS `.app`、DMG、notarization
- Automatic updater
- Windows code signing
- 強制首次登入修改密碼的完整 authentication middleware
- 保證所有 native Python packages 零設定打包
- 在 build time 修改 production database

## 5. 名稱與公開 API

- PyPI distribution：`django-binary-builder`
- Import package：`django_binary_builder`
- Django AppConfig：`DjangoBinaryBuilderConfig`
- Django setting：`DJANGO_BINARY_BUILDER`
- Management command：`binary`
- Platform values：`windows`、`linux`、`macos`
- Database values：`sqlite`、`external`
- Runtime marker：`DJANGO_BINARY_RUNTIME=1`
- Runtime data override：`DJANGO_BINARY_DATA_DIR`

## 6. `pyproject.toml`

```toml
[project]
name = "django-binary-builder"
version = "0.1.0"
description = "Build Django projects as installable desktop applications"
readme = "README.md"
authors = [
    { name = "Benjamin Chau", email = "68836494+swarfte@users.noreply.github.com" }
]
requires-python = ">=3.14"
license = "MIT"
keywords = [
    "django",
    "pyinstaller",
    "inno-setup",
    "windows",
    "installer",
    "desktop",
    "packaging",
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Framework :: Django",
    "Framework :: Django :: 6.0",
    "Framework :: Django :: 6.1",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Topic :: Software Development :: Build Tools",
]
dependencies = [
    "Django>=6.0,<7.0",
    "jinja2>=3.1.6,<4.0",
    "pyinstaller>=6.22.2,<7.0",
    "python-dotenv>=1.1,<2.0",
    "waitress>=3.0.2,<4.0",
]

[project.urls]
Homepage = "https://github.com/swarfte/django-binary-builder"
Repository = "https://github.com/swarfte/django-binary-builder"
Issues = "https://github.com/swarfte/django-binary-builder/issues"

[build-system]
requires = ["uv_build>=0.12.0,<0.13.0"]
build-backend = "uv_build"

[dependency-groups]
dev = [
    "pytest>=9.1.1,<10.0",
    "pytest-django>=4.14.0,<5.0",
    "ruff>=0.16.4,<1.0",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.test_project.settings"
python_files = ["test_*.py"]
addopts = ["-ra", "--strict-markers", "--strict-config"]

[tool.ruff]
target-version = "py314"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

## 7. 專案結構

```text
django-binary-builder/
├── .python-version
├── LICENSE
├── README.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── django_binary_builder/
│       ├── __init__.py
│       ├── apps.py
│       ├── conf.py
│       ├── context.py
│       ├── enums.py
│       ├── exceptions.py
│       ├── management/
│       │   ├── __init__.py
│       │   └── commands/
│       │       ├── __init__.py
│       │       └── binary.py
│       ├── discovery/
│       │   ├── __init__.py
│       │   ├── django_project.py
│       │   ├── dependencies.py
│       │   └── database.py
│       ├── environment/
│       │   ├── __init__.py
│       │   ├── loader.py
│       │   ├── policy.py
│       │   ├── snapshot.py
│       │   └── validation.py
│       ├── platforms/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── windows.py
│       │   ├── linux.py
│       │   └── macos.py
│       ├── builders/
│       │   ├── __init__.py
│       │   ├── launcher.py
│       │   ├── pyinstaller.py
│       │   └── inno_setup.py
│       ├── runtime/
│       │   ├── __init__.py
│       │   ├── paths.py
│       │   ├── environment.py
│       │   ├── database.py
│       │   ├── initialization.py
│       │   ├── admin.py
│       │   ├── state.py
│       │   └── locks.py
│       └── templates/
│           ├── launcher.py.j2
│           ├── application.spec.j2
│           ├── installer.iss.j2
│           └── runtime-defaults.json.j2
├── examples/
│   └── basic_project/
│       ├── .env.example
│       ├── manage.py
│       └── basic_project/
│           ├── __init__.py
│           ├── settings.py
│           ├── urls.py
│           └── wsgi.py
└── tests/
    ├── __init__.py
    ├── test_command.py
    ├── test_conf.py
    ├── test_context.py
    ├── test_environment_loader.py
    ├── test_environment_snapshot.py
    ├── test_pyinstaller_builder.py
    ├── test_inno_builder.py
    ├── test_runtime_paths.py
    ├── test_runtime_database.py
    ├── test_runtime_initialization.py
    ├── test_runtime_admin.py
    ├── test_runtime_state.py
    └── test_project/
        ├── __init__.py
        ├── settings.py
        ├── urls.py
        └── wsgi.py
```

## 8. 模組責任與協作方式

### 8.1 `apps.py`

定義 `DjangoBinaryBuilderConfig`。不包含 models、views 或 migrations。

### 8.2 `conf.py`

負責：

- 定義 defaults
- 深層合併 `DJANGO_BINARY_BUILDER`
- 正規化路徑
- 驗證設定型別
- 產生安全 executable name
- 不執行 build
- 不讀取秘密值到 BuildContext

### 8.3 `enums.py`

定義：

```python
class TargetPlatform(StrEnum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class DatabaseMode(StrEnum):
    SQLITE = "sqlite"
    EXTERNAL = "external"
```

### 8.4 `context.py`

提供 `BuildContext`，集中保存非敏感 build metadata 及 paths。不得保存 database password、admin password 或完整 database URL。

### 8.5 `management/commands/binary.py`

只負責：

- 建立 CLI parser
- 載入設定
- 套用 CLI overrides
- 建立 BuildContext
- 驗證 target 與 host
- dispatch 到 platform implementation

不得直接 render template、呼叫 PyInstaller 或呼叫 Inno Setup。

### 8.6 `discovery/`

負責發現：

- project root
- settings module
- WSGI application
- installed apps
- static root
- database backend
- database driver package
- package data requirements

### 8.7 `environment/`

負責 `.env`：

- 尋找及解析 `.env`
- 合併 process environment
- 套用 include、exclude、secret policies
- 建立 runtime environment snapshot
- redact build log
- 不把原始 `.env` 整份直接複製到 bundle

### 8.8 `platforms/windows.py`

負責 Windows pipeline orchestration。它呼叫 builders，但不包含 Jinja template 細節。

### 8.9 `builders/launcher.py`

產生 launcher entry point。

### 8.10 `builders/pyinstaller.py`

產生 spec、執行 PyInstaller、驗證 bundle。

### 8.11 `builders/inno_setup.py`

尋找 ISCC、產生 `.iss`、執行 ISCC、驗證 installer。

### 8.12 `runtime/`

只在 packaged application 啟動時使用：

- 載入 runtime environment snapshot
- 建立 persistent directories
- 套用 database runtime mode
- 執行 migrations
- 建立初始管理員
- 管理 state 與 lock

## 9. 完整 Django 設定格式

```python
DJANGO_BINARY_BUILDER = {
    "NAME": "My Application",
    "VERSION": "1.0.0",
    "PUBLISHER": "Example Company",
    "EXECUTABLE_NAME": "my-application",
    "ICON": BASE_DIR / "assets" / "application.ico",
    "OUTPUT_DIR": BASE_DIR / "release",
    "WORK_DIR": BASE_DIR / ".django-binary-builder",
    "SERVER": {
        "HOST": "127.0.0.1",
        "PORT": 8765,
        "THREADS": 8,
        "MODE": "webview",
        "OPEN_BROWSER": True,
    },
    "WEBVIEW": {
        "TITLE": None,
        "WIDTH": 1200,
        "HEIGHT": 800,
        "RESIZABLE": True,
    },
    "ENVIRONMENT": {
        "ENABLED": True,
        "FILES": [BASE_DIR / ".env"],
        "OVERRIDE_PROCESS_ENV": False,
        "INCLUDE": [
            "DJANGO_SECRET_KEY",
            "DJANGO_ALLOWED_HOSTS",
            "APP_FEATURE_*",
        ],
        "EXCLUDE": [
            "DJANGO_BINARY_ADMIN_PASSWORD",
            "DJANGO_BINARY_DB_PASSWORD",
        ],
        "REQUIRED": ["DJANGO_SECRET_KEY"],
        "PACKAGE_MODE": "snapshot",
        "SNAPSHOT_FILENAME": "runtime-environment.json",
        "ALLOW_SECRETS": True,
        "WARN_ON_SECRET_NAMES": True,
    },
    "DATABASE": {
        "MODE": "sqlite",
        "RUN_MIGRATIONS": True,
        "MIGRATION_TIMEOUT": 300,
        "SQLITE": {
            "FILENAME": "db.sqlite3",
            "COPY_INITIAL_DATABASE": False,
            "INITIAL_DATABASE": None,
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
        "RESET_PASSWORD_IF_USER_EXISTS": False,
    },
    "RUNTIME": {
        "COMPANY_DIRECTORY": "ExampleCompany",
        "APPLICATION_DIRECTORY": "MyApplication",
        "DATA_DIRECTORY": None,
        "LOG_DIRECTORY": "logs",
        "MEDIA_DIRECTORY": "media",
        "CONFIG_DIRECTORY": "config",
    },
    "BUILD": {
        "MODE": "onedir",
        "CONSOLE": True,
        "CLEAN": True,
        "COLLECT_STATIC": True,
        "HIDDEN_IMPORTS": [],
        "EXCLUDED_MODULES": [],
        "EXTRA_DATA": [],
    },
    "WINDOWS": {
        "INNO_SETUP_COMPILER": None,
        "PRIVILEGES": "lowest",
        "ARCHITECTURE": "x64compatible",
        "CREATE_DESKTOP_SHORTCUT": True,
        "CREATE_START_MENU_SHORTCUT": True,
    },
}
```

## 10. CLI 規格

```text
python manage.py binary PLATFORM [OPTIONS]
```

### Positional argument

`PLATFORM` 接受 `windows`、`linux`、`macos`。

### Options

```text
--check
--generate-only
--skip-installer
--clean
--name VALUE
--app-version VALUE
--output PATH
--console
--no-collectstatic
--env-file PATH
--no-env
```

不得註冊 `--version`，因為 Django `BaseCommand` 已提供此 option。

### Option 行為

- `--check`：只執行 preflight。
- `--generate-only`：產生 launcher、spec、runtime metadata 及選擇性的 `.iss`。
- `--skip-installer`：執行 PyInstaller，不要求 Inno Setup。
- `--app-version`：覆寫 packaged application version。
- `--env-file`：在設定的 `ENVIRONMENT.FILES` 之後額外載入指定 `.env`。
- `--no-env`：完全停用 `.env` 讀取及 snapshot。

設定優先順序：

```text
CLI override
→ process environment
→ later .env file
→ earlier .env file
→ DJANGO_BINARY_BUILDER
→ library defaults
```

`OVERRIDE_PROCESS_ENV=False` 時，process environment 必須勝過 `.env`。

## 11. `.env` 打包規格

### 11.1 目標

Build 時自動讀取 `.env`，將選定變數轉換為 runtime snapshot，讓 packaged Django application 在沒有原始 `.env` 的環境中仍可獲得必要設定。

### 11.2 重要安全模型

PyInstaller bundle 與 installer 不能安全隱藏內嵌秘密。任何打包進 client-side application 的 password、API key 或 Django secret 都可能被具備檔案存取權的使用者取出。因此 `ALLOW_SECRETS=True` 代表使用者明確接受此風險，不代表內容已被加密或安全保護。

原始 `.env` 不得直接加入 bundle。必須解析後依 policy 建立 snapshot。

### 11.3 `.env` 搜尋順序

1. CLI `--env-file`
2. `ENVIRONMENT.FILES`
3. 若兩者均未設定，搜尋 `<PROJECT_ROOT>/.env`

不存在的自動預設 `.env` 可忽略。明確指定但不存在的檔案必須 raise `CommandError`。

### 11.4 合併規則

- 使用 `python-dotenv` 解析。
- 不修改 build process 的 `os.environ`，除非另有明確 API。
- 將所有來源先合併至獨立 dictionary。
- `OVERRIDE_PROCESS_ENV=False` 時，process environment 勝出。
- 支援 `${NAME}` interpolation，但檢測循環引用及 unresolved required values。

### 11.5 Include 與 exclude

- `INCLUDE` 支援完整名稱及 glob pattern。
- `EXCLUDE` 支援完整名稱及 glob pattern。
- `EXCLUDE` 永遠勝過 `INCLUDE`。
- `INCLUDE=[]` 表示不自動打包任何變數，而非全部包含。
- 若使用者要全部包含，必須明確使用 `INCLUDE=["*"]`。

### 11.6 Secret name detection

下列名稱 pattern 視為敏感：

```text
*SECRET*
*PASSWORD*
*TOKEN*
*API_KEY*
*PRIVATE_KEY*
*DATABASE_URL*
*DB_PASSWORD*
```

如果敏感變數被 include：

- `ALLOW_SECRETS=False` 時 build 失敗。
- `ALLOW_SECRETS=True` 時輸出 warning，但不顯示值。
- Build summary 只顯示 variable name 及 `[REDACTED]`。

### 11.7 Snapshot 格式

產生：

```text
<generated-dir>/runtime-environment.json
```

格式：

```json
{
  "schema_version": 1,
  "variables": {
    "DJANGO_SECRET_KEY": "value",
    "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
    "APP_FEATURE_REPORTING": "true"
  }
}
```

Snapshot 不得包含 source `.env` path，不得包含未選取變數。

### 11.8 Runtime 載入

Launcher 必須在 import Django settings 前：

```text
定位 bundled runtime-environment.json
→ 讀取 variables
→ 只對尚未存在於 os.environ 的名稱設定值
→ 設定 DJANGO_BINARY_RUNTIME=1
→ 設定 DJANGO_SETTINGS_MODULE
→ import Django settings
```

Runtime process environment 必須勝過 bundled snapshot，方便 IT 管理員覆寫。

### 11.9 Database credentials 特別規則

預設不得把 external database password 打包入 snapshot。建議透過：

```text
DJANGO_BINARY_DB_PASSWORD
runtime config/database.json
Windows deployment environment
```

如果使用者明確將它放入 `INCLUDE` 並設定 `ALLOW_SECRETS=True`，library 可以打包，但必須顯示高風險警告。

### 11.10 `.env` 測試

必須測試：

- 預設 `.env`
- 明確 `--env-file`
- 多檔案合併
- process environment precedence
- include glob
- exclude precedence
- required variable missing
- secret blocked
- secret allowed with warning
- value 不出現在 log
- snapshot 被 PyInstaller 收集
- runtime override snapshot

## 12. BuildContext

```python
@dataclass(slots=True)
class BuildContext:
    target_platform: str
    app_name: str
    app_version: str
    publisher: str | None
    executable_name: str
    database_mode: str
    runtime_company_directory: str
    runtime_application_directory: str
    project_root: Path
    work_dir: Path
    generated_dir: Path
    pyinstaller_build_dir: Path
    pyinstaller_dist_dir: Path
    release_dir: Path
    settings_module: str
    wsgi_application: str
    config: dict[str, Any]
```

Properties：

```python
launcher_path
spec_path
inno_script_path
runtime_environment_path
runtime_defaults_path
bundle_dir
executable_path
installer_filename
installer_path
uses_sqlite
uses_external_database
```

BuildContext 不得保存明文秘密。

## 13. Build 目錄

```text
<project-root>/
├── .django-binary-builder/
│   └── windows/
│       ├── generated/
│       │   ├── launcher.py
│       │   ├── application.spec
│       │   ├── installer.iss
│       │   ├── runtime-environment.json
│       │   └── runtime-defaults.json
│       ├── build/
│       └── dist/
│           └── <executable-name>/
│               ├── <executable-name>.exe
│               └── _internal/
└── release/
    └── windows/
        └── <executable-name>-<version>-Setup.exe
```

## 14. Windows Runtime 目錄

```text
%LOCALAPPDATA%/<CompanyDirectory>/<ApplicationDirectory>/
├── data/
│   └── db.sqlite3
├── config/
│   └── database.json
├── media/
├── logs/
│   └── application.log
└── state/
    ├── initialization.json
    └── initialization.lock
```

優先順序：

```text
DJANGO_BINARY_DATA_DIR
→ RUNTIME.DATA_DIRECTORY
→ %LOCALAPPDATA% default
```

Installer 及 uninstaller 不得預設刪除此 runtime directory。

## 15. Database 模式

### 15.1 SQLite

Runtime `DATABASES`：

```python
{
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": runtime_root / "data" / filename,
    }
}
```

Filename 必須是純 filename，禁止絕對路徑及 `..`。允許 `.sqlite3`、`.sqlite`、`.db`。

SQLite 初始化：

```text
建立 runtime directories
→ 若啟用 seed database 且 runtime DB 不存在，複製 seed
→ django.setup()
→ migrate
→ 建立 initial admin
→ 寫入 state
```

### 15.2 External database

支援兩種來源：

1. `USE_PROJECT_SETTINGS=True`，沿用 Django project 的 `DATABASES`
2. `USE_PROJECT_SETTINGS=False`，讀取 runtime `config/database.json`

支援環境變數：

```text
DJANGO_BINARY_DB_ENGINE
DJANGO_BINARY_DB_NAME
DJANGO_BINARY_DB_USER
DJANGO_BINARY_DB_PASSWORD
DJANGO_BINARY_DB_HOST
DJANGO_BINARY_DB_PORT
```

External config precedence：

```text
runtime process environment
→ database.json
→ project DATABASES
```

預設不將 external password 寫入 snapshot。

### 15.3 External driver

Builder 不安裝所有 drivers。使用者自行加入，例如：

```powershell
uv add "psycopg[binary]"
```

或：

```powershell
uv add mysqlclient
```

Preflight 根據 ENGINE 驗證 driver，並加入對應 hidden imports。

## 16. Runtime migrations

當 `RUN_MIGRATIONS=True`：

```python
call_command(
    "migrate",
    interactive=False,
    verbosity=1,
)
```

規則：

- Runtime 可執行 migrate。
- Build time 不執行 production migrations。
- 不執行 `makemigrations`。
- migration 失敗時不啟動 Waitress。
- migration error 不得包含 database password。
- 第一版 timeout 只記錄 elapsed warning，不強制中止 thread。

## 17. 初始管理員

### 17.1 預設值

```text
username: admin
password: admin1234
email: admin@localhost
```

此固定密碼只適用於首次建立，且屬公開初始 credential。Build 及 runtime 必須顯示不包含密碼內容的安全警告，要求首次登入後立即修改。

### 17.2 建立條件

- `INITIAL_ADMIN.ENABLED=True`
- SQLite mode，或 `SQLITE_ONLY=False`
- migrations 已成功完成
- 同名 user 不存在

### 17.3 實作要求

- 使用 `get_user_model()`。
- 使用 `USERNAME_FIELD`。
- 使用 `_default_manager`。
- 使用 `create_superuser()`。
- 使用 transaction。
- 支援 `EXTRA_FIELDS`。
- 不假設 email field 存在。
- 不在 state 或 log 記錄 password。

### 17.4 Idempotency

如果 user 已存在：

- 不重建
- 不重設 password
- 不修改 email
- 不提升普通 user 為 superuser
- state 記錄 `already_exists`

`RESET_PASSWORD_IF_USER_EXISTS=True` 在 MVP 不實作，應輸出安全 warning。

### 17.5 Environment override

```text
DJANGO_BINARY_ADMIN_USERNAME
DJANGO_BINARY_ADMIN_PASSWORD
DJANGO_BINARY_ADMIN_EMAIL
```

Runtime process environment 優先。成功建立後，後續啟動不得重新套用初始 password。

### 17.6 Password change flag

`REQUIRE_PASSWORD_CHANGE=True` 在 MVP 只代表：

- state 記錄需要修改
- application log 持續提醒
- README 說明

除非使用者整合 middleware 或客製 login flow，library 不得宣稱已技術上強制修改。

## 18. Runtime initialization

Launcher 順序必須是：

```text
1. 載入 bundled environment snapshot
2. 設定 DJANGO_BINARY_RUNTIME=1
3. 設定 DJANGO_SETTINGS_MODULE
4. 建立 runtime directories
5. import django 並呼叫 django.setup()
6. 取得 initialization lock
7. 測試 database connection
8. 執行 migrations
9. 建立 initial admin
10. 寫入 initialization state
11. 釋放 lock
12. import WSGI application
13. 選擇可用 port
14. 啟動 Waitress
15. 開啟 browser
```

初始化失敗時：

- 不啟動 Waitress
- 不開啟 browser
- 寫入 sanitized log
- process 以 non-zero code 結束

## 19. Runtime state

`initialization.json`：

```json
{
  "schema_version": 1,
  "application_version": "1.0.0",
  "database_mode": "sqlite",
  "migrations_completed": true,
  "initial_admin_status": "created",
  "initial_admin_username": "admin",
  "initial_admin_password_change_required": true,
  "initialized_at": "ISO-8601 timestamp"
}
```

不得記錄 administrator password、database password、Django secret key 或 database URL。

## 20. Launcher

Launcher 必須：

- 在 import settings 前完成 environment snapshot loading。
- 不使用 `runserver`。
- 不使用 autoreload。
- 支援直接以普通 Python 執行。
- 使用 Waitress，並以背景 thread 執行（`waitress.server.create_server(...).run()`），
  以便主 thread 可以控制 webview 的事件迴圈及後續關閉。
- 綁定 `127.0.0.1`。
- port 衝突時選擇可用 port。
- 依 `SERVER.MODE` 決定顯示方式：
  - `"webview"`（預設）：在主 thread 呼叫 `webview.create_window(...)` 及
    `webview.start()`，以原生桌面視窗顯示應用程式，不顯示瀏覽器網址列。
    `webview.start()` 為 blocking call；回傳（使用者關閉視窗）後，呼叫
    `server.close()` 並結束整個 process。
  - `"browser"`：使用實際 port 呼叫 `webbrowser.open()` 開啟系統預設瀏覽器，
    process 維持執行直到被外部終止。
  - 若 `pywebview` 無法 import，退回 `"browser"` 行為並記錄 warning，不得
    crash。
- 初始化失敗時停止，不啟動 Waitress，不建立 webview 視窗或開啟 browser。

## 21. PyInstaller

### 21.1 執行方式

```python
command = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--workpath",
    str(context.pyinstaller_build_dir),
    "--distpath",
    str(context.pyinstaller_dist_dir),
    str(context.spec_path),
]
```

不得使用 `shell=True`。

### 21.2 Spec requirements

包含：

- `Analysis`
- `PYZ`
- `EXE`
- `COLLECT`
- `upx=False`
- project root `pathex`
- Django data、binaries、hidden imports
- Waitress data、binaries、hidden imports
- installed app submodules
- selected database driver
- runtime modules
- static root
- extra data
- environment snapshot
- runtime defaults
- seed SQLite file，如啟用
- console setting
- icon setting

Runtime modules必須保留：

```text
django_binary_builder.runtime
```

Build-only modules可排除：

```text
django_binary_builder.builders
django_binary_builder.management
django_binary_builder.platforms
django_binary_builder.templates
```

### 21.3 成功驗證

必須驗證：

```python
context.bundle_dir.is_dir()
context.executable_path.is_file()
```

## 22. Static 與 extra data

當 `COLLECT_STATIC=True`：

- `STATIC_ROOT` 必須已設定。
- 執行 `collectstatic`。
- 將 `STATIC_ROOT` 加入 spec data。

`EXTRA_DATA` 格式：

```python
[
    {
        "source": "frontend/dist",
        "destination": "frontend/dist",
    }
]
```

必須驗證 item type、source、existence 及 destination。

不得無條件把整個 project root、`.git`、`.venv`、`.env`、database、release 或 node_modules 放入 bundle。

## 23. Inno Setup

### 23.1 ISCC 搜尋順序

1. `WINDOWS.INNO_SETUP_COMPILER`
2. `shutil.which("ISCC.exe")`
3. `C:\Program Files (x86)\Inno Setup 7\ISCC.exe`
4. `C:\Program Files\Inno Setup 7\ISCC.exe`

### 23.2 Installer

- 安裝至 `{localappdata}\Programs\<ApplicationName>`。
- `PrivilegesRequired=lowest`。
- 遞迴加入整個 onedir bundle。
- 根據設定建立 Start Menu 及 Desktop shortcuts。
- `.iss` 使用 UTF-8 BOM。
- AppId 使用固定 namespace 加 publisher 和 app name 的 UUID v5。
- version 不影響 AppId。
- 不刪除 runtime data。

## 24. Windows Pipeline

```text
1. 解析設定
2. 載入及驗證 .env
3. 建立安全 snapshot
4. 執行 preflight
5. 按需要清理 work directory
6. 建立 directories
7. Django system check
8. collectstatic
9. 產生 runtime defaults
10. 產生 launcher
11. 產生 PyInstaller spec
12. 如需要，產生 Inno Setup script
13. --generate-only 時停止
14. 執行 PyInstaller
15. 驗證 bundle 與 exe
16. --skip-installer 時停止
17. 執行 Inno Setup
18. 驗證 Setup.exe
19. 輸出 sanitized summary
```

## 25. Preflight

必須檢查：

- host 與 target 一致
- PyInstaller、Jinja2、Waitress、python-dotenv、pywebview 可 import
- project root 存在
- settings module 及 WSGI application 有效
- build mode 是 `onedir`
- STATIC_ROOT 在需要時有效
- icon 存在且為 `.ico`
- executable name 合法
- application version 非空
- output parent 可建立
- `.env` required variables 完整
- secret policy 合法
- snapshot 不包含 excluded variables
- database mode 合法
- SQLite filename 合法
- seed database 存在
- auth 及 contenttypes 在 initial admin 啟用時存在
- external backend driver 已安裝
- `EXTRA_DATA` source 存在
- 需要 installer 時可找到 ISCC

## 26. Option interaction

### `--check`

只做設定、environment 及 build preflight，不建立檔案，不連接 production database。

### `--generate-only`

生成 environment snapshot、runtime defaults、launcher、spec，並按需要生成 `.iss`，不執行 packaging tools。

### `--skip-installer`

不要求 ISCC，不生成 `.iss`，只產生 application bundle。

### `--generate-only --skip-installer`

只產生 runtime metadata、launcher 及 spec。

### `--no-env`

不讀取 `.env`，不產生包含 variables 的 snapshot。仍可產生空 schema snapshot。

## 27. Error handling

可理解的錯誤全部轉成 `CommandError`。Runtime 使用自訂：

```python
class RuntimeInitializationError(RuntimeError):
    pass
```

錯誤訊息及 logs 必須 redact：

- password
- token
- API key
- secret key
- private key
- database URL credentials

External process 必須保留正常 build log，但 library 不得自行把敏感 config 印出。

## 28. 測試

### 28.1 Unit tests

- command parser 沒有 `--version` conflict
- `--app-version` override
- host validation
- deep merge
- path normalization
- safe filename
- BuildContext paths
- `.env` precedence、glob、required、redaction
- secret opt-in
- runtime environment loading
- SQLite path
- external config precedence
- driver detection
- admin create、existing user、password preservation
- custom user model
- runtime state 無秘密
- PyInstaller subprocess failure 及 artifact validation
- ISCC discovery、AppId stability、artifact validation

### 28.2 Integration tests

Windows CI：

```text
建立 basic project
→ generate-only
→ validate generated Python/spec
→ build onedir
→ 啟動 exe
→ HTTP 200
→ 終止 process
```

SQLite integration：

```text
首次啟動
→ database 建立
→ migrations 完成
→ admin 建立
→ 修改 admin password
→ 第二次啟動
→ password 沒有被重設
```

External database integration 可使用 ephemeral PostgreSQL CI service，但不得連接真實 production database。

### 28.3 Wheel tests

Wheel 必須包含四個 templates。安裝 wheel 到另一個 Django project 後，`binary windows --check` 必須正常。

## 29. Example project

Example 必須展示：

- SQLite mode
- `.env.example`
- `ENVIRONMENT.INCLUDE`
- runtime settings integration
- Django admin URL
- static root
- `CONSOLE=True`

`.env.example` 只含示例值，不含真實秘密。

## 30. README 必須包含

- 安裝方式
- `INSTALLED_APPS`
- 完整 settings example
- Windows build prerequisites
- Inno Setup 安裝說明
- `.env` snapshot 安全警告
- external database driver 安裝
- SQLite runtime location
- initial admin 公開預設 credential 警告
- 首次登入修改密碼要求
- build、install、runtime data 分離
- 已知限制
- troubleshooting

## 31. 驗收里程碑

### Milestone 1

`help binary` 正常，`--app-version` 可用，無 parser conflict。

### Milestone 2

`--check --skip-installer` 通過。

### Milestone 3

`--generate-only --skip-installer` 產生合法 launcher、spec 及 runtime snapshot。

### Milestone 4

Launcher 可直接執行並回傳 HTTP 200。

### Milestone 5

`--skip-installer` 產生可執行 onedir bundle。

### Milestone 6

完整命令產生 Setup.exe，可安裝、啟動及解除安裝。

### Milestone 7

SQLite database 在 `%LOCALAPPDATA%` 建立且升級後保留。

### Milestone 8

首次建立 admin，第二次啟動不重設 password。

### Milestone 9

External mode 不建立 SQLite，能使用 project settings 或 runtime config。

### Milestone 10

`.env` allowlisted variables 在 runtime 可用，excluded variables 不在 bundle，logs 無明文秘密。

## 32. Coding Agent 實作次序

1. Command、conf、enums、BuildContext
2. Environment loader、policy、snapshot、tests
3. Windows preflight
4. Launcher 與 runtime environment loader
5. Runtime paths、SQLite、state、lock
6. Migrations 與 initial admin
7. External database config 及 driver discovery
8. PyInstaller spec 與 runner
9. Inno Setup template 與 runner
10. Example、README、wheel package data
11. Windows integration tests

每一 phase 完成後必須先通過 unit tests，才進入下一 phase。

## 33. 禁止事項

- 不得註冊 `--version`
- 不得使用 `shell=True`
- 不得使用 Django `runserver`
- 不得直接複製 `.venv`
- 不得直接複製原始 `.env`
- 不得預設把所有環境變數打包
- 不得在 logs 顯示秘密值
- 不得宣稱 packaged secret 是安全或加密的
- 不得把 SQLite 放在 `{app}` 或 temporary extraction directory
- 不得在升級時覆寫 SQLite
- 不得在 uninstall 時預設刪除 runtime data
- 不得在 build time修改 production database
- 不得在每次啟動重設 admin password
- 不得直接 import built-in `User`
- 不得自動提升已存在 user
- 不得預設在 external database 建立 admin
- 不得無條件把 project root 加入 data
- 不得只依賴 subprocess return code 而不驗證 artifact
- 不得把所有實作塞入 management command

## 34. 完成後執行

```powershell
uv sync
uv run python -m compileall src
uv run ruff format .
uv run ruff check .
uv run pytest
uv run python examples\basic_project\manage.py check
uv run python examples\basic_project\manage.py help binary
uv run python examples\basic_project\manage.py binary windows --check --skip-installer
uv run python examples\basic_project\manage.py binary windows --generate-only --skip-installer
uv build
```

Coding agent 最後必須報告：

1. 修改檔案清單
2. 各檔案責任
3. 執行過的測試
4. 通過及失敗結果
5. 已知限制
6. artifacts 路徑
7. `.env` 中哪些 variable names 被打包，但不得顯示 values
8. 是否發現任何高風險 secret 被 include

## 35. 最終成功標準

使用者可在新的 Django 6.x 專案中執行：

```powershell
uv add django-binary-builder
uv run python manage.py binary windows
```

並得到可安裝的 Windows `Setup.exe`。安裝後 application 可啟動 Waitress、使用 SQLite 或外部 database、按設定執行 migrations、在 SQLite 首次初始化時建立管理員，並載入 build 時明確選取的 `.env` variables。所有可寫入資料位於 persistent runtime directory，升級與解除安裝不會預設刪除使用者資料。
