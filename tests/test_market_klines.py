from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from finchx.contracts import Source
from finchx.datasets import (
    MARKET_KLINES_DATASET,
    MarketKlineData,
    KlineAdjustment,
    KlinesRequest,
)
from finchx.datasets.market_klines import (
    _ProviderKlineRow,
    _normalize_klines_rows,
    _kline_record_id,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol


CAPTURED_AT = datetime(2026, 9, 18, 2, 20, tzinfo=timezone.utc)
SOURCE = Source(
    providerId="tencent.finance.qq",
    sourceUrl="https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get",
)


def instrument(
    code="600519",
    *,
    exchange=Exchange.SSE,
    kind=InstrumentKind.EQUITY,
):
    return InstrumentId(
        code=code,
        market=Market.CN_A,
        exchange=exchange,
        kind=kind,
    )


def request(
    *,
    identity=None,
    start=date(2025, 6, 12),
    end=date(2025, 6, 12),
    adjustment=KlineAdjustment.QFQ,
):
    return KlinesRequest(
        instrumentId=identity or instrument(),
        startDate=start,
        endDate=end,
        adjustment=adjustment,
    )


def bar(
    *,
    identity=None,
    day=date(2025, 6, 12),
    adjustment=KlineAdjustment.QFQ,
    amount=Decimal("123.45"),
    open_value=Decimal("10"),
    high=Decimal("12"),
    low=Decimal("9"),
    close=Decimal("11"),
    volume=100,
):
    return MarketKlineData(
        instrumentId=identity or instrument(),
        barDate=day,
        open=open_value,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        adjustment=adjustment,
    )


def test_request_accepts_verified_equity_routes_and_inclusive_date_bounds():
    same_day = request()
    assert same_day.start_date == same_day.end_date == date(2025, 6, 12)

    ranged = request(
        identity=instrument("000001", exchange=Exchange.SZSE),
        start=date(2025, 6, 1),
        end=date(2025, 6, 30),
        adjustment="none",
    )
    assert ranged.instrument_id.exchange is Exchange.SZSE
    assert ranged.adjustment is KlineAdjustment.NONE
    assert MARKET_KLINES_DATASET.name == "market.klines"
    assert MARKET_KLINES_DATASET.schema_version == "1.0"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": date(2025, 6, 13), "end": date(2025, 6, 12)},
        {"start": datetime(2025, 6, 12), "end": date(2025, 6, 12)},
        {"adjustment": KlineAdjustment.NOT_APPLICABLE},
        {"identity": instrument("000001", exchange=Exchange.SSE)},
        {"identity": instrument("600519", exchange=Exchange.SZSE)},
        {"identity": instrument("600519", exchange=None)},
        {"identity": instrument("430001", exchange=Exchange.BSE)},
        {"identity": instrument("399001", kind=InstrumentKind.INDEX)},
        {"identity": instrument("510300", kind=InstrumentKind.ETF)},
    ],
)
def test_request_rejects_reversed_dates_unsupported_identity_or_adjustment(kwargs):
    with pytest.raises(ValidationError):
        request(**kwargs)


def test_request_requires_explicit_adjustment():
    with pytest.raises(ValidationError):
        KlinesRequest(
            instrumentId=instrument(),
            startDate=date(2025, 6, 12),
            endDate=date(2025, 6, 12),
        )


def test_contract_enforces_ohlc_order_and_nonnegative_amount_without_overconstraining_prices():
    valid_zero = bar(
        open_value=Decimal("0"),
        high=Decimal("0"),
        low=Decimal("0"),
        close=Decimal("0"),
        volume=0,
        amount=Decimal("0"),
    )
    assert valid_zero.volume == 0
    assert valid_zero.amount == 0

    valid_negative_adjusted = bar(
        open_value=Decimal("-2"),
        high=Decimal("-1"),
        low=Decimal("-3"),
        close=Decimal("-2.5"),
        adjustment=KlineAdjustment.HFQ,
    )
    assert valid_negative_adjusted.open == Decimal("-2")

    with pytest.raises(ValidationError):
        bar(high=Decimal("8"))
    with pytest.raises(ValidationError):
        bar(amount=Decimal("-0.01"))
    with pytest.raises(ValidationError):
        bar(volume=-1)


def test_normalizer_sorts_bars_and_preserves_date_time_units_and_partial_amount():
    req = request(start=date(2025, 6, 11), end=date(2025, 6, 13))
    bars = (
        _ProviderKlineRow(data=bar(day=date(2025, 6, 13), amount=None)),
        _ProviderKlineRow(data=bar(day=date(2025, 6, 11))),
    )
    records = _normalize_klines_rows(req, bars, source=SOURCE, captured_at=CAPTURED_AT)

    assert [record.data["barDate"] for record in records] == ["2025-06-11", "2025-06-13"]
    assert {record.captured_at for record in records} == {CAPTURED_AT}
    assert all(record.event_at is None and record.as_of is None for record in records)
    assert all(record.entity_id == req.instrument_id for record in records)
    assert all(record.dataset == "market.klines" for record in records)
    assert all(record.provenance.adjustments[0].name == "qfq" for record in records)
    assert records[0].data["open"] == "10"
    assert records[0].data["volume"] == 100
    assert records[0].data["amount"] == "123.45"
    assert records[1].data["amount"] is None
    assert records[1].quality.issues[0].kind.value == "partial"


def test_record_identity_distinguishes_each_adjustment_for_the_same_bar():
    identity = instrument()
    ids = {
        _kline_record_id(identity, date(2026, 9, 17), mode)
        for mode in (
            KlineAdjustment.NONE,
            KlineAdjustment.QFQ,
            KlineAdjustment.HFQ,
        )
    }
    assert len(ids) == 3
    assert all(value.startswith(f"{format_symbol(identity)}@2026-09-17@") for value in ids)


@pytest.mark.parametrize(
    "wrong_bar",
    [
        bar(identity=instrument("000001", exchange=Exchange.SZSE)),
        bar(day=date(2025, 6, 11)),
        bar(adjustment=KlineAdjustment.NONE),
    ],
)
def test_normalizer_rejects_wrong_identity_range_or_adjustment(wrong_bar):
    with pytest.raises(ValueError):
        _normalize_klines_rows(
            request(),
            (_ProviderKlineRow(data=wrong_bar),),
            source=SOURCE,
            captured_at=CAPTURED_AT,
        )


def test_normalizer_rejects_duplicate_dates_and_naive_capture_times():
    same_day = bar()
    with pytest.raises(ValueError, match="duplicate"):
        _normalize_klines_rows(
            request(),
            (_ProviderKlineRow(data=same_day), _ProviderKlineRow(data=same_day)),
            source=SOURCE,
            captured_at=CAPTURED_AT,
        )
    with pytest.raises(ValueError, match="naive"):
        _normalize_klines_rows(
            request(),
            (_ProviderKlineRow(data=same_day, captured_at=datetime(2025, 6, 12)),),
            source=SOURCE,
            captured_at=CAPTURED_AT,
        )


@pytest.mark.parametrize(
    ("exchange", "code"),
    [
        (Exchange.SSE, "000001"),
        (Exchange.SZSE, "399001"),
        (Exchange.SZSE, "399006"),
    ],
)
def test_index_request_omits_adjustment_and_result_uses_not_applicable(exchange, code):
    identity = instrument(code, exchange=exchange, kind=InstrumentKind.INDEX)
    req = KlinesRequest(
        instrumentId=identity,
        startDate=date(2026, 9, 17),
        endDate=date(2026, 9, 18),
    )
    result = bar(identity=identity, day=date(2026, 9, 17), adjustment=KlineAdjustment.NOT_APPLICABLE)
    records = _normalize_klines_rows(
        req,
        (_ProviderKlineRow(data=result),),
        source=SOURCE,
        captured_at=CAPTURED_AT,
    )
    assert records[0].record_id == f"{format_symbol(identity)}@2026-09-17@not_applicable"
    assert records[0].data["adjustment"] == "not_applicable"
    assert records[0].provenance.adjustments[0].name == "not_applicable"


@pytest.mark.parametrize(
    "adjustment",
    [None, KlineAdjustment.NONE, KlineAdjustment.QFQ, KlineAdjustment.HFQ, KlineAdjustment.NOT_APPLICABLE],
)
def test_index_request_rejects_any_explicit_adjustment(adjustment):
    identity = instrument("000001", exchange=Exchange.SSE, kind=InstrumentKind.INDEX)
    with pytest.raises(ValidationError, match="omit adjustment"):
        KlinesRequest(
            instrumentId=identity,
            startDate=date(2026, 9, 17),
            endDate=date(2026, 9, 17),
            adjustment=adjustment,
        )


@pytest.mark.parametrize(
    "identity",
    [
        instrument("000001", exchange=Exchange.SZSE, kind=InstrumentKind.INDEX),
        instrument("430001", exchange=Exchange.BSE, kind=InstrumentKind.INDEX),
        instrument("399005", exchange=Exchange.SZSE, kind=InstrumentKind.INDEX),
        instrument("510300", exchange=Exchange.SSE, kind=InstrumentKind.ETF),
    ],
)
def test_index_request_rejects_unverified_exchange_kind_or_code(identity):
    with pytest.raises(ValidationError):
        KlinesRequest(
            instrumentId=identity,
            startDate=date(2026, 9, 17),
            endDate=date(2026, 9, 17),
        )
