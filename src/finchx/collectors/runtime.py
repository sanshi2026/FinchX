"""Collector execution, cache boundary and diagnostic observations."""

from __future__ import annotations

from collections.abc import (
    Callable,
    Iterable,
    Mapping,
)
from datetime import (
    datetime,
    timezone,
)
from types import (
    MappingProxyType,
)
from typing import (
    Any,
)
from finchx.contracts import (
    Source,
)
from finchx.datasets.definition import (
    DatasetDefinition,
)
from finchx.providers.errors import (
    ProviderError,
)
from finchx.providers.registry import (
    PROVIDER_REGISTRY,
    DatasetRoutingSemantics,
    ProviderRegistry,
    ProviderSpec,
)
from finchx.health import (
    HealthError,
    HealthMonitor,
    HealthObservation,
)
from finchx.observability import (
    CacheObservationState,
    ObservabilityError,
    ObservabilityMonitor,
)
from finchx.quality import (
    QualityError,
    QualityMonitor,
)
from finchx.storage import (
    Cache,
    CacheState,
    StorageKey,
    StoredObject,
)
from finchx.collectors.errors import (
    AllProvidersFailed,
    CollectorError,
    InvalidRequest,
    MissingOptionalDependency,
    ProviderDoesNotSupportDataset,
    ProviderExecutionError,
    SourceUnavailable,
    Timeout,
    UnknownDataset,
    UnknownProvider,
)
from finchx.collectors.policies import (
    CachePolicy,
    RoutingPolicy,
    _has_enabled_cache_policy,
    _is_cache_like,
    _is_fail_fast,
    _normalize_cache_policy,
    _provider_supports_request,
    _routing_error,
    _safe_error_message,
    _with_cause,
)
from finchx.collectors.results import (
    FetchAttempt,
    FetchResult,
    _RouteResult,
    _thaw_json_metadata,
)
from finchx.collectors.routing import (
    CollectorRoute,
    RouteHandler,
    _request_identity,
    default_route,
)


ProviderFactory = Callable[[], Any]


_CACHE_PROVIDER_METADATA = "__finchx_collector_provider__"


_CACHE_CAPTURED_AT_METADATA = "__finchx_collector_captured_at__"


_CACHE_PROVENANCE_METADATA = "__finchx_collector_provenance__"


_CACHE_WARNINGS_METADATA = "__finchx_collector_warnings__"


_CACHE_FALLBACK_METADATA = "__finchx_collector_fallback_used__"


_CACHE_RESULT_METADATA = "__finchx_collector_result_metadata__"


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

        specs = self._ordered_specs(
            definition,
            provider,
            request=kwargs.get("request"),
        )
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
                    route_warnings = ()
                    route_metadata: Mapping[str, Any] = {}
                    if route is None:
                        data = self._invoke_generic(instance, definition, kwargs)
                    else:
                        routed = route(instance, definition, dict(kwargs))
                        if isinstance(routed, _RouteResult):
                            data = routed.data
                            route_warnings = routed.warnings
                            route_metadata = routed.metadata
                        else:
                            data = routed
                            route_warnings = ()
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
                    if (
                        not getattr(error, "retry_budget_exhausted", False)
                        and self._policy.should_retry(routing_error, retry_count)
                    ):
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
                        warnings=route_warnings,
                        provenance=self._provider_provenance(instance),
                        attempts=tuple(attempts),
                        fallback_used=provider_index > 0,
                        metadata=route_metadata,
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
            _CACHE_RESULT_METADATA: _thaw_json_metadata(result.metadata),
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
        result_metadata = metadata.get(_CACHE_RESULT_METADATA, {})
        if not isinstance(result_metadata, Mapping):
            raise CollectorError("cached Collector result metadata is invalid")

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
            metadata=result_metadata,
        )

    def _ordered_specs(
        self,
        definition: DatasetDefinition[Any, Any],
        provider: str | None,
        *,
        request: Any = None,
    ) -> tuple[ProviderSpec, ...]:
        if provider is not None:
            spec = self._select_provider(definition, provider)
            if not _provider_supports_request(spec, request):
                raise InvalidRequest(
                    f"provider {provider!r} does not support this request for {definition.name!r}"
                )
            return (spec,)

        configured = self._policy.provider_ids_for(definition)
        if configured is None:
            try:
                specs = tuple(
                    spec
                    for spec in self._registry.providers_for(definition)
                    if spec.auto_selectable
                )
            except KeyError as exc:
                raise UnknownDataset(f"no Provider is registered for {definition.name!r}") from exc
        else:
            specs = tuple(self._select_provider(definition, provider_id) for provider_id in configured)

        specs = tuple(spec for spec in specs if _provider_supports_request(spec, request))

        if not specs:
            raise InvalidRequest(
                f"no Provider supports this request for {definition.name!r}"
            )
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

    _default_route = staticmethod(default_route)


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

# Keep historical public class identities for callers and pickles.
Collector.__module__ = "finchx.collectors.core"
