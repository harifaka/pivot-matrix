"""System tray integration."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from pivot.constants import APP_THEME_DARK, APP_THEME_LIGHT
from pivot.ui.theme import ACCENT, BACKGROUND, TEXT


def build_app_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(BACKGROUND))
    painter.drawRoundedRect(0, 0, size, size, 18, 18)
    painter.setPen(QColor(TEXT))
    font = QFont("Segoe UI", int(size * 0.45), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "P")
    painter.setPen(QColor(ACCENT))
    painter.drawRoundedRect(3, 3, size - 6, size - 6, 18, 18)
    painter.end()
    return QIcon(pixmap)


class AppTrayIcon(QSystemTrayIcon):
    """A tray icon shell that can be expanded later without touching the main UI."""

    def __init__(
        self,
        parent_window: QWidget,
        *,
        on_save: Callable[[], None],
        on_quit: Callable[[], None],
        on_theme_change: Callable[[str], None],
        on_minimize_to_tray_change: Callable[[bool], None],
        on_start_minimized_change: Callable[[bool], None],
        minimize_to_tray: bool,
        start_minimized: bool,
        active_theme: str,
    ) -> None:
        super().__init__(build_app_icon(), parent_window)
        self._window = parent_window
        menu = QMenu(parent_window)

        show_action = QAction("Show Pivot", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        toggle_action = QAction("Toggle Visibility", self)
        toggle_action.triggered.connect(self._toggle_window)
        menu.addAction(toggle_action)

        hide_action = QAction("Hide Pivot", self)
        hide_action.triggered.connect(self._window.hide)
        menu.addAction(hide_action)

        menu.addSeparator()

        save_action = QAction("Save Now", self)
        save_action.triggered.connect(on_save)
        menu.addAction(save_action)

        settings_menu = menu.addMenu("Settings")

        minimize_action = QAction("Minimize to tray", self)
        minimize_action.setCheckable(True)
        minimize_action.setChecked(minimize_to_tray)
        minimize_action.triggered.connect(on_minimize_to_tray_change)
        settings_menu.addAction(minimize_action)

        start_minimized_action = QAction("Start minimized", self)
        start_minimized_action.setCheckable(True)
        start_minimized_action.setChecked(start_minimized)
        start_minimized_action.triggered.connect(on_start_minimized_change)
        settings_menu.addAction(start_minimized_action)

        theme_menu = settings_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        def handle_dark_theme(checked: bool) -> None:
            if checked:
                on_theme_change(APP_THEME_DARK)

        def handle_light_theme(checked: bool) -> None:
            if checked:
                on_theme_change(APP_THEME_LIGHT)

        dark_action = QAction("Dark", self)
        dark_action.setCheckable(True)
        dark_action.setChecked(active_theme == APP_THEME_DARK)
        dark_action.triggered.connect(handle_dark_theme)
        theme_group.addAction(dark_action)
        theme_menu.addAction(dark_action)

        light_action = QAction("Light", self)
        light_action.setCheckable(True)
        light_action.setChecked(active_theme == APP_THEME_LIGHT)
        light_action.triggered.connect(handle_light_theme)
        theme_group.addAction(light_action)
        theme_menu.addAction(light_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(on_quit)
        menu.addAction(quit_action)

        self.setToolTip("Pivot")
        self.setContextMenu(menu)
        self.activated.connect(self._handle_activation)

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self._toggle_window()

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
            return
        self._show_window()
