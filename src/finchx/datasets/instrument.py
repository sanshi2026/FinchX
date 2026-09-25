"""The stable Instrument dataset contract and provider-row normalization."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Sequence

from pydantic import Field

from finchx.contracts import (
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import (
    InstrumentId,
    InstrumentKind,
    Market,
    format_symbol,
    normalize_symbol,
)


class InstrumentUniverse(str, Enum):
    """Source-neutral instrument listing scope supported by FinchX."""

    CN_A_SHARE = "cn_a_share"


class InstrumentRequest(ContractModel):
    """Request one instrument by its complete, already-normalized identity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")


class InstrumentUniverseRequest(ContractModel):
    """Request the canonical instrument rows in one declared universe."""

    universe: InstrumentUniverse


class InstrumentData(ContractModel):
    """Provider-neutral instrument payload for the instrument dataset."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str = Field(min_length=1, pattern=r".*\S.*")


INSTRUMENT_DATASET: DatasetDefinition[InstrumentRequest, InstrumentData] = DatasetDefinition(
    name="instrument",
    schema_version="1.0",
    request_type=InstrumentRequest,
    data_type=InstrumentData,
)


@dataclass(frozen=True)
class _ProviderInstrumentRow:
    """Small internal handoff from a provider adapter to dataset normalization."""

    code: str
    market: str
    exchange: str | None
    kind: str
    name: str
    source_record_id: str | None = None
    captured_at: datetime | None = None


def _standardized_instrument_record(
    instrument_id: InstrumentId,
    name: str,
    *,
    source: Source,
    source_record_id: str | None,
    captured_at: datetime,
) -> StandardRecord:
    payload = InstrumentData(instrumentId=instrument_id, name=name)
    record_source = Source(
        providerId=source.provider_id,
        sourceRecordId=source_record_id,
        sourceUrl=source.source_url,
    )
    return StandardRecord(
        dataset=INSTRUMENT_DATASET.name,
        schemaVersion=INSTRUMENT_DATASET.schema_version,
        recordId=format_symbol(instrument_id),
        entityId=instrument_id,
        capturedAt=captured_at,
        source=record_source,
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="instrument-normalizer/1",
        ),
        data=payload.model_dump(mode="json", by_alias=True),
    )


def _provider_row_identity(row: _ProviderInstrumentRow) -> InstrumentId:
    return normalize_symbol(
        row.code,
        market=row.market,
        exchange=row.exchange,
        kind=row.kind,
    )


def _normalize_provider_rows(
    request: InstrumentRequest,
    rows: Sequence[_ProviderInstrumentRow],
    *,
    source: Source,
    captured_at: datetime,
) -> tuple[StandardRecord, ...]:
    """Turn parsed provider rows into stable records for an exact lookup."""

    if len(rows) > 1:
        raise ValueError("provider returned multiple rows for an exact instrument request")

    records: list[StandardRecord] = []
    for row in rows:
        instrument_id = _provider_row_identity(row)
        if instrument_id != request.instrument_id:
            raise ValueError("provider returned an instrument outside the explicit request")
        records.append(
            _standardized_instrument_record(
                instrument_id,
                row.name,
                source=source,
                source_record_id=row.source_record_id,
                captured_at=row.captured_at or captured_at,
            )
        )
    return tuple(records)


def _normalize_listing_provider_rows(
    request: InstrumentUniverseRequest,
    rows: Sequence[_ProviderInstrumentRow],
    *,
    source: Source,
    captured_at: datetime,
) -> tuple[StandardRecord, ...]:
    """Normalize a listing as independent instrument records under one Dataset identity."""

    if request.universe is not InstrumentUniverse.CN_A_SHARE:
        raise ValueError(f"unsupported instrument universe: {request.universe!r}")

    records: list[StandardRecord] = []
    seen: set[str] = set()
    for row in rows:
        instrument_id = _provider_row_identity(row)
        if instrument_id.market is not Market.CN_A or instrument_id.kind is not InstrumentKind.EQUITY:
            raise ValueError("CN_A_SHARE listing contains a non-A-share-equity identity")
        identity_key = format_symbol(instrument_id)
        if identity_key in seen:
            raise ValueError(f"instrument listing contains duplicate identity: {identity_key}")
        seen.add(identity_key)
        records.append(
            _standardized_instrument_record(
                instrument_id,
                row.name,
                source=source,
                source_record_id=row.source_record_id,
                captured_at=row.captured_at or captured_at,
            )
        )
    return tuple(records)
