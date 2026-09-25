"""Equity and index intraday point contracts and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
import re
from typing import Sequence

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Shares,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.contracts.units import DecimalString
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
_POSITIVE_DECIMAL_PATTERN = r"^(?:[1-9][0-9]*(?:\.[0-9]+)?|0\.[0-9]*[1-9][0-9]*)$"
_NON_NEGATIVE_DECIMAL_PATTERN = r"^(?:0|[1-9][0-9]*(?:\.[0-9]+)?|0\.[0-9]+)$"
_TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


def _validate_equity(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A:
        raise ValueError("intraday datasets currently support only Market.CN_A")
    prefixes = _SUPPORTED_EQUITY_PREFIXES.get(instrument.exchange)
    if instrument.kind is not InstrumentKind.EQUITY or prefixes is None:
        raise ValueError("equity intraday datasets support SSE and SZSE equities only")
    if (
        len(instrument.code) != 6
        or not instrument.code.isascii()
        or not instrument.code.isdigit()
        or not instrument.code.startswith(prefixes)
    ):
        raise ValueError("equity code does not match its explicit SSE/SZSE identity")


def _validate_index(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A:
        raise ValueError("intraday datasets currently support only Market.CN_A")
    if instrument.kind is not InstrumentKind.INDEX:
        raise ValueError("index intraday datasets require an index InstrumentId")
    if (instrument.exchange, instrument.code) not in _SUPPORTED_INDEX_IDENTITIES:
        raise ValueError("index intraday datasets support SSE 000001 and SZSE 399001/399006")


class EquityIntradayRequest(ContractModel):
    """Request one explicitly identified SSE or SZSE equity session."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> EquityIntradayRequest:
        _validate_equity(self.instrument_id)
        return self


class EquityIntraday5dRequest(ContractModel):
    """Request the most recent five or fewer sessions for one equity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> EquityIntraday5dRequest:
        _validate_equity(self.instrument_id)
        return self


class IndexIntradayRequest(ContractModel):
    """Request one explicitly identified SSE or SZSE index session."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> IndexIntradayRequest:
        _validate_index(self.instrument_id)
        return self


class IndexIntraday5dRequest(ContractModel):
    """Request the most recent five or fewer sessions for one index."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> IndexIntraday5dRequest:
        _validate_index(self.instrument_id)
        return self


class _IntradayDataBase(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    trade_date: date = Field(
        alias="tradeDate",
        description="Source trading-date label; not FinchX capturedAt.",
    )
    time: str = Field(
        description="Source trading time in HHMM normalized to HH:MM; not capturedAt.",
        pattern=_TIME_PATTERN.pattern,
    )
    price: DecimalString = Field(
        description=(
            "Exact decimal in the source price unit (CNY per share for equities; index points "
            "for indices)."
        ),
        json_schema_extra={"pattern": _POSITIVE_DECIMAL_PATTERN},
    )
    volume: Shares = Field(
        description="Volume traded during this minute, in whole shares.",
    )
    amount: Amount = Field(
        description="Amount traded during this minute, in CNY.",
        json_schema_extra={"pattern": _NON_NEGATIVE_DECIMAL_PATTERN},
    )
    cumulative_volume: Shares = Field(
        alias="cumulativeVolume",
        description=(
            "Tencent source cumulative traded volume, normalized to whole shares from lots "
            "(source lots multiplied by 100)."
        ),
    )
    cumulative_amount: Amount = Field(
        alias="cumulativeAmount",
        description="Tencent source cumulative traded amount in CNY, unchanged from source.",
        json_schema_extra={"pattern": _NON_NEGATIVE_DECIMAL_PATTERN},
    )

    @field_validator("trade_date", mode="before")
    @classmethod
    def trade_date_must_not_be_datetime(cls, value: object) -> object:
        if isinstance(value, datetime):
            raise ValueError("tradeDate must be a date, not a timestamp")
        return value

    @field_validator("time")
    @classmethod
    def validate_source_time(cls, value: str) -> str:
        if not _TIME_PATTERN.fullmatch(value):
            raise ValueError("time must be a valid source HH:MM")
        time.fromisoformat(value)
        return value

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("intraday price must be positive")
        return value

    @field_validator("amount", "cumulative_amount")
    @classmethod
    def amounts_must_be_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("intraday amounts must be non-negative")
        return value


class EquityIntradayData(_IntradayDataBase):
    """One equity intraday point with cumulative volume and amount."""

    @model_validator(mode="after")
    def validate_instrument(self) -> EquityIntradayData:
        _validate_equity(self.instrument_id)
        return self


class IndexIntradayData(_IntradayDataBase):
    """One index intraday point with cumulative volume and amount."""

    @model_validator(mode="after")
    def validate_instrument(self) -> IndexIntradayData:
        _validate_index(self.instrument_id)
        return self


MARKET_EQUITY_INTRADAY_DATASET: DatasetDefinition[
    EquityIntradayRequest, EquityIntradayData
] = DatasetDefinition(
    name="market.equity_intraday",
    schema_version="1.0",
    request_type=EquityIntradayRequest,
    data_type=EquityIntradayData,
)
MARKET_EQUITY_INTRADAY_5D_DATASET: DatasetDefinition[
    EquityIntraday5dRequest, EquityIntradayData
] = DatasetDefinition(
    name="market.equity_intraday_5d",
    schema_version="1.0",
    request_type=EquityIntraday5dRequest,
    data_type=EquityIntradayData,
)
MARKET_INDEX_INTRADAY_DATASET: DatasetDefinition[
    IndexIntradayRequest, IndexIntradayData
] = DatasetDefinition(
    name="market.index_intraday",
    schema_version="1.0",
    request_type=IndexIntradayRequest,
    data_type=IndexIntradayData,
)
MARKET_INDEX_INTRADAY_5D_DATASET: DatasetDefinition[
    IndexIntraday5dRequest, IndexIntradayData
] = DatasetDefinition(
    name="market.index_intraday_5d",
    schema_version="1.0",
    request_type=IndexIntraday5dRequest,
    data_type=IndexIntradayData,
)


@dataclass(frozen=True)
class _ProviderIntradayRow:
    """Typed source row with source cumulative figures normalized to public units."""

    instrument_id: InstrumentId
    trade_date: date
    time: str
    price: Decimal
    cumulative_volume_lots: int
    cumulative_amount_cny: Decimal
    source_record_id: str
    source_url: str
    captured_at: datetime


def _normalize_intraday_rows(
    instrument_id: InstrumentId,
    rows: Sequence[_ProviderIntradayRow],
    *,
    source: Source,
    dataset_name: str,
    five_day: bool,
) -> tuple[StandardRecord, ...]:
    if not rows:
        raise ValueError("provider returned no intraday rows")

    seen: set[tuple[date, str]] = set()
    dates: set[date] = set()
    for row in rows:
        if not isinstance(row, _ProviderIntradayRow):
            raise ValueError("provider returned a row with an unsupported type")
        if row.instrument_id != instrument_id:
            raise ValueError("provider returned intraday data for a different instrument")
        if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
            raise ValueError("provider returned a naive captured_at timestamp")
        if not isinstance(row.price, Decimal) or not row.price.is_finite() or row.price <= 0:
            raise ValueError("provider returned an invalid intraday price")
        if type(row.cumulative_volume_lots) is not int or row.cumulative_volume_lots < 0:
            raise ValueError("provider returned an invalid cumulative volume in lots")
        if (
            not isinstance(row.cumulative_amount_cny, Decimal)
            or not row.cumulative_amount_cny.is_finite()
            or row.cumulative_amount_cny < 0
        ):
            raise ValueError("provider returned an invalid cumulative amount in CNY")
        key = (row.trade_date, row.time)
        if key in seen:
            raise ValueError(
                f"provider returned duplicate intraday point {row.trade_date.isoformat()} {row.time}"
            )
        seen.add(key)
        dates.add(row.trade_date)

    ordered_dates = sorted(dates)
    selected_dates = set(ordered_dates[-5:] if five_day else ordered_dates[-1:])
    selected = sorted(
        (row for row in rows if row.trade_date in selected_dates),
        key=lambda row: (row.trade_date, time.fromisoformat(row.time)),
    )
    previous_cumulative_by_date: dict[date, tuple[int, Decimal]] = {}
    data_type = (
        EquityIntradayData
        if instrument_id.kind is InstrumentKind.EQUITY
        else IndexIntradayData
    )
    records: list[StandardRecord] = []
    symbol = format_symbol(instrument_id)
    for row in selected:
        cumulative_volume = row.cumulative_volume_lots * 100
        previous = previous_cumulative_by_date.get(row.trade_date)
        if previous is None:
            minute_volume = cumulative_volume
            minute_amount = row.cumulative_amount_cny
        else:
            previous_volume, previous_amount = previous
            if cumulative_volume < previous_volume:
                raise ValueError(
                    "cumulativeVolume decreased within tradeDate "
                    f"{row.trade_date.isoformat()} at {row.time}"
                )
            if row.cumulative_amount_cny < previous_amount:
                raise ValueError(
                    "cumulativeAmount decreased within tradeDate "
                    f"{row.trade_date.isoformat()} at {row.time}"
                )
            minute_volume = cumulative_volume - previous_volume
            minute_amount = row.cumulative_amount_cny - previous_amount
        previous_cumulative_by_date[row.trade_date] = (
            cumulative_volume,
            row.cumulative_amount_cny,
        )
        data = data_type(
            instrumentId=row.instrument_id,
            tradeDate=row.trade_date,
            time=row.time,
            price=row.price,
            volume=minute_volume,
            amount=minute_amount,
            cumulativeVolume=cumulative_volume,
            cumulativeAmount=row.cumulative_amount_cny,
        )
        records.append(
            StandardRecord(
                dataset=dataset_name,
                schemaVersion="1.0",
                recordId=f"{symbol}@{row.trade_date.isoformat()}T{row.time}",
                entityId=row.instrument_id,
                capturedAt=row.captured_at,
                source=Source(
                    providerId=source.provider_id,
                    sourceRecordId=row.source_record_id,
                    sourceUrl=row.source_url,
                ),
                status=DataStatus.LIVE,
                quality=Quality(),
                provenance=Provenance(
                    recordClass=ProvenanceClass.STANDARDIZED,
                    transformationVersion="market-intraday-normalizer/2",
                ),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)


def normalize_equity_intraday(
    request: EquityIntradayRequest | EquityIntraday5dRequest,
    rows: Sequence[_ProviderIntradayRow],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, (EquityIntradayRequest, EquityIntraday5dRequest)):
        raise ValueError("equity intraday normalizer requires an equity request")
    _validate_equity(request.instrument_id)
    five_day = isinstance(request, EquityIntraday5dRequest)
    dataset_name = (
        MARKET_EQUITY_INTRADAY_5D_DATASET.name
        if five_day
        else MARKET_EQUITY_INTRADAY_DATASET.name
    )
    return _normalize_intraday_rows(
        request.instrument_id,
        rows,
        source=source,
        dataset_name=dataset_name,
        five_day=five_day,
    )


def normalize_index_intraday(
    request: IndexIntradayRequest | IndexIntraday5dRequest,
    rows: Sequence[_ProviderIntradayRow],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, (IndexIntradayRequest, IndexIntraday5dRequest)):
        raise ValueError("index intraday normalizer requires an index request")
    _validate_index(request.instrument_id)
    five_day = isinstance(request, IndexIntraday5dRequest)
    dataset_name = (
        MARKET_INDEX_INTRADAY_5D_DATASET.name
        if five_day
        else MARKET_INDEX_INTRADAY_DATASET.name
    )
    return _normalize_intraday_rows(
        request.instrument_id,
        rows,
        source=source,
        dataset_name=dataset_name,
        five_day=five_day,
    )
