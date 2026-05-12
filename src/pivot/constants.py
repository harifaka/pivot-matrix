"""Application-wide constants."""

from __future__ import annotations

APP_NAME = "Pivot"
APP_SLUG = "pivot"
APP_VERSION = "0.1.0"
APP_ORGANIZATION = "harifaka"
APP_AUTHOR = "Peter Hari"
DATA_FILE_NAME = "tasks.json"
CONFIG_FILE_NAME = "config.json"
LOG_FILE_NAME = "pivot.log"
SCHEMA_VERSION = 1
DEFAULT_AUTOSAVE_INTERVAL_MS = 1500
WINDOW_MINIMUM_SIZE = (1240, 780)
WINDOW_DEFAULT_SIZE = (1440, 900)
DATE_DISPLAY_FORMAT = "ddd d MMM yyyy hh:mm"
TOOLTIP_DATE_FORMAT = "%Y-%m-%d %H:%M %Z"
HISTORY_DISPLAY_FORMAT = "%Y-%m-%d %H:%M"
TOOLTIP_BODY_MAX_LENGTH = 400
BOARD_SECTION_ORDER = ("inbox", "do", "schedule", "delegate", "eliminate")
RECENT_HISTORY_PREVIEW_COUNT = 6
