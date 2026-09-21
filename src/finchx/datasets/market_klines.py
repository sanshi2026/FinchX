"""The stable daily market.klines contract and record normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Sequence

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    Adjustment,
    Amount,
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
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol


class KlineAdjustment(str, Enum):
    """Public adjustment mode for daily Klines bars."""

    NONE = "none"
    QFQ = "qfq"
    HFQ = "hfq"
    NOT_APPLICABLE = "not_applicable"


_SUPPORTED_EQUITY_PREFIXES = {
    Exchange.SSE: ("60", "68"),
    Exchange.SZSE: ("00", "30"),
}
_SUPPORTED_INDEX_IDENTITIES = {
    (Exchange.SSE, "000001"),
    (Exchange.SSE, "000002"),
    (Exchange.SSE, "000688"),
    (Exchange.SZSE, "399001"),
    (Exchange.SZSE, "399006"),
    (Exchange.SZSE, "399102"),
    (Exchange.SZSE, "399107"),
}


class KlinesRequest(ContractModel):
    """Inclusive date range for one explicitly identified equity or index."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    adjustment: KlineAdjustment | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def bounds_must_be_dates_not_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime):
            raise ValueError("Klines bounds must be dates, not datetimes")
        return value

    @model_validator(mode="after")
    def validate_request_scope(self) -> KlinesRequest:
        instrument = self.instrument_id
        if instrument.market is not Market.CN_A:
            raise ValueError("market.klines currently supports only Market.CN_A")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")

        if instrument.kind is InstrumentKind.EQUITY:
            if instrument.exchange not in _SUPPORTED_EQUITY_PREFIXES:
                raise ValueError("equity klines currently support SSE and SZSE only")
            if (
                len(instrument.code) != 6
                or not instrument.code.isascii()
                or not instrument.code.isdigit()
                or not instrument.code.startswith(_SUPPORTED_EQUITY_PREFIXES[instrument.exchange])
            ):
                raise ValueError("equity code does not match its exchange identity")
            if self.adjustment is None:
                raise ValueError("equity kline requests require an adjustment")
            if self.adjustment is KlineAdjustment.NOT_APPLICABLE:
                raise ValueError("not_applicable is reserved for index kline results")
        elif instrument.kind is InstrumentKind.INDEX:
            if (instrument.exchange, instrument.code) not in _SUPPORTED_INDEX_IDENTITIES:
                raise ValueError("index klines support only the verified SSE/SZSE identities")
            if "adjustment" in self.model_fields_set:
                raise ValueError("index kline requests must omit adjustment")
        else:
            raise ValueError("market.klines currently supports only equity and index")

        return self


class MarketKlineData(ContractModel):
    """One daily Klines bar; date is the event label, not a timestamp."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    bar_date: date = Field(alias="barDate")
    open: Price
    high: Price
    low: Price
    close: Price
    volume: Shares
    amount: Amount | None = None
    adjustment: KlineAdjustment

    @field_validator("bar_date", mode="before")
    @classmethod
    def bar_date_must_not_be_datetime(cls, value: object) -> object:
        if isinstance(value, datetime):
            raise ValueError("bar_date must be a date, not a datetime")
        return value

    @model_validator(mode="after")
    def validate_bar_values(self) -> MarketKlineData:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to open, close, and high")
        if self.amount is not None and self.amount < 0:
            raise ValueError("traded amount must not be negative")
        return self


MARKET_KLINES_DATASET: DatasetDefinition[KlinesRequest, MarketKlineData] = DatasetDefinition(
    name="market.klines",
    schema_version="1.0",
    request_type=KlinesRequest,
    data_type=MarketKlineData,
)


@dataclass(frozen=True)
class _ProviderKlineRow:
    """Provider-neutral typed handoff for one daily bar."""

    data: MarketKlineData
    source_record_id: str | None = None
    captured_at: datetime | None = None
    source_url: str | None = None


def _kline_record_id(
    instrument_id: InstrumentId,
    bar_date: date,
    adjustment: KlineAdjustment,
) -> str:
    """Adjustment is part of identity because each mode is a different value."""

    return f"{format_symbol(instrument_id)}@{bar_date.isoformat()}@{adjustment.value}"


def _normalize_klines_rows(
    request: KlinesRequest,
    rows: Sequence[_ProviderKlineRow],
    *,
    source: Source,
    captured_at: datetime,
) -> tuple[StandardRecord, ...]:
    """Validate the request-bound series and produce one StandardRecord per bar."""

    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")

    expected_adjustment = (
        request.adjustment
        if request.instrument_id.kind is InstrumentKind.EQUITY
        else KlineAdjustment.NOT_APPLICABLE
    )
    seen: set[date] = set()
    for row in rows:
        if not isinstance(row, _ProviderKlineRow):
            raise ValueError("provider returned a row with an unsupported type")
        bar = row.data
        if bar.instrument_id != request.instrument_id:
            raise ValueError("provider returned a bar for a different instrument")
        if bar.adjustment is not expected_adjustment:
            raise ValueError("provider returned a bar with a different adjustment mode")
        if bar.bar_date < request.start_date or bar.bar_date > request.end_date:
            raise ValueError("provider returned a bar outside the requested date range")
        if bar.bar_date in seen:
            raise ValueError(f"provider returned duplicate bar date {bar.bar_date.isoformat()}")
        seen.add(bar.bar_date)
        if row.captured_at is not None and (
            row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None
        ):
            raise ValueError("provider returned a naive captured_at timestamp")

    records: list[StandardRecord] = []
    for row in sorted(rows, key=lambda item: item.data.bar_date):
        bar = row.data
        record_source = Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url or source.source_url,
        )
        quality = Quality(
            issues=[
                QualityIssue(
                    kind=QualityIssueKind.PARTIAL,
                    detail="amount was unavailable from the direct provider; it was not estimated",
                )
            ]
            if bar.amount is None
            else []
        )
        records.append(
            StandardRecord(
                dataset=MARKET_KLINES_DATASET.name,
                schemaVersion=MARKET_KLINES_DATASET.schema_version,
                recordId=_kline_record_id(
                    bar.instrument_id,
                    bar.bar_date,
                    bar.adjustment,
                ),
                entityId=bar.instrument_id,
                eventAt=None,
                capturedAt=row.captured_at or captured_at,
                asOf=None,
                source=record_source,
                status=DataStatus.LIVE,
                quality=quality,
                provenance=Provenance(
                    recordClass=ProvenanceClass.STANDARDIZED,
                    transformationVersion="market-klines-normalizer/1",
                    adjustments=[Adjustment(name=expected_adjustment.value)],
                ),
                data=bar.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
