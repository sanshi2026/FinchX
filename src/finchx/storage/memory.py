"""Small in-memory Storage implementation for contract use and tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from finchx.contracts import Provenance, Source
from finchx.storage.errors import InvalidStorageKey
from finchx.storage.models import StorageKey, StoredObject
from finchx.storage.protocol import Clock


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStorage:
    """Deterministic key/value Storage with replacement semantics.

    This implementation intentionally keeps values in memory only.  It has no
    persistence or policy beyond the Storage contract.
    """

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or _utc_now
        self._objects: dict[StorageKey, StoredObject[Any]] = {}

    @staticmethod
    def _validate_key(key: StorageKey) -> StorageKey:
        if not isinstance(key, StorageKey):
            raise InvalidStorageKey("storage operations require a StorageKey")
        return key

    def get(self, key: StorageKey) -> StoredObject[Any] | None:
        return self._objects.get(self._validate_key(key))

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
            stored_at=stored_at if stored_at is not None else self._clock(),
            source=source,
            provenance=provenance,
            metadata={} if metadata is None else metadata,
        )
        self._objects[key] = object_value
        return object_value

    def delete(self, key: StorageKey) -> bool:
        key = self._validate_key(key)
        return self._objects.pop(key, None) is not None

    def exists(self, key: StorageKey) -> bool:
        return self._validate_key(key) in self._objects


__all__ = ["MemoryStorage"]
