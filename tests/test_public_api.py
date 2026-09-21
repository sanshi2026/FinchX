"""Public v1 Client API contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
from pathlib import Path
from typing import get_origin, get_type_hints

import finchx
from finchx import FinchX
from finchx.client import CLIENT_ENDPOINTS
from finchx.collectors import FetchResult
from finchx.providers import __all__ as PROVIDER_EXPORTS
from finchx.providers.registry import PROVIDER_REGISTRY


PUBLIC_TOP_LEVEL_EXPORTS = {
    "CLIENT_ENDPOINTS",
    "Collector",
    "DisclosureService",
    "FinancialStatementService",
    "FinchX",
    "MarketNewsService",
    "NewsService",
    "__version__",
    "disclosure",
    "financial_statements",
    "market_news",
    "news",
}

PUBLIC_PROVIDER_EXPORTS = {
    "AigupiaoDragonTigerProvider",
    "AigupiaoMarketNewsProvider",
    "AigupiaoMarketSentimentProvider",
    "AigupiaoSeriesLimitUpProvider",
    "BaiduFinscopeMarketNewsProvider",
    "EastMoneyStockKeywordProvider",
    "EastmoneyBreadthProvider",
    "EastmoneyBrokenLimitPoolProvider",
    "EastmoneyDisclosureProvider",
    "EastmoneyLimitDownPoolProvider",
    "EastmoneyLimitUpPoolProvider",
    "EastmoneyMarketNewsProvider",
    "EastmoneyNewsProvider",
    "EastmoneyStrongPoolProvider",
    "EastmoneyYesterdayLimitUpPoolProvider",
    "InstrumentListingProvider",
    "InstrumentProvider",
    "JiyangongsheReplayProvider",
    "KlinesProvider",
    "MarketQuoteProvider",
    "MarketRankingProvider",
    "PmcTradingCalendarProvider",
    "ProviderError",
    "SohuKlinesProvider",
    "SzseTradingCalendarProvider",
    "TencentF10Provider",
    "TencentFloatHolderProvider",
    "TencentFundFlowProvider",
    "TencentIndustryComparisonProvider",
    "TencentIntradayProvider",
    "TencentKlinesProvider",
    "TencentMarketProvider",
    "TencentQuoteProvider",
    "TencentSectorProvider",
    "TonghuashunFinancialProvider",
    "TradingCalendarProvider",
}

PUBLIC_ENDPOINTS = {
    "reference": ("instrument", "trading_calendar"),
    "market": (
        "breadth",
        "broken_limit_pool",
        "consecutive_limit_up",
        "daily_replay",
        "dragon_tiger_detail",
        "dragon_tiger_list",
        "equity_intraday",
        "equity_intraday_5d",
        "fund_flow_daily",
        "fund_flow_intraday",
        "fund_flow_snapshot",
        "index_intraday",
        "index_intraday_5d",
        "industry_comparison",
        "instrument_sector_snapshot",
        "stock_keyword",
        "limit_down_pool",
        "limit_up_pool",
        "ohlcv",
        "orderbook",
        "quote",
        "quote_snapshot",
        "ranking",
        "sentiment",
        "strong_pool",
        "yesterday_limit_up_pool",
    ),
    "fundamental": (
        "company_profile",
        "financial_summary",
        "industry_comparison",
        "revenue_breakdown",
    ),
    "financial": ("statements",),
    "news": ("search",),
    "disclosure": ("search",),
    "ownership": ("capital_snapshot", "float_holder", "holder_summary_snapshot"),
    "company": ("executive_share_change", "executive_snapshot"),
    "corporate_action": ("dividend", "repurchase"),
}

# A suffix of ``?`` means a parameter with a default. Keyword-only runtime
# controls are checked separately so the inventory stays readable.
PUBLIC_SIGNATURES = {
    "reference.instrument": "instrument_id? request? provider* use_cache*",
    "reference.trading_calendar": "start_date? end_date? market? request? provider* use_cache*",
    "market.breadth": "request? provider* use_cache*",
    "market.broken_limit_pool": "request provider* use_cache*",
    "market.consecutive_limit_up": "request? provider* use_cache*",
    "market.daily_replay": "request provider* use_cache*",
    "market.dragon_tiger_detail": "request provider* use_cache*",
    "market.dragon_tiger_list": "request provider* use_cache*",
    "market.equity_intraday": "request provider* use_cache*",
    "market.equity_intraday_5d": "request provider* use_cache*",
    "market.fund_flow_daily": "request provider* use_cache*",
    "market.fund_flow_intraday": "request provider* use_cache*",
    "market.fund_flow_snapshot": "request provider* use_cache*",
    "market.index_intraday": "request provider* use_cache*",
    "market.index_intraday_5d": "request provider* use_cache*",
    "market.industry_comparison": "request provider* use_cache*",
    "market.instrument_sector_snapshot": "request provider* use_cache*",
    "market.limit_down_pool": "request provider* use_cache*",
    "market.stock_keyword": "request provider* use_cache*",
    "market.limit_up_pool": "request provider* use_cache*",
    "market.ohlcv": "instrument_id? start_date? end_date? adjustment? request? provider* use_cache*",
    "market.orderbook": "request provider* use_cache*",
    "market.quote": "universe? request? provider* use_cache*",
    "market.quote_snapshot": "request provider* use_cache*",
    "market.ranking": "request provider* use_cache*",
    "market.sentiment": "request? provider* use_cache*",
    "market.strong_pool": "request provider* use_cache*",
    "market.yesterday_limit_up_pool": "request provider* use_cache*",
    "fundamental.company_profile": "instrument_id? request? provider* use_cache*",
    "fundamental.financial_summary": "request provider* use_cache*",
    "fundamental.industry_comparison": "request provider* use_cache*",
    "fundamental.revenue_breakdown": "request provider* use_cache*",
    "financial.statements": "instrument_id? statement_type? period_end? max_periods? request? provider* use_cache*",
    "news.search": "instrument? page? page_size? max_results? since? until? sort? request? provider* use_cache*",
    "disclosure.search": "instrument? page? page_size? max_results? since? until? categories? sort? request? provider* use_cache*",
    "ownership.capital_snapshot": "request provider* use_cache*",
    "ownership.float_holder": "request provider* use_cache*",
    "ownership.holder_summary_snapshot": "request provider* use_cache*",
    "company.executive_share_change": "request provider* use_cache*",
    "company.executive_snapshot": "request provider* use_cache*",
    "corporate_action.dividend": "request provider* use_cache*",
    "corporate_action.repurchase": "request provider* use_cache*",
}

CAPTURED_AT = datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc)


def _client_with_fake_collector():
    class FakeCollector:
        def __init__(self):
            self.calls = []

        def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
            self.calls.append((dataset, provider, use_cache, kwargs))
            return FetchResult(
                data=None,
                dataset=dataset,
                provider=provider or "public-test.fake",
                captured_at=CAPTURED_AT,
            )

    collector = FakeCollector()
    return FinchX(collector=collector), collector


def _signature_shape(method) -> str:
    shape = []
    for parameter in inspect.signature(method).parameters.values():
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            shape.append(f"{parameter.name}...args")
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            shape.append(f"{parameter.name}...kwargs")
        elif parameter.kind is inspect.Parameter.KEYWORD_ONLY and parameter.name in {
            "provider",
            "use_cache",
        }:
            shape.append(f"{parameter.name}*")
        elif parameter.default is not inspect.Parameter.empty:
            shape.append(f"{parameter.name}?")
        else:
            shape.append(parameter.name)
    return " ".join(shape)


def test_top_level_exports_match_the_public_contract_without_removing_compatibility_exports():
    assert set(finchx.__all__) == PUBLIC_TOP_LEVEL_EXPORTS


def test_namespace_and_endpoint_inventory_matches_real_client_code():
    actual = {
        namespace: tuple(
            endpoint.method
            for endpoint in CLIENT_ENDPOINTS
            if endpoint.namespace == namespace
        )
        for namespace in PUBLIC_ENDPOINTS
    }

    assert actual == PUBLIC_ENDPOINTS
    assert len(actual) == 9
    assert sum(len(methods) for methods in actual.values()) == 42
    assert len(CLIENT_ENDPOINTS) == 42


def test_registry_inventory_and_client_routes_match_the_public_contract():
    registered_datasets = {dataset.name for dataset in PROVIDER_REGISTRY.list_datasets()}
    client_datasets = {endpoint.dataset.name for endpoint in CLIENT_ENDPOINTS}
    registered_pairs = sum(
        len(PROVIDER_REGISTRY.providers_for(dataset))
        for dataset in PROVIDER_REGISTRY.list_datasets()
    )

    assert set(PROVIDER_EXPORTS) == PUBLIC_PROVIDER_EXPORTS
    assert len(PROVIDER_EXPORTS) == 36
    assert len(PROVIDER_REGISTRY.list_providers()) == 29
    assert len(registered_datasets) == 42
    assert client_datasets == registered_datasets
    assert registered_pairs == 47
    assert all(
        PROVIDER_REGISTRY.providers_for(endpoint.dataset)
        for endpoint in CLIENT_ENDPOINTS
    )


def test_computed_deviation_surface_is_outside_provider_inventory():
    client, _ = _client_with_fake_collector()
    method = client.market.deviation
    signature = inspect.signature(method)
    parameters = tuple(signature.parameters.values())

    assert tuple(parameter.name for parameter in parameters) == (
        "instrument_id",
        "windows",
        "as_of",
        "window_convention",
        "provider",
        "use_cache",
    )
    assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters[1:]
    )
    assert get_origin(get_type_hints(method)["return"]) is FetchResult
    assert all(
        endpoint.method != "deviation"
        for endpoint in CLIENT_ENDPOINTS
    )
    assert "market.deviation" not in {
        dataset.name for dataset in PROVIDER_REGISTRY.list_datasets()
    }


def test_all_public_endpoint_signatures_have_stable_parameters_and_return_types():
    client, _ = _client_with_fake_collector()

    actual = {}
    for endpoint in CLIENT_ENDPOINTS:
        method = getattr(getattr(client, endpoint.namespace), endpoint.method)
        key = f"{endpoint.namespace}.{endpoint.method}"
        actual[key] = _signature_shape(method)
        signature = inspect.signature(method)
        assert signature.return_annotation is not inspect.Signature.empty
        assert get_origin(get_type_hints(method)["return"]) is FetchResult
        assert signature.parameters["provider"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["use_cache"].kind is inspect.Parameter.KEYWORD_ONLY

    assert actual == PUBLIC_SIGNATURES
    assert all("...args" not in shape and "...kwargs" not in shape for shape in actual.values())


def test_all_public_endpoints_return_fetchresult_with_the_existing_contract():
    client, collector = _client_with_fake_collector()

    for endpoint in CLIENT_ENDPOINTS:
        method = getattr(getattr(client, endpoint.namespace), endpoint.method)
        result = method(
            request=endpoint.request_type.model_construct(),
            provider="public-test.fake",
            use_cache=True,
        )

        assert isinstance(result, FetchResult)
        assert result.dataset is endpoint.dataset
        assert result.provider == "public-test.fake"
        assert result.captured_at == CAPTURED_AT
        assert result.attempts == ()

    assert len(collector.calls) == 42


def test_advanced_api_imports_remain_available_and_distinct_from_primary_client():
    from finchx.collector import Collector, FetchResult as CollectorFetchResult
    from finchx.health import HealthMonitor
    from finchx.observability import ObservabilityMonitor
    from finchx.quality import QualityMonitor
    from finchx.storage import Cache, MemoryStorage, SQLiteStorage, Storage

    assert Collector is not FinchX
    assert CollectorFetchResult is FetchResult
    assert all(
        value is not None
        for value in (
            HealthMonitor,
            ObservabilityMonitor,
            QualityMonitor,
            Cache,
            MemoryStorage,
            SQLiteStorage,
            Storage,
        )
    )


def test_release_docs_and_example_use_public_endpoint_forms():
    root = Path(__file__).parents[1]
    readme = (root / "README.md").read_text()
    api_reference = (root / "docs" / "DATA_API_REFERENCE.md").read_text()
    example = (root / "examples" / "client_api.py").read_text()

    assert "from finchx import FinchX" in readme
    assert "result = fx.market.quote()" in readme
    assert "result = client.market.quote()" in example
    assert 'client.market.quote(provider="tencent.finance.qq.market")' in example
    assert "MissingOptionalDependency" in example
    assert "42 Provider-backed / Dataset-backed public endpoints" in api_reference
