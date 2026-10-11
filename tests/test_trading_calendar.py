"""隔离来源请求，验证日历业务字段、关键日期和来源回退。"""

import calendar
from datetime import date, datetime
from http.client import IncompleteRead
import subprocess
import sys
import warnings
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import FinchX, FinchXError, SourceError
from finchx._common import http
from finchx.sources.pandas_market_calendars import calendar as pmc
from finchx.sources.szse import calendar as szse


def month_payload(year, month):
    # 人工测试夹具只验证协议，不作为文档中的真实日历示例。
    return {
        "data": [
            {"jyrq": date(year, month, day).isoformat(), "jybz": "1" if day % 2 else "0", "未知字段": {"值": day}}
            for day in range(1, calendar.monthrange(year, month)[1] + 1)
        ],
        "nowdate": "来源原值",
        "未知顶层字段": [0, None],
    }


@pytest.fixture
def official(monkeypatch):
    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        label = parse_qs(urlparse(url).query)["month"][0]
        return month_payload(*map(int, label.split("-")))

    monkeypatch.setattr(szse, "get_json", request)
    return calls


@pytest.mark.parametrize("value", [date(2024, 2, 29), "2024-02-29", "20240229", "2024/02/29"])
def test_date_formats(value, official):
    rows = FinchX().reference.trading_calendar(value, value, source="szse")
    assert [row["date"] for row in rows] == ["2024-02-29"]


@pytest.mark.parametrize("value", [True, False, None, 20240229, datetime(2024, 2, 29), "2023-02-29", "0000-01-01", "2024-2-29", "2024/02-29", " 2024-02-29", "2024-02-29T00:00:00", "２０２４０２２９"])
@pytest.mark.parametrize("parameter", ["start_date", "end_date"])
def test_invalid_dates_fail_before_request(value, parameter, official):
    args = {"start_date": "2024-02-29", "end_date": "2024-02-29", parameter: value}
    with pytest.raises(ValueError, match=parameter):
        FinchX().reference.trading_calendar(**args)
    assert official == []


@pytest.mark.parametrize("source", [None, True, [], "official", "SZSE", ""])
def test_source_rejected_before_request(source, official):
    with pytest.raises(ValueError, match="source"):
        FinchX().reference.trading_calendar("2024-02-01", "2024-02-01", source=source)
    assert official == []


def test_reversed_range(official):
    with pytest.raises(ValueError, match="不得晚于"):
        FinchX().reference.trading_calendar("2024-03-01", "2024-02-29")
    assert official == []


@pytest.mark.parametrize("timeout", [True, None, "15", 0, -1, float("inf"), float("nan"), 10**1000])
def test_timeout_validation(timeout):
    with pytest.raises(ValueError, match="timeout"):
        FinchX(timeout=timeout)


@pytest.mark.parametrize("start,end,labels", [
    ("2024-02-28", "2024-03-02", ["2024-02", "2024-03"]),
    ("2023-12-31", "2024-01-01", ["2023-12", "2024-01"]),
    (date.max, date.max, ["9999-12"]),
])
def test_complete_inclusive_range(start, end, labels, official):
    rows = FinchX(timeout=2.5).reference.trading_calendar(start, end, source="szse")
    first = date.fromisoformat(rows[0]["date"])
    last = date.fromisoformat(rows[-1]["date"])
    assert len(rows) == (last - first).days + 1
    assert [parse_qs(urlparse(url).query)["month"][0] for url, _ in official] == labels
    assert all(options["timeout"] == 2.5 for _, options in official)
    assert all(options["headers"]["Referer"] == "https://www.szse.cn/aboutus/calendar/" for _, options in official)


def test_official_ignores_noncritical_fields_and_sorts(monkeypatch):
    payload = month_payload(2024, 2)
    payload["data"].reverse()
    monkeypatch.setattr(szse, "get_json", lambda *args, **kwargs: payload)
    rows = FinchX().reference.trading_calendar("2024-02-01", "2024-02-29", source="szse")
    assert [row["date"] for row in rows] == sorted(row["date"] for row in rows)
    assert rows[0] == {"date": "2024-02-01", "is_trading_day": True}
    assert all(set(row) == {"date", "is_trading_day"} for row in rows)


def test_noncritical_source_fields_optional(monkeypatch):
    payload = month_payload(2024, 2)
    del payload["nowdate"]
    monkeypatch.setattr(szse, "get_json", lambda *args, **kwargs: payload)
    api = FinchX().reference
    with_unknown = api.trading_calendar("2024-02-01", "2024-02-02", source="szse")
    for row in payload["data"]:
        row.pop("未知字段")
    del payload["未知顶层字段"]
    without_unknown = api.trading_calendar("2024-02-01", "2024-02-02", source="szse")
    assert without_unknown == with_unknown == [
        {"date": "2024-02-01", "is_trading_day": True},
        {"date": "2024-02-02", "is_trading_day": False},
    ]


@pytest.mark.parametrize("defect,match", [
    ("missing", "缺少"), ("duplicate", "日期重复"), ("month", "其他月份"),
    ("flag_int", "jybz"), ("flag_unknown", "jybz"), ("date", "jyrq"),
    ("row", "结构无效"), ("envelope", "data"), ("data", "data"),
])
def test_official_corruption_fails_entire_month(monkeypatch, defect, match):
    payload = month_payload(2024, 2)
    if defect == "missing":
        payload["data"].pop()  # 缺失请求范围外的日期仍表示官方整月响应损坏。
    elif defect == "duplicate":
        payload["data"].append(payload["data"][0])
    elif defect == "month":
        payload["data"][0]["jyrq"] = "2024-03-01"
    elif defect.startswith("flag"):
        payload["data"][0]["jybz"] = 1 if defect == "flag_int" else "2"
    elif defect == "date":
        payload["data"][0]["jyrq"] = "2024-02-30"
    elif defect == "row":
        payload["data"][0] = None
    elif defect == "envelope":
        payload = []
    else:
        payload["data"] = {}
    monkeypatch.setattr(szse, "get_json", lambda *args, **kwargs: payload)
    with pytest.raises(SourceError, match=match) as caught:
        FinchX().reference.trading_calendar("2024-02-01", "2024-02-01", source="szse")
    assert caught.value.source == "szse"


def test_explicit_official_never_falls_back(monkeypatch):
    error = SourceError("szse", "来源结构损坏")
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(szse, "trading_calendar", fail)
    monkeypatch.setattr(pmc, "trading_calendar", lambda *args: pytest.fail("不应回退"))
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(SourceError) as caught:
            FinchX().reference.trading_calendar("2024-01-01", "2024-01-01", source="szse")
    assert emitted == []
    assert caught.value is error


def test_auto_falls_back_whole_range_after_later_month_failure(monkeypatch, official):
    request = szse.get_json
    def second_month_fails(url, **kwargs):
        if "2024-03" in url:
            raise SourceError("szse", "三月请求失败")
        return request(url, **kwargs)
    monkeypatch.setattr(szse, "get_json", second_month_fails)
    calls = []
    def fallback(start, end):
        calls.append((start, end))
        return [{"date": date.fromordinal(day).isoformat(), "is_trading_day": False}
                for day in range(start.toordinal(), end.toordinal() + 1)]
    monkeypatch.setattr(pmc, "trading_calendar", fallback)
    with pytest.warns(UserWarning, match="三月请求失败") as emitted:
        rows = FinchX().reference.trading_calendar("2024-02-29", "2024-03-01")
    assert len(emitted) == 1
    assert emitted[0].filename == __file__
    assert "整段请求" in str(emitted[0].message)
    assert "pandas_market_calendars 的 SSE 离线日历" in str(emitted[0].message)
    assert calls == [(date(2024, 2, 29), date(2024, 3, 1))]
    assert [row["date"] for row in rows] == ["2024-02-29", "2024-03-01"]
    # 官方二月夹具标记 2/29 开市；回退结果全部休市，不能混入该官方行。
    assert all(row["is_trading_day"] is False for row in rows)
    assert all(set(row) == {"date", "is_trading_day"} for row in rows)


def test_two_source_failures_keep_both_contexts(monkeypatch):
    primary = SourceError("szse", "官方断开")
    fallback = SourceError("pandas_market_calendars", "依赖缺失")
    def fail_primary(*args, **kwargs):
        raise primary
    def fail_fallback(*args, **kwargs):
        raise fallback
    monkeypatch.setattr(szse, "trading_calendar", fail_primary)
    monkeypatch.setattr(pmc, "trading_calendar", fail_fallback)
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(FinchXError) as caught:
            FinchX().reference.trading_calendar("2024-01-01", "2024-01-01")
    assert emitted == []
    assert caught.value.errors == (primary, fallback)
    assert caught.value.__cause__ is fallback
    assert "官方断开" in str(caught.value) and "依赖缺失" in str(caught.value)


def test_each_call_requests_source_again(official):
    api = FinchX().reference
    api.trading_calendar("2024-02-01", "2024-02-01")
    api.trading_calendar("2024-02-01", "2024-02-01")
    assert len(official) == 2


def test_import_and_official_success_without_optional_dependency(official, monkeypatch):
    def unavailable(*args):
        raise ImportError("测试依赖缺失")
    monkeypatch.setattr(pmc, "import_module", unavailable)
    assert FinchX().reference.trading_calendar("2024-02-01", "2024-02-01") == [{"date": "2024-02-01", "is_trading_day": True}]
    with pytest.raises(SourceError, match=r"finchx\[calendar\]"):
        FinchX().reference.trading_calendar("2024-02-01", "2024-02-01", source="pandas_market_calendars")
    # 独立进程确认顶层导入本身也没有导入可选依赖。
    script = "import sys; import finchx; assert 'pandas_market_calendars' not in sys.modules"
    subprocess.run([sys.executable, "-c", script], check=True, env={**__import__("os").environ, "PYTHONPATH": "src"})


def install_pmc(monkeypatch, days):
    calls = []
    def valid_days(**kwargs):
        calls.append(kwargs)
        return days
    def get_calendar(name):
        assert name == "SSE"
        return SimpleNamespace(valid_days=valid_days)
    monkeypatch.setattr(pmc, "import_module", lambda name: SimpleNamespace(get_calendar=get_calendar))
    return calls


def test_pmc_natural_days_from_valid_days(monkeypatch, official):
    calls = install_pmc(monkeypatch, [datetime(2024, 2, 29)])
    rows = FinchX().reference.trading_calendar("2024-02-28", "2024-03-01", source="pandas_market_calendars")
    assert official == []
    assert calls == [{"start_date": "2024-02-28", "end_date": "2024-03-01"}]
    assert [row["is_trading_day"] for row in rows] == [False, True, False]
    assert [row["date"] for row in rows] == ["2024-02-28", "2024-02-29", "2024-03-01"]
    assert all(set(row) == {"date", "is_trading_day"} for row in rows)


@pytest.mark.parametrize("defect", ["outside", "duplicate", "missing", "not_date", "date_time"])
def test_invalid_pmc_trading_dates_fail(monkeypatch, defect):
    days = [datetime(2024, 2, 29)]
    if defect == "outside":
        days = [datetime(2024, 3, 1)]
    elif defect == "duplicate":
        days *= 2
    elif defect == "missing":
        days = [None]
    elif defect == "not_date":
        days = [SimpleNamespace(date=lambda: "2024-02-29")]
    else:
        days = [SimpleNamespace(date=lambda: datetime(2024, 2, 29))]
    install_pmc(monkeypatch, days)
    with pytest.raises(SourceError, match="SSE 交易日期生成失败"):
        FinchX().reference.trading_calendar("2024-02-29", "2024-02-29", source="pandas_market_calendars")


def test_pmc_limit_is_reported_not_fabricated(monkeypatch):
    def get_calendar(name):
        raise OverflowError("来源日期越界")
    monkeypatch.setattr(pmc, "import_module", lambda name: SimpleNamespace(get_calendar=get_calendar))
    with pytest.raises(SourceError, match="OverflowError"):
        FinchX().reference.trading_calendar(date.max, date.max, source="pandas_market_calendars")


@pytest.mark.parametrize("failure", [RuntimeError("损坏依赖"), ValueError("损坏配置")])
def test_pmc_import_failure_preserves_explicit_and_auto_context(monkeypatch, failure):
    primary_error = SourceError("szse", "官方请求失败")
    def fail_official(*args, **kwargs):
        raise primary_error
    def fail_import(name):
        raise failure
    monkeypatch.setattr(szse, "trading_calendar", fail_official)
    monkeypatch.setattr(pmc, "import_module", fail_import)
    with pytest.raises(SourceError, match="日历依赖加载失败") as explicit:
        FinchX().reference.trading_calendar("2024-02-29", "2024-02-29", source="pandas_market_calendars")
    assert explicit.value.__cause__ is failure
    assert explicit.value.source == "pandas_market_calendars"
    with pytest.raises(FinchXError) as auto:
        FinchX().reference.trading_calendar("2024-02-29", "2024-02-29")
    assert auto.value.errors[0] is primary_error
    assert auto.value.errors[1].__cause__ is failure
    assert "日历依赖加载失败" in auto.value.errors[1].reason


@pytest.mark.parametrize("defect", ["http", "network", "json"])
def test_http_failures_are_source_errors(monkeypatch, defect):
    def opener(*args, **kwargs):
        if defect == "http":
            raise HTTPError("https://example.invalid", 403, "拒绝", {}, None)
        if defect == "network":
            raise URLError("测试断开")
    if defect == "json":
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return b"not-json"
        opener = lambda *args, **kwargs: Response()
    monkeypatch.setattr(http, "urlopen", opener)
    with pytest.raises(SourceError):
        http.get_json("https://example.invalid", timeout=1, headers={}, source="szse")


def test_incomplete_read_explicit_error_and_auto_fallback(monkeypatch):
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            raise IncompleteRead(b"{", 100)
    monkeypatch.setattr(http, "urlopen", lambda *args, **kwargs: Response())
    calls = []
    def fallback(start, end):
        calls.append((start, end))
        return [{"date": date.fromordinal(day).isoformat(), "is_trading_day": False}
                for day in range(start.toordinal(), end.toordinal() + 1)]
    monkeypatch.setattr(pmc, "trading_calendar", fallback)
    with pytest.raises(SourceError, match="IncompleteRead") as caught:
        FinchX().reference.trading_calendar("2024-02-29", "2024-03-01", source="szse")
    assert isinstance(caught.value.__cause__, IncompleteRead)
    assert calls == []
    with pytest.warns(UserWarning, match="IncompleteRead"):
        rows = FinchX().reference.trading_calendar("2024-02-29", "2024-03-01")
    assert calls == [(date(2024, 2, 29), date(2024, 3, 1))]
    assert len(rows) == 2


@pytest.mark.parametrize("source", ["szse", "pandas_market_calendars", "auto"])
def test_success_contract_and_no_warning(monkeypatch, official, source):
    install_pmc(monkeypatch, [datetime(2024, 2, 29), datetime(2024, 3, 1)])
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        rows = FinchX().reference.trading_calendar("2024-02-28", "2024-03-01", source=source)
    assert emitted == []
    assert [row["date"] for row in rows] == ["2024-02-28", "2024-02-29", "2024-03-01"]
    assert [row["is_trading_day"] for row in rows] == [False, True, True]
    assert all(set(row) == {"date", "is_trading_day"} for row in rows)
    assert all(type(row["date"]) is str and type(row["is_trading_day"]) is bool for row in rows)


@pytest.mark.parametrize("value", ['2026-09-30', '20260930', '2026/09/30', '2026-09-30 15:30:00', '20260930 15:30:00', '2026/09/30 15:30:00'])
def test_all_date_string_formats_and_validated_clock_select_same_calendar_day(value, official):
    rows = FinchX().reference.trading_calendar(value, value, source="szse")
    assert rows == [{"date": "2026-09-30", "is_trading_day": False}]
