"""Reusable Qt widgets for the Pivot shell."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, override

from PySide6.QtCore import QDateTime, QEvent, QMimeData, QObject, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pivot.application.state import TaskSortMode, TaskStatusFilter, TaskViewState
from pivot.constants import (
    DATE_DISPLAY_FORMAT,
    RECENT_HISTORY_PREVIEW_COUNT,
    TOOLTIP_BODY_MAX_LENGTH,
    TOOLTIP_DATE_FORMAT,
)
from pivot.domain.models import Quadrant, Task
from pivot.markdown_sanitize import sanitize_markdown
from pivot.ui.theme import TEXT, TEXT_COMPLETED

TASK_MIME_TYPE = "application/x-pivot-task-id"
ITEM_IDENTIFIER_ROLE = Qt.ItemDataRole.UserRole


@dataclass(slots=True)
class EditorPayload:
    title: str
    content_markdown: str
    due_at: datetime | None
    inbox: bool
    quadrant: Quadrant | None
    completed: bool


@dataclass(slots=True, frozen=True)
class PaletteCommand:
    identifier: str
    title: str
    subtitle: str = ""
    shortcut: str = ""

    @property
    def search_text(self) -> str:
        return " ".join((self.title, self.subtitle, self.shortcut)).casefold()


class TaskListWidget(QListWidget):
    """Single task list with drag/drop and inline renaming."""

    task_selected = Signal(str)
    task_dropped = Signal(str, str)
    title_edited = Signal(str, str)

    def __init__(self, section_key: str) -> None:
        super().__init__()
        self._section_key = section_key
        self._refreshing = False
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.currentItemChanged.connect(self._emit_selection)
        self.itemChanged.connect(self._handle_item_changed)

    def refresh(self, tasks: list[Task], selected_id: str) -> None:
        self._refreshing = True
        blocker = QSignalBlocker(self)
        self.clear()
        current_row = -1
        for index, task in enumerate(tasks):
            item = QListWidgetItem(task.display_title)
            item.setData(ITEM_IDENTIFIER_ROLE, task.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(self._build_tooltip(task))
            item.setForeground(QColor(TEXT_COMPLETED if task.is_completed else TEXT))
            font = item.font()
            font.setStrikeOut(task.is_completed)
            item.setFont(font)
            self.addItem(item)
            if task.id == selected_id:
                current_row = index
        if current_row >= 0:
            self.setCurrentRow(current_row)
        del blocker
        self._refreshing = False

    def focus_list(self) -> None:
        self.setFocus(Qt.FocusReason.ShortcutFocusReason)

    @override
    def startDrag(self, supported_actions: Any) -> None:
        del supported_actions
        item = self.currentItem()
        if item is None:
            return
        task_id = item.data(ITEM_IDENTIFIER_ROLE)
        if not isinstance(task_id, str):
            return
        mime_data = QMimeData()
        mime_data.setData(TASK_MIME_TYPE, task_id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)

    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(TASK_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    @override
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat(TASK_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(TASK_MIME_TYPE):
            super().dropEvent(event)
            return
        payload = bytes(event.mimeData().data(TASK_MIME_TYPE).data()).decode("utf-8")
        if payload:
            self.task_dropped.emit(payload, self._section_key)
        event.acceptProposedAction()

    def _emit_selection(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        if current is None:
            return
        task_id = current.data(ITEM_IDENTIFIER_ROLE)
        if isinstance(task_id, str):
            self.task_selected.emit(task_id)

    def _handle_item_changed(self, item: QListWidgetItem) -> None:
        if self._refreshing:
            return
        task_id = item.data(ITEM_IDENTIFIER_ROLE)
        if isinstance(task_id, str):
            self.title_edited.emit(task_id, item.text())

    def _build_tooltip(self, task: Task) -> str:
        due_text = ""
        if task.due_at is not None:
            local_zone = datetime.now().astimezone().tzinfo or UTC
            due_text = f"Due: {task.due_at.astimezone(local_zone).strftime(TOOLTIP_DATE_FORMAT)}\n"
        body = task.content_markdown.strip() or "No notes yet"
        return f"{due_text}{body[:TOOLTIP_BODY_MAX_LENGTH]}"


class ActivityTimeline(QFrame):
    """Scrollable read-only activity log for a task."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ActivityTimeline")
        header = QLabel("Activity")
        header.setProperty("class", "eyebrow")
        self._list = QListWidget()
        self._list.setObjectName("TimelineList")
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(header)
        layout.addWidget(self._list, 1)

    def set_entries(self, entries: list[str]) -> None:
        self._list.clear()
        if not entries:
            item = QListWidgetItem("No activity yet")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._list.addItem(item)
            return
        for entry in entries:
            item = QListWidgetItem(entry)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._list.addItem(item)


class TaskSectionPanel(QFrame):
    """Reusable section shell for inbox and quadrants."""

    task_selected = Signal(str)
    task_dropped = Signal(str, str)
    title_edited = Signal(str, str)
    create_requested = Signal(str)

    def __init__(self, section_key: str, title: str, subtitle: str) -> None:
        super().__init__()
        self.setObjectName("Panel")
        self._title = title
        self._section_key = section_key
        eyebrow = QLabel(subtitle)
        eyebrow.setProperty("class", "eyebrow")
        self._header = QLabel(title)
        self._header.setProperty("class", "sectionTitle")
        self._meta = QLabel("")
        self._meta.setProperty("class", "muted")
        add_button = QPushButton("+")
        add_button.setObjectName("SectionAddButton")
        add_button.clicked.connect(lambda: self.create_requested.emit(self._section_key))
        self._list = TaskListWidget(section_key)
        self._list.task_selected.connect(self.task_selected.emit)
        self._list.task_dropped.connect(self.task_dropped.emit)
        self._list.title_edited.connect(self.title_edited.emit)

        header_row = QHBoxLayout()
        header_row.addWidget(self._header)
        header_row.addStretch(1)
        header_row.addWidget(add_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(eyebrow)
        layout.addLayout(header_row)
        layout.addWidget(self._meta)
        layout.addWidget(self._list, 1)

    def refresh(self, tasks: list[Task], selected_id: str) -> None:
        self._header.setText(self._title)
        count_text = f"{len(tasks)} task{'s' if len(tasks) != 1 else ''}"
        self._meta.setText(count_text)
        self._list.refresh(tasks, selected_id)

    def focus_list(self) -> None:
        self._list.focus_list()


class FilterBar(QFrame):
    """Search and filter controls shared by the main window."""

    query_changed = Signal(str)
    status_changed = Signal(object)
    sort_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Panel")
        eyebrow = QLabel("Flow")
        eyebrow.setProperty("class", "eyebrow")
        title = QLabel("Search, filter, sort")
        title.setProperty("class", "sectionTitle")

        self._query = QLineEdit()
        self._query.setClearButtonEnabled(True)
        self._query.setPlaceholderText("Search tasks, notes, and due context")
        self._query.textChanged.connect(self.query_changed.emit)

        self._status = QComboBox()
        for status in TaskStatusFilter:
            self._status.addItem(status.label, status)
        self._status.currentIndexChanged.connect(
            lambda: self.status_changed.emit(self._status.currentData())
        )

        self._sort = QComboBox()
        for sort in TaskSortMode:
            self._sort.addItem(sort.label, sort)
        self._sort.currentIndexChanged.connect(
            lambda: self.sort_changed.emit(self._sort.currentData())
        )

        self._summary = QLabel("0 visible")
        self._summary.setProperty("class", "muted")

        layout = QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        layout.addWidget(eyebrow, 0, 0, 1, 4)
        layout.addWidget(title, 1, 0, 1, 4)
        layout.addWidget(self._query, 2, 0, 1, 2)
        layout.addWidget(self._status, 2, 2)
        layout.addWidget(self._sort, 2, 3)
        layout.addWidget(self._summary, 3, 0, 1, 4)

    def sync(
        self,
        view_state: TaskViewState,
        counts: dict[TaskStatusFilter, int],
        visible_count: int,
    ) -> None:
        query_blocker = QSignalBlocker(self._query)
        status_blocker = QSignalBlocker(self._status)
        sort_blocker = QSignalBlocker(self._sort)
        self._query.setText(view_state.query)
        self._status.setCurrentIndex(max(self._status.findData(view_state.status), 0))
        self._sort.setCurrentIndex(max(self._sort.findData(view_state.sort), 0))
        total = counts[TaskStatusFilter.ALL]
        today = counts[TaskStatusFilter.TODAY]
        self._summary.setText(
            f"{visible_count} visible · {counts[TaskStatusFilter.ACTIVE]} active · "
            f"{counts[TaskStatusFilter.COMPLETED]} completed · "
            f"{counts[TaskStatusFilter.ARCHIVED]} archived · "
            f"{today} due today · "
            f"{total} total"
        )
        del query_blocker
        del status_blocker
        del sort_blocker

    def focus_search(self) -> None:
        self._query.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._query.selectAll()


class TaskEditorPanel(QFrame):
    """Task detail/editor shell with live markdown preview."""

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

        archive_button = QPushButton("Archive")
        archive_button.clicked.connect(lambda: self.archive_requested.emit(True))
        restore_button = QPushButton("Restore")
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

        self._history = ActivityTimeline()

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

    def focus_title(self) -> None:
        self._title_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._title_edit.selectAll()

    def populate(self, task: Task | None, history: list[str]) -> None:
        self._loading = True
        self._current_task_id = task.id if task else ""
        self._set_enabled(task is not None)
        if task is None:
            self._title_edit.clear()
            self._body_edit.clear()
            self._preview.clear()
            self._history.set_entries([])
            self._loading = False
            return

        self._title_edit.setText(task.title)
        self._body_edit.setMarkdown(task.content_markdown)
        self._preview.setMarkdown(sanitize_markdown(task.content_markdown))
        self._inbox_check.setChecked(task.inbox)
        self._completed_check.setChecked(task.is_completed)
        self._due_check.setChecked(task.due_at is not None)
        self._due_edit.setEnabled(task.due_at is not None)
        self._due_edit.setDateTime(self._to_qdatetime(task.due_at or datetime.now(tz=UTC)))
        quadrant_index = 0
        if task.quadrant is not None:
            quadrant_index = self._quadrant_combo.findData(task.quadrant)
        self._quadrant_combo.setCurrentIndex(max(quadrant_index, 0))
        self._quadrant_combo.setEnabled(not task.inbox)
        self._history.set_entries(history[:RECENT_HISTORY_PREVIEW_COUNT])
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
        self._preview.setMarkdown(sanitize_markdown(self._body_edit.toMarkdown()))

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
        return datetime.fromtimestamp(qdatetime.toSecsSinceEpoch(), tz=UTC)

    def _to_qdatetime(self, value: datetime) -> QDateTime:
        return QDateTime.fromSecsSinceEpoch(int(value.timestamp()), Qt.TimeSpec.UTC).toLocalTime()


class CommandPaletteDialog(QDialog):
    """Small command palette foundation for keyboard-first actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.resize(560, 440)
        self._commands: list[PaletteCommand] = []

        eyebrow = QLabel("Commands")
        eyebrow.setProperty("class", "eyebrow")
        title = QLabel("Command palette")
        title.setProperty("class", "sectionTitle")

        self._query = QLineEdit()
        self._query.setPlaceholderText("Type a command…")
        self._query.setClearButtonEnabled(True)
        self._query.textChanged.connect(self._refresh_list)
        self._query.installEventFilter(self)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _: self.accept())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(self._query)
        layout.addWidget(self._list, 1)

    def set_commands(self, commands: list[PaletteCommand]) -> None:
        self._commands = commands
        self._refresh_list()

    def selected_command(self) -> str:
        item = self._list.currentItem()
        if item is None:
            return ""
        command_id = item.data(ITEM_IDENTIFIER_ROLE)
        return command_id if isinstance(command_id, str) else ""

    def open_with_focus(self) -> int:
        self._query.clear()
        self._refresh_list()
        self._query.setFocus(Qt.FocusReason.ShortcutFocusReason)
        return self.exec()

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._query and isinstance(event, QKeyEvent):
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._navigate_list(1)
                return True
            elif key == Qt.Key.Key_Up:
                self._navigate_list(-1)
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._list.count() > 0:
                    self.accept()
                return True
        return bool(super().eventFilter(watched, event))

    def _navigate_list(self, delta: int) -> None:
        count = self._list.count()
        if count == 0:
            return
        current = self._list.currentRow()
        next_row = max(0, min(count - 1, current + delta))
        self._list.setCurrentRow(next_row)

    def _refresh_list(self) -> None:
        query = self._query.text().strip().casefold()
        self._list.clear()
        for command in self._commands:
            if query and query not in command.search_text:
                continue
            label = command.title
            if command.shortcut:
                label = f"{command.title}  [{command.shortcut}]"
            item = QListWidgetItem(label)
            item.setData(ITEM_IDENTIFIER_ROLE, command.identifier)
            item.setToolTip(command.subtitle)
            font = QFont(item.font())
            font.setBold(True)
            item.setFont(font)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
