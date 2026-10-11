"""同花顺概念业务契约；fixtures 为官方原文，异常场景明确模拟。"""

import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

import pytest

from finchx import FinchX, SourceError
from finchx.sources.tonghuashun import concept

_FIXTURES = Path(__file__).parent / "fixtures"
_LIST = (_FIXTURES / "tonghuashun_concept_list.html").read_text(encoding="utf-8")
_DETAIL = (_FIXTURES / "tonghuashun_concept_detail.html").read_text(encoding="utf-8")
_QUOTE = (_FIXTURES / "tonghuashun_concept_quote.txt").read_text(encoding="utf-8")
_YEAR = (_FIXTURES / "tonghuashun_concept_year.txt").read_text(encoding="utf-8")
_LAST = (_FIXTURES / "tonghuashun_concept_last.txt").read_text(encoding="utf-8")
_SNAPSHOT_FIELDS = {"code", "name", "date", "time", "index_level", "previous_close", "open", "high", "low",
                    "level_change", "change_percent", "volume", "amount", "net_inflow", "up_count", "down_count"}
_BAR_FIELDS = {"date", "open", "high", "low", "close", "volume", "amount"}


@pytest.fixture(autouse=True)
def fixed_request_clock(monkeypatch):
    """仅固定滚动文件的请求调度时钟；业务日期仍读取来源 CSV。"""
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            current = cls(2026, 10, 8, 12, tzinfo=timezone(timedelta(hours=8)))
            return current.astimezone(tz) if tz is not None else current.replace(tzinfo=None)

    monkeypatch.setattr(concept, "datetime", FixedDatetime)


def unwrapped(text):
    return json.loads(text[text.index("(") + 1:text.rindex(")")])


def wrapped(original, payload):
    return original[:original.index("(") + 1] + json.dumps(payload, ensure_ascii=False) + ")"


def serve(monkeypatch, *, directory=_LIST, detail=_DETAIL, quote=_QUOTE, year=_YEAR, last=_LAST):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        if "/gn/detail/" in url:
            return detail
        if "realhead" in url:
            return quote
        if "line" in url:
            return last if "last" in url else year
        if "/gn/" in url:
            return directory
        raise AssertionError(f"意外请求：{url}")
    monkeypatch.setattr(concept, "get_text", request)
    return calls


def assert_http(calls, timeout=20):
    assert all(kwargs["timeout"] == timeout and kwargs["source"] == "tonghuashun.concept"
               and kwargs["encoding"] == "gb18030" for _, kwargs in calls)


def test_real_directory_union_includes_links_only_and_hidden_only_in_source_order_contract(monkeypatch):
    calls = serve(monkeypatch)
    rows = FinchX(timeout=20).sector.ths_concept_list()
    assert len(rows) == 387
    assert all(set(row) == {"code", "name"} and re.fullmatch(r"[0-9]{6}", row["code"]) for row in rows)
    assert [row["code"] for row in rows] == sorted({row["code"] for row in rows})
    by_code = {row["code"]: row["name"] for row in rows}
    assert by_code["302035"] == "人工智能"
    assert "300008" in by_code  # 真实目录仅链接提供。
    assert "309022" in by_code and by_code["309022"] == "Web3.0"  # 仅 gnSection 提供。
    assert len(calls) == 1 and "/gn/" in calls[0][0]
    assert FinchX(timeout=20).sector.ths_concept_list() == rows and len(calls) == 2
    assert_http(calls)


def test_directory_union_dedup_and_unrelated_links_do_not_become_concepts(monkeypatch):
    # 模拟来源：重复相同概念、目录外域名和行业链接，以及只出现于一个块的合法概念。
    text = '''<a href="/gn/detail/code/302035/">人工智能</a>
    <a href="http://q.10jqka.com.cn/gn/detail/code/302035/">人工智能</a>
    <a href="/gn/detail/code/302036/">人工智能</a>
    <a href="https://example.invalid/gn/detail/code/309999/">站外</a>
    <a href="/thshy/detail/code/309998/">行业</a>
    <input id="gnSection" value='{"1":{"cid":"000001","platecode":"885111","platename":"仅隐藏"}}'>'''
    serve(monkeypatch, directory=text)
    assert concept.ths_concept_list(timeout=20) == [{"code":"000001","name":"仅隐藏"}, {"code":"302035","name":"人工智能"}, {"code":"302036","name":"人工智能"}]


@pytest.mark.parametrize("text", [
    '<a href="/gn/detail/code/302035/">人工智能</a><a href="/gn/detail/code/302035/">不同名称</a>',
    '<a href="/gn/detail/code/302035/">人工智能</a><input id="gnSection" value=\'{"1":{"cid":"302035","platename":"不同名称"}}\'>',
    '<a href="/gn/detail/code/30203/">坏身份</a>',
    '<a href="/gn/detail/code/３０２０３５/">坏身份</a>',
    '<input id="gnSection" value="not-json">',
    '<input id="gnSection" value=\'{"1":{"cid":302035,"platename":"人工智能"}}\'>',
])
def test_known_directory_corruption_is_not_silently_partial(monkeypatch, text):
    serve(monkeypatch, directory=text)
    with pytest.raises(SourceError):
        concept.ths_concept_list(timeout=20)


def test_real_snapshot_exact_units_source_time_and_two_fresh_requests(monkeypatch):
    calls = serve(monkeypatch)
    api = FinchX(timeout=20).sector
    row = api.ths_concept_quote_snapshot("302035")
    assert set(row) == _SNAPSHOT_FIELDS
    assert row == {"code":"302035", "name":"人工智能", "date":"2026-10-08", "time":"15:00",
                   "index_level":1250.956, "previous_close":1273.197, "open":1274.838,
                   "high":1282.946, "low":1243.436, "level_change":-22.241, "change_percent":-1.75,
                   "volume":19950267000, "amount":318787330000.0, "net_inflow":-24831000000.0,
                   "up_count":205, "down_count":863}
    assert type(row["volume"]) is int and type(row["up_count"]) is int
    assert len(calls) == 2 and "/detail/code/302035/" in calls[0][0]
    assert all(not ("/gn/" in url and "/detail/" not in url) for url, _ in calls)
    assert api.ths_concept_quote_snapshot("302035") == row and len(calls) == 4
    assert_http(calls)


def test_snapshot_missing_update_time_never_falls_back_to_server_clock_and_zero_survives(monkeypatch):
    payload = unwrapped(_QUOTE)
    payload["items"].pop("updateTime")
    payload["items"].update({"10":None,"13":"0","19":"0","38":"0","39":None,"264648":"0","199112":"0"})
    serve(monkeypatch, quote=wrapped(_QUOTE,payload))
    row = concept.ths_concept_quote_snapshot("302035",timeout=20)
    assert row["date"] is None and row["time"] is None
    assert row["index_level"] is None and row["down_count"] is None
    assert row["volume"] == row["amount"] == row["up_count"] == row["level_change"] == row["change_percent"] == 0
    assert set(row) == _SNAPSHOT_FIELDS


@pytest.mark.parametrize("field,value", [("updateTime","2026-02-29 15:00"),("updateTime","2026-10-08 25:00"),
    ("updateTime",True),("5","885729"),("13",-1),("13",True),("13","1.5"),("19",-1),
    ("38",-1),("39",True),("10",float("nan")),("10",[]),("264648",False)])
def test_snapshot_invalid_known_source_values_fail(monkeypatch,field,value):
    payload = unwrapped(_QUOTE); payload["items"][field]=value
    serve(monkeypatch,quote=wrapped(_QUOTE,payload))
    with pytest.raises(SourceError):
        concept.ths_concept_quote_snapshot("302035",timeout=20)


def test_snapshot_missing_optional_detail_flow_keeps_identity_and_unknown_does_not_break(monkeypatch):
    detail = _DETAIL.replace('-248.31','--')
    payload=unwrapped(_QUOTE); payload["items"]["unknown"]={"bad":[]}
    serve(monkeypatch,detail=detail,quote=wrapped(_QUOTE,payload))
    row=concept.ths_concept_quote_snapshot("302035",timeout=20)
    assert row["net_inflow"] is None and row["name"] == "人工智能" and row["volume"] == 19950267000


def test_real_daily_full_year_ascending_inclusive_shares_amount_and_no_today_bar(monkeypatch):
    calls=serve(monkeypatch)
    rows=FinchX(timeout=20).sector.ths_concept_ohlcv("302035","2026-01-01","2026-10-08")
    assert len(rows)==181 and all(set(row)==_BAR_FIELDS for row in rows)
    assert [row["date"] for row in rows] == sorted({row["date"] for row in rows})
    assert rows[0]=={"date":"2026-01-05","open":1391.917,"high":1421.110,"low":1390.401,
                      "close":1421.110,"volume":35323956000,"amount":645934740000.0}
    assert rows[-1]=={"date":"2026-09-30","open":1283.440,"high":1283.624,"low":1270.619,
                       "close":1273.197,"volume":18118957000,"amount":287163320000.0}
    assert len(calls)<=3 and any("2026" in url for url,_ in calls) and any("last" in url for url,_ in calls)
    first_request_count=len(calls)
    assert FinchX(timeout=20).sector.ths_concept_ohlcv("302035","2026-01-01","2026-10-08") == rows
    assert len(calls)==first_request_count*2
    assert_http(calls)


def test_daily_last_overlap_replaces_whole_row_not_cross_field_fill(monkeypatch):
    year=unwrapped(_YEAR); last=unwrapped(_LAST)
    # 模拟 last 对年度最后一行的来源修订：缺量也必须保留为空，不能取年度旧量拼接。
    last["data"]="20260930,1283.440,1284.000,1270.619,1274.000,,0,,,,0"
    serve(monkeypatch,year=wrapped(_YEAR,year),last=wrapped(_LAST,last))
    rows=concept.ths_concept_ohlcv("302035","2026-09-30","2026-09-30",timeout=20)
    assert rows==[{"date":"2026-09-30","open":1283.440,"high":1284.0,"low":1270.619,
                  "close":1274.0,"volume":None,"amount":0.0}]


@pytest.mark.parametrize("line", [
    "20260229,1,2,0,1,0,0", "20260930,1,2,0,1,-1,0", "20260930,1,2,0,1,0,-1",
    "20260930,1,2,0,1,1.5,0", "20260930,NaN,2,0,1,0,0", "20250930,1,2,0,1,0,0",
])
def test_daily_invalid_date_unit_or_year_identity_fails(monkeypatch,line):
    year=unwrapped(_YEAR); year["data"]=line
    serve(monkeypatch,year=wrapped(_YEAR,year))
    with pytest.raises(SourceError):
        concept.ths_concept_ohlcv("302035","2026-01-01","2026-10-08",timeout=20)


@pytest.mark.parametrize("target", ["year","last"])
def test_daily_same_file_duplicate_is_not_an_overlap_merge(monkeypatch,target):
    payload=unwrapped(_YEAR if target=="year" else _LAST)
    first=payload["data"].split(';')[0]; payload["data"]=first+';'+first
    override={target:wrapped(_YEAR if target=="year" else _LAST,payload)}
    serve(monkeypatch,**override)
    with pytest.raises(SourceError):
        concept.ths_concept_ohlcv("302035","2026-01-01","2026-10-08",timeout=20)


@pytest.mark.parametrize("code", [None,302035,True,"30203","３０２０３５","bk885728"," 302035"])
def test_bad_concept_identity_fails_before_network(monkeypatch,code):
    calls=serve(monkeypatch)
    with pytest.raises(ValueError):
        concept.ths_concept_quote_snapshot(code,timeout=20)
    with pytest.raises(ValueError):
        concept.ths_concept_ohlcv(code,"2026-01-01","2026-10-08",timeout=20)
    assert calls==[]


@pytest.mark.parametrize("start,end", [("2026-10-08","2026-01-01"),("2026-02-29","2026-10-08"),(True,"2026-10-08"),(None,"2026-10-08")])
def test_invalid_required_date_range_fails_before_network(monkeypatch,start,end):
    calls=serve(monkeypatch)
    with pytest.raises(ValueError):
        concept.ths_concept_ohlcv("302035",start,end,timeout=20)
    assert calls==[]


def test_public_signatures_and_no_legacy_concept_aliases():
    api=FinchX().sector
    assert list(inspect.signature(api.ths_concept_list).parameters)==[]
    assert list(inspect.signature(api.ths_concept_quote_snapshot).parameters)==["code"]
    assert list(inspect.signature(api.ths_concept_ohlcv).parameters)==["code","start_date","end_date"]
    assert not hasattr(FinchX().market,"concept_quote_snapshot")
    assert not hasattr(FinchX().market,"concept_ohlcv")
    for name in ("concept_list", "concept_quote_snapshot", "concept_ohlcv"):
        assert not hasattr(api, name)


@pytest.mark.parametrize("timeout", [True,0,float("inf"),"20"])
def test_invalid_timeout_fails_before_all_three_requests(monkeypatch,timeout):
    calls=serve(monkeypatch)
    for invoke in [lambda:concept.ths_concept_list(timeout=timeout),
                   lambda:concept.ths_concept_quote_snapshot("302035",timeout=timeout),
                   lambda:concept.ths_concept_ohlcv("302035","2026-01-01","2026-10-08",timeout=timeout)]:
        with pytest.raises(ValueError):
            invoke()
    assert calls==[]


def test_explicit_transport_failure_is_not_retried_or_returned_as_empty(monkeypatch):
    calls=[]
    error=SourceError("tonghuashun","模拟来源不可达")
    def fail(*args,**kwargs):
        calls.append(args); raise error
    monkeypatch.setattr(concept,"get_text",fail)
    for invoke in [lambda:concept.ths_concept_list(timeout=20),
                   lambda:concept.ths_concept_quote_snapshot("302035",timeout=20),
                   lambda:concept.ths_concept_ohlcv("302035","2026-01-01","2026-10-08",timeout=20)]:
        with pytest.raises(SourceError) as caught:
            invoke()
        assert caught.value is error
    assert len(calls)==3


@pytest.mark.parametrize("quote", ['callback({});alert(1)','callback({"items":[]})'])
def test_quote_wrapper_or_required_structure_corruption_fails(monkeypatch,quote):
    serve(monkeypatch,quote=quote)
    with pytest.raises(SourceError):
        concept.ths_concept_quote_snapshot("302035",timeout=20)


def test_daily_source_name_cannot_be_for_another_concept(monkeypatch):
    last=unwrapped(_LAST); last["name"]="另一概念"
    serve(monkeypatch,last=wrapped(_LAST,last))
    with pytest.raises(SourceError):
        concept.ths_concept_ohlcv("302035","2026-01-01","2026-10-08",timeout=20)


def test_concept_code_is_not_checked_against_stock_prefixes(monkeypatch):
    # 模拟合法目录概念身份；行情身份仍由每次详情取得。
    calls=serve(monkeypatch,detail=_DETAIL.replace("code/302035","code/900001"))
    row=concept.ths_concept_quote_snapshot("900001",timeout=20)
    assert row["code"]=="900001" and row["name"]=="人工智能"
    assert len(calls)==2 and "/detail/code/900001/" in calls[0][0]


def test_daily_only_requested_years_are_loaded_and_inclusive_boundary_survives(monkeypatch):
    # 模拟前一年文件，行数字取真实原文，仅日期改为另一合法年份。
    calls=[]
    year_2025=unwrapped(_YEAR)
    year_2025["data"]=year_2025["data"].replace("2026","2025")
    def request(url,**kwargs):
        calls.append((url,kwargs))
        if "/detail/" in url: return _DETAIL
        if "/2025.js" in url: return wrapped(_YEAR,year_2025)
        if "/2026.js" in url: return _YEAR
        if "/last.js" in url: return _LAST
        raise AssertionError(f"非必要年份请求：{url}")
    monkeypatch.setattr(concept,"get_text",request)
    rows=concept.ths_concept_ohlcv("302035","2025-09-30","2026-01-05",timeout=20)
    assert [row["date"] for row in rows]==["2025-09-30","2026-01-05"]
    assert len(calls)<=4 and all("2024.js" not in url and "2027.js" not in url for url,_ in calls)
    assert_http(calls)


@pytest.mark.parametrize("value", ['2026-09-30', '20260930', '2026/09/30', '2026-09-30 15:30:00', '20260930 15:30:00', '2026/09/30 15:30:00'])
def test_all_date_string_formats_select_same_concept_daily_interval(monkeypatch, value):
    serve(monkeypatch)
    rows = FinchX().sector.ths_concept_ohlcv("302035", value, value)
    assert [row["date"] for row in rows] == ["2026-09-30"]
