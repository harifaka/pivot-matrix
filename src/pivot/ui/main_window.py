"""Main application window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QDateTime, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pivot.application.state import AppState
from pivot.config import UserConfig
from pivot.constants import DATE_DISPLAY_FORMAT, WINDOW_MINIMUM_SIZE
from pivot.domain.models import Quadrant, Task


@dataclass(slots=True)
class EditorPayload:
    title: str
    content_markdown: str
    due_at: datetime | None
    inbox: bool
    quadrant: Quadrant | None
    completed: bool


class TaskListPanel(QFrame):
    task_selected = Signal(str)

    def __init__(self, section_key: str, title: str) -> None:
        super().__init__()
        self.setObjectName("Panel")
        self.section_key = section_key
        self._title = title
        self._list = QListWidget()
        self._header = QLabel(title)
        self._header.setProperty("class", "sectionTitle")
        subtitle = QLabel("keyboard-first queue")
        subtitle.setProperty("class", "eyebrow")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(subtitle)
        layout.addWidget(self._header)
        layout.addWidget(self._list)
        self._list.currentItemChanged.connect(self._emit_selection)

    def refresh(self, tasks: list[Task], selected_id: str) -> None:
        with QSignalBlocker(self._list):
            self._list.clear()
            self._header.setText(f"{self._title} · {len(tasks)}")
            current_row = -1
            for index, task in enumerate(tasks):
                item = QListWidgetItem(self._item_label(task))
                item.setData(Qt.ItemDataRole.UserRole, task.id)
                self._list.addItem(item)
                if task.id == selected_id:
                    current_row = index
            if current_row >= 0:
                self._list.setCurrentRow(current_row)

    def focus_list(self) -> None:
        self._list.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _item_label(self, task: Task) -> str:
        prefix = "✓" if task.is_completed else "•"
        suffix = " ⏳" if task.due_at else ""
        return f"{prefix} {task.display_title}{suffix}"

    def _emit_selection(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            return
        task_id = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(task_id, str):
            self.task_selected.emit(task_id)


class TaskEditor(QFrame):
    payload_changed = Signal(object)
    archive_requested = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Panel")
        self._current_task_id = ""
        self._loading = False

        eyebrow = QLabel("Task detail")
        eyebrow.setProperty("class", "eyebrow")
        title = QLabel("Focus")
        title.setProperty("class", "sectionTitle")

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Task title")
        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("Write in markdown…")
        self._preview = QTextBrowser()
        self._preview.setOpenExternalLinks(False)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._body_edit, "Markdown")
        self._tabs.addTab(self._preview, "Preview")

        self._inbox_check = QCheckBox("Keep in inbox")
        self._completed_check = QCheckBox("Completed")
        self._due_check = QCheckBox("Due date")
        self._due_edit = QDateTimeEdit()
        self._due_edit.setCalendarPopup(True)
        self._due_edit.setDisplayFormat(DATE_DISPLAY_FORMAT)
        self._quadrant_combo = QComboBox()
        self._quadrant_combo.addItem("Choose quadrant", None)
        for quadrant in Quadrant:
            self._quadrant_combo.addItem(quadrant.label, quadrant)

        archive_button = QPushButton("Archive task")
        archive_button.clicked.connect(lambda: self.archive_requested.emit(True))
        restore_button = QPushButton("Restore task")
        restore_button.clicked.connect(lambda: self.archive_requested.emit(False))

        controls = QGridLayout()
        controls.addWidget(self._inbox_check, 0, 0)
        controls.addWidget(self._completed_check, 0, 1)
        controls.addWidget(self._due_check, 1, 0)
        controls.addWidget(self._due_edit, 1, 1)
        controls.addWidget(QLabel("Quadrant"), 2, 0)
        controls.addWidget(self._quadrant_combo, 2, 1)

        action_row = QHBoxLayout()
        action_row.addWidget(archive_button)
        action_row.addWidget(restore_button)
        action_row.addStretch(1)

        self._history = QLabel("No history yet")
        self._history.setWordWrap(True)
        self._history.setProperty("class", "muted")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(self._title_edit)
        layout.addLayout(controls)
        layout.addWidget(self._tabs, 1)
        layout.addLayout(action_row)
        layout.addWidget(self._history)

        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(250)
        self._emit_timer.timeout.connect(self._emit_payload)

        self._title_edit.editingFinished.connect(self._emit_payload)
        self._body_edit.textChanged.connect(self._queue_emit)
        self._body_edit.textChanged.connect(self._render_preview)
        self._inbox_check.toggled.connect(self._handle_inbox_toggle)
        self._completed_check.toggled.connect(self._emit_payload)
        self._due_check.toggled.connect(self._handle_due_toggle)
        self._due_edit.dateTimeChanged.connect(self._emit_payload)
        self._quadrant_combo.currentIndexChanged.connect(self._emit_payload)
        self._set_enabled(False)

    def current_task_id(self) -> str:
        return self._current_task_id

    def populate(self, task: Task | None, history: list[str]) -> None:
        self._loading = True
        self._current_task_id = task.id if task else ""
        enabled = task is not None
        self._set_enabled(enabled)
        if task is None:
            self._title_edit.clear()
            self._body_edit.clear()
            self._preview.clear()
            self._history.setText("Select a task to start editing.")
            self._loading = False
            return

        self._title_edit.setText(task.title)
        self._body_edit.setMarkdown(task.content_markdown)
        self._preview.setMarkdown(task.content_markdown)
        self._inbox_check.setChecked(task.inbox)
        self._completed_check.setChecked(task.is_completed)
        self._due_check.setChecked(task.due_at is not None)
        self._due_edit.setEnabled(task.due_at is not None)
        self._due_edit.setDateTime(self._to_qdatetime(task.due_at or datetime.now(tz=timezone.utc)))
        quadrant_index = 0
        if task.quadrant is not None:
            quadrant_index = self._quadrant_combo.findData(task.quadrant)
        self._quadrant_combo.setCurrentIndex(max(quadrant_index, 0))
        self._quadrant_combo.setEnabled(not task.inbox)
        self._history.setText("\n".join(history[:6]) or "No history yet")
        self._loading = False

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (
            self._title_edit,
            self._body_edit,
            self._tabs,
            self._inbox_check,
            self._completed_check,
            self._due_check,
            self._due_edit,
            self._quadrant_combo,
        ):
            widget.setEnabled(enabled)

    def _queue_emit(self) -> None:
        if self._loading:
            return
        self._emit_timer.start()

    def _handle_inbox_toggle(self, checked: bool) -> None:
        self._quadrant_combo.setEnabled(not checked)
        self._emit_payload()

    def _handle_due_toggle(self, checked: bool) -> None:
        self._due_edit.setEnabled(checked)
        self._emit_payload()

    def _render_preview(self) -> None:
        self._preview.setMarkdown(self._body_edit.toMarkdown())

    def _emit_payload(self) -> None:
        if self._loading or not self._current_task_id:
            return
        self.payload_changed.emit(
            EditorPayload(
                title=self._title_edit.text(),
                content_markdown=self._body_edit.toMarkdown(),
                due_at=self._due_at(),
                inbox=self._inbox_check.isChecked(),
                quadrant=self._quadrant_combo.currentData(),
                completed=self._completed_check.isChecked(),
            )
        )

    def _due_at(self) -> datetime | None:
        if not self._due_check.isChecked():
            return None
        qdatetime = self._due_edit.dateTime().toUTC()
        return datetime.fromtimestamp(qdatetime.toSecsSinceEpoch(), tz=timezone.utc)

    def _to_qdatetime(self, value: datetime) -> QDateTime:
        return QDateTime.fromSecsSinceEpoch(int(value.timestamp()), Qt.TimeSpec.UTC).toLocalTime()


class MainWindow(QMainWindow):
    """Primary desktop shell for Pivot."""

    def __init__(self, state: AppState, user_config: UserConfig) -> None:
        super().__init__()
        self._state = state
        self._user_config = user_config
        self.setWindowTitle("Pivot")
        self.setMinimumSize(*WINDOW_MINIMUM_SIZE)
        self.resize(user_config.window.width, user_config.window.height)

        self._panels = {
            "inbox": TaskListPanel("inbox", "Inbox"),
            "do": TaskListPanel("do", "Do"),
            "schedule": TaskListPanel("schedule", "Schedule"),
            "delegate": TaskListPanel("delegate", "Delegate"),
            "eliminate": TaskListPanel("eliminate", "Eliminate"),
        }
        self._editor = TaskEditor()
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Booting")

        self._build_toolbar()
        self._build_layout()
        self._connect_state()
        self._setup_shortcuts()
        self.refresh()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Commands", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(lambda: self._state.create_task())
        toolbar.addAction(new_action)

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._state.save_now)
        toolbar.addAction(save_action)

        complete_action = QAction("Toggle Complete", self)
        complete_action.setShortcut(QKeySequence("Ctrl+Enter"))
        complete_action.triggered.connect(self._toggle_selected_completed)
        toolbar.addAction(complete_action)

        archive_action = QAction("Archive", self)
        archive_action.setShortcut(QKeySequence("Ctrl+Backspace"))
        archive_action.triggered.connect(lambda: self._archive_selected(True))
        toolbar.addAction(archive_action)

        primary_button = QPushButton("New Task")
        primary_button.setObjectName("PrimaryButton")
        primary_button.clicked.connect(lambda: self._state.create_task())
        toolbar.addWidget(primary_button)

    def _build_layout(self) -> None:
        shell = QWidget()
        root_layout = QHBoxLayout(shell)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        board_widget = QWidget()
        board_layout = QVBoxLayout(board_widget)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_layout.setSpacing(16)
        board_layout.addWidget(self._panels["inbox"], 1)

        quadrant_grid = QGridLayout()
        quadrant_grid.setSpacing(16)
        quadrant_grid.addWidget(self._panels["do"], 0, 0)
        quadrant_grid.addWidget(self._panels["schedule"], 0, 1)
        quadrant_grid.addWidget(self._panels["delegate"], 1, 0)
        quadrant_grid.addWidget(self._panels["eliminate"], 1, 1)
        board_layout.addLayout(quadrant_grid, 3)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(board_widget)
        splitter.addWidget(self._editor)
        splitter.setSizes([900, 420])

        root_layout.addWidget(splitter)
        self.setCentralWidget(shell)

    def _connect_state(self) -> None:
        for panel in self._panels.values():
            panel.task_selected.connect(self._state.select_task)
        self._editor.payload_changed.connect(self._apply_editor_payload)
        self._editor.archive_requested.connect(self._archive_selected)
        self._state.document_changed.connect(self.refresh)
        self._state.selection_changed.connect(self._sync_selection)
        self._state.status_changed.connect(self._status.showMessage)
        self._state.save_state_changed.connect(self._update_window_title)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self._panels["inbox"].focus_list)
        QShortcut(QKeySequence("Ctrl+2"), self, activated=self._panels["do"].focus_list)
        QShortcut(QKeySequence("Ctrl+3"), self, activated=self._panels["schedule"].focus_list)
        QShortcut(QKeySequence("Ctrl+4"), self, activated=self._panels["delegate"].focus_list)
        QShortcut(QKeySequence("Ctrl+5"), self, activated=self._panels["eliminate"].focus_list)

    def refresh(self) -> None:
        sections = self._state.board_sections()
        selected_id = self._state.selected_task_id
        for key, panel in self._panels.items():
            panel.refresh(sections.get(key, []), selected_id)
        task = self._state.selected_task()
        self._editor.populate(task, self._state.history_for(selected_id) if selected_id else [])
        self._update_window_title(self._state.is_dirty)

    def _sync_selection(self, task_id: str) -> None:
        self._editor.populate(self._state.get_task(task_id), self._state.history_for(task_id))
        self.refresh()

    def _apply_editor_payload(self, payload: Any) -> None:
        if not isinstance(payload, EditorPayload):
            return
        task_id = self._editor.current_task_id()
        if not task_id:
            return
        self._state.update_task(
            task_id,
            title=payload.title,
            content_markdown=payload.content_markdown,
            due_at=payload.due_at,
            inbox=payload.inbox,
            quadrant=payload.quadrant,
        )
        self._state.set_task_completed(task_id, payload.completed)

    def _toggle_selected_completed(self) -> None:
        task = self._state.selected_task()
        if task is None:
            return
        self._state.set_task_completed(task.id, not task.is_completed)

    def _archive_selected(self, archived: bool) -> None:
        task = self._state.selected_task()
        if task is None:
            return
        self._state.archive_task(task.id, archived)

    def _update_window_title(self, dirty: bool) -> None:
        marker = " •" if dirty else ""
        self.setWindowTitle(f"Pivot{marker}")
