from __future__ import annotations

from pathlib import Path

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
