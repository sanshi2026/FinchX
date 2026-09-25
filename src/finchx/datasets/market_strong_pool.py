"""EastMoney strong-pool contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field, field_validator, model_validator

from finchx.contracts import Amount, DataStatus, Percentage, Price, Provenance, ProvenanceClass, Quality, Ratio, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


def _validate_identity(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A or instrument.kind is not InstrumentKind.EQUITY:
        raise ValueError("strong pool supports CN_A equities only")
    if instrument.exchange not in (Exchange.SSE, Exchange.SZSE):
        raise ValueError("pool identity must come from the EastMoney m exchange field")
    if len(instrument.code) != 6 or not instrument.code.isascii() or not instrument.code.isdigit():
        raise ValueError("pool instrument code must be six ASCII digits")


class StrongPoolSelectionReason(str, Enum):
    SIXTY_DAY_HIGH = "sixty_day_high"
    RECENT_MULTIPLE_LIMIT_UPS = "recent_multiple_limit_ups"
    SIXTY_DAY_HIGH_AND_RECENT_MULTIPLE_LIMIT_UPS = "sixty_day_high_and_recent_multiple_limit_ups"


class MarketStrongPoolRequest(ContractModel):
    """Request the latest EastMoney strong-pool snapshot.

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


class MarketStrongPoolStats(ContractModel):
    lookback_days: int = Field(alias="lookbackDays", strict=True, ge=0)
    limit_up_count: int = Field(alias="limitUpCount", strict=True, ge=0)


class MarketStrongPoolData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    trade_date: date = Field(alias="tradeDate")
    name: str = Field(min_length=1)
    price: Price = Field(description="Latest price in CNY per share.")
    limit_up_price: Price = Field(alias="limitUpPrice", description="Current limit-up price in CNY per share.")
    change_rate: Percentage = Field(alias="changeRate", description="Ratio fraction; 20% is 0.20.")
    amount: Amount = Field(description="Current-session traded amount in CNY.")
    float_market_capitalization: Amount = Field(alias="floatMarketCapitalization")
    market_capitalization: Amount = Field(alias="marketCapitalization")
    turnover_rate: Percentage = Field(alias="turnoverRate", description="Ratio fraction.")
    is_sixty_day_high: bool = Field(alias="isSixtyDayHigh")
    selection_reason: StrongPoolSelectionReason = Field(alias="selectionReason")
    volume_ratio: Ratio = Field(alias="volumeRatio", description="Source volume ratio as a dimensionless multiple.")
    industry: str = Field(min_length=1)
    limit_up_stats: MarketStrongPoolStats = Field(alias="limitUpStats")

    @field_validator("price", "limit_up_price")
    @classmethod
    def prices_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("prices must be positive")
        return value

    @field_validator("amount", "float_market_capitalization", "market_capitalization")
    @classmethod
    def amounts_must_be_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("amounts must not be negative")
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> MarketStrongPoolData:
        _validate_identity(self.instrument_id)
        return self


MARKET_STRONG_POOL_DATASET: DatasetDefinition[MarketStrongPoolRequest, MarketStrongPoolData] = DatasetDefinition(
    name="market.strong_pool",
    schema_version="1.0",
    request_type=MarketStrongPoolRequest,
    data_type=MarketStrongPoolData,
)


@dataclass(frozen=True)
class _ProviderStrongPoolRow:
    instrument_id: InstrumentId
    trade_date: date
    name: str
    price_milli_cny: Decimal
    limit_up_price_milli_cny: Decimal
    change_percent_points: Decimal
    amount_cny: Decimal
    float_market_cap_cny: Decimal
    market_cap_cny: Decimal
    turnover_percent_points: Decimal
    is_sixty_day_high: bool
    selection_reason: StrongPoolSelectionReason
    volume_ratio: Decimal
    speed_raw: Decimal | None
    ztf_raw: str | None
    stats_days: int
    stats_count: int
    industry: str
    source_record_id: str
    source_url: str
    captured_at: datetime


def normalize_market_strong_pool(
    request: MarketStrongPoolRequest,
    rows: tuple[_ProviderStrongPoolRow, ...],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, MarketStrongPoolRequest):
        raise ValueError("request must be a MarketStrongPoolRequest")
    records: list[StandardRecord] = []
    for row in rows:
        if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
            raise ValueError("provider returned a naive captured_at timestamp")
        _validate_identity(row.instrument_id)
        data = MarketStrongPoolData(
            instrumentId=row.instrument_id,
            tradeDate=row.trade_date,
            name=row.name,
            price=row.price_milli_cny / Decimal("1000"),
            limitUpPrice=row.limit_up_price_milli_cny / Decimal("1000"),
            changeRate=row.change_percent_points / Decimal("100"),
            amount=row.amount_cny,
            floatMarketCapitalization=row.float_market_cap_cny,
            marketCapitalization=row.market_cap_cny,
            turnoverRate=row.turnover_percent_points / Decimal("100"),
            isSixtyDayHigh=row.is_sixty_day_high,
            selectionReason=row.selection_reason,
            volumeRatio=row.volume_ratio,
            industry=row.industry,
            limitUpStats={"lookbackDays": row.stats_days, "limitUpCount": row.stats_count},
        )
        records.append(
            StandardRecord(
                dataset=MARKET_STRONG_POOL_DATASET.name,
                schemaVersion=MARKET_STRONG_POOL_DATASET.schema_version,
                recordId=f"eastmoney-strong:{row.trade_date.isoformat()}:{row.instrument_id.exchange.value}:{row.instrument_id.code}",
                entityId=row.instrument_id,
                capturedAt=row.captured_at,
                source=Source(providerId=source.provider_id, sourceRecordId=row.source_record_id, sourceUrl=row.source_url),
                status=DataStatus.LIVE,
                quality=Quality(),
                provenance=Provenance(recordClass=ProvenanceClass.STANDARDIZED, transformationVersion="eastmoney-strong-pool-normalizer/1"),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
