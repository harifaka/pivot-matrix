"""Application state and orchestration."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from pivot.domain.models import Quadrant, Task, TaskDocument

if TYPE_CHECKING:
    from pivot.persistence.json_store import JsonDataStore

logger = logging.getLogger(__name__)

SectionTasks = dict[str, list[Task]]


class AppState(QObject):
    """Central application state separate from the Qt widget tree."""

    document_changed = Signal()
    selection_changed = Signal(str)
    status_changed = Signal(str)
    save_state_changed = Signal(bool)

    def __init__(self, store: "JsonDataStore") -> None:
        super().__init__()
        self._store = store
        self._document = TaskDocument.empty()
        self._selected_task_id = ""
        self._dirty = False

    @property
    def selected_task_id(self) -> str:
        return self._selected_task_id

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def tasks(self) -> list[Task]:
        return list(self._document.tasks)

    def load(self) -> None:
        self._document = self._store.load()
        self._selected_task_id = self._document.tasks[0].id if self._document.tasks else ""
        self._dirty = False
        self.document_changed.emit()
        self.selection_changed.emit(self._selected_task_id)
        self.status_changed.emit("Ready")

    def save_now(self) -> None:
        self._store.save(self._document)
        self._dirty = False
        self.save_state_changed.emit(False)
        self.status_changed.emit("Saved")

    def create_task(self, *, quadrant: Quadrant | None = None, inbox: bool = True) -> Task:
        task = Task.create(quadrant=quadrant, inbox=inbox)
        self._document.tasks.insert(0, task)
        self._mark_dirty(f"Created {task.display_title}")
        self.select_task(task.id)
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
        if task.apply_updates(
            title=title,
            content_markdown=content_markdown,
            due_at=due_at,
            inbox=inbox,
            quadrant=quadrant,
        ):
            self._mark_dirty(f"Updated {task.display_title}")

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
            )
        else:
            changed = task.apply_updates(
                title=task.title,
                content_markdown=task.content_markdown,
                due_at=task.due_at,
                inbox=False,
                quadrant=Quadrant(section),
            )
        if changed:
            self._mark_dirty(f"Moved {task.display_title}")

    def set_task_completed(self, task_id: str, completed: bool) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        if task.set_completed(completed):
            state = "Completed" if completed else "Reopened"
            self._mark_dirty(f"{state} {task.display_title}")

    def archive_task(self, task_id: str, archived: bool = True) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        if task.set_archived(archived):
            state = "Archived" if archived else "Restored"
            self._mark_dirty(f"{state} {task.display_title}")

    def board_sections(self) -> SectionTasks:
        sections: SectionTasks = defaultdict(list)
        for task in self.sorted_tasks():
            if task.archived:
                continue
            key = "inbox" if task.inbox or task.quadrant is None else task.quadrant.value
            sections[key].append(task)
        return {section: sections.get(section, []) for section in ("inbox", *[item.value for item in Quadrant])}

    def sorted_tasks(self) -> list[Task]:
        def sort_key(task: Task) -> tuple[int, int, datetime, datetime]:
            due = task.due_at or datetime.max.replace(tzinfo=task.updated_at.tzinfo)
            return (1 if task.is_completed else 0, 1 if task.inbox else 0, due, task.updated_at)

        return sorted(self._document.tasks, key=sort_key)

    def history_for(self, task_id: str) -> list[str]:
        task = self.get_task(task_id)
        if task is None:
            return []
        return [f"{entry.timestamp.isoformat()} · {entry.action}" for entry in reversed(task.history)]

    def _mark_dirty(self, message: str) -> None:
        self._dirty = True
        self.document_changed.emit()
        self.save_state_changed.emit(True)
        self.status_changed.emit(message)
        logger.info(message)
