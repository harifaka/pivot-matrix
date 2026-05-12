from __future__ import annotations

from datetime import UTC, datetime

from pivot.domain.models import Quadrant, Task


def test_task_create_records_initial_history() -> None:
    task = Task.create(title="Ship foundation", quadrant=Quadrant.DO, inbox=False)

    assert task.id
    assert task.quadrant is Quadrant.DO
    assert not task.inbox
    assert len(task.history) == 1
    assert task.history[0].action == "created"


def test_task_updates_keep_history() -> None:
    task = Task.create()
    due_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)

    changed = task.apply_updates(
        title="Clarify priorities",
        content_markdown="## Today\n- Focus",
        due_at=due_at,
        inbox=False,
        quadrant=Quadrant.SCHEDULE,
    )

    assert changed
    assert task.display_title == "Clarify priorities"
    assert task.due_at == due_at
    assert task.quadrant is Quadrant.SCHEDULE
    assert len(task.history) == 2
    assert task.history[-1].action == "updated"


def test_completion_toggles_timestamp() -> None:
    task = Task.create(title="Complete me")

    assert task.set_completed(True)
    assert task.completed_at is not None
    assert task.set_completed(False)
    assert task.completed_at is None
