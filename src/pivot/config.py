"""Configuration and application path helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pivot.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_SLUG,
    DEFAULT_PORTABLE_DIR_NAME,
    CONFIG_FILE_NAME,
    DATA_FILE_NAME,
    DEFAULT_AUTOSAVE_INTERVAL_MS,
    DEFAULT_THEME,
    LOG_FILE_NAME,
    PORTABLE_MARKER_FILE,
    WINDOW_DEFAULT_SIZE,
)


@dataclass(slots=True)
class WindowConfig:
    width: int = WINDOW_DEFAULT_SIZE[0]
    height: int = WINDOW_DEFAULT_SIZE[1]


@dataclass(slots=True)
class UserConfig:
    autosave_interval_ms: int = DEFAULT_AUTOSAVE_INTERVAL_MS
    tray_enabled: bool = True
    minimize_to_tray: bool = True
    start_minimized: bool = False
    theme: str = DEFAULT_THEME
    window: WindowConfig = field(default_factory=WindowConfig)

    def to_dict(self) -> dict[str, object]:
        return {
            "autosave_interval_ms": self.autosave_interval_ms,
            "tray_enabled": self.tray_enabled,
            "minimize_to_tray": self.minimize_to_tray,
            "start_minimized": self.start_minimized,
            "theme": self.theme,
            "window": {"width": self.window.width, "height": self.window.height},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> UserConfig:
        window_payload = payload.get("window", {})
        if not isinstance(window_payload, dict):
            window_payload = {}
        return cls(
            autosave_interval_ms=_coerce_int(
                payload.get("autosave_interval_ms"),
                DEFAULT_AUTOSAVE_INTERVAL_MS,
            ),
            tray_enabled=bool(payload.get("tray_enabled", True)),
            minimize_to_tray=bool(payload.get("minimize_to_tray", True)),
            start_minimized=bool(payload.get("start_minimized", False)),
            theme=str(payload.get("theme", DEFAULT_THEME)),
            window=WindowConfig(
                width=_coerce_int(window_payload.get("width"), WINDOW_DEFAULT_SIZE[0]),
                height=_coerce_int(window_payload.get("height"), WINDOW_DEFAULT_SIZE[1]),
            ),
        )


@dataclass(slots=True)
class AppPaths:
    root: Path
    portable: bool
    config_dir: Path
    data_dir: Path
    log_dir: Path
    backup_dir: Path
    config_file: Path
    data_file: Path
    log_file: Path

    def ensure(self) -> None:
        for folder in (self.root, self.config_dir, self.data_dir, self.log_dir, self.backup_dir):
            folder.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class AppEnvironment:
    app_name: str
    organization: str
    paths: AppPaths
    user_config: UserConfig


def _default_root() -> Path:
    app_data = os.getenv("APPDATA")
    if app_data:
        return Path(app_data) / APP_NAME
    return Path.home() / f".{APP_SLUG}"


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_base_dir() -> Path:
    executable_path = os.getenv("PIVOT_EXECUTABLE_PATH")
    if executable_path:
        return Path(executable_path).expanduser().resolve().parent
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def _resolve_root() -> tuple[Path, bool]:
    explicit_root = os.getenv("PIVOT_ROOT")
    if explicit_root:
        return Path(explicit_root).expanduser().resolve(), False

    portable_env = _is_truthy(os.getenv("PIVOT_PORTABLE"))
    app_base = _app_base_dir()
    portable_marker = app_base / PORTABLE_MARKER_FILE
    portable = portable_env or portable_marker.exists()
    if portable:
        return app_base / DEFAULT_PORTABLE_DIR_NAME, True
    return _default_root(), False


def _coerce_int(value: object, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def resolve_paths() -> AppPaths:
    root, portable = _resolve_root()
    config_dir = root / "config"
    data_dir = root / "data"
    log_dir = root / "logs"
    backup_dir = root / "backups"
    return AppPaths(
        root=root,
        portable=portable,
        config_dir=config_dir,
        data_dir=data_dir,
        log_dir=log_dir,
        backup_dir=backup_dir,
        config_file=config_dir / CONFIG_FILE_NAME,
        data_file=data_dir / DATA_FILE_NAME,
        log_file=log_dir / LOG_FILE_NAME,
    )


def _atomic_write_json(file_path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=file_path.parent,
        prefix=f".{file_path.stem}-",
        suffix=".tmp",
    ) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(file_path)


def load_user_config(paths: AppPaths) -> UserConfig:
    paths.ensure()
    if not paths.config_file.exists():
        return UserConfig()
    try:
        payload = json.loads(paths.config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        backup_path = paths.config_file.with_suffix(".bak")
        if backup_path.exists():
            try:
                payload = json.loads(backup_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return UserConfig()
        else:
            return UserConfig()
    if not isinstance(payload, dict):
        return UserConfig()
    return UserConfig.from_dict(payload)


def save_user_config(paths: AppPaths, config: UserConfig) -> None:
    paths.ensure()
    if paths.config_file.exists():
        backup_path = paths.config_file.with_suffix(".bak")
        backup_path.write_text(paths.config_file.read_text(encoding="utf-8"), encoding="utf-8")
    _atomic_write_json(paths.config_file, config.to_dict())


def load_environment() -> AppEnvironment:
    paths = resolve_paths()
    config = load_user_config(paths)
    return AppEnvironment(
        app_name=APP_NAME,
        organization=APP_ORGANIZATION,
        paths=paths,
        user_config=config,
    )
