"""Backend-independent storage contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Protocol, TypeVar, runtime_checkable

from finchx.contracts import Provenance, Source
from finchx.storage.models import StorageKey, StoredObject


DataT = TypeVar("DataT")


@runtime_checkable
class Storage(Protocol):
    """Minimal storage contract for already-acquired FinchX objects.

    A missing key is represented by ``None`` from ``get`` and ``False`` from
    ``delete``.  Implementations must replace an existing value on ``put``.
    """

    def get(self, key: StorageKey) -> StoredObject[Any] | None:
        """Return the stored object for key, or None when it is absent."""

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
        """Store value under key, replacing any existing value."""

    def delete(self, key: StorageKey) -> bool:
        """Remove key and return whether a value was present."""

    def exists(self, key: StorageKey) -> bool:
        """Return whether key is currently present."""


Clock = Callable[[], datetime]


__all__ = ["Clock", "Storage"]
