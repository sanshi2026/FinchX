"""来源时刻边界不能随 Python ISO 解析器版本改变。"""

from datetime import datetime, timedelta, timezone
from functools import partial

import pytest

from finchx._common.errors import SourceError
from finchx.sources.aigupiao.articles import _published
from finchx.sources.eastmoney.news import _parse_header_time, _source_time
from finchx.sources.eastmoney.regulation import _date
from finchx.sources.iwencai._values import source_time
from finchx.sources.taoguba.forum import _moment
from finchx.sources.tonghuashun.concept import _source_time as concept_time


_BEIJING = timezone(timedelta(hours=8))
_SECOND_RESULT = "2026-10-09T23:59:59+08:00"
_MINUTE_RESULT = "2026-10-09T23:59+08:00"
_DATE_VALUE = partial(_date, field="date")
_CASES = [
    pytest.param(_moment, "2026-10-09 24:00:00", "2026-10-09 23:59:59",
                 (datetime(2026, 10, 9, 23, 59, 59, tzinfo=_BEIJING), _SECOND_RESULT), id="forum-seconds"),
    pytest.param(_moment, "2026-10-09 24:00", "2026-10-09 23:59",
                 (datetime(2026, 10, 9, 23, 59, tzinfo=_BEIJING), _MINUTE_RESULT), id="forum-minutes"),
    pytest.param(source_time, "2026-10-09 24:00:00", "2026-10-09 23:59:59",
                 _SECOND_RESULT, id="iwencai-seconds"),
    pytest.param(source_time, "2026-10-09 24:00", "2026-10-09 23:59",
                 _MINUTE_RESULT, id="iwencai-minutes"),
    pytest.param(source_time, "2026-10-09T24:00:00", "2026-10-09T23:59:59",
                 _SECOND_RESULT, id="iwencai-t-seconds"),
    pytest.param(source_time, "2026-10-09T24:00", "2026-10-09T23:59",
                 _MINUTE_RESULT, id="iwencai-t-minutes"),
    pytest.param(_source_time, "2026-10-09 24:00:00", "2026-10-09 23:59:59",
                 datetime(2026, 10, 9, 23, 59, 59, tzinfo=_BEIJING), id="news-seconds"),
    pytest.param(_parse_header_time, "2026年10月09日 24:00:00", "2026年10月09日 23:59:59",
                 _SECOND_RESULT, id="news-header-seconds"),
    pytest.param(_parse_header_time, "2026年10月09日 24:00", "2026年10月09日 23:59",
                 _MINUTE_RESULT, id="news-header-minutes"),
    pytest.param(concept_time, "2026-10-09 24:00:00", "2026-10-09 23:59:59",
                 ("2026-10-09", "23:59:59"), id="concept-seconds"),
    pytest.param(concept_time, "2026-10-09 24:00", "2026-10-09 23:59",
                 ("2026-10-09", "23:59"), id="concept-minutes"),
    pytest.param(_published, "2026-10-09 24:00:00", "2026-10-09 23:59:59",
                 _SECOND_RESULT, id="articles-seconds"),
    pytest.param(_published, "2026-10-09 24:00", "2026-10-09 23:59",
                 _MINUTE_RESULT, id="articles-minutes"),
    pytest.param(_DATE_VALUE, "2026-10-09 24:00:00", "2026-10-09 23:59:59",
                 "2026-10-09", id="regulation-seconds"),
]


@pytest.mark.parametrize("parse, invalid, valid, expected", _CASES)
def test_source_time_rejects_hour_24(parse, invalid, valid, expected):
    with pytest.raises(SourceError):
        parse(invalid)


@pytest.mark.parametrize("parse, invalid, valid, expected", _CASES)
def test_source_time_preserves_last_valid_minute_and_precision(parse, invalid, valid, expected):
    assert parse(valid) == expected
