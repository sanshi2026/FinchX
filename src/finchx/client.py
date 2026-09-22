"""Stable public Client and explicit Dataset namespaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from finchx.collectors import CachePolicy, Collector, FetchResult, RoutingPolicy
from finchx.computed import DeviationData, DeviationService, DeviationWindowConvention
from finchx.datasets import (
    CapitalSnapshotData,
    COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET,
    COMPANY_EXECUTIVE_SNAPSHOT_DATASET,
    CompanyProfileData,
    CORPORATE_ACTION_DIVIDEND_DATASET,
    CORPORATE_ACTION_REPURCHASE_DATASET,
    DISCLOSURE_DOCUMENT_DATASET,
    FINANCIAL_STATEMENT_DATASET,
    FUNDAMENTAL_COMPANY_PROFILE_DATASET,
    FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,
    FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET,
    FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET,
    INSTRUMENT_DATASET,
    InstrumentData,
    IndustryComparisonData,
    IndexIntradayData,
    MARKET_BREADTH_DATASET,
    MarketBreadthData,
    MARKET_BROKEN_LIMIT_POOL_DATASET,
    MarketBrokenLimitPoolData,
    MARKET_CONSECUTIVE_LIMIT_UP_DATASET,
    MarketConsecutiveLimitUpData,
    MARKET_DAILY_REPLAY_DATASET,
    MarketDailyReplayData,
    MARKET_DRAGON_TIGER_DETAIL_DATASET,
    MARKET_DRAGON_TIGER_LIST_DATASET,
    MarketDragonTigerDetailData,
    MarketDragonTigerListData,
    MARKET_EQUITY_INTRADAY_5D_DATASET,
    MARKET_EQUITY_INTRADAY_DATASET,
    EquityIntradayData,
    MARKET_FUND_FLOW_DAILY_DATASET,
    MARKET_FUND_FLOW_INTRADAY_DATASET,
    MARKET_FUND_FLOW_SNAPSHOT_DATASET,
    MarketFundFlowDailyData,
    MarketFundFlowIntradayData,
    MarketFundFlowSnapshotData,
    MARKET_INDEX_INTRADAY_5D_DATASET,
    MARKET_INDEX_INTRADAY_DATASET,
    MARKET_INDUSTRY_COMPARISON_DATASET,
    MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET,
    MARKET_STOCK_KEYWORD_DATASET,
    MARKET_KLINES_DATASET,
    MarketIndustryComparisonData,
    MarketInstrumentSectorSnapshotData,
    MarketStockKeywordData,
    MarketKlineData,
    MarketLimitDownPoolData,
    MarketLimitUpPoolData,
    MARKET_LIMIT_DOWN_POOL_DATASET,
    MARKET_LIMIT_UP_POOL_DATASET,
    MARKET_ORDERBOOK_DATASET,
    MarketOrderbookData,
    MARKET_QUOTE_DATASET,
    MARKET_QUOTE_SNAPSHOT_DATASET,
    MarketQuoteData,
    MarketQuoteSnapshotData,
    MARKET_RANKING_DATASET,
    MarketRankingData,
    MARKET_SENTIMENT_DATASET,
    MarketSentimentData,
    MARKET_STRONG_POOL_DATASET,
    MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET,
    MarketStrongPoolData,
    MarketYesterdayLimitUpPoolData,
    NEWS_DOCUMENT_DATASET,
    FinancialStatementData,
    FloatHolderData,
    DividendData,
    ExecutiveShareChangeData,
    ExecutiveSnapshotData,
    FinancialSummaryData,
    HolderSummarySnapshotData,
    RepurchaseData,
    RevenueBreakdownData,
    TradingCalendarData,
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
    InstrumentRequest,
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
    MarketSentimentRequest,
    MarketStrongPoolRequest,
    MarketYesterdayLimitUpPoolRequest,
    NewsDocumentRef,
    NewsSearchRequest,
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
from finchx.entities import InstrumentId, InstrumentInput, Market, normalize_instrument
from finchx.providers.registry import PROVIDER_REGISTRY, ProviderRegistry
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
        request: Any,
        request_type: type[Any],
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        """Fetch a request model or build one from a single instrument input."""
        if isinstance(request, (InstrumentId, str)):
            request = request_type(instrumentId=normalize_instrument(request))
        return self._fetch_request(
            dataset,
            request,
            provider=provider,
            use_cache=use_cache,
        )


class ReferenceNamespace(_Namespace):
    """Reference and identity lookups."""

    def instrument(
        self,
        instrument_id: InstrumentInput | None = None,
        *,
        request: InstrumentRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[InstrumentData]:
        """Fetch instrument identity data and return it in a FetchResult."""
        if request is not None:
            if instrument_id is not None:
                raise TypeError("instrument_id cannot be combined with request")
        else:
            request = InstrumentRequest(
                instrumentId=(
                    normalize_instrument(instrument_id)
                    if instrument_id is not None
                    else None
                )
            )
        return self._fetch(
            INSTRUMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def trading_calendar(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        *,
        market: Market = Market.CN_A,
        request: TradingCalendarRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[TradingCalendarData]:
        """Return canonical natural-date trading-day flags."""

        if request is not None:
            if start_date is not None or end_date is not None or market is not Market.CN_A:
                raise TypeError("calendar business parameters cannot be combined with request")
        else:
            if start_date is None or end_date is None:
                raise TypeError("trading_calendar requires start_date and end_date")
            request = TradingCalendarRequest(
                market=market,
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
        request: MarketQuoteUniverseRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketQuoteData]:
        """Fetch the selected quote universe in a FetchResult."""
        request = request or MarketQuoteUniverseRequest(universe=universe)
        return self._fetch(
            MARKET_QUOTE_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def ohlcv(
        self,
        instrument_id: InstrumentInput | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        adjustment: KlineAdjustment | None = None,
        *,
        request: KlinesRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketKlineData]:
        """Fetch OHLCV history for one instrument in a FetchResult."""
        if request is not None:
            if any(value is not None for value in (instrument_id, start_date, end_date, adjustment)):
                raise TypeError("ohlcv business parameters cannot be combined with request")
        else:
            if instrument_id is None or start_date is None or end_date is None:
                raise TypeError("ohlcv requires instrument_id, start_date, and end_date")
            request_values: dict[str, Any] = {
                "instrumentId": normalize_instrument(instrument_id),
                "startDate": start_date,
                "endDate": end_date,
            }
            if adjustment is not None:
                request_values["adjustment"] = adjustment
            request = KlinesRequest(**request_values)
        return self._fetch(
            MARKET_KLINES_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def deviation(
        self,
        instrument_id: InstrumentInput,
        *,
        windows: Sequence[int] = (10, 30),
        as_of: date | None = None,
        window_convention: DeviationWindowConvention = DeviationWindowConvention.MAX_DEVIATION_SCAN,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[DeviationData]:
        """Compute close-based 10-day/30-day deviation from existing data."""
        return self._client._deviation_service.calculate(
            normalize_instrument(instrument_id),
            windows=windows,
            as_of=as_of,
            window_convention=window_convention,
            provider=provider,
            use_cache=use_cache,
        )

    def breadth(
        self,
        request: MarketBreadthRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketBreadthData]:
        """Fetch the current market breadth snapshot in a FetchResult."""
        request = request if request is not None else MarketBreadthRequest()
        return self._fetch_request(MARKET_BREADTH_DATASET, request, provider=provider, use_cache=use_cache)

    def broken_limit_pool(
        self,
        request: MarketBrokenLimitPoolRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketBrokenLimitPoolData]:
        """Fetch the latest broken-limit pool snapshot in a FetchResult."""
        request = request if request is not None else MarketBrokenLimitPoolRequest()
        return self._fetch_request(MARKET_BROKEN_LIMIT_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def consecutive_limit_up(
        self,
        request: MarketConsecutiveLimitUpRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketConsecutiveLimitUpData]:
        """Fetch the consecutive-limit-up snapshot in a FetchResult."""
        request = request if request is not None else MarketConsecutiveLimitUpRequest()
        return self._fetch_request(MARKET_CONSECUTIVE_LIMIT_UP_DATASET, request, provider=provider, use_cache=use_cache)

    def daily_replay(
        self,
        request: MarketDailyReplayRequest,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketDailyReplayData]:
        """Fetch one daily replay request in a FetchResult."""
        return self._fetch_request(MARKET_DAILY_REPLAY_DATASET, request, provider=provider, use_cache=use_cache)

    def dragon_tiger_detail(
        self,
        request: MarketDragonTigerDetailRequest,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketDragonTigerDetailData]:
        """Fetch Dragon-Tiger detail data in a FetchResult."""
        return self._fetch_request(MARKET_DRAGON_TIGER_DETAIL_DATASET, request, provider=provider, use_cache=use_cache)

    def dragon_tiger_list(
        self,
        request: MarketDragonTigerListRequest,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketDragonTigerListData]:
        """Fetch Dragon-Tiger list data in a FetchResult."""
        return self._fetch_request(MARKET_DRAGON_TIGER_LIST_DATASET, request, provider=provider, use_cache=use_cache)

    def equity_intraday(
        self,
        request: EquityIntradayRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[EquityIntradayData]:
        """Fetch one equity intraday session in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_EQUITY_INTRADAY_DATASET,
            request,
            EquityIntradayRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def equity_intraday_5d(
        self,
        request: EquityIntraday5dRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[EquityIntradayData]:
        """Fetch five-day equity intraday data in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_EQUITY_INTRADAY_5D_DATASET,
            request,
            EquityIntraday5dRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def fund_flow_daily(
        self,
        request: MarketFundFlowRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketFundFlowDailyData]:
        """Fetch daily fund-flow data in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_FUND_FLOW_DAILY_DATASET,
            request,
            MarketFundFlowRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def fund_flow_intraday(
        self,
        request: MarketFundFlowRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketFundFlowIntradayData]:
        """Fetch intraday fund-flow data in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_FUND_FLOW_INTRADAY_DATASET,
            request,
            MarketFundFlowRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def fund_flow_snapshot(
        self,
        request: MarketFundFlowRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketFundFlowSnapshotData]:
        """Fetch the fund-flow snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_FUND_FLOW_SNAPSHOT_DATASET,
            request,
            MarketFundFlowRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def index_intraday(
        self,
        request: IndexIntradayRequest,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[IndexIntradayData]:
        """Fetch one index intraday session in a FetchResult."""
        return self._fetch_request(MARKET_INDEX_INTRADAY_DATASET, request, provider=provider, use_cache=use_cache)

    def index_intraday_5d(
        self,
        request: IndexIntraday5dRequest,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[IndexIntradayData]:
        """Fetch five-day index intraday data in a FetchResult."""
        return self._fetch_request(MARKET_INDEX_INTRADAY_5D_DATASET, request, provider=provider, use_cache=use_cache)

    def industry_comparison(
        self,
        request: MarketIndustryComparisonRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketIndustryComparisonData]:
        """Fetch the market industry comparison in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_INDUSTRY_COMPARISON_DATASET,
            request,
            MarketIndustryComparisonRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def instrument_sector_snapshot(
        self,
        request: MarketInstrumentSectorSnapshotRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketInstrumentSectorSnapshotData]:
        """Fetch sector tags and snapshots for an instrument in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET,
            request,
            MarketInstrumentSectorSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def stock_keyword(
        self,
        request: MarketStockKeywordRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketStockKeywordData]:
        """Fetch EastMoney source-ranked hot keywords for an instrument."""
        return self._fetch_instrument_request(
            MARKET_STOCK_KEYWORD_DATASET,
            request,
            MarketStockKeywordRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def limit_down_pool(
        self,
        request: MarketLimitDownPoolRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketLimitDownPoolData]:
        """Fetch the latest limit-down pool snapshot in a FetchResult."""
        request = request if request is not None else MarketLimitDownPoolRequest()
        return self._fetch_request(MARKET_LIMIT_DOWN_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def limit_up_pool(
        self,
        request: MarketLimitUpPoolRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketLimitUpPoolData]:
        """Fetch the latest limit-up pool snapshot in a FetchResult."""
        request = request if request is not None else MarketLimitUpPoolRequest()
        return self._fetch_request(MARKET_LIMIT_UP_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def orderbook(
        self,
        request: MarketOrderbookRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketOrderbookData]:
        """Fetch the order book in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_ORDERBOOK_DATASET,
            request,
            MarketOrderbookRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def quote_snapshot(
        self,
        request: MarketQuoteSnapshotRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketQuoteSnapshotData]:
        """Fetch one quote snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            MARKET_QUOTE_SNAPSHOT_DATASET,
            request,
            MarketQuoteSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def ranking(
        self,
        request: MarketRankingRequest,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketRankingData]:
        """Fetch the requested market ranking in a FetchResult."""
        return self._fetch_request(MARKET_RANKING_DATASET, request, provider=provider, use_cache=use_cache)

    def sentiment(
        self,
        request: MarketSentimentRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketSentimentData]:
        """Fetch the market sentiment snapshot in a FetchResult."""
        request = request if request is not None else MarketSentimentRequest()
        return self._fetch_request(MARKET_SENTIMENT_DATASET, request, provider=provider, use_cache=use_cache)

    def strong_pool(
        self,
        request: MarketStrongPoolRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketStrongPoolData]:
        """Fetch the latest strong-pool snapshot in a FetchResult."""
        request = request if request is not None else MarketStrongPoolRequest()
        return self._fetch_request(MARKET_STRONG_POOL_DATASET, request, provider=provider, use_cache=use_cache)

    def yesterday_limit_up_pool(
        self,
        request: MarketYesterdayLimitUpPoolRequest | None = None,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[MarketYesterdayLimitUpPoolData]:
        """Fetch the latest yesterday-limit-up pool snapshot in a FetchResult."""
        request = request if request is not None else MarketYesterdayLimitUpPoolRequest()
        return self._fetch_request(MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET, request, provider=provider, use_cache=use_cache)


class FundamentalNamespace(_RequestNamespace):
    """Company and other source-neutral fundamental lookups."""

    def company_profile(
        self,
        instrument_id: InstrumentInput | None = None,
        *,
        request: CompanyProfileRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[CompanyProfileData]:
        """Fetch a company's profile in a FetchResult."""
        if request is not None:
            if instrument_id is not None:
                raise TypeError("instrument_id cannot be combined with request")
        else:
            request = CompanyProfileRequest(
                instrumentId=(
                    normalize_instrument(instrument_id)
                    if instrument_id is not None
                    else None
                )
            )
        return self._fetch(
            FUNDAMENTAL_COMPANY_PROFILE_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def financial_summary(
        self,
        request: FinancialSummaryRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[FinancialSummaryData]:
        """Fetch a company's financial summary in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,
            request,
            FinancialSummaryRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def industry_comparison(
        self,
        request: FundamentalIndustryComparisonRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[IndustryComparisonData]:
        """Fetch the fundamental industry comparison in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET,
            request,
            FundamentalIndustryComparisonRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def revenue_breakdown(
        self,
        request: RevenueBreakdownRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[RevenueBreakdownData]:
        """Fetch a company's revenue breakdown in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET,
            request,
            RevenueBreakdownRequest,
            provider=provider,
            use_cache=use_cache,
        )


class FinancialNamespace(_Namespace):
    """Financial statement lookups."""

    def statements(
        self,
        instrument_id: InstrumentInput | None = None,
        statement_type: StatementType | None = None,
        *,
        period_end: date | None = None,
        max_periods: int | None = None,
        request: FinancialStatementRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[FinancialStatementData]:
        """Fetch financial statements in a FetchResult."""
        if request is not None:
            if instrument_id is not None or statement_type is not None or period_end is not None or max_periods is not None:
                raise TypeError("statement business parameters cannot be combined with request")
        else:
            if instrument_id is None or statement_type is None:
                raise TypeError("statements requires instrument_id and statement_type")
            request = FinancialStatementRequest(
                instrumentId=normalize_instrument(instrument_id),
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


class NewsNamespace(_Namespace):
    """Individual-stock news search."""

    def search(
        self,
        instrument: InstrumentId | str | None = None,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | None = None,
        until: date | datetime | None = None,
        sort: str = "published_desc",
        request: NewsSearchRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[NewsDocumentRef, ...]]:
        """Search news metadata and return document references in a FetchResult."""
        if request is not None:
            if instrument is not None:
                raise TypeError("instrument cannot be combined with request")
        else:
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


class DisclosureNamespace(_Namespace):
    """Individual-stock disclosure search."""

    def search(
        self,
        instrument: InstrumentId | str | None = None,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | None = None,
        until: date | datetime | None = None,
        categories: Sequence[str] | None = None,
        sort: str = "published_desc",
        request: DisclosureSearchRequest | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[DisclosureDocumentRef, ...]]:
        """Search disclosures and return document references in a FetchResult."""
        if request is not None:
            if instrument is not None:
                raise TypeError("instrument cannot be combined with request")
        else:
            request = DisclosureSearchRequest(
                instrumentId=normalize_document_instrument(instrument),
                page=page,
                pageSize=page_size,
                maxResults=max_results,
                since=since,
                until=until,
                categories=list(categories) if categories is not None else None,
                sort=sort,
            )
        return self._fetch(
            DISCLOSURE_DOCUMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )


class OwnershipNamespace(_RequestNamespace):
    """Shareholding and ownership snapshots."""

    def capital_snapshot(
        self,
        request: CapitalSnapshotRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[CapitalSnapshotData]:
        """Fetch a capital snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_CAPITAL_SNAPSHOT_DATASET,
            request,
            CapitalSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def float_holder(
        self,
        request: FloatHolderRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[FloatHolderData]:
        """Fetch floating-holder data in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_FLOAT_HOLDER_DATASET,
            request,
            FloatHolderRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def holder_summary_snapshot(
        self,
        request: HolderSummarySnapshotRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[HolderSummarySnapshotData]:
        """Fetch a holder-summary snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET,
            request,
            HolderSummarySnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )


class CompanyNamespace(_RequestNamespace):
    """Company management and executive data."""

    def executive_snapshot(
        self,
        request: ExecutiveSnapshotRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[ExecutiveSnapshotData]:
        """Fetch an executive snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            COMPANY_EXECUTIVE_SNAPSHOT_DATASET,
            request,
            ExecutiveSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def executive_share_change(
        self,
        request: ExecutiveShareChangeRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[ExecutiveShareChangeData]:
        """Fetch executive share changes in a FetchResult."""
        return self._fetch_instrument_request(
            COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET,
            request,
            ExecutiveShareChangeRequest,
            provider=provider,
            use_cache=use_cache,
        )


class CorporateActionNamespace(_RequestNamespace):
    """Dividend and repurchase observations."""

    def dividend(
        self,
        request: DividendRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[DividendData]:
        """Fetch dividend actions in a FetchResult."""
        return self._fetch_instrument_request(
            CORPORATE_ACTION_DIVIDEND_DATASET,
            request,
            DividendRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def repurchase(
        self,
        request: RepurchaseRequest | InstrumentInput,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[RepurchaseData]:
        """Fetch repurchase actions in a FetchResult."""
        return self._fetch_instrument_request(
            CORPORATE_ACTION_REPURCHASE_DATASET,
            request,
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
        "reference",
        "market",
        "fundamental",
        "financial",
        "news",
        "disclosure",
        "ownership",
        "company",
        "corporate_action",
    )

    reference: ReferenceNamespace
    market: MarketNamespace
    fundamental: FundamentalNamespace
    financial: FinancialNamespace
    news: NewsNamespace
    disclosure: DisclosureNamespace
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
        self.reference = ReferenceNamespace(self)
        self.market = MarketNamespace(self)
        self.fundamental = FundamentalNamespace(self)
        self.financial = FinancialNamespace(self)
        self.news = NewsNamespace(self)
        self.disclosure = DisclosureNamespace(self)
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
    ClientEndpoint("reference", "instrument", INSTRUMENT_DATASET, InstrumentRequest),
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
    ClientEndpoint("fundamental", "company_profile", FUNDAMENTAL_COMPANY_PROFILE_DATASET, CompanyProfileRequest),
    ClientEndpoint("fundamental", "financial_summary", FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET, FinancialSummaryRequest),
    ClientEndpoint("fundamental", "industry_comparison", FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET, FundamentalIndustryComparisonRequest),
    ClientEndpoint("fundamental", "revenue_breakdown", FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET, RevenueBreakdownRequest),
    ClientEndpoint("financial", "statements", FINANCIAL_STATEMENT_DATASET, FinancialStatementRequest),
    ClientEndpoint("news", "search", NEWS_DOCUMENT_DATASET, NewsSearchRequest),
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
    "MarketNamespace",
    "NewsNamespace",
    "OwnershipNamespace",
    "ReferenceNamespace",
]
