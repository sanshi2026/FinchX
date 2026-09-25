"""韭研公社 daily replay contract and source normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from finchx.contracts import (
    DataStatus,
    Percentage,
    Price,
    Provenance,
    ProvenanceClass,
    Quality,
    QualityIssue,
    QualityIssueKind,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


_UTC_PLUS_8 = timezone(timedelta(hours=8))


class MarketDailyReplayRequest(ContractModel):
    """Request one source-selected daily replay snapshot."""

    requested_date: date = Field(alias="requestedDate")


class ReplayStock(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str = Field(min_length=1)
    limit_up_time: time | None = Field(default=None, alias="limitUpTime")
    streak_text: str | None = Field(default=None, alias="streakText")
    price: Price | None = None
    change_ratio: Percentage | None = Field(default=None, alias="changeRatio")
    day: int | None = Field(default=None, strict=True, ge=1)
    edition: int | None = Field(default=None, strict=True, ge=1)
    expound: str | None = None


class ReplayTheme(ContractModel):
    theme_name: str = Field(alias="themeName", min_length=1)
    reason: str | None = None
    stock_count: int = Field(alias="stockCount", strict=True, ge=0)
    source_theme_id: str | None = Field(default=None, alias="sourceThemeId")
    stocks: list[ReplayStock] = Field(default_factory=list)


class MarketDailyReplayData(ContractModel):
    requested_date: date = Field(alias="requestedDate")
    trade_date: date = Field(alias="tradeDate")
    themes: list[ReplayTheme]

    @model_validator(mode="after")
    def requested_and_trade_dates_are_valid(self) -> MarketDailyReplayData:
        if self.trade_date > self.requested_date:
            raise ValueError("tradeDate cannot be later than requestedDate")
        return self


MARKET_DAILY_REPLAY_DATASET: DatasetDefinition[MarketDailyReplayRequest, MarketDailyReplayData] = DatasetDefinition(
    name="market.daily_replay",
    schema_version="1.0",
    request_type=MarketDailyReplayRequest,
    data_type=MarketDailyReplayData,
)


@dataclass(frozen=True)
class _ProviderReplayStock:
    instrument_id: InstrumentId
    name: str
    limit_up_time: time | None
    streak_text: str | None
    price_cny: Decimal | None
    change_ratio: Decimal | None
    day: int | None
    edition: int | None
    expound: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class _ProviderReplayTheme:
    theme_name: str
    reason: str | None
    stock_count: int
    source_theme_id: str | None
    stocks: tuple[_ProviderReplayStock, ...]
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class _ProviderDailyReplay:
    requested_date: date
    trade_date: date
    themes: tuple[_ProviderReplayTheme, ...]
    diagram_metadata: dict[str, Any] | None
    raw_payload: dict[str, Any]
    source_url: str
    captured_at: datetime


def _validate_instrument(instrument: InstrumentId) -> None:
    if instrument.market is not Market.CN_A or instrument.kind is not InstrumentKind.EQUITY:
        raise ValueError("daily replay supports CN_A equities only")
    if instrument.exchange not in {Exchange.SSE, Exchange.SZSE, Exchange.BSE}:
        raise ValueError("daily replay requires an explicit SSE, SZSE, or BSE identity")
    if len(instrument.code) != 6 or not instrument.code.isascii() or not instrument.code.isdigit():
        raise ValueError("daily replay instrument code must be six ASCII digits")


def normalize_market_daily_replay(
    request: MarketDailyReplayRequest,
    row: _ProviderDailyReplay,
    *,
    source: Source,
) -> StandardRecord:
    """Normalize a source replay into one stable daily snapshot record."""

    if not isinstance(request, MarketDailyReplayRequest):
        raise ValueError("request must be a MarketDailyReplayRequest")
    if row.requested_date != request.requested_date:
        raise ValueError("provider returned a different requested date")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")

    themes: list[ReplayTheme] = []
    issues: list[QualityIssue] = []
    for theme in row.themes:
        stocks: list[ReplayStock] = []
        for stock in theme.stocks:
            _validate_instrument(stock.instrument_id)
            stocks.append(
                ReplayStock(
                    instrumentId=stock.instrument_id,
                    name=stock.name,
                    limitUpTime=stock.limit_up_time,
                    streakText=stock.streak_text,
                    price=stock.price_cny,
                    changeRatio=stock.change_ratio,
                    day=stock.day,
                    edition=stock.edition,
                    expound=stock.expound,
                )
            )
        if theme.stock_count != len(stocks):
            issues.append(
                QualityIssue(
                    kind=QualityIssueKind.VALIDATION_CONCERN,
                    detail=(
                        f"source theme {theme.source_theme_id or theme.theme_name!r} reported "
                        f"count={theme.stock_count} but returned {len(stocks)} stocks; "
                        "the source list was preserved"
                    ),
                )
            )
        themes.append(
            ReplayTheme(
                themeName=theme.theme_name,
                reason=theme.reason,
                stockCount=theme.stock_count,
                sourceThemeId=theme.source_theme_id,
                stocks=stocks,
            )
        )

    data = MarketDailyReplayData(
        requestedDate=row.requested_date,
        tradeDate=row.trade_date,
        themes=themes,
    )
    snapshot_at = datetime.combine(row.trade_date, time.min, tzinfo=_UTC_PLUS_8)
    return StandardRecord(
        dataset=MARKET_DAILY_REPLAY_DATASET.name,
        schemaVersion=MARKET_DAILY_REPLAY_DATASET.schema_version,
        recordId=f"jiyangongshe-daily-replay:{row.trade_date.isoformat()}",
        entityId=f"market:cn_a:daily_replay:{row.trade_date.isoformat()}",
        eventAt=snapshot_at,
        asOf=snapshot_at,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.trade_date.isoformat(),
            sourceUrl=row.source_url or source.source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(issues=issues),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="jiyangongshe-daily-replay-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "MARKET_DAILY_REPLAY_DATASET",
    "MarketDailyReplayData",
    "MarketDailyReplayRequest",
    "ReplayStock",
    "ReplayTheme",
    "normalize_market_daily_replay",
]
