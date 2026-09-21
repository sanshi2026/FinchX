"""Single-instrument equity orderbook contract and normalization."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    DataStatus,
    Price,
    Provenance,
    ProvenanceClass,
    Quality,
    QualityIssue,
    QualityIssueKind,
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
    """One non-empty price level; size is a whole number of shares."""

    level: int = Field(strict=True, ge=1, le=5)
    price: Price
    size: Shares = Field(gt=0)

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("orderbook level price must be positive")
        return value


class MarketOrderbookData(ContractModel):
    """Up to five best-to-worse bid and ask levels for an equity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    bids: list[OrderbookLevel] = Field(max_length=5)
    asks: list[OrderbookLevel] = Field(max_length=5)

    @model_validator(mode="after")
    def validate_book(self) -> MarketOrderbookData:
        _validate_supported_equity(self.instrument_id)
        if any(left.price < right.price for left, right in zip(self.bids, self.bids[1:])):
            raise ValueError("bids must be ordered from highest price to lowest")
        if any(left.price > right.price for left, right in zip(self.asks, self.asks[1:])):
            raise ValueError("asks must be ordered from lowest price to highest")
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

    omitted = False

    def normalized_levels(raw_levels, *, bids: bool) -> list[OrderbookLevel]:
        nonlocal omitted
        levels: list[OrderbookLevel] = []
        for raw in raw_levels:
            if raw.price is None or raw.size_hands is None:
                omitted = True
                continue
            if raw.price < 0 or raw.size_hands < 0:
                raise ValueError("provider returned a negative orderbook slot")
            if raw.price == 0 or raw.size_hands == 0:
                omitted = True
                continue
            shares = raw.size_hands * 100
            if shares != shares.to_integral_value():
                raise ValueError("orderbook size does not normalize to whole shares")
            levels.append(
                OrderbookLevel(
                    level=raw.level,
                    price=raw.price,
                    size=int(shares),
                )
            )
        return sorted(levels, key=lambda level: (-level.price if bids else level.price, level.level))

    data = MarketOrderbookData(
        instrumentId=row.instrument_id,
        bids=normalized_levels(row.bids, bids=True),
        asks=normalized_levels(row.asks, bids=False),
    )
    has_levels = bool(data.bids or data.asks)
    issues = (
        [
            QualityIssue(
                kind=QualityIssueKind.PARTIAL,
                detail="Zero or unavailable source depth slots were omitted.",
            )
        ]
        if omitted and has_levels
        else []
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
        status=DataStatus.LIVE if has_levels else DataStatus.MISSING,
        quality=Quality(issues=issues),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="market-orderbook-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )
