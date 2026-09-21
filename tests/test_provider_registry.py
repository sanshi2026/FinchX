import pytest

from finchx import datasets as dataset_exports
from finchx import providers as provider_exports
from finchx.datasets import INSTRUMENT_DATASET, MARKET_KLINES_DATASET
from finchx.providers import (
    DatasetRoutingSemantics,
    ProviderRegistry,
    PROVIDER_REGISTRY,
    PROVIDER_SPECS,
    ProviderSpec,
    TencentKlinesProvider,
    TencentMarketProvider,
)


PROTOCOL_TYPES = {
    provider_exports.InstrumentProvider,
    provider_exports.InstrumentListingProvider,
    provider_exports.TradingCalendarProvider,
    provider_exports.MarketQuoteProvider,
    provider_exports.MarketRankingProvider,
    provider_exports.KlinesProvider,
}


def test_provider_inventory_is_explicitly_covered():
    public_providers = {
        getattr(provider_exports, name)
        for name in provider_exports.__all__
        if name.endswith("Provider")
    }
    registered_providers = {spec.provider for spec in PROVIDER_REGISTRY.list_providers()}
    assert len(PROVIDER_SPECS) == 29
    assert registered_providers == public_providers - PROTOCOL_TYPES
    assert not registered_providers.intersection(PROTOCOL_TYPES)

    public_datasets = {
        getattr(dataset_exports, name)
        for name in dataset_exports.__all__
        if name.endswith("_DATASET")
    }
    registered_datasets = set(PROVIDER_REGISTRY.list_datasets())
    assert len(public_datasets) == 42
    assert registered_datasets == public_datasets


def test_provider_ids_are_unique_and_duplicate_ids_are_rejected():
    provider_ids = [spec.provider_id for spec in PROVIDER_REGISTRY.list_providers()]
    assert len(provider_ids) == len(set(provider_ids))

    duplicate = ProviderSpec(
        provider_id=provider_ids[0],
        provider=type("UnregisteredProvider", (), {}),
        supported_datasets=(INSTRUMENT_DATASET,),
    )
    with pytest.raises(ValueError, match="duplicate provider_id"):
        ProviderRegistry((PROVIDER_SPECS[0], duplicate))


def test_provider_to_dataset_and_dataset_to_provider_queries():
    market_spec = PROVIDER_REGISTRY.get_provider("tencent.finance.qq.market")
    assert PROVIDER_REGISTRY.provider("tencent.finance.qq.market") is market_spec
    assert PROVIDER_REGISTRY.datasets_for("tencent.finance.qq.market") == (
        INSTRUMENT_DATASET,
        next(dataset for dataset in market_spec.supported_datasets if dataset.name == "market.quote"),
        next(dataset for dataset in market_spec.supported_datasets if dataset.name == "market.ranking"),
    )
    assert PROVIDER_REGISTRY.datasets_for(TencentMarketProvider) == market_spec.supported_datasets

    kline_provider_ids = {
        spec.provider_id for spec in PROVIDER_REGISTRY.providers_for(MARKET_KLINES_DATASET)
    }
    assert {"tencent.finance.qq.klines", "sohu.finance.klines"} <= kline_provider_ids
    assert PROVIDER_REGISTRY.get_provider("tencent.finance.qq.klines").provider is TencentKlinesProvider


def test_unknown_provider_and_dataset_fail_clearly():
    with pytest.raises(KeyError, match="unknown provider_id"):
        PROVIDER_REGISTRY.get_provider("does.not.exist")
    with pytest.raises(KeyError, match="unknown dataset"):
        PROVIDER_REGISTRY.providers_for("does.not.exist")
    with pytest.raises(KeyError, match="unknown provider class"):
        PROVIDER_REGISTRY.datasets_for(type("UnknownProvider", (), {}))


def test_auth_optional_dependency_and_source_semantics_are_metadata_only():
    replay = PROVIDER_REGISTRY.get_provider("jiuyangongshe.daily_replay")
    assert replay.requires_auth is True
    assert replay.optional_dependencies == ("playwright",)
    assert PROVIDER_REGISTRY.routing_semantics_for("market.daily_replay") is DatasetRoutingSemantics.SINGLE_SOURCE

    assert PROVIDER_REGISTRY.routing_semantics_for(MARKET_KLINES_DATASET) is DatasetRoutingSemantics.MULTI_PROVIDER
    assert PROVIDER_REGISTRY.routing_semantics_for("market.breadth") is DatasetRoutingSemantics.SINGLE_SOURCE

    for spec in PROVIDER_REGISTRY.list_providers():
        assert not hasattr(spec, "priority")
        assert not hasattr(spec, "fallback")
    assert not hasattr(PROVIDER_REGISTRY, "priority")
    assert not hasattr(PROVIDER_REGISTRY, "fallback")
