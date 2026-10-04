"""Immutable fetch results and JSON metadata."""

from __future__ import annotations

from collections.abc import (
    Mapping,
)
from copy import (
    deepcopy,
)
from dataclasses import (
    dataclass,
    field,
)
from datetime import (
    datetime,
)
import math
from pprint import (
    pformat,
)
from types import (
    MappingProxyType,
)
from typing import (
    Any,
    Generic,
    TypeVar,
)
from pydantic import (
    BaseModel,
)
from finchx.contracts import (
    Source,
    StandardRecord,
)
from finchx.datasets.definition import (
    DatasetDefinition,
)


DataT = TypeVar("DataT")


def _short_display(value: Any, *, max_chars: int = 1200) -> str:
    """Render a terminal-friendly business-data preview."""

    rendered = pformat(value, width=100, compact=True)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max_chars - 3] + "..."


@dataclass(frozen=True)
class FetchAttempt:
    """Safe, per-attempt execution facts retained by a successful fetch."""

    provider: str
    attempt: int
    started_at: datetime
    captured_at: datetime
    success: bool
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider:
            raise ValueError("attempt provider must be a non-empty string")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("attempt must be a positive integer")
        for name, value in (
            ("started_at", self.started_at),
            ("captured_at", self.captured_at),
        ):
            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(f"{name} must be timezone-aware")
        if type(self.success) is not bool:
            raise TypeError("success must be a bool")
        if self.success and (self.error_type is not None or self.error_message is not None):
            raise ValueError("successful attempts cannot contain an error")

    @property
    def provider_id(self) -> str:
        return self.provider

    @property
    def attempt_number(self) -> int:
        return self.attempt


@dataclass(frozen=True)
class _RouteResult:
    """Internal route envelope for successful data plus non-fatal warnings."""

    data: Any
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if any(not isinstance(warning, str) or not warning.strip() for warning in self.warnings):
            raise TypeError("route warnings must contain non-empty strings")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("route metadata must be a mapping")
        object.__setattr__(self, "metadata", _freeze_json_metadata(self.metadata, path="route metadata"))


@dataclass(frozen=True)
class FetchResult(Generic[DataT]):
    """The data and direct provenance of one successful Collector fetch."""

    data: DataT
    dataset: DatasetDefinition[Any, Any]
    provider: str | None
    captured_at: datetime
    warnings: tuple[str, ...] = ()
    provenance: tuple[Source, ...] = ()
    attempts: tuple[FetchAttempt, ...] = ()
    fallback_used: bool = False
    cache_hit: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, DatasetDefinition):
            raise TypeError("dataset must be a DatasetDefinition")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider
        ):
            raise ValueError("provider must be None or a non-empty string")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        if type(self.fallback_used) is not bool:
            raise TypeError("fallback_used must be a bool")
        if type(self.cache_hit) is not bool:
            raise TypeError("cache_hit must be a bool")
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        object.__setattr__(self, "attempts", tuple(self.attempts))
        if any(not isinstance(attempt, FetchAttempt) for attempt in self.attempts):
            raise TypeError("attempts must contain FetchAttempt values")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(self, "metadata", _freeze_json_metadata(self.metadata))

    @property
    def dataset_id(self) -> str:
        """Return the stable Dataset name without changing the Dataset contract."""

        return self.dataset.name

    @property
    def provider_id(self) -> str | None:
        """Return the selected stable Provider identity."""

        return self.provider

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return the business data as a list of independent dictionaries.

        Standard records expose their business ``data`` payload, while typed
        Pydantic results expose their JSON-shaped model dump.  Provider,
        provenance, attempts, cache and other ``FetchResult`` audit facts
        remain on the result and are not mixed into these row dictionaries.
        """

        values = self.data if isinstance(self.data, (tuple, list)) else (self.data,)
        try:
            return [deepcopy(self._business_dict(value)) for value in values]
        except TypeError as exc:
            raise TypeError(
                "FetchResult.to_dicts() requires StandardRecord or Pydantic model data"
            ) from exc

    @staticmethod
    def _business_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, StandardRecord):
            return value.data
        if isinstance(value, BaseModel):
            dumped = value.model_dump(mode="json", by_alias=True)
            if not isinstance(dumped, dict):
                raise TypeError("Pydantic result models must dump to dictionaries")
            return dumped
        raise TypeError("unsupported FetchResult data value")

    def __repr__(self) -> str:
        records = self._standard_records()
        if records is not None:
            rows = self.to_dicts()
            preview = rows[:3]
            if len(rows) > len(preview):
                preview.append({"...": f"{len(rows) - len(preview)} more rows"})
            return (
                f"FetchResult(dataset={self.dataset_id!r}, rows={len(rows)}, "
                f"data={_short_display(preview)})"
            )

        business_data = self.data
        if isinstance(business_data, BaseModel):
            business_data = business_data.model_dump(mode="json", by_alias=True)
        return (
            f"FetchResult(dataset={self.dataset_id!r}, "
            f"data={_short_display(business_data)})"
        )

    def __str__(self) -> str:
        return repr(self)

    def _standard_records(self) -> tuple[StandardRecord, ...] | None:
        if isinstance(self.data, StandardRecord):
            return (self.data,)
        if isinstance(self.data, (tuple, list)) and all(
            isinstance(record, StandardRecord) for record in self.data
        ):
            return tuple(self.data)
        return None


def _freeze_json_metadata(value: Any, *, path: str = "metadata") -> Any:
    """Validate and recursively freeze JSON-compatible result metadata."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} numbers must be finite")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise TypeError(f"{path} mapping keys must be non-empty strings")
            normalized[key] = _freeze_json_metadata(item, path=f"{path}.{key}")
        return MappingProxyType(normalized)
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json_metadata(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise TypeError(
        f"{path} must contain only JSON-compatible values; got {type(value).__name__}"
    )


def _thaw_json_metadata(value: Any) -> Any:
    """Return mutable JSON-shaped data for the configured Storage backend."""

    if isinstance(value, Mapping):
        return {key: _thaw_json_metadata(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_metadata(item) for item in value]
    return value

# Keep historical public class identities for callers and pickles.
FetchAttempt.__module__ = "finchx.collectors.core"
FetchResult.__module__ = "finchx.collectors.core"
