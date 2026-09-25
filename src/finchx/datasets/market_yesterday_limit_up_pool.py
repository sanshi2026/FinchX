"""EastMoney yesterday-limit-up, current-performance contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import re

from pydantic import Field, field_validator, model_validator

from finchx.contracts import Amount, DataStatus, Percentage, Price, Provenance, ProvenanceClass, Quality, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


_TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$")


def _validate_identity(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A or instrument.kind is not InstrumentKind.EQUITY:
        raise ValueError("yesterday limit-up pool supports CN_A equities only")
    if instrument.exchange not in (Exchange.SSE, Exchange.SZSE):
        raise ValueError("pool identity must come from the EastMoney m exchange field")
    if len(instrument.code) != 6 or not instrument.code.isascii() or not instrument.code.isdigit():
        raise ValueError("pool instrument code must be six ASCII digits")


class MarketYesterdayLimitUpPoolRequest(ContractModel):
    """Request the latest EastMoney yesterday-limit-up pool snapshot.

    ``tradeDate`` remains an optional, deprecated construction-time field for
    callers migrating from the old request shape.  It cannot select history;
    the Provider rejects it instead of silently returning a different date.
    """

    trade_date: date | None = Field(
        default=None,
        alias="tradeDate",
        deprecated=True,
        description="Deprecated compatibility input; this Provider returns the latest snapshot and does not support historical selection.",
    )


class MarketYesterdayLimitUpPoolData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    trade_date: date = Field(alias="tradeDate", description="Current observed source date, not the prior limit-up event date.")
    name: str = Field(min_length=1)
    current_price: Price = Field(alias="currentPrice", description="Current-session price in CNY per share.")
    current_limit_up_price: Price = Field(alias="currentLimitUpPrice", description="Current-session limit-up price in CNY per share.")
    current_change_rate: Percentage = Field(alias="currentChangeRate", description="Current-session ratio fraction.")
    current_amount: Amount = Field(alias="currentAmount", description="Current-session traded amount in CNY.")
    float_market_capitalization: Amount = Field(alias="floatMarketCapitalization")
    market_capitalization: Amount = Field(alias="marketCapitalization")
    current_turnover_rate: Percentage = Field(alias="currentTurnoverRate", description="Current-session turnover ratio fraction.")
    current_amplitude: Percentage = Field(alias="currentAmplitude", description="Current-session amplitude as a ratio fraction.")
    yesterday_first_limit_up_time: str | None = Field(default=None, alias="yesterdayFirstLimitUpTime", description="Previous-session first limit-up time, market-local HH:MM:SS.")
    yesterday_consecutive_limit_up_days: int = Field(alias="yesterdayConsecutiveLimitUpDays", strict=True, ge=1)
    industry: str = Field(min_length=1)

    @field_validator("current_price", "current_limit_up_price")
    @classmethod
    def prices_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("prices must be positive")
        return value

    @field_validator("current_amount", "float_market_capitalization", "market_capitalization")
    @classmethod
    def amounts_must_be_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("amounts must not be negative")
        return value

    @field_validator("yesterday_first_limit_up_time")
    @classmethod
    def prior_time_must_be_market_local_hhmmss(cls, value: str | None) -> str | None:
        if value is not None and not _TIME_PATTERN.fullmatch(value):
            raise ValueError("prior event time must be market-local HH:MM:SS")
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> MarketYesterdayLimitUpPoolData:
        _validate_identity(self.instrument_id)
        return self


MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET: DatasetDefinition[MarketYesterdayLimitUpPoolRequest, MarketYesterdayLimitUpPoolData] = DatasetDefinition(
    name="market.yesterday_limit_up_pool",
    schema_version="1.0",
    request_type=MarketYesterdayLimitUpPoolRequest,
    data_type=MarketYesterdayLimitUpPoolData,
)


@dataclass(frozen=True)
class _ProviderYesterdayLimitUpRow:
    instrument_id: InstrumentId
    trade_date: date
    name: str
    current_price_milli_cny: Decimal
    current_limit_up_price_milli_cny: Decimal
    change_percent_points: Decimal
    amount_cny: Decimal
    float_market_cap_cny: Decimal
    market_cap_cny: Decimal
    turnover_percent_points: Decimal
    amplitude_percent_points: Decimal
    speed_raw: Decimal | None
    yesterday_first_limit_up_time: str | None
    yesterday_consecutive_days: int
    stats_days_raw: int | None
    stats_count_raw: int | None
    industry: str
    source_record_id: str
    source_url: str
    captured_at: datetime


def normalize_market_yesterday_limit_up_pool(
    request: MarketYesterdayLimitUpPoolRequest,
    rows: tuple[_ProviderYesterdayLimitUpRow, ...],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, MarketYesterdayLimitUpPoolRequest):
        raise ValueError("request must be a MarketYesterdayLimitUpPoolRequest")
    records: list[StandardRecord] = []
    for row in rows:
        if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
            raise ValueError("provider returned a naive captured_at timestamp")
        _validate_identity(row.instrument_id)
        data = MarketYesterdayLimitUpPoolData(
            instrumentId=row.instrument_id,
            tradeDate=row.trade_date,
            name=row.name,
            currentPrice=row.current_price_milli_cny / Decimal("1000"),
            currentLimitUpPrice=row.current_limit_up_price_milli_cny / Decimal("1000"),
            currentChangeRate=row.change_percent_points / Decimal("100"),
            currentAmount=row.amount_cny,
            floatMarketCapitalization=row.float_market_cap_cny,
            marketCapitalization=row.market_cap_cny,
            currentTurnoverRate=row.turnover_percent_points / Decimal("100"),
            currentAmplitude=row.amplitude_percent_points / Decimal("100"),
            yesterdayFirstLimitUpTime=row.yesterday_first_limit_up_time,
            yesterdayConsecutiveLimitUpDays=row.yesterday_consecutive_days,
            industry=row.industry,
        )
        records.append(
            StandardRecord(
                dataset=MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET.name,
                schemaVersion=MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET.schema_version,
                recordId=f"eastmoney-yesterday-limit-up:{row.trade_date.isoformat()}:{row.instrument_id.exchange.value}:{row.instrument_id.code}",
                entityId=row.instrument_id,
                capturedAt=row.captured_at,
                source=Source(providerId=source.provider_id, sourceRecordId=row.source_record_id, sourceUrl=row.source_url),
                status=DataStatus.LIVE,
                quality=Quality(),
                provenance=Provenance(recordClass=ProvenanceClass.STANDARDIZED, transformationVersion="eastmoney-yesterday-limit-up-pool-normalizer/1"),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
