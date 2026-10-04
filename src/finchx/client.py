"""Stable public Client and compatibility exports for Dataset namespaces."""

from __future__ import annotations

from collections.abc import (
    Mapping,
)
from dataclasses import (
    dataclass,
)
from typing import (
    Any,
    Protocol,
)
from finchx.collectors import (
    CachePolicy,
    Collector,
    FetchResult,
    RoutingPolicy,
)
from finchx.computed import (
    DeviationService,
)
from finchx.datasets import (
    ARTICLE_DETAIL_DATASET,
    ArticleDetailRequest,
    ARTICLE_TOPIC_DATASET,
    TopicArticlesRequest,
    HOT_CONTENT_DATASET,
    HOT_CONVERTIBLE_BONDS_DATASET,
    HOT_ETFS_DATASET,
    HOT_SECTORS_DATASET,
    HOT_STOCKS_DATASET,
    HotContentRequest,
    HotConvertibleBondsRequest,
    HotEtfsRequest,
    HotSectorsRequest,
    HotStocksRequest,
    MARKET_CONCEPT_LIST_DATASET,
    MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET,
    MARKET_CONCEPT_OHLCV_DATASET,
    ConceptListRequest,
    ConceptQuoteSnapshotRequest,
    ConceptOhlcvRequest,
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
    MARKET_BREADTH_DATASET,
    MARKET_ABNORMAL_COUNTS_DATASET,
    MARKET_ABNORMAL_RECORDS_DATASET,
    MARKET_REGULATION_WATCHLIST_DATASET,
    MARKET_SEVERE_PREDICTIONS_DATASET,
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
    IWENCAI_REPORT_DETAIL_DATASET,
    IWENCAI_SEARCH_DATASET,
    IWENCAI_SELECTION_DATASET,
    IwencaiReportDetailRequest,
    IwencaiSearchRequest,
    IwencaiSelectionRequest,
    OWNERSHIP_CAPITAL_SNAPSHOT_DATASET,
    OWNERSHIP_FLOAT_HOLDER_DATASET,
    OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET,
    TRADING_CALENDAR_DATASET,
    CapitalSnapshotRequest,
    CompanyProfileRequest,
    DisclosureSearchRequest,
    DividendRequest,
    ExecutiveShareChangeRequest,
    ExecutiveSnapshotRequest,
    FinancialSummaryRequest,
    FinancialStatementRequest,
    FloatHolderRequest,
    HolderSummarySnapshotRequest,
    KlinesRequest,
    MarketBreadthRequest,
    AbnormalCountsRequest,
    AbnormalRecordsRequest,
    RegulationWatchlistRequest,
    SeverePredictionsRequest,
    MarketBrokenLimitPoolRequest,
    MarketConsecutiveLimitUpRequest,
    MarketDailyReplayRequest,
    MarketDragonTigerDetailRequest,
    MarketDragonTigerListRequest,
    MarketFundFlowRequest,
    MarketIndustryComparisonRequest,
    MarketInstrumentSectorSnapshotRequest,
    MarketStockKeywordRequest,
    MarketLimitDownPoolRequest,
    MarketLimitUpPoolRequest,
    MarketOrderbookRequest,
    MarketQuoteSnapshotRequest,
    MarketQuoteUniverseRequest,
    MarketRankingRequest,
    MarketSentimentRequest,
    MarketStrongPoolRequest,
    MarketYesterdayLimitUpPoolRequest,
    NewsSearchRequest,
    RepurchaseRequest,
    RevenueBreakdownRequest,
    TradingCalendarRequest,
    EquityIntraday5dRequest,
    EquityIntradayRequest,
    IndexIntraday5dRequest,
    IndexIntradayRequest,
)
from finchx.datasets.definition import (
    DatasetDefinition,
)
from finchx.datasets.fundamental_industry_comparison import (
    IndustryComparisonRequest as FundamentalIndustryComparisonRequest,
)
from finchx.providers.registry import (
    PROVIDER_REGISTRY,
    ProviderRegistry,
)
from finchx.query.documents import (
    DisclosureService,
    NewsService,
)
from finchx.query.forum import (
    ForumService,
)
from finchx.query.market_news import (
    MarketNewsService,
)
from finchx.query.articles import (
    ArticleDetailService,
)
from finchx.storage import (
    Cache,
)
from finchx.api.documents import (
    ArticlesNamespace,
    DisclosureNamespace,
    ForumNamespace,
    MarketNewsNamespace,
    NewsNamespace,
)
from finchx.api.fundamental import (
    FinancialNamespace,
    FundamentalNamespace,
)
from finchx.api.hotlist import (
    HotlistNamespace,
)
from finchx.api.iwencai import (
    IwencaiNamespace,
)
from finchx.api.market import (
    MarketNamespace,
)
from finchx.api.ownership import (
    CompanyNamespace,
    CorporateActionNamespace,
    OwnershipNamespace,
)
from finchx.api.reference import (
    ReferenceNamespace,
)


from finchx.api._base import _regulation_request, _Namespace, _RequestNamespace
from finchx.api.documents import _normalize_disclosure_categories


class CollectorLike(Protocol):
    """The small Collector surface required by the public Client."""

    def fetch(
        self,
        dataset: DatasetDefinition[Any, Any] | str,
        provider: str | None = None,
        *,
        use_cache: bool | None = None,
        **kwargs: Any,
    ) -> FetchResult[Any]: ...


@dataclass(frozen=True)
class ClientEndpoint:
    """One explicit public namespace method and its Dataset contract."""

    namespace: str
    method: str
    dataset: DatasetDefinition[Any, Any]
    request_type: type[Any]


class FinchX:
    """Lightweight public entry point over one shared Collector runtime.

    Constructing a Client only builds in-memory objects.  It does not resolve a
    Provider, access the network, or create a storage file. Article details
    have an in-memory cache; Collector caching remains disabled by default.
    """

    __slots__ = (
        "_collector",
        "_deviation_service",
        "_news_service",
        "_disclosure_service",
        "_market_news_service",
        "_articles_service",
        "_forum_service",
        "hotlist",
        "reference",
        "market",
        "fundamental",
        "financial",
        "iwencai",
        "news",
        "disclosure",
        "market_news",
        "articles",
        "forum",
        "ownership",
        "company",
        "corporate_action",
    )

    reference: ReferenceNamespace
    market: MarketNamespace
    fundamental: FundamentalNamespace
    financial: FinancialNamespace
    iwencai: IwencaiNamespace
    news: NewsNamespace
    disclosure: DisclosureNamespace
    market_news: MarketNewsNamespace
    articles: ArticlesNamespace
    forum: ForumNamespace
    hotlist: HotlistNamespace
    ownership: OwnershipNamespace
    company: CompanyNamespace
    corporate_action: CorporateActionNamespace

    def __init__(
        self,
        collector: CollectorLike | None = None,
        *,
        registry: ProviderRegistry = PROVIDER_REGISTRY,
        cache: Cache | None = None,
        policy: RoutingPolicy | None = None,
        cache_policy: CachePolicy | Mapping[str, CachePolicy] | None = None,
    ) -> None:
        if collector is not None:
            if not callable(getattr(collector, "fetch", None)):
                raise TypeError("collector must provide a callable fetch method")
            if registry is not PROVIDER_REGISTRY or cache is not None or policy is not None or cache_policy is not None:
                raise ValueError("collector cannot be combined with Collector configuration")
            self._collector = collector
        else:
            self._collector = Collector(
                registry=registry,
                cache=cache,
                policy=policy,
                cache_policy=cache_policy,
            )
        self._deviation_service = DeviationService(self._collector)
        self._news_service = NewsService()
        self._disclosure_service = DisclosureService()
        self._market_news_service = MarketNewsService()
        self._articles_service = ArticleDetailService(self._collector, cache=cache)
        self._forum_service = ForumService()
        self.reference = ReferenceNamespace(self)
        self.market = MarketNamespace(self)
        self.fundamental = FundamentalNamespace(self)
        self.financial = FinancialNamespace(self)
        self.iwencai = IwencaiNamespace(self)
        self.news = NewsNamespace(self)
        self.disclosure = DisclosureNamespace(self)
        self.market_news = MarketNewsNamespace(self)
        self.articles = ArticlesNamespace(self)
        self.forum = ForumNamespace(self)
        self.hotlist = HotlistNamespace(self)
        self.ownership = OwnershipNamespace(self)
        self.company = CompanyNamespace(self)
        self.corporate_action = CorporateActionNamespace(self)

    @property
    def collector(self) -> CollectorLike:
        """Return the shared Collector or Collector-compatible injection."""

        return self._collector

    def fetch(
        self,
        dataset: DatasetDefinition[Any, Any] | str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
        **kwargs: Any,
    ) -> FetchResult[Any]:
        """Low-level escape hatch that delegates directly to Collector.fetch."""

        return self._collector.fetch(
            dataset,
            provider=provider,
            use_cache=use_cache,
            **kwargs,
        )


CLIENT_ENDPOINTS: tuple[ClientEndpoint, ...] = (
    ClientEndpoint("reference", "trading_calendar", TRADING_CALENDAR_DATASET, TradingCalendarRequest),
    ClientEndpoint("market", "breadth", MARKET_BREADTH_DATASET, MarketBreadthRequest),
    ClientEndpoint("market", "regulation_watchlist", MARKET_REGULATION_WATCHLIST_DATASET, RegulationWatchlistRequest),
    ClientEndpoint("market", "abnormal_records", MARKET_ABNORMAL_RECORDS_DATASET, AbnormalRecordsRequest),
    ClientEndpoint("market", "severe_predictions", MARKET_SEVERE_PREDICTIONS_DATASET, SeverePredictionsRequest),
    ClientEndpoint("market", "abnormal_counts", MARKET_ABNORMAL_COUNTS_DATASET, AbnormalCountsRequest),
    ClientEndpoint("market", "broken_limit_pool", MARKET_BROKEN_LIMIT_POOL_DATASET, MarketBrokenLimitPoolRequest),
    ClientEndpoint("market", "consecutive_limit_up", MARKET_CONSECUTIVE_LIMIT_UP_DATASET, MarketConsecutiveLimitUpRequest),
    ClientEndpoint("market", "daily_replay", MARKET_DAILY_REPLAY_DATASET, MarketDailyReplayRequest),
    ClientEndpoint("market", "dragon_tiger_detail", MARKET_DRAGON_TIGER_DETAIL_DATASET, MarketDragonTigerDetailRequest),
    ClientEndpoint("market", "dragon_tiger_list", MARKET_DRAGON_TIGER_LIST_DATASET, MarketDragonTigerListRequest),
    ClientEndpoint("market", "equity_intraday", MARKET_EQUITY_INTRADAY_DATASET, EquityIntradayRequest),
    ClientEndpoint("market", "equity_intraday_5d", MARKET_EQUITY_INTRADAY_5D_DATASET, EquityIntraday5dRequest),
    ClientEndpoint("market", "fund_flow_daily", MARKET_FUND_FLOW_DAILY_DATASET, MarketFundFlowRequest),
    ClientEndpoint("market", "fund_flow_intraday", MARKET_FUND_FLOW_INTRADAY_DATASET, MarketFundFlowRequest),
    ClientEndpoint("market", "fund_flow_snapshot", MARKET_FUND_FLOW_SNAPSHOT_DATASET, MarketFundFlowRequest),
    ClientEndpoint("market", "concept_list", MARKET_CONCEPT_LIST_DATASET, ConceptListRequest),
    ClientEndpoint("market", "concept_quote_snapshot", MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET, ConceptQuoteSnapshotRequest),
    ClientEndpoint("market", "concept_ohlcv", MARKET_CONCEPT_OHLCV_DATASET, ConceptOhlcvRequest),
    ClientEndpoint("market", "index_intraday", MARKET_INDEX_INTRADAY_DATASET, IndexIntradayRequest),
    ClientEndpoint("market", "index_intraday_5d", MARKET_INDEX_INTRADAY_5D_DATASET, IndexIntraday5dRequest),
    ClientEndpoint("market", "industry_comparison", MARKET_INDUSTRY_COMPARISON_DATASET, MarketIndustryComparisonRequest),
    ClientEndpoint("market", "instrument_sector_snapshot", MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET, MarketInstrumentSectorSnapshotRequest),
    ClientEndpoint("market", "stock_keyword", MARKET_STOCK_KEYWORD_DATASET, MarketStockKeywordRequest),
    ClientEndpoint("market", "limit_down_pool", MARKET_LIMIT_DOWN_POOL_DATASET, MarketLimitDownPoolRequest),
    ClientEndpoint("market", "limit_up_pool", MARKET_LIMIT_UP_POOL_DATASET, MarketLimitUpPoolRequest),
    ClientEndpoint("market", "ohlcv", MARKET_KLINES_DATASET, KlinesRequest),
    ClientEndpoint("market", "orderbook", MARKET_ORDERBOOK_DATASET, MarketOrderbookRequest),
    ClientEndpoint("market", "quote", MARKET_QUOTE_DATASET, MarketQuoteUniverseRequest),
    ClientEndpoint("market", "quote_snapshot", MARKET_QUOTE_SNAPSHOT_DATASET, MarketQuoteSnapshotRequest),
    ClientEndpoint("market", "ranking", MARKET_RANKING_DATASET, MarketRankingRequest),
    ClientEndpoint("market", "sentiment", MARKET_SENTIMENT_DATASET, MarketSentimentRequest),
    ClientEndpoint("market", "strong_pool", MARKET_STRONG_POOL_DATASET, MarketStrongPoolRequest),
    ClientEndpoint("market", "yesterday_limit_up_pool", MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET, MarketYesterdayLimitUpPoolRequest),
    ClientEndpoint("hotlist", "stocks", HOT_STOCKS_DATASET, HotStocksRequest),
    ClientEndpoint("hotlist", "sectors", HOT_SECTORS_DATASET, HotSectorsRequest),
    ClientEndpoint("hotlist", "convertible_bonds", HOT_CONVERTIBLE_BONDS_DATASET, HotConvertibleBondsRequest),
    ClientEndpoint("hotlist", "etfs", HOT_ETFS_DATASET, HotEtfsRequest),
    ClientEndpoint("hotlist", "content", HOT_CONTENT_DATASET, HotContentRequest),
    ClientEndpoint("fundamental", "company_profile", FUNDAMENTAL_COMPANY_PROFILE_DATASET, CompanyProfileRequest),
    ClientEndpoint("fundamental", "financial_summary", FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET, FinancialSummaryRequest),
    ClientEndpoint("fundamental", "industry_comparison", FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET, FundamentalIndustryComparisonRequest),
    ClientEndpoint("fundamental", "revenue_breakdown", FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET, RevenueBreakdownRequest),
    ClientEndpoint("financial", "statements", FINANCIAL_STATEMENT_DATASET, FinancialStatementRequest),
    ClientEndpoint("iwencai", "select", IWENCAI_SELECTION_DATASET, IwencaiSelectionRequest),
    ClientEndpoint("iwencai", "search", IWENCAI_SEARCH_DATASET, IwencaiSearchRequest),
    ClientEndpoint("iwencai", "report_detail", IWENCAI_REPORT_DETAIL_DATASET, IwencaiReportDetailRequest),
    ClientEndpoint("news", "search", NEWS_DOCUMENT_DATASET, NewsSearchRequest),
    ClientEndpoint("articles", "get", ARTICLE_DETAIL_DATASET, ArticleDetailRequest),
    ClientEndpoint("articles", "from_topic", ARTICLE_TOPIC_DATASET, TopicArticlesRequest),
    ClientEndpoint("disclosure", "search", DISCLOSURE_DOCUMENT_DATASET, DisclosureSearchRequest),
    ClientEndpoint("ownership", "capital_snapshot", OWNERSHIP_CAPITAL_SNAPSHOT_DATASET, CapitalSnapshotRequest),
    ClientEndpoint("ownership", "float_holder", OWNERSHIP_FLOAT_HOLDER_DATASET, FloatHolderRequest),
    ClientEndpoint("ownership", "holder_summary_snapshot", OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET, HolderSummarySnapshotRequest),
    ClientEndpoint("company", "executive_share_change", COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET, ExecutiveShareChangeRequest),
    ClientEndpoint("company", "executive_snapshot", COMPANY_EXECUTIVE_SNAPSHOT_DATASET, ExecutiveSnapshotRequest),
    ClientEndpoint("corporate_action", "dividend", CORPORATE_ACTION_DIVIDEND_DATASET, DividendRequest),
    ClientEndpoint("corporate_action", "repurchase", CORPORATE_ACTION_REPURCHASE_DATASET, RepurchaseRequest),
)

# Resolve the base constructor annotation without a runtime import cycle.
from finchx.api import _base as _namespace_base
_namespace_base.FinchX = FinchX
