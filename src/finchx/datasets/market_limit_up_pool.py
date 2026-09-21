"""EastMoney limit-up pool contract and normalization."""

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
        raise ValueError("limit-up pool supports CN_A equities only")
    if instrument.exchange not in (Exchange.SSE, Exchange.SZSE):
        raise ValueError("limit-up pool requires an SSE or SZSE identity from source m")
    if len(instrument.code) != 6 or not instrument.code.isascii() or not instrument.code.isdigit():
        raise ValueError("pool instrument code must be six ASCII digits")


class MarketLimitUpPoolRequest(ContractModel):
    """Request the EastMoney limit-up pool for one source trade date."""

    trade_date: date = Field(alias="tradeDate")


class MarketLimitUpStats(ContractModel):
    lookback_days: int = Field(alias="lookbackDays", strict=True, ge=0)
    limit_up_count: int = Field(alias="limitUpCount", strict=True, ge=0)


class MarketLimitUpPoolData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    trade_date: date = Field(alias="tradeDate")
    name: str = Field(min_length=1)
    price: Price = Field(description="Latest price in CNY per share.")
    change_rate: Percentage = Field(alias="changeRate", description="Ratio fraction; 10% is 0.10.")
    amount: Amount = Field(description="Current-session traded amount in CNY.")
    float_market_capitalization: Amount = Field(alias="floatMarketCapitalization")
    market_capitalization: Amount = Field(alias="marketCapitalization")
    turnover_rate: Percentage = Field(alias="turnoverRate", description="Ratio fraction; 5% is 0.05.")
    consecutive_limit_up_days: int = Field(alias="consecutiveLimitUpDays", strict=True, ge=1)
    first_limit_up_time: str | None = Field(default=None, alias="firstLimitUpTime")
    last_limit_up_time: str | None = Field(default=None, alias="lastLimitUpTime")
    limit_up_queue_amount: Amount | None = Field(default=None, alias="limitUpQueueAmount")
    limit_up_break_count: int = Field(alias="limitUpBreakCount", strict=True, ge=0)
    industry: str = Field(min_length=1)
    limit_up_stats: MarketLimitUpStats = Field(alias="limitUpStats")

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("price must be positive")
        return value

    @field_validator("amount", "float_market_capitalization", "market_capitalization", "limit_up_queue_amount")
    @classmethod
    def monetary_values_must_be_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("monetary values must not be negative")
        return value

    @field_validator("first_limit_up_time", "last_limit_up_time")
    @classmethod
    def source_times_must_be_market_local_hhmmss(cls, value: str | None) -> str | None:
        if value is not None and not _TIME_PATTERN.fullmatch(value):
            raise ValueError("source time must be market-local HH:MM:SS")
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> MarketLimitUpPoolData:
        _validate_identity(self.instrument_id)
        return self


MARKET_LIMIT_UP_POOL_DATASET: DatasetDefinition[MarketLimitUpPoolRequest, MarketLimitUpPoolData] = DatasetDefinition(
    name="market.limit_up_pool",
    schema_version="1.0",
    request_type=MarketLimitUpPoolRequest,
    data_type=MarketLimitUpPoolData,
)


@dataclass(frozen=True)
class _ProviderLimitUpRow:
    instrument_id: InstrumentId
    trade_date: date
    name: str
    price_milli_cny: Decimal
    change_percent_points: Decimal
    amount_cny: Decimal
    float_market_cap_cny: Decimal
    market_cap_cny: Decimal
    turnover_percent_points: Decimal
    consecutive_days: int
    first_limit_up_time: str | None
    last_limit_up_time: str | None
    limit_up_queue_amount_cny: Decimal | None
    break_count: int
    industry: str
    stats_days: int
    stats_count: int
    source_record_id: str
    source_url: str
    captured_at: datetime


def normalize_market_limit_up_pool(
    request: MarketLimitUpPoolRequest,
    rows: tuple[_ProviderLimitUpRow, ...],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, MarketLimitUpPoolRequest):
        raise ValueError("request must be a MarketLimitUpPoolRequest")
    records: list[StandardRecord] = []
    for row in rows:
        if row.trade_date != request.trade_date:
            raise ValueError("provider limit-up row tradeDate does not match request")
        if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
            raise ValueError("provider returned a naive captured_at timestamp")
        _validate_identity(row.instrument_id)
        data = MarketLimitUpPoolData(
            instrumentId=row.instrument_id,
            tradeDate=row.trade_date,
            name=row.name,
            price=row.price_milli_cny / Decimal("1000"),
            changeRate=row.change_percent_points / Decimal("100"),
            amount=row.amount_cny,
            floatMarketCapitalization=row.float_market_cap_cny,
            marketCapitalization=row.market_cap_cny,
            turnoverRate=row.turnover_percent_points / Decimal("100"),
            consecutiveLimitUpDays=row.consecutive_days,
            firstLimitUpTime=row.first_limit_up_time,
            lastLimitUpTime=row.last_limit_up_time,
            limitUpQueueAmount=row.limit_up_queue_amount_cny,
            limitUpBreakCount=row.break_count,
            industry=row.industry,
            limitUpStats={"lookbackDays": row.stats_days, "limitUpCount": row.stats_count},
        )
        records.append(
            StandardRecord(
                dataset=MARKET_LIMIT_UP_POOL_DATASET.name,
                schemaVersion=MARKET_LIMIT_UP_POOL_DATASET.schema_version,
                recordId=f"eastmoney-limit-up:{row.trade_date.isoformat()}:{row.instrument_id.exchange.value}:{row.instrument_id.code}",
                entityId=row.instrument_id,
                capturedAt=row.captured_at,
                source=Source(providerId=source.provider_id, sourceRecordId=row.source_record_id, sourceUrl=row.source_url),
                status=DataStatus.LIVE,
                quality=Quality(),
                provenance=Provenance(recordClass=ProvenanceClass.STANDARDIZED, transformationVersion="eastmoney-limit-up-pool-normalizer/1"),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
