"""Client namespace implementation: market."""

from __future__ import annotations

from collections.abc import (
    Sequence,
)
from datetime import (
    date,
)
from typing import (
    Any,
    Literal,
)
from finchx.collectors import (
    FetchResult,
)
from finchx.computed import (
    DeviationData,
)
from finchx.contracts import (
    StandardRecord,
)
from finchx.datasets import (
    MARKET_CONCEPT_LIST_DATASET,
    MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET,
    MARKET_CONCEPT_OHLCV_DATASET,
    ConceptRef,
    ConceptListRequest,
    ConceptQuoteSnapshotRequest,
    ConceptOhlcvRequest,
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
    InstrumentUniverse,
    KlineAdjustment,
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
    RankingCriterion,
    RankingDirection,
    MarketSentimentRequest,
    MarketStrongPoolRequest,
    MarketYesterdayLimitUpPoolRequest,
    EquityIntraday5dRequest,
    EquityIntradayRequest,
    IndexIntraday5dRequest,
    IndexIntradayRequest,
)
from finchx.entities import (
    InstrumentKind,
    normalize_instrument,
)
from finchx.api._base import (
    _RequestNamespace,
    _regulation_request,
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
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[DeviationData]:
        """Compute pre-open, current, and next-session deviation observations."""
        return self._client._deviation_service.calculate(
            normalize_instrument(instrument),
            windows=windows,
            as_of=as_of,
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

    def regulation_watchlist(
        self,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch EastMoney's latest risk watchlist and preserve unknown kinds."""
        request = RegulationWatchlistRequest()
        return self._fetch_request(
            MARKET_REGULATION_WATCHLIST_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def abnormal_records(
        self,
        *,
        dataset: Literal["abnormal_events", "severe_events", "prediction_history"],
        page: int = 1,
        page_size: int = 20,
        status: Literal["current", "history", "all"] | None = None,
        triggered: Literal["all", "yes", "no"] | None = None,
        rise_only: bool | None = None,
        include_current: bool | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch exactly one upstream page of one supported abnormal-record dataset."""
        request = _regulation_request(
            AbnormalRecordsRequest,
            dataset=dataset,
            page=page,
            pageSize=page_size,
            status=status,
            triggered=triggered,
            riseOnly=rise_only,
            includeCurrent=include_current,
        )
        return self._fetch_request(
            MARKET_ABNORMAL_RECORDS_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def severe_predictions(
        self,
        *,
        rise_only: bool = False,
        include_bse: bool = True,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the bounded EastMoney severe-prediction pool."""
        request = _regulation_request(
            SeverePredictionsRequest,
            riseOnly=rise_only,
            includeBse=include_bse,
        )
        return self._fetch_request(
            MARKET_SEVERE_PREDICTIONS_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def abnormal_counts(
        self,
        *,
        sort_by: Literal["count", "price", "max_deviation"] = "count",
        order: Literal["asc", "desc"] = "desc",
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the bounded EastMoney abnormal-count pool."""
        request = _regulation_request(
            AbnormalCountsRequest,
            sortBy=sort_by,
            order=order,
        )
        return self._fetch_request(
            MARKET_ABNORMAL_COUNTS_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

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
    ) -> FetchResult[StandardRecord]:
        """Fetch the Tencent five-level order book as one record."""
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
        """Fetch one SSE/SZSE equity or supported index quote snapshot."""
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

# Preserve historical public type identities as implementation moves.
MarketNamespace.__module__ = "finchx.client"
