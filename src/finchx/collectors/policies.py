"""Routing/cache policies and safe error classification."""

from __future__ import annotations

from collections.abc import (
    Callable,
    Mapping,
)
from dataclasses import (
    dataclass,
    field,
)
from datetime import (
    timedelta,
)
import math
from numbers import (
    Real,
)
import re
from time import (
    sleep,
)
from types import (
    MappingProxyType,
)
from typing import (
    Any,
)
from finchx.datasets.definition import (
    DatasetDefinition,
)
from finchx.providers.errors import (
    ProviderError,
)
from finchx.providers.registry import (
    ProviderSpec,
)
from finchx.collectors.errors import (
    AuthenticationError,
    InvalidRequest,
    NoData,
    RateLimitError,
    SchemaDrift,
    SourceUnavailable,
    Timeout,
)


ErrorType = type[BaseException]


_DEFAULT_RETRYABLE_ERRORS = frozenset({Timeout, RateLimitError, SourceUnavailable})


_DEFAULT_FALLBACK_ERRORS = frozenset(
    {Timeout, RateLimitError, SourceUnavailable, NoData}
)


@dataclass(frozen=True)
class RoutingPolicy:
    """Small runtime policy for Provider order, retry, and fallback behavior."""

    provider_order: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    max_retries: int = 1
    retryable_errors: frozenset[ErrorType] = _DEFAULT_RETRYABLE_ERRORS
    fallback_errors: frozenset[ErrorType] = _DEFAULT_FALLBACK_ERRORS
    allow_fallback: bool = True
    retry_delay_seconds: float = 0.25
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


def _matches_error(error: BaseException, error_types: frozenset[ErrorType]) -> bool:
    return any(isinstance(error, error_type) for error_type in error_types)


def _provider_supports_request(spec: ProviderSpec, request: Any) -> bool:
    """Apply optional request-level Provider capabilities before any I/O."""

    if request is None:
        return True
    supports_request = getattr(spec.provider, "supports_request", None)
    if not callable(supports_request):
        return True
    return bool(supports_request(request))


def _routing_error(error: Exception) -> Exception:
    """Classify legacy ProviderError messages without changing their cause."""

    if not isinstance(error, ProviderError):
        if isinstance(error, TimeoutError):
            return Timeout(str(error))
        if isinstance(error, (ConnectionError, OSError)):
            return SourceUnavailable(str(error))
        return error

    stage = getattr(error, "stage", None)
    category = getattr(error, "category", None)
    retryable = getattr(error, "retryable", None)
    if stage is not None and category is not None:
        if category == "insufficient_history":
            return NoData(error.reason)
        if category == "invalid_request":
            return InvalidRequest(error.reason)
        if category == "schema":
            return SchemaDrift(error.reason)
        if category == "transient_http" and retryable:
            if "HTTP 429" in error.reason:
                return RateLimitError(error.reason)
            return SourceUnavailable(error.reason)
        if category == "timeout" and retryable:
            return Timeout(error.reason)
        if stage == "transport" and retryable:
            return SourceUnavailable(error.reason)
        if category in {"dns_resolution", "connection", "tls_failure", "transport_error"}:
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

# Keep historical public class identities for callers and pickles.
RoutingPolicy.__module__ = "finchx.collectors.core"
CachePolicy.__module__ = "finchx.collectors.core"
