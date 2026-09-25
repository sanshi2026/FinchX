"""Tonghuashun concept reference, detail, and market-data contracts."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    IndexPoints,
    Percentage,
    Provenance,
    ProvenanceClass,
    Quality,
    QualityIssue,
    QualityIssueKind,
    Shares,
    Source,
    SourceReference,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition


class ConceptRef(ContractModel):
    """Stable page identity used by all concept-specific requests."""

    sector_type: Literal["concept"] = Field(
        alias="sectorType",
        description="Sector classification; this reference always represents a concept.",
    )
    sector_name: str = Field(
        alias="sectorName",
        min_length=1,
        description="Concept name from the Tonghuashun concept directory.",
    )
    provider_namespace: Literal["tonghuashun_concept"] = Field(
        alias="providerNamespace",
        description="Namespace that identifies the provider's concept-ID scheme.",
    )
    provider_sector_id: str = Field(
        alias="providerSectorId",
        min_length=1,
        pattern=r"^[0-9]+$",
        description="Tonghuashun concept page ID, distinct from its quote ID.",
    )

    @field_validator("sector_name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("sectorName must contain a non-whitespace character")
        return value

    @model_validator(mode="after")
    def fixed_identity(self) -> ConceptRef:
        if self.sector_type != "concept" or self.provider_namespace != "tonghuashun_concept":
            raise ValueError("invalid Tonghuashun concept identity")
        return self


class ConceptListRequest(ContractModel):
    """Request the current Tonghuashun concept directory."""


class ConceptQuoteSnapshotRequest(ContractModel):
    concept: ConceptRef | str


class ConceptOhlcvRequest(ContractModel):
    concept: ConceptRef | str
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def dates_must_not_be_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime):
            raise ValueError("concept OHLCV bounds must be dates, not datetimes")
        return value

    @model_validator(mode="after")
    def dates_ordered(self) -> ConceptOhlcvRequest:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not exceed end_date")
        return self


class ConceptQuoteSnapshotData(ContractModel):
    """Current concept-board quote; OHLC fields are index points, amounts CNY."""

    concept: ConceptRef
    index_level: IndexPoints | None = Field(default=None, alias="indexLevel")
    previous_close: IndexPoints | None = Field(default=None, alias="previousClose")
    open: IndexPoints | None = None
    high: IndexPoints | None = None
    low: IndexPoints | None = None
    level_change: IndexPoints | None = Field(default=None, alias="levelChange")
    change_rate: Percentage | None = Field(default=None, alias="changeRate", description="Change as a ratio fraction; -0.85% is -0.0085.")
    volume: Shares | None = Field(default=None, description="Aggregate constituent trading volume in shares.")
    amount: Amount | None = Field(default=None, description="Aggregate constituent traded amount in CNY.")
    net_money_flow: Amount | None = Field(default=None, alias="netMoneyFlow", description="Net money flow in CNY.")
    rise_count: int | None = Field(default=None, alias="riseCount", ge=0)
    fall_count: int | None = Field(default=None, alias="fallCount", ge=0)
    source_timestamp: datetime | None = Field(default=None, alias="sourceTimestamp")

    @field_validator("source_timestamp")
    @classmethod
    def source_time_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("sourceTimestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_level_order(self) -> ConceptQuoteSnapshotData:
        if self.high is not None and self.low is not None and self.high < self.low:
            raise ValueError("high must not be lower than low")
        return self


class ConceptOhlcvData(ContractModel):
    """One daily concept-index bar; OHLC values are points, volume is shares."""

    concept: ConceptRef
    bar_date: date = Field(alias="barDate")
    open: IndexPoints
    high: IndexPoints
    low: IndexPoints
    close: IndexPoints
    volume: Shares
    amount: Amount | None = None

    @field_validator("bar_date", mode="before")
    @classmethod
    def bar_date_must_not_be_datetime(cls, value: object) -> object:
        if isinstance(value, datetime):
            raise ValueError("barDate must be a date, not a datetime")
        return value

    @model_validator(mode="after")
    def validate_bar_values(self) -> ConceptOhlcvData:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to open, close, and high")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount must not be negative")
        return self


MARKET_CONCEPT_LIST_DATASET = DatasetDefinition(
    name="market.concept_list", schema_version="1.0", request_type=ConceptListRequest, data_type=ConceptRef
)
MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET = DatasetDefinition(
    name="market.concept_quote_snapshot", schema_version="1.0", request_type=ConceptQuoteSnapshotRequest, data_type=ConceptQuoteSnapshotData
)
MARKET_CONCEPT_OHLCV_DATASET = DatasetDefinition(
    name="market.concept_ohlcv", schema_version="1.0", request_type=ConceptOhlcvRequest, data_type=ConceptOhlcvData
)

_CONCEPT_DATASETS = (
    MARKET_CONCEPT_LIST_DATASET,
    MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET,
    MARKET_CONCEPT_OHLCV_DATASET,
)


def normalize_concept(request: ContractModel, raw: Any, *, source: Source):
    """Create the standard records shared by the three concept Datasets."""

    dataset = next((item for item in _CONCEPT_DATASETS if isinstance(request, item.request_type)), None)
    if dataset is None:
        raise ValueError("unknown concept request")
    values = raw if isinstance(raw, list) else [raw]
    records: list[StandardRecord] = []
    for index, item in enumerate(values):
        normalized_item = dict(item) if isinstance(item, dict) else item
        metadata = normalized_item.pop("__finchx", {}) if isinstance(normalized_item, dict) else {}
        try:
            model = dataset.data_type.model_validate(normalized_item)
        except Exception as exc:
            from finchx.providers.errors import ProviderError

            raise ProviderError(source, f"invalid normalized {dataset.name} data: {type(exc).__name__}") from exc
        concept = model if isinstance(model, ConceptRef) else getattr(model, "concept", None)
        identity = concept.provider_sector_id if concept is not None else "all"
        partial = _has_partial_fields(dataset, model)
        issues = (
            [QualityIssue(kind=QualityIssueKind.PARTIAL, detail="Tonghuashun omitted one or more optional concept fields.")]
            if partial
            else []
        )
        record_source = Source(
            providerId=source.provider_id,
            sourceUrl=metadata.get("sourceUrl", source.source_url),
            sourceRecordId=metadata.get("sourceRecordId"),
        )
        source_references = [
            SourceReference.model_validate(reference)
            for reference in metadata.get("sourceReferences", [])
        ]
        captured_at = metadata.get("capturedAt", datetime.now(timezone.utc))
        records.append(
            StandardRecord(
                dataset=dataset.name,
                schemaVersion=dataset.schema_version,
                recordId=_concept_record_id(
                    dataset.name, identity, model, captured_at=captured_at
                ),
                entityId=identity,
                capturedAt=captured_at,
                source=record_source,
                status=DataStatus.LIVE,
                quality=Quality(issues=issues),
                provenance=Provenance(
                    recordClass=ProvenanceClass.STANDARDIZED,
                    transformationVersion="tonghuashun-concept/1",
                    sourceReferences=source_references,
                ),
                data=model.model_dump(mode="json", by_alias=True),
            )
        )
    if isinstance(raw, list):
        return tuple(records)
    return records[0]


def _has_partial_fields(dataset: DatasetDefinition, model: ContractModel) -> bool:
    if dataset.name == MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET.name:
        return any(
            getattr(model, field) is None
            for field in (
                "index_level",
                "previous_close",
                "open",
                "high",
                "low",
                "level_change",
                "change_rate",
                "volume",
                "amount",
                "net_money_flow",
                "rise_count",
                "fall_count",
                "source_timestamp",
            )
        )
    if dataset.name == MARKET_CONCEPT_OHLCV_DATASET.name:
        return model.amount is None
    return False


def _concept_record_id(
    dataset_name: str,
    identity: str,
    model: ContractModel,
    *,
    captured_at: datetime,
) -> str:
    if dataset_name == MARKET_CONCEPT_LIST_DATASET.name:
        return identity
    if dataset_name == MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET.name:
        source_timestamp = getattr(model, "source_timestamp", None)
        timestamp = source_timestamp if source_timestamp is not None else captured_at
        return f"{identity}:quote:{timestamp.isoformat()}"
    if dataset_name == MARKET_CONCEPT_OHLCV_DATASET.name:
        return f"{identity}:{model.bar_date.isoformat()}"
    return f"{identity}:unknown"
