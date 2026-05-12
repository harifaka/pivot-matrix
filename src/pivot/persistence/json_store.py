"""JSON persistence engine for Pivot."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import tempfile
from typing import Any

from pivot.constants import SCHEMA_VERSION
from pivot.domain.models import TaskDocument

logger = logging.getLogger(__name__)


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when a future schema version is encountered."""


@dataclass(slots=True)
class JsonDataStore:
    """Load and save the application document as JSON."""

    file_path: Path

    def load(self) -> TaskDocument:
        if not self.file_path.exists():
            logger.info("Creating a new empty task document at %s", self.file_path)
            return TaskDocument.empty()

        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Root JSON payload must be an object")

        schema_version = int(payload.get("schema_version", SCHEMA_VERSION))
        if schema_version > SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                f"Schema version {schema_version} is newer than supported version {SCHEMA_VERSION}."
            )
        return TaskDocument.from_dict(payload)

    def save(self, document: TaskDocument) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = document.to_dict()
        encoded = json.dumps(payload, indent=2, ensure_ascii=False)

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.file_path.parent,
            prefix=f".{self.file_path.stem}-",
            suffix=".tmp",
        ) as handle:
            handle.write(encoded)
            temp_path = Path(handle.name)

        temp_path.replace(self.file_path)
        logger.info("Saved %s tasks to %s", len(document.tasks), self.file_path)

    def export_snapshot(self) -> dict[str, Any]:
        return self.load().to_dict()
