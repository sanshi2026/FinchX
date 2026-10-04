"""Dataset-to-provider adapters and request identities."""

from __future__ import annotations

from collections.abc import (
    Callable,
    Mapping,
)
from dataclasses import (
    dataclass,
)
from datetime import (
    datetime,
)
from typing import (
    Any,
)
from pydantic import (
    BaseModel,
)
from finchx.datasets.definition import (
    DatasetDefinition,
)
from finchx.datasets.disclosure import (
    DISCLOSURE_DOCUMENT_DATASET,
)
from finchx.datasets.financial_statement import (
    FINANCIAL_STATEMENT_DATASET,
    normalize_financial_statement,
)
from finchx.datasets.fundamental_company_profile import (
    FUNDAMENTAL_COMPANY_PROFILE_DATASET,
    normalize_company_profile,
)
from finchx.datasets.instrument import (
    INSTRUMENT_DATASET,
    InstrumentUniverse,
    InstrumentUniverseRequest,
    _normalize_provider_rows,
    _provider_row_identity,
)
from finchx.datasets.company_executive_share_change import (
    normalize_executive_share_change,
)
from finchx.datasets.company_executive_snapshot import (
    normalize_executive_snapshot,
)
from finchx.datasets.corporate_action_dividend import (
    normalize_dividend,
)
from finchx.datasets.corporate_action_repurchase import (
    normalize_repurchase,
)
from finchx.datasets.market_klines import (
    MARKET_KLINES_DATASET,
    _normalize_klines_rows,
)
from finchx.datasets.market_breadth import (
    MARKET_BREADTH_DATASET,
    normalize_market_breadth,
)
from finchx.datasets.market_broken_limit_pool import (
    MARKET_BROKEN_LIMIT_POOL_DATASET,
    normalize_market_broken_limit_pool,
)
from finchx.datasets.market_consecutive_limit_up import (
    MARKET_CONSECUTIVE_LIMIT_UP_DATASET,
    normalize_market_consecutive_limit_up,
)
from finchx.datasets.market_daily_replay import (
    MARKET_DAILY_REPLAY_DATASET,
    normalize_market_daily_replay,
)
from finchx.datasets.market_dragon_tiger import (
    MARKET_DRAGON_TIGER_DETAIL_DATASET,
    MARKET_DRAGON_TIGER_LIST_DATASET,
    normalize_market_dragon_tiger_detail,
    normalize_market_dragon_tiger_list,
)
from finchx.datasets.market_fund_flow import (
    MARKET_FUND_FLOW_DAILY_DATASET,
    MARKET_FUND_FLOW_INTRADAY_DATASET,
    MARKET_FUND_FLOW_SNAPSHOT_DATASET,
    _normalize_fund_flow_daily,
    _normalize_fund_flow_intraday,
    _normalize_fund_flow_snapshot,
)
from finchx.datasets.market_industry_comparison import (
    MARKET_INDUSTRY_COMPARISON_DATASET,
    normalize_industry_comparison as normalize_market_industry_comparison,
)
from finchx.datasets.market_instrument_sector_snapshot import (
    MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET,
    normalize_instrument_sector_snapshot,
)
from finchx.datasets.market_stock_keyword import (
    MARKET_STOCK_KEYWORD_DATASET,
    normalize_stock_keyword,
)
from finchx.datasets.market_concept import (
    MARKET_CONCEPT_LIST_DATASET,
    MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET,
    MARKET_CONCEPT_OHLCV_DATASET,
    normalize_concept,
)
from finchx.datasets.hotlist import (
    HOT_CONTENT_DATASET,
    HOT_CONVERTIBLE_BONDS_DATASET,
    HOT_ETFS_DATASET,
    HOT_SECTORS_DATASET,
    HOT_STOCKS_DATASET,
    normalize_hotlist,
)
from finchx.datasets.market_intraday import (
    MARKET_EQUITY_INTRADAY_5D_DATASET,
    MARKET_EQUITY_INTRADAY_DATASET,
    MARKET_INDEX_INTRADAY_5D_DATASET,
    MARKET_INDEX_INTRADAY_DATASET,
    normalize_equity_intraday,
    normalize_index_intraday,
)
from finchx.datasets.market_limit_down_pool import (
    MARKET_LIMIT_DOWN_POOL_DATASET,
    normalize_market_limit_down_pool,
)
from finchx.datasets.market_limit_up_pool import (
    MARKET_LIMIT_UP_POOL_DATASET,
    normalize_market_limit_up_pool,
)
from finchx.datasets.market_orderbook import (
    MARKET_ORDERBOOK_DATASET,
    _normalize_orderbook_row,
)
from finchx.datasets.market_quote import (
    MARKET_QUOTE_DATASET,
    _normalize_quote_rows,
)
from finchx.datasets.market_quote_snapshot import (
    MARKET_QUOTE_SNAPSHOT_DATASET,
    _normalize_quote_snapshot_row,
)
from finchx.datasets.market_regulation import (
    MARKET_ABNORMAL_COUNTS_DATASET,
    MARKET_ABNORMAL_RECORDS_DATASET,
    MARKET_REGULATION_WATCHLIST_DATASET,
    MARKET_SEVERE_PREDICTIONS_DATASET,
    normalize_abnormal_counts,
    normalize_severe_predictions,
    normalize_watchlist,
    local_filter_records,
)
from finchx.datasets.news import (
    NEWS_DOCUMENT_DATASET,
)
from finchx.datasets.article_detail import (
    ARTICLE_DETAIL_DATASET,
    normalize_article_detail,
)
from finchx.datasets.topic_articles import (
    ARTICLE_TOPIC_DATASET,
    normalize_topic_articles,
)
from finchx.datasets.market_sentiment import (
    MARKET_SENTIMENT_DATASET,
    normalize_market_sentiment,
)
from finchx.datasets.market_strong_pool import (
    MARKET_STRONG_POOL_DATASET,
    normalize_market_strong_pool,
)
from finchx.datasets.market_yesterday_limit_up_pool import (
    MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET,
    normalize_market_yesterday_limit_up_pool,
)
from finchx.datasets.fundamental_financial_summary import (
    normalize_financial_summary,
)
from finchx.datasets.fundamental_industry_comparison import (
    normalize_industry_comparison as normalize_fundamental_industry_comparison,
)
from finchx.datasets.fundamental_revenue_breakdown import (
    normalize_revenue_breakdown,
)
from finchx.datasets.ownership_capital_snapshot import (
    normalize_capital_snapshot,
)
from finchx.datasets.ownership_float_holder import (
    normalize_float_holder,
)
from finchx.datasets.ownership_holder_summary_snapshot import (
    normalize_holder_summary_snapshot,
)
from finchx.datasets.market_ranking import (
    MARKET_RANKING_DATASET,
    _normalize_ranking_rows,
)
from finchx.datasets.provider_rows import (
    _ProviderRowsResponse,
)
from finchx.datasets.trading_calendar import (
    TRADING_CALENDAR_DATASET,
    _normalize_calendar_rows,
)
from finchx.collectors.errors import (
    InvalidRequest,
    SchemaDrift,
)
from finchx.collectors.results import (
    _RouteResult,
)


RouteHandler = Callable[
    [Any, DatasetDefinition[Any, Any], Mapping[str, Any]],
    Any,
]


@dataclass(frozen=True)
class CollectorRoute:
    """One explicit route override used for fixtures or a provider adapter."""

    dataset: DatasetDefinition[Any, Any] | str
    provider_id: str
    handler: RouteHandler

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, (DatasetDefinition, str)):
            raise TypeError("route dataset must be a DatasetDefinition or dataset name")
        if not isinstance(self.provider_id, str) or not self.provider_id:
            raise ValueError("route provider_id must be a non-empty string")
        if not callable(self.handler):
            raise TypeError("route handler must be callable")


def _request_for(
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    if "request" in kwargs:
        if len(kwargs) != 1:
            raise TypeError("request cannot be combined with other Collector keyword arguments")
        return kwargs["request"]
    try:
        return definition.request_type(**dict(kwargs))
    except (TypeError, ValueError) as exc:
        raise InvalidRequest(
            f"invalid request for dataset {definition.name!r}: {exc}"
        ) from exc


def _request_identity(
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    """Return the validated business request used for a deterministic cache key."""

    if definition.name == MARKET_DAILY_REPLAY_DATASET.name:
        if set(kwargs) != {"request", "session"}:
            raise InvalidRequest(
                "market.daily_replay requires request and session execution inputs"
            )
        session = kwargs["session"]
        if not isinstance(session, str) or not session.strip():
            raise InvalidRequest("session must be a non-empty string")
        request = kwargs["request"]
        if not isinstance(request, definition.request_type):
            raise InvalidRequest("market.daily_replay request must be a MarketDailyReplayRequest")
        return request.model_dump(mode="python", by_alias=True)

    if "request" in kwargs:
        if len(kwargs) != 1:
            raise InvalidRequest("request cannot be combined with other Collector keyword arguments")
        request = kwargs["request"]
    elif isinstance(definition.request_type, type) and issubclass(
        definition.request_type, BaseModel
    ):
        try:
            request = definition.request_type(**dict(kwargs))
        except (TypeError, ValueError) as exc:
            raise InvalidRequest(
                f"invalid request for dataset {definition.name!r}: {exc}"
            ) from exc
    else:
        request = dict(kwargs)

    if isinstance(request, BaseModel):
        return request.model_dump(mode="python", by_alias=True)
    return request


def _calendar_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.get_calendar(request)
    return _normalize_calendar_rows(request, rows, source=provider.source)


def _with_provider_rows_metadata(response: Any, data: Any) -> Any:
    if not isinstance(response, _ProviderRowsResponse):
        return data
    metadata = dict(response.metadata)
    metadata["returned_count"] = len(data)
    return _RouteResult(data, response.warnings, metadata)


def _request_normalizer_route(
    method_name: str,
    normalizer: Callable[..., Any],
) -> RouteHandler:
    """Bind one typed provider request method to its existing normalizer."""

    def route(
        provider: Any,
        definition: DatasetDefinition[Any, Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        passthrough = _generic_route_override(provider, kwargs)
        if passthrough is not _NO_GENERIC_OVERRIDE:
            return passthrough
        request = _request_for(definition, kwargs)
        method = getattr(provider, method_name, None)
        if not callable(method):
            fetch = getattr(provider, "fetch", None)
            if callable(fetch):
                return fetch(**dict(kwargs))
            raise AttributeError(f"Provider has no {method_name} method")
        raw = method(request)
        normalized = normalizer(
            request,
            raw.rows if isinstance(raw, _ProviderRowsResponse) else raw,
            source=provider.source,
        )
        return _with_provider_rows_metadata(raw, normalized)

    return route


def _regulation_route(
    method_name: str,
    normalizer: Callable[..., Any],
    clock: Callable[[], datetime],
) -> RouteHandler:
    """Carry EastMoney pagination metadata through normalization and caching."""

    def route(
        provider: Any,
        definition: DatasetDefinition[Any, Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        passthrough = _generic_route_override(provider, kwargs)
        if passthrough is not _NO_GENERIC_OVERRIDE:
            return passthrough
        request = _request_for(definition, kwargs)
        method = getattr(provider, method_name, None)
        if not callable(method):
            raise AttributeError(f"Provider has no {method_name} method")
        response = method(request)
        captured_at = _route_capture_time(clock)
        source_url = response.metadata.get("source_url")
        if not isinstance(source_url, str) or not source_url:
            raise SchemaDrift("EastMoney regulation response omitted source_url metadata")
        try:
            records = normalizer(
                request,
                response.rows,
                captured_at=captured_at,
                source=provider.source,
                source_url=source_url,
            )
        except (TypeError, ValueError) as exc:
            raise SchemaDrift(f"EastMoney {definition.name} rows could not be normalized: {exc}") from exc
        metadata = dict(response.metadata)
        metadata["returned_count"] = len(records)
        if definition.name == MARKET_REGULATION_WATCHLIST_DATASET.name:
            metadata["unclassified_count"] = len(response.rows)
            metadata["classification_complete"] = False
        if definition.name == MARKET_ABNORMAL_RECORDS_DATASET.name:
            metadata["records_dataset"] = request.dataset
            metadata["upstream_page"] = request.page
            metadata["page_size"] = request.page_size
            metadata["has_more"] = bool(metadata.get("has_more", False))
            metadata["page_complete"] = bool(metadata.get("page_complete", False))
            metadata["collection_complete"] = bool(metadata.get("collection_complete", False))
        return _RouteResult(records, response.warnings, metadata)

    return route


def _topic_articles_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    """Normalize a provider's topic news refs and preserve feed warnings."""

    passthrough = _generic_route_override(provider, kwargs)
    if passthrough is not _NO_GENERIC_OVERRIDE:
        return passthrough
    request = _request_for(definition, kwargs)
    method = getattr(provider, "fetch_raw_topic_articles", None)
    if not callable(method):
        raise AttributeError("Provider has no fetch_raw_topic_articles method")
    raw = method(request)
    records = normalize_topic_articles(request, raw, source=provider.source)
    warnings = raw.get("warnings", ()) if isinstance(raw, Mapping) else ()
    return _RouteResult(records, tuple(warnings or ()))


def _daily_replay_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    """Execute the authenticated replay without making credentials business data."""

    if set(kwargs) != {"request", "session"}:
        raise InvalidRequest(
            "market.daily_replay requires request and session execution inputs"
        )
    request = kwargs["request"]
    if not isinstance(request, definition.request_type):
        raise InvalidRequest("market.daily_replay request must be a MarketDailyReplayRequest")
    session = kwargs["session"]
    if not isinstance(session, str) or not session.strip():
        raise InvalidRequest("session must be a non-empty string")
    method = getattr(provider, "fetch_replay", None)
    if not callable(method):
        raise AttributeError("Provider has no fetch_replay method")
    raw = method(request, session=session)
    return normalize_market_daily_replay(request, raw, source=provider.source)


def _fund_flow_route(normalizer: Callable[..., Any], response_field: str) -> RouteHandler:
    """Normalize one view from Tencent's shared fund-flow response."""

    def route(
        provider: Any,
        definition: DatasetDefinition[Any, Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        passthrough = _generic_route_override(provider, kwargs)
        if passthrough is not _NO_GENERIC_OVERRIDE:
            return passthrough
        request = _request_for(definition, kwargs)
        method = getattr(provider, "fetch_raw_fund_flow", None)
        if not callable(method):
            fetch = getattr(provider, "fetch", None)
            if callable(fetch):
                return fetch(**dict(kwargs))
            raise AttributeError("Provider has no fetch_raw_fund_flow method")
        response = method(request.instrument_id)
        raw = getattr(response, response_field)
        return normalizer(request, raw, source=provider.source)

    return route


def _clocked_route(
    handler: Callable[[Any, DatasetDefinition[Any, Any], Mapping[str, Any], Callable[[], datetime]], Any],
    clock: Callable[[], datetime],
) -> RouteHandler:
    def route(
        provider: Any,
        definition: DatasetDefinition[Any, Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        return handler(provider, definition, kwargs, clock)

    return route


def _klines_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
    clock: Callable[[], datetime],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.fetch_klines(request)
    records = _normalize_klines_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )
    return _with_provider_rows_metadata(rows, records)


def _quote_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
    clock: Callable[[], datetime],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.fetch_quotes(request)
    records = _normalize_quote_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )
    return _with_provider_rows_metadata(rows, records)


def _ranking_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
    clock: Callable[[], datetime],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.fetch_ranking(request)
    records = _normalize_ranking_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )
    return _with_provider_rows_metadata(rows, records)


def _quote_snapshot_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    request = _request_for(definition, kwargs)
    row = provider.fetch_raw_quote(request.instrument_id)
    return _normalize_quote_snapshot_row(request, row, source=provider.source)


def _orderbook_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    request = _request_for(definition, kwargs)
    row = provider.fetch_raw_quote(request.instrument_id)
    return _normalize_orderbook_row(request, row, source=provider.source)


def _instrument_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
    clock: Callable[[], datetime],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.fetch_instrument(request)
    records = _normalize_provider_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )
    return _with_provider_rows_metadata(rows, records)


def _instrument_listing_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
    clock: Callable[[], datetime],
) -> Any:
    """Use a listing-capable Provider for an exact instrument lookup."""

    passthrough = _generic_route_override(provider, kwargs)
    if passthrough is not _NO_GENERIC_OVERRIDE:
        return passthrough
    request = _request_for(definition, kwargs)
    method = getattr(provider, "list_instruments", None)
    if not callable(method):
        fetch = getattr(provider, "fetch", None)
        if callable(fetch):
            return fetch(**dict(kwargs))
        raise AttributeError("Provider has no list_instruments method")
    listing_request = InstrumentUniverseRequest(universe=InstrumentUniverse.CN_A_SHARE)
    rows = method(listing_request)
    matching_rows = tuple(
        row for row in rows if _provider_row_identity(row) == request.instrument_id
    )
    records = _normalize_provider_rows(
        request,
        matching_rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )
    return _with_provider_rows_metadata(rows, records)


def _financial_statement_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    passthrough = _generic_route_override(provider, kwargs)
    if passthrough is not _NO_GENERIC_OVERRIDE:
        return passthrough
    request = _request_for(definition, kwargs)
    row = provider.fetch_raw_statement(request)
    return normalize_financial_statement(request, row, source=provider.source)


def _company_profile_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    passthrough = _generic_route_override(provider, kwargs)
    if passthrough is not _NO_GENERIC_OVERRIDE:
        return passthrough
    request = _request_for(definition, kwargs)
    row = provider.fetch_bundle(request)
    return normalize_company_profile(request, row, source=provider.source)


def _news_search_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    passthrough = _generic_route_override(provider, kwargs)
    if passthrough is not _NO_GENERIC_OVERRIDE:
        return passthrough
    request = _request_for(definition, kwargs)
    # The existing document service owns bounded pagination and the two-stage
    # DocumentRef contract.  Reuse it with this Collector-resolved Provider so
    # the public Client path still has one runtime owner.
    from finchx.query.documents import NewsService

    outcome = NewsService(provider)._search_request_with_warnings(request)
    return _RouteResult(outcome.records, outcome.warnings)


def _disclosure_search_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    passthrough = _generic_route_override(provider, kwargs)
    if passthrough is not _NO_GENERIC_OVERRIDE:
        return passthrough
    request = _request_for(definition, kwargs)
    from finchx.query.documents import DisclosureService

    outcome = DisclosureService(provider)._search_request_with_warnings(request)
    return _RouteResult(outcome.records, outcome.warnings)


_NO_GENERIC_OVERRIDE = object()


def _generic_route_override(provider: Any, kwargs: Mapping[str, Any]) -> Any:
    """Keep the generic injection seam available to test doubles."""

    if "request" not in kwargs or len(kwargs) == 1:
        return _NO_GENERIC_OVERRIDE
    fetch = getattr(provider, "fetch", None)
    if not callable(fetch):
        return _NO_GENERIC_OVERRIDE
    return fetch(**dict(kwargs))


def _generic_provider_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    fetch = getattr(provider, "fetch", None)
    if not callable(fetch):
        raise AttributeError(f"Provider has no generic fetch method for {definition.name!r}")
    return fetch(**dict(kwargs))


def _route_capture_time(clock: Callable[[], datetime]) -> datetime:
    captured_at = clock()
    if (
        not isinstance(captured_at, datetime)
        or captured_at.tzinfo is None
        or captured_at.utcoffset() is None
    ):
        raise ValueError("Collector clock must return a timezone-aware datetime")
    return captured_at


def default_route(
    definition: DatasetDefinition[Any, Any],
    clock: Callable[[], datetime],
    provider_type: type[Any],
) -> RouteHandler | None:
    if definition.name == TRADING_CALENDAR_DATASET.name:
        return _calendar_route
    regulation_methods = {
        MARKET_REGULATION_WATCHLIST_DATASET.name: ("fetch_watchlist", normalize_watchlist),
        MARKET_ABNORMAL_RECORDS_DATASET.name: ("fetch_abnormal_records", local_filter_records),
        MARKET_SEVERE_PREDICTIONS_DATASET.name: ("fetch_severe_predictions", normalize_severe_predictions),
        MARKET_ABNORMAL_COUNTS_DATASET.name: ("fetch_abnormal_counts", normalize_abnormal_counts),
    }
    regulation_route = regulation_methods.get(definition.name)
    if regulation_route is not None and hasattr(provider_type, regulation_route[0]):
        return _regulation_route(regulation_route[0], regulation_route[1], clock)
    if definition.name == MARKET_BREADTH_DATASET.name and hasattr(
        provider_type, "fetch_raw_breadth"
    ):
        return _request_normalizer_route("fetch_raw_breadth", normalize_market_breadth)
    if definition.name == MARKET_LIMIT_UP_POOL_DATASET.name and hasattr(
        provider_type, "fetch_raw_limit_up_pool"
    ):
        return _request_normalizer_route("fetch_raw_limit_up_pool", normalize_market_limit_up_pool)
    if definition.name == MARKET_LIMIT_DOWN_POOL_DATASET.name and hasattr(
        provider_type, "fetch_raw_limit_down_pool"
    ):
        return _request_normalizer_route("fetch_raw_limit_down_pool", normalize_market_limit_down_pool)
    if definition.name == MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET.name and hasattr(
        provider_type, "fetch_raw_yesterday_limit_up_pool"
    ):
        return _request_normalizer_route(
            "fetch_raw_yesterday_limit_up_pool",
            normalize_market_yesterday_limit_up_pool,
        )
    if definition.name == MARKET_STRONG_POOL_DATASET.name and hasattr(
        provider_type, "fetch_raw_strong_pool"
    ):
        return _request_normalizer_route("fetch_raw_strong_pool", normalize_market_strong_pool)
    if definition.name == MARKET_BROKEN_LIMIT_POOL_DATASET.name and hasattr(
        provider_type, "fetch_raw_broken_limit_pool"
    ):
        return _request_normalizer_route("fetch_raw_broken_limit_pool", normalize_market_broken_limit_pool)
    if definition.name == MARKET_DAILY_REPLAY_DATASET.name and hasattr(
        provider_type, "fetch_replay"
    ):
        return _daily_replay_route
    if definition.name == MARKET_SENTIMENT_DATASET.name and hasattr(
        provider_type, "fetch_snapshot"
    ):
        return _request_normalizer_route("fetch_snapshot", normalize_market_sentiment)
    if definition.name == MARKET_CONSECUTIVE_LIMIT_UP_DATASET.name and hasattr(
        provider_type, "fetch_snapshot"
    ):
        return _request_normalizer_route(
            "fetch_snapshot",
            normalize_market_consecutive_limit_up,
        )
    if definition.name == MARKET_DRAGON_TIGER_LIST_DATASET.name and hasattr(
        provider_type, "fetch_list"
    ):
        return _request_normalizer_route("fetch_list", normalize_market_dragon_tiger_list)
    if definition.name == MARKET_DRAGON_TIGER_DETAIL_DATASET.name and hasattr(
        provider_type, "fetch_detail"
    ):
        return _request_normalizer_route("fetch_detail", normalize_market_dragon_tiger_detail)
    if definition.name == MARKET_EQUITY_INTRADAY_DATASET.name and hasattr(
        provider_type, "fetch_equity_intraday"
    ):
        return _request_normalizer_route("fetch_equity_intraday", normalize_equity_intraday)
    if definition.name == MARKET_EQUITY_INTRADAY_5D_DATASET.name and hasattr(
        provider_type, "fetch_equity_intraday_5d"
    ):
        return _request_normalizer_route("fetch_equity_intraday_5d", normalize_equity_intraday)
    if definition.name == MARKET_INDEX_INTRADAY_DATASET.name and hasattr(
        provider_type, "fetch_index_intraday"
    ):
        return _request_normalizer_route("fetch_index_intraday", normalize_index_intraday)
    if definition.name == MARKET_INDEX_INTRADAY_5D_DATASET.name and hasattr(
        provider_type, "fetch_index_intraday_5d"
    ):
        return _request_normalizer_route("fetch_index_intraday_5d", normalize_index_intraday)
    if definition.name == MARKET_FUND_FLOW_SNAPSHOT_DATASET.name and hasattr(
        provider_type, "fetch_raw_fund_flow"
    ):
        return _fund_flow_route(_normalize_fund_flow_snapshot, "snapshot")
    if definition.name == MARKET_FUND_FLOW_INTRADAY_DATASET.name and hasattr(
        provider_type, "fetch_raw_fund_flow"
    ):
        return _fund_flow_route(_normalize_fund_flow_intraday, "intraday_rows")
    if definition.name == MARKET_FUND_FLOW_DAILY_DATASET.name and hasattr(
        provider_type, "fetch_raw_fund_flow"
    ):
        return _fund_flow_route(_normalize_fund_flow_daily, "daily_rows")
    if definition.name == MARKET_INDUSTRY_COMPARISON_DATASET.name and hasattr(
        provider_type, "fetch_raw_industry_comparison"
    ):
        return _request_normalizer_route(
            "fetch_raw_industry_comparison",
            normalize_market_industry_comparison,
        )
    if definition.name == MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET.name and hasattr(
        provider_type, "fetch_raw_instrument_sector_snapshot"
    ):
        return _request_normalizer_route(
            "fetch_raw_instrument_sector_snapshot",
            normalize_instrument_sector_snapshot,
        )
    if definition.name == MARKET_STOCK_KEYWORD_DATASET.name and hasattr(
        provider_type, "fetch_raw_stock_keyword"
    ):
        return _request_normalizer_route(
            "fetch_raw_stock_keyword",
            normalize_stock_keyword,
        )
    concept_methods = {
        MARKET_CONCEPT_LIST_DATASET.name: "fetch_raw_concept_list",
        MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET.name: "fetch_raw_concept_quote_snapshot",
        MARKET_CONCEPT_OHLCV_DATASET.name: "fetch_raw_concept_ohlcv",
    }
    if definition.name in concept_methods and hasattr(provider_type, concept_methods[definition.name]):
        return _request_normalizer_route(concept_methods[definition.name], normalize_concept)
    hotlist_datasets = {
        HOT_STOCKS_DATASET.name,
        HOT_SECTORS_DATASET.name,
        HOT_CONVERTIBLE_BONDS_DATASET.name,
        HOT_ETFS_DATASET.name,
        HOT_CONTENT_DATASET.name,
    }
    if definition.name in hotlist_datasets and hasattr(provider_type, "fetch_raw_hotlist"):
        return _request_normalizer_route("fetch_raw_hotlist", normalize_hotlist)
    if definition.name == MARKET_KLINES_DATASET.name:
        return _clocked_route(_klines_route, clock)
    if definition.name == MARKET_QUOTE_DATASET.name:
        return _clocked_route(_quote_route, clock)
    if definition.name == MARKET_RANKING_DATASET.name:
        return _clocked_route(_ranking_route, clock)
    if definition.name == MARKET_QUOTE_SNAPSHOT_DATASET.name:
        return _quote_snapshot_route
    if definition.name == MARKET_ORDERBOOK_DATASET.name:
        return _orderbook_route
    if definition.name == INSTRUMENT_DATASET.name and hasattr(provider_type, "fetch_instrument"):
        return _clocked_route(_instrument_route, clock)
    if definition.name == INSTRUMENT_DATASET.name and hasattr(provider_type, "list_instruments"):
        return _clocked_route(_instrument_listing_route, clock)
    if definition.name == FINANCIAL_STATEMENT_DATASET.name and hasattr(
        provider_type, "fetch_raw_statement"
    ):
        return _financial_statement_route
    if definition.name == FUNDAMENTAL_COMPANY_PROFILE_DATASET.name and hasattr(
        provider_type, "fetch_bundle"
    ):
        return _company_profile_route
    f10_routes = {
        "fundamental.financial_summary": normalize_financial_summary,
        "fundamental.industry_comparison": normalize_fundamental_industry_comparison,
        "fundamental.revenue_breakdown": normalize_revenue_breakdown,
        "ownership.capital_snapshot": normalize_capital_snapshot,
        "ownership.holder_summary_snapshot": normalize_holder_summary_snapshot,
        "company.executive_snapshot": normalize_executive_snapshot,
        "company.executive_share_change": normalize_executive_share_change,
        "corporate_action.dividend": normalize_dividend,
        "corporate_action.repurchase": normalize_repurchase,
    }
    normalizer = f10_routes.get(definition.name)
    if normalizer is not None and hasattr(provider_type, "fetch_bundle"):
        return _request_normalizer_route("fetch_bundle", normalizer)
    if definition.name == "ownership.float_holder" and hasattr(
        provider_type, "fetch_raw_float_holders"
    ):
        return _request_normalizer_route("fetch_raw_float_holders", normalize_float_holder)
    if definition.name == NEWS_DOCUMENT_DATASET.name and hasattr(
        provider_type, "fetch_raw_news_page"
    ):
        return _news_search_route
    if definition.name == ARTICLE_DETAIL_DATASET.name and hasattr(
        provider_type, "fetch_raw_article_detail"
    ):
        return _request_normalizer_route(
            "fetch_raw_article_detail",
            normalize_article_detail,
        )
    if definition.name == ARTICLE_TOPIC_DATASET.name and hasattr(
        provider_type, "fetch_raw_topic_articles"
    ):
        return _topic_articles_route
    if definition.name == DISCLOSURE_DOCUMENT_DATASET.name and hasattr(
        provider_type, "fetch_raw_disclosure_page"
    ):
        return _disclosure_search_route
    if definition.name in {"iwencai.selection", "iwencai.search", "iwencai.report_detail"} and hasattr(
        provider_type, "fetch"
    ):
        return _generic_provider_route
    return None

# Keep historical public class identities for callers and pickles.
CollectorRoute.__module__ = "finchx.collectors.core"
