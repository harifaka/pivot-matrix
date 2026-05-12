"""Application bootstrap for Pivot."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from pivot.application import AppState, AutosaveController
from pivot.config import load_environment, save_user_config
from pivot.logging_config import configure_logging
from pivot.persistence import JsonDataStore
from pivot.ui import AppTrayIcon, MainWindow
from pivot.ui.theme import apply_theme

logger = logging.getLogger(__name__)


def run() -> int:
    environment = load_environment()
    configure_logging(environment.paths)

    app = QApplication(sys.argv)
    app.setApplicationDisplayName(environment.app_name)
    apply_theme(app)

    store = JsonDataStore(environment.paths.data_file)
    state = AppState(store)
    state.load()
    autosave = AutosaveController(state, environment.user_config.autosave_interval_ms)

    window = MainWindow(state, environment.user_config)
    tray: AppTrayIcon | None = None
    if environment.user_config.tray_enabled and QSystemTrayIcon.isSystemTrayAvailable():
        tray = AppTrayIcon(window)
        tray.show()

    def handle_about_to_quit() -> None:
        autosave.flush()
        environment.user_config.window.width = window.width()
        environment.user_config.window.height = window.height()
        save_user_config(environment.paths, environment.user_config)
        logger.info("Pivot shutdown complete")

    app.aboutToQuit.connect(handle_about_to_quit)

    window.show()
    if tray is not None:
        tray.showMessage("Pivot", "Offline-first matrix ready.", tray.MessageIcon.Information, 2500)
    return app.exec()
