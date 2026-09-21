"""Aigupiao consecutive-limit-up snapshot contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import re

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    Percentage,
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
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol


_TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
_SUPPORTED_EXCHANGES = {Exchange.SSE, Exchange.SZSE, Exchange.BSE}


def _validate_instrument(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A or instrument.kind is not InstrumentKind.EQUITY:
        raise ValueError("consecutive-limit-up snapshot supports CN_A equities only")
    if instrument.exchange not in _SUPPORTED_EXCHANGES:
        raise ValueError("consecutive-limit-up snapshot requires an explicit SSE, SZSE, or BSE identity")
    if len(instrument.code) != 6 or not instrument.code.isascii() or not instrument.code.isdigit():
        raise ValueError("consecutive-limit-up instrument code must be six ASCII digits")


class MarketConsecutiveLimitUpRequest(ContractModel):
    """Request the current Aigupiao consecutive-limit-up snapshot."""


class MarketConsecutiveLimitUpData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str = Field(min_length=1)
    trade_date: date = Field(alias="tradeDate")
    last_price: Price = Field(alias="lastPrice")
    change: Price = Field(description="Signed price change in CNY per share.")
    change_ratio: Percentage = Field(alias="changeRatio", description="Ratio fraction; 10% is 0.10.")
    turnover_ratio: Percentage = Field(alias="turnoverRatio", description="Ratio fraction; 12% is 0.12.")
    amount: Amount
    limit_up_time: str = Field(alias="limitUpTime", pattern=_TIME_PATTERN.pattern)
    state: str = Field(min_length=1)
    is_consecutive_limit_up: bool = Field(alias="isConsecutiveLimitUp")
    consecutive_limit_up_count: int | None = Field(default=None, alias="consecutiveLimitUpCount", ge=1)
    previous_consecutive_limit_up_count: int | None = Field(
        default=None,
        alias="previousConsecutiveLimitUpCount",
        ge=0,
    )
    theme_id: int | None = Field(default=None, alias="themeId", strict=True)
    theme_name: str | None = Field(default=None, alias="themeName")
    float_shares: Shares = Field(alias="floatShares")
    total_shares: Shares = Field(alias="totalShares")
    market_cap: Amount = Field(alias="marketCap", description="Total market capitalization in CNY.")

    @field_validator("last_price")
    @classmethod
    def last_price_must_be_nonnegative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("last price must not be negative")
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> MarketConsecutiveLimitUpData:
        _validate_instrument(self.instrument_id)
        return self


MARKET_CONSECUTIVE_LIMIT_UP_DATASET: DatasetDefinition[
    MarketConsecutiveLimitUpRequest, MarketConsecutiveLimitUpData
] = DatasetDefinition(
    name="market.consecutive_limit_up_snapshot",
    schema_version="1.0",
    request_type=MarketConsecutiveLimitUpRequest,
    data_type=MarketConsecutiveLimitUpData,
)


@dataclass(frozen=True)
class _ProviderConsecutiveLimitUpRow:
    instrument_id: InstrumentId
    name: str
    trade_date: date
    last_price: Decimal
    change: Decimal
    change_percent_points: Decimal
    turnover_percent_points: Decimal
    amount_cny: Decimal
    limit_up_time: str
    source_series_limit_up: int
    is_consecutive_limit_up: bool
    state: str
    previous_consecutive_limit_up_count: int
    theme_id: int | None
    theme_name: str | None
    float_shares: int
    total_shares: int
    market_cap_100m_cny: Decimal
    raw_payload: dict[str, object]
    source_record_id: str
    source_url: str
    captured_at: datetime


def normalize_market_consecutive_limit_up(
    request: MarketConsecutiveLimitUpRequest,
    rows: tuple[_ProviderConsecutiveLimitUpRow, ...],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, MarketConsecutiveLimitUpRequest):
        raise ValueError("request must be a MarketConsecutiveLimitUpRequest")
    if not rows:
        return ()
    records: list[StandardRecord] = []
    seen: set[str] = set()
    for row in rows:
        _validate_instrument(row.instrument_id)
        if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
            raise ValueError("provider returned a naive captured_at timestamp")
        identity = format_symbol(row.instrument_id)
        if identity in seen:
            raise ValueError(f"provider returned a duplicate consecutive-limit-up instrument: {identity}")
        seen.add(identity)
        if row.limit_up_time and not _TIME_PATTERN.fullmatch(row.limit_up_time):
            raise ValueError("provider returned an invalid source limit-up time")
        consecutive_count = None
        match = re.fullmatch(r"([1-9][0-9]*)连板", row.state)
        if match and row.is_consecutive_limit_up:
            consecutive_count = int(match.group(1))
        data = MarketConsecutiveLimitUpData(
            instrumentId=row.instrument_id,
            name=row.name,
            tradeDate=row.trade_date,
            lastPrice=row.last_price,
            change=row.change,
            changeRatio=row.change_percent_points / Decimal("100"),
            turnoverRatio=row.turnover_percent_points / Decimal("100"),
            amount=row.amount_cny,
            limitUpTime=row.limit_up_time,
            state=row.state,
            isConsecutiveLimitUp=row.is_consecutive_limit_up,
            consecutiveLimitUpCount=consecutive_count,
            previousConsecutiveLimitUpCount=row.previous_consecutive_limit_up_count,
            themeId=row.theme_id,
            themeName=row.theme_name,
            floatShares=row.float_shares,
            totalShares=row.total_shares,
            marketCap=row.market_cap_100m_cny * Decimal("100000000"),
        )
        event_at = datetime.combine(row.trade_date, datetime.strptime(row.limit_up_time, "%H:%M").time()).replace(
            tzinfo=timezone(timedelta(hours=8))
        )
        records.append(
            StandardRecord(
                dataset=MARKET_CONSECUTIVE_LIMIT_UP_DATASET.name,
                schemaVersion=MARKET_CONSECUTIVE_LIMIT_UP_DATASET.schema_version,
                recordId=f"aigupiao-consecutive-limit-up:{row.trade_date.isoformat()}:{row.instrument_id.exchange.value}:{row.instrument_id.code}",
                entityId=row.instrument_id,
                eventAt=event_at,
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
                    transformationVersion="aigupiao-consecutive-limit-up-normalizer/1",
                ),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)


__all__ = [
    "MARKET_CONSECUTIVE_LIMIT_UP_DATASET",
    "MarketConsecutiveLimitUpData",
    "MarketConsecutiveLimitUpRequest",
    "normalize_market_consecutive_limit_up",
]
