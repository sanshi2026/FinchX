"""Tencent-backed single-equity fund-flow contracts and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import re
from typing import Sequence

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    Percentage,
    Price,
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
}
_TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


def _validate_fund_flow_instrument(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A:
        raise ValueError("fund-flow datasets currently support only Market.CN_A")
    prefixes = _SUPPORTED_EQUITY_PREFIXES.get(instrument.exchange)
    if instrument.kind is not InstrumentKind.EQUITY or prefixes is None:
        raise ValueError("fund-flow datasets support SSE and SZSE equities only")
    if (
        len(instrument.code) != 6
        or not instrument.code.isascii()
        or not instrument.code.isdigit()
        or not instrument.code.startswith(prefixes)
    ):
        raise ValueError("equity code does not match its explicit SSE/SZSE identity")


class MarketFundFlowRequest(ContractModel):
    """Request fund flow for one fully identified SSE or SZSE equity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketFundFlowRequest:
        _validate_fund_flow_instrument(self.instrument_id)
        return self


class _MarketFundFlowDataBase(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    trade_date: date = Field(
        alias="tradeDate",
        description="Trading date reported by Tencent, not FinchX capture time.",
    )

    @model_validator(mode="after")
    def validate_instrument(self):
        _validate_fund_flow_instrument(self.instrument_id)
        return self


class MarketFundFlowSnapshotData(_MarketFundFlowDataBase):
    """One source trading day's fund-flow summary; money is in CNY."""

    main_net_inflow: Amount = Field(alias="mainNetInflow")
    main_inflow: Amount = Field(alias="mainInflow")
    main_outflow: Amount = Field(alias="mainOutflow")
    main_inflow_rate: Percentage = Field(
        alias="mainInflowRate",
        description="Ratio fraction; 15% is 0.15.",
    )
    main_outflow_rate: Percentage = Field(
        alias="mainOutflowRate",
        description="Ratio fraction; 19% is 0.19.",
    )
    retail_inflow: Amount = Field(alias="retailInflow")
    retail_outflow: Amount = Field(alias="retailOutflow")
    retail_inflow_rate: Percentage = Field(
        alias="retailInflowRate",
        description="Ratio fraction; 35% is 0.35.",
    )
    retail_outflow_rate: Percentage = Field(
        alias="retailOutflowRate",
        description="Ratio fraction; 31% is 0.31.",
    )
    super_large_net_inflow: Amount = Field(alias="superLargeNetInflow")
    large_net_inflow: Amount = Field(alias="largeNetInflow")
    medium_net_inflow: Amount = Field(alias="mediumNetInflow")
    small_net_inflow: Amount = Field(alias="smallNetInflow")

    @field_validator(
        "main_inflow_rate",
        "main_outflow_rate",
        "retail_inflow_rate",
        "retail_outflow_rate",
    )
    @classmethod
    def rates_must_be_ratios_between_zero_and_one(cls, value: Decimal) -> Decimal:
        if value < 0 or value > 1:
            raise ValueError("fund-flow rates must be ratio fractions from 0 to 1")
        return value

    @field_validator("main_inflow", "main_outflow", "retail_inflow", "retail_outflow")
    @classmethod
    def gross_flows_must_be_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("gross inflow and outflow values must not be negative")
        return value

    @model_validator(mode="after")
    def rates_must_approximately_sum_to_one(self) -> MarketFundFlowSnapshotData:
        total = (
            self.main_inflow_rate
            + self.main_outflow_rate
            + self.retail_inflow_rate
            + self.retail_outflow_rate
        )
        if abs(total - Decimal("1")) > Decimal("0.01"):
            raise ValueError("fund-flow rates must sum to approximately 1")
        return self


class MarketFundFlowIntradayData(_MarketFundFlowDataBase):
    """One minute of Tencent cumulative fund-flow values, in CNY."""

    time: str = Field(
        description="Source market-local time, HH:MM; values are cumulative from open.",
        pattern=_TIME_PATTERN.pattern,
    )
    price: Price = Field(description="Source price in CNY per share.")
    cumulative_main_net_inflow: Amount = Field(alias="cumulativeMainNetInflow")
    cumulative_retail_net_inflow: Amount = Field(alias="cumulativeRetailNetInflow")
    cumulative_super_large_net_inflow: Amount = Field(alias="cumulativeSuperLargeNetInflow")
    cumulative_large_net_inflow: Amount = Field(alias="cumulativeLargeNetInflow")
    cumulative_medium_net_inflow: Amount = Field(alias="cumulativeMediumNetInflow")
    cumulative_small_net_inflow: Amount = Field(alias="cumulativeSmallNetInflow")
    cumulative_main_inflow: Amount = Field(alias="cumulativeMainInflow")
    cumulative_main_outflow: Amount = Field(alias="cumulativeMainOutflow")

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if not _TIME_PATTERN.fullmatch(value):
            raise ValueError("time must be a valid HH:MM source time")
        return value

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("price must be positive")
        return value

    @field_validator("cumulative_main_inflow", "cumulative_main_outflow")
    @classmethod
    def cumulative_gross_flows_must_be_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("cumulative gross inflow and outflow must not be negative")
        return value


class MarketFundFlowDailyData(_MarketFundFlowDataBase):
    """One historical trading day's main net inflow and verified close."""

    main_net_inflow: Amount = Field(alias="mainNetInflow")
    close: Price = Field(description="Daily close in CNY per share.")

    @field_validator("close")
    @classmethod
    def close_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("close must be positive")
        return value


MARKET_FUND_FLOW_SNAPSHOT_DATASET: DatasetDefinition[
    MarketFundFlowRequest, MarketFundFlowSnapshotData
] = DatasetDefinition(
    name="market.fund_flow_snapshot",
    schema_version="1.0",
    request_type=MarketFundFlowRequest,
    data_type=MarketFundFlowSnapshotData,
)
MARKET_FUND_FLOW_INTRADAY_DATASET: DatasetDefinition[
    MarketFundFlowRequest, MarketFundFlowIntradayData
] = DatasetDefinition(
    name="market.fund_flow_intraday",
    schema_version="1.0",
    request_type=MarketFundFlowRequest,
    data_type=MarketFundFlowIntradayData,
)
MARKET_FUND_FLOW_DAILY_DATASET: DatasetDefinition[
    MarketFundFlowRequest, MarketFundFlowDailyData
] = DatasetDefinition(
    name="market.fund_flow_daily",
    schema_version="1.0",
    request_type=MarketFundFlowRequest,
    data_type=MarketFundFlowDailyData,
)


@dataclass(frozen=True)
class _ProviderFundFlowSnapshot:
    instrument_id: InstrumentId
    trade_date: date
    main_net_inflow: Decimal
    main_inflow: Decimal
    main_inflow_rate_percent: Decimal
    main_outflow: Decimal
    main_outflow_rate_percent: Decimal
    retail_inflow: Decimal
    retail_inflow_rate_percent: Decimal
    retail_outflow: Decimal
    retail_outflow_rate_percent: Decimal
    super_large_net_inflow: Decimal
    large_net_inflow: Decimal
    medium_net_inflow: Decimal
    small_net_inflow: Decimal
    source_record_id: str
    source_url: str
    captured_at: datetime


@dataclass(frozen=True)
class _ProviderFundFlowIntradayRow:
    instrument_id: InstrumentId
    trade_date: date
    time: str
    price: Decimal
    cumulative_main_net_inflow: Decimal
    cumulative_retail_net_inflow: Decimal
    cumulative_super_large_net_inflow: Decimal
    cumulative_large_net_inflow: Decimal
    cumulative_medium_net_inflow: Decimal
    cumulative_small_net_inflow: Decimal
    cumulative_main_inflow: Decimal
    cumulative_main_outflow: Decimal
    source_record_id: str
    source_url: str
    captured_at: datetime


@dataclass(frozen=True)
class _ProviderFundFlowDailyRow:
    instrument_id: InstrumentId
    trade_date: date
    main_net_inflow: Decimal
    close: Decimal
    source_record_id: str
    source_url: str
    captured_at: datetime


@dataclass(frozen=True)
class _ProviderFundFlowResponse:
    instrument_id: InstrumentId
    snapshot: _ProviderFundFlowSnapshot
    intraday_rows: tuple[_ProviderFundFlowIntradayRow, ...]
    daily_rows: tuple[_ProviderFundFlowDailyRow, ...]


def _aware_capture_time(captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")


def _normalize_fund_flow_snapshot(
    request: MarketFundFlowRequest,
    row: _ProviderFundFlowSnapshot,
    *,
    source: Source,
) -> StandardRecord:
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned fund flow for a different instrument")
    _validate_fund_flow_instrument(row.instrument_id)
    _aware_capture_time(row.captured_at)
    data = MarketFundFlowSnapshotData(
        instrumentId=row.instrument_id,
        tradeDate=row.trade_date,
        mainNetInflow=row.main_net_inflow,
        mainInflow=row.main_inflow,
        mainOutflow=row.main_outflow,
        mainInflowRate=row.main_inflow_rate_percent / Decimal("100"),
        mainOutflowRate=row.main_outflow_rate_percent / Decimal("100"),
        retailInflow=row.retail_inflow,
        retailOutflow=row.retail_outflow,
        retailInflowRate=row.retail_inflow_rate_percent / Decimal("100"),
        retailOutflowRate=row.retail_outflow_rate_percent / Decimal("100"),
        superLargeNetInflow=row.super_large_net_inflow,
        largeNetInflow=row.large_net_inflow,
        mediumNetInflow=row.medium_net_inflow,
        smallNetInflow=row.small_net_inflow,
    )
    return StandardRecord(
        dataset=MARKET_FUND_FLOW_SNAPSHOT_DATASET.name,
        schemaVersion=MARKET_FUND_FLOW_SNAPSHOT_DATASET.schema_version,
        recordId=f"{format_symbol(row.instrument_id)}@{row.trade_date.isoformat()}",
        entityId=row.instrument_id,
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
            transformationVersion="market-fund-flow-snapshot-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


def _normalize_fund_flow_intraday(
    request: MarketFundFlowRequest,
    rows: Sequence[_ProviderFundFlowIntradayRow],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not rows:
        raise ValueError("provider returned no fund-flow intraday rows")
    _validate_fund_flow_instrument(request.instrument_id)
    if any(not isinstance(row, _ProviderFundFlowIntradayRow) for row in rows):
        raise ValueError("provider returned an unsupported fund-flow intraday row")
    ordered_rows = sorted(rows, key=lambda row: (row.trade_date, row.time))
    previous_key = None
    dates: set[date] = set()
    records: list[StandardRecord] = []
    for row in ordered_rows:
        if row.instrument_id != request.instrument_id:
            raise ValueError("provider returned fund flow for a different instrument")
        _aware_capture_time(row.captured_at)
        key = (row.trade_date, row.time)
        if key == previous_key:
            raise ValueError("provider returned a duplicate fund-flow minute")
        previous_key = key
        dates.add(row.trade_date)
        data = MarketFundFlowIntradayData(
            instrumentId=row.instrument_id,
            tradeDate=row.trade_date,
            time=row.time,
            price=row.price,
            cumulativeMainNetInflow=row.cumulative_main_net_inflow,
            cumulativeRetailNetInflow=row.cumulative_retail_net_inflow,
            cumulativeSuperLargeNetInflow=row.cumulative_super_large_net_inflow,
            cumulativeLargeNetInflow=row.cumulative_large_net_inflow,
            cumulativeMediumNetInflow=row.cumulative_medium_net_inflow,
            cumulativeSmallNetInflow=row.cumulative_small_net_inflow,
            cumulativeMainInflow=row.cumulative_main_inflow,
            cumulativeMainOutflow=row.cumulative_main_outflow,
        )
        records.append(
            StandardRecord(
                dataset=MARKET_FUND_FLOW_INTRADAY_DATASET.name,
                schemaVersion=MARKET_FUND_FLOW_INTRADAY_DATASET.schema_version,
                recordId=(
                    f"{format_symbol(row.instrument_id)}@{row.trade_date.isoformat()}"
                    f"T{row.time.replace(':', '')}"
                ),
                entityId=row.instrument_id,
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
                    transformationVersion="market-fund-flow-intraday-normalizer/1",
                ),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    if len(dates) != 1:
        raise ValueError("market.fund_flow_intraday must contain exactly one tradeDate")
    return tuple(records)


def _normalize_fund_flow_daily(
    request: MarketFundFlowRequest,
    rows: Sequence[_ProviderFundFlowDailyRow],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not rows:
        raise ValueError("provider returned no fund-flow daily rows")
    _validate_fund_flow_instrument(request.instrument_id)
    seen: set[date] = set()
    ordered_rows = sorted(rows, key=lambda row: row.trade_date)
    records: list[StandardRecord] = []
    for row in ordered_rows:
        if not isinstance(row, _ProviderFundFlowDailyRow):
            raise ValueError("provider returned an unsupported fund-flow daily row")
        if row.instrument_id != request.instrument_id:
            raise ValueError("provider returned fund flow for a different instrument")
        if row.trade_date in seen:
            raise ValueError(f"provider returned a duplicate fund-flow date: {row.trade_date}")
        seen.add(row.trade_date)
        _aware_capture_time(row.captured_at)
        data = MarketFundFlowDailyData(
            instrumentId=row.instrument_id,
            tradeDate=row.trade_date,
            mainNetInflow=row.main_net_inflow,
            close=row.close,
        )
        records.append(
            StandardRecord(
                dataset=MARKET_FUND_FLOW_DAILY_DATASET.name,
                schemaVersion=MARKET_FUND_FLOW_DAILY_DATASET.schema_version,
                recordId=f"{format_symbol(row.instrument_id)}@{row.trade_date.isoformat()}",
                entityId=row.instrument_id,
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
                    transformationVersion="market-fund-flow-daily-normalizer/1",
                ),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
