"""Errors raised at the FinchX storage boundary."""


class StorageError(RuntimeError):
    """Base class for storage contract and backend failures."""


class InvalidStorageKey(StorageError, ValueError):
    """A key is malformed or an operation received a non-key object."""


class InvalidStoredObject(StorageError, ValueError):
    """A stored-object envelope contains invalid metadata."""


class StorageBackendError(StorageError):
    """A concrete storage backend could not complete an operation."""


class StorageSerializationError(StorageBackendError):
    """A stored payload cannot be safely encoded or decoded."""


class CacheError(StorageError):
    """Base class for cache entry validation failures."""


class InvalidCacheEntry(CacheError, ValueError):
    """A cache entry or TTL value is invalid."""


__all__ = [
    "CacheError",
    "InvalidStorageKey",
    "InvalidStoredObject",
    "InvalidCacheEntry",
    "StorageBackendError",
    "StorageError",
    "StorageSerializationError",
]
