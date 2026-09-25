"""Backend-independent storage contracts for already-acquired FinchX data."""

from finchx.storage.cache import Cache, CacheEntry, CacheState
from finchx.storage.errors import (
    CacheError,
    InvalidCacheEntry,
    InvalidStorageKey,
    InvalidStoredObject,
    StorageBackendError,
    StorageError,
    StorageSerializationError,
)
from finchx.storage.memory import MemoryStorage
from finchx.storage.models import StorageKey, StoredObject
from finchx.storage.protocol import Storage
from finchx.storage.sqlite import SQLiteStorage

__all__ = [
    "Cache",
    "CacheEntry",
    "CacheError",
    "CacheState",
    "InvalidCacheEntry",
    "InvalidStorageKey",
    "InvalidStoredObject",
    "MemoryStorage",
    "Storage",
    "StorageBackendError",
    "StorageError",
    "StorageSerializationError",
    "StorageKey",
    "SQLiteStorage",
    "StoredObject",
]
