"""EastMoney stock hot-keyword dataset contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

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
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol


_SUPPORTED_EQUITY_PREFIXES = {
    Exchange.SSE: ("60", "68"),
    Exchange.SZSE: ("00", "30"),
    Exchange.BSE: ("4", "8", "9"),
}


def _validate_stock_keyword_instrument(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A:
        raise ValueError("EastMoney stock keyword datasets support only Market.CN_A")
    prefixes = _SUPPORTED_EQUITY_PREFIXES.get(instrument.exchange)
    if instrument.kind is not InstrumentKind.EQUITY or prefixes is None:
        raise ValueError("EastMoney stock keyword datasets support CN_A equities with an explicit SSE/SZSE/BSE exchange")
    if (
        len(instrument.code) != 6
        or not instrument.code.isascii()
        or not instrument.code.isdigit()
        or not instrument.code.startswith(prefixes)
    ):
        raise ValueError("equity code does not match its explicit SSE/SZSE/BSE identity")


class MarketStockKeywordRequest(ContractModel):
    """Request one source-provided hot-keyword observation for an equity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketStockKeywordRequest:
        _validate_stock_keyword_instrument(self.instrument_id)
        return self


class StockKeywordEntry(ContractModel):
    """One EastMoney source-ranked keyword/concept relationship."""

    keyword_name: str = Field(alias="keywordName", min_length=1, pattern=r".*\S.*")
    provider_namespace: Literal["eastmoney_stockrank"] = Field(alias="providerNamespace")
    provider_keyword_id: str = Field(alias="providerKeywordId", min_length=1, pattern=r".*\S.*")
    hit_count: int = Field(alias="hitCount", ge=0)
    calculated_at: datetime = Field(alias="calculatedAt")

    @field_validator("provider_keyword_id")
    @classmethod
    def provider_id_must_not_contain_whitespace(cls, value: str) -> str:
        if any(character.isspace() for character in value):
            raise ValueError("providerKeywordId must not contain whitespace")
        return value

    @field_validator("calculated_at")
    @classmethod
    def calculated_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("calculatedAt must include a timezone offset")
        return value


class MarketStockKeywordData(ContractModel):
    """Stable public payload for one stock's current hot-keyword snapshot."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    keywords: list[StockKeywordEntry]

    @model_validator(mode="after")
    def validate_data(self) -> MarketStockKeywordData:
        _validate_stock_keyword_instrument(self.instrument_id)
        identities: set[tuple[str, str]] = set()
        for keyword in self.keywords:
            identity = (keyword.provider_namespace, keyword.provider_keyword_id)
            if identity in identities:
                raise ValueError("stock keyword data contains a duplicate provider keyword id")
            identities.add(identity)
        return self


MARKET_STOCK_KEYWORD_DATASET = DatasetDefinition(
    name="market.stock_keyword",
    schema_version="1.0",
    request_type=MarketStockKeywordRequest,
    data_type=MarketStockKeywordData,
)


@dataclass(frozen=True)
class _ProviderStockKeywordEntry:
    keyword_name: str
    provider_keyword_id: str
    hit_count: int
    calculated_at: datetime


@dataclass(frozen=True)
class _ProviderStockKeywordSnapshot:
    instrument_id: InstrumentId
    entries: tuple[_ProviderStockKeywordEntry, ...]
    source_record_id: str
    source_url: str
    captured_at: datetime


def normalize_stock_keyword(
    request: MarketStockKeywordRequest,
    row: _ProviderStockKeywordSnapshot,
    *,
    source: Source,
) -> StandardRecord:
    """Normalize Provider output without changing source time semantics."""

    if not isinstance(request, MarketStockKeywordRequest):
        raise ValueError("request must be a MarketStockKeywordRequest")
    _validate_stock_keyword_instrument(request.instrument_id)
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned stock keyword data for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")

    data = MarketStockKeywordData(
        instrumentId=request.instrument_id,
        keywords=[
            StockKeywordEntry(
                keywordName=entry.keyword_name,
                providerNamespace="eastmoney_stockrank",
                providerKeywordId=entry.provider_keyword_id,
                hitCount=entry.hit_count,
                calculatedAt=entry.calculated_at,
            )
            for entry in row.entries
        ],
    )
    return StandardRecord(
        dataset=MARKET_STOCK_KEYWORD_DATASET.name,
        schemaVersion=MARKET_STOCK_KEYWORD_DATASET.schema_version,
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
            transformationVersion="eastmoney-stockrank-keyword-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "MARKET_STOCK_KEYWORD_DATASET",
    "MarketStockKeywordData",
    "MarketStockKeywordRequest",
    "StockKeywordEntry",
    "normalize_stock_keyword",
]
