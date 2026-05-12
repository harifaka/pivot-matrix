"""Dark theme tokens and stylesheets."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from pivot.constants import APP_THEME_DARK, APP_THEME_LIGHT, DEFAULT_THEME

ACCENT = "#63f5d2"
ACCENT_ALT = "#a86fff"
BACKGROUND = "#0b0f17"
PANEL = "#121827"
PANEL_ALT = "#0f1524"
BORDER = "#232c42"
GLOW = "rgba(99, 245, 210, 0.14)"
GLOW_SOFT = "rgba(99, 245, 210, 0.08)"
TEXT = "#edf2ff"
TEXT_COMPLETED = "#aeb9d6"
TEXT_MUTED = "#8b98b8"
SUCCESS = "#7fe6a2"
WARNING = "#ffd56b"

LIGHT_THEME_TOKEN_MAP = {
    BACKGROUND: "#f4f6fb",
    PANEL: "#ffffff",
    PANEL_ALT: "#f7f9ff",
    BORDER: "#d8deef",
    TEXT: "#1d2433",
    TEXT_COMPLETED: "#61718f",
    TEXT_MUTED: "#6f7c98",
    "rgba(99, 245, 210, 0.18)": "rgba(168, 111, 255, 0.14)",
    "rgba(99, 245, 210, 0.5)": "rgba(168, 111, 255, 0.4)",
    "rgba(99, 245, 210, 0.55)": "rgba(168, 111, 255, 0.45)",
}


def normalize_theme_name(name: str) -> str:
    return name if name in {APP_THEME_DARK, APP_THEME_LIGHT} else DEFAULT_THEME


def apply_theme(app: QApplication, theme_name: str = DEFAULT_THEME) -> None:
    if normalize_theme_name(theme_name) == APP_THEME_LIGHT:
        _apply_light_theme(app)
        return
    _apply_dark_theme(app)


def _apply_dark_theme(app: QApplication) -> None:
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


def _apply_light_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f4f6fb"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1d2433"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f2f5ff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1d2433"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1d2433"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#f2f5ff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1d2433"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_ALT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(_mapped_stylesheet(stylesheet(), LIGHT_THEME_TOKEN_MAP))


def _mapped_stylesheet(source: str, replacements: dict[str, str]) -> str:
    themed = source
    for token, value in replacements.items():
        themed = themed.replace(token, value)
    return themed


def stylesheet() -> str:
    return f"""
    QWidget {{
        background: {BACKGROUND};
        color: {TEXT};
        font-family: Segoe UI, Inter, Arial, sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QMenu, QStatusBar, QDialog {{
        background: {BACKGROUND};
    }}
    QToolBar {{
        background: transparent;
        border: none;
        spacing: 8px;
    }}
    QStatusBar {{
        color: {TEXT_MUTED};
    }}
    QFrame#Panel,
    QListWidget,
    QTextEdit,
    QTextBrowser,
    QLineEdit,
    QDateTimeEdit,
    QComboBox,
    QDialog {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 8px;
    }}
    QFrame#Panel {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {PANEL}, stop:1 {PANEL_ALT});
    }}
    QListWidget::item {{
        padding: 10px 8px;
        margin: 4px 0;
        border-radius: 10px;
    }}
    QListWidget::item:hover {{
        background: {GLOW_SOFT};
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
        background: {GLOW};
    }}
    QPushButton#PrimaryButton {{
        background: rgba(99, 245, 210, 0.14);
        border-color: rgba(99, 245, 210, 0.42);
    }}
    QPushButton#SectionAddButton {{
        min-width: 32px;
        max-width: 32px;
        min-height: 32px;
        max-height: 32px;
        border-radius: 16px;
        font-size: 18px;
        padding: 0;
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
    QSplitter::handle {{
        background: transparent;
    }}
    QLineEdit:focus,
    QTextEdit:focus,
    QTextBrowser:focus,
    QListWidget:focus,
    QDateTimeEdit:focus,
    QComboBox:focus {{
        border-color: rgba(99, 245, 210, 0.55);
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
