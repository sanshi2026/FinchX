"""分时来源身份、端点、相邻点差分及损坏响应验证。"""

from copy import deepcopy
import json
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import SourceError
from finchx.sources.tencent import intraday


def _day(day="20260930", points=None):
    return {"date": day, "data": points if points is not None else ["0930 10.1 1 10.10", "0932 10.2 3 30.20"]}


def _stub(monkeypatch, *, symbol="sh600519", days=None, minute=False, payload=None, wrapper=None):
    days = [_day()] if days is None else days
    document = payload if payload is not None else {"code": 0, "data": {symbol: {"data": days[0] if minute else days}}}
    variable = wrapper or ("min_data_" if minute else "fdays_data_") + symbol
    text = variable + "=" + json.dumps(document, ensure_ascii=False) + ";"
    calls = []

    def get_text(url, **kwargs):
        calls.append((url, kwargs))
        return text

    monkeypatch.setattr(intraday, "get_text", get_text)
    return calls


@pytest.mark.parametrize("method,code,symbol,minute", [
    ("equity_intraday", "600519", "sh600519", False),
    ("equity_intraday_5d", "000001", "sz000001", False),
    ("index_intraday", "000001", "sh000001", True),
    ("index_intraday_5d", "399006", "sz399006", False),
])
def test_endpoints_identity_and_point_units(monkeypatch, method, code, symbol, minute):
    calls = _stub(monkeypatch, symbol=symbol, minute=minute)
    rows = getattr(intraday, method)(code, timeout=7)
    assert rows == [
        {"date": "2026-09-30", "time": "09:30", "price": 10.1, "volume": 100, "amount": 10.1, "cumulative_volume": 100, "cumulative_amount": 10.1},
        {"date": "2026-09-30", "time": "09:32", "price": 10.2, "volume": 200, "amount": 20.1, "cumulative_volume": 300, "cumulative_amount": 30.2},
    ]
    url, kwargs = calls[0]
    assert urlparse(url).path.endswith("/minute/query" if minute else "/day/query")
    assert parse_qs(urlparse(url).query) == {"code": [symbol], "_var": [("min_data_" if minute else "fdays_data_") + symbol]}
    assert kwargs["timeout"] == 7 and kwargs["source"] == "tencent"
    assert len(calls) == 1


def test_latest_days_sorting_reset_and_no_prec_dependency(monkeypatch):
    days = [_day(f"202609{n:02d}", ["0932 1 3 0.30", "930 1 2 0.20"]) for n in range(24, 30)]
    _stub(monkeypatch, days=list(reversed(days)))
    latest = intraday.equity_intraday("600519", timeout=15)
    recent = intraday.equity_intraday_5d("600519", timeout=15)
    assert [row["date"] for row in latest] == ["2026-09-29"] * 2
    assert len(recent) == 10 and recent[0]["date"] == "2026-09-25"
    assert [(row["volume"], row["amount"]) for row in recent] == [(200, 0.2), (100, 0.1)] * 5


def test_missing_numbers_retain_points_and_do_not_create_deltas(monkeypatch):
    points = [["0930", None, None, None], ["0931", "--", "1", "0.20"], ["0932", "0", "2", "0.30"], ["0934", "", None, None], ["0935", "0", "4", "0.40"]]
    _stub(monkeypatch, days=[_day(points=points)])
    rows = intraday.equity_intraday("600519", timeout=15)
    assert len(rows) == 5 and rows[0]["price"] is None
    assert [row["volume"] for row in rows] == [None, None, 100, None, None]
    assert [row["amount"] for row in rows] == [None, None, 0.1, None, None]
    assert rows[2]["price"] == 0 and rows[4]["cumulative_volume"] == 400


def test_zero_values_and_fractional_lot_to_integral_shares(monkeypatch):
    _stub(monkeypatch, days=[_day(points=[[930, 0, 0, 0], [931, 0, "0.01", 0]])])
    rows = intraday.equity_intraday("600519", timeout=15)
    assert rows[0] == {"date": "2026-09-30", "time": "09:30", "price": 0.0, "volume": 0, "amount": 0.0, "cumulative_volume": 0, "cumulative_amount": 0.0}
    assert rows[1]["volume"] == rows[1]["cumulative_volume"] == 1


@pytest.mark.parametrize("method,code", [
    ("equity_intraday", "60051"), ("equity_intraday_5d", "６００５１９"),
    ("equity_intraday", 600519), ("equity_intraday", "bj920001"),
    ("equity_intraday", "920001"), ("index_intraday", "000688"),
    ("index_intraday_5d", "399107"), ("index_intraday", "600519"),
])
def test_invalid_or_unsupported_code_fails_before_request(monkeypatch, method, code):
    calls = _stub(monkeypatch)
    with pytest.raises(ValueError):
        getattr(intraday, method)(code, timeout=15)
    assert calls == []


@pytest.mark.parametrize("text", [
    "", "{}", 'other={"code":0,"data":{}};',
    'fdays_data_sh600519={broken};',
    'fdays_data_sh600519={}; extra={};',
])
def test_wrong_wrapper_or_invalid_json_fails(monkeypatch, text):
    monkeypatch.setattr(intraday, "get_text", lambda *a, **k: text)
    with pytest.raises(SourceError):
        intraday.equity_intraday("600519", timeout=15)


@pytest.mark.parametrize("payload", [
    {}, {"code": False, "data": {}}, {"code": 1, "data": {}},
    {"code": 0, "data": {}},
    {"code": 0, "data": {"sz600519": {"data": []}}},
    {"code": 0, "data": {"sh600519": {}}},
    {"code": 0, "data": {"sh600519": {"data": {}}}},
    {"data": {"sh600519": {"data": []}}},
])
def test_invalid_status_or_missing_series_cannot_masquerade_as_empty(monkeypatch, payload):
    _stub(monkeypatch, payload=payload)
    with pytest.raises(SourceError):
        intraday.equity_intraday("600519", timeout=15)


def test_explicit_success_empty_series_can_return_empty(monkeypatch):
    _stub(monkeypatch, days=[])
    assert intraday.equity_intraday("600519", timeout=15) == []
    _stub(monkeypatch, symbol="sh000001", minute=True, days=[_day(points=[])])
    assert intraday.index_intraday("000001", timeout=15) == []


@pytest.mark.parametrize("day", [
    {"data": ["0930 1 1 1"]}, _day("20260230"), _day("2026/09/30"),
    _day(True), _day(points=["2460 1 1 1"]), _day(points=["09:30 1 1 1"]),
    _day(points=[[None, 1, 1, 1]]), _day(points=["0930 1 1"]),
    _day(points=["0930 bad 1 1"]), _day(points=[[930, True, 1, 1]]),
    _day(points=["0930 NaN 1 1"]), _day(points=["0930 1 -1 1"]),
    _day(points=["0930 1 0.001 1"]), _day(points=["0930 1 1 -1"]),
    _day(points=["0930 -1 1 1"]), _day(points=["0930 1 1 Infinity"]),
    _day(points=None) | {"data": None},
])
def test_source_date_time_structure_and_numbers_are_validated(monkeypatch, day):
    _stub(monkeypatch, days=[day])
    with pytest.raises(SourceError):
        intraday.equity_intraday("600519", timeout=15)


@pytest.mark.parametrize("days", [
    [_day(), deepcopy(_day())],
    [_day(points=["0930 1 1 1", "930 2 2 2"])],
    [_day(points=["0930 1 2 1", "0931 1 1 2"])],
    [_day(points=["0930 1 1 2", "0931 1 2 1"])],
    [_day(points=[[930, 1, 2, 2], [931, 1, None, None], [932, 1, 1, 1]])],
])
def test_duplicate_points_or_cumulative_regression_fail(monkeypatch, days):
    _stub(monkeypatch, days=days)
    with pytest.raises(SourceError):
        intraday.equity_intraday_5d("600519", timeout=15)


def test_each_call_reads_source_and_transport_error_propagates(monkeypatch):
    calls = _stub(monkeypatch)
    intraday.equity_intraday("600519", timeout=15)
    intraday.equity_intraday("600519", timeout=15)
    assert len(calls) == 2
    failure = SourceError("tencent", "网络不可用")

    def broken(*args, **kwargs):
        raise failure

    monkeypatch.setattr(intraday, "get_text", broken)
    with pytest.raises(SourceError) as caught:
        intraday.equity_intraday("600519", timeout=15)
    assert caught.value is failure
