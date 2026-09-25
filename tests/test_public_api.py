"""Public v1 Client API contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
from pathlib import Path
import sys
from typing import get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import finchx
from finchx import FinchX
from finchx.client import CLIENT_ENDPOINTS
from finchx.collectors import FetchResult
from finchx.providers import __all__ as PROVIDER_EXPORTS
from finchx.providers.registry import PROVIDER_REGISTRY
from tools.generate_api_reference import all_endpoint_keys, computed_endpoint_keys


PUBLIC_TOP_LEVEL_EXPORTS = {
    "ArticleDetailService",
    "CLIENT_ENDPOINTS",
    "Collector",
    "DisclosureService",
    "FinancialStatementService",
    "FinchX",
    "ForumService",
    "MarketNewsService",
    "NewsService",
    "__version__",
    "disclosure",
    "financial_statements",
    "forum",
    "market_news",
    "news",
}

PUBLIC_PROVIDER_EXPORTS = {
    "ArticleDetailSourceError",
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
    "IwencaiProvider",
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
    "TonghuashunConceptProvider",
    "THSHotListProvider",
    "TradingCalendarProvider",
    "THSArticleDetailProvider",
    "THSTopicArticlesProvider",
}

PUBLIC_ENDPOINTS = {
    "reference": ("trading_calendar",),
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
        "concept_list",
        "concept_quote_snapshot",
        "concept_ohlcv",
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
    "hotlist": ("stocks", "sectors", "convertible_bonds", "etfs", "content"),
    "fundamental": (
        "company_profile",
        "financial_summary",
        "industry_comparison",
        "revenue_breakdown",
    ),
    "financial": ("statements",),
    "iwencai": ("select", "search", "report_detail"),
    "news": ("search",),
    "articles": ("get", "from_topic"),
    "disclosure": ("search",),
    "ownership": ("capital_snapshot", "float_holder", "holder_summary_snapshot"),
    "company": ("executive_share_change", "executive_snapshot"),
    "corporate_action": ("dividend", "repurchase"),
}

# A suffix of ``?`` means a parameter with a default. Keyword-only runtime
# controls are checked separately so the inventory stays readable.
PUBLIC_SIGNATURES = {
    "reference.trading_calendar": "start_date end_date provider* use_cache*",
    "market.breadth": "provider* use_cache*",
    "market.broken_limit_pool": "provider* use_cache*",
    "market.consecutive_limit_up": "provider* use_cache*",
    "market.daily_replay": "requested_date session provider* use_cache*",
    "market.dragon_tiger_detail": "instrument trade_date trade_id provider* use_cache*",
    "market.dragon_tiger_list": "trade_date provider* use_cache*",
    "market.equity_intraday": "instrument provider* use_cache*",
    "market.equity_intraday_5d": "instrument provider* use_cache*",
    "market.fund_flow_daily": "instrument provider* use_cache*",
    "market.fund_flow_intraday": "instrument provider* use_cache*",
    "market.fund_flow_snapshot": "instrument provider* use_cache*",
    "market.index_intraday": "instrument provider* use_cache*",
    "market.index_intraday_5d": "instrument provider* use_cache*",
    "market.industry_comparison": "instrument provider* use_cache*",
    "market.instrument_sector_snapshot": "instrument provider* use_cache*",
    "market.concept_list": "provider* use_cache*",
    "market.concept_quote_snapshot": "concept provider* use_cache*",
    "market.concept_ohlcv": "concept start_date end_date provider* use_cache*",
    "market.limit_down_pool": "provider* use_cache*",
    "market.stock_keyword": "instrument provider* use_cache*",
    "market.limit_up_pool": "provider* use_cache*",
    "market.ohlcv": "instrument start_date end_date adjustment? provider* use_cache*",
    "market.orderbook": "instrument provider* use_cache*",
    "market.quote": "universe? provider* use_cache*",
    "market.quote_snapshot": "instrument provider* use_cache*",
    "market.ranking": "criterion direction limit provider* use_cache*",
    "market.sentiment": "provider* use_cache*",
    "market.strong_pool": "provider* use_cache*",
    "market.yesterday_limit_up_pool": "provider* use_cache*",
    "hotlist.stocks": "category? period? limit? provider* use_cache*",
    "hotlist.sectors": "sector_type? limit? provider* use_cache*",
    "hotlist.convertible_bonds": "limit? provider* use_cache*",
    "hotlist.etfs": "category? limit? provider* use_cache*",
    "hotlist.content": "content_type? limit? provider* use_cache*",
    "articles.get": "url provider* use_cache*",
    "articles.from_topic": "topic_url sort? limit? provider* use_cache*",
    "fundamental.company_profile": "instrument provider* use_cache*",
    "fundamental.financial_summary": "instrument provider* use_cache*",
    "fundamental.industry_comparison": "instrument provider* use_cache*",
    "fundamental.revenue_breakdown": "instrument provider* use_cache*",
    "financial.statements": "instrument statement_type period_end? max_periods? provider* use_cache*",
    "iwencai.select": "query cookies user_agent? page_size? max_pages? provider* use_cache*",
    "iwencai.search": "query channel? size? cookies? api_key? deduplicate? provider* use_cache*",
    "iwencai.report_detail": "url cookies uid? title? published_at? user_agent? provider* use_cache*",
    "news.search": "instrument page? page_size? max_results? since? until? sort? provider* use_cache*",
    "disclosure.search": "instrument page? page_size? max_results? since? until? categories? sort? provider* use_cache*",
    "ownership.capital_snapshot": "instrument provider* use_cache*",
    "ownership.float_holder": "instrument provider* use_cache*",
    "ownership.holder_summary_snapshot": "instrument provider* use_cache*",
    "company.executive_share_change": "instrument provider* use_cache*",
    "company.executive_snapshot": "instrument provider* use_cache*",
    "corporate_action.dividend": "instrument provider* use_cache*",
    "corporate_action.repurchase": "instrument provider* use_cache*",
}

CAPTURED_AT = datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc)


def _client_with_fake_collector():
    class FakeCollector:
        def __init__(self):
            self.calls = []

        def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
            self.calls.append((dataset, provider, use_cache, kwargs))
            if dataset.name == "articles.detail":
                from finchx.contracts import Source
                from finchx.datasets.article_detail import normalize_article_detail

                request = kwargs["request"]
                record = normalize_article_detail(
                    request,
                    {
                        "contentId": request.content_id,
                        "contentType": request.content_type or "news",
                        "title": "Fixture article",
                        "contentHtml": "<p>Fixture article body.</p>",
                        "contentText": "Fixture article body.",
                        "capturedAt": CAPTURED_AT,
                    },
                    source=Source(providerId=provider or "public-test.fake"),
                )
                return FetchResult(
                    data=record,
                    dataset=dataset,
                    provider=provider or "public-test.fake",
                    captured_at=CAPTURED_AT,
                )
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
    assert len(actual) == len(PUBLIC_ENDPOINTS)
    assert sum(len(methods) for methods in actual.values()) == len(CLIENT_ENDPOINTS)
    assert len(CLIENT_ENDPOINTS) == sum(len(methods) for methods in PUBLIC_ENDPOINTS.values())


def test_registry_inventory_and_client_routes_match_the_public_contract():
    registered_datasets = {dataset.name for dataset in PROVIDER_REGISTRY.list_datasets()}
    client_datasets = {endpoint.dataset.name for endpoint in CLIENT_ENDPOINTS}
    registered_pairs = sum(
        len(PROVIDER_REGISTRY.providers_for(dataset))
        for dataset in PROVIDER_REGISTRY.list_datasets()
    )

    assert set(PROVIDER_EXPORTS) == PUBLIC_PROVIDER_EXPORTS
    assert len(PROVIDER_EXPORTS) == 42
    assert len(PROVIDER_REGISTRY.list_providers()) == 34
    assert len(registered_datasets) == len(client_datasets) + 1
    assert client_datasets == registered_datasets - {"instrument"}
    assert registered_pairs == 60
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
        "instrument",
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


def test_ohlcv_public_adjustment_annotation_is_string_or_none():
    client, _ = _client_with_fake_collector()
    method = client.market.ohlcv
    parameter = inspect.signature(method).parameters["adjustment"]

    assert get_type_hints(method)["adjustment"] == (str | None)
    assert parameter.default is None


def _call_public_endpoint(client, endpoint):
    method = getattr(getattr(client, endpoint.namespace), endpoint.method)
    key = f"{endpoint.namespace}.{endpoint.method}"
    def invoke(*args, **kwargs):
        kwargs.update(provider="public-test.fake", use_cache=True)
        return method(*args, **kwargs)

    if key == "reference.trading_calendar":
        return invoke("2026-09-01", "2026-09-30")
    if key == "market.quote":
        return invoke()
    if key == "market.concept_list":
        return invoke()
    if key in {
        "market.concept_quote_snapshot",
    }:
        return invoke("人工智能")
    if key == "market.concept_ohlcv":
        return invoke("人工智能", "2026-09-01", "2026-09-23")
    if key == "market.ohlcv":
        return invoke("600519", "2026-09-01", "2026-09-18", "qfq")
    if key == "market.daily_replay":
        return invoke("2026-09-18", session="placeholder-session")
    if key == "market.dragon_tiger_detail":
        return invoke("600519", "2026-09-18", "example-trade-id")
    if key == "market.dragon_tiger_list":
        return invoke("2026-09-18")
    if key == "market.ranking":
        return invoke("amount", "desc", 20)
    if key == "financial.statements":
        return invoke("600519", "income_statement")
    if key == "iwencai.select":
        return invoke("非ST", cookies="sid=owned")
    if key == "iwencai.search":
        return invoke("人形机器人", cookies="sid=owned", api_key="key")
    if key == "iwencai.report_detail":
        return invoke(
            "https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html?duid=d9924066929303a3",
            cookies="sid=owned",
        )
    if key == "articles.get":
        return invoke("https://stock.10jqka.com.cn/20260924/c680232196.shtml")
    if key == "articles.from_topic":
        return invoke("https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=T4dryo6")
    if endpoint.namespace in {"news", "disclosure"}:
        return invoke("600519")
    if endpoint.namespace == "market" and endpoint.method.startswith("index_"):
        return invoke("000001")
    if endpoint.namespace in {"market", "fundamental", "ownership", "company", "corporate_action"}:
        if endpoint.method not in {
            "breadth",
            "broken_limit_pool",
            "consecutive_limit_up",
            "limit_down_pool",
            "limit_up_pool",
            "sentiment",
            "strong_pool",
            "yesterday_limit_up_pool",
            "quote",
            "ranking",
        }:
            return invoke("600519")
    return invoke()


def test_all_public_endpoints_return_fetchresult_with_the_existing_contract():
    client, collector = _client_with_fake_collector()

    for endpoint in CLIENT_ENDPOINTS:
        method = getattr(getattr(client, endpoint.namespace), endpoint.method)
        result = _call_public_endpoint(client, endpoint)

        assert isinstance(result, FetchResult)
        assert result.dataset is endpoint.dataset
        assert result.provider == "public-test.fake"
        assert result.captured_at == CAPTURED_AT
        assert result.attempts == ()

    assert len(collector.calls) == len(CLIENT_ENDPOINTS)


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
    readme_zh = (root / "README.zh-CN.md").read_text()
    api_reference = (root / "docs" / "DATA_API_REFERENCE.md").read_text()
    example = (root / "examples" / "client_api.py").read_text()

    assert "from finchx import FinchX" in readme
    assert "result = fx.market.quote_snapshot(" in readme
    assert 'print(record.data["price"])' in readme
    assert "rows = result.to_dicts()" in readme
    assert "result = fx.market.quote_snapshot(" in readme_zh
    assert "record.data 是业务数据" in readme_zh
    assert "rows = result.to_dicts()" in readme_zh
    assert "https://github.com/sanshi2026/FinchX/blob/main/docs/DATA_API_REFERENCE.md" in readme
    assert "https://github.com/sanshi2026/FinchX/blob/main/docs/DATA_API_REFERENCE.zh-CN.md" in readme_zh
    assert "result = client.market.quote(" in example
    assert "provider=" not in example
    assert "use_cache=" not in example
    assert 'market=Market.CN_A' not in example
    assert 'adjustment="qfq"' in readme
    assert "KlineAdjustment" not in readme
    assert (
        f"This document covers {len(CLIENT_ENDPOINTS)} data interfaces and "
        f"{len(computed_endpoint_keys())} computed capability, for "
        f"{len(all_endpoint_keys())} core capabilities."
    ) in api_reference
