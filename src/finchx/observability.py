"""Process-local runtime/cache observability summaries for FinchX."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finchx.collectors.core import FetchAttempt


class ObservabilityError(RuntimeError):
    """Base error for the auxiliary observability subsystem."""


class CacheObservationState(str, Enum):
    """Cache path taken by one Collector fetch."""

    NONE = "none"
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"
    BYPASS = "bypass"


@dataclass(frozen=True)
class RuntimeObservation:
    """One fetch-level runtime summary derived from existing Collector facts."""

    dataset: str
    provider: str | None
    observed_at: datetime
    success: bool
    cache_state: CacheObservationState | str
    attempt_count: int
    retry_occurred: bool
    fallback_occurred: bool
    error_category: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, str) or not self.dataset.strip():
            raise ValueError("dataset must be a non-empty string")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider.strip()
        ):
            raise ValueError("provider must be None or a non-empty string")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if type(self.success) is not bool:
            raise TypeError("success must be a bool")
        if type(self.attempt_count) is not int or self.attempt_count < 0:
            raise ValueError("attempt_count must be a non-negative integer")
        if type(self.retry_occurred) is not bool or type(self.fallback_occurred) is not bool:
            raise TypeError("retry_occurred and fallback_occurred must be bools")
        try:
            state = (
                self.cache_state
                if isinstance(self.cache_state, CacheObservationState)
                else CacheObservationState(self.cache_state)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid cache observation state") from exc
        if self.success and self.error_category is not None:
            raise ValueError("successful runtime observations cannot have an error")
        object.__setattr__(self, "cache_state", state)

    @property
    def cache_hit(self) -> bool:
        return self.cache_state is CacheObservationState.HIT

    @property
    def cache_miss(self) -> bool:
        return self.cache_state is CacheObservationState.MISS

    @property
    def cache_expired(self) -> bool:
        return self.cache_state is CacheObservationState.EXPIRED

    @property
    def cache_bypass(self) -> bool:
        return self.cache_state is CacheObservationState.BYPASS


@dataclass(frozen=True)
class DatasetRuntimeSummary:
    """Aggregated fetch/runtime summary for one Dataset."""

    dataset: str
    fetches: int
    successes: int
    failures: int
    attempts: int
    retries: int
    fallbacks: int
    cache_hits: int
    cache_misses: int
    cache_expired: int
    cache_bypasses: int
    last_observed_at: datetime | None
    last_provider: str | None
    last_error_category: str | None


@dataclass(frozen=True)
class ObservabilitySnapshot:
    """Immutable runtime/cache summary keyed by Dataset."""

    datasets: Mapping[str, DatasetRuntimeSummary]
    fetches: int
    successes: int
    failures: int
    attempts: int
    retries: int
    fallbacks: int
    cache_hits: int
    cache_misses: int
    cache_expired: int
    cache_bypasses: int
    last_observed_at: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "datasets", MappingProxyType(dict(self.datasets)))

    @property
    def runtime(self) -> Mapping[str, DatasetRuntimeSummary]:
        return self.datasets

    def dataset(self, dataset: str) -> DatasetRuntimeSummary | None:
        return self.datasets.get(dataset)


@dataclass
class _MutableRuntime:
    fetches: int = 0
    successes: int = 0
    failures: int = 0
    attempts: int = 0
    retries: int = 0
    fallbacks: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_expired: int = 0
    cache_bypasses: int = 0
    last_observed_at: datetime | None = None
    last_provider: str | None = None
    last_error_category: str | None = None

    def add(self, observation: RuntimeObservation) -> None:
        self.fetches += 1
        self.successes += int(observation.success)
        self.failures += int(not observation.success)
        self.attempts += observation.attempt_count
        self.retries += int(observation.retry_occurred)
        self.fallbacks += int(observation.fallback_occurred)
        self.cache_hits += int(observation.cache_hit)
        self.cache_misses += int(observation.cache_miss)
        self.cache_expired += int(observation.cache_expired)
        self.cache_bypasses += int(observation.cache_bypass)
        self.last_observed_at = observation.observed_at
        self.last_provider = observation.provider
        if not observation.success:
            self.last_error_category = observation.error_category

    def snapshot(self, dataset: str) -> DatasetRuntimeSummary:
        return DatasetRuntimeSummary(
            dataset=dataset,
            fetches=self.fetches,
            successes=self.successes,
            failures=self.failures,
            attempts=self.attempts,
            retries=self.retries,
            fallbacks=self.fallbacks,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            cache_expired=self.cache_expired,
            cache_bypasses=self.cache_bypasses,
            last_observed_at=self.last_observed_at,
            last_provider=self.last_provider,
            last_error_category=self.last_error_category,
        )


class ObservabilityMonitor:
    """In-memory fetch/runtime summary; it does not retain request payloads."""

    def __init__(self) -> None:
        self._observations: list[RuntimeObservation] = []
        self._datasets: dict[str, _MutableRuntime] = {}

    @property
    def observations(self) -> tuple[RuntimeObservation, ...]:
        return tuple(self._observations)

    def record(self, observation: RuntimeObservation) -> None:
        if not isinstance(observation, RuntimeObservation):
            raise TypeError("observation must be a RuntimeObservation")
        self._observations.append(observation)
        self._datasets.setdefault(observation.dataset, _MutableRuntime()).add(observation)

    def record_fetch(
        self,
        *,
        dataset: str,
        provider: str | None,
        observed_at: datetime,
        success: bool,
        cache_state: CacheObservationState | str,
        attempts: Iterable[FetchAttempt] = (),
        fallback_occurred: bool = False,
        error_category: str | None = None,
    ) -> RuntimeObservation:
        from finchx.collectors.core import FetchAttempt

        attempt_values = tuple(attempts)
        if any(not isinstance(attempt, FetchAttempt) for attempt in attempt_values):
            raise TypeError("attempts must contain FetchAttempt values")
        retry_occurred = _retry_occurred(attempt_values)
        observation = RuntimeObservation(
            dataset=dataset,
            provider=provider,
            observed_at=observed_at,
            success=success,
            cache_state=cache_state,
            attempt_count=len(attempt_values),
            retry_occurred=retry_occurred,
            fallback_occurred=fallback_occurred,
            error_category=error_category,
        )
        self.record(observation)
        return observation

    def snapshot(self) -> ObservabilitySnapshot:
        values = list(self._observations)
        return ObservabilitySnapshot(
            datasets={
                dataset: summary.snapshot(dataset)
                for dataset, summary in self._datasets.items()
            },
            fetches=len(values),
            successes=sum(int(item.success) for item in values),
            failures=sum(int(not item.success) for item in values),
            attempts=sum(item.attempt_count for item in values),
            retries=sum(int(item.retry_occurred) for item in values),
            fallbacks=sum(int(item.fallback_occurred) for item in values),
            cache_hits=sum(int(item.cache_hit) for item in values),
            cache_misses=sum(int(item.cache_miss) for item in values),
            cache_expired=sum(int(item.cache_expired) for item in values),
            cache_bypasses=sum(int(item.cache_bypass) for item in values),
            last_observed_at=values[-1].observed_at if values else None,
        )

    def dataset(self, dataset: str) -> DatasetRuntimeSummary | None:
        return self.snapshot().dataset(dataset)


def _retry_occurred(attempts: tuple[FetchAttempt, ...]) -> bool:
    seen: set[str] = set()
    for attempt in attempts:
        if attempt.provider in seen:
            return True
        seen.add(attempt.provider)
    return False


__all__ = [
    "CacheObservationState",
    "DatasetRuntimeSummary",
    "ObservabilityError",
    "ObservabilityMonitor",
    "ObservabilitySnapshot",
    "RuntimeObservation",
]
