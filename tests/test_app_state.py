from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pivot.application.state import AppState, TaskSortMode, TaskStatusFilter
from pivot.domain.models import Quadrant, Task, TaskDocument
from pivot.persistence.json_store import JsonDataStore


def build_state(tmp_path: Path, tasks: list[Task]) -> AppState:
    store = JsonDataStore(tmp_path / "tasks.json")
    store.save(TaskDocument(tasks=tasks))
    state = AppState(store)
    state.load()
    return state


def test_app_state_filters_and_search_visible_tasks(tmp_path: Path) -> None:
    active = Task.create(title="Focus roadmap", quadrant=Quadrant.DO, inbox=False)
    completed = Task.create(title="Ship notes", quadrant=Quadrant.SCHEDULE, inbox=False)
    completed.set_completed(True)
    archived = Task.create(title="Old draft")
    archived.set_archived(True)

    state = build_state(tmp_path, [active, completed, archived])

    assert [task.id for task in state.visible_tasks()] == [active.id]

    state.set_status_filter(TaskStatusFilter.COMPLETED)
    assert [task.id for task in state.visible_tasks()] == [completed.id]

    state.set_status_filter(TaskStatusFilter.ARCHIVED)
    assert [task.id for task in state.visible_tasks()] == [archived.id]

    state.set_status_filter(TaskStatusFilter.ALL)
    state.set_search_query("focus road")
    assert [task.id for task in state.visible_tasks()] == [active.id]


def test_app_state_sort_mode_and_board_section_moves(tmp_path: Path) -> None:
    later_due = Task.create(title="Later", quadrant=Quadrant.DO, inbox=False)
    later_due.apply_updates(
        title=later_due.title,
        content_markdown="",
        due_at=datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
        inbox=False,
        quadrant=Quadrant.DO,
    )
    sooner_due = Task.create(title="Sooner", quadrant=Quadrant.DO, inbox=False)
    sooner_due.apply_updates(
        title=sooner_due.title,
        content_markdown="",
        due_at=datetime(2026, 5, 13, 9, 0, tzinfo=UTC),
        inbox=False,
        quadrant=Quadrant.DO,
    )

    state = build_state(tmp_path, [later_due, sooner_due])
    state.set_status_filter(TaskStatusFilter.ALL)
    state.set_sort_mode(TaskSortMode.DUE)

    do_section = state.board_sections()["do"]
    assert [task.id for task in do_section] == [sooner_due.id, later_due.id]

    state.move_task_to_section(sooner_due.id, "delegate")
    moved = state.get_task(sooner_due.id)
    assert moved is not None
    assert moved.section_key == "delegate"
    assert sooner_due.id in [task.id for task in state.board_sections()["delegate"]]


def test_app_state_retitles_and_reselects_when_filtered_out(tmp_path: Path) -> None:
    first = Task.create(title="First")
    second = Task.create(title="Second")

    state = build_state(tmp_path, [first, second])
    state.select_task(first.id)
    assert state.selected_task_id == first.id

    state.rename_task(first.id, "Inbox zero")
    renamed = state.get_task(first.id)
    assert renamed is not None
    assert renamed.title == "Inbox zero"

    state.archive_task(first.id, True)
    assert state.selected_task_id == second.id
