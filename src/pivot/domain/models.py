"""Pure domain models for Pivot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pivot.constants import SCHEMA_VERSION


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(tz=UTC)


def datetime_to_storage(value: datetime | None) -> str | None:
    """Convert a UTC datetime into an ISO-8601 string."""

    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def datetime_from_storage(value: str | None) -> datetime | None:
    """Parse a persisted ISO-8601 datetime string."""

    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class Quadrant(StrEnum):
    """Eisenhower Matrix quadrants."""

    DO = "do"
    SCHEDULE = "schedule"
    DELEGATE = "delegate"
    ELIMINATE = "eliminate"

    @property
    def label(self) -> str:
        labels = {
            Quadrant.DO: "Do",
            Quadrant.SCHEDULE: "Schedule",
            Quadrant.DELEGATE: "Delegate",
            Quadrant.ELIMINATE: "Eliminate",
        }
        return labels[self]


@dataclass(slots=True)
class HistoryEntry:
    """An immutable history snapshot of a task change."""

    timestamp: datetime
    action: str
    snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": datetime_to_storage(self.timestamp),
            "action": self.action,
            "snapshot": self.snapshot,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> HistoryEntry:
        timestamp = datetime_from_storage(payload.get("timestamp")) or utc_now()
        snapshot = payload.get("snapshot", {})
        if not isinstance(snapshot, dict):
            snapshot = {}
        return cls(
            timestamp=timestamp,
            action=str(payload.get("action", "updated")),
            snapshot=snapshot,
        )


@dataclass(slots=True)
class Task:
    """A productivity task tracked inside the matrix."""

    id: str
    title: str
    content_markdown: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    due_at: datetime | None = None
    quadrant: Quadrant | None = None
    inbox: bool = True
    archived: bool = False
    history: list[HistoryEntry] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        title: str = "",
        content_markdown: str = "",
        quadrant: Quadrant | None = None,
        inbox: bool = True,
        due_at: datetime | None = None,
    ) -> Task:
        now = utc_now()
        task = cls(
            id=str(uuid4()),
            title=title,
            content_markdown=content_markdown,
            created_at=now,
            updated_at=now,
            due_at=due_at,
            quadrant=None if inbox else quadrant,
            inbox=inbox,
        )
        task.record_history("created")
        return task

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def display_title(self) -> str:
        stripped = self.title.strip()
        if stripped:
            return stripped
        first_line = self.content_markdown.strip().splitlines()
        if first_line:
            return first_line[0][:72]
        return "Untitled task"

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content_markdown": self.content_markdown,
            "created_at": datetime_to_storage(self.created_at),
            "updated_at": datetime_to_storage(self.updated_at),
            "completed_at": datetime_to_storage(self.completed_at),
            "due_at": datetime_to_storage(self.due_at),
            "quadrant": self.quadrant.value if self.quadrant else None,
            "inbox": self.inbox,
            "archived": self.archived,
        }

    def record_history(self, action: str) -> None:
        self.history.append(
            HistoryEntry(timestamp=utc_now(), action=action, snapshot=self.snapshot())
        )

    def touch(self, action: str = "updated") -> None:
        self.updated_at = utc_now()
        self.record_history(action)

    def apply_updates(
        self,
        *,
        title: str,
        content_markdown: str,
        due_at: datetime | None,
        inbox: bool,
        quadrant: Quadrant | None,
    ) -> bool:
        next_quadrant = None if inbox else quadrant or self.quadrant or Quadrant.DO
        changed = False
        if self.title != title:
            self.title = title
            changed = True
        if self.content_markdown != content_markdown:
            self.content_markdown = content_markdown
            changed = True
        if self.due_at != due_at:
            self.due_at = due_at
            changed = True
        if self.inbox != inbox:
            self.inbox = inbox
            changed = True
        if self.quadrant != next_quadrant:
            self.quadrant = next_quadrant
            changed = True
        if changed:
            self.touch("updated")
        return changed

    def set_completed(self, completed: bool) -> bool:
        if completed and self.completed_at is None:
            self.completed_at = utc_now()
            self.touch("completed")
            return True
        if not completed and self.completed_at is not None:
            self.completed_at = None
            self.touch("reopened")
            return True
        return False

    def set_archived(self, archived: bool) -> bool:
        if self.archived == archived:
            return False
        self.archived = archived
        self.touch("archived" if archived else "restored")
        return True

    def to_dict(self) -> dict[str, Any]:
        payload = self.snapshot()
        payload["history"] = [entry.to_dict() for entry in self.history]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Task:
        history_payload = payload.get("history", [])
        history = [
            HistoryEntry.from_dict(item) for item in history_payload if isinstance(item, dict)
        ]
        task = cls(
            id=str(payload.get("id") or uuid4()),
            title=str(payload.get("title", "")),
            content_markdown=str(payload.get("content_markdown", "")),
            created_at=datetime_from_storage(payload.get("created_at")) or utc_now(),
            updated_at=datetime_from_storage(payload.get("updated_at")) or utc_now(),
            completed_at=datetime_from_storage(payload.get("completed_at")),
            due_at=datetime_from_storage(payload.get("due_at")),
            quadrant=Quadrant(payload["quadrant"]) if payload.get("quadrant") else None,
            inbox=bool(payload.get("inbox", True)),
            archived=bool(payload.get("archived", False)),
            history=history,
        )
        if not task.history:
            task.record_history("imported")
        return task


@dataclass(slots=True)
class TaskDocument:
    """The persisted document root."""

    schema_version: int = SCHEMA_VERSION
    tasks: list[Task] = field(default_factory=list)
    saved_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        self.saved_at = utc_now()
        return {
            "schema_version": self.schema_version,
            "saved_at": datetime_to_storage(self.saved_at),
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def empty(cls) -> TaskDocument:
        return cls(schema_version=SCHEMA_VERSION, tasks=[])

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TaskDocument:
        tasks_payload = payload.get("tasks", [])
        tasks = [Task.from_dict(item) for item in tasks_payload if isinstance(item, dict)]
        return cls(
            schema_version=int(payload.get("schema_version", SCHEMA_VERSION)),
            tasks=tasks,
            saved_at=datetime_from_storage(payload.get("saved_at")) or utc_now(),
        )
