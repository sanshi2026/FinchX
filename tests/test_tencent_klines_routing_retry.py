from datetime import date, datetime, timedelta, timezone
import json
import socket
import traceback
from urllib.error import URLError

import pytest

from finchx import FinchX
from finchx.collectors import (
    AllProvidersFailed,
    CachePolicy,
    Collector,
    InvalidRequest,
    NoData,
)
from finchx.contracts import Source
from finchx.datasets import KlineAdjustment
from finchx.datasets.trading_calendar import _ProviderCalendarDay
from finchx.providers import TencentKlinesError
from finchx.providers.sohu_klines import SohuKlinesProvider, _SohuResponse
from finchx.providers.tencent import _TencentHttpResponse, _TencentTransportFailure
from finchx.providers.tencent_klines import (
    TENCENT_KLINE_ENDPOINT,
    TencentKlinesProvider,
    _classify_transport_failure,
)
from finchx.storage import Cache, MemoryStorage


CAPTURED_AT = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)
KLINE_ROW = ["2026-09-25", "10", "11", "12", "9", "100"]


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class QueueTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, params, headers, timeout_seconds):
        self.calls.append((url, dict(params), timeout_seconds))
        assert url == TENCENT_KLINE_ENDPOINT
        assert 0 < timeout_seconds <= 15
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _tencent_response(rows=(KLINE_ROW,), *, symbol="sh600519", adjustment="qfq", status=200):
    response_variable = "kline_dayqfq" if adjustment == "qfq" else "kline_day"
    series_key = "qfqday" if adjustment == "qfq" else "day"
    payload = {"code": 0, "data": {symbol: {series_key: rows}}}
    return _TencentHttpResponse(status, f"{response_variable}={json.dumps(payload)}")


def _tencent_series_response(series, *, symbol="sh600519", status=200):
    payload = {"code": 0, "data": {symbol: series}}
    return _TencentHttpResponse(status, f"kline_dayqfq={json.dumps(payload)}")


def _provider(transport, *, fake_time=None, retry_budget_seconds=45):
    fake_time = fake_time or FakeTime()
    return TencentKlinesProvider(
        transport,
        clock=lambda: CAPTURED_AT,
        monotonic_clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
        retry_budget_seconds=retry_budget_seconds,
    ), fake_time


def test_tencent_klines_retries_transient_transport_up_to_four_attempts_then_succeeds():
    transport = QueueTransport(
        [TimeoutError("proxy=https://user:secret@example.invalid")] * 3
        + [_tencent_response()]
    )
    provider, fake_time = _provider(transport)

    rows = provider.fetch_klines(
        _request(adjustment=KlineAdjustment.QFQ)
    )

    assert len(rows) == 1
    assert len(transport.calls) == 4
    assert fake_time.sleeps == [0.25, 0.5, 1.0]
    assert all(call[2] <= 15 for call in transport.calls)


def test_tencent_klines_exposes_attempt_history_and_redacts_transport_text():
    sensitive_marker = "restricted-" + str(987654)
    transport = QueueTransport(
        [TimeoutError("".join(("pro", "xy=")) + sensitive_marker + "@example.invalid")] * 4
    )
    provider, fake_time = _provider(transport)

    with pytest.raises(TencentKlinesError) as captured:
        provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ))

    error = captured.value
    assert len(transport.calls) == 4
    assert fake_time.sleeps == [0.25, 0.5, 1.0]
    assert error.provider_id == "tencent.finance.qq"
    assert error.attempt_count == 4
    assert error.attempt == 4
    assert error.stage == "transport"
    assert error.category == "timeout"
    assert error.retryable is True
    assert error.retry_budget_exhausted is True
    assert [item.attempt for item in error.attempts] == [1, 2, 3, 4]
    assert all(item.category == "timeout" and item.retryable for item in error.attempts)
    assert "attempt_count=4" in str(error)
    assert sensitive_marker not in str(error)
    assert "example.invalid" not in str(error)
    formatted = "".join(traceback.format_exception(error))
    assert sensitive_marker not in formatted
    assert "proxy=" not in formatted


@pytest.mark.parametrize(
    ("status", "category", "expected_sleeps"),
    [
        (404, "permanent_http", []),
        (429, "transient_http", [2.0, 4.0, 8.0]),
    ],
)
def test_tencent_klines_retries_only_temporary_http_failures(status, category, expected_sleeps):
    transport = QueueTransport([_TencentHttpResponse(status, "")] * (1 if status == 404 else 4))
    provider, fake_time = _provider(transport)

    with pytest.raises(TencentKlinesError) as captured:
        provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ))

    error = captured.value
    assert error.category == category
    assert error.retryable is (status == 429)
    assert error.attempt_count == (1 if status == 404 else 4)
    assert len(transport.calls) == error.attempt_count
    assert fake_time.sleeps == expected_sleeps
    assert error.retry_budget_exhausted is (status == 429)


def test_successful_empty_history_is_not_retried_as_a_transport_failure():
    transport = QueueTransport([_tencent_response(rows=[])])
    provider, fake_time = _provider(transport)

    assert provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ)) == ()
    assert len(transport.calls) == 1
    assert fake_time.sleeps == []


def test_qfqday_is_preferred_when_both_adjusted_and_unadjusted_series_exist():
    qfq_row = ["2026-09-25", "10", "11", "12", "9", "100"]
    raw_row = ["2026-09-25", "20", "21", "22", "19", "100"]
    transport = QueueTransport(
        [_tencent_series_response({"qfqday": [qfq_row], "day": [raw_row]})]
    )
    provider, _ = _provider(transport)

    rows = provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ))

    assert len(transport.calls) == 1
    assert rows[0].data.adjustment is KlineAdjustment.QFQ
    assert rows[0].data.close == 11
    assert rows[0].adjustment_fallback is False


def test_missing_qfqday_uses_same_response_day_and_preserves_actual_mode_and_cache_metadata():
    transport = QueueTransport(
        [_tencent_series_response({"day": [KLINE_ROW]})]
    )
    provider, _ = _provider(transport)
    collector = Collector(
        provider_instances={"tencent.finance.qq.klines": provider},
        cache=Cache(MemoryStorage(clock=lambda: CAPTURED_AT), clock=lambda: CAPTURED_AT),
        cache_policy={"market.klines": CachePolicy(enabled=True, ttl=60)},
    )
    client = FinchX(collector=collector)

    first = client.market.ohlcv(
        "600519", date(2026, 9, 25), date(2026, 9, 25), "qfq", use_cache=True
    )
    cached = client.market.ohlcv(
        "600519", date(2026, 9, 25), date(2026, 9, 25), "qfq", use_cache=True
    )

    assert len(transport.calls) == 1
    assert first.data[0].data["adjustment"] == "none"
    assert first.data[0].record_id.endswith("@none")
    assert first.data[0].provenance.adjustments[0].name == "none"
    assert first.metadata["requested_adjustment"] == "qfq"
    assert first.metadata["actual_adjustment"] == "none"
    assert first.metadata["source_series"] == "day"
    assert first.metadata["adjustment_fallback"] is True
    assert any("not forward-adjusted" in warning for warning in first.warnings)
    assert cached.cache_hit is True
    assert cached.metadata == first.metadata
    assert cached.warnings == first.warnings
    assert cached.data[0].data["adjustment"] == "none"


def test_present_empty_qfqday_does_not_fall_back_to_day():
    transport = QueueTransport(
        [_tencent_series_response({"qfqday": [], "day": [KLINE_ROW]})]
    )
    provider, _ = _provider(transport)

    assert provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ)) == ()
    assert len(transport.calls) == 1


def test_present_malformed_qfqday_does_not_fall_back_to_valid_day():
    transport = QueueTransport(
        [_tencent_series_response({"qfqday": {"bad": True}, "day": [KLINE_ROW]})]
    )
    provider, _ = _provider(transport)

    with pytest.raises(TencentKlinesError, match="invalid qfqday array"):
        provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ))
    assert len(transport.calls) == 1


def test_missing_qfqday_with_invalid_day_still_fails():
    transport = QueueTransport([_tencent_series_response({"day": "not-an-array"})])
    provider, _ = _provider(transport)

    with pytest.raises(TencentKlinesError, match="no valid day array"):
        provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ))
    assert len(transport.calls) == 1


def test_qfq_pagination_rejects_a_change_to_unadjusted_day_series(monkeypatch):
    import finchx.providers.tencent_klines as tencent_klines

    monkeypatch.setattr(tencent_klines, "_PAGE_SIZE", 2)
    first_page = {
        "qfqday": [
            ["2026-09-25", "10", "11", "12", "9", "100"],
            ["2026-09-24", "10", "11", "12", "9", "100"],
        ]
    }
    second_page = {
        "day": [["2026-09-23", "10", "11", "12", "9", "100"]]
    }
    transport = QueueTransport(
        [
            _tencent_series_response(first_page),
            _tencent_series_response(second_page),
        ]
    )
    provider, _ = _provider(transport)
    request = _request(adjustment=KlineAdjustment.QFQ).model_copy(
        update={"start_date": date(2026, 9, 23)}
    )

    with pytest.raises(TencentKlinesError, match="series changed between Kline pages"):
        provider.fetch_klines(request)
    assert len(transport.calls) == 2


def test_retry_deadline_can_stop_before_attempt_four_and_bounds_each_timeout():
    fake_time = FakeTime()

    class SlowTimeoutTransport:
        def __init__(self):
            self.timeouts = []

        def get(self, url, *, params, headers, timeout_seconds):
            self.timeouts.append(timeout_seconds)
            fake_time.now += timeout_seconds
            raise TimeoutError("timed out")

    transport = SlowTimeoutTransport()
    provider, _ = _provider(transport, fake_time=fake_time)

    with pytest.raises(TencentKlinesError) as captured:
        provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ))

    assert captured.value.retry_budget_exhausted is True
    assert captured.value.attempt_count < 4
    assert 0 < fake_time.now <= 45
    assert all(timeout <= 15 for timeout in transport.timeouts)


def test_dns_errors_have_a_safe_retryable_classification_with_errno():
    error = URLError(socket.gaierror(8, "not included in safe diagnostics"))
    stage, category, safe_reason, retryable = _classify_transport_failure(error)

    assert (stage, category, retryable) == ("transport", "dns_resolution", True)
    assert "errno=8" in safe_reason
    assert "not included" not in safe_reason


def test_schema_failure_after_http_success_is_not_retried():
    transport = QueueTransport([_TencentHttpResponse(200, "not-json")])
    provider, fake_time = _provider(transport)

    with pytest.raises(TencentKlinesError) as captured:
        provider.fetch_klines(_request(adjustment=KlineAdjustment.QFQ))

    assert captured.value.stage == "response"
    assert captured.value.category == "schema"
    assert captured.value.retryable is False
    assert captured.value.attempt_count == 1
    assert len(transport.calls) == 1
    assert fake_time.sleeps == []


@pytest.mark.parametrize(
    ("instrument", "adjustment"),
    [
        ("cn_a:sse:equity:600519", "qfq"),
        ("cn_a:sse:index:000001", None),
    ],
)
def test_public_ohlcv_does_not_auto_fallback_to_sohu(instrument, adjustment):
    tencent_transport = QueueTransport([TimeoutError("temporary timeout")] * 4)
    tencent, _ = _provider(tencent_transport)
    sohu_transport = CountingSohuTransport()
    sohu = SohuKlinesProvider(sohu_transport, clock=lambda: CAPTURED_AT)
    client = FinchX(
        collector=Collector(
            provider_instances={
                "tencent.finance.qq.klines": tencent,
                "sohu.finance.klines": sohu,
            }
        )
    )

    with pytest.raises(AllProvidersFailed) as captured:
        client.market.ohlcv(
            instrument,
            date(2026, 9, 25),
            date(2026, 9, 25),
            adjustment,
            use_cache=False,
        )

    error = captured.value
    assert error.providers == ("tencent.finance.qq.klines",)
    assert len(error.attempts) == 1  # Provider-internal retries are not repeated by Collector.
    assert len(tencent_transport.calls) == 4
    assert sohu_transport.calls == 0
    assert isinstance(error.last_error, TencentKlinesError)
    assert error.last_error.attempt_count == 4
    assert error.last_error.retry_budget_exhausted is True


def test_explicit_sohu_supports_indices_but_rejects_equities_before_network():
    sohu_transport = CountingSohuTransport()
    sohu = SohuKlinesProvider(sohu_transport, clock=lambda: CAPTURED_AT)
    client = FinchX(
        collector=Collector(provider_instances={"sohu.finance.klines": sohu})
    )

    result = client.market.ohlcv(
        "cn_a:sse:index:000001",
        date(2026, 9, 25),
        date(2026, 9, 25),
        provider="sohu.finance.klines",
        use_cache=False,
    )
    assert result.provider == "sohu.finance.klines"
    assert len(result.data) == 1
    assert sohu_transport.calls == 1

    with pytest.raises(InvalidRequest, match="does not support this request"):
        client.market.ohlcv(
            "cn_a:sse:equity:600519",
            date(2026, 9, 25),
            date(2026, 9, 25),
            "qfq",
            provider="sohu.finance.klines",
            use_cache=False,
        )
    assert sohu_transport.calls == 1


def test_public_deviation_preserves_provider_retry_history_on_transport_failure():
    tencent_transport = QueueTransport([TimeoutError("temporary timeout")] * 4)
    tencent, _ = _provider(tencent_transport)
    client = FinchX(
        collector=Collector(
            provider_instances={
                "tencent.finance.qq.klines": tencent,
                "szse.official.calendar": FixtureCalendarProvider(),
            }
        )
    )

    with pytest.raises(AllProvidersFailed) as captured:
        client.market.deviation(
            "cn_a:sse:equity:600519",
            windows=(10,),
            as_of=date(2026, 9, 25),
            use_cache=False,
        )

    assert len(tencent_transport.calls) == 4
    assert isinstance(captured.value.last_error, TencentKlinesError)
    assert captured.value.last_error.category == "timeout"
    assert captured.value.last_error.attempt_count == 4
    assert "attempt_count=4" in str(captured.value.last_error)


def test_public_deviation_reports_insufficient_history_without_transport_retry():
    transport = QueueTransport([
        _tencent_response(symbol="sh600519", adjustment="qfq"),
        _tencent_response(symbol="sh000002", adjustment="none"),
    ])
    provider, fake_time = _provider(transport)
    client = FinchX(
        collector=Collector(
            provider_instances={
                "tencent.finance.qq.klines": provider,
                "szse.official.calendar": FixtureCalendarProvider(),
            }
        )
    )

    with pytest.raises(NoData, match="missing aligned stock or benchmark closes"):
        client.market.deviation(
            "cn_a:sse:equity:600519",
            windows=(10,),
            as_of=date(2026, 9, 25),
            use_cache=False,
        )

    assert len(transport.calls) == 2
    assert fake_time.sleeps == []


def _request(*, adjustment):
    from finchx.datasets.market_klines import KlinesRequest
    from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

    return KlinesRequest(
        instrumentId=InstrumentId(
            code="600519",
            market=Market.CN_A,
            exchange=Exchange.SSE,
            kind=InstrumentKind.EQUITY,
        ),
        startDate=date(2026, 9, 25),
        endDate=date(2026, 9, 25),
        adjustment=adjustment,
    )


class CountingSohuTransport:
    def __init__(self):
        self.calls = 0

    def get(self, url, *, headers, timeout_seconds):
        self.calls += 1
        payload = {
            "status": 0,
            "type": "quote_day",
            "dataDiv": [["20260925", "10", "11", "12", "9", "100", "1"]],
        }
        return _SohuResponse(200, f"quote_d_dividend({json.dumps(payload)})")


class FixtureCalendarProvider:
    source = Source(providerId="fixture.calendar")

    def get_calendar(self, request):
        count = (request.end_date - request.start_date).days + 1
        return tuple(
            _ProviderCalendarDay(
                date=request.start_date + timedelta(days=offset),
                is_trading_day=(request.start_date + timedelta(days=offset)).weekday() < 5,
                captured_at=CAPTURED_AT,
            )
            for offset in range(count)
        )
