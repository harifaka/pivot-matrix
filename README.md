# Pivot

Pivot is an offline-first Eisenhower Matrix desktop app for Windows built with Python and PySide6.
It is designed for low-friction planning with a dark ambient interface, keyboard-first controls, JSON persistence, and zero cloud dependencies.

## Why this foundation exists

This repository now contains a production-oriented foundation for a desktop application with:

- a strict separation between UI, application state, domain models, and persistence
- typed dataclass-based task models with UUID identifiers and timestamp history
- JSON persistence with schema versioning and atomic writes
- debounced autosave architecture
- markdown editing and preview support
- dark theme and tray icon scaffolding
- linting, formatting, type-checking, tests, and Nuitka build scripts

## Architecture

```text
pivot-matrix/
├── pyproject.toml
├── requirements-build.txt
├── requirements-dev.txt
├── scripts/
│   ├── build_nuitka.py
│   └── build_windows.ps1
├── src/pivot/
│   ├── __main__.py
│   ├── bootstrap.py
│   ├── config.py
│   ├── constants.py
│   ├── logging_config.py
│   ├── application/
│   │   ├── autosave.py
│   │   └── state.py
│   ├── domain/
│   │   └── models.py
│   ├── persistence/
│   │   └── json_store.py
│   └── ui/
│       ├── main_window.py
│       ├── theme.py
│       └── tray.py
├── tests/
└── .vscode/
```

### Layer responsibilities

- **Domain**: pure task entities, timestamps, history, serialization boundaries
- **Application state**: orchestration, selection, matrix section projections, save lifecycle
- **Persistence**: file IO, atomic JSON reads/writes, schema compatibility checks
- **UI**: Qt widgets, keyboard shortcuts, rendering, preview, tray integration

## Task model

Each task supports:

- UUID-based identity
- title plus markdown body
- created, updated, completed, and saved timestamps
- optional due date
- inbox routing or quadrant placement
- archived and completed states
- append-only history snapshots for every state transition

## Getting started

### Runtime requirements

- Python 3.13
- Windows for the primary desktop target

### Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

### Run the app

```powershell
python -m pivot
```

## Development workflow

### Install dev tooling

```powershell
python -m pip install -r requirements-dev.txt
```

### Lint, format, type-check, and test

```powershell
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest
```

## Build strategy

The repository keeps a simple split dependency strategy:

- runtime dependencies live in `pyproject.toml`
- developer tooling installs through `requirements-dev.txt`
- packaging tooling installs through `requirements-build.txt`

## Nuitka build instructions

Install build dependencies and create a standalone Windows executable:

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_nuitka.py
```

Or use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

## VS Code recommendations

The workspace includes recommended settings for:

- Ruff formatting and import organization on save
- pytest discovery
- Python and Pylance extensions

## Persistence and configuration

Pivot stores all user data locally:

- `%APPDATA%\Pivot\data\tasks.json` for the task document
- `%APPDATA%\Pivot\config\config.json` for user configuration
- `%APPDATA%\Pivot\logs\pivot.log` for rotating logs

On non-Windows systems, it falls back to `~/.pivot/`.

## License recommendation

MIT is already included in this repository and is a strong fit for this project foundation because it keeps distribution and future packaging flexible.

## Next recommended milestones

- drag-and-drop task movement between sections
- richer markdown attachments and backlinks
- recurring task scheduling
- saved filters and command palette actions
- import and export flows
