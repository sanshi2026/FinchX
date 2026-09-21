from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from finchx import FinchX
from finchx.collectors import FetchResult
from finchx.collectors.errors import InvalidRequest
from finchx.computed import (
    COMPUTED_DEVIATION_DATASET,
    DEVIATION_RULE_VERSION,
    BenchmarkSpec,
    DeviationWindowConvention,
    PricePoint,
    calculate_deviation,
    resolve_deviation_benchmark,
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
    TradingCalendarRequest,
)
from finchx.datasets.market_klines import MarketKlineData
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
        window_convention=DeviationWindowConvention.STRICT_EXCHANGE_WINDOW,
    )

    assert result.stock_return == Decimal("0.8")
    assert result.benchmark_return == Decimal("0.2")
    assert result.deviation == Decimal("0.6")
    assert result.upper_threshold == Decimal("1.00")
    assert result.upper_trigger_price == Decimal("220.0")
    assert result.remaining_to_upper == Decimal("0.4")


class FixtureCollector:
    def __init__(self, sessions: tuple[date, ...], stock: InstrumentId, benchmark: InstrumentId):
        self.sessions = sessions
        self.stock = stock
        self.benchmark = benchmark
        self.calls: list[tuple[object, object, str | None]] = []
        self.health = HealthMonitor()
        self.quality = QualityMonitor(clock=lambda: CAPTURED_AT)
        self.observability = ObservabilityMonitor()
        self._source = Source(providerId="fixture.deviation")

    def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
        request = kwargs["request"]
        self.calls.append((dataset, request, provider))
        if dataset is TRADING_CALENDAR_DATASET:
            data = tuple(
                _record(
                    TRADING_CALENDAR_DATASET.name,
                    f"calendar:{day.isoformat()}",
                    "CN_A:" + day.isoformat(),
                    {"date": day.isoformat(), "isTradingDay": True},
                )
                for day in self.sessions
            )
            return FetchResult(
                data=data,
                dataset=TRADING_CALENDAR_DATASET,
                provider="fixture.calendar",
                captured_at=CAPTURED_AT,
                provenance=(self._source,),
            )
        assert dataset is MARKET_KLINES_DATASET
        identity = request.instrument_id
        assert isinstance(request, KlinesRequest)
        if identity == self.stock:
            closes = [Decimal(100 + index) for index in range(len(self.sessions))]
            assert request.adjustment is KlineAdjustment.QFQ
        else:
            assert identity == self.benchmark
            closes = [Decimal(1000 + 2 * index) for index in range(len(self.sessions))]
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
                    adjustment=(request.adjustment or KlineAdjustment.NOT_APPLICABLE),
                ).model_dump(mode="json", by_alias=True),
            )
            for day, close in zip(self.sessions, closes)
        )
        return FetchResult(
            data=data,
            dataset=MARKET_KLINES_DATASET,
            provider=provider or "fixture.klines",
            captured_at=CAPTURED_AT,
            provenance=(self._source,),
        )


def _record(dataset, record_id, entity_id, data):
    return StandardRecord(
        dataset=dataset,
        schemaVersion="1.0",
        recordId=record_id,
        entityId=entity_id,
        capturedAt=CAPTURED_AT,
        source=Source(providerId="fixture.deviation"),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="fixture/1",
        ),
        data=data,
    )


def test_client_computed_capability_uses_strict_qfq_stock_and_raw_index():
    sessions = tuple(date(2026, 7, 1) + timedelta(days=index) for index in range(31))
    stock = equity("600519", Exchange.SSE)
    benchmark = resolve_deviation_benchmark(stock).instrument
    collector = FixtureCollector(sessions, stock, benchmark)
    client = FinchX(collector=collector)

    result = client.market.deviation(stock, windows=(10, 30), as_of=sessions[-1])

    assert result.dataset is COMPUTED_DEVIATION_DATASET
    assert result.provider is None
    assert result.data.rule_version == DEVIATION_RULE_VERSION
    assert [item.window_days for item in result.data.windows] == [10, 30]
    kline_requests = [request for dataset, request, _ in collector.calls if dataset is MARKET_KLINES_DATASET]
    assert len(kline_requests) == 2
    assert kline_requests[0].adjustment is KlineAdjustment.QFQ
    assert kline_requests[1].adjustment is None
    assert collector.health.snapshot().dataset("market.deviation").successes == 1
    assert collector.quality.dataset("market.deviation").latest.has_data is True
    assert collector.observability.dataset("market.deviation").successes == 1


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
