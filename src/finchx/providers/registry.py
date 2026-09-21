"""Explicit Provider capability registry for FinchX.

The registry is deliberately declarative.  It records which exported Provider
type can supply which Dataset and the minimum metadata needed by a caller to
understand that capability.  It does not construct Providers, collect data, or
choose an implementation for a request.
"""

from dataclasses import dataclass, field
from enum import Enum
from re import fullmatch
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from finchx.datasets import (
    COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET,
    COMPANY_EXECUTIVE_SNAPSHOT_DATASET,
    CORPORATE_ACTION_DIVIDEND_DATASET,
    CORPORATE_ACTION_REPURCHASE_DATASET,
    DISCLOSURE_DOCUMENT_DATASET,
    FINANCIAL_STATEMENT_DATASET,
    FUNDAMENTAL_COMPANY_PROFILE_DATASET,
    FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,
    FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET,
    FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET,
    INSTRUMENT_DATASET,
    MARKET_BREADTH_DATASET,
    MARKET_BROKEN_LIMIT_POOL_DATASET,
    MARKET_CONSECUTIVE_LIMIT_UP_DATASET,
    MARKET_DAILY_REPLAY_DATASET,
    MARKET_DRAGON_TIGER_DETAIL_DATASET,
    MARKET_DRAGON_TIGER_LIST_DATASET,
    MARKET_EQUITY_INTRADAY_5D_DATASET,
    MARKET_EQUITY_INTRADAY_DATASET,
    MARKET_FUND_FLOW_DAILY_DATASET,
    MARKET_FUND_FLOW_INTRADAY_DATASET,
    MARKET_FUND_FLOW_SNAPSHOT_DATASET,
    MARKET_INDEX_INTRADAY_5D_DATASET,
    MARKET_INDEX_INTRADAY_DATASET,
    MARKET_INDUSTRY_COMPARISON_DATASET,
    MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET,
    MARKET_STOCK_KEYWORD_DATASET,
    MARKET_KLINES_DATASET,
    MARKET_LIMIT_DOWN_POOL_DATASET,
    MARKET_LIMIT_UP_POOL_DATASET,
    MARKET_ORDERBOOK_DATASET,
    MARKET_QUOTE_DATASET,
    MARKET_QUOTE_SNAPSHOT_DATASET,
    MARKET_RANKING_DATASET,
    MARKET_SENTIMENT_DATASET,
    MARKET_STRONG_POOL_DATASET,
    MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET,
    NEWS_DOCUMENT_DATASET,
    OWNERSHIP_CAPITAL_SNAPSHOT_DATASET,
    OWNERSHIP_FLOAT_HOLDER_DATASET,
    OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET,
    TRADING_CALENDAR_DATASET,
)
from finchx.datasets.definition import DatasetDefinition
from finchx.providers.aigupiao_market_intelligence import (
    AigupiaoDragonTigerProvider,
    AigupiaoMarketSentimentProvider,
    AigupiaoSeriesLimitUpProvider,
)
from finchx.providers.eastmoney_documents import EastmoneyDisclosureProvider, EastmoneyNewsProvider
from finchx.providers.eastmoney_market import (
    EastmoneyBreadthProvider,
    EastmoneyBrokenLimitPoolProvider,
    EastmoneyLimitDownPoolProvider,
    EastmoneyLimitUpPoolProvider,
    EastmoneyStrongPoolProvider,
    EastmoneyYesterdayLimitUpPoolProvider,
)
from finchx.providers.jiuyangongshe_replay import JiyangongsheReplayProvider
from finchx.providers.market_news import (
    AigupiaoMarketNewsProvider,
    BaiduFinscopeMarketNewsProvider,
    EastmoneyMarketNewsProvider,
)
from finchx.providers.sohu_klines import SohuKlinesProvider
from finchx.providers.tencent import TencentMarketProvider
from finchx.providers.tencent_f10 import TencentF10Provider
from finchx.providers.tencent_float_holder import TencentFloatHolderProvider
from finchx.providers.tencent_fund_flow import TencentFundFlowProvider
from finchx.providers.tencent_industry import TencentIndustryComparisonProvider
from finchx.providers.tencent_intraday import TencentIntradayProvider
from finchx.providers.tencent_klines import TencentKlinesProvider
from finchx.providers.tencent_quote import TencentQuoteProvider
from finchx.providers.eastmoney_stock_keyword import EastMoneyStockKeywordProvider
from finchx.providers.tencent_sector import TencentSectorProvider
from finchx.providers.tonghuashun_financial import TonghuashunFinancialProvider
from finchx.providers.trading_calendar import (
    PmcTradingCalendarProvider,
    SzseTradingCalendarProvider,
)


class DatasetRoutingSemantics(str, Enum):
    """Whether a Dataset contract can admit future peer Providers."""

    MULTI_PROVIDER = "multi_provider"
    SINGLE_SOURCE = "single_source"


@dataclass(frozen=True)
class ProviderSpec:
    """Declarative identity and capabilities for one exported Provider type."""

    provider_id: str
    provider: type[Any]
    supported_datasets: tuple[DatasetDefinition[Any, Any], ...]
    requires_auth: bool = False
    optional_dependencies: tuple[str, ...] = ()
    routing_semantics: Mapping[str, DatasetRoutingSemantics] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or fullmatch(
            r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", self.provider_id
        ) is None:
            raise ValueError(f"invalid provider_id: {self.provider_id!r}")
        if not isinstance(self.provider, type):
            raise TypeError("provider must be a class")
        if type(self.requires_auth) is not bool:
            raise TypeError("requires_auth must be a bool")

        datasets = tuple(self.supported_datasets)
        if not datasets:
            raise ValueError("supported_datasets must not be empty")
        if any(not isinstance(dataset, DatasetDefinition) for dataset in datasets):
            raise TypeError("supported_datasets must contain DatasetDefinition values")
        names = tuple(dataset.name for dataset in datasets)
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate supported dataset in provider {self.provider_id!r}")
        object.__setattr__(self, "supported_datasets", datasets)

        dependencies = tuple(self.optional_dependencies)
        if any(
            not isinstance(dependency, str)
            or not dependency
            or dependency != dependency.strip()
            for dependency in dependencies
        ):
            raise ValueError("optional_dependencies must contain non-empty strings")
        if len(set(dependencies)) != len(dependencies):
            raise ValueError(f"duplicate optional dependency in provider {self.provider_id!r}")
        object.__setattr__(self, "optional_dependencies", dependencies)

        semantics = dict(self.routing_semantics)
        unknown = set(semantics).difference(names)
        if unknown:
            raise ValueError(
                f"routing semantics mention unsupported datasets: {sorted(unknown)!r}"
            )
        for name, value in semantics.items():
            if not isinstance(value, DatasetRoutingSemantics):
                raise TypeError(f"invalid routing semantics for dataset {name!r}")
        for name in names:
            semantics.setdefault(name, DatasetRoutingSemantics.MULTI_PROVIDER)
        object.__setattr__(self, "routing_semantics", MappingProxyType(semantics))

    def supports_dataset(self, dataset: DatasetDefinition[Any, Any] | str) -> bool:
        """Return whether this Provider advertises the requested Dataset."""

        name = dataset.name if isinstance(dataset, DatasetDefinition) else dataset
        return name in self.routing_semantics

    def semantics_for(self, dataset: DatasetDefinition[Any, Any] | str) -> DatasetRoutingSemantics:
        """Return the declared semantics for one supported Dataset."""

        name = dataset.name if isinstance(dataset, DatasetDefinition) else dataset
        try:
            return self.routing_semantics[name]
        except KeyError as exc:
            raise KeyError(
                f"provider {self.provider_id!r} does not support dataset {name!r}"
            ) from exc


class ProviderRegistry:
    """An explicit, immutable-by-convention Provider capability index."""

    def __init__(self, specs: Iterable[ProviderSpec]) -> None:
        registered = tuple(specs)
        by_id: dict[str, ProviderSpec] = {}
        by_type: dict[type[Any], ProviderSpec] = {}
        by_dataset: dict[str, list[ProviderSpec]] = {}
        dataset_definitions: dict[str, DatasetDefinition[Any, Any]] = {}
        dataset_semantics: dict[str, DatasetRoutingSemantics] = {}

        for spec in registered:
            if not isinstance(spec, ProviderSpec):
                raise TypeError("registry specs must contain ProviderSpec values")
            if spec.provider_id in by_id:
                raise ValueError(f"duplicate provider_id: {spec.provider_id!r}")
            if spec.provider in by_type:
                raise ValueError(f"provider class registered more than once: {spec.provider!r}")
            by_id[spec.provider_id] = spec
            by_type[spec.provider] = spec

            for dataset in spec.supported_datasets:
                name = dataset.name
                by_dataset.setdefault(name, []).append(spec)
                existing_definition = dataset_definitions.setdefault(name, dataset)
                if existing_definition != dataset:
                    raise ValueError(f"conflicting DatasetDefinition for {name!r}")
                semantics = spec.semantics_for(dataset)
                existing_semantics = dataset_semantics.setdefault(name, semantics)
                if existing_semantics != semantics:
                    raise ValueError(f"conflicting routing semantics for dataset {name!r}")

        self._providers = registered
        self._by_id = MappingProxyType(by_id)
        self._by_type = MappingProxyType(by_type)
        self._by_dataset = MappingProxyType(
            {name: tuple(values) for name, values in by_dataset.items()}
        )
        self._dataset_definitions = MappingProxyType(dataset_definitions)
        self._dataset_semantics = MappingProxyType(dataset_semantics)

    def get_provider(self, provider_id: str) -> ProviderSpec:
        """Find a Provider spec by its stable identity."""

        try:
            return self._by_id[provider_id]
        except KeyError as exc:
            raise KeyError(f"unknown provider_id: {provider_id!r}") from exc

    provider = get_provider

    def providers_for(
        self, dataset: DatasetDefinition[Any, Any] | str
    ) -> tuple[ProviderSpec, ...]:
        """Find all registered Providers advertising a Dataset."""

        name = self._dataset_name(dataset)
        try:
            return self._by_dataset[name]
        except KeyError as exc:
            raise KeyError(f"unknown dataset: {name!r}") from exc

    def datasets_for(self, provider: str | ProviderSpec | type[Any]) -> tuple[DatasetDefinition[Any, Any], ...]:
        """Find the Datasets advertised by a Provider identity or class."""

        if isinstance(provider, ProviderSpec):
            spec = provider
        elif isinstance(provider, str):
            spec = self.get_provider(provider)
        elif isinstance(provider, type):
            try:
                spec = self._by_type[provider]
            except KeyError as exc:
                raise KeyError(f"unknown provider class: {provider!r}") from exc
        else:
            raise TypeError("provider must be a provider_id, ProviderSpec, or provider class")
        if self._by_id.get(spec.provider_id) is not spec:
            raise KeyError(f"provider is not registered: {spec.provider_id!r}")
        return spec.supported_datasets

    def list_providers(self) -> tuple[ProviderSpec, ...]:
        """Return all registered Provider specs in declaration order."""

        return self._providers

    def list_datasets(self) -> tuple[DatasetDefinition[Any, Any], ...]:
        """Return all Dataset definitions covered by this registry."""

        return tuple(self._dataset_definitions.values())

    def routing_semantics_for(
        self, dataset: DatasetDefinition[Any, Any] | str
    ) -> DatasetRoutingSemantics:
        """Return the Dataset-level source/routing semantic declaration."""

        name = self._dataset_name(dataset)
        try:
            return self._dataset_semantics[name]
        except KeyError as exc:
            raise KeyError(f"unknown dataset: {name!r}") from exc

    def _dataset_name(self, dataset: DatasetDefinition[Any, Any] | str) -> str:
        if isinstance(dataset, DatasetDefinition):
            return dataset.name
        if isinstance(dataset, str):
            return dataset
        raise TypeError("dataset must be a DatasetDefinition or dataset name")


def _spec(
    provider_id: str,
    provider: type[Any],
    *datasets: DatasetDefinition[Any, Any],
    requires_auth: bool = False,
    optional_dependencies: tuple[str, ...] = (),
    semantics: DatasetRoutingSemantics = DatasetRoutingSemantics.MULTI_PROVIDER,
) -> ProviderSpec:
    return ProviderSpec(
        provider_id=provider_id,
        provider=provider,
        supported_datasets=tuple(datasets),
        requires_auth=requires_auth,
        optional_dependencies=optional_dependencies,
        routing_semantics={dataset.name: semantics for dataset in datasets},
    )


# These are the source-specific contracts whose public fields or event meaning
# are tied to the named source.  A future Provider may still be registered for
# the other Datasets when it implements the same public contract.
_SINGLE_SOURCE = DatasetRoutingSemantics.SINGLE_SOURCE


PROVIDER_SPECS = (
    _spec("szse.official.calendar", SzseTradingCalendarProvider, TRADING_CALENDAR_DATASET),
    _spec(
        "pandas_market_calendars",
        PmcTradingCalendarProvider,
        TRADING_CALENDAR_DATASET,
        optional_dependencies=("pandas_market_calendars",),
    ),
    _spec(
        "tencent.finance.qq.market",
        TencentMarketProvider,
        INSTRUMENT_DATASET,
        MARKET_QUOTE_DATASET,
        MARKET_RANKING_DATASET,
    ),
    _spec("tencent.finance.qq.quote", TencentQuoteProvider, MARKET_QUOTE_SNAPSHOT_DATASET, MARKET_ORDERBOOK_DATASET),
    _spec("tencent.finance.qq.klines", TencentKlinesProvider, MARKET_KLINES_DATASET),
    _spec("sohu.finance.klines", SohuKlinesProvider, MARKET_KLINES_DATASET),
    _spec(
        "tencent.finance.qq.intraday",
        TencentIntradayProvider,
        MARKET_EQUITY_INTRADAY_DATASET,
        MARKET_EQUITY_INTRADAY_5D_DATASET,
        MARKET_INDEX_INTRADAY_DATASET,
        MARKET_INDEX_INTRADAY_5D_DATASET,
    ),
    _spec(
        "tencent.finance.qq.fund_flow",
        TencentFundFlowProvider,
        MARKET_FUND_FLOW_SNAPSHOT_DATASET,
        MARKET_FUND_FLOW_INTRADAY_DATASET,
        MARKET_FUND_FLOW_DAILY_DATASET,
    ),
    _spec(
        "eastmoney.push2ex.breadth",
        EastmoneyBreadthProvider,
        MARKET_BREADTH_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "eastmoney.push2ex.limit_up_pool",
        EastmoneyLimitUpPoolProvider,
        MARKET_LIMIT_UP_POOL_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "eastmoney.push2ex.limit_down_pool",
        EastmoneyLimitDownPoolProvider,
        MARKET_LIMIT_DOWN_POOL_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "eastmoney.push2ex.yesterday_limit_up_pool",
        EastmoneyYesterdayLimitUpPoolProvider,
        MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "eastmoney.push2ex.strong_pool",
        EastmoneyStrongPoolProvider,
        MARKET_STRONG_POOL_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "eastmoney.push2ex.broken_limit_pool",
        EastmoneyBrokenLimitPoolProvider,
        MARKET_BROKEN_LIMIT_POOL_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "tencent.finance.qq.sector",
        TencentSectorProvider,
        MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "eastmoney.stockrank",
        EastMoneyStockKeywordProvider,
        MARKET_STOCK_KEYWORD_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "tencent.finance.qq.industry",
        TencentIndustryComparisonProvider,
        MARKET_INDUSTRY_COMPARISON_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec("tonghuashun.financial", TonghuashunFinancialProvider, FINANCIAL_STATEMENT_DATASET),
    _spec(
        "tencent.finance.qq.f10",
        TencentF10Provider,
        FUNDAMENTAL_COMPANY_PROFILE_DATASET,
        FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,
        FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET,
        FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET,
        OWNERSHIP_CAPITAL_SNAPSHOT_DATASET,
        OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET,
        COMPANY_EXECUTIVE_SNAPSHOT_DATASET,
        COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET,
        CORPORATE_ACTION_DIVIDEND_DATASET,
        CORPORATE_ACTION_REPURCHASE_DATASET,
    ),
    _spec("tencent.finance.qq.float_holder", TencentFloatHolderProvider, OWNERSHIP_FLOAT_HOLDER_DATASET),
    _spec("eastmoney.news", EastmoneyNewsProvider, NEWS_DOCUMENT_DATASET),
    _spec("eastmoney.disclosure", EastmoneyDisclosureProvider, DISCLOSURE_DOCUMENT_DATASET),
    _spec("eastmoney.market_news", EastmoneyMarketNewsProvider, NEWS_DOCUMENT_DATASET),
    _spec("aigupiao.market_news", AigupiaoMarketNewsProvider, NEWS_DOCUMENT_DATASET),
    _spec("baidu.finscope.market_news", BaiduFinscopeMarketNewsProvider, NEWS_DOCUMENT_DATASET),
    _spec(
        "aigupiao.market_sentiment",
        AigupiaoMarketSentimentProvider,
        MARKET_SENTIMENT_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "aigupiao.series_limit_up",
        AigupiaoSeriesLimitUpProvider,
        MARKET_CONSECUTIVE_LIMIT_UP_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "aigupiao.dragon_tiger",
        AigupiaoDragonTigerProvider,
        MARKET_DRAGON_TIGER_LIST_DATASET,
        MARKET_DRAGON_TIGER_DETAIL_DATASET,
        semantics=_SINGLE_SOURCE,
    ),
    _spec(
        "jiuyangongshe.daily_replay",
        JiyangongsheReplayProvider,
        MARKET_DAILY_REPLAY_DATASET,
        requires_auth=True,
        optional_dependencies=("playwright",),
        semantics=_SINGLE_SOURCE,
    ),
)


PROVIDER_REGISTRY = ProviderRegistry(PROVIDER_SPECS)


__all__ = [
    "DatasetRoutingSemantics",
    "ProviderRegistry",
    "ProviderSpec",
    "PROVIDER_REGISTRY",
    "PROVIDER_SPECS",
]
