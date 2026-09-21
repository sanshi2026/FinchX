"""Core contracts for source-aware, versioned standardized records."""

from datetime import datetime
from enum import Enum
import re
from typing import Any, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator

from finchx.contracts.dataset import DatasetId
from finchx.contracts.status import DataStatus
from finchx.entities import InstrumentId


_RFC3339_TIMESTAMP = re.compile(
    r"^(?!.*-00:00$)[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})$"
)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )


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
