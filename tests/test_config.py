from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from pivot.config import AppPaths, UserConfig, load_user_config, resolve_paths, save_user_config
from pivot.constants import DEFAULT_PORTABLE_DIR_NAME


def test_resolve_paths_uses_portable_mode_when_marker_exists(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "pivot.portable"
    marker.write_text("", encoding="utf-8")
    monkeypatch.setenv("PIVOT_EXECUTABLE_PATH", str(tmp_path / "Pivot.exe"))
    monkeypatch.delenv("PIVOT_ROOT", raising=False)
    monkeypatch.delenv("PIVOT_PORTABLE", raising=False)

    paths = resolve_paths()

    assert paths.portable
    assert paths.root == tmp_path / DEFAULT_PORTABLE_DIR_NAME


def test_user_config_roundtrip_and_backup_fallback(tmp_path: Path) -> None:
    config_root = tmp_path / "app"
    paths = AppPaths(
        root=config_root,
        portable=False,
        config_dir=config_root / "config",
        data_dir=config_root / "data",
        log_dir=config_root / "logs",
        backup_dir=config_root / "backups",
        config_file=config_root / "config" / "config.json",
        data_file=config_root / "data" / "tasks.json",
        log_file=config_root / "logs" / "pivot.log",
    )
    expected = UserConfig(theme="light", start_minimized=True, minimize_to_tray=False)
    save_user_config(paths, expected)
    save_user_config(paths, expected)
    paths.config_file.write_text("{bad-json", encoding="utf-8")

    loaded = load_user_config(paths)

    assert loaded.theme == "light"
    assert loaded.start_minimized is True
    assert loaded.minimize_to_tray is False
