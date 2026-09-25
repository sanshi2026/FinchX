from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from finchx import FinchX
from finchx.computed import DeviationRequest
from finchx.datasets import (
    FinancialStatementRequest,
    KlineAdjustment,
    KlinesRequest,
    MarketDailyReplayRequest,
    MarketDragonTigerListRequest,
    MarketNewsSearchRequest,
    DisclosureSearchRequest,
    NewsSearchRequest,
    TradingCalendarRequest,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers import ProviderError


class SpyCollector:
    def __init__(self):
        self.calls = []
        self.result = object()

    def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
        self.calls.append((dataset, kwargs["request"]))
        return self.result


IDENTITY = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)


@pytest.mark.parametrize("value", ["2026-09-01", "20260901", "2026/09/01", date(2026, 9, 1)])
def test_date_request_models_normalize_supported_inputs(value):
    request = TradingCalendarRequest(
        market=Market.CN_A,
        startDate=value,
        endDate=value,
    )

    assert request.start_date == date(2026, 9, 1)
    assert request.end_date == date(2026, 9, 1)


def test_date_normalization_covers_representative_request_models():
    assert KlinesRequest(
        instrumentId=IDENTITY,
        startDate="20260901",
        endDate="2026/09/30",
        adjustment=KlineAdjustment.QFQ,
    ).start_date == date(2026, 9, 1)
    assert MarketDailyReplayRequest(requestedDate="2026-09-18").requested_date == date(2026, 9, 18)
    assert MarketDragonTigerListRequest(tradeDate="20260918").trade_date == date(2026, 9, 18)
    assert FinancialStatementRequest(
        instrumentId=IDENTITY,
        statementType="income_statement",
        periodEnd="2026/09/30",
    ).period_end == date(2026, 9, 30)
    assert DeviationRequest(instrumentId=IDENTITY, asOf="2026-09-30").as_of == date(2026, 9, 30)


def test_datetime_bounds_keep_existing_timezone_aware_support():
    since = datetime(2026, 9, 1, 9, tzinfo=timezone.utc)
    request = NewsSearchRequest(
        instrumentId=IDENTITY,
        since=since,
    )

    assert request.since == since


@pytest.mark.parametrize(
    "request_type,kwargs",
    [
        (NewsSearchRequest, {"instrumentId": IDENTITY, "since": datetime(2026, 9, 1, 9)}),
        (DisclosureSearchRequest, {"instrumentId": IDENTITY, "until": datetime(2026, 9, 1, 9)}),
        (MarketNewsSearchRequest, {"since": datetime(2026, 9, 1, 9)}),
    ],
)
def test_document_search_rejects_naive_datetime_bounds(request_type, kwargs):
    with pytest.raises(ValidationError, match="timezone offset"):
        request_type(**kwargs)


def test_document_date_range_search_requires_first_page():
    with pytest.raises(ValidationError, match="page=1"):
        NewsSearchRequest(instrumentId=IDENTITY, page=2, since="2026-09-01")
    with pytest.raises(ValidationError, match="page=1"):
        DisclosureSearchRequest(instrumentId=IDENTITY, page=2, until="2026-09-30")
    with pytest.raises(ValidationError, match="page=1"):
        MarketNewsSearchRequest(page=2, since="2026-09-01")


def test_convenience_endpoints_accept_date_strings_and_build_normalized_requests():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    client.reference.trading_calendar("2026-09-01", "20260930")
    assert collector.calls[-1][1].market is Market.CN_A
    assert collector.calls[-1][1].start_date == date(2026, 9, 1)
    assert collector.calls[-1][1].end_date == date(2026, 9, 30)

    with pytest.raises(TypeError, match="unexpected keyword argument 'request'"):
        client.reference.trading_calendar(request=TradingCalendarRequest(
            market=Market.CN_A,
            startDate="2026/09/01",
            endDate="2026-09-30",
        ))

    client.market.ohlcv("600519", "2026/09/01", "2026-09-18", "qfq")
    assert collector.calls[-1][1].start_date == date(2026, 9, 1)
    assert collector.calls[-1][1].end_date == date(2026, 9, 18)

    client.financial.statements("600519", "income_statement", period_end="20260930")
    assert collector.calls[-1][1].period_end == date(2026, 9, 30)

    client.news.search("600519", since="2026-09-01", until="2026/09/30")
    assert collector.calls[-1][1].since == date(2026, 9, 1)
    assert collector.calls[-1][1].until == date(2026, 9, 30)

    client.disclosure.search("600519", since="20260901", until="2026-09-30")
    assert collector.calls[-1][1].since == date(2026, 9, 1)
    assert collector.calls[-1][1].until == date(2026, 9, 30)


@pytest.mark.parametrize(
    ("value", "message"),
    [("2026-02-30", "invalid date input"), ("09/01/2026", "ambiguous date input")],
)
def test_invalid_and_ambiguous_date_strings_are_rejected(value, message):
    with pytest.raises(ValidationError, match=message):
        TradingCalendarRequest(market=Market.CN_A, startDate=value, endDate="2026-09-01")

    client = FinchX(collector=SpyCollector())
    with pytest.raises(ValidationError, match=message):
        client.reference.trading_calendar(value, "2026-09-01")


def test_latest_snapshot_compatibility_trade_date_still_cannot_select_history():
    from finchx.datasets import MarketLimitUpPoolRequest
    from finchx.providers.eastmoney_market import EastmoneyLimitUpPoolProvider

    request = MarketLimitUpPoolRequest(tradeDate="2026-09-01")
    provider = EastmoneyLimitUpPoolProvider(transport={})
    with pytest.raises(ProviderError, match="latest snapshot only.*tradeDate"):
        provider.fetch_raw_limit_up_pool(request)
