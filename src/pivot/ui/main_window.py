"""Main application window."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pivot.application.state import AppState, TaskSortMode, TaskStatusFilter
from pivot.config import UserConfig
from pivot.constants import WINDOW_MINIMUM_SIZE
from pivot.domain.models import Quadrant
from pivot.ui.components import (
    CommandPaletteDialog,
    EditorPayload,
    FilterBar,
    PaletteCommand,
    TaskEditorPanel,
    TaskSectionPanel,
)


class MainWindow(QMainWindow):
    """Primary desktop shell for Pivot."""

    def __init__(self, state: AppState, user_config: UserConfig) -> None:
        super().__init__()
        self._state = state
        self._user_config = user_config
        self.setWindowTitle("Pivot")
        self.setMinimumSize(*WINDOW_MINIMUM_SIZE)
        self.resize(user_config.window.width, user_config.window.height)

        self._filter_bar = FilterBar()
        self._panels = {
            "inbox": TaskSectionPanel("inbox", "Inbox", "Capture"),
            "do": TaskSectionPanel("do", "Do", "Urgent + important"),
            "schedule": TaskSectionPanel("schedule", "Schedule", "Important, not urgent"),
            "delegate": TaskSectionPanel("delegate", "Delegate", "Urgent, not important"),
            "eliminate": TaskSectionPanel("eliminate", "Eliminate", "Not urgent, not important"),
        }
        self._editor = TaskEditorPanel()
        self._palette = CommandPaletteDialog(self)
        self._shortcuts: list[QShortcut] = []
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Booting")

        self._build_toolbar()
        self._build_layout()
        self._connect_state()
        self._setup_shortcuts()
        self._palette.set_commands(self._palette_commands())
        self.refresh()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Commands", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._create_inbox_task)
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

        restore_action = QAction("Restore", self)
        restore_action.setShortcut(QKeySequence("Ctrl+Shift+Backspace"))
        restore_action.triggered.connect(lambda: self._archive_selected(False))
        toolbar.addAction(restore_action)

        palette_action = QAction("Command Palette", self)
        palette_action.setShortcut(QKeySequence("Ctrl+K"))
        palette_action.triggered.connect(self._open_command_palette)
        toolbar.addAction(palette_action)

        primary_button = QPushButton("New Task")
        primary_button.setObjectName("PrimaryButton")
        primary_button.clicked.connect(self._create_inbox_task)
        toolbar.addWidget(primary_button)

    def _build_layout(self) -> None:
        shell = QWidget()
        root_layout = QVBoxLayout(shell)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)
        root_layout.addWidget(self._filter_bar)

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
        splitter.setSizes([980, 420])

        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(shell)

    def _connect_state(self) -> None:
        for panel in self._panels.values():
            panel.task_selected.connect(self._state.select_task)
            panel.task_dropped.connect(self._state.move_task_to_section)
            panel.title_edited.connect(self._state.rename_task)
            panel.create_requested.connect(self._create_task_for_section)
        self._filter_bar.query_changed.connect(self._state.set_search_query)
        self._filter_bar.status_changed.connect(self._handle_status_filter)
        self._filter_bar.sort_changed.connect(self._handle_sort_mode)
        self._editor.payload_changed.connect(self._apply_editor_payload)
        self._editor.archive_requested.connect(self._archive_selected)
        self._state.document_changed.connect(self.refresh)
        self._state.selection_changed.connect(self._sync_selection)
        self._state.filters_changed.connect(self.refresh)
        self._state.status_changed.connect(self._status.showMessage)
        self._state.save_state_changed.connect(self._update_window_title)

    def _setup_shortcuts(self) -> None:
        bindings = [
            ("Ctrl+1", self._panels["inbox"].focus_list),
            ("Ctrl+2", self._panels["do"].focus_list),
            ("Ctrl+3", self._panels["schedule"].focus_list),
            ("Ctrl+4", self._panels["delegate"].focus_list),
            ("Ctrl+5", self._panels["eliminate"].focus_list),
            ("Ctrl+F", self._filter_bar.focus_search),
            ("Ctrl+L", self._filter_bar.focus_search),
        ]
        for sequence, callback in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

        move_bindings = [
            ("Ctrl+Shift+1", "inbox"),
            ("Ctrl+Shift+2", "do"),
            ("Ctrl+Shift+3", "schedule"),
            ("Ctrl+Shift+4", "delegate"),
            ("Ctrl+Shift+5", "eliminate"),
        ]
        for sequence, section in move_bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(lambda section_key=section: self._move_selected(section_key))
            self._shortcuts.append(shortcut)

    def refresh(self) -> None:
        sections = self._state.board_sections()
        selected_id = self._state.selected_task_id
        for key, panel in self._panels.items():
            panel.refresh(sections.get(key, []), selected_id)
        self._filter_bar.sync(
            self._state.view,
            self._state.counts_by_status(),
            len(self._state.visible_tasks()),
        )
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

    def _create_inbox_task(self) -> None:
        self._state.create_task()
        QTimer.singleShot(0, self._editor.focus_title)

    def _create_task_for_section(self, section: str) -> None:
        if section == "inbox":
            self._create_inbox_task()
            return
        self._state.create_task(quadrant=Quadrant(section), inbox=False)
        QTimer.singleShot(0, self._editor.focus_title)

    def _handle_status_filter(self, value: object) -> None:
        if isinstance(value, TaskStatusFilter):
            self._state.set_status_filter(value)

    def _handle_sort_mode(self, value: object) -> None:
        if isinstance(value, TaskSortMode):
            self._state.set_sort_mode(value)

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

    def _move_selected(self, section: str) -> None:
        task = self._state.selected_task()
        if task is None:
            return
        self._state.move_task_to_section(task.id, section)

    def _open_command_palette(self) -> None:
        self._palette.set_commands(self._palette_commands())
        if self._palette.open_with_focus() != int(self._palette.DialogCode.Accepted):
            return
        command_id = self._palette.selected_command()
        if command_id:
            self._execute_palette_command(command_id)

    def _palette_commands(self) -> list[PaletteCommand]:
        return [
            PaletteCommand("new:inbox", "New inbox task", "Capture a task into the inbox", "Ctrl+N"),
            PaletteCommand("new:do", "New do task", "Create directly in the Do quadrant", "Ctrl+Shift+2"),
            PaletteCommand("new:schedule", "New schedule task", "Create directly in Schedule"),
            PaletteCommand("new:delegate", "New delegate task", "Create directly in Delegate"),
            PaletteCommand("new:eliminate", "New eliminate task", "Create directly in Eliminate"),
            PaletteCommand("focus:search", "Focus search", "Jump to search/filter controls", "Ctrl+F"),
            PaletteCommand("filters:clear", "Clear filters", "Reset search, status, and sort"),
            PaletteCommand("state:complete", "Toggle completed", "Flip the selected task state", "Ctrl+Enter"),
            PaletteCommand("state:archive", "Archive selected task", "Move selected task into archive", "Ctrl+Backspace"),
            PaletteCommand("state:restore", "Restore selected task", "Restore archived task", "Ctrl+Shift+Backspace"),
            PaletteCommand("move:inbox", "Move selected to inbox", "Keyboard move target", "Ctrl+Shift+1"),
            PaletteCommand("move:do", "Move selected to Do", "Keyboard move target", "Ctrl+Shift+2"),
            PaletteCommand("move:schedule", "Move selected to Schedule", "Keyboard move target", "Ctrl+Shift+3"),
            PaletteCommand("move:delegate", "Move selected to Delegate", "Keyboard move target", "Ctrl+Shift+4"),
            PaletteCommand("move:eliminate", "Move selected to Eliminate", "Keyboard move target", "Ctrl+Shift+5"),
        ]

    def _execute_palette_command(self, command_id: str) -> None:
        if command_id == "new:inbox":
            self._create_inbox_task()
            return
        if command_id.startswith("new:"):
            self._create_task_for_section(command_id.split(":", maxsplit=1)[1])
            return
        if command_id == "focus:search":
            self._filter_bar.focus_search()
            return
        if command_id == "filters:clear":
            self._state.clear_filters()
            return
        if command_id == "state:complete":
            self._toggle_selected_completed()
            return
        if command_id == "state:archive":
            self._archive_selected(True)
            return
        if command_id == "state:restore":
            self._archive_selected(False)
            return
        if command_id.startswith("move:"):
            self._move_selected(command_id.split(":", maxsplit=1)[1])

    def _update_window_title(self, dirty: bool) -> None:
        marker = " •" if dirty else ""
        self.setWindowTitle(f"Pivot{marker}")
