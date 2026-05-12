"""System tray integration."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

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

    def __init__(self, parent_window: QWidget) -> None:
        super().__init__(build_app_icon(), parent_window)
        self._window = parent_window
        menu = QMenu(parent_window)

        show_action = QAction("Show Pivot", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        toggle_action = QAction("Toggle Visibility", self)
        toggle_action.triggered.connect(self._toggle_window)
        menu.addAction(toggle_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(parent_window.close)
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
