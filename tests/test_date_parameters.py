"""公开日期格式兼容与来源日期校验边界。"""

from datetime import date, datetime

import pytest

from finchx import FinchX, SourceError
from finchx._common.convert import parse_date, parse_date_parameter
from finchx.sources.tencent import deviation
from finchx.sources.tonghuashun import financial
from finchx.sources.jiuyangongshe import replay


_CALLS = [
    lambda fx, value: fx.reference.trading_calendar(value, value, source="szse"),
    lambda fx, value: fx.market.ohlcv("600519", value, value),
    lambda fx, value: fx.sector.ths_concept_ohlcv("302035", value, value),
    lambda fx, value: fx.fund_flow.dragon_tiger_list(value),
    lambda fx, value: fx.fund_flow.dragon_tiger_detail("301139", value, "100420668"),
    lambda fx, value: fx.financial.statements("600519", "income_statement", period_end=value),
    lambda fx, value: fx.regulation.deviation("600519", end_date=value),
    lambda fx, value: fx.fupan.jygs_replay(value, session="controlled-session"),
    lambda fx, value: fx.news.agp_list(since=value),
    lambda fx, value: fx.news.bd_list(until=value),
    lambda fx, value: fx.news.em_list("600519", since=value),
]


@pytest.mark.parametrize("call", _CALLS)
@pytest.mark.parametrize("value", [
    True, 20260930, datetime(2026, 9, 30),
    "20260229", "2026/02/30 12:00:00", "00000101",
    "20260930 24:00:00", "2026/09/30 12:60:00", "2026-09-30 12:00:60",
    "20260930 12:00", "2026/09/30 12:00:00+08:00", "20260930T12:00:00",
    "20260930 12:00:00.1", " 20260930", "20260930 ", "2026/9/30",
    "２０２６０９３０", "2026/09-30",
])
def test_invalid_dates_and_clocks_fail_before_any_source_read(monkeypatch, call, value):
    def unexpected(*args, **kwargs):
        pytest.fail("日期参数非法时不应读取来源")

    from finchx.api import reference
    from finchx.sources.tencent import klines
    from finchx.sources.tonghuashun import concept
    from finchx.sources.aigupiao import dragon_tiger, news as agp_news
    from finchx.sources.baidu import news as bd_news
    from finchx.sources.eastmoney import news as em_news
    monkeypatch.setattr(reference.szse, "trading_calendar", unexpected)
    for source in [klines, concept, financial]:
        monkeypatch.setattr(source, "get_text", unexpected)
    for source in [dragon_tiger, agp_news, bd_news, em_news]:
        monkeypatch.setattr(source, "get_json", unexpected)
    monkeypatch.setattr(replay, "_capture", unexpected)
    monkeypatch.setattr(deviation.quote, "quote_snapshot", unexpected)
    with pytest.raises(ValueError):
        call(FinchX(), value)


def test_python_date_support_remains_explicit_and_datetime_objects_are_rejected():
    day = date(2026, 9, 30)
    assert parse_date_parameter(day, "date", allow_date_object=True) == day
    with pytest.raises(ValueError):
        parse_date_parameter(day, "date")
    with pytest.raises(ValueError):
        parse_date_parameter(datetime(2026, 9, 30), "date", allow_date_object=True)


@pytest.mark.parametrize("value", ["20260930", "2026/09/30", "2026-09-30 15:30:00"])
def test_source_iso_dates_keep_strict_validation(value):
    with pytest.raises(SourceError):
        deviation._date(value, "来源日期")
    with pytest.raises(SourceError):
        financial._date_text(value, "来源报告期")
    with pytest.raises(SourceError):
        replay._source_date(value, "来源复盘日")


@pytest.mark.parametrize("value", [
    "2026-09-30 15:30:00", "20260930 15:30:00", "2026/09/30 15:30:00",
])
def test_existing_source_date_conversion_does_not_truncate_clock(value):
    with pytest.raises(ValueError):
        parse_date(value, "来源日期")
