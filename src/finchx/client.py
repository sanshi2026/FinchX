"""Stable public Client and explicit Dataset namespaces."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol

from finchx.collectors import CachePolicy, Collector, FetchResult, RoutingPolicy
from finchx.computed import DeviationData, DeviationService, DeviationWindowConvention
from finchx.contracts import StandardRecord
from finchx.datasets import (
    ARTICLE_DETAIL_DATASET,
    ArticleDetailRequest,
    ARTICLE_TOPIC_DATASET,
    TopicArticlesRequest,
    UnsupportedTopicURL,
    classify_topic_url,
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
    MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET, MARKET_CONCEPT_OHLCV_DATASET,
    ConceptRef,
    ConceptListRequest,
    ConceptQuoteSnapshotRequest, ConceptOhlcvRequest,
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
    DisclosureDocumentRef,
    DisclosureSearchRequest,
    DividendRequest,
    ExecutiveShareChangeRequest,
    ExecutiveSnapshotRequest,
    FinancialSummaryRequest,
    FinancialStatementRequest,
    FloatHolderRequest,
    HolderSummarySnapshotRequest,
    InstrumentUniverse,
    KlineAdjustment,
    KlinesRequest,
    MarketBreadthRequest,
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
    RankingCriterion,
    RankingDirection,
    MarketSentimentRequest,
    MarketStrongPoolRequest,
    MarketYesterdayLimitUpPoolRequest,
    NewsDocumentRef,
    NewsSearchRequest,
    ForumReply,
    RepurchaseRequest,
    RevenueBreakdownRequest,
    TradingCalendarRequest,
    EquityIntraday5dRequest,
    EquityIntradayRequest,
    IndexIntraday5dRequest,
    IndexIntradayRequest,
)
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.document_common import normalize_document_instrument
from finchx.datasets.financial_statement import StatementType
from finchx.datasets.fundamental_industry_comparison import (
    IndustryComparisonRequest as FundamentalIndustryComparisonRequest,
)
from finchx.entities import InstrumentKind, Market, normalize_index_instrument, normalize_instrument
from finchx.providers.registry import PROVIDER_REGISTRY, ProviderRegistry
from finchx.query.documents import DisclosureService, NewsService
from finchx.query.forum import ForumService
from finchx.query.market_news import MarketNewsService
from finchx.query.articles import ArticleDetailService
from finchx.storage import Cache


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


class _Namespace:
    __slots__ = ("_client",)

    def __init__(self, client: FinchX) -> None:
        self._client = client

    def _fetch(
        self,
        dataset: Any,
        request: Any,
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        return self._client.fetch(
            dataset,
            provider=provider,
            use_cache=use_cache,
            request=request,
        )


class _RequestNamespace(_Namespace):
    """Shared thin delegation for endpoints whose request model is the API."""

    def _fetch_request(
        self,
        dataset: DatasetDefinition[Any, Any],
        request: Any,
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        if request is None:
            raise TypeError(f"{dataset.name} requires its request model")
        return self._fetch(
            dataset,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def _fetch_instrument_request(
        self,
        dataset: DatasetDefinition[Any, Any],
        instrument: str,
        request_type: type[Any],
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        """Fetch a request model or build one from a single instrument input."""
        request = request_type(instrumentId=normalize_instrument(instrument))
        return self._fetch_request(
            dataset,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def _fetch_index_request(
        self,
        dataset: DatasetDefinition[Any, Any],
        instrument: str,
        request_type: type[Any],
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        """Fetch an index request or resolve a bare code as an index."""
        request = request_type(instrumentId=normalize_index_instrument(instrument))
        return self._fetch_request(
            dataset,
            request,
            provider=provider,
            use_cache=use_cache,
        )


class ReferenceNamespace(_Namespace):
    """Reference and identity lookups."""

    def trading_calendar(
        self,
        start_date: date | str,
        end_date: date | str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Return one trading-day flag per natural date in an inclusive A-share range."""

        request = TradingCalendarRequest(
            market=Market.CN_A,
            startDate=start_date,
            endDate=end_date,
        )
        return self._fetch(
            TRADING_CALENDAR_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )


class MarketNamespace(_RequestNamespace):
    """Market snapshots and time-series lookups."""

    def quote(
        self,
        *,
        universe: InstrumentUniverse = InstrumentUniverse.CN_A_SHARE,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a full-market A-share quote snapshot in a FetchResult."""
        request = MarketQuoteUniverseRequest(universe=universe)
        return self._fetch(
            MARKET_QUOTE_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def ohlcv(
        self,
        instrument: str,
        start_date: date | str,
        end_date: date | str,
        adjustment: str | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch OHLCV history for one instrument in a FetchResult."""
        instrument_id = normalize_instrument(instrument)
        request_values: dict[str, Any] = {
            "instrumentId": instrument_id,
            "startDate": start_date,
            "endDate": end_date,
        }
        if instrument_id.kind is InstrumentKind.EQUITY:
            if adjustment is None:
                internal_adjustment = KlineAdjustment.NONE
            elif type(adjustment) is str and adjustment == "qfq":
                internal_adjustment = KlineAdjustment.QFQ
            elif type(adjustment) is str and adjustment == "hfq":
                internal_adjustment = KlineAdjustment.HFQ
            else:
                raise ValueError("adjustment must be one of: qfq, hfq, None")
            request_values["adjustment"] = internal_adjustment
        elif instrument_id.kind is InstrumentKind.INDEX:
            if adjustment is not None:
                raise ValueError("index OHLCV adjustment must be None")
        request = KlinesRequest(**request_values)
        return self._fetch(
            MARKET_KLINES_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def deviation(
        self,
        instrument: str,
        *,
        windows: Sequence[int] = (10, 30),
        as_of: date | str | None = None,
        window_convention: DeviationWindowConvention = DeviationWindowConvention.MAX_DEVIATION_SCAN,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[DeviationData]:
        """Compute close-based 10-day/30-day deviation from existing data."""
        return self._client._deviation_service.calculate(
            normalize_instrument(instrument),
            windows=windows,
            as_of=as_of,
            window_convention=window_convention,
            provider=provider,
            use_cache=use_cache,
        )

    def breadth(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the current market breadth snapshot in a FetchResult."""
        request = MarketBreadthRequest()
        return self._fetch_request(MARKET_BREADTH_DATASET, request, provider=provider, use_cache=use_cache)

    def broken_limit_pool(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the latest broken-limit pool snapshot in a FetchResult."""
        request = MarketBrokenLimitPoolRequest()
        return self._fetch_request(MARKET_BROKEN_LIMIT_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def consecutive_limit_up(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the consecutive-limit-up snapshot in a FetchResult."""
        request = MarketConsecutiveLimitUpRequest()
        return self._fetch_request(MARKET_CONSECUTIVE_LIMIT_UP_DATASET, request, provider=provider, use_cache=use_cache)

    def daily_replay(
        self,
        requested_date: date | str,
        *,
        session: str,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch one daily replay request with an explicit authenticated session."""
        if not isinstance(session, str):
            raise TypeError("session must be a non-empty string")
        if not session.strip():
            raise ValueError("session must be a non-empty string")
        request = MarketDailyReplayRequest(requestedDate=requested_date)
        return self._client.fetch(
            MARKET_DAILY_REPLAY_DATASET,
            provider=provider,
            use_cache=use_cache,
            request=request,
            session=session,
        )

    def dragon_tiger_detail(
        self,
        instrument: str,
        trade_date: date | str,
        trade_id: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch Dragon-Tiger detail data in a FetchResult."""
        request = MarketDragonTigerDetailRequest(
            instrumentId=normalize_instrument(instrument),
            tradeDate=trade_date,
            tradeId=trade_id,
        )
        return self._fetch_request(MARKET_DRAGON_TIGER_DETAIL_DATASET, request, provider=provider, use_cache=use_cache)

    def dragon_tiger_list(
        self,
        trade_date: date | str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch Dragon-Tiger list data in a FetchResult."""
        request = MarketDragonTigerListRequest(tradeDate=trade_date)
        return self._fetch_request(MARKET_DRAGON_TIGER_LIST_DATASET, request, provider=provider, use_cache=use_cache)

    def equity_intraday(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch one equity intraday session in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_EQUITY_INTRADAY_DATASET,
            instrument,
            EquityIntradayRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def equity_intraday_5d(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch five-day equity intraday data in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_EQUITY_INTRADAY_5D_DATASET,
            instrument,
            EquityIntraday5dRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def fund_flow_daily(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch daily fund-flow data in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_FUND_FLOW_DAILY_DATASET,
            instrument,
            MarketFundFlowRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def fund_flow_intraday(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch intraday fund-flow data in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_FUND_FLOW_INTRADAY_DATASET,
            instrument,
            MarketFundFlowRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def fund_flow_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the fund-flow snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_FUND_FLOW_SNAPSHOT_DATASET,
            instrument,
            MarketFundFlowRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def index_intraday(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch one index intraday session in a FetchResult."""
        return self._fetch_index_request(
            MARKET_INDEX_INTRADAY_DATASET,
            instrument,
            IndexIntradayRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def index_intraday_5d(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch five-day index intraday data in a FetchResult."""
        return self._fetch_index_request(
            MARKET_INDEX_INTRADAY_5D_DATASET,
            instrument,
            IndexIntraday5dRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def industry_comparison(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the market industry comparison in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_INDUSTRY_COMPARISON_DATASET,
            instrument,
            MarketIndustryComparisonRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def instrument_sector_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch sector tags and snapshots for an instrument in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET,
            instrument,
            MarketInstrumentSectorSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def stock_keyword(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch EastMoney source-ranked hot keywords for an instrument."""
        return self._fetch_instrument_request(
            MARKET_STOCK_KEYWORD_DATASET,
            instrument,
            MarketStockKeywordRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def concept_list(
        self, *, provider: str | None = None, use_cache: bool | None = None
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the complete available Tonghuashun concept directory."""
        return self._fetch_request(MARKET_CONCEPT_LIST_DATASET, ConceptListRequest(), provider=provider, use_cache=use_cache)

    def concept_quote_snapshot(
        self, concept: ConceptRef | str, *, provider: str | None = None, use_cache: bool | None = None
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the current index-point quote and available breadth/flow for one concept."""
        return self._fetch_request(MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET, ConceptQuoteSnapshotRequest(concept=concept), provider=provider, use_cache=use_cache)

    def concept_ohlcv(
        self,
        concept: ConceptRef | str,
        start_date: date | str,
        end_date: date | str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch inclusive daily index-point OHLCV bars for one concept."""
        request=ConceptOhlcvRequest(concept=concept,startDate=start_date,endDate=end_date)
        return self._fetch_request(MARKET_CONCEPT_OHLCV_DATASET, request, provider=provider, use_cache=use_cache)

    def limit_down_pool(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the latest limit-down pool snapshot in a FetchResult."""
        request = MarketLimitDownPoolRequest()
        return self._fetch_request(MARKET_LIMIT_DOWN_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def limit_up_pool(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the latest limit-up pool snapshot in a FetchResult."""
        request = MarketLimitUpPoolRequest()
        return self._fetch_request(MARKET_LIMIT_UP_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def orderbook(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the order book in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_ORDERBOOK_DATASET,
            instrument,
            MarketOrderbookRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def quote_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch one quote snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_QUOTE_SNAPSHOT_DATASET,
            instrument,
            MarketQuoteSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def ranking(
        self,
        criterion: str,
        direction: str,
        limit: int | None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a ranked list of A-share stocks in a FetchResult."""
        try:
            mapped_criterion = {
                "amount": RankingCriterion.TURNOVER,
                "zdf": RankingCriterion.CHANGE_PERCENT,
                "volume": RankingCriterion.VOLUME,
            }[criterion] if type(criterion) is str else None
        except KeyError as exc:
            raise ValueError("criterion must be one of: amount, zdf, volume") from exc
        if mapped_criterion is None:
            raise ValueError("criterion must be one of: amount, zdf, volume")

        try:
            mapped_direction = {
                "asc": RankingDirection.ASCENDING,
                "desc": RankingDirection.DESCENDING,
            }[direction] if type(direction) is str else None
        except KeyError as exc:
            raise ValueError("direction must be one of: asc, desc") from exc
        if mapped_direction is None:
            raise ValueError("direction must be one of: asc, desc")

        request = MarketRankingRequest(
            universe=InstrumentUniverse.CN_A_SHARE,
            criterion=mapped_criterion,
            direction=mapped_direction,
            limit=limit,
        )
        return self._fetch_request(MARKET_RANKING_DATASET, request, provider=provider, use_cache=use_cache)

    def sentiment(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the market sentiment snapshot in a FetchResult."""
        request = MarketSentimentRequest()
        return self._fetch_request(MARKET_SENTIMENT_DATASET, request, provider=provider, use_cache=use_cache)

    def strong_pool(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the latest strong-pool snapshot in a FetchResult."""
        request = MarketStrongPoolRequest()
        return self._fetch_request(MARKET_STRONG_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def yesterday_limit_up_pool(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the latest yesterday-limit-up pool snapshot in a FetchResult."""
        request = MarketYesterdayLimitUpPoolRequest()
        return self._fetch_request(MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET, request, provider=provider, use_cache=use_cache)


class FundamentalNamespace(_RequestNamespace):
    """Company and other source-neutral fundamental lookups."""

    def company_profile(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a company's profile in a FetchResult."""
        request = CompanyProfileRequest(
            instrumentId=normalize_instrument(instrument)
        )
        return self._fetch(
            FUNDAMENTAL_COMPANY_PROFILE_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def financial_summary(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a company's financial summary in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,
            instrument,
            FinancialSummaryRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def industry_comparison(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the fundamental industry comparison in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET,
            instrument,
            FundamentalIndustryComparisonRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def revenue_breakdown(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a company's revenue breakdown in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET,
            instrument,
            RevenueBreakdownRequest,
            provider=provider,
            use_cache=use_cache,
        )


class FinancialNamespace(_Namespace):
    """Financial statement lookups."""

    def statements(
        self,
        instrument: str,
        statement_type: StatementType,
        *,
        period_end: date | str | None = None,
        max_periods: int | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch financial statements in a FetchResult."""
        request = FinancialStatementRequest(
            instrumentId=normalize_instrument(instrument),
            statementType=statement_type,
            periodEnd=period_end,
            maxPeriods=max_periods,
        )
        return self._fetch(
            FINANCIAL_STATEMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )


class IwencaiNamespace(_RequestNamespace):
    """iWenCai's cookie-backed screener, search, and report details."""

    def select(
        self,
        query: str,
        *,
        cookies: str | Mapping[str, str],
        user_agent: str | None = None,
        page_size: int = 100,
        max_pages: int = 100,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Run the final table rendered by ``iwencai.com/screener``.

        A caller-owned Cookie header is mandatory.  The result contains one
        standardized ``StandardRecord`` per stock; dynamic source columns
        are retained under ``extraFields``.
        """

        request = IwencaiSelectionRequest(
            query=query,
            cookies=cookies,
            userAgent=user_agent,
            pageSize=page_size,
            maxPages=max_pages,
        )
        return self._fetch(
            IWENCAI_SELECTION_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def search(
        self,
        query: str,
        *,
        channel: str = "report",
        size: int = 50,
        cookies: str | Mapping[str, str] | None = None,
        api_key: str | None = None,
        deduplicate: bool = True,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Search reports, announcements, or news with SkillHub OpenAPI.

        The API key is read from ``IWENCAI_API_KEY`` when omitted.  Cookies
        are accepted and forwarded for one consistent credential surface, but
        the OpenAPI authorization is the API key plus X-Claw headers.  The
        result contains one standardized ``StandardRecord`` per hit.
        """

        request = IwencaiSearchRequest(
            query=query,
            channel=channel,
            size=size,
            cookies=cookies,
            apiKey=api_key,
            deduplicate=deduplicate,
        )
        return self._fetch(
            IWENCAI_SEARCH_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def report_detail(
        self,
        url: str,
        *,
        cookies: str | Mapping[str, str],
        uid: str | None = None,
        title: str | None = None,
        published_at: str | None = None,
        user_agent: str | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch report text and metadata linked from ``iwencai.search``.

        Pass the hit's ``url`` field, for example
        ``fx.iwencai.report_detail(hit["url"], cookies=...)``.  The request
        requires the caller's iWenCai/THS cookie.
        """

        request = IwencaiReportDetailRequest(
            url=url,
            cookies=cookies,
            uid=uid,
            title=title,
            publishedAt=published_at,
            userAgent=user_agent,
        )
        return self._fetch(
            IWENCAI_REPORT_DETAIL_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def detail(
        self,
        url: str,
        *,
        cookies: str | Mapping[str, str],
        uid: str | None = None,
        title: str | None = None,
        published_at: str | None = None,
        user_agent: str | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Alias for :meth:`report_detail`."""

        return self.report_detail(
            url,
            cookies=cookies,
            uid=uid,
            title=title,
            published_at=published_at,
            user_agent=user_agent,
            provider=provider,
            use_cache=use_cache,
        )


class NewsNamespace(_Namespace):
    """Individual-stock news search."""

    def search(
        self,
        instrument: str,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
        sort: str = "published_desc",
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[NewsDocumentRef, ...]]:
        """Search news metadata and return document references in a FetchResult."""
        request = NewsSearchRequest(
            instrumentId=normalize_document_instrument(instrument),
            page=page,
            pageSize=page_size,
            maxResults=max_results,
            since=since,
            until=until,
            sort=sort,
        )
        return self._fetch(
            NEWS_DOCUMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def get_document(self, ref: NewsDocumentRef) -> FetchResult[StandardRecord]:
        """Fetch one complete news document in a FetchResult."""
        return self._client._news_service.get_document(ref)

    def get_documents(self, refs: Iterable[NewsDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch complete news documents in a FetchResult."""
        return self._client._news_service.get_documents(refs)


class DisclosureNamespace(_Namespace):
    """Individual-stock disclosure search."""

    def search(
        self,
        instrument: str,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
        categories: Sequence[str] | None = None,
        sort: str = "published_desc",
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[DisclosureDocumentRef, ...]]:
        """Search disclosures and return document references in a FetchResult."""
        request = DisclosureSearchRequest(
            instrumentId=normalize_document_instrument(instrument),
            page=page,
            pageSize=page_size,
            maxResults=max_results,
            since=since,
            until=until,
            categories=_normalize_disclosure_categories(categories),
            sort=sort,
        )
        return self._fetch(
            DISCLOSURE_DOCUMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def get_document(self, ref: DisclosureDocumentRef) -> FetchResult[StandardRecord]:
        """Fetch one complete disclosure in a FetchResult."""
        return self._client._disclosure_service.get_document(ref)

    def get_documents(self, refs: Iterable[DisclosureDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch complete disclosures in a FetchResult."""
        return self._client._disclosure_service.get_documents(refs)


def _normalize_disclosure_categories(categories: Sequence[str] | None) -> list[str] | None:
    if categories is None:
        return None
    if isinstance(categories, (str, bytes)) or not isinstance(categories, Sequence):
        raise TypeError("categories must be a sequence of category names")
    values = list(categories)
    if not values:
        raise ValueError("categories must contain at least one category name")
    return values


class MarketNewsNamespace(_Namespace):
    """All-market 7x24 news search and detail lookup."""

    def search(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
        sort: str = "published_desc",
    ) -> FetchResult[tuple[NewsDocumentRef, ...]]:
        """Search deduplicated all-market news in a FetchResult."""
        return self._client._market_news_service.search_result(
            page=page,
            page_size=page_size,
            max_results=max_results,
            since=since,
            until=until,
            sort=sort,
        )

    def get_document(self, ref: NewsDocumentRef) -> FetchResult[StandardRecord]:
        """Fetch one complete all-market news document in a FetchResult."""
        return self._client._market_news_service.get_document(ref)

    def get_documents(self, refs: Iterable[NewsDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch complete all-market news documents in a FetchResult."""
        return self._client._market_news_service.get_documents(refs)


class ArticlesNamespace(_Namespace):
    """Unified THS news and zhibo article details for research evidence."""

    def get(
        self,
        url: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[StandardRecord]:
        """Fetch one article by its public Tonghuashun URL."""
        return self._client._articles_service.get(
            url,
            provider=provider,
            use_cache=use_cache,
        )

    def from_topic(
        self,
        topic_url: str,
        *,
        sort: Literal["recommend"] = "recommend",
        limit: int = 20,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """List supported news refs from a Tonghuashun T-code topic URL."""
        topic_kind, topic_identity = classify_topic_url(topic_url)
        if topic_kind == "deep_topic":
            raise UnsupportedTopicURL(
                "deep-topic report pages have no verified report-scoped news feed; "
                "the public deep-topic items API is a global report index, not related news"
            )
        request = TopicArticlesRequest(topicCode=topic_identity, sort=sort, limit=limit)
        return self._fetch(
            ARTICLE_TOPIC_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

class HotlistNamespace(_RequestNamespace):
    """Tonghuashun stock, sector, convertible-bond, ETF and content heat rankings."""

    def stocks(self, category: str = "popular", period: str | None = None, limit: int = 20, *,
               provider: str | None = None, use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotStocksRequest(category=category, period=period, limit=limit)
        return self._fetch_request(HOT_STOCKS_DATASET, request, provider=provider, use_cache=use_cache)

    def sectors(self, sector_type: str = "concept", limit: int = 20, *,
                provider: str | None = None, use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotSectorsRequest(sectorType=sector_type, limit=limit)
        return self._fetch_request(HOT_SECTORS_DATASET, request, provider=provider, use_cache=use_cache)

    def convertible_bonds(self, limit: int = 20, *, provider: str | None = None,
                          use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotConvertibleBondsRequest(limit=limit)
        return self._fetch_request(HOT_CONVERTIBLE_BONDS_DATASET, request, provider=provider, use_cache=use_cache)

    def etfs(self, category: str = "popular", limit: int = 20, *, provider: str | None = None,
             use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotEtfsRequest(category=category, limit=limit)
        return self._fetch_request(HOT_ETFS_DATASET, request, provider=provider, use_cache=use_cache)

    def content(self, content_type: str = "topic", limit: int = 20, *, provider: str | None = None,
                use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotContentRequest(contentType=content_type, limit=limit)
        return self._fetch_request(HOT_CONTENT_DATASET, request, provider=provider, use_cache=use_cache)


class ForumNamespace(_Namespace):
    """Public Taoguba forum queries."""

    def replies(
        self,
        *,
        cookies: str | Mapping[str, str],
        user_names: Sequence[str] | None = None,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
    ) -> FetchResult[tuple[ForumReply, ...]]:
        """Fetch qualified replies from the current account's activity feed."""
        return self._client._forum_service.replies(
            cookies=cookies,
            user_names=user_names,
            max_results=max_results,
            since=since,
            until=until,
        )


class OwnershipNamespace(_RequestNamespace):
    """Shareholding and ownership snapshots."""

    def capital_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a capital snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_CAPITAL_SNAPSHOT_DATASET,
            instrument,
            CapitalSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def float_holder(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch floating-holder data in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_FLOAT_HOLDER_DATASET,
            instrument,
            FloatHolderRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def holder_summary_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a holder-summary snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET,
            instrument,
            HolderSummarySnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )


class CompanyNamespace(_RequestNamespace):
    """Company management and executive data."""

    def executive_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch an executive snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            COMPANY_EXECUTIVE_SNAPSHOT_DATASET,
            instrument,
            ExecutiveSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def executive_share_change(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch executive share changes in a FetchResult."""
        return self._fetch_instrument_request(
            COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET,
            instrument,
            ExecutiveShareChangeRequest,
            provider=provider,
            use_cache=use_cache,
        )


class CorporateActionNamespace(_RequestNamespace):
    """Dividend and repurchase observations."""

    def dividend(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch dividend actions in a FetchResult."""
        return self._fetch_instrument_request(
            CORPORATE_ACTION_DIVIDEND_DATASET,
            instrument,
            DividendRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def repurchase(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch repurchase actions in a FetchResult."""
        return self._fetch_instrument_request(
            CORPORATE_ACTION_REPURCHASE_DATASET,
            instrument,
            RepurchaseRequest,
            provider=provider,
            use_cache=use_cache,
        )


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
    Provider, access the network, create a Cache, or create a storage file.
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


__all__ = [
    "CLIENT_ENDPOINTS",
    "ClientEndpoint",
    "CompanyNamespace",
    "CollectorLike",
    "CorporateActionNamespace",
    "DisclosureNamespace",
    "FinancialNamespace",
    "FinchX",
    "FundamentalNamespace",
    "ForumNamespace",
    "HotlistNamespace",
    "IwencaiNamespace",
    "MarketNamespace",
    "MarketNewsNamespace",
    "ArticlesNamespace",
    "NewsNamespace",
    "OwnershipNamespace",
    "ReferenceNamespace",
]
