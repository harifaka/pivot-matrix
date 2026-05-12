# Pivot Matrix

Pivot is an offline-first Eisenhower Matrix desktop app built with Python + PySide6 and packaged for Windows distribution.

## Highlights

- system tray integration with close-to-tray behavior and quick actions
- robust autosave and crash-safe persistence
- atomic JSON writes with backup snapshots and recovery from corruption
- portable mode with app-relative storage support
- persisted settings (window size, tray behavior, startup behavior, theme)
- dark/light theme support
- large task list performance improvements and bounded history memory growth
- production build pipeline with Nuitka onefile output and Windows release packaging

## Screenshots

> Replace these placeholders with real screenshots.

### Main board

`docs/screenshots/main-board.png` (placeholder)

### Task editor

`docs/screenshots/task-editor.png` (placeholder)

### Tray menu

`docs/screenshots/tray-menu.png` (placeholder)

## Architecture

```text
src/pivot/
├── application/   # state orchestration + autosave
├── domain/        # typed task/document models
├── persistence/   # JSON load/save, backups, recovery
├── ui/            # Qt window, components, tray, themes
├── bootstrap.py   # app lifecycle wiring
└── config.py      # paths, modes, settings persistence
```

## Storage model

Standard mode:

- `%APPDATA%\Pivot\data\tasks.json`
- `%APPDATA%\Pivot\config\config.json`
- `%APPDATA%\Pivot\logs\pivot.log`
- `%APPDATA%\Pivot\backups\...`

Portable mode:

- `./pivot-data/data/tasks.json`
- `./pivot-data/config/config.json`
- `./pivot-data/logs/pivot.log`
- `./pivot-data/backups/...`

Portable mode can be enabled by:

- setting `PIVOT_PORTABLE=1`, or
- placing a `pivot.portable` marker file next to the executable.

## Development

### Requirements

- Python 3.13 target runtime (CI/development may also run on recent Python versions)

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

### Run locally

```powershell
python -m pivot
```

### Validate

```powershell
python -m ruff check .
python -m mypy src
python -m pytest
```

## Production build and release

Install build tooling:

```powershell
python -m pip install -r requirements-build.txt
```

Build onefile executable:

```powershell
python scripts/build_nuitka.py --onefile
```

Build and package Windows releases (standard + portable zip):

```powershell
python scripts/release_windows.py
```

PowerShell helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Optional icon integration:

```powershell
python scripts/release_windows.py --icon .\assets\pivot.ico
```

## Documentation map

- contribution guide: `CONTRIBUTING.md`
- roadmap: `ROADMAP.md`
- changelog: `CHANGELOG.md`

## License

MIT
