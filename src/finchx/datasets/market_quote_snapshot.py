"""Single-instrument current quote snapshot contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    Percentage,
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
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol

_SUPPORTED_EQUITY_PREFIXES = {
    Exchange.SSE: ("60", "68"),
    Exchange.SZSE: ("00", "30"),
}
_SUPPORTED_INDEX_IDENTITIES = {
    (Exchange.SSE, "000001"),
    (Exchange.SZSE, "399001"),
    (Exchange.SZSE, "399006"),
}


def _validate_supported_equity(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A:
        raise ValueError("market quote datasets currently support only Market.CN_A")
    prefixes = _SUPPORTED_EQUITY_PREFIXES.get(instrument.exchange)
    if instrument.kind is not InstrumentKind.EQUITY or prefixes is None:
        raise ValueError("equity quote datasets support SSE and SZSE equities only")
    if (
        len(instrument.code) != 6
        or not instrument.code.isascii()
        or not instrument.code.isdigit()
        or not instrument.code.startswith(prefixes)
    ):
        raise ValueError("equity code does not match its explicit SSE/SZSE identity")


def _validate_snapshot_instrument(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A:
        raise ValueError("market.quote_snapshot currently supports only Market.CN_A")
    if instrument.kind is InstrumentKind.EQUITY:
        _validate_supported_equity(instrument)
        return
    if instrument.kind is InstrumentKind.INDEX:
        if (instrument.exchange, instrument.code) not in _SUPPORTED_INDEX_IDENTITIES:
            raise ValueError("index quote snapshots support only verified SSE/SZSE identities")
        return
    raise ValueError("market.quote_snapshot currently supports equity and index")


class MarketQuoteSnapshotRequest(ContractModel):
    """Request the current quote for one complete, explicit instrument identity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketQuoteSnapshotRequest:
        _validate_snapshot_instrument(self.instrument_id)
        return self


class MarketQuoteSnapshotData(ContractModel):
    """A single current quote snapshot; monetary values use CNY and volume uses shares."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    price: Price = Field(description="Latest price in CNY per share.")
    previous_close: Price | None = Field(default=None, alias="previousClose")
    open: Price | None = Field(default=None, description="Session open in CNY per share.")
    high: Price | None = Field(default=None, description="Session high in CNY per share.")
    low: Price | None = Field(default=None, description="Session low in CNY per share.")
    price_change: Price | None = Field(default=None, alias="priceChange")
    change_rate: Percentage | None = Field(
        default=None,
        alias="changeRate",
        description="Change from previous close as a ratio fraction; 3% is 0.03.",
    )
    volume: Shares | None = Field(default=None, description="Cumulative session volume in shares.")
    amount: Amount | None = Field(default=None, description="Cumulative session amount in CNY.")
    source_timestamp: datetime = Field(
        alias="sourceTimestamp",
        description="Source-reported quote time, separate from FinchX capturedAt.",
    )

    @field_validator("price", "previous_close", "open", "high", "low")
    @classmethod
    def non_change_prices_must_not_be_negative(cls, value):
        if value is not None and value < 0:
            raise ValueError("quote prices must not be negative")
        return value

    @field_validator("amount")
    @classmethod
    def amount_must_not_be_negative(cls, value):
        if value is not None and value < 0:
            raise ValueError("quote amount must not be negative")
        return value

    @field_validator("source_timestamp")
    @classmethod
    def source_timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source_timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketQuoteSnapshotData:
        _validate_snapshot_instrument(self.instrument_id)
        return self


MARKET_QUOTE_SNAPSHOT_DATASET: DatasetDefinition[
    MarketQuoteSnapshotRequest, MarketQuoteSnapshotData
] = DatasetDefinition(
    name="market.quote_snapshot",
    schema_version="1.0",
    request_type=MarketQuoteSnapshotRequest,
    data_type=MarketQuoteSnapshotData,
)


@dataclass(frozen=True)
class _ProviderRawBookLevel:
    """One parsed Tencent depth slot before its hand-to-share conversion."""

    level: int
    price: Decimal | None
    size_hands: Decimal | None


@dataclass(frozen=True)
class _ProviderQuoteSnapshotRow:
    """Typed Tencent quote result shared by the quote and orderbook normalizers."""

    instrument_id: InstrumentId
    price: Decimal
    previous_close: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    price_change: Decimal | None
    change_rate_percent_points: Decimal | None
    volume_hands: Decimal | None
    amount_ten_thousand_cny: Decimal | None
    source_timestamp: datetime
    bids: tuple[_ProviderRawBookLevel, ...]
    asks: tuple[_ProviderRawBookLevel, ...]
    source_record_id: str
    source_url: str
    captured_at: datetime


def _snapshot_record_id(instrument_id: InstrumentId, source_timestamp: datetime) -> str:
    return f"{format_symbol(instrument_id)}@{source_timestamp.isoformat()}"


def _normalize_quote_snapshot_row(
    request: MarketQuoteSnapshotRequest,
    row: _ProviderQuoteSnapshotRow,
    *,
    source: Source,
) -> StandardRecord:
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned a quote for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    _validate_snapshot_instrument(row.instrument_id)

    volume = None
    if row.volume_hands is not None:
        if row.volume_hands < 0:
            raise ValueError("provider returned a negative source volume")
        shares = row.volume_hands * Decimal("100")
        if shares != shares.to_integral_value():
            raise ValueError("provider volume does not normalize to whole shares")
        volume = int(shares)

    amount = None
    if row.amount_ten_thousand_cny is not None:
        if row.amount_ten_thousand_cny < 0:
            raise ValueError("provider returned a negative source amount")
        amount = row.amount_ten_thousand_cny * Decimal("10000")

    change_rate = (
        row.change_rate_percent_points / Decimal("100")
        if row.change_rate_percent_points is not None
        else None
    )
    data = MarketQuoteSnapshotData(
        instrumentId=row.instrument_id,
        price=row.price,
        previousClose=row.previous_close,
        open=row.open,
        high=row.high,
        low=row.low,
        priceChange=row.price_change,
        changeRate=change_rate,
        volume=volume,
        amount=amount,
        sourceTimestamp=row.source_timestamp,
    )
    missing = [
        alias
        for alias, value in (
            ("previousClose", data.previous_close),
            ("open", data.open),
            ("high", data.high),
            ("low", data.low),
            ("priceChange", data.price_change),
            ("changeRate", data.change_rate),
            ("volume", data.volume),
            ("amount", data.amount),
        )
        if value is None
    ]
    return StandardRecord(
        dataset=MARKET_QUOTE_SNAPSHOT_DATASET.name,
        schemaVersion=MARKET_QUOTE_SNAPSHOT_DATASET.schema_version,
        recordId=_snapshot_record_id(row.instrument_id, row.source_timestamp),
        entityId=row.instrument_id,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(
            issues=[
                QualityIssue(
                    kind=QualityIssueKind.PARTIAL,
                    detail=f"Optional quote fields unavailable: {', '.join(missing)}",
                )
            ]
            if missing
            else []
        ),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="market-quote-snapshot-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )
