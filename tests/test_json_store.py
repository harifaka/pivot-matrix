from __future__ import annotations

from pathlib import Path

from pivot.constants import MAX_BACKUP_SNAPSHOTS
from pivot.domain.models import Quadrant, Task, TaskDocument
from pivot.persistence.json_store import JsonDataStore


def test_json_store_roundtrip(tmp_path: Path) -> None:
    store = JsonDataStore(tmp_path / "tasks.json")
    document = TaskDocument(
        tasks=[Task.create(title="Write README", quadrant=Quadrant.DO, inbox=False)]
    )

    store.save(document)
    loaded = store.load()

    assert loaded.schema_version == document.schema_version
    assert len(loaded.tasks) == 1
    assert loaded.tasks[0].display_title == "Write README"
    assert loaded.tasks[0].quadrant is Quadrant.DO


def test_json_store_creates_empty_document(tmp_path: Path) -> None:
    store = JsonDataStore(tmp_path / "missing.json")

    document = store.load()

    assert document.tasks == []


def test_json_store_recovers_from_corrupted_primary_json(tmp_path: Path) -> None:
    store = JsonDataStore(tmp_path / "tasks.json")
    original = TaskDocument(tasks=[Task.create(title="Recover me", inbox=True)])
    store.save(original)
    store.file_path.write_text("{corrupted", encoding="utf-8")

    loaded = store.load()

    assert len(loaded.tasks) == 1
    assert loaded.tasks[0].display_title == "Recover me"


def test_json_store_prunes_backup_snapshots(tmp_path: Path) -> None:
    store = JsonDataStore(tmp_path / "tasks.json")
    for index in range(MAX_BACKUP_SNAPSHOTS + 4):
        document = TaskDocument(tasks=[Task.create(title=f"Task {index}")])
        store.save(document)

    backups = sorted(store.backup_dir.glob("tasks-*.json")) if store.backup_dir else []
    assert len(backups) <= MAX_BACKUP_SNAPSHOTS
