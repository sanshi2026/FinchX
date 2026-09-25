"""Aigupiao Dragon Tiger list/detail contracts and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

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


_SUPPORTED_EXCHANGES = {Exchange.SSE, Exchange.SZSE, Exchange.BSE}


def _validate_instrument(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A or instrument.kind is not InstrumentKind.EQUITY:
        raise ValueError("Dragon Tiger datasets support CN_A equities only")
    if instrument.exchange not in _SUPPORTED_EXCHANGES:
        raise ValueError("Dragon Tiger identity requires an explicit SSE, SZSE, or BSE exchange")
    if len(instrument.code) != 6 or not instrument.code.isascii() or not instrument.code.isdigit():
        raise ValueError("Dragon Tiger instrument code must be six ASCII digits")


class MarketDragonTigerListRequest(ContractModel):
    trade_date: date = Field(alias="tradeDate")


class MarketDragonTigerDetailRequest(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    trade_date: date = Field(alias="tradeDate")
    trade_id: str = Field(alias="tradeId", min_length=1)

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketDragonTigerDetailRequest:
        _validate_instrument(self.instrument_id)
        return self


class MarketDragonTigerListData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str = Field(min_length=1)
    trade_date: date = Field(alias="tradeDate")
    trade_id: str = Field(alias="tradeId", min_length=1)
    close_price: Price = Field(alias="closePrice")
    change_ratio: Percentage = Field(alias="changeRatio", description="Ratio fraction; 10% is 0.10.")
    amount: Amount
    total_buy: Amount = Field(alias="totalBuy")
    total_net: Amount = Field(alias="totalNet")
    explanation: str = Field(min_length=1)
    three_day_flag: str | None = Field(default=None, alias="threeDayFlag")
    theme_id: int | None = Field(default=None, alias="themeId", strict=True)
    theme_name: str | None = Field(default=None, alias="themeName")

    @model_validator(mode="after")
    def validate_identity(self) -> MarketDragonTigerListData:
        _validate_instrument(self.instrument_id)
        return self


class DragonTigerSeat(ContractModel):
    rank: int = Field(strict=True, ge=1, description="Derived from the source array order.")
    seat_name: str = Field(alias="seatName", min_length=1)
    source_seat_code: str | None = Field(default=None, alias="sourceSeatCode")
    has_details: bool | None = Field(default=None, alias="hasDetails")
    buy_amount: Amount = Field(alias="buyAmount")
    sell_amount: Amount = Field(alias="sellAmount")
    net_amount: Amount = Field(alias="netAmount")


class MarketDragonTigerDetailData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str = Field(min_length=1)
    trade_date: date = Field(alias="tradeDate")
    trade_id: str = Field(alias="tradeId", min_length=1)
    close_price: Price = Field(alias="closePrice")
    change_ratio: Percentage = Field(alias="changeRatio")
    amount: Amount
    total_buy: Amount = Field(alias="totalBuy")
    total_sell: Amount = Field(alias="totalSell")
    total_net: Amount = Field(alias="totalNet")
    explanation: str = Field(min_length=1)
    comment_kind: str | None = Field(default=None, alias="commentKind")
    comment_object_id: str | None = Field(default=None, alias="commentObjectId")
    buy_seats: list[DragonTigerSeat] = Field(alias="buySeats")
    sell_seats: list[DragonTigerSeat] = Field(alias="sellSeats")

    @model_validator(mode="after")
    def validate_identity(self) -> MarketDragonTigerDetailData:
        _validate_instrument(self.instrument_id)
        return self


MARKET_DRAGON_TIGER_LIST_DATASET: DatasetDefinition[
    MarketDragonTigerListRequest, MarketDragonTigerListData
] = DatasetDefinition(
    name="market.dragon_tiger_list",
    schema_version="1.0",
    request_type=MarketDragonTigerListRequest,
    data_type=MarketDragonTigerListData,
)
MARKET_DRAGON_TIGER_DETAIL_DATASET: DatasetDefinition[
    MarketDragonTigerDetailRequest, MarketDragonTigerDetailData
] = DatasetDefinition(
    name="market.dragon_tiger_detail",
    schema_version="1.0",
    request_type=MarketDragonTigerDetailRequest,
    data_type=MarketDragonTigerDetailData,
)


@dataclass(frozen=True)
class _ProviderDragonTigerListRow:
    instrument_id: InstrumentId
    name: str
    trade_date: date
    trade_id: str
    close_price: Decimal
    change_percent_points: Decimal
    amount_cny: Decimal
    total_buy_cny: Decimal
    total_net_cny: Decimal
    explanation: str
    three_day_flag: str | None
    theme_id: int | None
    theme_name: str | None
    raw_payload: dict[str, object]
    source_url: str
    captured_at: datetime


@dataclass(frozen=True)
class _ProviderDragonTigerSeat:
    seat_name: str
    source_seat_code: str | None
    has_details: bool | None
    buy_amount_cny: Decimal
    sell_amount_cny: Decimal
    net_amount_cny: Decimal
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class _ProviderDragonTigerDetail:
    instrument_id: InstrumentId
    name: str
    trade_date: date
    trade_id: str
    close_price: Decimal
    change_percent_points: Decimal
    amount_cny: Decimal
    total_buy_cny: Decimal
    total_sell_cny: Decimal
    total_net_cny: Decimal
    explanation: str
    comment_kind: str | None
    comment_object_id: str | None
    buy_seats: tuple[_ProviderDragonTigerSeat, ...]
    sell_seats: tuple[_ProviderDragonTigerSeat, ...]
    raw_payload: dict[str, object]
    source_url: str
    captured_at: datetime


def _record_base(source: Source, *, source_record_id: str, source_url: str, captured_at: datetime, dataset: str, record_id: str, entity_id: InstrumentId, data: dict[str, object]) -> StandardRecord:
    return StandardRecord(
        dataset=dataset,
        schemaVersion="1.0",
        recordId=record_id,
        entityId=entity_id,
        capturedAt=captured_at,
        source=Source(providerId=source.provider_id, sourceRecordId=source_record_id, sourceUrl=source_url or source.source_url),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion=f"aigupiao-{dataset.replace('.', '-')}-normalizer/1",
            adjustments=[
                {
                    "name": "seat-rank-from-source-array-order",
                    "version": "1",
                    "details": {"appliesTo": "dragonTigerSeat.rank"},
                }
            ] if dataset == MARKET_DRAGON_TIGER_DETAIL_DATASET.name else [],
        ),
        data=data,
    )


def normalize_market_dragon_tiger_list(
    request: MarketDragonTigerListRequest,
    rows: tuple[_ProviderDragonTigerListRow, ...],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    if not isinstance(request, MarketDragonTigerListRequest):
        raise ValueError("request must be a MarketDragonTigerListRequest")
    records: list[StandardRecord] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if row.trade_date != request.trade_date:
            raise ValueError("provider Dragon Tiger row date does not match request")
        if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
            raise ValueError("provider returned a naive captured_at timestamp")
        _validate_instrument(row.instrument_id)
        key = (format_symbol(row.instrument_id), row.trade_id)
        if key in seen:
            raise ValueError("provider returned a duplicate Dragon Tiger trade_id")
        seen.add(key)
        data = MarketDragonTigerListData(
            instrumentId=row.instrument_id,
            name=row.name,
            tradeDate=row.trade_date,
            tradeId=row.trade_id,
            closePrice=row.close_price,
            changeRatio=row.change_percent_points / Decimal("100"),
            amount=row.amount_cny,
            totalBuy=row.total_buy_cny,
            totalNet=row.total_net_cny,
            explanation=row.explanation,
            threeDayFlag=row.three_day_flag,
            themeId=row.theme_id,
            themeName=row.theme_name,
        )
        records.append(_record_base(
            source,
            source_record_id=row.trade_id,
            source_url=row.source_url,
            captured_at=row.captured_at,
            dataset=MARKET_DRAGON_TIGER_LIST_DATASET.name,
            record_id=f"aigupiao-dragon-tiger:{row.trade_date.isoformat()}:{row.instrument_id.exchange.value}:{row.instrument_id.code}:{row.trade_id}",
            entity_id=row.instrument_id,
            data=data.model_dump(mode="json", by_alias=True),
        ))
    return tuple(records)


def _normalize_seats(rows: tuple[_ProviderDragonTigerSeat, ...]) -> list[dict[str, object]]:
    return [
        DragonTigerSeat(
            rank=index,
            seatName=row.seat_name,
            sourceSeatCode=row.source_seat_code,
            hasDetails=row.has_details,
            buyAmount=row.buy_amount_cny,
            sellAmount=row.sell_amount_cny,
            netAmount=row.net_amount_cny,
        ).model_dump(mode="json", by_alias=True)
        for index, row in enumerate(rows, start=1)
    ]


def normalize_market_dragon_tiger_detail(
    request: MarketDragonTigerDetailRequest,
    row: _ProviderDragonTigerDetail,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, MarketDragonTigerDetailRequest):
        raise ValueError("request must be a MarketDragonTigerDetailRequest")
    if row.instrument_id != request.instrument_id or row.trade_date != request.trade_date or row.trade_id != request.trade_id:
        raise ValueError("provider Dragon Tiger detail identity does not match request")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = MarketDragonTigerDetailData(
        instrumentId=row.instrument_id,
        name=row.name,
        tradeDate=row.trade_date,
        tradeId=row.trade_id,
        closePrice=row.close_price,
        changeRatio=row.change_percent_points / Decimal("100"),
        amount=row.amount_cny,
        totalBuy=row.total_buy_cny,
        totalSell=row.total_sell_cny,
        totalNet=row.total_net_cny,
        explanation=row.explanation,
        commentKind=row.comment_kind,
        commentObjectId=row.comment_object_id,
        buySeats=_normalize_seats(row.buy_seats),
        sellSeats=_normalize_seats(row.sell_seats),
    )
    return _record_base(
        source,
        source_record_id=row.trade_id,
        source_url=row.source_url,
        captured_at=row.captured_at,
        dataset=MARKET_DRAGON_TIGER_DETAIL_DATASET.name,
        record_id=f"aigupiao-dragon-tiger-detail:{row.trade_date.isoformat()}:{row.instrument_id.exchange.value}:{row.instrument_id.code}:{row.trade_id}",
        entity_id=row.instrument_id,
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "DragonTigerSeat",
    "MARKET_DRAGON_TIGER_DETAIL_DATASET",
    "MARKET_DRAGON_TIGER_LIST_DATASET",
    "MarketDragonTigerDetailData",
    "MarketDragonTigerDetailRequest",
    "MarketDragonTigerListData",
    "MarketDragonTigerListRequest",
    "normalize_market_dragon_tiger_detail",
    "normalize_market_dragon_tiger_list",
]
