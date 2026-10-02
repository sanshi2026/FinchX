"""Single-instrument equity orderbook contract and normalization."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    DataStatus,
    Price,
    Provenance,
    ProvenanceClass,
    Quality,
    Shares,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.market_quote_snapshot import (
    _ProviderQuoteSnapshotRow,
    _validate_supported_equity,
)
from finchx.entities import InstrumentId, format_symbol


class MarketOrderbookRequest(ContractModel):
    """Request the current five-level book for one SSE or SZSE equity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketOrderbookRequest:
        try:
            _validate_supported_equity(self.instrument_id)
        except ValueError as exc:
            raise ValueError(
                "market.orderbook capability supports SSE/SZSE equities only; indices have no five-level book"
            ) from exc
        return self


class OrderbookLevel(ContractModel):
    """One Tencent source slot with nullable price and whole-share size."""

    level: int = Field(
        strict=True,
        ge=1,
        le=5,
        description="Original Tencent source level number (1 through 5).",
    )
    price: Price | None = Field(
        description="Source price in CNY per share; null means Tencent supplied no value.",
        json_schema_extra={"pattern": r"^(?:0|[1-9]\d*)(?:\.\d+)?$"},
    )
    size: Shares | None = Field(
        description=(
            "Source quantity converted to whole shares (Tencent hands × 100); "
            "null means Tencent supplied no value."
        ),
    )

    @field_validator("price")
    @classmethod
    def price_must_be_non_negative(cls, value):
        if value is not None and value < 0:
            raise ValueError("orderbook level price must not be negative")
        return value


class MarketOrderbookData(ContractModel):
    """Tencent's five bid and ask source slots in their original level order."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    bids: list[OrderbookLevel] = Field(
        min_length=5,
        max_length=5,
        description="Five source bid slots in original order; zero and null values are retained.",
    )
    asks: list[OrderbookLevel] = Field(
        min_length=5,
        max_length=5,
        description="Five source ask slots in original order; zero and null values are retained.",
    )
    source_timestamp: datetime = Field(
        alias="sourceTimestamp",
        description=(
            "Tencent-reported quote time in Shanghai time (UTC+08:00), "
            "separate from capturedAt."
        ),
    )

    @field_validator("source_timestamp")
    @classmethod
    def source_timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source_timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_book(self) -> MarketOrderbookData:
        _validate_supported_equity(self.instrument_id)
        for side, levels in (("bids", self.bids), ("asks", self.asks)):
            if len({level.level for level in levels}) != len(levels):
                raise ValueError(f"{side} cannot repeat a source level number")
        return self


MARKET_ORDERBOOK_DATASET: DatasetDefinition[MarketOrderbookRequest, MarketOrderbookData] = (
    DatasetDefinition(
        name="market.orderbook",
        schema_version="1.0",
        request_type=MarketOrderbookRequest,
        data_type=MarketOrderbookData,
    )
)


def _normalize_orderbook_row(
    request: MarketOrderbookRequest,
    row: _ProviderQuoteSnapshotRow,
    *,
    source: Source,
) -> StandardRecord:
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned an orderbook for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")

    def normalized_levels(raw_levels) -> list[OrderbookLevel]:
        if len(raw_levels) != 5:
            raise ValueError("provider must return exactly five source book slots per side")
        levels: list[OrderbookLevel] = []
        for raw in raw_levels:
            if raw.price is not None:
                if not raw.price.is_finite() or raw.price < 0:
                    raise ValueError("provider returned an invalid or negative orderbook price")
            if raw.size_hands is not None:
                if (
                    not raw.size_hands.is_finite()
                    or raw.size_hands < 0
                ):
                    raise ValueError("provider returned an invalid or negative orderbook size")
                shares = raw.size_hands * Decimal("100")
                if shares != shares.to_integral_value():
                    raise ValueError("orderbook size does not normalize to whole shares")
            else:
                shares = None
            levels.append(
                OrderbookLevel(
                    level=raw.level,
                    price=raw.price,
                    size=int(shares) if shares is not None else None,
                )
            )
        return levels

    bids = normalized_levels(row.bids)
    asks = normalized_levels(row.asks)

    data = MarketOrderbookData(
        instrumentId=row.instrument_id,
        bids=bids,
        asks=asks,
        sourceTimestamp=row.source_timestamp,
    )
    has_values = any(
        level.price is not None or level.size is not None
        for level in (*data.bids, *data.asks)
    )
    timestamp = row.source_timestamp.isoformat()
    return StandardRecord(
        dataset=MARKET_ORDERBOOK_DATASET.name,
        schemaVersion=MARKET_ORDERBOOK_DATASET.schema_version,
        recordId=f"{format_symbol(row.instrument_id)}@{timestamp}",
        entityId=row.instrument_id,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url,
        ),
        status=DataStatus.LIVE if has_values else DataStatus.MISSING,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="market-orderbook-normalizer/2",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )
