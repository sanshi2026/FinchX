from datetime import date

import pytest

from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.query import financial as financial_query


class SpyCollector:
    def __init__(self):
        self.calls = []
        self.result = object()

    def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
        self.calls.append((dataset.name, kwargs["request"]))
        return self.result


def test_all_equity_convenience_endpoints_resolve_one_bare_code():
    collector = SpyCollector()
    client = FinchX(collector=collector)
    expected = InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )

    calls = [
        ("market.ohlcv", lambda: client.market.ohlcv("600519", date(2026, 9, 1), date(2026, 9, 18), "qfq")),
        ("market.equity_intraday", lambda: client.market.equity_intraday("600519")),
        ("market.equity_intraday_5d", lambda: client.market.equity_intraday_5d("600519")),
        ("market.fund_flow.daily", lambda: client.market.fund_flow_daily("600519")),
        ("market.fund_flow.intraday", lambda: client.market.fund_flow_intraday("600519")),
        ("market.fund_flow.snapshot", lambda: client.market.fund_flow_snapshot("600519")),
        ("market.industry_comparison", lambda: client.market.industry_comparison("600519")),
        ("market.instrument_sector_snapshot", lambda: client.market.instrument_sector_snapshot("600519")),
        ("market.stock_keyword", lambda: client.market.stock_keyword("600519")),
        ("market.orderbook", lambda: client.market.orderbook("600519")),
        ("market.quote_snapshot", lambda: client.market.quote_snapshot("600519")),
        ("fundamental.company_profile", lambda: client.fundamental.company_profile("600519")),
        ("fundamental.financial_summary", lambda: client.fundamental.financial_summary("600519")),
        ("fundamental.industry_comparison", lambda: client.fundamental.industry_comparison("600519")),
        ("fundamental.revenue_breakdown", lambda: client.fundamental.revenue_breakdown("600519")),
        ("financial.statement", lambda: client.financial.statements("600519", "income_statement")),
        ("news.document", lambda: client.news.search("600519")),
        ("disclosure.document", lambda: client.disclosure.search("600519")),
        ("ownership.capital_snapshot", lambda: client.ownership.capital_snapshot("600519")),
        ("ownership.float_holder", lambda: client.ownership.float_holder("600519")),
        ("ownership.holder_summary_snapshot", lambda: client.ownership.holder_summary_snapshot("600519")),
        ("company.executive_snapshot", lambda: client.company.executive_snapshot("600519")),
        ("company.executive_share_change", lambda: client.company.executive_share_change("600519")),
        ("corporate_action.dividend", lambda: client.corporate_action.dividend("600519")),
        ("corporate_action.repurchase", lambda: client.corporate_action.repurchase("600519")),
    ]

    for _, call in calls:
        assert call() is collector.result

    assert len(collector.calls) == len(calls)
    assert all(request.instrument_id == expected for _, request in collector.calls)


def test_index_convenience_endpoints_resolve_000001_as_the_sse_index():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    client.market.index_intraday("000001")
    client.market.index_intraday_5d("000001")

    expected = InstrumentId(
        code="000001",
        market=Market.CN_A,
        kind=InstrumentKind.INDEX,
        exchange=Exchange.SSE,
    )
    assert [request.instrument_id for _, request in collector.calls] == [expected, expected]


def test_public_instrument_keyword_is_supported_without_request_compatibility():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    assert client.market.quote_snapshot(instrument="600519") is collector.result
    assert collector.calls[0][1].instrument_id == InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )
    with pytest.raises(TypeError, match="unexpected keyword argument 'request'"):
        client.market.quote_snapshot(request=object())


def test_legacy_financial_statement_service_uses_the_same_instrument_helper(monkeypatch):
    class FakeProvider:
        source = object()

        def fetch_raw_statement(self, request):
            self.request = request
            return object()

    provider = FakeProvider()
    monkeypatch.setattr(
        financial_query,
        "normalize_financial_statement",
        lambda request, raw, source: request,
    )

    result = financial_query.FinancialStatementService(provider=provider).get(
        "600519",
        "income_statement",
    )

    assert result.instrument_id == InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )
