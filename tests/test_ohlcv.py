"""日 K 线的真实列布局、复权身份与完整倒页边界测试。"""

from datetime import date, timedelta
import json
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import SourceError
from finchx.sources.tencent import klines


def bar(day="2026-09-30", *, prices=None, volume="38331.00", amount="479724.66", long=True):
    values = [day, *(prices or ["1239.53", "1258.62", "1268.00", "1236.05"]), volume]
    return values + [{"未知字段": "保留于来源但不解释"}, "不是成交额", amount, ""] if long else values


def response(rows, *, symbol="sh600519", variable="kline_day", series="day", code=0):
    return variable + "=" + json.dumps({"code": code, "data": {symbol: {series: rows}}}) + ";"


def install(monkeypatch, value):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return value
    monkeypatch.setattr(klines, "get_text", request)
    return calls


def test_daily_fields_actual_column_order_and_units(monkeypatch):
    calls = install(monkeypatch, response([bar()]))
    result = klines.ohlcv("600519", "2026-09-30", "2026-10-08", timeout=2.5)
    assert result == [{"date": "2026-09-30", "open": 1239.53, "high": 1268.0, "low": 1236.05, "close": 1258.62, "volume": 3833100, "amount": 4797246600.0}]
    params = parse_qs(urlparse(calls[0][0]).query)
    assert params == {"_var": ["kline_day"], "param": ["sh600519,day,,2026-10-08,800,none"]}
    assert calls[0][1]["timeout"] == 2.5


@pytest.mark.parametrize("mode,variable,series", [(None, "kline_day", "day"), ("qfq", "kline_dayqfq", "qfqday"), ("hfq", "kline_dayhfq", "hfqday")])
def test_adjustment_selects_only_requested_series(monkeypatch, mode, variable, series):
    calls = install(monkeypatch, response([bar()], variable=variable, series=series))
    assert len(klines.ohlcv("600519", "2026-09-30", "2026-09-30", mode, timeout=1)) == 1
    assert parse_qs(urlparse(calls[0][0]).query)["_var"] == [variable]


def test_qfq_never_silently_returns_day(monkeypatch):
    install(monkeypatch, response([bar()], variable="kline_dayqfq", series="day"))
    with pytest.raises(SourceError, match="qfqday"):
        klines.ohlcv("600519", "2026-09-30", "2026-09-30", "qfq", timeout=1)


def test_empty_requested_series_is_valid(monkeypatch):
    install(monkeypatch, response([], variable="kline_dayqfq", series="qfqday"))
    assert klines.ohlcv("600519", "2026-09-30", "2026-09-30", "qfq", timeout=1) == []


def test_missing_and_zero_price_volume_amount_are_not_fabricated(monkeypatch):
    rows = [bar("2026-09-29", prices=["", "--", "-", None], volume=None, long=False), bar("2026-09-30", prices=["0", "0", "0", "0"], volume="0", amount="0")]
    install(monkeypatch, response(rows))
    result = klines.ohlcv("600519", "20260929", "2026/09/30", timeout=1)
    assert all(value is None for key, value in result[0].items() if key != "date")
    assert all(value == 0 for key, value in result[1].items() if key != "date")


def test_paging_reads_beyond_800_including_source_extra_day(monkeypatch):
    start = date(2020, 1, 1)
    rows = [bar((start + timedelta(days=offset)).isoformat(), volume="0.29") for offset in range(1002)]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        end = date.fromisoformat(params["param"][0].split(",")[3])
        candidates = [row for row in rows if date.fromisoformat(row[0]) <= end]
        page = candidates[-801:] if not calls else candidates[-800:]
        calls.append((end, kwargs["timeout"]))
        return response(list(reversed(page)))
    monkeypatch.setattr(klines, "get_text", request)
    end = start + timedelta(days=1001)
    result = klines.ohlcv("600519", start, end, timeout=4)
    assert len(result) == 1002
    assert result[0]["date"] == start.isoformat() and result[-1]["date"] == end.isoformat()
    assert [row["date"] for row in result] == sorted(row["date"] for row in result)
    assert all(row["volume"] == 29 for row in result)
    assert calls == [(end, 4), (start + timedelta(days=200), 4)]


def test_source_exhaustion_and_trim_before_requested_start(monkeypatch):
    install(monkeypatch, response([bar("2026-09-29"), bar("2026-09-30")]))
    result = klines.ohlcv("600519", "2026-09-30", "2026-10-08", timeout=1)
    assert [row["date"] for row in result] == ["2026-09-30"]


@pytest.mark.parametrize("rows", [[bar(), bar()], [bar("2026-10-09")], [bar("2026-02-30")], [bar(prices=["10", "10", "9", "8"])], [bar(prices=["8", "10", "11", "9"])], [bar(volume="0.001")], [bar(amount="-1")], [bar(prices=["NaN", "10", "11", "9"])], [["2026-09-30", "1"]]])
def test_corrupt_source_rows_fail(monkeypatch, rows):
    install(monkeypatch, response(rows))
    with pytest.raises(SourceError):
        klines.ohlcv("600519", "2026-09-01", "2026-10-08", timeout=1)


def test_stalled_or_duplicate_pages_fail_instead_of_looping(monkeypatch):
    start = date(2020, 1, 1)
    rows = [bar((start + timedelta(days=offset)).isoformat()) for offset in range(800)]
    install(monkeypatch, response(rows))
    with pytest.raises(SourceError):
        klines.ohlcv("600519", "2019-01-01", "2023-01-01", timeout=1)


@pytest.mark.parametrize("value", [response([], symbol="sz000001"), response([], variable="wrong"), response([], code=1), response([], code=True), "kline_day=bad", "[]"])
def test_schema_status_and_symbol_identity_fail(monkeypatch, value):
    install(monkeypatch, value)
    with pytest.raises(SourceError):
        klines.ohlcv("600519", "2026-09-30", "2026-09-30", timeout=1)


def test_index_is_explicit_and_units_remain_index_points(monkeypatch):
    calls = install(monkeypatch, response([bar()], symbol="sh000001"))
    assert klines.ohlcv("000001", "2026-09-30", "2026-09-30", kind="index", timeout=1)[0]["close"] == 1258.62
    assert "sh000001" in parse_qs(urlparse(calls[0][0]).query)["param"][0]
    with pytest.raises(ValueError):
        klines.ohlcv("000001", "2026-09-30", "2026-09-30", "qfq", kind="index", timeout=1)
    assert len(calls) == 1


@pytest.mark.parametrize("args", [
    {"code": 1}, {"code": "920001"}, {"kind": "other"}, {"adjustment": "none"},
    {"adjustment": True}, {"start_date": "2026-10-09"}, {"end_date": "2026-02-30"}, {"timeout": 0},
])
def test_invalid_parameters_fail_before_source(monkeypatch, args):
    calls = install(monkeypatch, response([]))
    values = {"code": "600519", "start_date": "2026-09-01", "end_date": "2026-10-08", "timeout": 1, **args}
    with pytest.raises(ValueError):
        klines.ohlcv(**values)
    assert not calls


@pytest.mark.parametrize("value", ['2026-09-30', '20260930', '2026/09/30', '2026-09-30 15:30:00', '20260930 15:30:00', '2026/09/30 15:30:00'])
def test_all_date_string_formats_select_same_daily_interval(monkeypatch, value):
    calls = install(monkeypatch, response([bar()]))
    from finchx import FinchX
    rows = FinchX().market.ohlcv("600519", value, value)
    assert [row["date"] for row in rows] == ["2026-09-30"]
    assert parse_qs(urlparse(calls[0][0]).query)["param"] == ["sh600519,day,,2026-09-30,800,none"]
