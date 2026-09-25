"""Process-local runtime health observations for FinchX.

Health is deliberately observational.  It records Provider attempts and the
final outcome of Dataset fetches, but it never participates in routing,
retry, fallback, or cache decisions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Final


class HealthError(RuntimeError):
    """Base error for the auxiliary health subsystem."""


class ObservationKind(str, Enum):
    """The runtime event represented by one health observation."""

    PROVIDER_ATTEMPT = "provider_attempt"
    DATASET_FETCH = "dataset_fetch"


class ObservationOutcome(str, Enum):
    """The outcome of an observed Provider attempt or Dataset fetch."""

    SUCCESS = "success"
    FAILURE = "failure"


ProviderCapability: Final = tuple[str, str]


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _normalize_enum(value: str | Enum, enum_type: type[Enum], field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(repr(item.value) for item in enum_type)
        raise ValueError(f"{field_name} must be one of {allowed}") from exc


@dataclass(frozen=True)
class HealthObservation:
    """One immutable runtime observation.

    Provider observations are emitted once for every actual Provider call.
    Dataset observations are emitted once for the final public fetch outcome.
    ``provider`` is optional for a Dataset failure that did not reach a
    particular Provider; successful Dataset observations carry the final
    Provider identity.
    """

    kind: ObservationKind | str
    dataset: str
    provider: str | None
    outcome: ObservationOutcome | str
    error_category: str | None = None
    latency_ms: float | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        kind = _normalize_enum(self.kind, ObservationKind, "kind")
        outcome = _normalize_enum(self.outcome, ObservationOutcome, "outcome")
        if not isinstance(self.dataset, str) or not self.dataset.strip():
            raise ValueError("dataset must be a non-empty string")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider.strip()
        ):
            raise ValueError("provider must be None or a non-empty string")
        if kind is ObservationKind.PROVIDER_ATTEMPT and self.provider is None:
            raise ValueError("provider_attempt observations require a provider")
        if outcome is ObservationOutcome.SUCCESS and self.error_category is not None:
            raise ValueError("successful observations cannot contain an error category")
        if self.error_category is not None and (
            not isinstance(self.error_category, str) or not self.error_category.strip()
        ):
            raise ValueError("error_category must be None or a non-empty string")
        if self.latency_ms is not None:
            if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, (int, float)):
                raise TypeError("latency_ms must be a number or None")
            if self.latency_ms < 0:
                raise ValueError("latency_ms must be non-negative")
        if self.observed_at is None:
            raise ValueError("observed_at is required")
        _require_aware_datetime(self.observed_at, "observed_at")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "outcome", outcome)
        if self.latency_ms is not None:
            object.__setattr__(self, "latency_ms", float(self.latency_ms))


@dataclass(frozen=True)
class _HealthStats:
    """Common aggregate fields shared by Provider and Dataset snapshots."""

    attempts: int
    successes: int
    failures: int
    success_rate: float
    last_observed_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error_category: str | None
    avg_latency_ms: float | None
    consecutive_failures: int


@dataclass(frozen=True)
class ProviderHealthSnapshot(_HealthStats):
    """Aggregated health for one Provider + Dataset capability."""

    provider: str
    dataset: str

    @property
    def capability(self) -> ProviderCapability:
        return (self.provider, self.dataset)


@dataclass(frozen=True)
class DatasetHealthSnapshot(_HealthStats):
    """Aggregated health for one public Dataset fetch outcome."""

    dataset: str


@dataclass(frozen=True)
class HealthSnapshot:
    """Immutable runtime health view captured at one point in process memory."""

    provider_health: Mapping[ProviderCapability, ProviderHealthSnapshot]
    dataset_health: Mapping[str, DatasetHealthSnapshot]
    provider_overall: Mapping[str, ProviderHealthSnapshot]

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_health", MappingProxyType(dict(self.provider_health)))
        object.__setattr__(self, "dataset_health", MappingProxyType(dict(self.dataset_health)))
        object.__setattr__(self, "provider_overall", MappingProxyType(dict(self.provider_overall)))

    @property
    def providers(self) -> Mapping[ProviderCapability, ProviderHealthSnapshot]:
        """Alias for capability-level Provider health."""

        return self.provider_health

    @property
    def datasets(self) -> Mapping[str, DatasetHealthSnapshot]:
        """Alias for Dataset-level health."""

        return self.dataset_health

    def provider(
        self,
        provider: str,
        dataset: str | None = None,
    ) -> ProviderHealthSnapshot | None:
        """Return capability-level or overall health for one Provider."""

        if dataset is None:
            return self.provider_overall.get(provider)
        return self.provider_health.get((provider, dataset))

    def dataset(self, dataset: str) -> DatasetHealthSnapshot | None:
        """Return Dataset-level health when it has been observed."""

        return self.dataset_health.get(dataset)


@dataclass
class _MutableStats:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    last_observed_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error_category: str | None = None
    latency_total_ms: float = 0.0
    latency_count: int = 0
    consecutive_failures: int = 0

    def add(self, observation: HealthObservation) -> None:
        self.attempts += 1
        self.last_observed_at = observation.observed_at
        if observation.latency_ms is not None:
            self.latency_total_ms += observation.latency_ms
            self.latency_count += 1
        if observation.outcome is ObservationOutcome.SUCCESS:
            self.successes += 1
            self.last_success_at = observation.observed_at
            self.consecutive_failures = 0
        else:
            self.failures += 1
            self.last_failure_at = observation.observed_at
            self.last_error_category = observation.error_category
            self.consecutive_failures += 1

    def snapshot(self, *, provider: str | None = None, dataset: str) -> _HealthStats:
        success_rate = self.successes / self.attempts if self.attempts else 0.0
        avg_latency = (
            self.latency_total_ms / self.latency_count if self.latency_count else None
        )
        values = dict(
            attempts=self.attempts,
            successes=self.successes,
            failures=self.failures,
            success_rate=success_rate,
            last_observed_at=self.last_observed_at,
            last_success_at=self.last_success_at,
            last_failure_at=self.last_failure_at,
            last_error_category=self.last_error_category,
            avg_latency_ms=avg_latency,
            consecutive_failures=self.consecutive_failures,
        )
        if provider is None:
            return DatasetHealthSnapshot(dataset=dataset, **values)
        return ProviderHealthSnapshot(provider=provider, dataset=dataset, **values)


class HealthMonitor:
    """In-memory health aggregator owned by one Collector runtime."""

    def __init__(self, observations: Iterable[HealthObservation] | None = None) -> None:
        self._observations: list[HealthObservation] = []
        self._provider_stats: dict[ProviderCapability, _MutableStats] = {}
        self._dataset_stats: dict[str, _MutableStats] = {}
        self._provider_overall_stats: dict[str, _MutableStats] = {}
        if observations is not None:
            for observation in observations:
                self.record(observation)

    def record(self, observation: HealthObservation) -> None:
        if not isinstance(observation, HealthObservation):
            raise TypeError("observation must be a HealthObservation")
        self._observations.append(observation)
        if observation.kind is ObservationKind.PROVIDER_ATTEMPT:
            capability = (observation.provider, observation.dataset)
            self._provider_stats.setdefault(capability, _MutableStats()).add(observation)
            self._provider_overall_stats.setdefault(observation.provider, _MutableStats()).add(
                observation
            )
        else:
            self._dataset_stats.setdefault(observation.dataset, _MutableStats()).add(observation)

    @property
    def observations(self) -> tuple[HealthObservation, ...]:
        """Return the immutable observation history for diagnostics and tests."""

        return tuple(self._observations)

    def snapshot(self) -> HealthSnapshot:
        provider_health = {
            capability: stats.snapshot(provider=capability[0], dataset=capability[1])
            for capability, stats in self._provider_stats.items()
        }
        dataset_health = {
            dataset: stats.snapshot(dataset=dataset)
            for dataset, stats in self._dataset_stats.items()
        }
        provider_overall = {
            provider: stats.snapshot(provider=provider, dataset="__overall__")
            for provider, stats in self._provider_overall_stats.items()
        }
        return HealthSnapshot(
            provider_health=provider_health,
            dataset_health=dataset_health,
            provider_overall=provider_overall,
        )

    def provider_health(
        self,
        provider: str,
        dataset: str | None = None,
    ) -> ProviderHealthSnapshot | None:
        """Query current capability-level or overall Provider health."""

        return self.snapshot().provider(provider, dataset)

    def dataset_health(self, dataset: str) -> DatasetHealthSnapshot | None:
        """Query current Dataset-level health."""

        return self.snapshot().dataset(dataset)


__all__ = [
    "DatasetHealthSnapshot",
    "HealthError",
    "HealthMonitor",
    "HealthObservation",
    "HealthSnapshot",
    "ObservationKind",
    "ObservationOutcome",
    "ProviderCapability",
    "ProviderHealthSnapshot",
]
