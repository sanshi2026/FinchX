from datetime import date, datetime, timezone
import inspect
from typing import get_args, get_origin, get_type_hints

import pytest
import finchx

from finchx import FinchX
from finchx import datasets
from finchx.client import CLIENT_ENDPOINTS
from finchx.collectors import Collector, FetchResult
from finchx.contracts.models import StandardRecord
from finchx.providers import PROVIDER_REGISTRY
from finchx.datasets import (
    DISCLOSURE_DOCUMENT_DATASET,
    DisclosureDocumentRef,
    FINANCIAL_STATEMENT_DATASET,
    FUNDAMENTAL_COMPANY_PROFILE_DATASET,
    MARKET_KLINES_DATASET,
    MARKET_RANKING_DATASET,
    MARKET_QUOTE_DATASET,
    NEWS_DOCUMENT_DATASET,
    NewsDocumentRef,
    InstrumentUniverse,
    KlineAdjustment,
    RankingCriterion,
    RankingDirection,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


class SpyCollector:
    def __init__(self):
        self.calls = []
        self.result = object()

    def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
        self.calls.append(
            {
                "dataset": dataset,
                "provider": provider,
                "use_cache": use_cache,
                "kwargs": kwargs,
            }
        )
        return self.result


def _instrument() -> InstrumentId:
    return InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )


def _index_instrument() -> InstrumentId:
    return InstrumentId(
        code="000001",
        market=Market.CN_A,
        kind=InstrumentKind.INDEX,
        exchange=Exchange.SSE,
    )


def test_public_client_exposes_shared_namespaces_and_no_default_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    client = FinchX()

    assert client.reference is not None
    assert not hasattr(client.reference, "instrument")
    assert client.market is not None
    assert client.fundamental is not None
    assert client.financial is not None
    assert client.news is not None
    assert client.articles is not None
    assert client.disclosure is not None
    assert client.market_news is not None
    assert client.forum is not None
    assert client.ownership is not None
    assert client.company is not None
    assert client.corporate_action is not None
    assert type(client.collector).__name__ == "Collector"
    assert list(tmp_path.iterdir()) == []


def test_forum_replies_requires_call_scoped_cookies():
    client = FinchX()
    assert "cookies" in inspect.signature(client.forum.replies).parameters
    assert inspect.signature(client.forum.replies).parameters["cookies"].default is inspect.Parameter.empty
    assert not hasattr(client.forum, "user_replies")
    assert not hasattr(client.forum, "following_replies")


def test_public_client_namespaces_share_one_collector():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    namespaces = {
        "reference",
        "market",
        "fundamental",
        "financial",
        "news",
        "articles",
        "disclosure",
        "forum",
        "ownership",
        "company",
        "corporate_action",
    }
    assert {getattr(client, name)._client for name in namespaces} == {client}


def test_representative_namespace_methods_build_real_requests_and_share_collector():
    collector = SpyCollector()
    client = FinchX(collector=collector)
    instrument = _instrument()

    assert client.market.quote(provider="tencent.finance.qq.market", use_cache=True) is collector.result
    assert client.market.ohlcv(
        instrument,
        date(2026, 9, 1),
        date(2026, 9, 18),
        "qfq",
    ) is collector.result
    assert client.fundamental.company_profile(instrument) is collector.result
    assert client.financial.statements(instrument, "income_statement") is collector.result
    assert client.news.search("600519", provider="eastmoney.news") is collector.result
    assert client.disclosure.search("600519") is collector.result

    assert client.reference._client is client
    assert client.market._client is client
    assert len(collector.calls) == 6
    assert collector.calls[0]["dataset"] is MARKET_QUOTE_DATASET
    assert collector.calls[1]["dataset"] is MARKET_KLINES_DATASET
    assert collector.calls[2]["dataset"] is FUNDAMENTAL_COMPANY_PROFILE_DATASET
    assert collector.calls[3]["dataset"] is FINANCIAL_STATEMENT_DATASET
    assert collector.calls[4]["dataset"] is NEWS_DOCUMENT_DATASET
    assert collector.calls[5]["dataset"] is DISCLOSURE_DOCUMENT_DATASET
    assert collector.calls[0]["provider"] == "tencent.finance.qq.market"
    assert collector.calls[0]["use_cache"] is True
    assert collector.calls[1]["kwargs"]["request"].adjustment is KlineAdjustment.QFQ
    assert collector.calls[3]["kwargs"]["request"].statement_type == "income_statement"
    assert collector.calls[4]["kwargs"]["request"].instrument_id == instrument
    assert collector.calls[5]["kwargs"]["request"].instrument_id == instrument


def test_public_document_namespaces_expose_search_and_detail_services():
    class StubService:
        def __init__(self, label):
            self.label = label
            self.calls = []

        def search(self, **kwargs):
            self.calls.append(("search", kwargs))
            return FetchResult(
                data=(f"{self.label}-ref",),
                dataset=NEWS_DOCUMENT_DATASET,
                provider="fake.market_news",
                captured_at=datetime.now(timezone.utc),
            )

        def search_result(self, **kwargs):
            return self.search(**kwargs)

        def get_document(self, ref):
            self.calls.append(("get_document", ref))
            return f"{self.label}-document:{ref}"

        def get_documents(self, refs):
            refs = tuple(refs)
            self.calls.append(("get_documents", refs))
            return tuple(f"{self.label}-document:{ref}" for ref in refs)

        def replies(self, **kwargs):
            self.calls.append(("replies", kwargs))
            return f"{self.label}-replies"

    client = FinchX(collector=SpyCollector())
    client._news_service = news = StubService("news")
    client._disclosure_service = disclosure = StubService("disclosure")
    client._market_news_service = market_news = StubService("market-news")
    client._forum_service = forum = StubService("forum")

    assert client.news.get_document("n1") == "news-document:n1"
    assert client.news.get_documents(["n1", "n2"]) == (
        "news-document:n1",
        "news-document:n2",
    )
    assert client.disclosure.get_document("d1") == "disclosure-document:d1"
    assert client.market_news.search(page_size=10, max_results=5).data == ("market-news-ref",)
    assert client.market_news.get_document("m1") == "market-news-document:m1"
    assert client.market_news.get_documents(["m1", "m2"]) == (
        "market-news-document:m1",
        "market-news-document:m2",
    )
    assert client.forum.replies(
        user_names=["u1", "u2"],
        max_results=5,
        cookies="session=value",
    ) == "forum-replies"
    assert news.calls == [("get_document", "n1"), ("get_documents", ("n1", "n2"))]
    assert disclosure.calls == [("get_document", "d1")]
    assert market_news.calls == [
        (
            "search",
            {
                "page": 1,
                "page_size": 10,
                "max_results": 5,
                "since": None,
                "until": None,
                "sort": "published_desc",
            },
        ),
        ("get_document", "m1"),
        ("get_documents", ("m1", "m2")),
    ]
    assert forum.calls == [("replies", {"user_names": ["u1", "u2"], "max_results": 5, "since": None, "until": None, "cookies": "session=value"})]


def test_ohlcv_public_signature_uses_string_adjustment_with_none_default():
    client = FinchX(collector=SpyCollector())
    signature = inspect.signature(client.market.ohlcv)
    hints = get_type_hints(client.market.ohlcv)

    assert hints["adjustment"] == (str | None)
    assert signature.parameters["adjustment"].default is None


@pytest.mark.parametrize(
    ("public_adjustment", "expected_adjustment"),
    [
        ("qfq", KlineAdjustment.QFQ),
        ("hfq", KlineAdjustment.HFQ),
        (None, KlineAdjustment.NONE),
    ],
)
def test_ohlcv_public_adjustments_map_to_internal_request_values(
    public_adjustment, expected_adjustment
):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    client.market.ohlcv(
        _instrument(),
        date(2026, 9, 1),
        date(2026, 9, 18),
        public_adjustment,
    )

    request = collector.calls[0]["kwargs"]["request"]
    assert request.adjustment is expected_adjustment


def test_ohlcv_equity_default_is_equivalent_to_explicit_none():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    client.market.ohlcv(_instrument(), date(2026, 9, 1), date(2026, 9, 18))
    client.market.ohlcv(_instrument(), date(2026, 9, 1), date(2026, 9, 18), None)

    assert [call["kwargs"]["request"].adjustment for call in collector.calls] == [
        KlineAdjustment.NONE,
        KlineAdjustment.NONE,
    ]


class _AdjustmentString(str):
    pass


@pytest.mark.parametrize(
    "adjustment",
    [
        KlineAdjustment.NONE,
        KlineAdjustment.QFQ,
        KlineAdjustment.HFQ,
        KlineAdjustment.NOT_APPLICABLE,
        "none",
        "QFQ",
        " hfq",
        "qfq ",
        "",
        _AdjustmentString("qfq"),
        1,
        True,
    ],
)
def test_ohlcv_rejects_non_public_equity_adjustments_before_collector(adjustment):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    with pytest.raises(ValueError, match=r"qfq, hfq, None"):
        client.market.ohlcv(
            _instrument(),
            date(2026, 9, 1),
            date(2026, 9, 18),
            adjustment,
        )

    assert collector.calls == []


def test_ohlcv_index_none_omits_internal_adjustment():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    client.market.ohlcv(
        _index_instrument(),
        date(2026, 9, 1),
        date(2026, 9, 18),
        None,
    )

    request = collector.calls[0]["kwargs"]["request"]
    assert request.adjustment is None
    assert "adjustment" not in request.model_fields_set


@pytest.mark.parametrize("adjustment", ["qfq", "hfq", "none", KlineAdjustment.NONE, 1])
def test_ohlcv_rejects_any_explicit_index_adjustment_before_collector(adjustment):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    with pytest.raises(ValueError, match="must be None"):
        client.market.ohlcv(
            _index_instrument(),
            date(2026, 9, 1),
            date(2026, 9, 18),
            adjustment,
        )

    assert collector.calls == []


@pytest.mark.parametrize(
    ("criterion", "expected_criterion"),
    [
        ("amount", RankingCriterion.TURNOVER),
        ("zdf", RankingCriterion.CHANGE_PERCENT),
        ("volume", RankingCriterion.VOLUME),
    ],
)
@pytest.mark.parametrize(
    ("direction", "expected_direction"),
    [("asc", RankingDirection.ASCENDING), ("desc", RankingDirection.DESCENDING)],
)
def test_ranking_public_strings_map_to_the_existing_internal_request(
    criterion, expected_criterion, direction, expected_direction
):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    assert client.market.ranking(criterion, direction, 20) is collector.result

    call = collector.calls[0]
    assert call["dataset"] is MARKET_RANKING_DATASET
    request = call["kwargs"]["request"]
    assert request.universe is InstrumentUniverse.CN_A_SHARE
    assert request.criterion is expected_criterion
    assert request.direction is expected_direction
    assert request.limit == 20


@pytest.mark.parametrize("limit", [None, 1, 20])
def test_ranking_limit_accepts_none_or_positive_integer(limit):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    client.market.ranking("amount", "desc", limit)

    assert collector.calls[0]["kwargs"]["request"].limit == limit


@pytest.mark.parametrize(
    "criterion",
    [
        "turnover",
        "change_percent",
        "Amount",
        " amount",
        "amount ",
        "",
        RankingCriterion.TURNOVER,
        RankingCriterion.CHANGE_PERCENT,
        RankingCriterion.VOLUME,
    ],
)
def test_ranking_rejects_non_public_criterion_before_collector(criterion):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    with pytest.raises(ValueError, match=r"amount, zdf, volume"):
        client.market.ranking(criterion, "desc", 20)

    assert collector.calls == []


@pytest.mark.parametrize(
    "direction",
    [
        "ascending",
        "descending",
        "Asc",
        " desc",
        "desc ",
        "",
        RankingDirection.ASCENDING,
        RankingDirection.DESCENDING,
    ],
)
def test_ranking_rejects_non_public_direction_before_collector(direction):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    with pytest.raises(ValueError, match=r"asc, desc"):
        client.market.ranking("amount", direction, 20)

    assert collector.calls == []


@pytest.mark.parametrize("limit", [0, -1, True, False, 1.0, "20"])
def test_ranking_rejects_invalid_limit_before_collector(limit):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    with pytest.raises(ValueError):
        client.market.ranking("amount", "desc", limit)

    assert collector.calls == []


def test_ranking_no_longer_accepts_public_universe_argument():
    client = FinchX(collector=SpyCollector())

    with pytest.raises(TypeError):
        client.market.ranking(
            universe=InstrumentUniverse.CN_A_SHARE,
            criterion="amount",
            direction="desc",
            limit=20,
        )


def test_client_request_objects_and_generic_fetch_are_thin_delegations():
    collector = SpyCollector()
    client = FinchX(collector=collector)
    instrument = _instrument()

    from finchx.datasets import MarketQuoteUniverseRequest

    request = MarketQuoteUniverseRequest(universe="cn_a_share")
    assert client.fetch("market.quote@1.0", provider="fake.provider", request=request) is collector.result

    assert collector.calls[0]["dataset"] == "market.quote@1.0"
    assert collector.calls[0]["provider"] == "fake.provider"
    assert collector.calls[0]["kwargs"] == {"request": request}


def test_client_does_not_hide_collector_errors():
    class FailingCollector(SpyCollector):
        def fetch(self, *args, **kwargs):
            raise RuntimeError("preserve this failure")

    client = FinchX(collector=FailingCollector())
    with pytest.raises(RuntimeError, match="preserve this failure"):
        client.market.quote()


@pytest.mark.parametrize(
    "method_name, request_type",
    [
        ("limit_up_pool", datasets.MarketLimitUpPoolRequest),
        ("limit_down_pool", datasets.MarketLimitDownPoolRequest),
        ("broken_limit_pool", datasets.MarketBrokenLimitPoolRequest),
        ("strong_pool", datasets.MarketStrongPoolRequest),
        ("yesterday_limit_up_pool", datasets.MarketYesterdayLimitUpPoolRequest),
    ],
)
def test_latest_snapshot_pool_methods_build_empty_requests_by_default(method_name, request_type):
    collector = SpyCollector()
    client = FinchX(collector=collector)

    assert getattr(client.market, method_name)() is collector.result

    request = collector.calls[0]["kwargs"]["request"]
    assert isinstance(request, request_type)
    assert request.__dict__["trade_date"] is None
    assert request.model_dump(exclude_none=True, by_alias=True) == {}


def test_collector_configuration_cannot_be_silently_ignored():
    with pytest.raises(ValueError, match="cannot be combined"):
        FinchX(collector=SpyCollector(), cache=object())


def test_every_public_dataset_has_one_explicit_client_endpoint():
    public_datasets = {
        getattr(datasets, name).name
        for name in datasets.__all__
        if name.endswith("_DATASET")
    }
    mapped_datasets = {endpoint.dataset.name for endpoint in CLIENT_ENDPOINTS}

    assert len(CLIENT_ENDPOINTS) == 54
    assert len(mapped_datasets) == len(CLIENT_ENDPOINTS)
    assert mapped_datasets == public_datasets - {"instrument", "forum.replies"}
    for endpoint in CLIENT_ENDPOINTS:
        assert endpoint.dataset.request_type is endpoint.request_type
        assert callable(getattr(getattr(FinchX(collector=SpyCollector()), endpoint.namespace), endpoint.method))


def test_public_api_surface_has_stable_namespaces_and_fetchresult_contract():
    expected_namespaces = {
        "reference",
        "market",
        "fundamental",
        "financial",
        "iwencai",
        "news",
        "articles",
        "disclosure",
        "ownership",
        "company",
        "corporate_action",
        "hotlist",
    }
    assert {endpoint.namespace for endpoint in CLIENT_ENDPOINTS} == expected_namespaces
    assert {"FinchX", "Collector", "CLIENT_ENDPOINTS"}.issubset(finchx.__all__)
    assert "MarketNamespace" not in finchx.__all__

    client = FinchX(collector=SpyCollector())
    assert client.market_news._client is client
    market_news_return = get_type_hints(client.market_news.search)["return"]
    assert get_origin(market_news_return) is FetchResult
    assert get_args(market_news_return) == (tuple[NewsDocumentRef, ...],)
    for endpoint in CLIENT_ENDPOINTS:
        method = getattr(getattr(client, endpoint.namespace), endpoint.method)
        signature = inspect.signature(method)
        assert signature.parameters["provider"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["use_cache"].kind is inspect.Parameter.KEYWORD_ONLY
        return_type = get_type_hints(method)["return"]
        assert get_origin(return_type) is FetchResult
        if endpoint.dataset.name == "news.document":
            expected = tuple[NewsDocumentRef, ...]
        elif endpoint.dataset.name == "disclosure.document":
            expected = tuple[DisclosureDocumentRef, ...]
        elif endpoint.namespace == "articles" and endpoint.method == "get":
            expected = StandardRecord
        else:
            expected = tuple[StandardRecord, ...]
        assert get_args(return_type) == (expected,)


def test_all_explicit_client_endpoints_hide_their_typed_request_model():
    client = FinchX(collector=SpyCollector())

    for endpoint in CLIENT_ENDPOINTS:
        method = getattr(getattr(client, endpoint.namespace), endpoint.method)
        signature = inspect.signature(method)
        assert "request" not in signature.parameters
        assert all(
            "InstrumentInput" not in str(parameter.annotation)
            and "InstrumentId" not in str(parameter.annotation)
            for parameter in signature.parameters.values()
        )


def test_collector_default_routes_cover_every_registered_dataset_provider_pair():
    collector = Collector()
    missing = [
        (dataset.name, spec.provider_id)
        for spec in PROVIDER_REGISTRY.list_providers()
        for dataset in spec.supported_datasets
        if (dataset.name, spec.provider_id) not in collector._routes
    ]

    assert missing == []
