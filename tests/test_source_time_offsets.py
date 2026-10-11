"""来源时钟严格验证，保留合法偏移、北京时间换日和来源精度。"""

import pytest

from finchx import SourceError
from finchx.sources.aigupiao import reports
from finchx.sources.iwencai import _document
from finchx.sources.tonghuashun import articles


@pytest.mark.parametrize("stamp", [
    "2026-10-09T24:00:00+08:00",
    "2026-10-09T24:00Z",
    "2026-10-09 24:00:00",
])
def test_article_source_time_rejects_hour_24(stamp):
    with pytest.raises(SourceError, match="来源完整发表时间无效"):
        articles._source_time(stamp)


@pytest.mark.parametrize("stamp, expected", [
    ("2026-10-09T23:30Z", "2026-10-10T07:30+08:00"),
    ("2026-10-09T23:30:45-03:30", "2026-10-10T11:00:45+08:00"),
    ("2026-10-09T23:30:45+09:00", "2026-10-09T22:30:45+08:00"),
])
def test_article_source_time_keeps_offset_conversion_and_precision(stamp, expected):
    assert articles._source_time(stamp) == (expected, None)


@pytest.mark.parametrize("stamp", [
    "2026-10-09T24:00:00Z",
    "2026-10-09T24:00:00.000123456789Z",
])
def test_report_recorded_time_rejects_hour_24(stamp):
    with pytest.raises(SourceError, match="rec_time 不是有效来源 UTC 时间"):
        reports._recorded(stamp)


@pytest.mark.parametrize("stamp, expected", [
    ("2026-10-09T23:30:45Z", "2026-10-10T07:30:45+08:00"),
    ("2026-10-09T23:30:45.000123456789Z", "2026-10-10T07:30:45.000123456789+08:00"),
])
def test_report_recorded_time_keeps_exact_fraction_and_utc_conversion(stamp, expected):
    assert reports._recorded(stamp) == expected


@pytest.mark.parametrize("stamp", [
    "2026-10-09T24:00:00+08:00",
    "2026/10/9 24:00Z",
    "2026-10-09 24:00:00",
])
def test_optional_document_date_returns_none_for_hour_24(stamp):
    assert _document._date(stamp) is None


@pytest.mark.parametrize("stamp, expected", [
    ("2026/10/9", "2026-10-09"),
    ("2026/10/9 23:30Z", "2026-10-10T07:30+08:00"),
    ("2026-10-09T23:30:45-03:30", "2026-10-10T11:00:45+08:00"),
    ("2026-10-09T23:30:45+09:00", "2026-10-09T22:30:45+08:00"),
])
def test_optional_document_date_keeps_format_offset_and_precision(stamp, expected):
    assert _document._date(stamp) == expected
