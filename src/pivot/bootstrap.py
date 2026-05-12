"""Application bootstrap for Pivot."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from pivot.application import AppState, AutosaveController
from pivot.config import load_environment, save_user_config
from pivot.logging_config import configure_logging
from pivot.persistence import JsonDataStore, UnsupportedSchemaVersionError
from pivot.ui import AppTrayIcon, MainWindow
from pivot.ui.theme import apply_theme, normalize_theme_name

logger = logging.getLogger(__name__)


def run() -> int:
    environment = load_environment()
    configure_logging(environment.paths)
    logger.info(
        "Starting Pivot | portable=%s | root=%s",
        environment.paths.portable,
        environment.paths.root,
    )

    def handle_unhandled_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: object,
    ) -> None:
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_unhandled_exception

    app = QApplication(sys.argv)
    app.setApplicationDisplayName(environment.app_name)
    environment.user_config.theme = normalize_theme_name(environment.user_config.theme)
    apply_theme(app, environment.user_config.theme)

    store = JsonDataStore(environment.paths.data_file, backup_dir=environment.paths.backup_dir)
    state = AppState(store)
    try:
        state.load()
    except UnsupportedSchemaVersionError:
        logger.exception("Unsupported data schema detected")
        raise
    except Exception:
        logger.exception("Failed to load persisted data; continuing with empty state")
    autosave = AutosaveController(state, environment.user_config.autosave_interval_ms)

    window = MainWindow(state, environment.user_config)
    window.configure_tray_behavior(
        enabled=environment.user_config.tray_enabled,
        minimize_to_tray=environment.user_config.minimize_to_tray,
    )
    tray: AppTrayIcon | None = None
    if environment.user_config.tray_enabled and QSystemTrayIcon.isSystemTrayAvailable():
        app.setQuitOnLastWindowClosed(False)
        def handle_theme_change(theme_name: str) -> None:
            normalized = normalize_theme_name(theme_name)
            environment.user_config.theme = normalized
            apply_theme(app, normalized)
            save_user_config(environment.paths, environment.user_config)

        def handle_minimize_to_tray_change(enabled: bool) -> None:
            environment.user_config.minimize_to_tray = enabled
            window.configure_tray_behavior(
                enabled=environment.user_config.tray_enabled,
                minimize_to_tray=enabled,
            )
            save_user_config(environment.paths, environment.user_config)

        def handle_start_minimized_change(enabled: bool) -> None:
            environment.user_config.start_minimized = enabled
            save_user_config(environment.paths, environment.user_config)

        tray = AppTrayIcon(
            window,
            on_save=state.save_now,
            on_quit=window.request_exit,
            on_theme_change=handle_theme_change,
            on_minimize_to_tray_change=handle_minimize_to_tray_change,
            on_start_minimized_change=handle_start_minimized_change,
            minimize_to_tray=environment.user_config.minimize_to_tray,
            start_minimized=environment.user_config.start_minimized,
            active_theme=environment.user_config.theme,
        )
        tray.show()

    def handle_about_to_quit() -> None:
        try:
            autosave.flush()
        except Exception:
            logger.exception("Autosave flush failed during shutdown")
        environment.user_config.window.width = window.width()
        environment.user_config.window.height = window.height()
        try:
            save_user_config(environment.paths, environment.user_config)
        except Exception:
            logger.exception("Failed to persist user configuration during shutdown")
        logger.info("Pivot shutdown complete")

    app.aboutToQuit.connect(handle_about_to_quit)

    if not environment.user_config.start_minimized:
        window.show()
    else:
        window.hide()
    if tray is not None:
        tray.showMessage("Pivot", "Offline-first matrix ready.", tray.MessageIcon.Information, 2500)
        if environment.user_config.start_minimized:
            QTimer.singleShot(1500, lambda: tray.showMessage("Pivot", "Running in tray.", tray.MessageIcon.Information, 2000))
    return app.exec()
