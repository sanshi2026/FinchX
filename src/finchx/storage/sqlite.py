"""SQLite-backed implementation of the FinchX Storage contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, TypeVar

from finchx.contracts import Provenance, Source
from finchx.storage.errors import (
    InvalidStorageKey,
    InvalidStoredObject,
    StorageBackendError,
    StorageError,
    StorageSerializationError,
)
from finchx.storage.models import StorageKey, StoredObject
from finchx.storage.serialization import dumps, loads


DataT = TypeVar("DataT")

_SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS stored_objects (
    storage_key TEXT PRIMARY KEY NOT NULL,
    dataset TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    payload TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    source_json TEXT,
    provenance_json TEXT,
    metadata_json TEXT NOT NULL
)
"""


class SQLiteStorage:
    """Local SQLite persistence for generic FinchX StoredObject envelopes."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection: sqlite3.Connection | None = None
        try:
            self._connection = sqlite3.connect(self.path)
            self._connection.row_factory = sqlite3.Row
            current_version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
            if current_version not in (0, _SCHEMA_VERSION):
                raise StorageBackendError(
                    f"unsupported FinchX storage schema version: {current_version}"
                )
            self._connection.executescript(_SCHEMA)
            self._connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            self._connection.commit()
        except StorageError:
            self.close()
            raise
        except sqlite3.Error as exc:
            self.close()
            raise StorageBackendError(
                f"could not initialize SQLite storage at {self.path!r}"
            ) from exc

    def __enter__(self) -> SQLiteStorage:
        self._connection_or_raise()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        try:
            connection.close()
        except sqlite3.Error as exc:
            raise StorageBackendError("could not close SQLite storage") from exc

    def _connection_or_raise(self) -> sqlite3.Connection:
        if self._connection is None:
            raise StorageBackendError("SQLite storage is closed")
        return self._connection

    @staticmethod
    def _validate_key(key: StorageKey) -> StorageKey:
        if not isinstance(key, StorageKey):
            raise InvalidStorageKey("storage operations require a StorageKey")
        return key

    def _run(self, operation: str, callback: Callable[[sqlite3.Connection], DataT]) -> DataT:
        connection = self._connection_or_raise()
        try:
            return callback(connection)
        except StorageError:
            raise
        except sqlite3.Error as exc:
            raise StorageBackendError(f"SQLite {operation} failed") from exc

    @staticmethod
    def _optional_load(payload: str | None, field_name: str) -> Any:
        if payload is None:
            return None
        try:
            return loads(payload)
        except StorageSerializationError as exc:
            raise StorageSerializationError(
                f"stored {field_name} could not be decoded"
            ) from exc

    @classmethod
    def _object_from_row(cls, key: StorageKey, row: sqlite3.Row) -> StoredObject[Any]:
        if (
            row["storage_key"] != key.serialized
            or row["dataset"] != key.dataset
            or row["dataset_version"] != key.version
        ):
            raise StorageSerializationError("stored key metadata does not match the requested key")

        stored_at = loads(row["stored_at"])
        source = cls._optional_load(row["source_json"], "source")
        provenance = cls._optional_load(row["provenance_json"], "provenance")
        metadata = loads(row["metadata_json"])
        data = loads(row["payload"])
        if not isinstance(stored_at, datetime):
            raise StorageSerializationError("stored_at payload is not a datetime")
        if source is not None and not isinstance(source, Source):
            raise StorageSerializationError("source payload is not a Source")
        if provenance is not None and not isinstance(provenance, Provenance):
            raise StorageSerializationError("provenance payload is not a Provenance")
        if not isinstance(metadata, Mapping):
            raise StorageSerializationError("metadata payload is not a mapping")
        try:
            return StoredObject(
                key=key,
                data=data,
                stored_at=stored_at,
                source=source,
                provenance=provenance,
                metadata=metadata,
            )
        except InvalidStoredObject as exc:
            raise StorageSerializationError("stored object envelope is invalid") from exc

    def get(self, key: StorageKey) -> StoredObject[Any] | None:
        key = self._validate_key(key)

        def read(connection: sqlite3.Connection) -> StoredObject[Any] | None:
            row = connection.execute(
                "SELECT * FROM stored_objects WHERE storage_key = ?",
                (key.serialized,),
            ).fetchone()
            return None if row is None else self._object_from_row(key, row)

        return self._run("get", read)

    def put(
        self,
        key: StorageKey,
        value: Any,
        *,
        stored_at: datetime | None = None,
        source: Source | None = None,
        provenance: Provenance | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> StoredObject[Any]:
        key = self._validate_key(key)
        object_value = StoredObject(
            key=key,
            data=value,
            stored_at=stored_at if stored_at is not None else datetime.now(timezone.utc),
            source=source,
            provenance=provenance,
            metadata={} if metadata is None else metadata,
        )
        try:
            payload = dumps(object_value.data)
            stored_at_payload = dumps(object_value.stored_at)
            source_payload = None if object_value.source is None else dumps(object_value.source)
            provenance_payload = (
                None
                if object_value.provenance is None
                else dumps(object_value.provenance)
            )
            metadata_payload = dumps(object_value.metadata)
        except StorageSerializationError:
            raise

        def write(connection: sqlite3.Connection) -> StoredObject[Any]:
            with connection:
                connection.execute(
                    """
                    INSERT INTO stored_objects (
                        storage_key, dataset, dataset_version, payload, stored_at,
                        source_json, provenance_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(storage_key) DO UPDATE SET
                        dataset = excluded.dataset,
                        dataset_version = excluded.dataset_version,
                        payload = excluded.payload,
                        stored_at = excluded.stored_at,
                        source_json = excluded.source_json,
                        provenance_json = excluded.provenance_json,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        key.serialized,
                        key.dataset,
                        key.version,
                        payload,
                        stored_at_payload,
                        source_payload,
                        provenance_payload,
                        metadata_payload,
                    ),
                )
            return object_value

        return self._run("put", write)

    def delete(self, key: StorageKey) -> bool:
        key = self._validate_key(key)

        def remove(connection: sqlite3.Connection) -> bool:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM stored_objects WHERE storage_key = ?",
                    (key.serialized,),
                )
            return cursor.rowcount > 0

        return self._run("delete", remove)

    def exists(self, key: StorageKey) -> bool:
        key = self._validate_key(key)

        def check(connection: sqlite3.Connection) -> bool:
            row = connection.execute(
                "SELECT 1 FROM stored_objects WHERE storage_key = ?",
                (key.serialized,),
            ).fetchone()
            return row is not None

        return self._run("exists", check)


__all__ = ["SQLiteStorage"]
