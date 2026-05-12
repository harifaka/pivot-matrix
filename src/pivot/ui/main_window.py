"""Main application window."""

from __future__ import annotations

from functools import partial
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QMainWindow,
    QPushButton,
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
    InboxOverlay,
    PaletteCommand,
    SearchFilterDialog,
    TaskEditorDialog,
    TaskSectionPanel,
)


class MainWindow(QMainWindow):
    """Primary desktop shell for Pivot."""

    def __init__(self, state: AppState, user_config: UserConfig) -> None:
        super().__init__()
        self._state = state
        self._user_config = user_config
        self._tray_enabled = user_config.tray_enabled
        self._minimize_to_tray = user_config.minimize_to_tray
        self._allow_close = False
        self._focus_mode = False
        self.setWindowTitle("Pivot")
        self.setMinimumSize(*WINDOW_MINIMUM_SIZE)
        self.resize(user_config.window.width, user_config.window.height)

        self._panels = {
            "do": TaskSectionPanel("do", "Do", "Urgent + important"),
            "schedule": TaskSectionPanel("schedule", "Schedule", "Important, not urgent"),
            "delegate": TaskSectionPanel("delegate", "Delegate", "Urgent, not important"),
            "eliminate": TaskSectionPanel("eliminate", "Eliminate", "Not urgent, not important"),
        }

        # Dialogs and overlay — created before layout so they can be wired up
        self._editor_dialog = TaskEditorDialog(parent=self)
        self._search_dialog = SearchFilterDialog(parent=self)
        self._palette = CommandPaletteDialog(self)
        self._inbox_overlay: InboxOverlay  # assigned in _build_layout
        self._inbox_btn: QPushButton  # assigned in _build_toolbar

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

    def configure_tray_behavior(self, *, enabled: bool, minimize_to_tray: bool) -> None:
        self._tray_enabled = enabled
        self._minimize_to_tray = minimize_to_tray

    def request_exit(self) -> None:
        self._allow_close = True
        self.close()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Commands", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        new_action = QAction("New Task", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._create_inbox_task)
        toolbar.addAction(new_action)

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._state.save_now)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        # Inbox toggle button with live task count badge
        self._inbox_btn = QPushButton("📥  Inbox  (0)")
        self._inbox_btn.setObjectName("PrimaryButton")
        self._inbox_btn.setCheckable(True)
        self._inbox_btn.setToolTip("Toggle inbox overlay  [Ctrl+1]")
        self._inbox_btn.toggled.connect(self._on_inbox_btn_toggled)
        toolbar.addWidget(self._inbox_btn)

        # Search button
        search_btn = QPushButton("🔍  Search")
        search_btn.setToolTip("Open search & filter dialog  [Ctrl+F]")
        search_btn.clicked.connect(self._open_search)
        toolbar.addWidget(search_btn)

        # Task editor toggle button
        editor_btn = QPushButton("✏️  Details")
        editor_btn.setToolTip("Open task detail editor  [Ctrl+E]")
        editor_btn.clicked.connect(self._toggle_editor_dialog)
        toolbar.addWidget(editor_btn)

        toolbar.addSeparator()

        palette_action = QAction("Commands  [Ctrl+K]", self)
        palette_action.setShortcut(QKeySequence("Ctrl+K"))
        palette_action.triggered.connect(self._open_command_palette)
        toolbar.addAction(palette_action)

    def _build_layout(self) -> None:
        shell = QWidget()
        shell.installEventFilter(self)

        quadrant_grid = QGridLayout()
        quadrant_grid.setContentsMargins(18, 18, 18, 18)
        quadrant_grid.setSpacing(16)
        quadrant_grid.addWidget(self._panels["do"], 0, 0)
        quadrant_grid.addWidget(self._panels["schedule"], 0, 1)
        quadrant_grid.addWidget(self._panels["delegate"], 1, 0)
        quadrant_grid.addWidget(self._panels["eliminate"], 1, 1)

        root_layout = QVBoxLayout(shell)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addLayout(quadrant_grid, 1)

        # Inbox overlay is a free-floating child of the shell (not in any layout)
        self._inbox_overlay = InboxOverlay(parent=shell)
        self._inbox_overlay.hide()
        self._inbox_overlay.close_requested.connect(self._close_inbox_overlay)

        self.setCentralWidget(shell)

    def _connect_state(self) -> None:
        inbox_panel = self._inbox_overlay.section_panel
        inbox_panel.task_selected.connect(self._state.select_task)
        inbox_panel.task_dropped.connect(self._state.move_task_to_section)
        inbox_panel.title_edited.connect(self._state.rename_task)
        inbox_panel.create_requested.connect(self._create_task_for_section)

        for panel in self._panels.values():
            panel.task_selected.connect(self._state.select_task)
            panel.task_dropped.connect(self._state.move_task_to_section)
            panel.title_edited.connect(self._state.rename_task)
            panel.create_requested.connect(self._create_task_for_section)

        self._search_dialog.query_changed.connect(self._state.set_search_query)
        self._search_dialog.status_changed.connect(self._handle_status_filter)
        self._search_dialog.sort_changed.connect(self._handle_sort_mode)

        self._editor_dialog.payload_changed.connect(self._apply_editor_payload)
        self._editor_dialog.archive_requested.connect(self._archive_selected)

        self._state.document_changed.connect(self.refresh)
        self._state.selection_changed.connect(self._sync_selection)
        self._state.filters_changed.connect(self.refresh)
        self._state.status_changed.connect(self._status.showMessage)
        self._state.save_state_changed.connect(self._update_window_title)

    def _setup_shortcuts(self) -> None:
        bindings: list[tuple[str, Any]] = [
            ("Ctrl+1", self._toggle_inbox_overlay_shortcut),
            ("Ctrl+2", self._panels["do"].focus_list),
            ("Ctrl+3", self._panels["schedule"].focus_list),
            ("Ctrl+4", self._panels["delegate"].focus_list),
            ("Ctrl+5", self._panels["eliminate"].focus_list),
            ("Ctrl+F", self._open_search),
            ("Ctrl+L", self._open_search),
            ("Ctrl+E", self._toggle_editor_dialog),
            ("Ctrl+.", self._toggle_focus_mode),
            ("Ctrl+Return", self._toggle_selected_completed),
            ("Ctrl+Backspace", lambda: self._archive_selected(True)),
            ("Ctrl+Shift+Backspace", lambda: self._archive_selected(False)),
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
            shortcut.activated.connect(partial(self._move_selected, section))
            self._shortcuts.append(shortcut)

    # ------------------------------------------------------------------
    # State refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        sections = self._state.board_sections()
        selected_id = self._state.selected_task_id

        for key, panel in self._panels.items():
            panel.refresh(sections.get(key, []), selected_id)

        inbox_tasks = sections.get("inbox", [])
        self._inbox_overlay.refresh(inbox_tasks, selected_id)
        self._inbox_btn.setText(f"📥  Inbox  ({len(inbox_tasks)})")

        if self._search_dialog.isVisible():
            self._search_dialog.sync(
                self._state.view,
                self._state.counts_by_status(),
                len(self._state.visible_tasks()),
            )

        if self._editor_dialog.isVisible():
            task = self._state.selected_task()
            history = self._state.history_for(selected_id) if selected_id else []
            self._editor_dialog.populate(task, history)

        self._update_window_title(self._state.is_dirty)

    def _sync_selection(self, task_id: str) -> None:
        task = self._state.get_task(task_id)
        history = self._state.history_for(task_id)
        self._editor_dialog.populate(task, history)
        self.refresh()

    # ------------------------------------------------------------------
    # Editor payload
    # ------------------------------------------------------------------

    def _apply_editor_payload(self, payload: Any) -> None:
        if not isinstance(payload, EditorPayload):
            return
        task_id = self._editor_dialog.current_task_id()
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

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def _create_inbox_task(self) -> None:
        self._state.create_task()
        # Reveal inbox overlay so the new task is visible
        if not self._inbox_overlay.isVisible():
            self._inbox_btn.setChecked(True)
        QTimer.singleShot(0, self._editor_dialog.focus_title)

    def _create_task_for_section(self, section: str) -> None:
        if section == "inbox":
            self._create_inbox_task()
            return
        self._state.create_task(quadrant=Quadrant(section), inbox=False)
        QTimer.singleShot(0, self._editor_dialog.focus_title)

    # ------------------------------------------------------------------
    # Inbox overlay
    # ------------------------------------------------------------------

    def _on_inbox_btn_toggled(self, checked: bool) -> None:
        if checked:
            self._inbox_overlay.show()
            self._reposition_inbox_overlay()
            self._inbox_overlay.raise_()
            self._inbox_overlay.focus_list()
        else:
            self._inbox_overlay.hide()

    def _toggle_inbox_overlay_shortcut(self) -> None:
        self._inbox_btn.setChecked(not self._inbox_btn.isChecked())

    def _close_inbox_overlay(self) -> None:
        self._inbox_btn.setChecked(False)

    def _reposition_inbox_overlay(self) -> None:
        shell = self.centralWidget()
        if shell is None:
            return
        margin = 12
        width = 340
        height = max(shell.height() - 2 * margin, 200)
        self._inbox_overlay.setGeometry(margin, margin, width, height)

    # ------------------------------------------------------------------
    # Search dialog
    # ------------------------------------------------------------------

    def _open_search(self) -> None:
        self._search_dialog.sync(
            self._state.view,
            self._state.counts_by_status(),
            len(self._state.visible_tasks()),
        )
        self._search_dialog.focus_search()

    # ------------------------------------------------------------------
    # Editor dialog toggle
    # ------------------------------------------------------------------

    def _toggle_editor_dialog(self) -> None:
        if self._editor_dialog.isVisible():
            self._editor_dialog.hide()
        else:
            task = self._state.selected_task()
            if task:
                self._editor_dialog.populate(
                    task, self._state.history_for(task.id)
                )
            else:
                self._editor_dialog.show()

    # ------------------------------------------------------------------
    # Filter / sort handlers
    # ------------------------------------------------------------------

    def _handle_status_filter(self, value: object) -> None:
        if isinstance(value, TaskStatusFilter):
            self._state.set_status_filter(value)

    def _handle_sort_mode(self, value: object) -> None:
        if isinstance(value, TaskSortMode):
            self._state.set_sort_mode(value)

    # ------------------------------------------------------------------
    # Task actions
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Focus mode (toolbar-hiding distraction-free view)
    # ------------------------------------------------------------------

    def _toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        toolbar = self.findChild(QToolBar)
        if toolbar:
            toolbar.setVisible(not self._focus_mode)
        if self._focus_mode:
            self._status.showMessage("Focus mode — press Ctrl+. to return to normal")
        else:
            self._status.showMessage("Board view")

    # ------------------------------------------------------------------
    # Command palette
    # ------------------------------------------------------------------

    def _open_command_palette(self) -> None:
        self._palette.set_commands(self._palette_commands())
        if self._palette.open_with_focus() != int(QDialog.DialogCode.Accepted):
            return
        command_id = self._palette.selected_command()
        if command_id:
            self._execute_palette_command(command_id)

    def _palette_commands(self) -> list[PaletteCommand]:
        return [
            PaletteCommand(
                "new:inbox", "New inbox task", "Capture a task into the inbox", "Ctrl+N"
            ),
            PaletteCommand(
                "new:do", "New do task", "Create directly in the Do quadrant", "Ctrl+Shift+2"
            ),
            PaletteCommand("new:schedule", "New schedule task", "Create directly in Schedule"),
            PaletteCommand("new:delegate", "New delegate task", "Create directly in Delegate"),
            PaletteCommand("new:eliminate", "New eliminate task", "Create directly in Eliminate"),
            PaletteCommand(
                "focus:search", "Search & filter", "Open the search dialog", "Ctrl+F"
            ),
            PaletteCommand("filters:clear", "Clear filters", "Reset search, status, and sort"),
            PaletteCommand(
                "mode:focus",
                "Toggle focus mode",
                "Hide toolbar — pure matrix view",
                "Ctrl+.",
            ),
            PaletteCommand(
                "editor:toggle",
                "Toggle task editor",
                "Show/hide the floating task editor",
                "Ctrl+E",
            ),
            PaletteCommand(
                "inbox:toggle",
                "Toggle inbox overlay",
                "Show/hide the inbox panel",
                "Ctrl+1",
            ),
            PaletteCommand(
                "view:today",
                "Today view",
                "Show tasks with a due date of today or earlier",
            ),
            PaletteCommand(
                "view:recent",
                "Recent changes",
                "Show all tasks sorted by most recently updated",
            ),
            PaletteCommand(
                "state:complete",
                "Toggle completed",
                "Flip the selected task state",
                "Ctrl+Enter",
            ),
            PaletteCommand(
                "state:archive",
                "Archive selected task",
                "Move selected task into archive",
                "Ctrl+Backspace",
            ),
            PaletteCommand(
                "state:restore",
                "Restore selected task",
                "Restore archived task",
                "Ctrl+Shift+Backspace",
            ),
            PaletteCommand(
                "move:inbox", "Move selected to inbox", "Keyboard move target", "Ctrl+Shift+1"
            ),
            PaletteCommand(
                "move:do", "Move selected to Do", "Keyboard move target", "Ctrl+Shift+2"
            ),
            PaletteCommand(
                "move:schedule",
                "Move selected to Schedule",
                "Keyboard move target",
                "Ctrl+Shift+3",
            ),
            PaletteCommand(
                "move:delegate",
                "Move selected to Delegate",
                "Keyboard move target",
                "Ctrl+Shift+4",
            ),
            PaletteCommand(
                "move:eliminate",
                "Move selected to Eliminate",
                "Keyboard move target",
                "Ctrl+Shift+5",
            ),
        ]

    def _execute_palette_command(self, command_id: str) -> None:
        if command_id == "new:inbox":
            self._create_inbox_task()
            return
        if command_id.startswith("new:"):
            self._create_task_for_section(command_id.split(":", maxsplit=1)[1])
            return
        if command_id == "focus:search":
            self._open_search()
            return
        if command_id == "filters:clear":
            self._state.clear_filters()
            return
        if command_id == "mode:focus":
            self._toggle_focus_mode()
            return
        if command_id == "editor:toggle":
            self._toggle_editor_dialog()
            return
        if command_id == "inbox:toggle":
            self._toggle_inbox_overlay_shortcut()
            return
        if command_id == "view:today":
            self._state.set_status_filter(TaskStatusFilter.TODAY)
            return
        if command_id == "view:recent":
            self._state.set_status_filter(TaskStatusFilter.ALL)
            self._state.set_sort_mode(TaskSortMode.UPDATED)
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

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------

    def _update_window_title(self, dirty: bool) -> None:
        marker = " •" if dirty else ""
        self.setWindowTitle(f"Pivot{marker}")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Reposition the inbox overlay whenever the shell widget is resized."""
        if event.type() == QEvent.Type.Resize and hasattr(self, "_inbox_overlay"):
            if self._inbox_overlay.isVisible():
                self._reposition_inbox_overlay()
        return False

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._tray_enabled and self._minimize_to_tray and not self._allow_close:
            self.hide()
            event.ignore()
            self._status.showMessage("Pivot is still running in the system tray.")
            return
        super().closeEvent(event)
