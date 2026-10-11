"""新闻时间范围与数量参数的客观边界。"""

from datetime import date, datetime, timedelta, timezone

import pytest

from finchx._common.news import BEIJING_TZ, in_window, validate_limit, validate_window


@pytest.mark.parametrize("limit", [1, 20, 21, 200, 10**30])
def test_positive_limit_has_no_arbitrary_page_size_cap(limit):
    assert validate_limit(limit) == limit


@pytest.mark.parametrize("limit", [True, False, 0, -1, 1.0, "20", None, [], float("inf")])
def test_invalid_limit_fails(limit):
    with pytest.raises(ValueError):
        validate_limit(limit)


@pytest.mark.parametrize("value", [
    True, False, 20261008, date(2026, 10, 8), datetime(2026, 10, 8),
    "", " 2026-10-08", "2026-10-08 ", "2026-1-08",
    "２０２６-１０-０８", "2026-02-29", "2024-02-30", "0000-01-01",
    "2026-10-08T12:00:00", "2026-10-08 12:00", "2026-10-08 12:00:00+08:00",
    "2026-10-08 24:00:00", "2026-10-08 12:60:00", "2026-10-08 12:00:60",
    "2026-10-08 12:00:00.5", [], {},
])
@pytest.mark.parametrize("name", ["since", "until"])
def test_only_exact_plain_beijing_strings_are_accepted(value, name):
    with pytest.raises(ValueError, match=name):
        validate_window(**{name: value, "until" if name == "since" else "since": None})


def test_leap_date_includes_whole_day_without_spilling_into_next_day():
    lower, upper = validate_window("2024-02-29", "2024-02-29")
    assert lower == datetime(2024, 2, 29, tzinfo=BEIJING_TZ)
    assert upper == datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=BEIJING_TZ)
    assert in_window(lower, lower, upper)
    assert in_window(upper, lower, upper)
    assert not in_window(lower - timedelta(microseconds=1), lower, upper)
    assert not in_window(upper + timedelta(microseconds=1), lower, upper)


def test_explicit_datetime_includes_that_second_both_ends():
    lower, upper = validate_window("2026-10-08 12:00:00", "2026-10-08 12:00:00")
    assert lower == datetime(2026, 10, 8, 12, tzinfo=BEIJING_TZ)
    assert upper == lower.replace(microsecond=999999)
    assert in_window(lower, lower, upper)
    assert in_window(upper, lower, upper)
    assert not in_window(lower - timedelta(microseconds=1), lower, upper)
    assert not in_window(upper + timedelta(microseconds=1), lower, upper)


@pytest.mark.parametrize("since,until", [
    ("2026-10-09", "2026-10-08"),
    ("2026-10-08 12:00:01", "2026-10-08 12:00:00"),
    ("2026-10-09", "2026-10-08 23:59:59"),
])
def test_reversed_range_fails(since, until):
    with pytest.raises(ValueError, match="since 不得晚于 until"):
        validate_window(since, until)


def test_date_and_datetime_boundaries_can_share_a_day():
    lower, upper = validate_window("2026-10-08", "2026-10-08 00:00:00")
    assert in_window(datetime(2026, 10, 8, tzinfo=BEIJING_TZ), lower, upper)
    lower, upper = validate_window("2026-10-08 23:59:59", "2026-10-08")
    assert in_window(datetime(2026, 10, 8, 23, 59, 59, tzinfo=BEIJING_TZ), lower, upper)


def test_aware_source_timestamp_comparison_uses_absolute_instant():
    lower, upper = validate_window("2026-10-08", "2026-10-08")
    assert lower.utcoffset() == timedelta(hours=8)
    assert in_window(datetime(2026, 10, 7, 16, tzinfo=timezone.utc), lower, upper)
    assert not in_window(datetime(2026, 10, 7, 15, 59, 59, tzinfo=timezone.utc), lower, upper)
    assert in_window(datetime(2026, 10, 8, 15, 59, 59, tzinfo=timezone.utc), lower, upper)
    assert not in_window(datetime(2026, 10, 8, 16, tzinfo=timezone.utc), lower, upper)


def test_none_boundaries_do_not_substitute_clock_or_invent_latest_time():
    assert validate_window(None, None) == (None, None)
    lower, upper = validate_window("9999-12-31", None)
    assert upper is None and in_window(datetime.max.replace(tzinfo=BEIJING_TZ), lower, upper)
    lower, upper = validate_window(None, "0001-01-01")
    assert lower is None and in_window(datetime.min.replace(tzinfo=BEIJING_TZ), lower, upper)


@pytest.mark.parametrize("day", ["2026-09-30", "20260930", "2026/09/30"])
def test_all_date_string_formats_keep_beijing_whole_day_and_explicit_seconds(day):
    lower, upper = validate_window(day, day)
    assert lower == datetime(2026, 9, 30, tzinfo=BEIJING_TZ)
    assert upper == datetime(2026, 9, 30, 23, 59, 59, 999999, tzinfo=BEIJING_TZ)
    lower, upper = validate_window(day + " 15:30:00", day + " 15:30:00")
    assert lower == datetime(2026, 9, 30, 15, 30, tzinfo=BEIJING_TZ)
    assert upper == lower.replace(microsecond=999999)
