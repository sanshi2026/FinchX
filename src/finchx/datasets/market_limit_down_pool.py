"""EastMoney limit-down pool contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import re

from pydantic import Field, field_validator, model_validator

from finchx.contracts import Amount, DataStatus, Percentage, Price, Provenance, ProvenanceClass, Quality, Source, StandardRecord, ValuationMultiple
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


_TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$")


def _validate_identity(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A or instrument.kind is not InstrumentKind.EQUITY:
        raise ValueError("limit-down pool supports CN_A equities only")
    if instrument.exchange not in (Exchange.SSE, Exchange.SZSE):
        raise ValueError("limit-down pool requires an SSE or SZSE identity from source m")
    if len(instrument.code) != 6 or not instrument.code.isascii() or not instrument.code.isdigit():
        raise ValueError("pool instrument code must be six ASCII digits")


class MarketLimitDownPoolRequest(ContractModel):
    """Request the EastMoney limit-down pool for one source trade date."""

    trade_date: date = Field(alias="tradeDate")


class MarketLimitDownPoolData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    trade_date: date = Field(alias="tradeDate")
    name: str = Field(min_length=1)
    price: Price = Field(description="Latest price in CNY per share.")
    change_rate: Percentage = Field(alias="changeRate", description="Ratio fraction; -10% is -0.10.")
    amount: Amount = Field(description="Current-session traded amount in CNY.")
    float_market_capitalization: Amount = Field(alias="floatMarketCapitalization")
    market_capitalization: Amount = Field(alias="marketCapitalization")
    price_earnings_ratio: ValuationMultiple | None = Field(default=None, alias="priceEarningsRatio", description="EastMoney-reported dynamic P/E; source calculation details are unspecified.")
    turnover_rate: Percentage = Field(alias="turnoverRate", description="Ratio fraction.")
    limit_down_queue_amount: Amount | None = Field(default=None, alias="limitDownQueueAmount", description="EastMoney-reported limit-down queued amount in CNY.")
    last_limit_down_time: str | None = Field(default=None, alias="lastLimitDownTime")
    board_traded_amount: Amount | None = Field(default=None, alias="boardTradedAmount", description="Amount traded at the limit-down price in CNY.")
    consecutive_limit_down_days: int = Field(alias="consecutiveLimitDownDays", strict=True, ge=1)
    limit_down_open_count: int = Field(alias="limitDownOpenCount", strict=True, ge=0)
    industry: str = Field(min_length=1)

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("price must be positive")
        return value

    @field_validator("amount", "float_market_capitalization", "market_capitalization", "limit_down_queue_amount", "board_traded_amount")
    @classmethod
    def monetary_values_must_be_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("monetary values must not be negative")
        return value

    @field_validator("last_limit_down_time")
    @classmethod
    def source_time_must_be_market_local_hhmmss(cls, value: str | None) -> str | None:
        if value is not None and not _TIME_PATTERN.fullmatch(value):
            raise ValueError("source time must be market-local HH:MM:SS")
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> MarketLimitDownPoolData:
        _validate_identity(self.instrument_id)
        return self


MARKET_LIMIT_DOWN_POOL_DATASET: DatasetDefinition[MarketLimitDownPoolRequest, MarketLimitDownPoolData] = DatasetDefinition(
    name="market.limit_down_pool",
    schema_version="1.0",
    request_type=MarketLimitDownPoolRequest,
    data_type=MarketLimitDownPoolData,
)


@dataclass(frozen=True)
class _ProviderLimitDownRow:
    instrument_id: InstrumentId
    trade_date: date
    name: str
    price_milli_cny: Decimal
    change_percent_points: Decimal
    amount_cny: Decimal
    float_market_cap_cny: Decimal
    market_cap_cny: Decimal
    price_earnings_ratio: Decimal | None
    turnover_percent_points: Decimal
    limit_down_queue_amount_cny: Decimal | None
    last_limit_down_time: str | None
    board_traded_amount_cny: Decimal | None
    consecutive_days: int
    open_count: int
    industry: str
    source_record_id: str
    source_url: str
    captured_at: datetime


def normalize_market_limit_down_pool(
    request: MarketLimitDownPoolRequest,
    rows: tuple[_ProviderLimitDownRow, ...],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, MarketLimitDownPoolRequest):
        raise ValueError("request must be a MarketLimitDownPoolRequest")
    records: list[StandardRecord] = []
    for row in rows:
        if row.trade_date != request.trade_date:
            raise ValueError("provider limit-down row tradeDate does not match request")
        if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
            raise ValueError("provider returned a naive captured_at timestamp")
        _validate_identity(row.instrument_id)
        data = MarketLimitDownPoolData(
            instrumentId=row.instrument_id,
            tradeDate=row.trade_date,
            name=row.name,
            price=row.price_milli_cny / Decimal("1000"),
            changeRate=row.change_percent_points / Decimal("100"),
            amount=row.amount_cny,
            floatMarketCapitalization=row.float_market_cap_cny,
            marketCapitalization=row.market_cap_cny,
            priceEarningsRatio=row.price_earnings_ratio,
            turnoverRate=row.turnover_percent_points / Decimal("100"),
            limitDownQueueAmount=row.limit_down_queue_amount_cny,
            lastLimitDownTime=row.last_limit_down_time,
            boardTradedAmount=row.board_traded_amount_cny,
            consecutiveLimitDownDays=row.consecutive_days,
            limitDownOpenCount=row.open_count,
            industry=row.industry,
        )
        records.append(
            StandardRecord(
                dataset=MARKET_LIMIT_DOWN_POOL_DATASET.name,
                schemaVersion=MARKET_LIMIT_DOWN_POOL_DATASET.schema_version,
                recordId=f"eastmoney-limit-down:{row.trade_date.isoformat()}:{row.instrument_id.exchange.value}:{row.instrument_id.code}",
                entityId=row.instrument_id,
                capturedAt=row.captured_at,
                source=Source(providerId=source.provider_id, sourceRecordId=row.source_record_id, sourceUrl=row.source_url),
                status=DataStatus.LIVE,
                quality=Quality(),
                provenance=Provenance(recordClass=ProvenanceClass.STANDARDIZED, transformationVersion="eastmoney-limit-down-pool-normalizer/1"),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
