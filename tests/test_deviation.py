from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from finchx import FinchX
from finchx.collectors import FetchResult
from finchx.collectors.errors import InvalidRequest, NoData
from finchx.computed import (
    COMPUTED_DEVIATION_DATASET,
    DEVIATION_RULE_VERSION,
    BenchmarkSpec,
    DeviationCoverageError,
    DeviationService,
    PricePoint,
    calculate_deviation,
    resolve_deviation_benchmark,
)
from finchx.computed.deviation import (
    _bridge_qfq_stock_history,
    _calculate_after_inferred_halt,
)
from finchx.contracts import (
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    StandardRecord,
)
from finchx.datasets import (
    KlineAdjustment,
    KlinesRequest,
    MARKET_KLINES_DATASET,
    TRADING_CALENDAR_DATASET,
    MARKET_QUOTE_SNAPSHOT_DATASET,
    TradingCalendarRequest,
)
from finchx.datasets.market_klines import MarketKlineData
from finchx.datasets.market_quote_snapshot import MarketQuoteSnapshotData
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.observability import ObservabilityMonitor
from finchx.quality import QualityMonitor
from finchx.health import HealthMonitor


FIXTURES = Path(__file__).parent / "fixtures" / "deviation"


CAPTURED_AT = datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc)


def equity(code: str, exchange: Exchange) -> InstrumentId:
    return InstrumentId(
        code=code,
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=exchange,
    )


def test_benchmark_resolver_freezes_audited_mappings_and_rejects_bse():
    cases = json.loads((FIXTURES / "benchmark-mapping.json").read_text(encoding="utf-8"))
    exchange_by_name = {exchange.value: exchange for exchange in Exchange}
    for case in cases:
        instrument = equity(case["code"], exchange_by_name[case["exchange"]])
        resolved = resolve_deviation_benchmark(instrument)
        assert resolved.instrument.code == case["benchmark"]
        assert resolved.board == case["board"]

    with pytest.raises(InvalidRequest, match="does not support BSE"):
        resolve_deviation_benchmark(equity("920298", Exchange.BSE))


def test_pure_calculator_selects_max_deviation_not_max_stock_return():
    fixture = json.loads((FIXTURES / "max-deviation.json").read_text(encoding="utf-8"))
    dates = tuple(date.fromisoformat(value) for value in fixture["dates"])
    stock_values = [Decimal(value) for value in fixture["stock"]]
    benchmark_values = [Decimal(value) for value in fixture["benchmark"]]
    instrument = equity("600519", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(instrument)

    result = calculate_deviation(
        tuple(PricePoint(day, Decimal(str(value))) for day, value in zip(dates, stock_values)),
        tuple(PricePoint(day, Decimal(str(value))) for day, value in zip(dates, benchmark_values)),
        instrument=instrument,
        benchmark=benchmark,
        window_days=10,
        end_date=dates[-1],
    )

    assert result.start_date == date.fromisoformat(fixture["expectedStartDate"])
    assert result.deviation == pytest.approx(
        Decimal(fixture["expectedDeviation"]), abs=Decimal("0.0000000001")
    )
    assert result.stock_return < Decimal("0.80")
    assert result.benchmark_return < Decimal("0.06")


def test_pure_calculator_uses_close_formula_and_trigger_price():
    dates = tuple(date(2026, 8, 1) + timedelta(days=index) for index in range(11))
    stock = tuple(PricePoint(day, Decimal("100") if index == 0 else Decimal("180")) for index, day in enumerate(dates))
    index = tuple(PricePoint(day, Decimal("100") if index == 0 else Decimal("120")) for index, day in enumerate(dates))
    instrument = equity("600519", Exchange.SSE)
    result = calculate_deviation(
        stock,
        index,
        instrument=instrument,
        benchmark=resolve_deviation_benchmark(instrument),
        window_days=10,
        end_date=dates[-1],
    )

    assert result.stock_return == Decimal("0.8")
    assert result.benchmark_return == Decimal("0.2")
    assert result.deviation == Decimal("0.6")
    assert result.upper_threshold == Decimal("1.00")
    assert result.upper_trigger_price == Decimal("220.0")
    expected_remaining = result.upper_trigger_price / result.current_price - Decimal("1")
    assert result.remaining_to_upper == expected_remaining


def test_pure_calculator_rounds_final_trigger_up_to_cent_and_uses_rounded_value_for_distance():
    dates = tuple(date(2026, 8, 1) + timedelta(days=index) for index in range(4))
    instrument = equity("600519", Exchange.SSE)
    result = calculate_deviation(
        tuple(PricePoint(day, Decimal(value)) for day, value in zip(dates, ("2.66135", "1.7742", "4.9", "5"))),
        tuple(PricePoint(day, Decimal(value)) for day, value in zip(dates, ("100", "50", "100", "100"))),
        instrument=instrument,
        benchmark=resolve_deviation_benchmark(instrument),
        window_days=10,
        end_date=dates[-1],
    )

    assert result.deviation == Decimal("5") / Decimal("2.66135") - Decimal("1")
    assert result.stock_baseline_price == Decimal("2.66135")
    assert result._upper_trigger_basis["stock_baseline_price"] == "1.7742"
    assert Decimal(result._upper_trigger_basis["unrounded_trigger_price"]) == Decimal("5.3226")
    assert result.upper_trigger_price_original == Decimal("5.3226")
    assert result.upper_trigger_price == Decimal("5.33")
    expected_remaining = Decimal("5.33") / Decimal("5") - Decimal("1")
    assert result.remaining_to_upper == expected_remaining


def test_pure_calculator_selects_max_deviation_and_min_trigger_independently():
    dates = tuple(date(2026, 8, 1) + timedelta(days=index) for index in range(4))
    stock = tuple(
        PricePoint(day, value)
        for day, value in zip(
            dates,
            (Decimal("10"), Decimal("8"), Decimal("12"), Decimal("18")),
        )
    )
    index = tuple(
        PricePoint(day, value)
        for day, value in zip(
            dates,
            (Decimal("148"), Decimal("100"), Decimal("120"), Decimal("148")),
        )
    )
    instrument = equity("600519", Exchange.SSE)
    result = calculate_deviation(
        stock,
        index,
        instrument=instrument,
        benchmark=resolve_deviation_benchmark(instrument),
        window_days=10,
        end_date=dates[-1],
    )

    assert result.deviation == Decimal("0.8")
    assert result.stock_baseline_price == Decimal("10")
    assert result.upper_trigger_price == Decimal("19.84")
    assert result.upper_trigger_price_original == Decimal("19.84")
    assert result._upper_trigger_basis["stock_baseline_price"] == "8"
    assert result._upper_trigger_basis["unrounded_trigger_price"] == "19.84"
    trigger_deviations = (
        result.upper_trigger_price_original / Decimal("10") - Decimal("1"),
        result.upper_trigger_price_original / Decimal("8") - Decimal("1") - Decimal("0.48"),
    )
    assert max(trigger_deviations) == result.upper_threshold


def test_scenario_service_returns_rounded_and_original_trigger_prices():
    observation_date = date(2026, 9, 28)
    sessions = _weekday_sessions_ending(observation_date, 31)
    stock = equity("600519", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    shared_history = {
        sessions[-3]: Decimal("2.6613"),
        sessions[-2]: Decimal("2.6613"),
        sessions[-1]: Decimal("2.6613"),
    }
    quote_time = datetime(2026, 9, 28, 14, 0, tzinfo=timezone(timedelta(hours=8)))
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=sessions[:-3],
        stock_close_overrides=shared_history,
        benchmark_close_overrides={day: Decimal("100") for day in sessions[-3:]},
        stock_quote_price=Decimal("5"),
        benchmark_quote_price=Decimal("100"),
        stock_quote_previous_close=Decimal("2.6613"),
        quote_timestamp=quote_time,
    )

    result = DeviationService(collector, clock=lambda: quote_time).calculate(
        stock,
        windows=(10,),
        as_of=observation_date,
    )
    current = next(window for window in result.data.windows if window.scenario == "current")

    assert current.upper_trigger_price_original == Decimal("5.3226")
    assert current.upper_trigger_price == Decimal("5.33")
    assert current.remaining_to_upper == Decimal("5.33") / Decimal("5") - Decimal("1")
    serialized_current = next(
        window for window in result.to_dicts()[0]["windows"] if window["scenario"] == "current"
    )
    assert Decimal(serialized_current["upperTriggerPrice_original"]) == Decimal("5.3226")
    assert serialized_current["upperTriggerPrice"] == "5.33"


def test_next_session_rolls_start_boundary_and_allows_d10_one_day_candidate():
    dates = tuple(date(2026, 8, 1) + timedelta(days=index) for index in range(11))
    stock_values = [Decimal("20")] * 9 + [Decimal("10"), Decimal("30")]
    benchmark_values = [Decimal("100")] * len(dates)
    instrument = equity("600519", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(instrument)
    stock = tuple(PricePoint(day, value) for day, value in zip(dates, stock_values))
    index = tuple(PricePoint(day, value) for day, value in zip(dates, benchmark_values))

    current = calculate_deviation(
        stock,
        index,
        instrument=instrument,
        benchmark=benchmark,
        window_days=10,
        end_date=dates[-1],
        scenario="current",
    )
    next_session = calculate_deviation(
        stock[1:],
        index[1:],
        instrument=instrument,
        benchmark=benchmark,
        window_days=10,
        end_date=dates[-1],
        scenario="next_session",
        target_date=dates[-1] + timedelta(days=1),
    )

    assert current.deviation == Decimal("0.5")
    assert next_session.deviation == Decimal("2")
    assert next_session.start_date == dates[-1]
    assert next_session.stock_baseline_date == dates[-2]
    assert next_session.trading_sessions == 1
    assert next_session.available_trading_sessions == 9
    assert next_session.remaining_to_upper == next_session.upper_trigger_price / next_session.current_price - Decimal("1")
    assert next_session.remaining_to_upper < 0


def test_all_negative_candidates_remain_negative():
    dates = tuple(date(2026, 8, 1) + timedelta(days=index) for index in range(4))
    instrument = equity("600519", Exchange.SSE)
    result = calculate_deviation(
        tuple(PricePoint(day, Decimal(value)) for day, value in zip(dates, ("10", "9", "8", "7"))),
        tuple(PricePoint(day, Decimal(value)) for day, value in zip(dates, ("100", "101", "102", "103"))),
        instrument=instrument,
        benchmark=resolve_deviation_benchmark(instrument),
        window_days=10,
        end_date=dates[-1],
    )

    assert result.deviation < 0
    assert result.remaining_to_upper == result.upper_trigger_price / result.current_price - Decimal("1")
    assert result.remaining_to_upper > 0


def test_quote_bridge_uses_last_observed_stock_bar_when_prior_session_bar_is_missing():
    stock = equity("600825", Exchange.SSE)
    observation_date = date(2026, 9, 28)
    bridge_date = date(2026, 9, 24)
    points = {
        bridge_date: PricePoint(bridge_date, Decimal("5")),
        observation_date: PricePoint(observation_date, Decimal("6")),
    }
    quote_time = datetime(2026, 9, 28, 16, 14, 52, tzinfo=timezone(timedelta(hours=8)))
    quote = MarketQuoteSnapshotData(
        instrumentId=stock,
        price=Decimal("12"),
        previousClose=Decimal("10"),
        sourceTimestamp=quote_time,
    )

    bridged, ratio, actual_bridge_date = _bridge_qfq_stock_history(
        points, quote, observation_date
    )

    assert actual_bridge_date == bridge_date
    assert ratio == Decimal("2")
    assert bridged[bridge_date].close == Decimal("10")
    assert bridged[observation_date].close == Decimal("12")


def test_first_resumed_session_remains_eligible_when_next_boundary_precedes_it():
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock)
    baseline_date = date(2026, 9, 4)
    benchmark_baseline_date = date(2026, 9, 25)
    resumed_date = date(2026, 9, 28)
    stock_points = {
        baseline_date: PricePoint(baseline_date, Decimal("10")),
        resumed_date: PricePoint(resumed_date, Decimal("12")),
    }
    benchmark_points = {
        benchmark_baseline_date: PricePoint(benchmark_baseline_date, Decimal("100")),
        resumed_date: PricePoint(resumed_date, Decimal("110")),
    }

    result = _calculate_after_inferred_halt(
        stock_points=stock_points,
        benchmark_points=benchmark_points,
        resume_sessions=(resumed_date,),
        stock_baseline_date=baseline_date,
        benchmark_baseline_date=benchmark_baseline_date,
        instrument=stock,
        benchmark=benchmark,
        window_days=10,
        end_date=resumed_date,
        scenario="next_session",
        target_date=date(2026, 9, 29),
        candidate_start_boundary=date(2026, 9, 2),
        stock_source_timestamp=None,
        benchmark_source_timestamp=None,
        coverage_status="halt_inferred_from_missing_kline",
        window_status="partial_after_inferred_halt",
        inferred_halt_dates=(date(2026, 9, 7),),
    )

    assert result.start_date == resumed_date
    assert result.stock_baseline_date == baseline_date
    assert result.benchmark_baseline_date == benchmark_baseline_date
    assert result.trading_sessions == result.available_trading_sessions == 1


class FixtureCollector:
    def __init__(
        self,
        sessions: tuple[date, ...],
        stock: InstrumentId,
        benchmark: InstrumentId,
        *,
        missing_stock_dates: tuple[date, ...] = (),
        missing_benchmark_dates: tuple[date, ...] = (),
        closed_dates: tuple[date, ...] = (),
        stock_close_overrides: dict[date, Decimal] | None = None,
        benchmark_close_overrides: dict[date, Decimal] | None = None,
        stock_quote_price: Decimal | None = None,
        benchmark_quote_price: Decimal | None = None,
        stock_quote_previous_close: Decimal | None = None,
        quote_timestamp: datetime | None = None,
        quote_status: DataStatus = DataStatus.LIVE,
        quote_entity_id: InstrumentId | str | None = None,
        stock_adjustment: KlineAdjustment = KlineAdjustment.QFQ,
    ):
        self.sessions = sessions
        self.stock = stock
        self.benchmark = benchmark
        self.missing_stock_dates = set(missing_stock_dates)
        self.missing_benchmark_dates = set(missing_benchmark_dates)
        self.closed_dates = closed_dates
        self.stock_close_overrides = stock_close_overrides or {}
        self.benchmark_close_overrides = benchmark_close_overrides or {}
        self.stock_quote_price = stock_quote_price
        self.benchmark_quote_price = benchmark_quote_price
        self.stock_quote_previous_close = stock_quote_previous_close
        self.quote_timestamp = quote_timestamp
        self.quote_status = quote_status
        self.quote_entity_id = quote_entity_id
        self.stock_adjustment = stock_adjustment
        self.calls: list[tuple[object, object, str | None]] = []
        self.health = HealthMonitor()
        self.quality = QualityMonitor(clock=lambda: CAPTURED_AT)
        self.observability = ObservabilityMonitor()
        self._source = Source(providerId="fixture.deviation")
        self._quote_source = Source(providerId="fixture.quote")

    def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
        request = kwargs["request"]
        self.calls.append((dataset, request, provider))
        if dataset is TRADING_CALENDAR_DATASET:
            future_day = self.sessions[-1] + timedelta(days=1)
            while future_day.weekday() >= 5 or future_day in self.closed_dates:
                future_day += timedelta(days=1)
            calendar_rows = tuple((day, True) for day in self.sessions) + (
                (future_day, True),
            ) + tuple((day, False) for day in self.closed_dates)
            data = tuple(
                _record(
                    TRADING_CALENDAR_DATASET.name,
                    f"calendar:{day.isoformat()}:{is_trading_day}",
                    "CN_A:" + day.isoformat(),
                    {"date": day.isoformat(), "isTradingDay": is_trading_day},
                )
                for day, is_trading_day in calendar_rows
            )
            return FetchResult(
                data=data,
                dataset=TRADING_CALENDAR_DATASET,
                provider="fixture.calendar",
                captured_at=CAPTURED_AT,
                provenance=(self._source,),
            )
        if dataset is MARKET_QUOTE_SNAPSHOT_DATASET:
            identity = request.instrument_id
            if identity == self.stock:
                closes = [
                    self.stock_close_overrides.get(day, Decimal(100 + index))
                    for index, day in enumerate(self.sessions)
                ]
                unavailable_dates = self.missing_stock_dates
                quote_price = (
                    self.stock_quote_price
                    if self.stock_quote_price is not None
                    else closes[-1]
                )
                previous_override = self.stock_quote_previous_close
            else:
                assert identity == self.benchmark
                closes = [
                    self.benchmark_close_overrides.get(day, Decimal(1000 + 2 * index))
                    for index, day in enumerate(self.sessions)
                ]
                unavailable_dates = self.missing_benchmark_dates
                quote_price = (
                    self.benchmark_quote_price
                    if self.benchmark_quote_price is not None
                    else closes[-1]
                )
                previous_override = None
            quote_index = len(self.sessions) - 1
            prior_available_indices = [
                index
                for index in range(quote_index)
                if self.sessions[index] not in unavailable_dates
            ]
            previous = (
                previous_override
                if previous_override is not None
                else closes[prior_available_indices[-1]]
                if prior_available_indices
                else None
            )
            quote_time = self.quote_timestamp or datetime.combine(
                self.sessions[quote_index],
                datetime.min.time().replace(hour=15),
                tzinfo=timezone(timedelta(hours=8)),
            )
            quote_entity = self.quote_entity_id or identity
            data = _record(
                MARKET_QUOTE_SNAPSHOT_DATASET.name,
                f"quote:{identity.code}:{quote_time.isoformat()}",
                quote_entity,
                {
                    "instrumentId": identity.model_dump(mode="json"),
                    "price": str(quote_price),
                    "previousClose": str(previous) if previous is not None else None,
                    "sourceTimestamp": quote_time.isoformat(),
                },
                captured_at=quote_time,
                status=self.quote_status,
            )
            return FetchResult(
                data=data,
                dataset=MARKET_QUOTE_SNAPSHOT_DATASET,
                provider="fixture.quote",
                captured_at=quote_time,
                provenance=(self._quote_source,),
            )
        assert dataset is MARKET_KLINES_DATASET
        identity = request.instrument_id
        assert isinstance(request, KlinesRequest)
        if identity == self.stock:
            closes = [
                self.stock_close_overrides.get(day, Decimal(100 + index))
                for index, day in enumerate(self.sessions)
            ]
            missing_dates = self.missing_stock_dates
            assert request.adjustment is KlineAdjustment.QFQ
        else:
            assert identity == self.benchmark
            closes = [
                self.benchmark_close_overrides.get(day, Decimal(1000 + 2 * index))
                for index, day in enumerate(self.sessions)
            ]
            missing_dates = self.missing_benchmark_dates
            assert request.adjustment is None
        data = tuple(
            _record(
                MARKET_KLINES_DATASET.name,
                f"{identity.code}:{day.isoformat()}",
                identity,
                MarketKlineData(
                    instrumentId=identity,
                    barDate=day,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=100,
                    adjustment=(
                        self.stock_adjustment
                        if identity == self.stock
                        else KlineAdjustment.NOT_APPLICABLE
                    ),
                ).model_dump(mode="json", by_alias=True),
            )
            for day, close in zip(self.sessions, closes)
            if day not in missing_dates
            and request.start_date <= day <= request.end_date
        )
        adjustment_warning = None
        warnings = ()
        metadata = {}
        if identity == self.stock and self.stock_adjustment is KlineAdjustment.NONE:
            adjustment_warning = (
                "market.deviation stock Klines use unadjusted day prices; "
                "the result is not forward-adjusted."
            )
            warnings = (adjustment_warning,)
            metadata = {
                "requested_adjustment": "qfq",
                "actual_adjustment": "none",
                "source_series": "day",
                "adjustment_fallback": True,
                "adjustment_warning": adjustment_warning,
            }
        return FetchResult(
            data=data,
            dataset=MARKET_KLINES_DATASET,
            provider=provider or "fixture.klines",
            captured_at=CAPTURED_AT,
            warnings=warnings,
            provenance=(self._source,),
            metadata=metadata,
        )


def _record(
    dataset,
    record_id,
    entity_id,
    data,
    *,
    captured_at=CAPTURED_AT,
    status=DataStatus.LIVE,
):
    return StandardRecord(
        dataset=dataset,
        schemaVersion="1.0",
        recordId=record_id,
        entityId=entity_id,
        capturedAt=captured_at,
        source=Source(providerId="fixture.deviation"),
        status=status,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="fixture/1",
        ),
        data=data,
    )


def _weekday_sessions_ending(
    end_date: date,
    count: int,
    *,
    closed_dates: tuple[date, ...] = (),
) -> tuple[date, ...]:
    closed = set(closed_dates)
    sessions: list[date] = []
    cursor = end_date
    while len(sessions) < count:
        if cursor.weekday() < 5 and cursor not in closed:
            sessions.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(sessions))


def test_client_computed_capability_uses_scenarios_and_shared_qfq_stock_raw_index_history():
    sessions = tuple(date(2026, 7, 1) + timedelta(days=index) for index in range(31))
    stock = equity("600519", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    collector = FixtureCollector(sessions, stock, benchmark)
    client = FinchX(collector=collector)

    result = client.market.deviation(
        stock,
        windows=(10, 30),
        as_of=sessions[-1],
    )

    assert result.dataset is COMPUTED_DEVIATION_DATASET
    assert result.provider is None
    assert result.data.rule_version == DEVIATION_RULE_VERSION
    assert [(item.window_days, item.scenario) for item in result.data.windows] == [
        (10, "pre_open"), (10, "current"), (10, "next_session"),
        (30, "pre_open"), (30, "current"), (30, "next_session"),
    ]
    assert result.data.as_of == result.data.effective_as_of == sessions[-1]
    assert result.data.calculation_mode == "scenario_based"
    kline_requests = [request for dataset, request, _ in collector.calls if dataset is MARKET_KLINES_DATASET]
    assert len(kline_requests) == 2
    assert kline_requests[0].adjustment is KlineAdjustment.QFQ
    assert kline_requests[1].adjustment is None
    assert collector.health.snapshot().dataset("market.deviation").successes == 1
    assert collector.quality.dataset("market.deviation").latest.has_data is True
    assert collector.observability.dataset("market.deviation").successes == 1


def test_suspension_gap_resets_with_stock_and_index_baselines_on_distinct_dates():
    effective_as_of = date(2026, 9, 24)
    sessions = _weekday_sessions_ending(effective_as_of, 31)
    halt_dates = tuple(
        day for day in sessions if date(2026, 9, 7) <= day <= date(2026, 9, 18)
    )
    assert len(halt_dates) == 10
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    resume_dates = tuple(date(2026, 9, day) for day in (21, 22, 23, 24))
    stock_closes = {
        date(2026, 9, 4): Decimal("80"),
        date(2026, 9, 21): Decimal("100"),
        date(2026, 9, 22): Decimal("120"),
        date(2026, 9, 23): Decimal("150"),
        date(2026, 9, 24): Decimal("200"),
    }
    benchmark_closes = {
        date(2026, 9, 18): Decimal("1000"),
        date(2026, 9, 21): Decimal("1000"),
        date(2026, 9, 22): Decimal("1001"),
        date(2026, 9, 23): Decimal("1002"),
        date(2026, 9, 24): Decimal("1003"),
    }
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        stock_close_overrides=stock_closes,
        benchmark_close_overrides=benchmark_closes,
    )

    result = DeviationService(collector).calculate(
        stock,
        windows=(10, 30),
        as_of=effective_as_of,
    )

    assert result.data.coverage_status == "halt_inferred_from_missing_kline"
    assert result.data.inferred_halt_dates == halt_dates
    assert len(result.data.windows) == 6
    current_windows = [window for window in result.data.windows if window.scenario == "current"]
    window_gap_dates = {
        window.window_days: tuple(day for day in halt_dates if day in sessions[-(window.window_days + 1) :])
        for window in current_windows
    }
    assert len(window_gap_dates[10]) == 7
    assert len(window_gap_dates[30]) == 10
    for window in current_windows:
        assert window.coverage_status == "halt_inferred_from_missing_kline"
        assert window.window_status == "partial_after_inferred_halt"
        assert window.window_days in (10, 30)
        assert window.available_trading_sessions == 4
        assert window.trading_sessions == 4
        assert window.start_date == resume_dates[0]
        assert window.stock_baseline_date == date(2026, 9, 4)
        assert window.benchmark_baseline_date == date(2026, 9, 18)
        assert window.inferred_halt_dates == window_gap_dates[window.window_days]
    assert current_windows[0].stock_return == Decimal("1.5")
    assert current_windows[0].benchmark_return == Decimal("0.003")
    assert current_windows[0].deviation == Decimal("1.497")
    assert result.metadata["coverage_status"] == "halt_inferred_from_missing_kline"
    assert result.metadata["inferred_halt_dates"] == tuple(day.isoformat() for day in halt_dates)
    assert any("not verified against an exchange notice" in warning for warning in result.warnings)
    assert any("4 resumed trading sessions" in warning for warning in result.warnings)


def test_multiple_internal_gaps_report_all_dates_and_reset_after_latest_gap():
    end_date = date(2026, 9, 24)
    sessions = _weekday_sessions_ending(end_date, 31)
    gap_dates = (sessions[22], sessions[27], sessions[28])
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    stock_closes = {
        sessions[21]: Decimal("80"),
        sessions[26]: Decimal("90"),
        sessions[29]: Decimal("100"),
        sessions[30]: Decimal("110"),
    }
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=gap_dates,
        stock_close_overrides=stock_closes,
    )

    result = DeviationService(collector).calculate(
        stock,
        windows=(10, 30),
        as_of=end_date,
    )

    assert result.data.inferred_halt_dates == gap_dates
    assert result.metadata["inferred_halt_dates"] == tuple(day.isoformat() for day in gap_dates)
    for window in (item for item in result.data.windows if item.scenario == "current"):
        expected_gaps = tuple(
            day for day in gap_dates if day in sessions[-(window.window_days + 1) :]
        )
        assert window.inferred_halt_dates == expected_gaps
        assert window.stock_baseline_date == sessions[26]
        assert window.benchmark_baseline_date == sessions[28]
        assert window.start_date == sessions[29]
        assert window.current_price == Decimal("110")
    assert any(", ".join(day.isoformat() for day in gap_dates) in warning for warning in result.warnings)


def test_gap_outside_ten_session_window_does_not_change_that_window():
    end_date = date(2026, 9, 24)
    sessions = _weekday_sessions_ending(end_date, 31)
    older_gap = (sessions[10],)
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=older_gap,
    )

    result = DeviationService(collector).calculate(
        stock,
        windows=(10, 30),
        as_of=end_date,
    )

    ten_day, thirty_day = [
        item for item in result.data.windows if item.scenario == "current"
    ]
    assert ten_day.window_days == 10
    assert ten_day.coverage_status == "complete"
    assert ten_day.inferred_halt_dates == ()
    assert ten_day.stock_baseline_date == ten_day.benchmark_baseline_date
    assert thirty_day.window_days == 30
    assert thirty_day.coverage_status == "halt_inferred_from_missing_kline"
    assert thirty_day.inferred_halt_dates == older_gap
    assert result.data.inferred_halt_dates == older_gap


def test_single_internal_stock_kline_gap_is_inferred_but_index_gap_is_no_data():
    end_date = date(2026, 9, 24)
    sessions = _weekday_sessions_ending(end_date, 11)
    internal_gap = (sessions[5],)
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=internal_gap,
    )

    result = DeviationService(collector).calculate(
        stock,
        windows=(10,),
        as_of=end_date,
    )

    window = next(item for item in result.data.windows if item.scenario == "current")
    assert window.coverage_status == "halt_inferred_from_missing_kline"
    assert window.inferred_halt_dates == internal_gap
    assert window.stock_baseline_date == sessions[4]
    assert window.benchmark_baseline_date == sessions[5]
    assert window.start_date == sessions[6]

    short_history_and_gap = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=tuple(sessions[:3]) + internal_gap,
    )
    combined = DeviationService(short_history_and_gap).calculate(
        stock,
        windows=(10,),
        as_of=end_date,
    )
    combined_window = combined.data.windows[0]
    assert combined_window.coverage_status == "short_history_and_halt_inferred_from_missing_kline"
    assert combined_window.window_status == "partial_short_history_and_inferred_halt"
    assert combined_window.inferred_halt_dates == internal_gap
    assert any("leading dates" in warning for warning in combined.warnings)
    assert any("partial after the inferred halt" in warning for warning in combined.warnings)

    missing_index_date = sessions[7]
    index_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_benchmark_dates=(missing_index_date,),
    )
    with pytest.raises(DeviationCoverageError) as captured:
        DeviationService(index_collector).calculate(
            stock,
            windows=(10,),
            as_of=end_date,
        )
    error = captured.value
    assert isinstance(error, NoData)
    assert error.reason_code == "missing_benchmark_closes"
    assert error.requested_as_of == end_date
    assert error.effective_as_of == date(2026, 9, 23)
    assert error.required_count == 10
    assert error.observed_stock_count == 10
    assert error.observed_benchmark_count == 9
    assert error.missing_benchmark_dates == (missing_index_date,)


def test_short_history_returns_with_two_comparable_closes_and_one_close_fails():
    end_date = date(2026, 9, 24)
    sessions = _weekday_sessions_ending(end_date, 31)
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    available_dates = sessions[-5:]
    missing_prefix = sessions[:-5]
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=missing_prefix,
        stock_adjustment=KlineAdjustment.NONE,
    )

    result = DeviationService(collector).calculate(
        stock,
        windows=(10, 30),
        as_of=end_date,
    )
    assert result.data.coverage_status == "short_history"
    assert result.data.price_basis == "raw_stock__raw_index"
    assert result.metadata["actual_adjustment"] == "none"
    assert not any(dataset is MARKET_QUOTE_SNAPSHOT_DATASET for dataset, _, _ in collector.calls)
    for window in (item for item in result.data.windows if item.scenario == "current"):
        assert window.coverage_status == "short_history"
        assert window.window_status == "partial_short_history"
        assert window.available_trading_sessions == 4
        assert window.end_date == end_date
        assert window.baseline_date in available_dates
    assert any("short listing history" in warning for warning in result.warnings)

    two_close_stock = {
        sessions[-3]: Decimal("10"),
        sessions[-2]: Decimal("10"),
        sessions[-1]: Decimal("12"),
    }
    two_close_index = {
        sessions[-3]: Decimal("100"),
        sessions[-2]: Decimal("100"),
        sessions[-1]: Decimal("110"),
    }
    two_close_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=sessions[:-3],
        stock_close_overrides=two_close_stock,
        benchmark_close_overrides=two_close_index,
    )
    two_close = DeviationService(two_close_collector).calculate(
        stock,
        windows=(10,),
        as_of=end_date,
    )
    two_close = next(item for item in two_close.data.windows if item.scenario == "current")
    assert two_close.window_status == "partial_short_history"
    assert two_close.trading_sessions == 2
    assert two_close.available_trading_sessions == 2
    assert two_close.stock_baseline_date == sessions[-3]
    assert two_close.stock_return == Decimal("0.2")
    assert two_close.benchmark_return == Decimal("0.1")
    assert two_close.deviation == Decimal("0.1")

    one_close_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=sessions[:-1],
        stock_adjustment=KlineAdjustment.NONE,
    )
    with pytest.raises(DeviationCoverageError) as captured:
        DeviationService(one_close_collector).calculate(
            stock,
            windows=(10,),
            as_of=end_date,
        )
    assert captured.value.reason_code == "missing_effective_asof_stock_close"
    assert captured.value.effective_as_of == sessions[-2]
    assert captured.value.missing_stock_dates == sessions[-12:-1]


def test_same_day_as_of_uses_daily_bars_after_close_and_next_session_calendar_boundary():
    end_date = date(2026, 9, 28)
    closures = tuple(date(2026, 9, day) for day in (25, 26, 27))
    sessions = _weekday_sessions_ending(end_date, 31, closed_dates=closures)
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    halt_dates = tuple(
        day for day in sessions if date(2026, 9, 7) <= day <= date(2026, 9, 18)
    )

    same_day_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        closed_dates=closures,
    )
    same_day_service = DeviationService(
        same_day_collector,
        clock=lambda: datetime(2026, 9, 28, 15, 59, tzinfo=timezone(timedelta(hours=8))),
    )
    same_day = same_day_service.calculate(
        stock,
        windows=(10,),
        as_of=date(2026, 9, 28),
    )
    assert same_day.data.as_of == same_day.data.effective_as_of == end_date
    pre_open, current, next_session = same_day.data.windows
    assert pre_open.scenario == "pre_open"
    assert pre_open.end_date == pre_open.target_date == date(2026, 9, 24)
    assert pre_open.available_trading_sessions == 4
    assert current.scenario == "current"
    assert current.end_date == current.target_date == end_date
    assert current.available_trading_sessions == 5
    assert current.stock_source_timestamp is None
    assert current.benchmark_source_timestamp is None
    assert next_session.scenario == "next_session"
    assert next_session.end_date == end_date
    assert next_session.target_date == date(2026, 9, 29)
    assert next_session.available_trading_sessions == 5
    assert next_session.current_price == current.current_price
    same_day_quote_calls = [
        (dataset, request)
        for dataset, request, _ in same_day_collector.calls
        if dataset is MARKET_QUOTE_SNAPSHOT_DATASET
    ]
    assert same_day_quote_calls == []
    assert same_day.metadata["price_inputs"] == "same_day_daily_bars"
    assert same_day.metadata["stock_terminal_source"] == "same_day_daily_bar"
    assert same_day.metadata["benchmark_terminal_source"] == "same_day_daily_bar"

    after_close_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        closed_dates=closures,
    )
    after_close = DeviationService(
        after_close_collector,
        clock=lambda: datetime(2026, 9, 28, 16, 0, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(
        stock,
        windows=(10,),
        as_of=date(2026, 9, 28),
    )
    assert after_close.data.as_of == after_close.data.effective_as_of == date(2026, 9, 28)
    assert after_close.data.windows[1].end_date == date(2026, 9, 28)
    assert after_close.data.windows[1].stock_source_timestamp is None
    assert after_close.data.windows[1].available_trading_sessions == 5
    assert after_close.metadata["price_inputs"] == "same_day_daily_bars"
    assert after_close.data.windows[0].stock_source_timestamp is None
    assert not any(dataset is MARKET_QUOTE_SNAPSHOT_DATASET for dataset, _, _ in after_close_collector.calls)

    postclose_time = datetime(
        2026, 9, 28, 16, 14, 52, tzinfo=timezone(timedelta(hours=8))
    )
    postclose_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        closed_dates=closures,
        quote_timestamp=postclose_time,
    )
    postclose = DeviationService(
        postclose_collector,
        clock=lambda: datetime(2026, 9, 28, 16, 20, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(stock, windows=(10,), as_of=date(2026, 9, 28))
    assert postclose.data.windows[1].stock_source_timestamp is None
    assert not any(dataset is MARKET_QUOTE_SNAPSHOT_DATASET for dataset, _, _ in postclose_collector.calls)

    last_preclose_quote = datetime(
        2026, 9, 28, 14, 59, tzinfo=timezone(timedelta(hours=8))
    )
    preclose_quote_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        closed_dates=closures,
        stock_quote_price=Decimal("999"),
        quote_timestamp=last_preclose_quote,
    )
    preclose_quote = DeviationService(
        preclose_quote_collector,
        clock=lambda: datetime(2026, 9, 28, 16, 0, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(stock, windows=(10,), as_of=date(2026, 9, 28))
    assert preclose_quote.data.windows[1].stock_source_timestamp is None
    assert preclose_quote.metadata["stock_terminal_source"] == "same_day_daily_bar"
    assert not any(dataset is MARKET_QUOTE_SNAPSHOT_DATASET for dataset, _, _ in preclose_quote_collector.calls)

    mismatched_stock_bar_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        closed_dates=closures,
        stock_quote_price=Decimal("999"),
        quote_timestamp=datetime(
            2026, 9, 28, 15, 1, tzinfo=timezone(timedelta(hours=8))
        ),
    )
    mismatched_stock_bar = DeviationService(
        mismatched_stock_bar_collector,
        clock=lambda: datetime(2026, 9, 28, 16, 0, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(stock, windows=(10,), as_of=date(2026, 9, 28))
    assert mismatched_stock_bar.data.windows[1].stock_source_timestamp is None
    assert mismatched_stock_bar.metadata["stock_terminal_source"] == "same_day_daily_bar"
    assert not any(dataset is MARKET_QUOTE_SNAPSHOT_DATASET for dataset, _, _ in mismatched_stock_bar_collector.calls)

    stale_quote_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        closed_dates=closures,
        quote_timestamp=datetime(
            2026, 9, 28, 9, 20, tzinfo=timezone(timedelta(hours=8))
        ),
    )
    with pytest.raises(NoData, match="stale for the current session"):
        DeviationService(
            stale_quote_collector,
            clock=lambda: datetime(2026, 9, 28, 10, 0, tzinfo=timezone(timedelta(hours=8))),
        ).calculate(stock, windows=(10,), as_of=date(2026, 9, 28))

    failed_quote_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        closed_dates=closures,
        quote_timestamp=datetime(
            2026, 9, 28, 9, 55, tzinfo=timezone(timedelta(hours=8))
        ),
        quote_status=DataStatus.FAILED,
    )
    with pytest.raises(NoData, match="status is not live"):
        DeviationService(
            failed_quote_collector,
            clock=lambda: datetime(2026, 9, 28, 10, 0, tzinfo=timezone(timedelta(hours=8))),
        ).calculate(stock, windows=(10,), as_of=date(2026, 9, 28))

    prior_day_quote_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=(date(2026, 9, 28),),
        closed_dates=closures,
        quote_timestamp=datetime(
            2026, 9, 24, 15, 0, tzinfo=timezone(timedelta(hours=8))
        ),
    )
    with pytest.raises(NoData, match="stale: expected 2026-09-28, received 2026-09-24"):
        DeviationService(
            prior_day_quote_collector,
            clock=lambda: datetime(2026, 9, 28, 16, 0, tzinfo=timezone(timedelta(hours=8))),
        ).calculate(stock, windows=(10,), as_of=date(2026, 9, 28))

    missing_current_close_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates + (date(2026, 9, 28),),
        closed_dates=closures,
    )
    with pytest.raises(NoData, match="sourceTimestamp is in the future"):
        DeviationService(
            missing_current_close_collector,
            clock=lambda: datetime(2026, 9, 28, 8, 0, tzinfo=timezone(timedelta(hours=8))),
        ).calculate(
            stock,
            windows=(10,),
            as_of=date(2026, 9, 28),
        )

    next_day_collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        closed_dates=closures,
    )
    next_day_service = DeviationService(
        next_day_collector,
        clock=lambda: datetime(2026, 9, 29, 8, 0, tzinfo=timezone(timedelta(hours=8))),
    )
    next_day = next_day_service.calculate(
        stock,
        windows=(10,),
        as_of=date(2026, 9, 28),
    )
    assert next_day.data.as_of == next_day.data.effective_as_of == date(2026, 9, 28)
    assert next_day.data.windows[1].end_date == date(2026, 9, 28)
    assert next_day.data.windows[1].stock_source_timestamp is None
    assert next_day.data.windows[2].target_date == date(2026, 9, 29)


@pytest.mark.parametrize(
    ("missing_stock", "missing_index", "stock_quote", "index_quote"),
    [
        (True, False, None, None),
        (False, True, None, None),
        (True, True, None, None),
        (False, True, Decimal("999"), None),
        (True, False, None, Decimal("9999")),
        (False, False, Decimal("999"), Decimal("9999")),
    ],
    ids=("stock-bar-missing", "index-bar-missing", "both-bars-missing", "stock-bar-preferred-over-mismatched-quote", "index-bar-preferred-over-mismatched-quote", "both-bars-present"),
)
def test_postclose_prefers_each_available_daily_bar_and_quotes_only_missing_sides(
    missing_stock, missing_index, stock_quote, index_quote
):
    end_date = date(2026, 9, 28)
    closures = tuple(date(2026, 9, day) for day in (25, 26, 27))
    sessions = _weekday_sessions_ending(end_date, 31, closed_dates=closures)
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=(end_date,) if missing_stock else (),
        missing_benchmark_dates=(end_date,) if missing_index else (),
        closed_dates=closures,
        stock_quote_price=stock_quote,
        benchmark_quote_price=index_quote,
        quote_timestamp=datetime(
            2026, 9, 28, 14, 59, tzinfo=timezone(timedelta(hours=8))
        ),
    )

    result = DeviationService(
        collector,
        clock=lambda: datetime(2026, 9, 28, 16, 0, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(stock, windows=(10,), as_of=end_date)

    current = result.data.windows[1]
    next_session = result.data.windows[2]
    default_stock_bar = Decimal(100 + len(sessions) - 1)
    default_index_bar = Decimal(1000 + 2 * (len(sessions) - 1))
    expected_stock_price = (
        stock_quote if missing_stock and stock_quote is not None else default_stock_bar
    )
    expected_index_price = (
        index_quote if missing_index and index_quote is not None else default_index_bar
    )
    assert current.current_price == next_session.current_price == expected_stock_price
    assert current.benchmark_current == next_session.benchmark_current == expected_index_price
    assert current.stock_source_timestamp == next_session.stock_source_timestamp
    assert current.benchmark_source_timestamp == next_session.benchmark_source_timestamp
    assert (current.stock_source_timestamp is not None) is missing_stock
    assert (current.benchmark_source_timestamp is not None) is missing_index
    expected_quote_codes = {
        identity.code
        for identity, missing in ((stock, missing_stock), (benchmark, missing_index))
        if missing
    }
    quote_requests = [
        request.instrument_id.code
        for dataset, request, _ in collector.calls
        if dataset is MARKET_QUOTE_SNAPSHOT_DATASET
    ]
    assert set(quote_requests) == expected_quote_codes
    assert len(quote_requests) == len(expected_quote_codes)
    provenance_providers = {source.provider_id for source in result.provenance}
    assert "fixture.deviation" in provenance_providers
    assert ("fixture.quote" in provenance_providers) is bool(expected_quote_codes)
    assert current.stock_source_timestamp == (
        datetime(2026, 9, 28, 14, 59, tzinfo=timezone(timedelta(hours=8)))
        if missing_stock else None
    )
    assert current.benchmark_source_timestamp == (
        datetime(2026, 9, 28, 14, 59, tzinfo=timezone(timedelta(hours=8)))
        if missing_index else None
    )
    expected_price_inputs = (
        "same_day_quotes"
        if len(expected_quote_codes) == 2
        else "same_day_daily_bars_with_quote_fallback"
        if len(expected_quote_codes) == 1
        else "same_day_daily_bars"
    )
    assert result.metadata["price_inputs"] == expected_price_inputs
    assert result.metadata["stock_terminal_source"] == (
        "same_day_quote" if missing_stock else "same_day_daily_bar"
    )
    assert result.metadata["benchmark_terminal_source"] == (
        "same_day_quote" if missing_index else "same_day_daily_bar"
    )
    assert result.metadata["terminal_source_scope"] == ("current", "next_session")
    assert bool(result.warnings) is bool(expected_quote_codes)
    if missing_stock:
        assert "stock" in result.warnings[0]
    if missing_index:
        assert "benchmark index" in result.warnings[0]
    assert result.data.windows[0].stock_source_timestamp is None
    assert result.data.windows[0].benchmark_source_timestamp is None


def test_intraday_quote_before_1500_is_used_with_existing_freshness_check():
    end_date = date(2026, 9, 28)
    closures = tuple(date(2026, 9, day) for day in (25, 26, 27))
    sessions = _weekday_sessions_ending(end_date, 31, closed_dates=closures)
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    quote_time = datetime(2026, 9, 28, 14, 25, tzinfo=timezone(timedelta(hours=8)))
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        closed_dates=closures,
        stock_quote_price=Decimal("999"),
        quote_timestamp=quote_time,
    )

    result = DeviationService(
        collector,
        clock=lambda: datetime(2026, 9, 28, 14, 30, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(stock, windows=(10,), as_of=end_date)

    assert result.data.windows[1].current_price == Decimal("999")
    assert result.data.windows[1].stock_source_timestamp == quote_time
    assert not result.warnings
    assert result.metadata["price_inputs"] == "same_day_quotes_with_daily_history"
    assert result.metadata["stock_terminal_source"] == "same_day_quote"
    assert result.data.windows[0].end_date == date(2026, 9, 24)


def test_historical_as_of_keeps_daily_bar_inputs_and_no_quote_close_warning():
    end_date = date(2026, 9, 24)
    sessions = _weekday_sessions_ending(end_date, 31)
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    collector = FixtureCollector(sessions, stock, benchmark)

    result = DeviationService(
        collector,
        clock=lambda: datetime(2026, 9, 29, 16, 0, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(stock, windows=(10,), as_of=end_date)

    assert result.metadata["price_inputs"] == "historical_daily_bars"
    assert result.metadata["stock_source_timestamp"] is None
    assert result.metadata["benchmark_source_timestamp"] is None
    assert not any("quote fallback" in warning for warning in result.warnings)
    assert [window.stock_source_timestamp for window in result.data.windows] == [None, None, None]


def test_captured_tencent_closes_reproduce_sep_28_five_session_deviation():
    """Keep the captured Tencent 600825/000002 closes as an offline regression."""

    end_date = date(2026, 9, 28)
    closed_dates = tuple(date(2026, 9, day) for day in (25, 26, 27))
    sessions = _weekday_sessions_ending(end_date, 31, closed_dates=closed_dates)
    halt_dates = tuple(
        day for day in sessions if date(2026, 9, 7) <= day <= date(2026, 9, 18)
    )
    stock = equity("600825", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    stock_closes = {
        date(2026, 9, 4): Decimal("5.31"),
        date(2026, 9, 21): Decimal("5.84"),
        date(2026, 9, 22): Decimal("6.42"),
        date(2026, 9, 23): Decimal("7.06"),
        date(2026, 9, 24): Decimal("7.77"),
        date(2026, 9, 28): Decimal("8.55"),
    }
    benchmark_closes = {
        date(2026, 9, 18): Decimal("4101.66"),
        date(2026, 9, 21): Decimal("4141.56"),
        date(2026, 9, 22): Decimal("4143.88"),
        date(2026, 9, 23): Decimal("4127.45"),
        date(2026, 9, 24): Decimal("4076.91"),
        date(2026, 9, 28): Decimal("4008.96"),
    }
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        missing_stock_dates=halt_dates,
        closed_dates=closed_dates,
        stock_close_overrides=stock_closes,
        benchmark_close_overrides=benchmark_closes,
    )
    service = DeviationService(
        collector,
        clock=lambda: datetime(2026, 9, 28, 16, 0, tzinfo=timezone(timedelta(hours=8))),
    )

    result = service.calculate(
        stock,
        windows=(10,),
        as_of=end_date,
    )

    window = result.data.windows[1]
    assert result.data.effective_as_of == end_date
    assert window.trading_sessions == 5
    assert window.available_trading_sessions == 5
    assert window.coverage_status == "halt_inferred_from_missing_kline"
    assert window.window_status == "partial_after_inferred_halt"
    assert window.start_date == date(2026, 9, 21)
    assert window.stock_baseline_date == date(2026, 9, 4)
    assert window.benchmark_baseline_date == date(2026, 9, 18)
    assert window.stock_baseline_price == Decimal("5.31")
    assert window.window_start_price == Decimal("5.84")
    assert window.current_price == Decimal("8.55")
    assert window.benchmark_start == Decimal("4101.66")
    assert window.benchmark_current == Decimal("4008.96")
    assert window.deviation == pytest.approx(
        Decimal("0.6327700971"), abs=Decimal("0.0000000001")
    )
    assert any("5 resumed trading sessions" in warning for warning in result.warnings)

    next_window = result.data.windows[2]
    assert next_window.start_date == date(2026, 9, 21)
    assert next_window.stock_baseline_date == window.stock_baseline_date
    assert next_window.deviation == window.deviation


def test_d10_quote_updates_do_not_change_pre_open_qfq_results():
    observation_date = date(2026, 9, 28)
    closures = tuple(date(2026, 9, day) for day in (25, 26, 27))
    sessions = _weekday_sessions_ending(observation_date, 31, closed_dates=closures)
    stock = equity("600519", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    quote_time = datetime(2026, 9, 28, 13, 55, tzinfo=timezone(timedelta(hours=8)))

    def calculate(quote_price: Decimal):
        collector = FixtureCollector(
            sessions,
            stock,
            benchmark,
            closed_dates=closures,
            stock_quote_price=quote_price,
            quote_timestamp=quote_time,
        )
        return DeviationService(
            collector,
            clock=lambda: datetime(2026, 9, 28, 14, 0, tzinfo=timezone(timedelta(hours=8))),
        ).calculate(stock, windows=(10,), as_of=observation_date)

    first = calculate(Decimal("131"))
    second = calculate(Decimal("262"))
    pre_open_first, current_first, _ = first.data.windows
    pre_open_second, current_second, _ = second.data.windows

    assert pre_open_first.current_price == pre_open_second.current_price
    assert pre_open_first.deviation == pre_open_second.deviation
    assert pre_open_first.upper_trigger_price == pre_open_second.upper_trigger_price
    assert current_first.current_price != current_second.current_price
    assert current_first.deviation != current_second.deviation
    assert first.metadata["stock_qfq_quote_bridge_date"] == sessions[-2].isoformat()


def test_unadjusted_day_fallback_continues_deviation_without_qfq_quote_bridge():
    observation_date = date(2026, 9, 28)
    closures = tuple(date(2026, 9, day) for day in (25, 26, 27))
    sessions = _weekday_sessions_ending(observation_date, 31, closed_dates=closures)
    stock = equity("600519", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    quote_time = datetime(2026, 9, 28, 13, 55, tzinfo=timezone(timedelta(hours=8)))
    collector = FixtureCollector(
        sessions,
        stock,
        benchmark,
        stock_adjustment=KlineAdjustment.NONE,
        stock_quote_price=Decimal("160"),
        stock_quote_previous_close=Decimal("9999"),
        quote_timestamp=quote_time,
    )

    result = DeviationService(
        collector,
        clock=lambda: datetime(2026, 9, 28, 14, 0, tzinfo=timezone(timedelta(hours=8))),
    ).calculate(stock, windows=(10,), as_of=observation_date)

    current = next(item for item in result.data.windows if item.scenario == "current")
    assert result.data.price_basis == "raw_stock__raw_index"
    assert result.metadata["requested_adjustment"] == "qfq"
    assert result.metadata["actual_adjustment"] == "none"
    assert result.metadata["source_series"] == "day"
    assert result.metadata["stock_qfq_quote_bridge_ratio"] is None
    assert result.metadata["stock_qfq_quote_bridge_date"] is None
    assert current.current_price == Decimal("160")
    assert current.stock_baseline_price == Decimal(
        100 + sessions.index(current.stock_baseline_date)
    )
    assert any("not forward-adjusted" in warning for warning in result.warnings)


def test_computed_result_matches_packaged_json_schema():
    from finchx.schemas import read_schema
    from referencing import Registry, Resource
    from jsonschema import Draft202012Validator, FormatChecker

    result = FinchX(collector=FixtureCollector(
        tuple(date(2026, 7, 1) + timedelta(days=index) for index in range(31)),
        equity("600519", Exchange.SSE),
        resolve_deviation_benchmark(equity("600519", Exchange.SSE)).instrument,
    )).market.deviation(
        equity("600519", Exchange.SSE),
        as_of=date(2026, 7, 31),
        windows=(10,),
    )
    schema = read_schema("market-deviation.schema.json")
    identity_schema = read_schema("instrument-identity.schema.json")
    registry = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
    registry = registry.with_resource(identity_schema["$id"], Resource.from_contents(identity_schema))
    validator = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
    validator.validate(result.data.model_dump(mode="json", by_alias=True))
