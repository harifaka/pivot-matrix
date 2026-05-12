"""Application state and orchestration."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from pivot.constants import BOARD_SECTION_ORDER
from pivot.domain.models import Quadrant, Task, TaskDocument

if TYPE_CHECKING:
    from pivot.persistence.json_store import JsonDataStore

logger = logging.getLogger(__name__)

SectionTasks = dict[str, list[Task]]


class TaskStatusFilter(StrEnum):
    """Task visibility filters."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    ALL = "all"

    @property
    def label(self) -> str:
        return {
            TaskStatusFilter.ACTIVE: "Active",
            TaskStatusFilter.COMPLETED: "Completed",
            TaskStatusFilter.ARCHIVED: "Archived",
            TaskStatusFilter.ALL: "All tasks",
        }[self]


class TaskSortMode(StrEnum):
    """Sorting options for visible tasks."""

    UPDATED = "updated"
    DUE = "due"
    CREATED = "created"
    TITLE = "title"

    @property
    def label(self) -> str:
        return {
            TaskSortMode.UPDATED: "Recently updated",
            TaskSortMode.DUE: "Due date",
            TaskSortMode.CREATED: "Recently created",
            TaskSortMode.TITLE: "Title",
        }[self]


@dataclass(slots=True, frozen=True)
class TaskViewState:
    """Lightweight view state shared across widgets."""

    query: str = ""
    status: TaskStatusFilter = TaskStatusFilter.ACTIVE
    sort: TaskSortMode = TaskSortMode.UPDATED


class AppState(QObject):
    """Central application state separate from the Qt widget tree."""

    document_changed = Signal()
    selection_changed = Signal(str)
    status_changed = Signal(str)
    save_state_changed = Signal(bool)
    filters_changed = Signal()

    def __init__(self, store: JsonDataStore) -> None:
        super().__init__()
        self._store = store
        self._document = TaskDocument.empty()
        self._selected_task_id = ""
        self._dirty = False
        self._view = TaskViewState()

    @property
    def selected_task_id(self) -> str:
        return self._selected_task_id

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def view(self) -> TaskViewState:
        return self._view

    @property
    def tasks(self) -> list[Task]:
        return list(self._document.tasks)

    def load(self) -> None:
        self._document = self._store.load()
        self._dirty = False
        self.save_state_changed.emit(False)
        self._sync_selection()
        self.document_changed.emit()
        self.filters_changed.emit()
        self.status_changed.emit("Ready")

    def save_now(self) -> None:
        self._store.save(self._document)
        self._dirty = False
        self.save_state_changed.emit(False)
        self.status_changed.emit("Saved")

    def create_task(
        self,
        *,
        title: str = "",
        quadrant: Quadrant | None = None,
        inbox: bool = True,
    ) -> Task:
        task = Task.create(title=title, quadrant=quadrant, inbox=inbox)
        self._document.tasks.insert(0, task)
        self._sync_selection(task.id)
        self._mark_dirty(f"Created {task.display_title}")
        return task

    def select_task(self, task_id: str) -> None:
        if task_id == self._selected_task_id:
            return
        self._selected_task_id = task_id
        self.selection_changed.emit(task_id)

    def selected_task(self) -> Task | None:
        return self.get_task(self._selected_task_id)

    def get_task(self, task_id: str) -> Task | None:
        for task in self._document.tasks:
            if task.id == task_id:
                return task
        return None

    def update_task(
        self,
        task_id: str,
        *,
        title: str,
        content_markdown: str,
        due_at: datetime | None,
        inbox: bool,
        quadrant: Quadrant | None,
    ) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        action = "updated"
        next_section = "inbox" if inbox else (quadrant or task.quadrant or Quadrant.DO).value
        if task.section_key != next_section:
            action = f"moved to {next_section}"
        if task.apply_updates(
            title=title,
            content_markdown=content_markdown,
            due_at=due_at,
            inbox=inbox,
            quadrant=quadrant,
            action=action,
        ):
            self._sync_selection(task.id)
            self._mark_dirty(f"Updated {task.display_title}")

    def rename_task(self, task_id: str, title: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        if task.apply_updates(
            title=title,
            content_markdown=task.content_markdown,
            due_at=task.due_at,
            inbox=task.inbox,
            quadrant=task.quadrant,
            action="retitled",
        ):
            self._mark_dirty(f"Retitled {task.display_title}")

    def move_task_to_section(self, task_id: str, section: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        if section == "inbox":
            changed = task.apply_updates(
                title=task.title,
                content_markdown=task.content_markdown,
                due_at=task.due_at,
                inbox=True,
                quadrant=None,
                action="moved to inbox",
            )
        else:
            changed = task.apply_updates(
                title=task.title,
                content_markdown=task.content_markdown,
                due_at=task.due_at,
                inbox=False,
                quadrant=Quadrant(section),
                action=f"moved to {section}",
            )
        if changed:
            self._sync_selection(task.id)
            self._mark_dirty(f"Moved {task.display_title}")

    def set_task_completed(self, task_id: str, completed: bool) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        if task.set_completed(completed):
            self._sync_selection(task.id)
            state = "Completed" if completed else "Reopened"
            self._mark_dirty(f"{state} {task.display_title}")

    def archive_task(self, task_id: str, archived: bool = True) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        if task.set_archived(archived):
            self._sync_selection(task.id)
            state = "Archived" if archived else "Restored"
            self._mark_dirty(f"{state} {task.display_title}")

    def set_search_query(self, query: str) -> None:
        normalized = query.strip()
        if normalized == self._view.query:
            return
        self._view = TaskViewState(query=normalized, status=self._view.status, sort=self._view.sort)
        self._sync_selection()
        self.filters_changed.emit()
        self.document_changed.emit()

    def set_status_filter(self, status: TaskStatusFilter) -> None:
        if status == self._view.status:
            return
        self._view = TaskViewState(query=self._view.query, status=status, sort=self._view.sort)
        self._sync_selection()
        self.filters_changed.emit()
        self.document_changed.emit()

    def set_sort_mode(self, sort: TaskSortMode) -> None:
        if sort == self._view.sort:
            return
        self._view = TaskViewState(query=self._view.query, status=self._view.status, sort=sort)
        self._sync_selection()
        self.filters_changed.emit()
        self.document_changed.emit()

    def clear_filters(self) -> None:
        if self._view == TaskViewState():
            return
        self._view = TaskViewState()
        self._sync_selection()
        self.filters_changed.emit()
        self.document_changed.emit()

    def visible_tasks(self) -> list[Task]:
        tasks = [task for task in self._document.tasks if self._matches_view(task)]
        return sorted(tasks, key=self._sort_key)

    def board_sections(self) -> SectionTasks:
        sections: SectionTasks = defaultdict(list)
        for task in self.visible_tasks():
            sections[task.section_key].append(task)
        return {section: sections.get(section, []) for section in BOARD_SECTION_ORDER}

    def counts_by_status(self) -> dict[TaskStatusFilter, int]:
        return {
            TaskStatusFilter.ACTIVE: sum(
                1 for task in self._document.tasks if not task.archived and not task.is_completed
            ),
            TaskStatusFilter.COMPLETED: sum(
                1 for task in self._document.tasks if not task.archived and task.is_completed
            ),
            TaskStatusFilter.ARCHIVED: sum(1 for task in self._document.tasks if task.archived),
            TaskStatusFilter.ALL: len(self._document.tasks),
        }

    def history_for(self, task_id: str) -> list[str]:
        task = self.get_task(task_id)
        if task is None:
            return []
        return [
            f"{entry.timestamp.astimezone(UTC).strftime('%Y-%m-%d %H:%M')} · {entry.action}"
            for entry in reversed(task.history)
        ]

    def _matches_view(self, task: Task) -> bool:
        if not task.matches_query(self._view.query):
            return False
        if self._view.status is TaskStatusFilter.ACTIVE:
            return not task.archived and not task.is_completed
        if self._view.status is TaskStatusFilter.COMPLETED:
            return not task.archived and task.is_completed
        if self._view.status is TaskStatusFilter.ARCHIVED:
            return task.archived
        return True

    def _sort_key(self, task: Task) -> tuple[object, ...]:
        max_due = datetime.max.replace(tzinfo=UTC)
        if self._view.sort is TaskSortMode.DUE:
            due = task.due_at or max_due
            return (due, task.display_title.casefold(), -task.updated_at.timestamp())
        if self._view.sort is TaskSortMode.CREATED:
            return (
                -task.created_at.timestamp(),
                -task.updated_at.timestamp(),
                task.display_title.casefold(),
            )
        if self._view.sort is TaskSortMode.TITLE:
            return (
                task.display_title.casefold(),
                task.due_at or max_due,
                -task.updated_at.timestamp(),
            )
        return (-task.updated_at.timestamp(), task.due_at or max_due, task.display_title.casefold())

    def _sync_selection(self, preferred_task_id: str = "") -> None:
        visible = self.visible_tasks()
        visible_ids = {task.id for task in visible}
        next_task_id = ""
        for candidate in (preferred_task_id, self._selected_task_id):
            if candidate and candidate in visible_ids:
                next_task_id = candidate
                break
        if not next_task_id and visible:
            next_task_id = visible[0].id
        if next_task_id == self._selected_task_id:
            return
        self._selected_task_id = next_task_id
        self.selection_changed.emit(next_task_id)

    def _mark_dirty(self, message: str) -> None:
        self._dirty = True
        self.document_changed.emit()
        self.save_state_changed.emit(True)
        self.status_changed.emit(message)
        logger.info(message)
