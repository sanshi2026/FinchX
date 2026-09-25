"""Tencent plateNew instrument-to-sector snapshot contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    DataStatus,
    Percentage,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol


_SUPPORTED_EQUITY_PREFIXES = {
    Exchange.SSE: ("60", "68"),
    Exchange.SZSE: ("00", "30"),
}

def _validate_sector_instrument(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A:
        raise ValueError("Tencent sector datasets currently support only Market.CN_A")
    prefixes = _SUPPORTED_EQUITY_PREFIXES.get(instrument.exchange)
    if instrument.kind is not InstrumentKind.EQUITY or prefixes is None:
        raise ValueError("Tencent sector datasets support SSE and SZSE equities only")
    if (
        len(instrument.code) != 6
        or not instrument.code.isascii()
        or not instrument.code.isdigit()
        or not instrument.code.startswith(prefixes)
    ):
        raise ValueError("equity code does not match its explicit SSE/SZSE identity")


class MarketInstrumentSectorSnapshotRequest(ContractModel):
    """Request a current Tencent sector/area/concept observation for one equity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketInstrumentSectorSnapshotRequest:
        _validate_sector_instrument(self.instrument_id)
        return self


class InstrumentSectorEntry(ContractModel):
    """One Tencent plateNew relationship and its source-reported move."""

    sector_type: Literal["area", "industry", "concept"] = Field(alias="sectorType")
    sector_name: str = Field(alias="sectorName", min_length=1, pattern=r".*\S.*")
    provider_namespace: Literal["tencent_plate"] = Field(alias="providerNamespace")
    provider_sector_id: str = Field(alias="providerSectorId", min_length=1, pattern=r".*\S.*")
    level: int | None = Field(default=None, ge=1)
    tag: str | None = Field(default=None, min_length=1, pattern=r".*\S.*")
    change_pct: Percentage | None = Field(
        default=None,
        alias="changePct",
        description="Tencent zdf converted from percentage points to a ratio fraction.",
    )

    @field_validator("provider_sector_id")
    @classmethod
    def provider_id_must_not_contain_whitespace(cls, value: str) -> str:
        if any(character.isspace() for character in value):
            raise ValueError("providerSectorId must not contain whitespace")
        return value


class MarketInstrumentSectorSnapshotData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    sectors: list[InstrumentSectorEntry]

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketInstrumentSectorSnapshotData:
        _validate_sector_instrument(self.instrument_id)
        ids: set[tuple[str, str]] = set()
        for entry in self.sectors:
            key = (entry.provider_namespace, entry.provider_sector_id)
            if key in ids:
                raise ValueError("sector snapshot contains a duplicate provider sector id")
            ids.add(key)
        return self


MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET = DatasetDefinition(
    name="market.instrument_sector_snapshot",
    schema_version="1.0",
    request_type=MarketInstrumentSectorSnapshotRequest,
    data_type=MarketInstrumentSectorSnapshotData,
)


@dataclass(frozen=True)
class _ProviderSectorEntry:
    block: Literal["area", "plate", "concept"]
    provider_sector_id: str
    name: str
    level: int | None
    tag: str | None
    change_pct_percent: Decimal | None


@dataclass(frozen=True)
class _ProviderInstrumentSectorSnapshot:
    instrument_id: InstrumentId
    entries: tuple[_ProviderSectorEntry, ...]
    source_record_id: str
    source_url: str
    captured_at: datetime


def _aware_capture_time(captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")


def normalize_instrument_sector_snapshot(
    request: MarketInstrumentSectorSnapshotRequest,
    row: _ProviderInstrumentSectorSnapshot,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, MarketInstrumentSectorSnapshotRequest):
        raise ValueError("request must be a MarketInstrumentSectorSnapshotRequest")
    _validate_sector_instrument(request.instrument_id)
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned sector data for a different instrument")
    _aware_capture_time(row.captured_at)

    type_by_block = {"area": "area", "plate": "industry", "concept": "concept"}
    entries: list[InstrumentSectorEntry] = []
    for raw in row.entries:
        sector_type = type_by_block[raw.block]
        if raw.block == "concept" and raw.name.startswith("昨日"):
            continue
        entries.append(
            InstrumentSectorEntry(
                sectorType=sector_type,
                sectorName=raw.name,
                providerNamespace="tencent_plate",
                providerSectorId=raw.provider_sector_id,
                level=raw.level,
                tag=raw.tag,
                changePct=(
                    None
                    if raw.change_pct_percent is None
                    else raw.change_pct_percent / Decimal("100")
                ),
            )
        )
    data = MarketInstrumentSectorSnapshotData(
        instrumentId=request.instrument_id,
        sectors=entries,
    )
    return StandardRecord(
        dataset=MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET.name,
        schemaVersion=MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET.schema_version,
        recordId=f"{format_symbol(request.instrument_id)}@{row.captured_at.isoformat()}",
        entityId=request.instrument_id,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url or source.source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="tencent-plate-new-sector-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )
