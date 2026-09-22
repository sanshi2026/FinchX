from datetime import date
import inspect
from typing import get_args, get_origin, get_type_hints

import pytest
import finchx

from finchx import FinchX
from finchx import datasets
from finchx.client import CLIENT_ENDPOINTS
from finchx.collectors import Collector, FetchResult
from finchx.providers import PROVIDER_REGISTRY
from finchx.datasets import (
    DISCLOSURE_DOCUMENT_DATASET,
    FINANCIAL_STATEMENT_DATASET,
    FUNDAMENTAL_COMPANY_PROFILE_DATASET,
    INSTRUMENT_DATASET,
    MARKET_KLINES_DATASET,
    MARKET_QUOTE_DATASET,
    NEWS_DOCUMENT_DATASET,
    KlineAdjustment,
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


def test_public_client_exposes_shared_namespaces_and_no_default_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    client = FinchX()

    assert client.reference is not None
    assert client.market is not None
    assert client.fundamental is not None
    assert client.financial is not None
    assert client.news is not None
    assert client.disclosure is not None
    assert client.ownership is not None
    assert client.company is not None
    assert client.corporate_action is not None
    assert type(client.collector).__name__ == "Collector"
    assert list(tmp_path.iterdir()) == []


def test_public_client_namespaces_share_one_collector():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    namespaces = {
        "reference",
        "market",
        "fundamental",
        "financial",
        "news",
        "disclosure",
        "ownership",
        "company",
        "corporate_action",
    }
    assert {getattr(client, name)._client for name in namespaces} == {client}


def test_representative_namespace_methods_build_real_requests_and_share_collector():
    collector = SpyCollector()
    client = FinchX(collector=collector)
    instrument = _instrument()

    assert client.reference.instrument(instrument) is collector.result
    assert client.market.quote(provider="tencent.finance.qq.market", use_cache=True) is collector.result
    assert client.market.ohlcv(
        instrument,
        date(2026, 9, 1),
        date(2026, 9, 18),
        KlineAdjustment.QFQ,
    ) is collector.result
    assert client.fundamental.company_profile(instrument) is collector.result
    assert client.financial.statements(instrument, "income_statement") is collector.result
    assert client.news.search("600519", provider="eastmoney.news") is collector.result
    assert client.disclosure.search("600519") is collector.result

    assert client.reference._client is client
    assert client.market._client is client
    assert len(collector.calls) == 7
    assert collector.calls[0]["dataset"] is INSTRUMENT_DATASET
    assert collector.calls[1]["dataset"] is MARKET_QUOTE_DATASET
    assert collector.calls[2]["dataset"] is MARKET_KLINES_DATASET
    assert collector.calls[3]["dataset"] is FUNDAMENTAL_COMPANY_PROFILE_DATASET
    assert collector.calls[4]["dataset"] is FINANCIAL_STATEMENT_DATASET
    assert collector.calls[5]["dataset"] is NEWS_DOCUMENT_DATASET
    assert collector.calls[6]["dataset"] is DISCLOSURE_DOCUMENT_DATASET
    assert collector.calls[1]["provider"] == "tencent.finance.qq.market"
    assert collector.calls[1]["use_cache"] is True
    assert collector.calls[2]["kwargs"]["request"].adjustment is KlineAdjustment.QFQ
    assert collector.calls[4]["kwargs"]["request"].statement_type == "income_statement"
    assert collector.calls[5]["kwargs"]["request"].instrument_id == instrument
    assert collector.calls[6]["kwargs"]["request"].instrument_id == instrument


def test_client_request_objects_and_generic_fetch_are_thin_delegations():
    collector = SpyCollector()
    client = FinchX(collector=collector)
    instrument = _instrument()

    from finchx.datasets import InstrumentRequest

    request = InstrumentRequest(instrumentId=instrument)
    assert client.reference.instrument(request=request) is collector.result
    assert client.fetch("market.quote@1.0", provider="fake.provider", request=request) is collector.result

    assert collector.calls[0]["kwargs"] == {"request": request}
    assert collector.calls[1]["dataset"] == "market.quote@1.0"
    assert collector.calls[1]["provider"] == "fake.provider"


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

    assert len(CLIENT_ENDPOINTS) == 42
    assert len(mapped_datasets) == len(CLIENT_ENDPOINTS)
    assert mapped_datasets == public_datasets
    for endpoint in CLIENT_ENDPOINTS:
        assert endpoint.dataset.request_type is endpoint.request_type
        assert callable(getattr(getattr(FinchX(collector=SpyCollector()), endpoint.namespace), endpoint.method))


def test_public_api_surface_has_stable_namespaces_and_fetchresult_contract():
    expected_namespaces = {
        "reference",
        "market",
        "fundamental",
        "financial",
        "news",
        "disclosure",
        "ownership",
        "company",
        "corporate_action",
    }
    assert {endpoint.namespace for endpoint in CLIENT_ENDPOINTS} == expected_namespaces
    assert {"FinchX", "Collector", "CLIENT_ENDPOINTS"}.issubset(finchx.__all__)
    assert "MarketNamespace" not in finchx.__all__

    client = FinchX(collector=SpyCollector())
    for endpoint in CLIENT_ENDPOINTS:
        method = getattr(getattr(client, endpoint.namespace), endpoint.method)
        signature = inspect.signature(method)
        assert signature.parameters["provider"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["use_cache"].kind is inspect.Parameter.KEYWORD_ONLY
        return_type = get_type_hints(method)["return"]
        assert get_origin(return_type) is FetchResult
        if endpoint.dataset.name not in {"news.document", "disclosure.document"}:
            assert get_args(return_type) == (endpoint.dataset.data_type,)


def test_all_explicit_client_endpoints_delegate_their_typed_request_model():
    collector = SpyCollector()
    client = FinchX(collector=collector)

    for endpoint in CLIENT_ENDPOINTS:
        request = endpoint.request_type.model_construct()
        method = getattr(getattr(client, endpoint.namespace), endpoint.method)
        assert method(request=request) is collector.result

    assert len(collector.calls) == len(CLIENT_ENDPOINTS)
    assert [call["dataset"].name for call in collector.calls] == [
        endpoint.dataset.name for endpoint in CLIENT_ENDPOINTS
    ]
    assert all(call["kwargs"]["request"] is not None for call in collector.calls)


def test_collector_default_routes_cover_every_registered_dataset_provider_pair():
    collector = Collector()
    missing = [
        (dataset.name, spec.provider_id)
        for spec in PROVIDER_REGISTRY.list_providers()
        for dataset in spec.supported_datasets
        if (dataset.name, spec.provider_id) not in collector._routes
    ]

    assert missing == []
