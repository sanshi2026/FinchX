"""Shared request and small helpers for Tencent F10 fundamental datasets."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from finchx.contracts import (
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    SourceReference,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.market_instrument_sector_snapshot import _validate_sector_instrument
from finchx.entities import InstrumentId, format_symbol
from pydantic import Field, model_validator


class FundamentalRequest(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> FundamentalRequest:
        _validate_sector_instrument(self.instrument_id)
        return self


def canonical_symbol(instrument_id: InstrumentId) -> str:
    return format_symbol(instrument_id)


def standardized_fundamental_record(
    *,
    request: FundamentalRequest,
    row: Any,
    source: Source,
    dataset: str,
    schema_version: str,
    transformation_version: str,
    data: dict[str, Any],
    as_of: datetime | None = None,
) -> StandardRecord:
    source_url = row.source_url or source.source_url
    source_record_id = row.source_record_id
    record_id = f"{canonical_symbol(request.instrument_id)}@{row.captured_at.isoformat()}"
    if as_of is not None:
        record_id += f"@asof={as_of.isoformat()}"
    return StandardRecord(
        dataset=dataset,
        schemaVersion=schema_version,
        recordId=record_id,
        entityId=request.instrument_id,
        asOf=as_of,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=source_record_id,
            sourceUrl=source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion=transformation_version,
            sourceReferences=[
                SourceReference(
                    providerId=source.provider_id,
                    sourceRecordId=source_record_id,
                    sourceUrl=source_url,
                )
            ],
        ),
        data=data,
    )


__all__ = ["FundamentalRequest", "canonical_symbol", "standardized_fundamental_record"]
