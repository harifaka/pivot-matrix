"""Autosave orchestration."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from pivot.application.state import AppState


class AutosaveController(QObject):
    """Debounced autosave bridge between app state and persistence."""

    def __init__(self, state: AppState, interval_ms: int) -> None:
        super().__init__()
        self._state = state
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._flush)
        self._state.document_changed.connect(self.schedule)

    def schedule(self) -> None:
        if self._state.is_dirty:
            self._timer.start()

    def flush(self) -> None:
        self._timer.stop()
        if self._state.is_dirty:
            self._state.save_now()

    def _flush(self) -> None:
        self.flush()
