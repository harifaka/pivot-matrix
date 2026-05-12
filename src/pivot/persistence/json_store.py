"""JSON persistence engine for Pivot."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pivot.constants import MAX_BACKUP_SNAPSHOTS, SCHEMA_VERSION
from pivot.domain.models import TaskDocument

logger = logging.getLogger(__name__)


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when a future schema version is encountered."""


@dataclass(slots=True)
class JsonDataStore:
    """Load and save the application document as JSON."""

    file_path: Path
    backup_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.backup_dir is None:
            self.backup_dir = self.file_path.parent / "backups"

    def load(self) -> TaskDocument:
        if not self.file_path.exists():
            logger.info("Creating a new empty task document at %s", self.file_path)
            return TaskDocument.empty()

        try:
            payload = self._load_payload_from(self.file_path)
            return self._document_from_payload(payload)
        except (json.JSONDecodeError, OSError, ValueError, TypeError) as error:
            logger.exception("Failed to load primary task store (%s): %s", self.file_path, error)
            for candidate in self._recovery_candidates():
                try:
                    payload = self._load_payload_from(candidate)
                    document = self._document_from_payload(payload)
                    logger.warning("Recovered task data from %s", candidate)
                    self.save(document)
                    return document
                except (json.JSONDecodeError, OSError, ValueError, TypeError):
                    continue
            logger.error("No valid backups found; starting with a new empty document")
            return TaskDocument.empty()

    def _document_from_payload(self, payload: dict[str, Any]) -> TaskDocument:
        schema_version = int(payload.get("schema_version", SCHEMA_VERSION))
        if schema_version > SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                f"Schema version {schema_version} is newer than supported version {SCHEMA_VERSION}.",
            )
        return TaskDocument.from_dict(payload)

    def _load_payload_from(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Root JSON payload must be an object")
        return payload

    def _recovery_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        sidecar = self.file_path.with_suffix(".bak")
        if sidecar.exists():
            candidates.append(sidecar)
        if self.backup_dir and self.backup_dir.exists():
            backups = sorted(
                [path for path in self.backup_dir.glob(f"{self.file_path.stem}-*.json") if path.is_file()],
                reverse=True,
            )
            candidates.extend(backups)
        return candidates

    def save(self, document: TaskDocument) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if self.backup_dir is not None:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_existing()
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
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        temp_path.replace(self.file_path)
        self._write_sidecar_backup(encoded)
        self._prune_backups()
        logger.info("Saved %s tasks to %s", len(document.tasks), self.file_path)

    def _snapshot_existing(self) -> None:
        if not self.file_path.exists() or self.backup_dir is None:
            return
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        snapshot = self.backup_dir / f"{self.file_path.stem}-{timestamp}.json"
        shutil.copy2(self.file_path, snapshot)

    def _write_sidecar_backup(self, payload: str) -> None:
        sidecar = self.file_path.with_suffix(".bak")
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=sidecar.parent,
            prefix=f".{sidecar.stem}-",
            suffix=".tmp",
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        temp_path.replace(sidecar)

    def _prune_backups(self) -> None:
        if self.backup_dir is None or not self.backup_dir.exists():
            return
        backups = sorted(
            [path for path in self.backup_dir.glob(f"{self.file_path.stem}-*.json") if path.is_file()],
            reverse=True,
        )
        for stale in backups[MAX_BACKUP_SNAPSHOTS:]:
            stale.unlink(missing_ok=True)

    def export_snapshot(self) -> dict[str, Any]:
        return self.load().to_dict()
