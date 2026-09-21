"""Small, conservative Dataset quality observations for FinchX.

Quality describes the data returned by a successful fetch.  It is separate
from runtime Health and never participates in routing, retry, fallback, or
cache decisions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Callable

from pydantic import BaseModel

from finchx.contracts import Source


class QualityError(RuntimeError):
    """Base error for the auxiliary quality subsystem."""


class QualityIssueKind(str, Enum):
    """Conservative, cross-Dataset quality issue vocabulary."""

    NO_DATA = "no_data"
    STALE = "stale"
    MISSING_PROVENANCE = "missing_provenance"
    SCHEMA_DRIFT = "schema_drift"


class QualityStatus(str, Enum):
    """Assessment status; it is not a health score or routing state."""

    OK = "ok"
    NO_DATA = "no_data"
    STALE = "stale"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class FreshnessStatus(str, Enum):
    """Whether freshness could be assessed under an explicit policy."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FreshnessPolicy:
    """One explicit maximum-age policy for a Dataset.

    No default Dataset thresholds are installed.  Callers must opt into a
    policy when a stable freshness expectation is known.
    """

    max_age: float | timedelta

    def __post_init__(self) -> None:
        if isinstance(self.max_age, timedelta):
            seconds = self.max_age.total_seconds()
        elif isinstance(self.max_age, (int, float)) and not isinstance(self.max_age, bool):
            seconds = float(self.max_age)
        else:
            raise TypeError("max_age must be seconds or timedelta")
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("max_age must be finite and non-negative")

    @property
    def max_age_seconds(self) -> float:
        if isinstance(self.max_age, timedelta):
            return self.max_age.total_seconds()
        return float(self.max_age)


@dataclass(frozen=True)
class QualityIssue:
    """One non-mutating quality diagnostic attached to an observation."""

    kind: QualityIssueKind | str
    detail: str | None = None

    def __post_init__(self) -> None:
        try:
            normalized = (
                self.kind
                if isinstance(self.kind, QualityIssueKind)
                else QualityIssueKind(self.kind)
            )
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(repr(item.value) for item in QualityIssueKind)
            raise ValueError(f"kind must be one of {allowed}") from exc
        if self.detail is not None and (
            not isinstance(self.detail, str) or not self.detail.strip()
        ):
            raise ValueError("detail must be None or a non-empty string")
        object.__setattr__(self, "kind", normalized)


@dataclass(frozen=True)
class QualityObservation:
    """One Dataset-result quality assessment."""

    dataset: str
    provider: str | None
    observed_at: datetime
    has_data: bool | None
    record_count: int | None
    data_timestamp: datetime | None
    freshness_status: FreshnessStatus | str
    freshness_age_seconds: float | None
    provenance_complete: bool | None
    structural_complete: bool | None
    issues: tuple[QualityIssue, ...] = ()
    status: QualityStatus | str = QualityStatus.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, str) or not self.dataset.strip():
            raise ValueError("dataset must be a non-empty string")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider.strip()
        ):
            raise ValueError("provider must be None or a non-empty string")
        _require_aware(self.observed_at, "observed_at")
        if self.has_data is not None and type(self.has_data) is not bool:
            raise TypeError("has_data must be bool or None")
        if self.record_count is not None and (
            type(self.record_count) is not int or self.record_count < 0
        ):
            raise ValueError("record_count must be a non-negative integer or None")
        if self.data_timestamp is not None:
            _require_aware(self.data_timestamp, "data_timestamp")
        try:
            freshness_status = (
                self.freshness_status
                if isinstance(self.freshness_status, FreshnessStatus)
                else FreshnessStatus(self.freshness_status)
            )
            status = (
                self.status
                if isinstance(self.status, QualityStatus)
                else QualityStatus(self.status)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid quality status") from exc
        if self.freshness_age_seconds is not None:
            if isinstance(self.freshness_age_seconds, bool) or not isinstance(
                self.freshness_age_seconds, (int, float)
            ):
                raise TypeError("freshness_age_seconds must be a number or None")
            if not math.isfinite(float(self.freshness_age_seconds)) or self.freshness_age_seconds < 0:
                raise ValueError("freshness_age_seconds must be finite and non-negative")
        for name, value in (
            ("provenance_complete", self.provenance_complete),
            ("structural_complete", self.structural_complete),
        ):
            if value is not None and type(value) is not bool:
                raise TypeError(f"{name} must be bool or None")
        normalized_issues = tuple(self.issues)
        if any(not isinstance(issue, QualityIssue) for issue in normalized_issues):
            raise TypeError("issues must contain QualityIssue values")
        object.__setattr__(self, "freshness_status", freshness_status)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "issues", normalized_issues)
        if self.freshness_age_seconds is not None:
            object.__setattr__(self, "freshness_age_seconds", float(self.freshness_age_seconds))

    @property
    def freshness_timestamp(self) -> datetime | None:
        """Alias using the established wording for the data timestamp."""

        return self.data_timestamp

    @property
    def item_count(self) -> int | None:
        """Alias for callers that use item rather than record terminology."""

        return self.record_count


@dataclass(frozen=True)
class DatasetQualitySnapshot:
    """Aggregated quality summary for one Dataset."""

    dataset: str
    observations: int
    with_data: int
    without_data: int
    stale: int
    missing_provenance: int
    schema_drift: int
    last_observed_at: datetime | None
    last_status: QualityStatus | None
    latest: QualityObservation | None

    @property
    def no_data(self) -> int:
        return self.without_data


@dataclass(frozen=True)
class QualitySnapshot:
    """Immutable in-memory quality view keyed by Dataset."""

    datasets: Mapping[str, DatasetQualitySnapshot]

    def __post_init__(self) -> None:
        object.__setattr__(self, "datasets", MappingProxyType(dict(self.datasets)))

    @property
    def quality(self) -> Mapping[str, DatasetQualitySnapshot]:
        return self.datasets

    def dataset(self, dataset: str) -> DatasetQualitySnapshot | None:
        return self.datasets.get(dataset)


@dataclass
class _MutableDatasetQuality:
    observations: int = 0
    with_data: int = 0
    without_data: int = 0
    stale: int = 0
    missing_provenance: int = 0
    schema_drift: int = 0
    last_observed_at: datetime | None = None
    last_status: QualityStatus | None = None
    latest: QualityObservation | None = None

    def add(self, observation: QualityObservation) -> None:
        self.observations += 1
        if observation.has_data is True:
            self.with_data += 1
        elif observation.has_data is False:
            self.without_data += 1
        kinds = {issue.kind for issue in observation.issues}
        if QualityIssueKind.STALE in kinds:
            self.stale += 1
        if QualityIssueKind.MISSING_PROVENANCE in kinds:
            self.missing_provenance += 1
        if QualityIssueKind.SCHEMA_DRIFT in kinds:
            self.schema_drift += 1
        self.last_observed_at = observation.observed_at
        self.last_status = observation.status
        self.latest = observation

    def snapshot(self, dataset: str) -> DatasetQualitySnapshot:
        return DatasetQualitySnapshot(
            dataset=dataset,
            observations=self.observations,
            with_data=self.with_data,
            without_data=self.without_data,
            stale=self.stale,
            missing_provenance=self.missing_provenance,
            schema_drift=self.schema_drift,
            last_observed_at=self.last_observed_at,
            last_status=self.last_status,
            latest=self.latest,
        )


class QualityMonitor:
    """Process-local quality assessment and aggregation."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        freshness_policies: Mapping[str, FreshnessPolicy | float | timedelta] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if not callable(self._clock):
            raise TypeError("clock must be callable")
        normalized: dict[str, FreshnessPolicy] = {}
        for dataset, policy in (freshness_policies or {}).items():
            if not isinstance(dataset, str) or not dataset.strip():
                raise ValueError("freshness policy dataset names must be non-empty strings")
            normalized[dataset] = (
                policy if isinstance(policy, FreshnessPolicy) else FreshnessPolicy(policy)
            )
        self._freshness_policies = MappingProxyType(normalized)
        self._observations: list[QualityObservation] = []
        self._datasets: dict[str, _MutableDatasetQuality] = {}

    @property
    def observations(self) -> tuple[QualityObservation, ...]:
        return tuple(self._observations)

    def observe_result(
        self,
        *,
        dataset: str,
        provider: str | None,
        data: Any,
        provenance: Iterable[Source] = (),
        observed_at: datetime | None = None,
        structural_complete: bool = True,
    ) -> QualityObservation:
        assessment_time = self._assessment_time(observed_at)
        has_data, record_count = _data_summary(data)
        data_timestamp = _extract_data_timestamp(data, assessment_time.tzinfo)
        provenance_values = tuple(provenance)
        provenance_complete = bool(provenance_values) and all(
            isinstance(source, Source) and bool(source.provider_id)
            for source in provenance_values
        )
        issues: list[QualityIssue] = []
        if has_data is False:
            issues.append(QualityIssue(QualityIssueKind.NO_DATA, "successful result contains no items"))
        if not provenance_complete:
            issues.append(
                QualityIssue(
                    QualityIssueKind.MISSING_PROVENANCE,
                    "successful result has no complete direct Provider provenance",
                )
            )
        freshness_status, age_seconds = self._assess_freshness(
            dataset,
            data_timestamp,
            assessment_time,
        )
        if freshness_status is FreshnessStatus.STALE:
            issues.append(QualityIssue(QualityIssueKind.STALE, "data exceeds the explicit freshness policy"))
        return self._record(
            QualityObservation(
                dataset=dataset,
                provider=provider,
                observed_at=assessment_time,
                has_data=has_data,
                record_count=record_count,
                data_timestamp=data_timestamp,
                freshness_status=freshness_status,
                freshness_age_seconds=age_seconds,
                provenance_complete=provenance_complete,
                structural_complete=structural_complete,
                issues=tuple(issues),
                status=_quality_status(issues, freshness_status),
            )
        )

    def observe_schema_drift(
        self,
        *,
        dataset: str,
        provider: str | None,
        observed_at: datetime,
    ) -> QualityObservation:
        return self._record(
            QualityObservation(
                dataset=dataset,
                provider=provider,
                observed_at=observed_at,
                has_data=None,
                record_count=None,
                data_timestamp=None,
                freshness_status=FreshnessStatus.UNKNOWN,
                freshness_age_seconds=None,
                provenance_complete=None,
                structural_complete=False,
                issues=(QualityIssue(QualityIssueKind.SCHEMA_DRIFT, "Provider schema drift"),),
                status=QualityStatus.DEGRADED,
            )
        )

    def record(self, observation: QualityObservation) -> None:
        self._record(observation)

    def snapshot(self) -> QualitySnapshot:
        return QualitySnapshot(
            datasets={
                dataset: summary.snapshot(dataset)
                for dataset, summary in self._datasets.items()
            }
        )

    def dataset(self, dataset: str) -> DatasetQualitySnapshot | None:
        return self.snapshot().dataset(dataset)

    def _record(self, observation: QualityObservation) -> QualityObservation:
        if not isinstance(observation, QualityObservation):
            raise TypeError("observation must be a QualityObservation")
        self._observations.append(observation)
        self._datasets.setdefault(observation.dataset, _MutableDatasetQuality()).add(observation)
        return observation

    def _assessment_time(self, observed_at: datetime | None) -> datetime:
        value = self._clock() if observed_at is None else observed_at
        _require_aware(value, "assessment timestamp")
        return value

    def _assess_freshness(
        self,
        dataset: str,
        data_timestamp: datetime | None,
        assessment_time: datetime,
    ) -> tuple[FreshnessStatus, float | None]:
        if data_timestamp is None:
            return FreshnessStatus.UNKNOWN, None
        age_seconds = max(0.0, (assessment_time - data_timestamp).total_seconds())
        policy = self._freshness_policies.get(dataset)
        if policy is None:
            return FreshnessStatus.UNKNOWN, age_seconds
        status = (
            FreshnessStatus.STALE
            if age_seconds > policy.max_age_seconds
            else FreshnessStatus.FRESH
        )
        return status, age_seconds


def _require_aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _data_summary(data: Any) -> tuple[bool, int | None]:
    if data is None:
        return False, 0
    if isinstance(data, (str, bytes, bytearray)):
        return bool(data), None
    if isinstance(data, (Sequence, Set)):
        return bool(data), len(data)
    if isinstance(data, Mapping):
        return bool(data), None
    if isinstance(data, BaseModel):
        dumped = data.model_dump(mode="python", by_alias=False)
        payload = dumped.get("data") if isinstance(dumped, Mapping) else None
        if isinstance(payload, Mapping) and payload.get("keywords") == []:
            return False, 0
        return True, 1
    return True, None


_DATA_TIMESTAMP_KEYS = frozenset(
    {
        "observed_at",
        "observedAt",
        "published_at",
        "publishedAt",
        "trade_date",
        "tradeDate",
        "report_date",
        "reportDate",
        "effective_at",
        "effectiveAt",
        "event_at",
        "eventAt",
        "updated_at",
        "updatedAt",
        "as_of",
        "asOf",
        "captured_at",
        "capturedAt",
    }
)


def _extract_data_timestamp(data: Any, tzinfo: Any) -> datetime | None:
    candidates: list[datetime] = []

    def visit(value: Any) -> None:
        if isinstance(value, BaseModel):
            visit(value.model_dump(mode="python", by_alias=False))
            return
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key in _DATA_TIMESTAMP_KEYS:
                    timestamp = _timestamp_value(item, tzinfo)
                    if timestamp is not None:
                        candidates.append(timestamp)
                visit(item)
            return
        if isinstance(value, (Sequence, Set)) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for item in value:
                visit(item)

    visit(data)
    return max(candidates) if candidates else None


def _timestamp_value(value: Any, tzinfo: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=tzinfo)
    return None


def _quality_status(
    issues: Iterable[QualityIssue],
    freshness_status: FreshnessStatus,
) -> QualityStatus:
    kinds = {issue.kind for issue in issues}
    if QualityIssueKind.SCHEMA_DRIFT in kinds or QualityIssueKind.MISSING_PROVENANCE in kinds:
        return QualityStatus.DEGRADED
    if QualityIssueKind.STALE in kinds:
        return QualityStatus.STALE
    if QualityIssueKind.NO_DATA in kinds:
        return QualityStatus.NO_DATA
    if freshness_status is FreshnessStatus.UNKNOWN:
        return QualityStatus.UNKNOWN
    return QualityStatus.OK


__all__ = [
    "DatasetQualitySnapshot",
    "FreshnessPolicy",
    "FreshnessStatus",
    "QualityError",
    "QualityIssue",
    "QualityIssueKind",
    "QualityMonitor",
    "QualityObservation",
    "QualitySnapshot",
    "QualityStatus",
]
