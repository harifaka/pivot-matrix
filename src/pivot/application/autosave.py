"""Autosave orchestration."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer

from pivot.application.state import AppState

logger = logging.getLogger(__name__)


class AutosaveController(QObject):
    """Debounced autosave bridge between app state and persistence."""

    def __init__(self, state: AppState, interval_ms: int) -> None:
        super().__init__()
        self._state = state
        self._interval_ms = max(interval_ms, 250)
        self._failure_streak = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._flush)
        self._state.document_changed.connect(self.schedule)

    def schedule(self) -> None:
        if self._state.is_dirty:
            self._timer.start()

    def flush(self) -> None:
        self._timer.stop()
        if self._state.is_dirty:
            try:
                self._state.save_now()
                self._failure_streak = 0
            except Exception:
                self._failure_streak += 1
                retry_ms = min(self._interval_ms * (2**self._failure_streak), 20_000)
                logger.exception("Autosave failed; retrying in %sms", retry_ms)
                self._timer.start(retry_ms)

    def _flush(self) -> None:
        self.flush()
