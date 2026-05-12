"""Dark theme tokens and stylesheets."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#63f5d2"
ACCENT_ALT = "#a86fff"
BACKGROUND = "#0b0f17"
PANEL = "#121827"
PANEL_ALT = "#0f1524"
BORDER = "#232c42"
TEXT = "#edf2ff"
TEXT_MUTED = "#8b98b8"
SUCCESS = "#7fe6a2"
WARNING = "#ffd56b"


def apply_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BACKGROUND))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet())


def stylesheet() -> str:
    return f"""
    QWidget {{
        background: {BACKGROUND};
        color: {TEXT};
        font-family: Segoe UI, Inter, Arial, sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QMenu, QStatusBar {{
        background: {BACKGROUND};
    }}
    QFrame#Panel, QListWidget, QTextEdit, QTextBrowser, QLineEdit, QDateTimeEdit, QComboBox {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 8px;
    }}
    QListWidget::item {{
        padding: 10px 8px;
        margin: 4px 0;
        border-radius: 10px;
    }}
    QListWidget::item:selected {{
        background: rgba(99, 245, 210, 0.18);
        border: 1px solid rgba(99, 245, 210, 0.5);
    }}
    QPushButton {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 8px 12px;
    }}
    QPushButton:hover {{
        border-color: {ACCENT};
    }}
    QPushButton#PrimaryButton {{
        background: rgba(99, 245, 210, 0.14);
        border-color: rgba(99, 245, 210, 0.42);
    }}
    QTabBar::tab {{
        background: {PANEL_ALT};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 8px 12px;
        margin-right: 6px;
    }}
    QTabBar::tab:selected {{
        background: rgba(168, 111, 255, 0.18);
        border-color: rgba(168, 111, 255, 0.45);
    }}
    QLabel[class='eyebrow'] {{
        color: {TEXT_MUTED};
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 11px;
    }}
    QLabel[class='sectionTitle'] {{
        font-size: 18px;
        font-weight: 600;
    }}
    QLabel[class='muted'] {{
        color: {TEXT_MUTED};
    }}
    QCheckBox {{
        spacing: 8px;
    }}
    QScrollBar:vertical {{
        width: 12px;
        background: transparent;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 6px;
        min-height: 24px;
    }}
    """
