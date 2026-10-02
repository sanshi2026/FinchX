"""Deterministic single-instrument A-share deviation capability."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from typing import Any, Literal, TypeAlias

from pydantic import Field, PrivateAttr, field_validator, model_validator

from finchx.collectors import FetchResult
from finchx.collectors.errors import InvalidRequest, NoData
from finchx.contracts import DataStatus, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.market_klines import (
    KlineAdjustment,
    KlinesRequest,
    MarketKlineData,
    MARKET_KLINES_DATASET,
)
from finchx.datasets.market_quote_snapshot import MARKET_QUOTE_SNAPSHOT_DATASET
from finchx.datasets.market_quote_snapshot import (
    MarketQuoteSnapshotData,
    MarketQuoteSnapshotRequest,
)
from finchx.datasets.trading_calendar import (
    TRADING_CALENDAR_DATASET,
    TradingCalendarRequest,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.health import HealthError, HealthObservation
from finchx.observability import CacheObservationState, ObservabilityError
from finchx.quality import QualityError


DEVIATION_RULE_VERSION = "cn-a-exchange-2026-07-06+finchx-v2-scenarios-1"
DEFAULT_DEVIATION_KLINE_PROVIDER = "tencent.finance.qq.klines"
_SHANGHAI = timezone(timedelta(hours=8))


DeviationScenario: TypeAlias = Literal["pre_open", "current", "next_session"]

DeviationCoverageStatus: TypeAlias = Literal[
    "complete",
    "short_history",
    "halt_inferred_from_missing_kline",
    "short_history_and_halt_inferred_from_missing_kline",
]
DeviationWindowStatus: TypeAlias = Literal[
    "complete",
    "partial_short_history",
    "partial_after_inferred_halt",
    "partial_short_history_and_inferred_halt",
]


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


@dataclass(frozen=True)
class _DeviationCandidate:
    deviation: Decimal
    candidate_index: int
    start_date: date
    stock_baseline_date: date
    benchmark_baseline_date: date
    stock_return: Decimal
    benchmark_return: Decimal
    stock_start: Decimal
    benchmark_start: Decimal


class DeviationRequest(ContractModel):
    """Computed-capability request metadata, not a Provider request."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    as_of: date | None = Field(
        default=None,
        alias="asOf",
        description="Observation trading date; historical dates use that session's closes.",
    )
    windows: tuple[Literal[10, 30], ...] = Field(
        default=(10, 30), description="Requested window lengths in trading sessions."
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
    """One scenario-specific deviation observation."""

    _upper_trigger_basis: dict[str, Any] = PrivateAttr(default_factory=dict)

    window_days: Literal[10, 30] = Field(alias="windowDays", description="Requested target window length; 10 or 30 trading sessions.")
    scenario: DeviationScenario = Field(description="pre_open uses the prior close; current uses the observation-date price; next_session rolls the candidate boundary forward one session.")
    trading_sessions: int = Field(alias="tradingSessions", ge=1, description="Observed statistic sessions in the selected maximum-deviation interval; the baseline price point is excluded.")
    available_trading_sessions: int = Field(alias="availableTradingSessions", ge=1, description="Observed statistic sessions available in this scenario, excluding the baseline and any unobserved target session.")
    window_status: DeviationWindowStatus = Field(alias="windowStatus", description="Whether the available observations form the requested window or a supported partial window.")
    coverage_status: DeviationCoverageStatus = Field(alias="coverageStatus", description="Historical coverage and inferred-stock-gap summary for this row.")
    start_date: date = Field(alias="startDate", description="First statistic session in the interval selected for maximum deviation; not the earliest candidate boundary.")
    baseline_date: date = Field(alias="baselineDate", description="Compatibility date for the stock return baseline; equal to stockBaselineDate.")
    stock_baseline_date: date = Field(alias="stockBaselineDate", description="Date of the stock price used as the return baseline.")
    benchmark_baseline_date: date = Field(alias="benchmarkBaselineDate", description="Date of the index point used as the return baseline; it may differ from the stock baseline after an inferred halt.")
    end_date: date = Field(alias="endDate", description="Date of the stock and benchmark terminal prices used in this row.")
    target_date: date = Field(alias="targetDate", description="Trading date that defines the candidate-window boundary; for next_session this is a future calendar date with no price data read.")
    inferred_halt_dates: tuple[date, ...] = Field(alias="inferredHaltDates", description="Missing stock Kline dates inferred as a gap between observed stock bars; index gaps are never inferred as halts.")
    stock_baseline_price: Decimal = Field(alias="stockBaselinePrice", gt=0, description="Stock return baseline in CNY per share, on the priceBasis reported by DeviationData.")
    window_start_price: Decimal = Field(alias="windowStartPrice", gt=0, description="Stock price at startDate in CNY per share; distinct from the preceding baseline price.")
    current_price: Decimal = Field(alias="currentPrice", gt=0, description="Terminal stock price in CNY per share, using the source and date selected for this scenario.")
    benchmark_instrument: InstrumentId = Field(alias="benchmarkInstrument", description="Full identity of the board-specific benchmark index.")
    benchmark_name: str = Field(alias="benchmarkName", min_length=1, description="Human-readable name of the board-specific benchmark index.")
    benchmark_start: Decimal = Field(alias="benchmarkStart", gt=0, description="Benchmark baseline in index points; retained under its existing field name.")
    benchmark_current: Decimal = Field(alias="benchmarkCurrent", gt=0, description="Terminal benchmark value in index points, on endDate.")
    stock_return: Decimal = Field(alias="stockReturn", description="Stock return ratio from stockBaselinePrice to currentPrice; 0.03 means 3%.")
    benchmark_return: Decimal = Field(alias="benchmarkReturn", description="Benchmark return ratio from benchmarkStart to benchmarkCurrent; 0.03 means 3%.")
    deviation: Decimal = Field(description="stockReturn minus benchmarkReturn for the candidate interval with the greatest deviation; negative values are preserved.")
    upper_threshold: Decimal = Field(alias="upperThreshold", description="Fixed upper threshold ratio: 1.00 for 10 sessions or 2.00 for 30 sessions.")
    remaining_to_upper: Decimal = Field(alias="remainingToUpper", description="Rounded upperTriggerPrice divided by currentPrice minus 1; negative values are preserved.")
    upper_trigger_price: Decimal = Field(alias="upperTriggerPrice", gt=0, description="Minimum theoretical stock price across eligible candidates, rounded up to CNY 0.01 after selection; CNY per share.")
    upper_trigger_price_original: Decimal = Field(alias="upperTriggerPrice_original", gt=0, description="Unrounded theoretical price for the selected minimum-price candidate; CNY per share.")
    stock_source_timestamp: datetime | None = Field(default=None, alias="stockSourceTimestamp", description="Source-reported timestamp for a stock quote terminal; null when the terminal comes from a daily bar.")
    benchmark_source_timestamp: datetime | None = Field(
        default=None, alias="benchmarkSourceTimestamp", description="Source-reported timestamp for a benchmark quote terminal; null when the terminal comes from a daily bar."
    )


class DeviationCoverageError(NoData):
    """Structured diagnosis when required deviation input is unavailable."""

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        benchmark_instrument: InstrumentId,
        requested_as_of: date | None,
        effective_as_of: date,
        requested_windows: tuple[int, ...],
        required_start_date: date,
        required_end_date: date,
        required_count: int,
        observed_stock_count: int,
        observed_benchmark_count: int,
        missing_stock_dates: tuple[date, ...],
        missing_benchmark_dates: tuple[date, ...],
        reason_code: str,
    ) -> None:
        self.reason_code = reason_code
        self.instrument_id = instrument_id
        self.benchmark_instrument = benchmark_instrument
        self.requested_as_of = requested_as_of
        self.effective_as_of = effective_as_of
        self.requested_windows = requested_windows
        self.required_start_date = required_start_date
        self.required_end_date = required_end_date
        self.required_count = required_count
        self.observed_stock_count = observed_stock_count
        self.observed_benchmark_count = observed_benchmark_count
        self.missing_stock_dates = missing_stock_dates
        self.missing_benchmark_dates = missing_benchmark_dates

        requested_text = requested_as_of.isoformat() if requested_as_of else "latest"
        stock_missing_text = ",".join(day.isoformat() for day in missing_stock_dates) or "none"
        benchmark_missing_text = (
            ",".join(day.isoformat() for day in missing_benchmark_dates) or "none"
        )
        failure_summary = (
            "market.deviation has missing aligned stock or benchmark closes"
            if reason_code == "missing_benchmark_closes"
            else "market.deviation cannot calculate because required input is unavailable"
        )
        super().__init__(
            f"{failure_summary}; "
            f"instrument={instrument_id}, benchmark={benchmark_instrument}, "
            f"reason_code={reason_code}, "
            f"requested_as_of={requested_text}, effective_as_of={effective_as_of.isoformat()}, "
            f"requested_windows={requested_windows}, "
            f"required_window={required_start_date.isoformat()}..{required_end_date.isoformat()}, "
            f"required_count={required_count}, "
            f"stock_observed_count={observed_stock_count}, "
            f"stock_missing_dates=[{stock_missing_text}], "
            f"benchmark_observed_count={observed_benchmark_count}, "
            f"benchmark_missing_dates=[{benchmark_missing_text}]"
        )


class DeviationData(ContractModel):
    """Public computed result returned inside FetchResult."""

    instrument_id: InstrumentId = Field(alias="instrumentId", description="Full identity of the requested A-share equity.")
    board: str = Field(min_length=1, description="Resolved board used to select the benchmark index.")
    as_of: date = Field(alias="asOf", description="Normalized observation trading date shared by the scenario rows.")
    effective_as_of: date = Field(
        alias="effectiveAsOf",
        description="Legacy alias retained for migration; it matches asOf and is not a shared window end date.",
    )
    calculation_mode: Literal["scenario_based"] = Field(
        alias="calculationMode",
        description="Legacy summary label retained for migration; each window's scenario determines its price source.",
    )
    price_basis: Literal["qfq_stock__raw_index", "raw_stock__raw_index"] = Field(
        alias="priceBasis",
        description=(
            "Reports the actual stock Kline adjustment and raw index points: qfq_stock__raw_index "
            "when the provider returns QFQ bars, or raw_stock__raw_index when it falls back to "
            "unadjusted day bars. A stock quote bridges QFQ history by previousClose only for QFQ "
            "bars; raw stock history and quotes stay on their source price scale."
        ),
    )
    rule_version: str = Field(alias="ruleVersion", min_length=1, description="Identifier for the frozen deviation threshold and scenario algorithm.")
    coverage_status: DeviationCoverageStatus = Field(alias="coverageStatus", description="Aggregate historical coverage summary across the requested scenario rows.")
    inferred_halt_dates: tuple[date, ...] = Field(alias="inferredHaltDates", description="Union of stock-gap dates inferred by the requested rows.")
    windows: tuple[DeviationWindowData, ...] = Field(description="Flat records ordered by requested window and then pre_open, current, next_session.")


COMPUTED_DEVIATION_DATASET: DatasetDefinition[DeviationRequest, DeviationData] = DatasetDefinition(
    name="market.deviation",
    schema_version="2.0",
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
        raise InvalidRequest("market.deviation does not support BSE equities")
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
    scenario: DeviationScenario = "current",
    target_date: date | None = None,
    stock_source_timestamp: datetime | None = None,
    benchmark_source_timestamp: datetime | None = None,
) -> DeviationWindowData:
    """Calculate one scenario without network, storage, Provider, or global state."""

    if window_days not in (10, 30):
        raise InvalidRequest("window_days must be 10 or 30")
    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise InvalidRequest("end_date must be a date")
    if scenario not in ("pre_open", "current", "next_session"):
        raise InvalidRequest("scenario must be pre_open, current, or next_session")
    target_date = end_date if target_date is None else target_date
    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise InvalidRequest("target_date must be a date")
    stock = _price_map(stock_prices, "stock")
    index = _price_map(benchmark_prices, "benchmark")
    common_dates = sorted(
        point_date
        for point_date in set(stock).intersection(index)
        if point_date <= end_date
    )
    if len(common_dates) < 2:
        raise NoData("market.deviation requires at least two aligned price points")
    required_points = window_days if scenario == "next_session" else window_days + 1
    complete = len(common_dates) >= required_points
    window_dates = common_dates[-required_points:] if complete else common_dates
    if window_dates[-1] != end_date:
        raise NoData("market.deviation end_date has no aligned stock and benchmark prices")

    candidate_stop = len(window_dates) if scenario == "next_session" else len(window_dates) - 1
    candidate_indices = tuple(range(1, candidate_stop))
    if not candidate_indices and len(window_dates) == 2:
        # The v2 short-listing rule permits one observed return from two closes.
        candidate_indices = (1,)
    if not candidate_indices:
        raise NoData("market.deviation has no eligible start date")

    candidates: list[_DeviationCandidate] = []
    for index_in_window in candidate_indices:
        baseline = window_dates[index_in_window - 1]
        base_stock = stock[baseline].close
        base_index = index[baseline].close
        current_stock = stock[end_date].close
        current_index = index[end_date].close
        stock_return = current_stock / base_stock - Decimal("1")
        benchmark_return = current_index / base_index - Decimal("1")
        candidates.append(_DeviationCandidate(
            deviation=stock_return - benchmark_return,
            candidate_index=index_in_window,
            start_date=window_dates[index_in_window],
            stock_baseline_date=baseline,
            benchmark_baseline_date=baseline,
            stock_return=stock_return,
            benchmark_return=benchmark_return,
            stock_start=base_stock,
            benchmark_start=base_index,
        ))
    chosen = max(candidates, key=lambda item: (item.deviation, -item.candidate_index))
    upper_threshold = _upper_threshold(window_days)
    upper_basis = min(
        candidates,
        key=lambda item: (
            item.stock_start * (Decimal("1") + upper_threshold + item.benchmark_return),
            item.candidate_index,
        )
    )
    unrounded_upper_trigger = upper_basis.stock_start * (
        Decimal("1") + upper_threshold + upper_basis.benchmark_return
    )
    upper_trigger = _round_trigger_price_up(unrounded_upper_trigger)
    if upper_trigger <= 0:
        raise NoData("market.deviation produced a non-positive trigger price")
    current_price = stock[end_date].close
    result = DeviationWindowData(
        windowDays=window_days,
        scenario=scenario,
        tradingSessions=len(window_dates) - chosen.candidate_index,
        availableTradingSessions=min(
            window_days - 1 if scenario == "next_session" else window_days,
            len(window_dates) - 1,
        ),
        windowStatus="complete" if complete else "partial_short_history",
        coverageStatus="complete" if complete else "short_history",
        startDate=chosen.start_date,
        baselineDate=chosen.stock_baseline_date,
        stockBaselineDate=chosen.stock_baseline_date,
        benchmarkBaselineDate=chosen.benchmark_baseline_date,
        endDate=end_date,
        targetDate=target_date,
        inferredHaltDates=(),
        stockBaselinePrice=chosen.stock_start,
        windowStartPrice=stock[chosen.start_date].close,
        currentPrice=current_price,
        benchmarkInstrument=benchmark.instrument,
        benchmarkName=benchmark.name,
        benchmarkStart=chosen.benchmark_start,
        benchmarkCurrent=index[end_date].close,
        stockReturn=chosen.stock_return,
        benchmarkReturn=chosen.benchmark_return,
        deviation=chosen.deviation,
        upperThreshold=upper_threshold,
        remainingToUpper=upper_trigger / current_price - Decimal("1"),
        upperTriggerPrice=upper_trigger,
        upperTriggerPrice_original=unrounded_upper_trigger,
        stockSourceTimestamp=stock_source_timestamp,
        benchmarkSourceTimestamp=benchmark_source_timestamp,
    )
    result._upper_trigger_basis = {
        "stock_baseline_date": upper_basis.stock_baseline_date.isoformat(),
        "benchmark_baseline_date": upper_basis.benchmark_baseline_date.isoformat(),
        "stock_baseline_price": str(upper_basis.stock_start),
        "benchmark_start": str(upper_basis.benchmark_start),
        "benchmark_return": str(upper_basis.benchmark_return),
        "candidate_start_date": upper_basis.start_date.isoformat(),
        "unrounded_trigger_price": str(unrounded_upper_trigger),
    }
    return result


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
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[DeviationData]:
        request = DeviationRequest(instrumentId=instrument_id, asOf=as_of, windows=tuple(windows))
        benchmark = resolve_deviation_benchmark(request.instrument_id, as_of=request.as_of)
        now = self._now_shanghai()
        requested_as_of = request.as_of or now.date()
        if requested_as_of > now.date():
            raise InvalidRequest("market.deviation as_of cannot be in the future")
        calendar_result = self._collector.fetch(
            TRADING_CALENDAR_DATASET,
            request=TradingCalendarRequest(
                market=Market.CN_A,
                startDate=requested_as_of - timedelta(days=180),
                endDate=requested_as_of + timedelta(days=14),
            ),
            use_cache=use_cache,
        )
        calendar_sessions = _calendar_sessions(calendar_result.data)
        prior_sessions = tuple(day for day in calendar_sessions if day <= requested_as_of)
        if not prior_sessions:
            raise NoData("market.deviation has no trading session on or before as_of")
        observation_date = prior_sessions[-1]
        next_sessions = tuple(day for day in calendar_sessions if day > observation_date)
        if not next_sessions:
            raise NoData("market.deviation trading calendar has no next session")
        next_session = next_sessions[0]
        pre_sessions = tuple(day for day in prior_sessions if day < observation_date)
        if not pre_sessions:
            raise NoData("market.deviation requires a prior trading session for pre_open")
        pre_open_date = pre_sessions[-1]

        observation_sessions = tuple(day for day in prior_sessions if day <= observation_date)
        history_start_date = calendar_sessions[0]
        use_live_quote = observation_date == now.date()
        if len(observation_sessions) < 2:
            raise NoData(
                "market.deviation requires at least two trading sessions in the calendar"
            )
        kline_provider = provider or DEFAULT_DEVIATION_KLINE_PROVIDER
        stock_result = self._collector.fetch(
            MARKET_KLINES_DATASET,
            provider=kline_provider,
            use_cache=False if use_live_quote else use_cache,
            request=KlinesRequest(
                instrumentId=request.instrument_id,
                startDate=history_start_date,
                endDate=observation_date,
                adjustment=KlineAdjustment.QFQ,
            ),
        )
        stock_rows = tuple(stock_result.data)
        stock_adjustment = _stock_kline_adjustment(
            stock_rows,
            stock_result.metadata,
        )
        benchmark_result = self._collector.fetch(
            MARKET_KLINES_DATASET,
            provider=kline_provider,
            use_cache=False if use_live_quote else use_cache,
            request=KlinesRequest(
                instrumentId=benchmark.instrument,
                startDate=history_start_date,
                endDate=observation_date,
            ),
        )
        stock_points = _kline_points(stock_rows, request.instrument_id)
        benchmark_points = _kline_points(benchmark_result.data, benchmark.instrument)
        pre_open_stock_points = {
            day: point for day, point in stock_points.items() if day <= pre_open_date
        }
        pre_open_benchmark_points = {
            day: point for day, point in benchmark_points.items() if day <= pre_open_date
        }
        warnings: list[str] = list(stock_result.warnings)
        adjustment_warning = stock_result.metadata.get("adjustment_warning")
        if stock_adjustment is KlineAdjustment.NONE:
            if not isinstance(adjustment_warning, str) or not adjustment_warning.strip():
                adjustment_warning = (
                    "market.deviation stock Klines use unadjusted day prices; "
                    "the result is not forward-adjusted."
                )
            if adjustment_warning not in warnings:
                warnings.append(adjustment_warning)
        else:
            adjustment_warning = None
        stock_quote: MarketQuoteSnapshotData | None = None
        benchmark_quote: MarketQuoteSnapshotData | None = None
        live_stock_points = dict(stock_points)
        live_benchmark_points = dict(benchmark_points)
        qfq_bridge_ratio: Decimal | None = None
        qfq_bridge_date: date | None = None
        after_close = now.time().replace(tzinfo=None) >= time(15, 0)
        use_stock_quote = use_live_quote and (
            not after_close or observation_date not in stock_points
        )
        use_benchmark_quote = use_live_quote and (
            not after_close or observation_date not in benchmark_points
        )
        stock_quote_result = None
        benchmark_quote_result = None
        if use_live_quote:
            if use_stock_quote:
                stock_quote_result = self._collector.fetch(
                    MARKET_QUOTE_SNAPSHOT_DATASET,
                    use_cache=False,
                    request=MarketQuoteSnapshotRequest(instrumentId=request.instrument_id),
                )
                stock_quote = _quote_snapshot_data(
                    stock_quote_result.data, request.instrument_id, observation_date, now,
                    stock_quote_result.captured_at,
                )
                if stock_adjustment is KlineAdjustment.QFQ:
                    live_stock_points, qfq_bridge_ratio, qfq_bridge_date = _bridge_qfq_stock_history(
                        stock_points,
                        stock_quote,
                        observation_date,
                    )
                else:
                    live_stock_points = dict(stock_points)
                live_stock_points[observation_date] = PricePoint(
                    observation_date, stock_quote.price
                )
            if use_benchmark_quote:
                benchmark_quote_result = self._collector.fetch(
                    MARKET_QUOTE_SNAPSHOT_DATASET,
                    use_cache=False,
                    request=MarketQuoteSnapshotRequest(instrumentId=benchmark.instrument),
                )
                benchmark_quote = _quote_snapshot_data(
                    benchmark_quote_result.data, benchmark.instrument, observation_date, now,
                    benchmark_quote_result.captured_at,
                )
                live_benchmark_points[observation_date] = PricePoint(
                    observation_date, benchmark_quote.price
                )
            if after_close:
                fallback_sides = tuple(
                    label
                    for label, quote in (
                        ("stock", stock_quote),
                        ("benchmark index", benchmark_quote),
                    )
                    if quote is not None
                )
                if fallback_sides:
                    warnings.append(
                        "market.deviation current and next_session use same-day "
                        f"quote fallback for {' and '.join(fallback_sides)} on "
                        f"{observation_date.isoformat()} because those daily bars are unavailable; "
                        "the quote terminal values are not cross-checked against daily bars"
                    )

        windows_data: list[DeviationWindowData] = []
        inferred_halt_dates: set[date] = set()
        saw_short_history = False
        saw_inferred_halt = False
        window_metadata: list[dict[str, Any]] = []
        for window in request.windows:
            for scenario in ("pre_open", "current", "next_session"):
                end_date = pre_open_date if scenario == "pre_open" else observation_date
                target_date = (
                    pre_open_date
                    if scenario == "pre_open"
                    else next_session
                    if scenario == "next_session"
                    else observation_date
                )
                end_sessions = tuple(day for day in observation_sessions if day <= end_date)
                required_count = window if scenario == "next_session" else window + 1
                window_sessions = end_sessions[-required_count:]
                scenario_sessions = tuple(day for day in observation_sessions if day <= end_date)
                candidate_start_boundary = (
                    window_sessions[1] if len(window_sessions) > 1 else window_sessions[0]
                )
                result_window, window_warnings = _calculate_window_from_history(
                    instrument=request.instrument_id,
                    benchmark=benchmark,
                    window_days=window,
                    scenario=scenario,
                    end_date=end_date,
                    target_date=target_date,
                    all_sessions=scenario_sessions,
                    window_sessions=window_sessions,
                    candidate_start_boundary=candidate_start_boundary,
                    stock_points=(
                        pre_open_stock_points if scenario == "pre_open" else live_stock_points
                    ),
                    benchmark_points=(
                        pre_open_benchmark_points
                        if scenario == "pre_open"
                        else live_benchmark_points
                    ),
                    requested_as_of=request.as_of,
                    requested_windows=request.windows,
                    stock_source_timestamp=(
                        stock_quote.source_timestamp if scenario != "pre_open" and stock_quote else None
                    ),
                    benchmark_source_timestamp=(
                        benchmark_quote.source_timestamp
                        if scenario != "pre_open" and benchmark_quote else None
                    ),
                )
                windows_data.append(result_window)
                warnings.extend(window_warnings)
                inferred_halt_dates.update(result_window.inferred_halt_dates)
                saw_short_history = saw_short_history or result_window.coverage_status in {
                    "short_history",
                    "short_history_and_halt_inferred_from_missing_kline",
                }
                saw_inferred_halt = saw_inferred_halt or result_window.coverage_status in {
                    "halt_inferred_from_missing_kline",
                    "short_history_and_halt_inferred_from_missing_kline",
                }
                window_metadata.append(
                    {
                        "window_days": result_window.window_days,
                        "scenario": result_window.scenario,
                        "target_date": result_window.target_date.isoformat(),
                        "trading_sessions": result_window.trading_sessions,
                        "available_trading_sessions": result_window.available_trading_sessions,
                        "window_status": result_window.window_status,
                        "coverage_status": result_window.coverage_status,
                        "stock_baseline_date": result_window.stock_baseline_date.isoformat(),
                        "benchmark_baseline_date": result_window.benchmark_baseline_date.isoformat(),
                        "upper_trigger_basis": dict(result_window._upper_trigger_basis),
                        "inferred_halt_dates": [
                            day.isoformat() for day in result_window.inferred_halt_dates
                        ],
                    }
                )
        if saw_short_history and saw_inferred_halt:
            coverage_status: DeviationCoverageStatus = (
                "short_history_and_halt_inferred_from_missing_kline"
            )
        elif saw_inferred_halt:
            coverage_status = "halt_inferred_from_missing_kline"
        elif saw_short_history:
            coverage_status = "short_history"
        else:
            coverage_status = "complete"
        data = DeviationData(
            instrumentId=request.instrument_id,
            board=benchmark.board,
            asOf=observation_date,
            effectiveAsOf=observation_date,
            calculationMode="scenario_based",
            priceBasis=(
                "qfq_stock__raw_index"
                if stock_adjustment is KlineAdjustment.QFQ
                else "raw_stock__raw_index"
            ),
            ruleVersion=DEVIATION_RULE_VERSION,
            coverageStatus=coverage_status,
            inferredHaltDates=tuple(sorted(inferred_halt_dates)),
            windows=tuple(windows_data),
        )
        provenance = _merge_provenance(
            calendar_result.provenance,
            stock_result.provenance,
            benchmark_result.provenance,
            stock_quote_result.provenance if stock_quote_result is not None else (),
            benchmark_quote_result.provenance if benchmark_quote_result is not None else (),
        )
        quote_results = tuple(
            quote_result
            for quote_result in (stock_quote_result, benchmark_quote_result)
            if quote_result is not None
        )
        captured_at = max(
            calendar_result.captured_at,
            stock_result.captured_at,
            benchmark_result.captured_at,
            *(quote_result.captured_at for quote_result in quote_results),
        )
        result = FetchResult(
            data=data,
            dataset=COMPUTED_DEVIATION_DATASET,
            provider=None,
            captured_at=captured_at,
            warnings=tuple(warnings),
            provenance=provenance,
            metadata={
                "coverage_status": coverage_status,
                "inferred_halt_dates": [
                    day.isoformat() for day in sorted(inferred_halt_dates)
                ],
                "windows": window_metadata,
                "observation_date": observation_date.isoformat(),
                "price_inputs": (
                    "historical_daily_bars"
                    if not use_live_quote
                    else "same_day_quotes_with_daily_history"
                    if not after_close
                    else "same_day_daily_bars_with_quote_fallback"
                    if len(quote_results) == 1
                    else "same_day_quotes"
                    if len(quote_results) == 2
                    else "same_day_daily_bars"
                ),
                "terminal_source_scope": ["current", "next_session"],
                "stock_terminal_source": (
                    "historical_daily_bar"
                    if not use_live_quote
                    else "same_day_quote"
                    if stock_quote is not None
                    else "same_day_daily_bar"
                ),
                "benchmark_terminal_source": (
                    "historical_daily_bar"
                    if not use_live_quote
                    else "same_day_quote"
                    if benchmark_quote is not None
                    else "same_day_daily_bar"
                ),
                "stock_qfq_quote_bridge_ratio": (
                    str(qfq_bridge_ratio) if qfq_bridge_ratio is not None else None
                ),
                "stock_qfq_quote_bridge_date": (
                    qfq_bridge_date.isoformat() if stock_quote is not None and qfq_bridge_date else None
                ),
                "stock_source_timestamp": (
                    stock_quote.source_timestamp.isoformat() if stock_quote else None
                ),
                "benchmark_source_timestamp": (
                    benchmark_quote.source_timestamp.isoformat() if benchmark_quote else None
                ),
                "requested_adjustment": KlineAdjustment.QFQ.value,
                "actual_adjustment": stock_adjustment.value,
                "source_series": stock_result.metadata.get(
                    "source_series",
                    "qfqday" if stock_adjustment is KlineAdjustment.QFQ else "day",
                ),
                "adjustment_warning": adjustment_warning,
            },
        )
        self._record_success(result)
        return result

    def _now_shanghai(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("deviation clock must return an aware datetime")
        return now.astimezone(_SHANGHAI)

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


def _calculate_window_from_history(
    *,
    instrument: InstrumentId,
    benchmark: BenchmarkSpec,
    window_days: Literal[10, 30],
    scenario: DeviationScenario,
    end_date: date,
    target_date: date,
    all_sessions: tuple[date, ...],
    window_sessions: tuple[date, ...],
    candidate_start_boundary: date,
    stock_points: dict[date, PricePoint],
    benchmark_points: dict[date, PricePoint],
    requested_as_of: date | None,
    requested_windows: tuple[int, ...],
    stock_source_timestamp: datetime | None,
    benchmark_source_timestamp: datetime | None,
) -> tuple[DeviationWindowData, tuple[str, ...]]:
    missing_stock_dates = tuple(day for day in window_sessions if day not in stock_points)
    missing_benchmark_dates = tuple(day for day in window_sessions if day not in benchmark_points)

    if missing_benchmark_dates:
        raise _deviation_coverage_error(
            instrument=instrument,
            benchmark=benchmark.instrument,
            requested_as_of=requested_as_of,
            effective_as_of=end_date,
            requested_windows=requested_windows,
            window_sessions=window_sessions,
            stock_points=stock_points,
            benchmark_points=benchmark_points,
            missing_stock_dates=missing_stock_dates,
            missing_benchmark_dates=missing_benchmark_dates,
            reason_code="missing_benchmark_closes",
        )
    if end_date not in stock_points:
        raise _deviation_coverage_error(
            instrument=instrument,
            benchmark=benchmark.instrument,
            requested_as_of=requested_as_of,
            effective_as_of=end_date,
            requested_windows=requested_windows,
            window_sessions=window_sessions,
            stock_points=stock_points,
            benchmark_points=benchmark_points,
            missing_stock_dates=missing_stock_dates,
            missing_benchmark_dates=(),
            reason_code="missing_effective_asof_stock_close",
        )

    observed_history = tuple(
        day for day in all_sessions if day in stock_points and day <= end_date
    )
    first_observed_date = observed_history[0] if observed_history else None
    last_observed_date = observed_history[-1] if observed_history else None
    bracketed_missing = tuple(
        day
        for day in missing_stock_dates
        if first_observed_date is not None
        and last_observed_date is not None
        and first_observed_date < day < last_observed_date
    )
    prefix_missing = tuple(day for day in missing_stock_dates if day not in bracketed_missing)

    if bracketed_missing:
        latest_gap_date = max(bracketed_missing)
        latest_gap_index = all_sessions.index(latest_gap_date)
        gap_start_index = latest_gap_index
        while gap_start_index > 0 and all_sessions[gap_start_index - 1] not in stock_points:
            gap_start_index -= 1
        gap_start_date = all_sessions[gap_start_index]
        stock_baselines = tuple(
            day
            for day in observed_history
            if day < gap_start_date
        )
        resume_index = latest_gap_index + 1
        if not stock_baselines or resume_index >= len(all_sessions):
            raise _deviation_coverage_error(
                instrument=instrument,
                benchmark=benchmark.instrument,
                requested_as_of=requested_as_of,
                effective_as_of=end_date,
                requested_windows=requested_windows,
                window_sessions=window_sessions,
                stock_points=stock_points,
                benchmark_points=benchmark_points,
                missing_stock_dates=bracketed_missing,
                missing_benchmark_dates=(),
                reason_code="missing_pre_halt_stock_close",
            )
        stock_baseline_date = stock_baselines[-1]
        resume_date = all_sessions[resume_index]
        if resume_date > end_date or resume_date not in stock_points:
            raise _deviation_coverage_error(
                instrument=instrument,
                benchmark=benchmark.instrument,
                requested_as_of=requested_as_of,
                effective_as_of=end_date,
                requested_windows=requested_windows,
                window_sessions=window_sessions,
                stock_points=stock_points,
                benchmark_points=benchmark_points,
                missing_stock_dates=bracketed_missing,
                missing_benchmark_dates=(),
                reason_code="missing_post_halt_stock_close",
            )
        benchmark_baseline_date = all_sessions[resume_index - 1]
        end_index = all_sessions.index(end_date)
        resume_sessions = all_sessions[resume_index : end_index + 1]
        benchmark_required = all_sessions[resume_index - 1 : end_index + 1]
        missing_benchmark_after_resume = tuple(
            day for day in benchmark_required if day not in benchmark_points
        )
        if missing_benchmark_after_resume:
            raise _deviation_coverage_error(
                instrument=instrument,
                benchmark=benchmark.instrument,
                requested_as_of=requested_as_of,
                effective_as_of=end_date,
                requested_windows=requested_windows,
                window_sessions=window_sessions,
                stock_points=stock_points,
                benchmark_points=benchmark_points,
                missing_stock_dates=bracketed_missing,
                missing_benchmark_dates=missing_benchmark_after_resume,
                reason_code="missing_benchmark_closes",
            )
        inferred_dates = bracketed_missing
        has_short_history = bool(prefix_missing)
        coverage_status = (
            "short_history_and_halt_inferred_from_missing_kline"
            if has_short_history
            else "halt_inferred_from_missing_kline"
        )
        available_sessions = sum(
            session >= candidate_start_boundary for session in resume_sessions
        )
        expected_sessions = window_days - (1 if scenario == "next_session" else 0)
        if has_short_history and available_sessions < expected_sessions:
            window_status: DeviationWindowStatus = (
                "partial_short_history_and_inferred_halt"
            )
        elif has_short_history:
            window_status = "complete"
        elif available_sessions < expected_sessions:
            window_status = "partial_after_inferred_halt"
        else:
            window_status = "complete"
        result = _calculate_after_inferred_halt(
            stock_points=stock_points,
            benchmark_points=benchmark_points,
            resume_sessions=resume_sessions,
            stock_baseline_date=stock_baseline_date,
            benchmark_baseline_date=benchmark_baseline_date,
            instrument=instrument,
            benchmark=benchmark,
            window_days=window_days,
            end_date=end_date,
            scenario=scenario,
            target_date=target_date,
            candidate_start_boundary=candidate_start_boundary,
            stock_source_timestamp=stock_source_timestamp,
            benchmark_source_timestamp=benchmark_source_timestamp,
            coverage_status=coverage_status,
            window_status=window_status,
            inferred_halt_dates=inferred_dates,
        )
        warnings = [
            "market.deviation inferred suspension dates from missing stock Kline rows "
            "(not verified against an exchange notice): "
            + ", ".join(day.isoformat() for day in inferred_dates)
        ]
        if has_short_history:
            warnings.append(
                f"market.deviation {window_days}-session window also has leading dates "
                "without stock Kline history; those dates were not inferred as suspensions."
            )
        if window_status.startswith("partial"):
            warnings.append(
                f"market.deviation {window_days}-session window is partial after the "
                f"inferred halt; {available_sessions} resumed trading sessions are available."
            )
        return result, tuple(warnings)

    if prefix_missing:
        observed_window_dates = tuple(
            day for day in window_sessions if day in stock_points
        )
        if len(observed_window_dates) < 2:
            raise _deviation_coverage_error(
                instrument=instrument,
                benchmark=benchmark.instrument,
                requested_as_of=requested_as_of,
                effective_as_of=end_date,
                requested_windows=requested_windows,
                window_sessions=window_sessions,
                stock_points=stock_points,
                benchmark_points=benchmark_points,
                missing_stock_dates=prefix_missing,
                missing_benchmark_dates=(),
                reason_code="insufficient_stock_close_history",
            )
        result = _calculate_short_history_window(
            stock_points=stock_points,
            benchmark_points=benchmark_points,
            observed_dates=observed_window_dates,
            instrument=instrument,
            benchmark=benchmark,
            window_days=window_days,
            scenario=scenario,
            target_date=target_date,
            stock_source_timestamp=stock_source_timestamp,
            benchmark_source_timestamp=benchmark_source_timestamp,
        )
        return result, (
            f"market.deviation {window_days}-session window uses short listing history; "
            f"{len(observed_window_dates) - 1} comparable trading sessions are available "
            "and this is not a complete window.",
        )

    result = calculate_deviation(
        tuple(stock_points[day] for day in window_sessions),
        tuple(benchmark_points[day] for day in window_sessions),
        instrument=instrument,
        benchmark=benchmark,
        window_days=window_days,
        end_date=end_date,
        scenario=scenario,
        target_date=target_date,
        stock_source_timestamp=stock_source_timestamp,
        benchmark_source_timestamp=benchmark_source_timestamp,
    )
    return result, ()


def _deviation_coverage_error(
    *,
    instrument: InstrumentId,
    benchmark: InstrumentId,
    requested_as_of: date | None,
    effective_as_of: date,
    requested_windows: tuple[int, ...],
    window_sessions: tuple[date, ...],
    stock_points: dict[date, PricePoint],
    benchmark_points: dict[date, PricePoint],
    missing_stock_dates: tuple[date, ...],
    missing_benchmark_dates: tuple[date, ...],
    reason_code: str,
) -> DeviationCoverageError:
    required_dates = set(window_sessions)
    return DeviationCoverageError(
        instrument_id=instrument,
        benchmark_instrument=benchmark,
        requested_as_of=requested_as_of,
        effective_as_of=effective_as_of,
        requested_windows=requested_windows,
        required_start_date=window_sessions[0],
        required_end_date=window_sessions[-1],
        required_count=len(window_sessions),
        observed_stock_count=len(required_dates.intersection(stock_points)),
        observed_benchmark_count=len(required_dates.intersection(benchmark_points)),
        missing_stock_dates=tuple(sorted(missing_stock_dates)),
        missing_benchmark_dates=tuple(sorted(missing_benchmark_dates)),
        reason_code=reason_code,
    )


def _calculate_short_history_window(
    *,
    stock_points: dict[date, PricePoint],
    benchmark_points: dict[date, PricePoint],
    observed_dates: tuple[date, ...],
    instrument: InstrumentId,
    benchmark: BenchmarkSpec,
    window_days: Literal[10, 30],
    scenario: DeviationScenario,
    target_date: date,
    stock_source_timestamp: datetime | None,
    benchmark_source_timestamp: datetime | None,
) -> DeviationWindowData:
    candidate_stop = len(observed_dates) if scenario == "next_session" else len(observed_dates) - 1
    candidate_indices = tuple(range(1, candidate_stop))
    if not candidate_indices:
        # Two closes are enough for one comparable return, including under the
        # default scan convention when no longer candidate exists.
        candidate_indices = (1,)
    end_date = observed_dates[-1]
    current_stock = stock_points[end_date].close
    current_index = benchmark_points[end_date].close
    candidate_starts = tuple(
        (
            index_in_window,
            observed_dates[index_in_window],
            observed_dates[index_in_window - 1],
            observed_dates[index_in_window - 1],
        )
        for index_in_window in candidate_indices
    )
    chosen, upper_basis = _best_deviation_candidate(
        candidate_starts,
        stock_points=stock_points,
        benchmark_points=benchmark_points,
        end_date=end_date,
        upper_threshold=_upper_threshold(window_days),
    )
    return _build_deviation_window(
        window_days=window_days,
        scenario=scenario,
        target_date=target_date,
        trading_sessions=len(observed_dates) - chosen.candidate_index,
        available_trading_sessions=min(
            window_days - 1 if scenario == "next_session" else window_days,
            len(observed_dates) - 1,
        ),
        window_status="partial_short_history",
        coverage_status="short_history",
        start_date=chosen.start_date,
        stock_baseline_date=chosen.stock_baseline_date,
        benchmark_baseline_date=chosen.benchmark_baseline_date,
        end_date=end_date,
        inferred_halt_dates=(),
        stock_baseline_price=chosen.stock_start,
        window_start_price=stock_points[chosen.start_date].close,
        current_price=current_stock,
        benchmark_start=chosen.benchmark_start,
        benchmark_current=current_index,
        stock_return=chosen.stock_return,
        benchmark_return=chosen.benchmark_return,
        deviation=chosen.deviation,
        instrument=instrument,
        benchmark=benchmark,
        upper_trigger_price=upper_basis.stock_start
        * (Decimal("1") + _upper_threshold(window_days) + upper_basis.benchmark_return),
        upper_trigger_basis=upper_basis,
        stock_source_timestamp=stock_source_timestamp,
        benchmark_source_timestamp=benchmark_source_timestamp,
    )


def _calculate_after_inferred_halt(
    *,
    stock_points: dict[date, PricePoint],
    benchmark_points: dict[date, PricePoint],
    resume_sessions: tuple[date, ...],
    stock_baseline_date: date,
    benchmark_baseline_date: date,
    instrument: InstrumentId,
    benchmark: BenchmarkSpec,
    window_days: Literal[10, 30],
    end_date: date,
    scenario: DeviationScenario,
    target_date: date,
    candidate_start_boundary: date,
    stock_source_timestamp: datetime | None,
    benchmark_source_timestamp: datetime | None,
    coverage_status: DeviationCoverageStatus,
    window_status: DeviationWindowStatus,
    inferred_halt_dates: tuple[date, ...],
) -> DeviationWindowData:
    candidate_stop = len(resume_sessions) if scenario == "next_session" else max(1, len(resume_sessions) - 1)
    candidate_indices = tuple(
        index
        for index in range(candidate_stop)
        if resume_sessions[index] >= candidate_start_boundary
    )
    if not candidate_indices:
        raise NoData(
            "market.deviation has no eligible next_session candidate after inferred halt"
        )

    current_stock = stock_points[end_date].close
    current_index = benchmark_points[end_date].close
    candidate_starts: list[tuple[int, date, date, date]] = []
    for index_in_segment in candidate_indices:
        if index_in_segment == 0:
            stock_base_date = stock_baseline_date
            benchmark_base_date = benchmark_baseline_date
        else:
            stock_base_date = resume_sessions[index_in_segment - 1]
            benchmark_base_date = stock_base_date
        candidate_starts.append(
            (
                index_in_segment,
                resume_sessions[index_in_segment],
                stock_base_date,
                benchmark_base_date,
            )
        )
    chosen, upper_basis = _best_deviation_candidate(
        tuple(candidate_starts),
        stock_points=stock_points,
        benchmark_points=benchmark_points,
        end_date=end_date,
        upper_threshold=_upper_threshold(window_days),
    )
    available = sum(
        session >= candidate_start_boundary for session in resume_sessions
    )
    return _build_deviation_window(
        window_days=window_days,
        scenario=scenario,
        target_date=target_date,
        trading_sessions=len(resume_sessions) - chosen.candidate_index,
        available_trading_sessions=available,
        window_status=window_status,
        coverage_status=coverage_status,
        start_date=chosen.start_date,
        stock_baseline_date=chosen.stock_baseline_date,
        benchmark_baseline_date=chosen.benchmark_baseline_date,
        end_date=end_date,
        inferred_halt_dates=inferred_halt_dates,
        stock_baseline_price=chosen.stock_start,
        window_start_price=stock_points[chosen.start_date].close,
        current_price=current_stock,
        benchmark_start=chosen.benchmark_start,
        benchmark_current=current_index,
        stock_return=chosen.stock_return,
        benchmark_return=chosen.benchmark_return,
        deviation=chosen.deviation,
        instrument=instrument,
        benchmark=benchmark,
        upper_trigger_price=upper_basis.stock_start
        * (Decimal("1") + _upper_threshold(window_days) + upper_basis.benchmark_return),
        upper_trigger_basis=upper_basis,
        stock_source_timestamp=stock_source_timestamp,
        benchmark_source_timestamp=benchmark_source_timestamp,
    )


def _best_deviation_candidate(
    candidate_starts: Sequence[tuple[int, date, date, date]],
    *,
    stock_points: dict[date, PricePoint],
    benchmark_points: dict[date, PricePoint],
    end_date: date,
    upper_threshold: Decimal,
) -> tuple[_DeviationCandidate, _DeviationCandidate]:
    current_stock = stock_points[end_date].close
    current_benchmark = benchmark_points[end_date].close
    candidates: list[_DeviationCandidate] = []
    for candidate_index, start_date, stock_baseline_date, benchmark_baseline_date in candidate_starts:
        stock_start = stock_points[stock_baseline_date].close
        benchmark_start = benchmark_points[benchmark_baseline_date].close
        stock_return = current_stock / stock_start - Decimal("1")
        benchmark_return = current_benchmark / benchmark_start - Decimal("1")
        candidates.append(
            _DeviationCandidate(
                deviation=stock_return - benchmark_return,
                candidate_index=candidate_index,
                start_date=start_date,
                stock_baseline_date=stock_baseline_date,
                benchmark_baseline_date=benchmark_baseline_date,
                stock_return=stock_return,
                benchmark_return=benchmark_return,
                stock_start=stock_start,
                benchmark_start=benchmark_start,
            )
        )
    deviation_basis = max(
        candidates,
        key=lambda candidate: (candidate.deviation, -candidate.candidate_index),
    )
    trigger_basis = min(
        candidates,
        key=lambda candidate: (
            candidate.stock_start
            * (Decimal("1") + upper_threshold + candidate.benchmark_return),
            candidate.candidate_index,
        ),
    )
    return deviation_basis, trigger_basis


def _build_deviation_window(
    *,
    window_days: Literal[10, 30],
    scenario: DeviationScenario,
    target_date: date,
    trading_sessions: int,
    available_trading_sessions: int,
    window_status: DeviationWindowStatus,
    coverage_status: DeviationCoverageStatus,
    start_date: date,
    stock_baseline_date: date,
    benchmark_baseline_date: date,
    end_date: date,
    inferred_halt_dates: tuple[date, ...],
    stock_baseline_price: Decimal,
    window_start_price: Decimal,
    current_price: Decimal,
    benchmark_start: Decimal,
    benchmark_current: Decimal,
    stock_return: Decimal,
    benchmark_return: Decimal,
    deviation: Decimal,
    instrument: InstrumentId,
    benchmark: BenchmarkSpec,
    upper_trigger_price: Decimal,
    upper_trigger_basis: _DeviationCandidate,
    stock_source_timestamp: datetime | None,
    benchmark_source_timestamp: datetime | None,
) -> DeviationWindowData:
    upper_threshold = _upper_threshold(window_days)
    if upper_trigger_price <= 0:
        raise NoData("market.deviation produced a non-positive trigger price")
    unrounded_upper_trigger = upper_trigger_price
    upper_trigger_price = _round_trigger_price_up(unrounded_upper_trigger)
    result = DeviationWindowData(
        windowDays=window_days,
        scenario=scenario,
        tradingSessions=trading_sessions,
        availableTradingSessions=available_trading_sessions,
        windowStatus=window_status,
        coverageStatus=coverage_status,
        startDate=start_date,
        baselineDate=stock_baseline_date,
        stockBaselineDate=stock_baseline_date,
        benchmarkBaselineDate=benchmark_baseline_date,
        endDate=end_date,
        targetDate=target_date,
        inferredHaltDates=inferred_halt_dates,
        stockBaselinePrice=stock_baseline_price,
        windowStartPrice=window_start_price,
        currentPrice=current_price,
        benchmarkInstrument=benchmark.instrument,
        benchmarkName=benchmark.name,
        benchmarkStart=benchmark_start,
        benchmarkCurrent=benchmark_current,
        stockReturn=stock_return,
        benchmarkReturn=benchmark_return,
        deviation=deviation,
        upperThreshold=upper_threshold,
        remainingToUpper=upper_trigger_price / current_price - Decimal("1"),
        upperTriggerPrice=upper_trigger_price,
        upperTriggerPrice_original=unrounded_upper_trigger,
        stockSourceTimestamp=stock_source_timestamp,
        benchmarkSourceTimestamp=benchmark_source_timestamp,
    )
    result._upper_trigger_basis = {
        "stock_baseline_date": upper_trigger_basis.stock_baseline_date.isoformat(),
        "benchmark_baseline_date": upper_trigger_basis.benchmark_baseline_date.isoformat(),
        "stock_baseline_price": str(upper_trigger_basis.stock_start),
        "benchmark_start": str(upper_trigger_basis.benchmark_start),
        "benchmark_return": str(upper_trigger_basis.benchmark_return),
        "candidate_start_date": upper_trigger_basis.start_date.isoformat(),
        "unrounded_trigger_price": str(unrounded_upper_trigger),
    }
    return result


def _price_map(points: Iterable[PricePoint], label: str) -> dict[date, PricePoint]:
    result: dict[date, PricePoint] = {}
    for point in points:
        if not isinstance(point, PricePoint):
            raise InvalidRequest(f"{label} prices must contain PricePoint values")
        if point.point_date in result:
            raise InvalidRequest(f"{label} prices contain duplicate dates")
        result[point.point_date] = point
    return result


def _upper_threshold(window_days: Literal[10, 30]) -> Decimal:
    return Decimal("1.00") if window_days == 10 else Decimal("2.00")


def _round_trigger_price_up(value: Decimal) -> Decimal:
    """Round a selected theoretical trigger price upward to the next cent."""

    return value.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def _calendar_sessions(data: Iterable[StandardRecord]) -> tuple[date, ...]:
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
        if record.data.get("isTradingDay") is True:
            sessions.append(session_date)
    return tuple(sorted(set(sessions)))


def _bridge_qfq_stock_history(
    stock_points: dict[date, PricePoint],
    quote: MarketQuoteSnapshotData,
    observation_date: date,
) -> tuple[dict[date, PricePoint], Decimal, date]:
    prior_dates = tuple(day for day in stock_points if day < observation_date)
    if not prior_dates:
        raise NoData(
            "market.deviation cannot bridge the stock quote: no prior stock Kline close is available"
        )
    if quote.previous_close is None or quote.previous_close <= 0:
        raise NoData(
            "market.deviation stock quote lacks a valid previousClose for the QFQ price bridge"
        )
    bridge_date = max(prior_dates)
    ratio = quote.previous_close / stock_points[bridge_date].close
    if not ratio.is_finite() or ratio <= 0:
        raise NoData("market.deviation could not establish the stock QFQ quote bridge")
    bridged = {
        day: PricePoint(day, point.close * ratio)
        for day, point in stock_points.items()
    }
    return bridged, ratio, bridge_date


def _quote_snapshot_data(
    data: object,
    expected: InstrumentId,
    observation_date: date,
    now: datetime,
    captured_at: datetime,
) -> MarketQuoteSnapshotData:
    if not isinstance(data, StandardRecord):
        raise NoData("market.deviation quote_snapshot returned an invalid record")
    if data.dataset != MARKET_QUOTE_SNAPSHOT_DATASET.name:
        raise NoData("market.deviation quote_snapshot returned a different dataset")
    if data.status is not DataStatus.LIVE:
        raise NoData("market.deviation quote_snapshot status is not live")
    if data.entity_id != expected:
        raise NoData("market.deviation quote_snapshot entityId does not match request")
    try:
        quote = MarketQuoteSnapshotData.model_validate(data.data)
    except Exception as exc:
        raise NoData("market.deviation quote_snapshot returned an invalid price") from exc
    if quote.instrument_id != expected:
        raise NoData("market.deviation quote_snapshot instrument does not match request")
    if quote.price <= 0:
        raise NoData("market.deviation quote_snapshot price must be positive")
    local_now = now.astimezone(_SHANGHAI)
    source_time = quote.source_timestamp.astimezone(_SHANGHAI)
    local_captured = captured_at.astimezone(_SHANGHAI)
    if source_time.date() != observation_date:
        raise NoData(
            f"market.deviation quote_snapshot is stale: expected {observation_date.isoformat()}, "
            f"received {source_time.date().isoformat()}"
        )
    if source_time > local_now + timedelta(minutes=1) or source_time > local_captured + timedelta(minutes=1):
        raise NoData("market.deviation quote_snapshot sourceTimestamp is in the future")
    source_clock = source_time.time().replace(tzinfo=None)
    current_clock = local_now.time().replace(tzinfo=None)
    if source_clock < time(9, 15):
        raise NoData("market.deviation quote_snapshot timestamp is before the A-share session")
    if current_clock < time(9, 15):
        raise NoData("market.deviation has no valid same-day quote before the A-share session")
    if current_clock < time(15, 0):
        if time(11, 30) <= current_clock < time(13, 0):
            if source_clock < time(11, 15):
                raise NoData("market.deviation quote_snapshot is stale for the lunch session")
        elif local_now - source_time > timedelta(minutes=20):
            raise NoData("market.deviation quote_snapshot is stale for the current session")
    return quote


def _scenario_quote_error(
    *,
    instrument: InstrumentId,
    benchmark: InstrumentId,
    requested_as_of: date | None,
    observation_date: date,
    windows: tuple[int, ...],
    sessions: tuple[date, ...],
    stock_points: dict[date, PricePoint],
    benchmark_points: dict[date, PricePoint],
    missing_stock_dates: tuple[date, ...],
    missing_benchmark_dates: tuple[date, ...],
    reason_code: str,
) -> DeviationCoverageError:
    return _deviation_coverage_error(
        instrument=instrument,
        benchmark=benchmark,
        requested_as_of=requested_as_of,
        effective_as_of=observation_date,
        requested_windows=windows,
        window_sessions=sessions,
        stock_points=stock_points,
        benchmark_points=benchmark_points,
        missing_stock_dates=missing_stock_dates,
        missing_benchmark_dates=missing_benchmark_dates,
        reason_code=reason_code,
    )


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


def _stock_kline_adjustment(
    data: Iterable[StandardRecord],
    metadata: Any,
) -> KlineAdjustment:
    observed_adjustments: set[KlineAdjustment] = set()
    for record in data:
        if not isinstance(record, StandardRecord):
            raise NoData("market.klines returned an invalid record")
        try:
            bar = MarketKlineData.model_validate(record.data)
        except Exception as exc:
            raise NoData("market.klines returned an invalid bar") from exc
        if bar.adjustment not in (KlineAdjustment.QFQ, KlineAdjustment.NONE):
            raise NoData("market.deviation stock Klines returned an unsupported adjustment mode")
        observed_adjustments.add(bar.adjustment)

    if len(observed_adjustments) > 1:
        raise NoData("market.deviation stock Klines mix adjustment modes")
    observed = next(iter(observed_adjustments), None)
    metadata_adjustment = metadata.get("actual_adjustment") if hasattr(metadata, "get") else None
    if metadata_adjustment is not None:
        try:
            declared = KlineAdjustment(metadata_adjustment)
        except (TypeError, ValueError) as exc:
            raise NoData("market.deviation stock Klines reported an invalid actual_adjustment") from exc
        if declared not in (KlineAdjustment.QFQ, KlineAdjustment.NONE):
            raise NoData("market.deviation stock Klines reported an unsupported actual_adjustment")
        if observed is not None and declared is not observed:
            raise NoData("market.deviation stock Klines metadata conflicts with bar adjustment")
        return declared
    return observed or KlineAdjustment.QFQ


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
    "DeviationCoverageError",
    "DeviationData",
    "DeviationRequest",
    "DeviationService",
    "DeviationScenario",
    "DeviationWindowData",
    "PricePoint",
    "calculate_deviation",
    "resolve_deviation_benchmark",
]
