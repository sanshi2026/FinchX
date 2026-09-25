"""Deterministic single-instrument A-share deviation capability."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from finchx.collectors import FetchResult
from finchx.collectors.errors import InvalidRequest, NoData
from finchx.contracts import Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.market_klines import (
    KlineAdjustment,
    KlinesRequest,
    MarketKlineData,
    MARKET_KLINES_DATASET,
)
from finchx.datasets.trading_calendar import (
    TRADING_CALENDAR_DATASET,
    TradingCalendarRequest,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.health import HealthError, HealthObservation
from finchx.observability import CacheObservationState, ObservabilityError
from finchx.quality import QualityError


DEVIATION_RULE_VERSION = "cn-a-exchange-2026-07-06+finchx-v1"
DEFAULT_DEVIATION_KLINE_PROVIDER = "tencent.finance.qq.klines"
_SHANGHAI = timezone(timedelta(hours=8))


class DeviationWindowConvention(str, Enum):
    """The two explicitly distinguished window interpretations."""

    STRICT_EXCHANGE_WINDOW = "strict_exchange_window"
    MAX_DEVIATION_SCAN = "max_deviation_scan"


@dataclass(frozen=True)
class PricePoint:
    """One validated close/point used by the pure deviation calculator."""

    point_date: date
    close: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.point_date, date) or isinstance(self.point_date, datetime):
            raise TypeError("point_date must be a date")
        if not isinstance(self.close, Decimal) or self.close <= 0:
            raise ValueError("close must be a positive Decimal")


@dataclass(frozen=True)
class BenchmarkSpec:
    """The audited benchmark identity for one equity identity."""

    instrument: InstrumentId
    name: str
    board: str


class DeviationRequest(ContractModel):
    """Computed-capability request metadata, not a Provider request."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    as_of: date | None = Field(default=None, alias="asOf")
    windows: tuple[Literal[10, 30], ...] = (10, 30)
    window_convention: DeviationWindowConvention = Field(
        default=DeviationWindowConvention.MAX_DEVIATION_SCAN,
        alias="windowConvention",
    )

    @field_validator("as_of", mode="before")
    @classmethod
    def as_of_must_be_a_date(cls, value: object) -> object:
        if isinstance(value, datetime):
            raise ValueError("as_of must be a date, not a datetime")
        return value

    @field_validator("windows")
    @classmethod
    def windows_must_be_supported(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value or any(item not in (10, 30) for item in value):
            raise ValueError("windows must contain only 10 and 30")
        if len(set(value)) != len(value):
            raise ValueError("windows must not contain duplicates")
        return value

    @model_validator(mode="after")
    def instrument_must_be_supported(self) -> "DeviationRequest":
        resolve_deviation_benchmark(self.instrument_id, as_of=self.as_of)
        return self


class DeviationWindowData(ContractModel):
    """One close-based deviation observation."""

    window_days: Literal[10, 30] = Field(alias="windowDays")
    window_convention: DeviationWindowConvention = Field(alias="windowConvention")
    trading_sessions: int = Field(alias="tradingSessions", ge=2)
    start_date: date = Field(alias="startDate")
    baseline_date: date = Field(alias="baselineDate")
    end_date: date = Field(alias="endDate")
    start_price: Decimal = Field(alias="startPrice", gt=0)
    window_start_price: Decimal = Field(alias="windowStartPrice", gt=0)
    current_price: Decimal = Field(alias="currentPrice", gt=0)
    benchmark_instrument: InstrumentId = Field(alias="benchmarkInstrument")
    benchmark_name: str = Field(alias="benchmarkName", min_length=1)
    benchmark_start: Decimal = Field(alias="benchmarkStart", gt=0)
    benchmark_current: Decimal = Field(alias="benchmarkCurrent", gt=0)
    stock_return: Decimal = Field(alias="stockReturn")
    benchmark_return: Decimal = Field(alias="benchmarkReturn")
    deviation: Decimal
    upper_threshold: Decimal = Field(alias="upperThreshold")
    lower_threshold: Decimal = Field(alias="lowerThreshold")
    remaining_to_upper: Decimal = Field(alias="remainingToUpper")
    remaining_to_lower: Decimal = Field(alias="remainingToLower")
    upper_trigger_price: Decimal = Field(alias="upperTriggerPrice", gt=0)
    lower_trigger_price: Decimal = Field(alias="lowerTriggerPrice", gt=0)
    remaining_price_pct_to_upper: Decimal = Field(alias="remainingPricePctToUpper")
    remaining_price_pct_to_lower: Decimal = Field(alias="remainingPricePctToLower")


class DeviationData(ContractModel):
    """Public computed result returned inside FetchResult."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    board: str = Field(min_length=1)
    effective_as_of: date = Field(alias="effectiveAsOf")
    calculation_mode: Literal["official_close"] = Field(alias="calculationMode")
    price_basis: Literal["qfq_stock__raw_index"] = Field(alias="priceBasis")
    rule_version: str = Field(alias="ruleVersion", min_length=1)
    windows: tuple[DeviationWindowData, ...]


COMPUTED_DEVIATION_DATASET: DatasetDefinition[DeviationRequest, DeviationData] = DatasetDefinition(
    name="market.deviation",
    schema_version="1.0",
    request_type=DeviationRequest,
    data_type=DeviationData,
)


def resolve_deviation_benchmark(
    instrument: InstrumentId,
    *,
    as_of: date | None = None,
) -> BenchmarkSpec:
    """Resolve the audited benchmark from the complete InstrumentId."""

    if not isinstance(instrument, InstrumentId):
        raise InvalidRequest("market.deviation requires an InstrumentId")
    if as_of is not None and (
        not isinstance(as_of, date) or isinstance(as_of, datetime)
    ):
        raise InvalidRequest("market.deviation as_of must be a date")
    if instrument.market is not Market.CN_A:
        raise InvalidRequest("market.deviation supports only Market.CN_A")
    if instrument.kind is not InstrumentKind.EQUITY:
        raise InvalidRequest("market.deviation supports equity InstrumentId values only")
    if instrument.exchange is Exchange.BSE:
        raise InvalidRequest("market.deviation does not support BSE in v1")
    if instrument.exchange is Exchange.SSE:
        if instrument.code.startswith("68"):
            return BenchmarkSpec(
                InstrumentId(
                    code="000688",
                    market=Market.CN_A,
                    kind=InstrumentKind.INDEX,
                    exchange=Exchange.SSE,
                ),
                "SSE STAR 50 Index",
                "star",
            )
        if instrument.code.startswith("60"):
            return BenchmarkSpec(
                InstrumentId(
                    code="000002",
                    market=Market.CN_A,
                    kind=InstrumentKind.INDEX,
                    exchange=Exchange.SSE,
                ),
                "SSE A Share Index",
                "sse_main_board",
            )
        raise InvalidRequest("unsupported SSE equity code for market.deviation")
    if instrument.exchange is Exchange.SZSE:
        if instrument.code.startswith("30"):
            return BenchmarkSpec(
                InstrumentId(
                    code="399102",
                    market=Market.CN_A,
                    kind=InstrumentKind.INDEX,
                    exchange=Exchange.SZSE,
                ),
                "ChiNext Composite Index",
                "chinext",
            )
        if instrument.code.startswith("00"):
            return BenchmarkSpec(
                InstrumentId(
                    code="399107",
                    market=Market.CN_A,
                    kind=InstrumentKind.INDEX,
                    exchange=Exchange.SZSE,
                ),
                "SZSE A Share Index",
                "szse_main_board",
            )
        raise InvalidRequest("unsupported SZSE equity code for market.deviation")
    raise InvalidRequest("market.deviation requires an explicit SSE or SZSE exchange")


def calculate_deviation(
    stock_prices: Sequence[PricePoint],
    benchmark_prices: Sequence[PricePoint],
    *,
    instrument: InstrumentId,
    benchmark: BenchmarkSpec,
    window_days: Literal[10, 30],
    end_date: date,
    window_convention: DeviationWindowConvention = DeviationWindowConvention.MAX_DEVIATION_SCAN,
) -> DeviationWindowData:
    """Calculate one window without network, storage, Provider, or global state."""

    if window_days not in (10, 30):
        raise InvalidRequest("window_days must be 10 or 30")
    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise InvalidRequest("end_date must be a date")
    convention = _coerce_window_convention(window_convention)
    stock = _price_map(stock_prices, "stock")
    index = _price_map(benchmark_prices, "benchmark")
    common_dates = sorted(
        point_date
        for point_date in set(stock).intersection(index)
        if point_date <= end_date
    )
    if len(common_dates) < window_days + 1:
        raise NoData(
            f"market.deviation requires at least {window_days + 1} aligned price points"
        )
    window_dates = common_dates[-(window_days + 1) :]
    if window_dates[-1] != end_date:
        raise NoData("market.deviation end_date has no aligned stock and benchmark prices")

    if convention is DeviationWindowConvention.STRICT_EXCHANGE_WINDOW:
        candidate_indices = (1,)
    else:
        candidate_indices = tuple(range(1, len(window_dates) - 1))
    if not candidate_indices:
        raise NoData("market.deviation has no eligible start date")

    candidates: list[tuple[Decimal, int, Decimal, Decimal, Decimal, Decimal]] = []
    for index_in_window in candidate_indices:
        baseline = window_dates[index_in_window - 1]
        end = window_dates[-1]
        base_stock = stock[baseline].close
        base_index = index[baseline].close
        current_stock = stock[end].close
        current_index = index[end].close
        stock_return = current_stock / base_stock - Decimal("1")
        benchmark_return = current_index / base_index - Decimal("1")
        candidates.append(
            (
                stock_return - benchmark_return,
                index_in_window,
                stock_return,
                benchmark_return,
                base_stock,
                base_index,
            )
        )
    deviation, chosen_index, stock_return, benchmark_return, start_price, benchmark_start = max(
        candidates,
        key=lambda item: (item[0], -item[1]),
    )
    baseline_date = window_dates[chosen_index - 1]
    start_date = window_dates[chosen_index]
    end = window_dates[-1]
    current_price = stock[end].close
    benchmark_current = index[end].close
    upper_threshold, lower_threshold = (
        (Decimal("1.00"), Decimal("-0.50"))
        if window_days == 10
        else (Decimal("2.00"), Decimal("-0.70"))
    )
    upper_trigger = start_price * (Decimal("1") + upper_threshold + benchmark_return)
    lower_trigger = start_price * (Decimal("1") + lower_threshold + benchmark_return)
    if upper_trigger <= 0 or lower_trigger <= 0:
        raise NoData("market.deviation produced a non-positive trigger price")
    return DeviationWindowData(
        windowDays=window_days,
        windowConvention=convention,
        tradingSessions=len(window_dates) - chosen_index,
        startDate=start_date,
        baselineDate=baseline_date,
        endDate=end,
        startPrice=start_price,
        windowStartPrice=stock[start_date].close,
        currentPrice=current_price,
        benchmarkInstrument=benchmark.instrument,
        benchmarkName=benchmark.name,
        benchmarkStart=benchmark_start,
        benchmarkCurrent=benchmark_current,
        stockReturn=stock_return,
        benchmarkReturn=benchmark_return,
        deviation=deviation,
        upperThreshold=upper_threshold,
        lowerThreshold=lower_threshold,
        remainingToUpper=upper_threshold - deviation,
        remainingToLower=deviation - lower_threshold,
        upperTriggerPrice=upper_trigger,
        lowerTriggerPrice=lower_trigger,
        remainingPricePctToUpper=upper_trigger / current_price - Decimal("1"),
        remainingPricePctToLower=lower_trigger / current_price - Decimal("1"),
    )


class DeviationService:
    """Small computed seam over existing Collector-backed capabilities."""

    def __init__(self, collector: Any, *, clock: Any | None = None) -> None:
        if not callable(getattr(collector, "fetch", None)):
            raise TypeError("collector must provide a callable fetch method")
        self._collector = collector
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def calculate(
        self,
        instrument_id: InstrumentId,
        *,
        windows: Sequence[int] = (10, 30),
        as_of: date | None = None,
        window_convention: DeviationWindowConvention = DeviationWindowConvention.MAX_DEVIATION_SCAN,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[DeviationData]:
        request = DeviationRequest(
            instrumentId=instrument_id,
            asOf=as_of,
            windows=tuple(windows),
            windowConvention=window_convention,
        )
        benchmark = resolve_deviation_benchmark(request.instrument_id, as_of=request.as_of)
        requested_as_of = request.as_of or self._today()
        cutoff = self._completed_cutoff(requested_as_of)
        calendar_result = self._collector.fetch(
            TRADING_CALENDAR_DATASET,
            request=TradingCalendarRequest(
                market=Market.CN_A,
                startDate=cutoff - timedelta(days=180),
                endDate=cutoff,
            ),
            use_cache=use_cache,
        )
        sessions = _calendar_sessions(calendar_result.data, cutoff)
        maximum_window = max(request.windows)
        if len(sessions) < maximum_window + 1:
            raise NoData(
                f"market.deviation requires {maximum_window + 1} completed trading sessions"
            )
        required_sessions = sessions[-(maximum_window + 1) :]
        baseline_date = required_sessions[0]
        end_date = required_sessions[-1]
        kline_provider = provider or DEFAULT_DEVIATION_KLINE_PROVIDER
        stock_result = self._collector.fetch(
            MARKET_KLINES_DATASET,
            provider=kline_provider,
            use_cache=use_cache,
            request=KlinesRequest(
                instrumentId=request.instrument_id,
                startDate=baseline_date,
                endDate=end_date,
                adjustment=KlineAdjustment.QFQ,
            ),
        )
        benchmark_result = self._collector.fetch(
            MARKET_KLINES_DATASET,
            provider=kline_provider,
            use_cache=use_cache,
            request=KlinesRequest(
                instrumentId=benchmark.instrument,
                startDate=baseline_date,
                endDate=end_date,
            ),
        )
        stock_points = _kline_points(stock_result.data, request.instrument_id)
        benchmark_points = _kline_points(benchmark_result.data, benchmark.instrument)
        required = set(required_sessions)
        if not required.issubset(stock_points) or not required.issubset(benchmark_points):
            raise NoData("market.deviation has missing aligned stock or benchmark closes")
        data = DeviationData(
            instrumentId=request.instrument_id,
            board=benchmark.board,
            effectiveAsOf=end_date,
            calculationMode="official_close",
            priceBasis="qfq_stock__raw_index",
            ruleVersion=DEVIATION_RULE_VERSION,
            windows=tuple(
                calculate_deviation(
                    tuple(stock_points[point_date] for point_date in required_sessions),
                    tuple(benchmark_points[point_date] for point_date in required_sessions),
                    instrument=request.instrument_id,
                    benchmark=benchmark,
                    window_days=window,
                    end_date=end_date,
                    window_convention=request.window_convention,
                )
                for window in request.windows
            ),
        )
        provenance = _merge_provenance(
            calendar_result.provenance,
            stock_result.provenance,
            benchmark_result.provenance,
        )
        captured_at = max(
            calendar_result.captured_at,
            stock_result.captured_at,
            benchmark_result.captured_at,
        )
        result = FetchResult(
            data=data,
            dataset=COMPUTED_DEVIATION_DATASET,
            provider=None,
            captured_at=captured_at,
            provenance=provenance,
        )
        self._record_success(result)
        return result

    def _today(self) -> date:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("deviation clock must return an aware datetime")
        return now.astimezone(_SHANGHAI).date()

    def _completed_cutoff(self, requested_as_of: date) -> date:
        today = self._today()
        if requested_as_of >= today:
            return today - timedelta(days=1)
        return requested_as_of

    def _record_success(self, result: FetchResult[DeviationData]) -> None:
        dataset = result.dataset.name
        captured_at = result.captured_at
        health = getattr(self._collector, "health", None)
        if health is not None:
            try:
                health.record(
                    HealthObservation(
                        kind="dataset_fetch",
                        dataset=dataset,
                        provider=None,
                        outcome="success",
                        observed_at=captured_at,
                    )
                )
            except HealthError:
                pass
        quality = getattr(self._collector, "quality", None)
        if quality is not None:
            try:
                quality.observe_result(
                    dataset=dataset,
                    provider=None,
                    data=result.data,
                    provenance=result.provenance,
                    observed_at=captured_at,
                )
            except QualityError:
                pass
        observability = getattr(self._collector, "observability", None)
        if observability is not None:
            try:
                observability.record_fetch(
                    dataset=dataset,
                    provider=None,
                    observed_at=captured_at,
                    success=True,
                    cache_state=CacheObservationState.NONE,
                )
            except ObservabilityError:
                pass


def _coerce_window_convention(value: DeviationWindowConvention | str) -> DeviationWindowConvention:
    try:
        return value if isinstance(value, DeviationWindowConvention) else DeviationWindowConvention(value)
    except (TypeError, ValueError) as exc:
        raise InvalidRequest("unknown market.deviation window convention") from exc


def _price_map(points: Iterable[PricePoint], label: str) -> dict[date, PricePoint]:
    result: dict[date, PricePoint] = {}
    for point in points:
        if not isinstance(point, PricePoint):
            raise InvalidRequest(f"{label} prices must contain PricePoint values")
        if point.point_date in result:
            raise InvalidRequest(f"{label} prices contain duplicate dates")
        result[point.point_date] = point
    return result


def _calendar_sessions(data: Iterable[StandardRecord], cutoff: date) -> tuple[date, ...]:
    sessions: list[date] = []
    for record in data:
        if not isinstance(record, StandardRecord):
            raise NoData("trading_calendar returned an invalid record")
        raw_date = record.data.get("date")
        if not isinstance(raw_date, str):
            raise NoData("trading_calendar returned a record without a date")
        try:
            session_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise NoData("trading_calendar returned an invalid date") from exc
        if record.data.get("isTradingDay") is True and session_date <= cutoff:
            sessions.append(session_date)
    return tuple(sorted(set(sessions)))


def _kline_points(data: Iterable[StandardRecord], expected: InstrumentId) -> dict[date, PricePoint]:
    points: dict[date, PricePoint] = {}
    for record in data:
        if not isinstance(record, StandardRecord):
            raise NoData("market.klines returned an invalid record")
        try:
            bar = MarketKlineData.model_validate(record.data)
        except Exception as exc:
            raise NoData("market.klines returned an invalid bar") from exc
        if bar.instrument_id != expected:
            raise NoData("market.klines returned a mismatched instrument")
        if bar.bar_date in points:
            raise NoData("market.klines returned duplicate dates")
        points[bar.bar_date] = PricePoint(bar.bar_date, bar.close)
    return points


def _merge_provenance(*groups: Iterable[Source]) -> tuple[Source, ...]:
    merged: list[Source] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for group in groups:
        for source in group:
            key = (
                source.provider_id,
                source.source_record_id,
                str(source.source_url) if source.source_url else None,
            )
            if key not in seen:
                seen.add(key)
                merged.append(source)
    return tuple(merged)


__all__ = [
    "BenchmarkSpec",
    "COMPUTED_DEVIATION_DATASET",
    "DEFAULT_DEVIATION_KLINE_PROVIDER",
    "DEVIATION_RULE_VERSION",
    "DeviationData",
    "DeviationRequest",
    "DeviationService",
    "DeviationWindowConvention",
    "DeviationWindowData",
    "PricePoint",
    "calculate_deviation",
    "resolve_deviation_benchmark",
]
