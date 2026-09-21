"""Stable storage identity and stored-object envelopes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import math
from types import MappingProxyType
from typing import Any, Generic, TypeVar
from urllib.parse import quote

from pydantic import BaseModel, TypeAdapter, ValidationError

from finchx.contracts import Provenance, Source
from finchx.contracts.dataset import DatasetId
from finchx.storage.errors import InvalidStorageKey, InvalidStoredObject


_DATASET_ID_ADAPTER = TypeAdapter(DatasetId)
DataT = TypeVar("DataT")


def _canonicalize(value: Any, *, path: str) -> Any:
    """Convert supported identity values into deterministic JSON-shaped data."""

    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python", by_alias=True), path=path)
    if isinstance(value, Enum):
        return _canonicalize(value.value, path=path)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidStorageKey(f"{path} datetime must be timezone-aware")
        normalized = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"$type": "datetime", "value": normalized}
    if isinstance(value, date):
        return {"$type": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise InvalidStorageKey(f"{path} Decimal must be finite")
        return {"$type": "decimal", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidStorageKey(f"{path} float must be finite")
        return {"$type": "float", "value": value.hex()}
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            if not isinstance(key, str) or not key:
                raise InvalidStorageKey(f"{path} mapping keys must be non-empty strings")
            normalized[key] = _canonicalize(value[key], path=f"{path}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _canonicalize(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise InvalidStorageKey(
        f"{path} has unsupported identity type {type(value).__name__}; "
        "use JSON-shaped values, dates, Decimals, or contract models"
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True, init=False)
class StorageKey:
    """Deterministic logical identity for one stored Dataset object.

    Provider identity is deliberately absent.  Source/provider facts belong in
    the stored value or its metadata, while Dataset name and schema version
    define the logical namespace.
    """

    dataset: DatasetId
    version: str
    identity: Mapping[str, Any]
    _serialized: str = field(repr=False, compare=False)

    def __init__(
        self,
        dataset: str,
        version: str,
        identity: Mapping[str, Any],
    ) -> None:
        try:
            validated_dataset = _DATASET_ID_ADAPTER.validate_python(dataset)
        except (ValidationError, TypeError) as exc:
            raise InvalidStorageKey(f"invalid dataset name: {dataset!r}") from exc
        if not isinstance(version, str) or not version or version != version.strip():
            raise InvalidStorageKey("version must be a non-empty string without outer whitespace")
        if not isinstance(identity, Mapping):
            raise InvalidStorageKey("identity must be a mapping of logical components")

        canonical = _canonicalize(identity, path="identity")
        frozen_identity = _freeze(canonical)
        canonical_json = json.dumps(
            _thaw(frozen_identity),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        namespace = f"{validated_dataset}/{quote(version, safe='')}"
        serialized = f"{namespace}/{quote(canonical_json, safe='')}"
        object.__setattr__(self, "dataset", validated_dataset)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "identity", frozen_identity)
        object.__setattr__(self, "_serialized", serialized)

    @classmethod
    def from_dataset(
        cls,
        dataset: Any,
        identity: Mapping[str, Any],
    ) -> StorageKey:
        """Build a key from an existing FinchX DatasetDefinition."""

        from finchx.datasets.definition import DatasetDefinition

        if not isinstance(dataset, DatasetDefinition):
            raise InvalidStorageKey("dataset must be a DatasetDefinition")
        return cls(dataset.name, dataset.schema_version, identity)

    @property
    def namespace(self) -> str:
        """The logical Dataset/version namespace, independent of disk layout."""

        return f"{self.dataset}/{quote(self.version, safe='')}"

    @property
    def serialized(self) -> str:
        """A stable, transport-neutral string representation of this key."""

        return self._serialized

    @property
    def dataset_version(self) -> str:
        """Alias for callers that want the versioned Dataset identity."""

        return self.version

    def __str__(self) -> str:
        return self.serialized

    def __hash__(self) -> int:
        return hash(self.serialized)


@dataclass(frozen=True, slots=True)
class StoredObject(Generic[DataT]):
    """One value plus storage metadata; it is not a Dataset contract."""

    key: StorageKey
    data: DataT
    stored_at: datetime
    source: Source | None = None
    provenance: Provenance | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.key, StorageKey):
            raise InvalidStoredObject("key must be a StorageKey")
        if not isinstance(self.stored_at, datetime):
            raise InvalidStoredObject("stored_at must be a datetime")
        if self.stored_at.tzinfo is None or self.stored_at.utcoffset() is None:
            raise InvalidStoredObject("stored_at must include a timezone offset")
        if self.source is not None and not isinstance(self.source, Source):
            raise InvalidStoredObject("source must be a Source or None")
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise InvalidStoredObject("provenance must be a Provenance or None")
        if not isinstance(self.metadata, Mapping):
            raise InvalidStoredObject("metadata must be a mapping")
        if any(not isinstance(name, str) or not name for name in self.metadata):
            raise InvalidStoredObject("metadata keys must be non-empty strings")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def dataset(self) -> DatasetId:
        """Return the Dataset namespace carried by the key."""

        return self.key.dataset

    @property
    def version(self) -> str:
        """Return the Dataset schema version carried by the key."""

        return self.key.version


__all__ = ["StorageKey", "StoredObject"]
