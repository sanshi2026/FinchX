"""Small TTL cache primitive layered on the FinchX Storage contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import math
from numbers import Real
from typing import Any, Generic, TypeVar

from finchx.contracts import Provenance, Source
from finchx.storage.errors import InvalidCacheEntry
from finchx.storage.models import StorageKey, StoredObject
from finchx.storage.protocol import Clock, Storage


DataT = TypeVar("DataT")
_EXPIRATION_METADATA_KEY = "__finchx_cache_expires_at__"


class CacheState(str, Enum):
    """The observable state of one cache key."""

    MISSING = "missing"
    FRESH = "fresh"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CacheEntry(Generic[DataT]):
    """A Storage object together with optional cache expiration metadata."""

    stored: StoredObject[DataT]
    expires_at: datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.stored, StoredObject):
            raise InvalidCacheEntry("stored must be a StoredObject")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
                raise InvalidCacheEntry("expires_at must include a timezone offset")
            if self.expires_at < self.stored.stored_at:
                raise InvalidCacheEntry("expires_at must not precede stored_at")

    @property
    def key(self) -> StorageKey:
        return self.stored.key

    @property
    def value(self) -> DataT:
        return self.stored.data

    @property
    def stored_at(self) -> datetime:
        return self.stored.stored_at

    def is_expired(self, now: datetime) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise InvalidCacheEntry("now must include a timezone offset")
        return self.expires_at is not None and now >= self.expires_at


class Cache:
    """Expiration behavior layered over any Storage backend."""

    def __init__(self, storage: Storage, *, clock: Clock | None = None) -> None:
        if not isinstance(storage, Storage):
            raise TypeError("storage must implement the Storage protocol")
        self._storage = storage
        self._clock = clock or (lambda: datetime.now().astimezone())

    def _now(self, now: datetime | None = None) -> datetime:
        value = self._clock() if now is None else now
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise InvalidCacheEntry("cache clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _expiration(now: datetime, ttl: float | timedelta | None) -> datetime | None:
        if ttl is None:
            return None
        if isinstance(ttl, timedelta):
            seconds = ttl.total_seconds()
            delta = ttl
        elif isinstance(ttl, Real) and not isinstance(ttl, bool):
            seconds = float(ttl)
        else:
            raise InvalidCacheEntry("ttl must be seconds, timedelta, or None")
        if not math.isfinite(seconds) or seconds < 0:
            raise InvalidCacheEntry("ttl must be finite and non-negative")
        if not isinstance(ttl, timedelta):
            try:
                delta = timedelta(seconds=seconds)
            except OverflowError as exc:
                raise InvalidCacheEntry("ttl produces an unrepresentable duration") from exc
        try:
            return now + delta
        except OverflowError as exc:
            raise InvalidCacheEntry("ttl produces an unrepresentable expiration time") from exc

    @staticmethod
    def _entry_from(stored: StoredObject[Any]) -> CacheEntry[Any]:
        raw_expiration = stored.metadata.get(_EXPIRATION_METADATA_KEY)
        if raw_expiration is not None and not isinstance(raw_expiration, datetime):
            raise InvalidCacheEntry("stored cache expiration metadata is invalid")
        user_metadata = {
            key: value
            for key, value in stored.metadata.items()
            if key != _EXPIRATION_METADATA_KEY
        }
        visible = StoredObject(
            key=stored.key,
            data=stored.data,
            stored_at=stored.stored_at,
            source=stored.source,
            provenance=stored.provenance,
            metadata=user_metadata,
        )
        return CacheEntry(stored=visible, expires_at=raw_expiration)

    def put(
        self,
        key: StorageKey,
        value: DataT,
        *,
        ttl: float | timedelta | None = None,
        source: Source | None = None,
        provenance: Provenance | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CacheEntry[DataT]:
        now = self._now()
        expires_at = self._expiration(now, ttl)
        user_metadata = {} if metadata is None else dict(metadata)
        if _EXPIRATION_METADATA_KEY in user_metadata:
            raise InvalidCacheEntry("reserved cache expiration metadata key cannot be supplied")
        if expires_at is not None:
            user_metadata[_EXPIRATION_METADATA_KEY] = expires_at
        stored = self._storage.put(
            key,
            value,
            stored_at=now,
            source=source,
            provenance=provenance,
            metadata=user_metadata,
        )
        return self._entry_from(stored)

    def get_entry(self, key: StorageKey) -> CacheEntry[Any] | None:
        """Return the entry even when expired; return None only when missing."""

        stored = self._storage.get(key)
        return None if stored is None else self._entry_from(stored)

    def get(self, key: StorageKey, *, now: datetime | None = None) -> StoredObject[Any] | None:
        """Return a fresh object; an expired object is treated as absent."""

        entry = self.get_entry(key)
        if entry is None or entry.is_expired(self._now(now)):
            return None
        return entry.stored

    def status(self, key: StorageKey, *, now: datetime | None = None) -> CacheState:
        """Distinguish missing, fresh, and expired without deleting data."""

        entry = self.get_entry(key)
        if entry is None:
            return CacheState.MISSING
        return CacheState.EXPIRED if entry.is_expired(self._now(now)) else CacheState.FRESH

    def exists(self, key: StorageKey, *, now: datetime | None = None) -> bool:
        """Return true only for a fresh cache entry."""

        return self.status(key, now=now) is CacheState.FRESH

    def delete(self, key: StorageKey) -> bool:
        return self._storage.delete(key)


__all__ = ["Cache", "CacheEntry", "CacheState"]
