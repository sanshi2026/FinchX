from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time

import pandas_market_calendars as mcal
import pytest
from pydantic import ValidationError

from finchx.contracts import DataStatus, Source
from finchx.datasets.trading_calendar import (
    TRADING_CALENDAR_DATASET,
    TradingCalendarData,
    TradingCalendarRequest,
    _ProviderCalendarDay,
)
from finchx.datasets.trading_calendar_service import TradingCalendarService
from finchx.entities import Market
from finchx.providers.errors import ProviderError
from finchx.providers.trading_calendar import (
    PMC_CALENDAR_NAME,
    SZSE_CALENDAR_ENDPOINT,
    PmcTradingCalendarProvider,
    SzseTradingCalendarProvider,
    _CalendarHttpResponse,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "szse_calendar"


def _fixture(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def _request(start: date, end: date | None = None) -> TradingCalendarRequest:
    return TradingCalendarRequest(
        market=Market.CN_A,
        startDate=start,
        endDate=end or start,
    )


def _synthetic_month(year: int, month: int, *, overrides=None) -> bytes:
    overrides = overrides or {}
    from calendar import monthrange

    rows = []
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        # This is an explicit synthetic upstream response used by parser tests.
        # Production code never derives an official flag from weekday.
        flag = "1" if current.weekday() < 5 else "0"
        flag = overrides.get(current.isoformat(), flag)
        rows.append({"zrxh": (day_number - 1) % 7 + 1, "jybz": flag, "jyrq": current.isoformat()})
    return json.dumps({"data": rows}).encode("utf-8")


class _FixtureTransport:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, *, params, headers, timeout_seconds):
        call = {
            "url": url,
            "params": dict(params),
            "headers": dict(headers),
            "timeout_seconds": timeout_seconds,
        }
        self.calls.append(call)
        response = self.responses[params["month"]]
        if isinstance(response, Exception):
            raise response
        if isinstance(response, _CalendarHttpResponse):
            return response
        return _CalendarHttpResponse(status_code=200, body=response)


def _clock_sequence(*values: datetime):
    iterator = iter(values)
    return lambda: next(iterator)


class _RowsProvider:
    def __init__(self, provider_id, rows=None, failure=None):
        self._source = Source(providerId=provider_id)
        self.rows = rows
        self.failure = failure
        self.calls = []

    @property
    def source(self):
        return self._source

    def get_calendar(self, request):
        self.calls.append(request)
        if self.failure is not None:
            raise self.failure
        if callable(self.rows):
            return self.rows(request)
        return self.rows


def _rows_for_request(request, *, captured_at, flags=None):
    flags = flags or {}
    count = (request.end_date - request.start_date).days + 1
    return tuple(
        _ProviderCalendarDay(
            date=request.start_date + timedelta(days=offset),
            is_trading_day=flags.get(
                (request.start_date + timedelta(days=offset)).isoformat(),
                False,
            ),
            captured_at=captured_at,
        )
        for offset in range(count)
    )


def test_request_data_and_dataset_contract_are_minimal_and_restrict_cn_a():
    request = TradingCalendarRequest(
        market=Market.CN_A,
        startDate=date(2026, 9, 1),
        endDate=date(2026, 9, 30),
    )
    assert request.market is Market.CN_A
    assert TRADING_CALENDAR_DATASET.name == "trading_calendar"
    assert TRADING_CALENDAR_DATASET.schema_version == "1.0"
    assert TRADING_CALENDAR_DATASET.request_type is TradingCalendarRequest
    assert TRADING_CALENDAR_DATASET.data_type is TradingCalendarData

    with pytest.raises(ValidationError):
        TradingCalendarRequest(market="SSE", startDate="2026-09-01", endDate="2026-09-30")
    with pytest.raises(ValidationError):
        TradingCalendarRequest(
            market=Market.CN_A,
            startDate=date(2026, 9, 2),
            endDate=date(2026, 9, 1),
        )
    with pytest.raises(ValidationError):
        TradingCalendarRequest(
            market=Market.CN_A,
            startDate=datetime(2026, 9, 1),
            endDate=date(2026, 9, 1),
        )
    with pytest.raises(ValidationError):
        TradingCalendarRequest(
            market=Market.CN_A,
            startDate=date(2026, 9, 1),
            endDate=date(2026, 9, 1),
            source="szse",
        )
    with pytest.raises(ValidationError):
        TradingCalendarData(date=date(2026, 9, 1), isTradingDay=1)


def test_full_official_month_fixture_has_complete_natural_dates_and_explicit_flags():
    transport = _FixtureTransport({"2026-09": _fixture("valid_month.json")})
    captured_at = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
    provider = SzseTradingCalendarProvider(
        transport=transport,
        clock=lambda: captured_at,
    )
    request = _request(date(2026, 9, 1), date(2026, 9, 30))

    rows = provider.get_calendar(request)

    assert len(rows) == 30
    assert [row.date for row in rows] == [date(2026, 9, day) for day in range(1, 31)]
    assert sum(row.is_trading_day for row in rows) == 21
    by_date = {row.date: row.is_trading_day for row in rows}
    assert by_date[date(2026, 9, 17)] is True
    assert by_date[date(2026, 9, 5)] is False
    assert date(2026, 9, 25).weekday() == 4
    assert by_date[date(2026, 9, 25)] is False
    assert all(row.captured_at == captured_at for row in rows)
    assert transport.calls[0]["url"] == SZSE_CALENDAR_ENDPOINT
    assert transport.calls[0]["params"] == {"month": "2026-09"}
    assert transport.calls[0]["headers"]["Referer"] == "https://www.szse.cn/aboutus/calendar/"
    assert not any(key.casefold() in {"cookie", "authorization"} for key in transport.calls[0]["headers"])


def test_real_holiday_fixture_has_explicit_weekday_closures():
    transport = _FixtureTransport({"2026-05": _fixture("holiday_month.json")})
    rows = SzseTradingCalendarProvider(
        transport=transport,
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    ).get_calendar(_request(date(2026, 5, 1), date(2026, 5, 31)))

    by_date = {row.date: row.is_trading_day for row in rows}
    assert len(rows) == 31
    assert by_date[date(2026, 5, 4)] is False
    assert by_date[date(2026, 5, 5)] is False


@pytest.mark.parametrize(
    ("calendar_request", "months", "expected_count"),
    [
        (_request(date(2026, 9, 1), date(2026, 9, 30)), ["2026-09"], 30),
        (_request(date(2026, 9, 18), date(2026, 9, 18)), ["2026-09"], 1),
        (_request(date(2026, 9, 29), date(2026, 10, 2)), ["2026-09", "2026-10"], 4),
        (_request(date(2025, 12, 31), date(2026, 1, 2)), ["2025-12", "2026-01"], 3),
        (_request(date(2024, 2, 1), date(2024, 2, 29)), ["2024-02"], 29),
    ],
)
def test_month_enumeration_is_inclusive_across_partial_cross_year_and_leap_ranges(
    calendar_request, months, expected_count
):
    responses = {}
    for month_label in months:
        year, month = map(int, month_label.split("-"))
        responses[month_label] = _synthetic_month(year, month)
    transport = _FixtureTransport(responses)
    captures = [
        datetime(2026, 9, 17, 10, index, tzinfo=timezone.utc)
        for index in range(len(months))
    ]
    provider = SzseTradingCalendarProvider(
        transport=transport,
        clock=_clock_sequence(*captures),
    )

    rows = provider.get_calendar(calendar_request)

    assert [call["params"]["month"] for call in transport.calls] == months
    assert len(rows) == expected_count
    assert [row.date for row in rows] == sorted(row.date for row in rows)
    assert rows[0].date == calendar_request.start_date
    assert rows[-1].date == calendar_request.end_date
    for index, month_label in enumerate(months):
        year, month = map(int, month_label.split("-"))
        month_rows = [row for row in rows if row.date.year == year and row.date.month == month]
        if month_rows:
            assert {row.captured_at for row in month_rows} == {captures[index]}


def test_response_order_is_normalized_to_ascending_date():
    document = json.loads(_fixture("valid_month.json"))
    document["data"].reverse()
    provider = SzseTradingCalendarProvider(
        transport=_FixtureTransport({"2026-09": json.dumps(document).encode()}),
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )

    rows = provider.get_calendar(_request(date(2026, 9, 1), date(2026, 9, 30)))

    assert [row.date for row in rows] == sorted(row.date for row in rows)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"{", "invalid JSON"),
        (b"[]", "invalid envelope"),
        (_fixture("malformed_envelope.json"), "missing calendar list"),
        (b'{"data":[]}', "missing date"),
        (_fixture("incomplete_month.json"), "missing date"),
        (_fixture("duplicate_date.json"), "duplicate date"),
        (_fixture("invalid_flag.json"), "invalid trading flag"),
    ],
)
def test_malformed_or_incomplete_official_responses_fail_with_specific_provider_errors(
    body, message
):
    provider = SzseTradingCalendarProvider(
        transport=_FixtureTransport({"2026-09": body}),
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )

    with pytest.raises(ProviderError, match=message):
        provider.get_calendar(_request(date(2026, 9, 1), date(2026, 9, 30)))


def test_invalid_date_and_month_boundary_fail_without_weekday_inference():
    invalid_date = json.loads(_fixture("valid_month.json"))
    invalid_date["data"][0]["jyrq"] = "2026-02-30"
    provider = SzseTradingCalendarProvider(
        transport=_FixtureTransport(
            {"2026-09": json.dumps(invalid_date).encode()}
        ),
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )
    with pytest.raises(ProviderError, match="invalid date"):
        provider.get_calendar(_request(date(2026, 9, 1), date(2026, 9, 30)))

    wrong_month = json.loads(_fixture("valid_month.json"))
    wrong_month["data"][0]["jyrq"] = "2026-08-31"
    provider = SzseTradingCalendarProvider(
        transport=_FixtureTransport(
            {"2026-09": json.dumps(wrong_month).encode()}
        ),
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )
    with pytest.raises(ProviderError, match="month mismatch"):
        provider.get_calendar(_request(date(2026, 9, 1), date(2026, 9, 30)))

    missing_weekend = json.loads(_fixture("valid_month.json"))
    missing_weekend["data"] = [
        row for row in missing_weekend["data"] if row["jyrq"] != "2026-09-05"
    ]
    provider = SzseTradingCalendarProvider(
        transport=_FixtureTransport(
            {"2026-09": json.dumps(missing_weekend).encode()}
        ),
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )
    with pytest.raises(ProviderError, match="missing date"):
        provider.get_calendar(_request(date(2026, 9, 1), date(2026, 9, 30)))


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_CalendarHttpResponse(500, b""), "HTTP failure"),
        (TimeoutError("fixture timeout"), "transport failure"),
        (ConnectionError("fixture connection"), "transport failure"),
    ],
)
def test_http_and_transport_failures_are_distinct_provider_errors(response, message):
    provider = SzseTradingCalendarProvider(
        transport=_FixtureTransport({"2026-09": response}),
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )

    with pytest.raises(ProviderError, match=message):
        provider.get_calendar(_request(date(2026, 9, 1), date(2026, 9, 30)))


def test_cross_month_official_responses_keep_their_own_capture_times():
    captures = (
        datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 30, 16, 1, tzinfo=timezone.utc),
    )
    transport = _FixtureTransport(
        {
            "2026-09": _fixture("valid_month.json"),
            "2026-10": _fixture("future_month.json"),
        }
    )
    service = TradingCalendarService(
        primary_provider=SzseTradingCalendarProvider(
            transport=transport,
            clock=_clock_sequence(*captures),
        ),
        fallback_provider=_RowsProvider("fallback.test"),
    )

    records = service.get_calendar(_request(date(2026, 9, 29), date(2026, 10, 2)))

    assert [record.data["date"] for record in records] == [
        "2026-09-29",
        "2026-09-30",
        "2026-10-01",
        "2026-10-02",
    ]
    assert records[0].captured_at == records[1].captured_at == captures[0]
    assert records[2].captured_at == records[3].captured_at == captures[1]


def test_primary_records_have_stable_calendar_identity_and_no_fake_event_time():
    captured_at = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
    service = TradingCalendarService(
        primary_provider=SzseTradingCalendarProvider(
            transport=_FixtureTransport({"2026-09": _fixture("valid_month.json")}),
            clock=lambda: captured_at,
        ),
        fallback_provider=_RowsProvider("fallback.test"),
    )

    record = service.get_calendar(_request(date(2026, 9, 17)))[0]

    assert record.record_id == record.entity_id == "CN_A:2026-09-17"
    assert record.dataset == "trading_calendar"
    assert record.schema_version == "1.0"
    assert record.data == {"date": "2026-09-17", "isTradingDay": True}
    assert record.source.provider_id == "szse.official.calendar"
    assert record.status is DataStatus.LIVE
    assert record.event_at is None
    assert record.as_of is None
    assert record.captured_at == captured_at


def test_primary_success_does_not_call_fallback():
    primary = SzseTradingCalendarProvider(
        transport=_FixtureTransport({"2026-09": _fixture("valid_month.json")}),
        clock=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )
    fallback = _RowsProvider("pandas_market_calendars", failure=AssertionError("must not call"))

    records = TradingCalendarService(
        primary_provider=primary,
        fallback_provider=fallback,
    ).get_calendar(_request(date(2026, 9, 1), date(2026, 9, 30)))

    assert len(records) == 30
    assert fallback.calls == []
    assert {record.source.provider_id for record in records} == {"szse.official.calendar"}


def test_any_primary_failure_falls_back_for_the_entire_range_and_never_mixes_sources():
    request = _request(date(2026, 9, 30), date(2026, 10, 2))
    incomplete_october = json.loads(_fixture("future_month.json"))
    incomplete_october["data"] = [
        row for row in incomplete_october["data"] if row["jyrq"] != "2026-10-01"
    ]
    transport = _FixtureTransport(
        {
            "2026-09": _fixture("valid_month.json"),
            "2026-10": json.dumps(incomplete_october).encode("utf-8"),
        }
    )
    primary = SzseTradingCalendarProvider(
        transport=transport,
        clock=_clock_sequence(
            datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc),
            datetime(2026, 9, 30, 16, 1, tzinfo=timezone.utc),
        ),
    )
    fallback_capture = datetime(2026, 9, 30, 16, 2, tzinfo=timezone.utc)
    fallback = _RowsProvider(
        "pandas_market_calendars",
        rows=lambda requested: _rows_for_request(
            requested,
            captured_at=fallback_capture,
            flags={"2026-09-30": True, "2026-10-01": False, "2026-10-02": False},
        ),
    )

    records = TradingCalendarService(
        primary_provider=primary,
        fallback_provider=fallback,
    ).get_calendar(request)

    assert [call["params"]["month"] for call in transport.calls] == ["2026-09", "2026-10"]
    assert fallback.calls == [request]
    assert [record.data["date"] for record in records] == [
        "2026-09-30",
        "2026-10-01",
        "2026-10-02",
    ]
    assert {record.source.provider_id for record in records} == {"pandas_market_calendars"}
    assert {record.captured_at for record in records} == {fallback_capture}


@pytest.mark.parametrize(
    "failure",
    [
        ProviderError(Source(providerId="szse.official.calendar"), "transport failure"),
        ProviderError(Source(providerId="szse.official.calendar"), "HTTP failure"),
        ProviderError(Source(providerId="szse.official.calendar"), "missing date"),
    ],
)
def test_fallback_is_used_for_primary_transport_http_and_completeness_failures(failure):
    request = _request(date(2026, 9, 4), date(2026, 9, 6))
    capture = datetime(2026, 9, 17, tzinfo=timezone.utc)
    primary = _RowsProvider("szse.official.calendar", failure=failure)
    fallback = _RowsProvider(
        "pandas_market_calendars",
        rows=lambda requested: _rows_for_request(
            requested,
            captured_at=capture,
            flags={"2026-09-04": True},
        ),
    )

    records = TradingCalendarService(
        primary_provider=primary,
        fallback_provider=fallback,
    ).get_calendar(request)

    assert primary.calls == [request]
    assert fallback.calls == [request]
    assert {record.source.provider_id for record in records} == {"pandas_market_calendars"}
    assert [record.data["date"] for record in records] == [
        "2026-09-04",
        "2026-09-05",
        "2026-09-06",
    ]


def test_fallback_failure_reports_both_primary_and_fallback_context():
    request = _request(date(2026, 9, 17))
    primary = _RowsProvider(
        "szse.official.calendar",
        failure=ProviderError(Source(providerId="szse.official.calendar"), "HTTP failure"),
    )
    fallback = _RowsProvider(
        "pandas_market_calendars",
        failure=ProviderError(Source(providerId="pandas_market_calendars"), "schedule failure"),
    )

    with pytest.raises(ProviderError, match="HTTP failure.*schedule failure") as raised:
        TradingCalendarService(
            primary_provider=primary,
            fallback_provider=fallback,
        ).get_calendar(request)
    assert raised.value.source.provider_id == "pandas_market_calendars"


def test_real_pmc_calendar_is_selected_and_expanded_to_all_natural_dates():
    provider = PmcTradingCalendarProvider(
        clock=lambda: datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    )
    request = _request(date(2026, 9, 1), date(2026, 9, 30))

    rows = provider.get_calendar(request)
    schedule = mcal.get_calendar("SSE").schedule("2026-09-01", "2026-09-30")
    expected_sessions = {label.date() for label in schedule.index}

    assert PMC_CALENDAR_NAME == "SSE"
    assert "SSE" in mcal.get_calendar_names()
    assert provider.version == mcal.__version__
    assert provider.calendar_name == "SSE"
    assert len(rows) == 30
    assert {row.date for row in rows if row.is_trading_day} == expected_sessions
    assert all(row.captured_at.tzinfo is not None for row in rows)


def test_pmc_fallback_does_not_depend_on_system_timezone():
    if not hasattr(time, "tzset"):
        pytest.skip("system timezone switching is unavailable")
    request = _request(date(2026, 9, 1), date(2026, 9, 30))
    captured_at = datetime(2026, 9, 17, tzinfo=timezone.utc)

    def values():
        return [
            (row.date, row.is_trading_day)
            for row in PmcTradingCalendarProvider(
                clock=lambda: captured_at
            ).get_calendar(request)
        ]

    before = values()
    old_timezone = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "Pacific/Honolulu"
        time.tzset()
        after = values()
    finally:
        if old_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_timezone
        time.tzset()

    assert after == before


def test_service_uses_real_pmc_as_offline_fallback_after_transport_failure():
    request = _request(date(2026, 9, 4), date(2026, 9, 6))
    transport = _FixtureTransport({"2026-09": TimeoutError("offline fixture")})
    capture = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    service = TradingCalendarService(
        primary_transport=transport,
        clock=lambda: capture,
    )

    records = service.get_calendar(request)

    assert len(records) == 3
    assert {record.source.provider_id for record in records} == {"pandas_market_calendars"}
    assert {record.status for record in records} == {DataStatus.LIVE}
    assert {record.captured_at for record in records} == {capture}
    assert records[1].data == {"date": "2026-09-05", "isTradingDay": False}
