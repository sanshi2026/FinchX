"""Core contracts for source-aware, versioned standardized records."""

from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
import re
from typing import Any, Literal, get_args, get_origin

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from finchx.contracts.dataset import DatasetId
from finchx.contracts.status import DataStatus
from finchx.contracts.dates import normalize_date_input
from finchx.entities import InstrumentId


_RFC3339_TIMESTAMP = re.compile(
    r"^(?!.*-00:00$)[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})$"
)
_DATE_STRING_PATTERNS = (
    re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    re.compile(r"^[0-9]{8}$"),
    re.compile(r"^[0-9]{4}/[0-9]{2}/[0-9]{2}$"),
)
_AMBIGUOUS_DATE_PATTERN = re.compile(r"^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$")


def _contains_type(annotation: Any, target: type[Any]) -> bool:
    if annotation is target:
        return True
    return any(_contains_type(item, target) for item in get_args(annotation))


def _looks_like_date_string(value: str) -> bool:
    return any(pattern.fullmatch(value) is not None for pattern in _DATE_STRING_PATTERNS)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_public_date_inputs(cls, value: Any) -> Any:
        """Convert supported date strings before field-specific validation.

        Request models and nested contract models share this hook, so public
        date inputs are normalized in one place instead of in each endpoint.
        Datetime-capable bounds retain their existing datetime parsing for
        non-date strings, while ambiguous slash formats are always rejected.
        """

        if not isinstance(value, Mapping):
            return value

        payload = dict(value)
        for name, field in cls.model_fields.items():
            annotation = field.annotation
            if not _contains_type(annotation, date):
                continue
            allows_datetime = _contains_type(annotation, datetime)
            for key in {name, field.alias}:
                if key is None or key not in payload or payload[key] is None:
                    continue
                candidate = payload[key]
                if isinstance(candidate, str):
                    if _AMBIGUOUS_DATE_PATTERN.fullmatch(candidate):
                        raise ValueError(
                            f"ambiguous date input {candidate!r}; use YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD"
                        )
                    if allows_datetime and not _looks_like_date_string(candidate):
                        continue
                    payload[key] = normalize_date_input(candidate)
                elif isinstance(candidate, date) and not isinstance(candidate, datetime):
                    payload[key] = normalize_date_input(candidate)
        return payload


class QualityIssueKind(str, Enum):
    WARNING = "warning"
    VALIDATION_CONCERN = "validation_concern"
    STALE = "stale"
    PARTIAL = "partial"
    ESTIMATED = "estimated"


class ProvenanceClass(str, Enum):
    RAW = "raw"
    STANDARDIZED = "standardized"
    DERIVED = "derived"


class Source(ContractModel):
    """Identity of the direct provider/source, without request configuration."""

    provider_id: str = Field(
        alias="providerId",
        min_length=1,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    )
    source_record_id: str | None = Field(default=None, alias="sourceRecordId")
    source_url: AnyUrl | None = Field(default=None, alias="sourceUrl")


class SourceReference(ContractModel):
    """Reference to an upstream provider record used by a transformation."""

    provider_id: str = Field(
        alias="providerId",
        min_length=1,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    )
    source_record_id: str | None = Field(default=None, alias="sourceRecordId")
    source_url: AnyUrl | None = Field(default=None, alias="sourceUrl")


class QualityIssue(ContractModel):
    kind: QualityIssueKind
    detail: str | None = None


class Quality(ContractModel):
    """Quality observations kept separate from availability status."""

    issues: list[QualityIssue] = Field(default_factory=list)


class Adjustment(ContractModel):
    """A named adjustment or transformation applied to upstream data."""

    name: str = Field(min_length=1)
    version: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Provenance(ContractModel):
    """Minimal origin and transformation facts; not a lineage engine."""

    record_class: ProvenanceClass = Field(alias="recordClass")
    transformation_version: str | None = Field(default=None, alias="transformationVersion")
    source_references: list[SourceReference] = Field(
        default_factory=list,
        alias="sourceReferences",
    )
    adjustments: list[Adjustment] = Field(default_factory=list)


class StandardRecord(ContractModel):
    """Version 1 standard record envelope shared by FinchX datasets."""

    dataset: DatasetId
    schema_version: Literal["1.0"] = Field(alias="schemaVersion")
    record_id: str = Field(
        alias="recordId",
        min_length=1,
        pattern=r".*\S.*",
        description="FinchX-owned stable identity, distinct from a provider record ID.",
    )
    # Instrument records use InstrumentId. Other datasets may use an opaque,
    # stable entity key; strings are never interpreted as stock symbols.
    entity_id: InstrumentId | str = Field(alias="entityId")

    event_at: datetime | None = Field(default=None, alias="eventAt")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    captured_at: datetime = Field(alias="capturedAt")
    as_of: datetime | None = Field(default=None, alias="asOf")

    source: Source
    status: DataStatus
    quality: Quality
    provenance: Provenance
    data: dict[str, Any]

    @field_validator(
        "event_at", "published_at", "updated_at", "captured_at", "as_of", mode="before"
    )
    @classmethod
    def timestamps_must_use_rfc3339_shape(cls, value: Any) -> Any:
        if value is None or isinstance(value, datetime):
            return value
        if not isinstance(value, str) or _RFC3339_TIMESTAMP.fullmatch(value) is None:
            raise ValueError("timestamps must be aware datetimes or RFC 3339 strings with offsets")
        return value[:-1] + "Z" if value.endswith("z") else value

    @field_validator("event_at", "published_at", "updated_at", "captured_at", "as_of")
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        offset = value.utcoffset()
        if value.tzinfo is None or offset is None:
            raise ValueError("timestamps must include a timezone offset")
        if offset.total_seconds() % 60:
            raise ValueError("timezone offsets must use whole-minute precision")
        return value
