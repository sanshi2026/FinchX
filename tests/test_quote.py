"""单标的行情与盘口的来源身份、列边界及精确单位测试。"""

from http.client import IncompleteRead
from types import SimpleNamespace

import pytest

from finchx import SourceError
from finchx._common import http
from finchx._common.convert import resolve_code, to_decimal, to_number
from finchx.sources.tencent import quote


def text(symbol="sh600519", changes=None, length=58):
    fields = [""] * length
    for index, value in {
        1: "贵州茅台", 2: symbol[2:], 3: "10.23", 4: "10.00", 5: "10.01",
        6: "0.29", 30: "20261008145726", 31: "0.23", 32: "2.30",
        33: "10.30", 34: "10.00", 36: "0.29", 57: "308613.9869",
    }.items():
        if index < length:
            fields[index] = value
    for index, value in (changes or {}).items():
        fields[index] = value
    return f'v_{symbol}="{"~".join(fields)}";'


def install(monkeypatch, value):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return value
    monkeypatch.setattr(quote, "get_text", request)
    return calls


def test_snapshot_identity_source_time_percentage_and_exact_amount(monkeypatch):
    calls = install(monkeypatch, text(changes={9: "无关坏盘口", 10: "无关坏数量"}))
    result = quote.quote_snapshot("600519", timeout=2.5)
    assert result == {
        "code": "600519", "exchange": "sh", "name": "贵州茅台",
        "time": "2026-10-08T14:57:26+08:00", "price": 10.23,
        "previous_close": 10.0, "open": 10.01, "high": 10.3, "low": 10.0,
        "price_change": 0.23, "change_percent": 2.3, "volume": 29, "amount": 3086139869.0,
    }
    assert calls[0][0] == "https://qt.gtimg.cn/q=sh600519"
    assert calls[0][1]["encoding"] == "gbk" and calls[0][1]["timeout"] == 2.5


def test_same_code_kind_changes_requested_identity(monkeypatch):
    calls = []
    def request(url, **kwargs):
        calls.append(url)
        return text(url.rsplit("=", 1)[1])
    monkeypatch.setattr(quote, "get_text", request)
    assert quote.quote_snapshot("000001", timeout=1)["exchange"] == "sz"
    assert quote.quote_snapshot("000001", kind="index", timeout=1)["exchange"] == "sh"
    assert calls == ["https://qt.gtimg.cn/q=sz000001", "https://qt.gtimg.cn/q=sh000001"]


@pytest.mark.parametrize("changes,expected", [
    ({3: "", 6: "", 36: "", 57: "--", 30: "", 1: ""}, {"price": None, "volume": None, "amount": None, "time": None, "name": None}),
    ({3: "0", 6: "0", 36: "0", 57: "0", 31: "-0.23", 32: "-2.3"}, {"price": 0.0, "volume": 0, "amount": 0.0, "price_change": -0.23, "change_percent": -2.3}),
    ({6: "", 36: "10"}, {"volume": 1000}),
])
def test_optional_fields_and_zero_are_distinct(monkeypatch, changes, expected):
    install(monkeypatch, text(changes=changes))
    result = quote.quote_snapshot("600519", timeout=1)
    for key, value in expected.items():
        assert result[key] == value


@pytest.mark.parametrize("changes", [{6: "1", 36: "2"}, {6: "NaN"}, {6: "0.001", 36: "0.001"}, {57: "-1"}, {30: "20260230090000"}, {30: "2026-10-08"}, {2: "600000"}])
def test_snapshot_critical_source_corruption(monkeypatch, changes):
    install(monkeypatch, text(changes=changes))
    with pytest.raises(SourceError):
        quote.quote_snapshot("600519", timeout=1)


@pytest.mark.parametrize("value", [text("sz000001"), 'v_pv_none_match="1";', text(length=57), text() + text()])
def test_snapshot_wrapper_identity_and_schema(monkeypatch, value):
    install(monkeypatch, value)
    with pytest.raises(SourceError):
        quote.quote_snapshot("600519", timeout=1)


def test_orderbook_keeps_all_source_slots_and_ignores_unrelated_quote(monkeypatch):
    changes = {3: "坏现价", 6: "坏成交量", 9: "10", 10: "0.29", 11: "0", 12: "0", 13: "", 14: "1", 15: "9.9", 16: "--", 19: "10.1", 20: "2"}
    install(monkeypatch, text(changes=changes, length=31))
    result = quote.orderbook("600519", timeout=1)
    assert set(result) == {"code", "exchange", "name", "time", "bids", "asks"}
    assert result["bids"] == [
        {"level": 1, "price": 10.0, "volume": 29},
        {"level": 2, "price": 0.0, "volume": 0},
        {"level": 3, "price": None, "volume": 100},
        {"level": 4, "price": 9.9, "volume": None},
        {"level": 5, "price": None, "volume": None},
    ]
    assert result["asks"][0] == {"level": 1, "price": 10.1, "volume": 200}
    assert len(result["asks"]) == 5


@pytest.mark.parametrize("changes", [{9: "-1"}, {10: "-1"}, {10: "0.001"}, {27: "NaN"}])
def test_orderbook_invalid_used_fields_fail(monkeypatch, changes):
    install(monkeypatch, text(changes=changes))
    with pytest.raises(SourceError):
        quote.orderbook("600519", timeout=1)


@pytest.mark.parametrize("code,kind", [(1, "stock"), ("sh600519", "stock"), ("600519 ", "stock"), ("６００５１９", "stock"), ("920001", "stock"), ("000300", "index"), ("000001", "fund")])
def test_parameters_fail_before_source(monkeypatch, code, kind):
    calls = install(monkeypatch, text())
    with pytest.raises(ValueError):
        quote.quote_snapshot(code, kind=kind, timeout=1)
    assert not calls


def test_each_call_is_fresh_and_source_timeout_is_validated(monkeypatch):
    calls = install(monkeypatch, text())
    quote.quote_snapshot("600519", timeout=3)
    quote.quote_snapshot("600519", timeout=3)
    assert len(calls) == 2
    with pytest.raises(ValueError):
        quote.orderbook("600519", timeout=True)
    assert len(calls) == 2


@pytest.mark.parametrize("value", [None, "", "--", "-"])
def test_shared_conversion_missing(value):
    assert to_decimal(value, "value", source="tencent") is None
    assert to_number(value, "value", source="tencent", integer=True) is None


@pytest.mark.parametrize("value", [True, "NaN", "Inf", float("nan"), [], "1_000"])
def test_shared_conversion_invalid(value):
    with pytest.raises(SourceError):
        to_decimal(value, "value", source="tencent")


def test_shared_conversion_exact_scaling_and_code_limits():
    assert to_number("0.29", "volume", source="tencent", scale=2, integer=True) == 29
    assert to_number("12345678901234567890123456789.01", "volume", source="tencent", scale=2, integer=True) == 1234567890123456789012345678901
    assert to_number("-139915.08", "amount", source="tencent", scale=4) == -1399150800.0
    assert resolve_code("399107", "index") == "sz399107"
    with pytest.raises(SourceError):
        to_number("1e10000", "price", source="tencent")


def test_http_text_decodes_gbk_and_reports_truncation(monkeypatch):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return "贵州茅台".encode("gbk")
    monkeypatch.setattr(http, "urlopen", lambda *args, **kwargs: Response())
    assert http.get_text("https://example.invalid", timeout=1, headers={}, source="tencent", encoding="gbk") == "贵州茅台"
    def truncated(*args, **kwargs):
        raise IncompleteRead(b"x", 100)
    monkeypatch.setattr(http, "urlopen", truncated)
    with pytest.raises(SourceError, match="IncompleteRead"):
        http.get_text("https://example.invalid", timeout=1, headers={}, source="tencent")
