"""Small, deterministic Dataset-to-Provider Collector for FinchX."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
from numbers import Real
import re
from time import sleep
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from finchx.contracts import Source
from finchx.datasets.definition import DatasetDefinition
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
from finchx.datasets.company_executive_share_change import normalize_executive_share_change
from finchx.datasets.company_executive_snapshot import normalize_executive_snapshot
from finchx.datasets.corporate_action_dividend import normalize_dividend
from finchx.datasets.corporate_action_repurchase import normalize_repurchase
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
from finchx.datasets.news import NEWS_DOCUMENT_DATASET
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
from finchx.datasets.fundamental_financial_summary import normalize_financial_summary
from finchx.datasets.fundamental_industry_comparison import normalize_industry_comparison as normalize_fundamental_industry_comparison
from finchx.datasets.fundamental_revenue_breakdown import normalize_revenue_breakdown
from finchx.datasets.ownership_capital_snapshot import normalize_capital_snapshot
from finchx.datasets.ownership_float_holder import normalize_float_holder
from finchx.datasets.ownership_holder_summary_snapshot import normalize_holder_summary_snapshot
from finchx.datasets.market_ranking import (
    MARKET_RANKING_DATASET,
    _normalize_ranking_rows,
)
from finchx.datasets.trading_calendar import (
    TRADING_CALENDAR_DATASET,
    _normalize_calendar_rows,
)
from finchx.providers.errors import ProviderError
from finchx.providers.registry import (
    PROVIDER_REGISTRY,
    DatasetRoutingSemantics,
    ProviderRegistry,
    ProviderSpec,
)
from finchx.health import HealthError, HealthMonitor, HealthObservation
from finchx.observability import (
    CacheObservationState,
    ObservabilityError,
    ObservabilityMonitor,
)
from finchx.quality import QualityError, QualityMonitor
from finchx.storage import Cache, CacheState, StorageKey, StoredObject

from finchx.collectors.errors import (
    AllProvidersFailed,
    AuthenticationError,
    CollectorError,
    InvalidRequest,
    MissingOptionalDependency,
    NoData,
    ProviderDoesNotSupportDataset,
    ProviderExecutionError,
    RateLimitError,
    SchemaDrift,
    SourceUnavailable,
    Timeout,
    UnknownDataset,
    UnknownProvider,
)


DataT = TypeVar("DataT")
ProviderFactory = Callable[[], Any]
RouteHandler = Callable[
    [Any, DatasetDefinition[Any, Any], Mapping[str, Any]],
    Any,
]
ErrorType = type[BaseException]

_DEFAULT_RETRYABLE_ERRORS = frozenset({Timeout, RateLimitError, SourceUnavailable})
_DEFAULT_FALLBACK_ERRORS = frozenset(
    {Timeout, RateLimitError, SourceUnavailable, NoData}
)


@dataclass(frozen=True)
class FetchAttempt:
    """Safe, per-attempt execution facts retained by a successful fetch."""

    provider: str
    attempt: int
    started_at: datetime
    captured_at: datetime
    success: bool
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider:
            raise ValueError("attempt provider must be a non-empty string")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("attempt must be a positive integer")
        for name, value in (
            ("started_at", self.started_at),
            ("captured_at", self.captured_at),
        ):
            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(f"{name} must be timezone-aware")
        if type(self.success) is not bool:
            raise TypeError("success must be a bool")
        if self.success and (self.error_type is not None or self.error_message is not None):
            raise ValueError("successful attempts cannot contain an error")

    @property
    def provider_id(self) -> str:
        return self.provider

    @property
    def attempt_number(self) -> int:
        return self.attempt


@dataclass(frozen=True)
class RoutingPolicy:
    """Small runtime policy for Provider order, retry, and fallback behavior."""

    provider_order: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    max_retries: int = 1
    retryable_errors: frozenset[ErrorType] = _DEFAULT_RETRYABLE_ERRORS
    fallback_errors: frozenset[ErrorType] = _DEFAULT_FALLBACK_ERRORS
    allow_fallback: bool = True
    retry_delay_seconds: float = 0.0
    sleeper: Callable[[float], None] = sleep

    def __post_init__(self) -> None:
        if type(self.max_retries) is not int or self.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        if (
            not isinstance(self.retry_delay_seconds, (int, float))
            or isinstance(self.retry_delay_seconds, bool)
            or not math.isfinite(float(self.retry_delay_seconds))
            or self.retry_delay_seconds < 0
        ):
            raise ValueError("retry_delay_seconds must be a finite non-negative number")
        if type(self.allow_fallback) is not bool:
            raise TypeError("allow_fallback must be a bool")
        if not callable(self.sleeper):
            raise TypeError("sleeper must be callable")

        normalized_order: dict[str, tuple[str, ...]] = {}
        for dataset, providers in dict(self.provider_order).items():
            if not isinstance(dataset, str) or not dataset.strip():
                raise ValueError("provider_order dataset names must be non-empty strings")
            provider_ids = tuple(providers)
            if not provider_ids or any(
                not isinstance(provider_id, str) or not provider_id
                for provider_id in provider_ids
            ):
                raise ValueError("provider_order values must contain Provider ids")
            if len(set(provider_ids)) != len(provider_ids):
                raise ValueError(f"provider_order repeats a Provider for {dataset!r}")
            normalized_order[dataset] = provider_ids
        object.__setattr__(self, "provider_order", MappingProxyType(normalized_order))

        for name, values in (
            ("retryable_errors", self.retryable_errors),
            ("fallback_errors", self.fallback_errors),
        ):
            error_types = frozenset(values)
            if any(
                not isinstance(error_type, type)
                or not issubclass(error_type, BaseException)
                for error_type in error_types
            ):
                raise TypeError(f"{name} must contain exception classes")
            object.__setattr__(self, name, error_types)

    def provider_ids_for(self, dataset: DatasetDefinition[Any, Any]) -> tuple[str, ...] | None:
        return self.provider_order.get(dataset.name)

    def should_retry(self, error: BaseException, retry_count: int) -> bool:
        return retry_count < self.max_retries and _matches_error(error, self.retryable_errors)

    def should_fallback(self, error: BaseException) -> bool:
        return self.allow_fallback and _matches_error(error, self.fallback_errors)

    def wait_before_retry(self) -> None:
        if self.retry_delay_seconds:
            self.sleeper(float(self.retry_delay_seconds))


@dataclass(frozen=True)
class FetchResult(Generic[DataT]):
    """The data and direct provenance of one successful Collector fetch."""

    data: DataT
    dataset: DatasetDefinition[Any, Any]
    provider: str | None
    captured_at: datetime
    warnings: tuple[str, ...] = ()
    provenance: tuple[Source, ...] = ()
    attempts: tuple[FetchAttempt, ...] = ()
    fallback_used: bool = False
    cache_hit: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, DatasetDefinition):
            raise TypeError("dataset must be a DatasetDefinition")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider
        ):
            raise ValueError("provider must be None or a non-empty string")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        if type(self.fallback_used) is not bool:
            raise TypeError("fallback_used must be a bool")
        if type(self.cache_hit) is not bool:
            raise TypeError("cache_hit must be a bool")
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        object.__setattr__(self, "attempts", tuple(self.attempts))
        if any(not isinstance(attempt, FetchAttempt) for attempt in self.attempts):
            raise TypeError("attempts must contain FetchAttempt values")

    @property
    def dataset_id(self) -> str:
        """Return the stable Dataset name without changing the Dataset contract."""

        return self.dataset.name

    @property
    def provider_id(self) -> str | None:
        """Return the selected stable Provider identity."""

        return self.provider


@dataclass(frozen=True)
class CachePolicy:
    """Small Dataset-level cache policy used by the Collector.

    Policies are disabled by default.  A mapping passed to ``Collector`` may
    select policies by ``<dataset>@<schema_version>``; the Dataset identity is
    consequently independent of the selected Provider.
    """

    enabled: bool = False
    ttl: float | timedelta | None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("cache policy enabled must be a bool")
        if self.ttl is None:
            return
        if isinstance(self.ttl, timedelta):
            seconds = self.ttl.total_seconds()
        elif isinstance(self.ttl, Real) and not isinstance(self.ttl, bool):
            seconds = float(self.ttl)
        else:
            raise TypeError("cache policy ttl must be seconds, timedelta, or None")
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("cache policy ttl must be finite and non-negative")


_CACHE_PROVIDER_METADATA = "__finchx_collector_provider__"
_CACHE_CAPTURED_AT_METADATA = "__finchx_collector_captured_at__"
_CACHE_PROVENANCE_METADATA = "__finchx_collector_provenance__"
_CACHE_WARNINGS_METADATA = "__finchx_collector_warnings__"
_CACHE_FALLBACK_METADATA = "__finchx_collector_fallback_used__"


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


class Collector:
    """Resolve one Dataset to Providers under one bounded runtime policy.

    Registry declaration order remains the default.  Retry and fallback are
    finite, policy-controlled, and never enabled by Provider metadata.
    """

    def __init__(
        self,
        *,
        registry: ProviderRegistry = PROVIDER_REGISTRY,
        provider_instances: Mapping[str, Any] | None = None,
        provider_factories: Mapping[str, ProviderFactory] | None = None,
        routes: Iterable[CollectorRoute]
        | Mapping[tuple[DatasetDefinition[Any, Any] | str, str], RouteHandler]
        | None = None,
        clock: Callable[[], datetime] | None = None,
        policy: RoutingPolicy | None = None,
        cache: Cache | None = None,
        cache_policy: CachePolicy | Mapping[str, CachePolicy] | None = None,
        health: HealthMonitor | None = None,
        quality: QualityMonitor | None = None,
        observability: ObservabilityMonitor | None = None,
    ) -> None:
        if not isinstance(registry, ProviderRegistry):
            raise TypeError("registry must be a ProviderRegistry")
        self._registry = registry
        self._provider_instances = MappingProxyType(dict(provider_instances or {}))
        self._provider_factories = MappingProxyType(dict(provider_factories or {}))
        overlap = set(self._provider_instances).intersection(self._provider_factories)
        if overlap:
            raise ValueError(
                "provider instances and factories overlap: "
                + ", ".join(sorted(overlap))
            )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._policy = policy or RoutingPolicy()
        if not isinstance(self._policy, RoutingPolicy):
            raise TypeError("policy must be a RoutingPolicy")
        if cache is not None and not _is_cache_like(cache):
            raise TypeError("cache must provide get and put methods")
        self._cache = cache
        self._cache_policy = _normalize_cache_policy(cache_policy)
        if cache is None and _has_enabled_cache_policy(self._cache_policy):
            raise ValueError("an enabled cache policy requires a Cache")
        if health is not None and not isinstance(health, HealthMonitor):
            raise TypeError("health must be a HealthMonitor")
        self._health = health or HealthMonitor()
        if quality is not None and not isinstance(quality, QualityMonitor):
            raise TypeError("quality must be a QualityMonitor")
        self._quality = quality or QualityMonitor(clock=self._clock)
        if observability is not None and not isinstance(observability, ObservabilityMonitor):
            raise TypeError("observability must be an ObservabilityMonitor")
        self._observability = observability or ObservabilityMonitor()
        self._routes: dict[tuple[str, str], RouteHandler] = {}
        self._install_default_routes()
        self._install_routes(routes)

    def fetch(
        self,
        dataset: DatasetDefinition[Any, Any] | str,
        provider: str | None = None,
        *,
        use_cache: bool | None = None,
        **kwargs: Any,
    ) -> FetchResult[Any]:
        """Fetch one Dataset under the configured retry and fallback policy."""

        definition = self._resolve_dataset(dataset)
        if use_cache is not None and type(use_cache) is not bool:
            raise TypeError("use_cache must be a bool or None")
        selected_cache_policy = self._cache_policy_for(definition)
        cache_enabled = (
            self._cache is not None
            and selected_cache_policy.enabled
            and use_cache is not False
        )
        cache_key = (
            self._cache_key(definition, kwargs)
            if cache_enabled
            else None
        )
        cache_state = CacheObservationState.NONE
        if self._cache is not None and selected_cache_policy.enabled:
            if provider is not None or use_cache is False:
                cache_state = CacheObservationState.BYPASS
            elif cache_enabled and cache_key is not None:
                cache_state = _cache_observation_state(self._cache.status(cache_key))
        if cache_enabled and provider is None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                result = self._result_from_cache(definition, cached)
                self._record_dataset_observation(
                    definition.name,
                    result.provider,
                    success=True,
                    error_category=None,
                    observed_at=result.captured_at,
                    latency_ms=0.0,
                )
                self._record_quality_result(
                    definition.name,
                    result.provider,
                    result.data,
                    result.provenance,
                    result.captured_at,
                )
                self._record_runtime_observation(
                    definition.name,
                    result.provider,
                    result.captured_at,
                    success=True,
                    cache_state=CacheObservationState.HIT,
                    attempts=(),
                    fallback_occurred=False,
                )
                return result

        specs = self._ordered_specs(definition, provider)
        attempts: list[FetchAttempt] = []
        fetch_started_at: datetime | None = None

        for provider_index, spec in enumerate(specs):
            retry_count = 0
            while True:
                attempt_number = len(attempts) + 1
                started_at = self._capture_time(definition.name, spec.provider_id)
                if fetch_started_at is None:
                    fetch_started_at = started_at
                try:
                    instance = self._resolve_provider(spec.provider_id, spec.provider)
                    route = self._routes.get((definition.name, spec.provider_id))
                    if route is None:
                        data = self._invoke_generic(instance, definition, kwargs)
                    else:
                        data = route(instance, definition, dict(kwargs))
                except Exception as raw_error:
                    error = self._normalize_execution_error(
                        raw_error,
                        definition.name,
                        spec.provider_id,
                    )
                    captured_at = self._attempt_end_time(started_at)
                    attempts.append(
                        FetchAttempt(
                            provider=spec.provider_id,
                            attempt=attempt_number,
                            started_at=started_at,
                            captured_at=captured_at,
                            success=False,
                            error_type=type(error).__name__,
                            error_message=_safe_error_message(error),
                        )
                    )
                    routing_error = _routing_error(error)
                    self._record_provider_observation(
                        definition.name,
                        spec.provider_id,
                        success=False,
                        error_category=type(routing_error).__name__,
                        started_at=started_at,
                        observed_at=captured_at,
                    )
                    if self._policy.should_retry(routing_error, retry_count):
                        retry_count += 1
                        self._policy.wait_before_retry()
                        continue

                    has_next_provider = provider_index + 1 < len(specs)
                    if _is_fail_fast(routing_error):
                        self._record_dataset_observation(
                            definition.name,
                            spec.provider_id,
                            success=False,
                            error_category=type(routing_error).__name__,
                            observed_at=captured_at,
                            latency_ms=_elapsed_ms(fetch_started_at, captured_at),
                        )
                        self._record_failure_diagnostics(
                            definition.name,
                            spec.provider_id,
                            captured_at,
                            cache_state,
                            tuple(attempts),
                            type(routing_error).__name__,
                        )
                        raise error
                    if (
                        has_next_provider
                        and provider is None
                        and self._policy.should_fallback(routing_error)
                    ):
                        break
                    if provider is not None:
                        aggregate = AllProvidersFailed(
                            definition.name,
                            (spec.provider_id,),
                            tuple(attempts),
                            error,
                        )
                        self._record_dataset_observation(
                            definition.name,
                            spec.provider_id,
                            success=False,
                            error_category=type(routing_error).__name__,
                            observed_at=captured_at,
                            latency_ms=_elapsed_ms(fetch_started_at, captured_at),
                        )
                        self._record_failure_diagnostics(
                            definition.name,
                            spec.provider_id,
                            captured_at,
                            cache_state,
                            tuple(attempts),
                            type(routing_error).__name__,
                        )
                        raise aggregate from error
                    if has_next_provider:
                        self._record_dataset_observation(
                            definition.name,
                            spec.provider_id,
                            success=False,
                            error_category=type(routing_error).__name__,
                            observed_at=captured_at,
                            latency_ms=_elapsed_ms(fetch_started_at, captured_at),
                        )
                        self._record_failure_diagnostics(
                            definition.name,
                            spec.provider_id,
                            captured_at,
                            cache_state,
                            tuple(attempts),
                            type(routing_error).__name__,
                        )
                        raise error
                    aggregate = AllProvidersFailed(
                        definition.name,
                        tuple(candidate.provider_id for candidate in specs),
                        tuple(attempts),
                        error,
                    )
                    self._record_dataset_observation(
                        definition.name,
                        spec.provider_id,
                        success=False,
                        error_category=type(routing_error).__name__,
                        observed_at=captured_at,
                        latency_ms=_elapsed_ms(fetch_started_at, captured_at),
                    )
                    self._record_failure_diagnostics(
                        definition.name,
                        spec.provider_id,
                        captured_at,
                        cache_state,
                        tuple(attempts),
                        type(routing_error).__name__,
                    )
                    raise aggregate from error
                else:
                    captured_at = self._capture_time(definition.name, spec.provider_id)
                    attempts.append(
                        FetchAttempt(
                            provider=spec.provider_id,
                            attempt=attempt_number,
                            started_at=started_at,
                            captured_at=captured_at,
                            success=True,
                        )
                    )
                    self._record_provider_observation(
                        definition.name,
                        spec.provider_id,
                        success=True,
                        error_category=None,
                        started_at=started_at,
                        observed_at=captured_at,
                    )
                    result = FetchResult(
                        data=data,
                        dataset=definition,
                        provider=spec.provider_id,
                        captured_at=captured_at,
                        provenance=self._provider_provenance(instance),
                        attempts=tuple(attempts),
                        fallback_used=provider_index > 0,
                    )
                    if cache_enabled:
                        self._cache_result(
                            cache_key,
                            selected_cache_policy,
                            result,
                        )
                    self._record_dataset_observation(
                        definition.name,
                        spec.provider_id,
                        success=True,
                        error_category=None,
                        observed_at=captured_at,
                        latency_ms=_elapsed_ms(fetch_started_at, captured_at),
                    )
                    self._record_quality_result(
                        definition.name,
                        spec.provider_id,
                        result.data,
                        result.provenance,
                        captured_at,
                    )
                    self._record_runtime_observation(
                        definition.name,
                        spec.provider_id,
                        captured_at,
                        success=True,
                        cache_state=cache_state,
                        attempts=result.attempts,
                        fallback_occurred=result.fallback_used,
                    )
                    return result

        raise AssertionError("Collector routing policy produced no Provider candidates")

    @property
    def health(self) -> HealthMonitor:
        """Return the process-local, observational health monitor."""

        return self._health

    @property
    def quality(self) -> QualityMonitor:
        """Return the process-local Dataset quality monitor."""

        return self._quality

    @property
    def observability(self) -> ObservabilityMonitor:
        """Return the process-local runtime/cache observability monitor."""

        return self._observability

    def _record_provider_observation(
        self,
        dataset: str,
        provider: str,
        *,
        success: bool,
        error_category: str | None,
        started_at: datetime,
        observed_at: datetime,
    ) -> None:
        self._record_health(
            HealthObservation(
                kind="provider_attempt",
                dataset=dataset,
                provider=provider,
                outcome="success" if success else "failure",
                error_category=error_category,
                latency_ms=_elapsed_ms(started_at, observed_at),
                observed_at=observed_at,
            )
        )

    def _record_dataset_observation(
        self,
        dataset: str,
        provider: str | None,
        *,
        success: bool,
        error_category: str | None,
        observed_at: datetime,
        latency_ms: float | None,
    ) -> None:
        self._record_health(
            HealthObservation(
                kind="dataset_fetch",
                dataset=dataset,
                provider=provider,
                outcome="success" if success else "failure",
                error_category=error_category,
                latency_ms=latency_ms,
                observed_at=observed_at,
            )
        )

    def _record_health(self, observation: HealthObservation) -> None:
        """Keep auxiliary health failures from changing the fetch contract."""

        try:
            self._health.record(observation)
        except HealthError:
            # HealthMonitor validates all observations before mutation.  A
            # HealthError is reserved for auxiliary failures and is therefore
            # intentionally isolated from Provider/Collector semantics.
            return

    def _record_quality_result(
        self,
        dataset: str,
        provider: str | None,
        data: Any,
        provenance: Iterable[Source],
        observed_at: datetime,
    ) -> None:
        try:
            self._quality.observe_result(
                dataset=dataset,
                provider=provider,
                data=data,
                provenance=provenance,
                observed_at=observed_at,
            )
        except QualityError:
            return

    def _record_failure_diagnostics(
        self,
        dataset: str,
        provider: str,
        observed_at: datetime,
        cache_state: CacheObservationState,
        attempts: tuple[FetchAttempt, ...],
        error_category: str,
    ) -> None:
        if error_category == "SchemaDrift":
            try:
                self._quality.observe_schema_drift(
                    dataset=dataset,
                    provider=provider,
                    observed_at=observed_at,
                )
            except QualityError:
                pass
        self._record_runtime_observation(
            dataset,
            provider,
            observed_at,
            success=False,
            cache_state=cache_state,
            attempts=attempts,
            fallback_occurred=_fallback_occurred(attempts),
            error_category=error_category,
        )

    def _record_runtime_observation(
        self,
        dataset: str,
        provider: str | None,
        observed_at: datetime,
        *,
        success: bool,
        cache_state: CacheObservationState,
        attempts: Iterable[FetchAttempt],
        fallback_occurred: bool,
        error_category: str | None = None,
    ) -> None:
        try:
            self._observability.record_fetch(
                dataset=dataset,
                provider=provider,
                observed_at=observed_at,
                success=success,
                cache_state=cache_state,
                attempts=attempts,
                fallback_occurred=fallback_occurred,
                error_category=error_category,
            )
        except ObservabilityError:
            return

    def _cache_policy_for(self, definition: DatasetDefinition[Any, Any]) -> CachePolicy:
        if isinstance(self._cache_policy, CachePolicy):
            return self._cache_policy
        versioned_name = f"{definition.name}@{definition.schema_version}"
        return self._cache_policy.get(
            versioned_name,
            self._cache_policy.get(definition.name, CachePolicy()),
        )

    @staticmethod
    def _cache_key(
        definition: DatasetDefinition[Any, Any],
        kwargs: Mapping[str, Any],
    ) -> StorageKey:
        return StorageKey.from_dataset(
            definition,
            {"request": _request_identity(definition, kwargs)},
        )

    def _cache_result(
        self,
        key: StorageKey | None,
        cache_policy: CachePolicy,
        result: FetchResult[Any],
    ) -> None:
        if self._cache is None or key is None:
            raise CollectorError("Collector cache write was requested without a cache key")
        metadata = {
            _CACHE_PROVIDER_METADATA: result.provider,
            _CACHE_CAPTURED_AT_METADATA: result.captured_at,
            _CACHE_PROVENANCE_METADATA: result.provenance,
            _CACHE_WARNINGS_METADATA: result.warnings,
            _CACHE_FALLBACK_METADATA: result.fallback_used,
        }
        source = result.provenance[0] if result.provenance else None
        self._cache.put(
            key,
            result.data,
            ttl=cache_policy.ttl,
            source=source,
            metadata=metadata,
        )

    @staticmethod
    def _result_from_cache(
        definition: DatasetDefinition[Any, Any],
        stored: StoredObject[Any],
    ) -> FetchResult[Any]:
        metadata = stored.metadata
        provider = metadata.get(_CACHE_PROVIDER_METADATA)
        if not isinstance(provider, str) or not provider:
            if stored.source is not None:
                provider = stored.source.provider_id
            else:
                raise CollectorError(
                    "cached Collector entry has no reliable original Provider identity"
                )

        raw_provenance = metadata.get(_CACHE_PROVENANCE_METADATA)
        if raw_provenance is None:
            provenance = (stored.source,) if stored.source is not None else ()
        else:
            try:
                provenance = tuple(raw_provenance)
            except TypeError as exc:
                raise CollectorError("cached Collector provenance is invalid") from exc
            if any(not isinstance(source, Source) for source in provenance):
                raise CollectorError("cached Collector provenance is invalid")

        captured_at = metadata.get(_CACHE_CAPTURED_AT_METADATA, stored.stored_at)
        if (
            not isinstance(captured_at, datetime)
            or captured_at.tzinfo is None
            or captured_at.utcoffset() is None
        ):
            raise CollectorError("cached Collector capture time is invalid")

        warnings = metadata.get(_CACHE_WARNINGS_METADATA, ())
        if not isinstance(warnings, (tuple, list)) or any(
            not isinstance(warning, str) for warning in warnings
        ):
            raise CollectorError("cached Collector warnings are invalid")
        fallback_used = metadata.get(_CACHE_FALLBACK_METADATA, False)
        if type(fallback_used) is not bool:
            raise CollectorError("cached Collector fallback metadata is invalid")

        return FetchResult(
            data=stored.data,
            dataset=definition,
            provider=provider,
            captured_at=captured_at,
            warnings=tuple(warnings),
            provenance=provenance,
            attempts=(),
            fallback_used=fallback_used,
            cache_hit=True,
        )

    def _ordered_specs(
        self,
        definition: DatasetDefinition[Any, Any],
        provider: str | None,
    ) -> tuple[ProviderSpec, ...]:
        if provider is not None:
            return (self._select_provider(definition, provider),)

        configured = self._policy.provider_ids_for(definition)
        if configured is None:
            try:
                specs = self._registry.providers_for(definition)
            except KeyError as exc:
                raise UnknownDataset(f"no Provider is registered for {definition.name!r}") from exc
        else:
            specs = tuple(self._select_provider(definition, provider_id) for provider_id in configured)

        if not specs:
            raise UnknownDataset(f"no Provider is registered for {definition.name!r}")
        semantics = self._registry.routing_semantics_for(definition)
        if (
            not self._policy.allow_fallback
            or semantics is DatasetRoutingSemantics.SINGLE_SOURCE
        ):
            return (specs[0],)
        return specs

    def _resolve_dataset(
        self,
        dataset: DatasetDefinition[Any, Any] | str,
    ) -> DatasetDefinition[Any, Any]:
        if isinstance(dataset, DatasetDefinition):
            requested_name = dataset.name
            requested_version = dataset.schema_version
        elif isinstance(dataset, str):
            requested_name, requested_version = self._split_dataset_id(dataset)
        else:
            raise UnknownDataset(f"dataset must be a DatasetDefinition or name, got {type(dataset).__name__}")

        try:
            definition = next(
                item
                for item in self._registry.list_datasets()
                if item.name == requested_name
            )
        except StopIteration as exc:
            raise UnknownDataset(f"unknown dataset: {requested_name!r}") from exc
        if requested_version is not None and requested_version != definition.schema_version:
            raise UnknownDataset(
                f"unknown dataset schema: {requested_name!r} version {requested_version!r}; "
                f"registered version is {definition.schema_version!r}"
            )
        return definition

    @staticmethod
    def _split_dataset_id(value: str) -> tuple[str, str | None]:
        if not value.strip():
            raise UnknownDataset("dataset name must not be empty")
        if "@" not in value:
            return value, None
        name, version = value.rsplit("@", 1)
        if not name or not version:
            raise UnknownDataset(f"invalid dataset identifier: {value!r}")
        return name, version

    def _select_provider(self, definition: DatasetDefinition[Any, Any], provider: str):
        try:
            spec = self._registry.get_provider(provider)
        except KeyError as exc:
            raise UnknownProvider(f"unknown provider: {provider!r}") from exc
        if not spec.supports_dataset(definition):
            raise ProviderDoesNotSupportDataset(
                f"provider {provider!r} does not support dataset {definition.name!r}"
            )
        return spec

    def _resolve_provider(self, provider_id: str, provider_type: type[Any]) -> Any:
        if provider_id in self._provider_instances:
            return self._provider_instances[provider_id]
        try:
            if provider_id in self._provider_factories:
                return self._provider_factories[provider_id]()
            return provider_type()
        except ImportError as exc:
            spec = self._registry.get_provider(provider_id)
            if spec.optional_dependencies:
                dependency = getattr(exc, "name", None) or spec.optional_dependencies[0]
                raise MissingOptionalDependency(
                    ",".join(dataset.name for dataset in spec.supported_datasets),
                    provider_id,
                    dependency,
                ) from exc
            raise

    @staticmethod
    def _invoke_generic(
        instance: Any,
        definition: DatasetDefinition[Any, Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        fetch = getattr(instance, "fetch", None)
        if not callable(fetch):
            raise RuntimeError(
                "Provider has no generic fetch method and no Collector route is registered"
            )
        return fetch(**dict(kwargs))

    def _capture_time(self, dataset: str, provider: str) -> datetime:
        captured_at = self._clock()
        if (
            not isinstance(captured_at, datetime)
            or captured_at.tzinfo is None
            or captured_at.utcoffset() is None
        ):
            raise ProviderExecutionError(
                dataset,
                provider,
                "Collector clock must return a timezone-aware datetime",
            )
        return captured_at

    def _attempt_end_time(self, started_at: datetime) -> datetime:
        try:
            return self._capture_time("attempt", "collector.clock")
        except ProviderExecutionError:
            return started_at

    @staticmethod
    def _normalize_execution_error(
        error: Exception,
        dataset: str,
        provider: str,
    ) -> Exception:
        if isinstance(error, (ProviderError, CollectorError)):
            return error
        if isinstance(error, TimeoutError):
            return _with_cause(Timeout(str(error) or "provider timed out"), error)
        if isinstance(error, (ConnectionError, OSError)):
            return _with_cause(SourceUnavailable(str(error) or "source unavailable"), error)
        return _with_cause(
            ProviderExecutionError(dataset, provider, f"{type(error).__name__}: {error}"),
            error,
        )

    @staticmethod
    def _provider_provenance(instance: Any) -> tuple[Source, ...]:
        source = getattr(instance, "source", None)
        return (source,) if isinstance(source, Source) else ()

    def _install_default_routes(self) -> None:
        for spec in self._registry.list_providers():
            for definition in spec.supported_datasets:
                route = self._default_route(definition, self._clock, spec.provider)
                if route is not None:
                    self._routes[(definition.name, spec.provider_id)] = route

    def _install_routes(
        self,
        routes: Iterable[CollectorRoute]
        | Mapping[tuple[DatasetDefinition[Any, Any] | str, str], RouteHandler]
        | None,
    ) -> None:
        if routes is None:
            return
        if isinstance(routes, Mapping):
            entries = (
                CollectorRoute(dataset=key[0], provider_id=key[1], handler=handler)
                for key, handler in routes.items()
            )
        else:
            entries = iter(routes)
        for route in entries:
            if not isinstance(route, CollectorRoute):
                raise TypeError("routes must contain CollectorRoute values")
            definition = self._resolve_dataset(route.dataset)
            try:
                spec = self._registry.get_provider(route.provider_id)
            except KeyError as exc:
                raise UnknownProvider(f"unknown provider: {route.provider_id!r}") from exc
            if not spec.supports_dataset(definition):
                raise ProviderDoesNotSupportDataset(
                    f"provider {route.provider_id!r} does not support dataset {definition.name!r}"
                )
            self._routes[(definition.name, route.provider_id)] = route.handler

    @staticmethod
    def _default_route(
        definition: DatasetDefinition[Any, Any],
        clock: Callable[[], datetime],
        provider_type: type[Any],
    ) -> RouteHandler | None:
        if definition.name == TRADING_CALENDAR_DATASET.name:
            return _calendar_route
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
            return _request_normalizer_route("fetch_replay", normalize_market_daily_replay)
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
        if definition.name == DISCLOSURE_DOCUMENT_DATASET.name and hasattr(
            provider_type, "fetch_raw_disclosure_page"
        ):
            return _disclosure_search_route
        return None


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


def _is_cache_like(value: Any) -> bool:
    return callable(getattr(value, "get", None)) and callable(getattr(value, "put", None))


def _normalize_cache_policy(
    value: CachePolicy | Mapping[str, CachePolicy] | None,
) -> CachePolicy | Mapping[str, CachePolicy]:
    if value is None or isinstance(value, CachePolicy):
        return value or CachePolicy()
    if not isinstance(value, Mapping):
        raise TypeError("cache_policy must be a CachePolicy or mapping")
    normalized: dict[str, CachePolicy] = {}
    for dataset_id, policy in value.items():
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            raise ValueError("cache policy keys must be non-empty Dataset identities")
        if not isinstance(policy, CachePolicy):
            raise TypeError("cache policy values must be CachePolicy values")
        normalized[dataset_id] = policy
    return MappingProxyType(normalized)


def _has_enabled_cache_policy(
    value: CachePolicy | Mapping[str, CachePolicy],
) -> bool:
    if isinstance(value, CachePolicy):
        return value.enabled
    return any(policy.enabled for policy in value.values())


def _calendar_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.get_calendar(request)
    return _normalize_calendar_rows(request, rows, source=provider.source)


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
        return normalizer(request, raw, source=provider.source)

    return route


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
    return _normalize_klines_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )


def _quote_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
    clock: Callable[[], datetime],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.fetch_quotes(request)
    return _normalize_quote_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )


def _ranking_route(
    provider: Any,
    definition: DatasetDefinition[Any, Any],
    kwargs: Mapping[str, Any],
    clock: Callable[[], datetime],
) -> Any:
    request = _request_for(definition, kwargs)
    rows = provider.fetch_ranking(request)
    return _normalize_ranking_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )


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
    return _normalize_provider_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )


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
    return _normalize_provider_rows(
        request,
        matching_rows,
        source=provider.source,
        captured_at=_route_capture_time(clock),
    )


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

    return NewsService(provider)._search_request(request)


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

    return DisclosureService(provider)._search_request(request)


_NO_GENERIC_OVERRIDE = object()


def _generic_route_override(provider: Any, kwargs: Mapping[str, Any]) -> Any:
    """Keep the generic injection seam available to test doubles."""

    if "request" not in kwargs or len(kwargs) == 1:
        return _NO_GENERIC_OVERRIDE
    fetch = getattr(provider, "fetch", None)
    if not callable(fetch):
        return _NO_GENERIC_OVERRIDE
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


def _elapsed_ms(started_at: datetime | None, observed_at: datetime) -> float:
    """Calculate a deterministic non-negative duration from Collector clocks."""

    if started_at is None:
        return 0.0
    return max(0.0, (observed_at - started_at).total_seconds() * 1000.0)


def _cache_observation_state(state: CacheState) -> CacheObservationState:
    if state is CacheState.FRESH:
        return CacheObservationState.HIT
    if state is CacheState.EXPIRED:
        return CacheObservationState.EXPIRED
    return CacheObservationState.MISS


def _fallback_occurred(attempts: tuple[FetchAttempt, ...]) -> bool:
    providers = {attempt.provider for attempt in attempts}
    return len(providers) > 1


def _matches_error(error: BaseException, error_types: frozenset[ErrorType]) -> bool:
    return any(isinstance(error, error_type) for error_type in error_types)


def _routing_error(error: Exception) -> Exception:
    """Classify legacy ProviderError messages without changing their cause."""

    if not isinstance(error, ProviderError):
        if isinstance(error, TimeoutError):
            return Timeout(str(error))
        if isinstance(error, (ConnectionError, OSError)):
            return SourceUnavailable(str(error))
        return error

    reason = error.reason.casefold()
    if "401" in reason or "403" in reason or "authentication" in reason or "session missing" in reason:
        return AuthenticationError(error.reason)
    if "429" in reason or "rate limit" in reason:
        return RateLimitError(error.reason)
    if "timeout" in reason or "timed out" in reason:
        return Timeout(error.reason)
    if "schema drift" in reason:
        return SchemaDrift(error.reason)
    if "no data" in reason or "no rows" in reason or "empty payload" in reason:
        return NoData(error.reason)
    if "transport failure" in reason or "server error" in reason or "unavailable" in reason:
        return SourceUnavailable(error.reason)
    if "unsupported market" in reason or "request must" in reason:
        return InvalidRequest(error.reason)
    return error


def _is_fail_fast(error: Exception) -> bool:
    return not isinstance(error, (Timeout, RateLimitError, SourceUnavailable, NoData))


def _with_cause(error: Exception, cause: Exception) -> Exception:
    error.__cause__ = cause
    return error


_SENSITIVE_ERROR_VALUE = re.compile(
    r"(?i)(session|token|cookie|authorization|password|secret)(\s*[:=]\s*)[^,;\s]+"
)


def _safe_error_message(error: BaseException) -> str:
    message = _SENSITIVE_ERROR_VALUE.sub(r"\1\2[redacted]", str(error))
    return message[:500]


__all__ = ["Collector", "CollectorRoute", "FetchAttempt", "FetchResult", "RoutingPolicy"]
