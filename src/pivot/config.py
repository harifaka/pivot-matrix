"""Configuration and application path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os

from pivot.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_SLUG,
    CONFIG_FILE_NAME,
    DATA_FILE_NAME,
    DEFAULT_AUTOSAVE_INTERVAL_MS,
    LOG_FILE_NAME,
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
    window: WindowConfig = WindowConfig()

    def to_dict(self) -> dict[str, object]:
        return {
            "autosave_interval_ms": self.autosave_interval_ms,
            "tray_enabled": self.tray_enabled,
            "window": {"width": self.window.width, "height": self.window.height},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "UserConfig":
        window_payload = payload.get("window", {})
        if not isinstance(window_payload, dict):
            window_payload = {}
        return cls(
            autosave_interval_ms=int(payload.get("autosave_interval_ms", DEFAULT_AUTOSAVE_INTERVAL_MS)),
            tray_enabled=bool(payload.get("tray_enabled", True)),
            window=WindowConfig(
                width=int(window_payload.get("width", WINDOW_DEFAULT_SIZE[0])),
                height=int(window_payload.get("height", WINDOW_DEFAULT_SIZE[1])),
            ),
        )


@dataclass(slots=True)
class AppPaths:
    root: Path
    config_dir: Path
    data_dir: Path
    log_dir: Path
    config_file: Path
    data_file: Path
    log_file: Path

    def ensure(self) -> None:
        for folder in (self.root, self.config_dir, self.data_dir, self.log_dir):
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


def resolve_paths() -> AppPaths:
    root = _default_root()
    config_dir = root / "config"
    data_dir = root / "data"
    log_dir = root / "logs"
    return AppPaths(
        root=root,
        config_dir=config_dir,
        data_dir=data_dir,
        log_dir=log_dir,
        config_file=config_dir / CONFIG_FILE_NAME,
        data_file=data_dir / DATA_FILE_NAME,
        log_file=log_dir / LOG_FILE_NAME,
    )


def load_user_config(paths: AppPaths) -> UserConfig:
    paths.ensure()
    if not paths.config_file.exists():
        return UserConfig()
    try:
        payload = json.loads(paths.config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserConfig()
    if not isinstance(payload, dict):
        return UserConfig()
    return UserConfig.from_dict(payload)


def save_user_config(paths: AppPaths, config: UserConfig) -> None:
    paths.ensure()
    paths.config_file.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")


def load_environment() -> AppEnvironment:
    paths = resolve_paths()
    config = load_user_config(paths)
    return AppEnvironment(app_name=APP_NAME, organization=APP_ORGANIZATION, paths=paths, user_config=config)
