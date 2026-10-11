"""龙虎榜真实事件、计数口径、直接详情映射与损坏响应验证。"""

from copy import deepcopy
from datetime import date as calendar_date
import inspect
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import FinchX, SourceError
from finchx.sources.aigupiao import dragon_tiger as source

_FIXTURES = Path(__file__).parent / "fixtures"
_LIST = json.loads((_FIXTURES / "fupan_agp_list.json").read_text(encoding="utf-8"))
_DETAIL = json.loads((_FIXTURES / "fupan_agp_detail.json").read_text(encoding="utf-8"))
_LIST_FIELDS = {"code", "exchange", "name", "trade_id", "close_price", "change_percent", "amount", "total_buy", "total_net", "explanation", "period_label", "theme_id", "theme_name"}
_DETAIL_FIELDS = {"code", "exchange", "name", "close_price", "change_percent", "amount", "total_buy", "total_sell", "total_net", "explanation", "buy_seats", "sell_seats"}
_SEAT_FIELDS = {"seat_name", "seat_code", "buy_amount", "sell_amount", "net_amount"}


def serve(monkeypatch, response):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return deepcopy(response)
    monkeypatch.setattr(source, "get_json", request)
    return calls


def test_real_complete_list_retains_every_event_and_source_units(monkeypatch):
    calls = serve(monkeypatch, _LIST)
    rows = FinchX(timeout=23).fund_flow.dragon_tiger_list("2026-09-30")
    assert len(rows) == 79 and len({(r["exchange"], r["code"]) for r in rows}) == 66
    assert all(set(r) == _LIST_FIELDS for r in rows)
    assert rows == sorted(rows, key=lambda r: (r["code"], r["exchange"], r["trade_id"]))
    row = next(r for r in rows if r["trade_id"] == "100420668")
    assert row == {"code": "301139", "exchange": "sz", "name": "元道退", "trade_id": "100420668", "close_price": .91, "change_percent": -72.5076, "amount": 28660561.0, "total_buy": 5016932.0, "total_net": 2996129.0, "explanation": "退市整理期", "period_label": None, "theme_id": 270, "theme_name": "储能"}
    assert next(r for r in rows if r["trade_id"] == "100421554")["period_label"] == "10日"
    assert sum(r["code"] == "000678" for r in rows) == 2
    assert any(r["name"].startswith("*ST") for r in rows)
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert urlsplit(url).path.endswith("/lists")
    assert parse_qs(urlsplit(url).query) == {"day": ["2026-09-30"], "source": ["pc"]}
    assert kwargs["timeout"] == 23.0 and kwargs["source"] == "aigupiao"


def test_real_detail_request_is_prefixed_and_has_only_business_fields(monkeypatch):
    calls = serve(monkeypatch, _DETAIL)
    result = FinchX(timeout=24).fund_flow.dragon_tiger_detail("301139", "2026-09-30", "100420668")
    assert set(result) == _DETAIL_FIELDS
    assert result["code"] == "301139" and result["exchange"] == "sz"
    assert result["total_sell"] == 2020803.0 and result["total_buy"] == 5016932.0
    assert result["buy_seats"][0] == {"seat_name": "国泰海通证券股份有限公司成都龙腾东路营业部", "seat_code": "10564259", "buy_amount": 1365120.0, "sell_amount": 237.0, "net_amount": 1364883.0}
    assert result["sell_seats"][0]["buy_amount"] == 0.0
    assert result["sell_seats"][0]["net_amount"] == -459805.0
    assert all(set(r) == _SEAT_FIELDS for f in ["buy_seats", "sell_seats"] for r in result[f])
    assert len(calls) == 1
    assert parse_qs(urlsplit(calls[0][0]).query) == {"day": ["2026-09-30"], "code": ["sz301139"], "trade_id": ["100420668"]}
    assert calls[0][1]["timeout"] == 24.0


def test_fresh_calls_no_aliases_or_additional_business_parameters(monkeypatch):
    calls = serve(monkeypatch, _LIST)
    fx = FinchX()
    assert fx.fund_flow.dragon_tiger_list("2026-09-30") == fx.fund_flow.dragon_tiger_list("2026-09-30")
    assert len(calls) == 2
    calls = serve(monkeypatch, _DETAIL)
    assert fx.fund_flow.dragon_tiger_detail("301139", "2026-09-30", "100420668") == fx.fund_flow.dragon_tiger_detail("301139", "2026-09-30", "100420668")
    assert len(calls) == 2
    assert list(inspect.signature(fx.fund_flow.dragon_tiger_list).parameters) == ["date"]
    assert list(inspect.signature(fx.fund_flow.dragon_tiger_detail).parameters) == ["code", "date", "trade_id"]
    for name in ("daily_replay", "dragon_tiger_list", "dragon_tiger_detail"):
        assert not hasattr(fx.market, name)
    for name in ("dragon_tiger_list", "dragon_tiger_detail"):
        assert not hasattr(fx.fupan, name)
    assert callable(fx.fupan.jygs_replay)


@pytest.mark.parametrize("date", [None, True, 20260930, calendar_date(2026, 9, 30), "2026-02-29", "2026-09-30 ", "２０２６-09-30", "2026-09-30T00:00:00"])
def test_invalid_date_fails_before_request(monkeypatch, date):
    calls = serve(monkeypatch, _LIST)
    with pytest.raises(ValueError):
        FinchX().fund_flow.dragon_tiger_list(date)
    with pytest.raises(ValueError):
        FinchX().fund_flow.dragon_tiger_detail("301139", date, "100420668")
    assert calls == []


@pytest.mark.parametrize("trade_id", [None, True, 100420668, "", " ", "１２３", "-1", "1.0", "1 "])
def test_invalid_trade_id_fails_before_request(monkeypatch, trade_id):
    calls = serve(monkeypatch, _DETAIL)
    with pytest.raises(ValueError):
        FinchX().fund_flow.dragon_tiger_detail("301139", "2026-09-30", trade_id)
    assert not calls


@pytest.mark.parametrize("code", [None, True, 301139, "sz301139", "３０１１３９", "30113", "920001", "900001", "200001", "510300", "399001"])
def test_unconfirmed_detail_market_fails_without_list_fetch(monkeypatch, code):
    calls = serve(monkeypatch, _DETAIL)
    with pytest.raises(ValueError):
        FinchX().fund_flow.dragon_tiger_detail(code, "2026-09-30", "100420668")
    assert not calls


@pytest.mark.parametrize("symbol", ["sh600519", "sh688001", "sz000001", "sz300001"])
def test_verified_detail_mapping(monkeypatch, symbol):
    response = deepcopy(_DETAIL)
    response["data"]["code"] = symbol
    calls = serve(monkeypatch, response)
    row = source.dragon_tiger_detail(symbol[2:], "2026-09-30", "100420668", timeout=3)
    assert row["exchange"] == symbol[:2] and row["code"] == symbol[2:]
    assert parse_qs(urlsplit(calls[0][0]).query)["code"] == [symbol]


def test_list_retains_source_b_share_etf_beijing_and_zero_values(monkeypatch):
    response = deepcopy(_LIST)
    raw = deepcopy(response["data"][0])
    raw.update(close_price=0, change_rate=0, accum_amount=0, total_buy=0, total_net=0, theme_id=0)
    response["data"] = [{**raw, "code": symbol, "trade_id": str(i)} for i, symbol in enumerate(["sh900001", "sz200001", "sh510300", "bj920001"])]
    response["count"] = 4
    serve(monkeypatch, response)
    rows = source.dragon_tiger_list("2026-09-30", timeout=15)
    assert len(rows) == 4
    assert {r["exchange"] for r in rows} == {"sh", "sz", "bj"}
    assert all(r["close_price"] == 0 and r["theme_id"] == 0 for r in rows)


def test_optional_leaves_missing_unknown_fields_ignored(monkeypatch):
    response = {"code": 1, "count": 1, "data": [{"code": "sz301139", "name": "元道退", "trade_id": "100420668", "explanation": "退市整理期", "new_field": {"unknown": True}}]}
    serve(monkeypatch, response)
    row = source.dragon_tiger_list("2026-09-30", timeout=15)[0]
    assert set(row) == _LIST_FIELDS
    assert all(row[k] is None for k in _LIST_FIELDS - {"code", "exchange", "name", "trade_id", "explanation"})
    response = {"code": 1, "data": {"code": "sz301139", "name": "元道退", "explanation": "退市整理期", "buy_fives": [{"name": "营业部"}], "sell_fives": [], "unknown": False}}
    serve(monkeypatch, response)
    row = source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=15)
    assert set(row) == _DETAIL_FIELDS
    assert row["buy_seats"] == [{"seat_name": "营业部", "seat_code": None, "buy_amount": None, "sell_amount": None, "net_amount": None}]


def test_all_source_seats_and_same_broker_in_both_sides_survive(monkeypatch):
    response = deepcopy(_DETAIL)
    response["data"]["sell_fives"].append(deepcopy(response["data"]["buy_fives"][0]))
    response["data"]["buy_fives"].append(deepcopy(response["data"]["sell_fives"][0]))
    serve(monkeypatch, response)
    row = source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=15)
    assert len(row["buy_seats"]) == len(row["sell_seats"]) == 6
    assert row["buy_seats"][0] == row["sell_seats"][-1]


def test_no_list_day_is_empty_only_with_zero_count(monkeypatch):
    serve(monkeypatch, {"code": 1, "count": 0, "data": []})
    assert FinchX().fund_flow.dragon_tiger_list("2026-10-09") == []


@pytest.mark.parametrize("value", [True, False, -1, 66.0, 66.5, None, "", "NaN"])
def test_invalid_list_count_fails(monkeypatch, value):
    response = deepcopy(_LIST)
    response["count"] = value
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_list("2026-09-30", timeout=15)


@pytest.mark.parametrize("defect", ["duplicate", "count_events", "missing_security", "extra_security", "missing_data", "data_object", "bad_row", "missing_count"])
def test_incomplete_or_damaged_list_never_returns_partial(monkeypatch, defect):
    response = deepcopy(_LIST)
    if defect == "duplicate": response["data"].append(deepcopy(response["data"][0]))
    elif defect == "count_events": response["count"] = len(response["data"])
    elif defect == "missing_security": response["data"] = [r for r in response["data"] if r["code"] != "sz301139"]
    elif defect == "extra_security": response["data"].append({**response["data"][0], "code": "bj920001"})
    elif defect == "missing_data": del response["data"]
    elif defect == "data_object": response["data"] = {}
    elif defect == "bad_row": response["data"][0] = []
    else: del response["count"]
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_list("2026-09-30", timeout=15)


@pytest.mark.parametrize("field,value", [("code", "301139"), ("code", "hk301139"), ("code", "sz３０１１３９"), ("code", None), ("trade_id", 1), ("trade_id", ""), ("trade_id", "１２３"), ("name", None), ("explanation", []), ("theme_id", True), ("theme_id", 1.5), ("theme_name", False), ("three_day_flag", True)])
def test_invalid_known_list_identity_or_text(monkeypatch, field, value):
    response = deepcopy(_LIST)
    response["data"][0][field] = value
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_list("2026-09-30", timeout=15)


@pytest.mark.parametrize("field", ["close_price", "change_rate", "accum_amount", "total_buy", "total_net"])
@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), "NaN", {}, []])
def test_bad_summary_numbers_fail_both_endpoints(monkeypatch, field, value):
    response = deepcopy(_LIST)
    response["data"][0][field] = value
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_list("2026-09-30", timeout=15)
    response = deepcopy(_DETAIL)
    response["data"][field] = value
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=15)


@pytest.mark.parametrize("field", ["close_price", "accum_amount", "total_buy", "total_sell"])
def test_negative_detail_price_or_gross_amount_fails(monkeypatch, field):
    response = deepcopy(_DETAIL)
    response["data"][field] = -1
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=15)


@pytest.mark.parametrize("field,value", [("buy", -1), ("sell", -1), ("buy", True), ("sell", float("inf")), ("net", float("nan")), ("name", None), ("code", True)])
def test_invalid_seat_fields_fail(monkeypatch, field, value):
    response = deepcopy(_DETAIL)
    response["data"]["sell_fives"][0][field] = value
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=15)


@pytest.mark.parametrize("defect", ["empty", "wrong_identity", "bare_identity", "missing_buy", "missing_sell", "bad_seat", "outer", "missing_data"])
def test_no_corresponding_or_damaged_detail_fails(monkeypatch, defect):
    response = deepcopy(_DETAIL)
    if defect == "empty": response["data"] = []
    elif defect == "wrong_identity": response["data"]["code"] = "sh301139"
    elif defect == "bare_identity": response["data"]["code"] = "301139"
    elif defect == "missing_buy": del response["data"]["buy_fives"]
    elif defect == "missing_sell": response["data"]["sell_fives"] = None
    elif defect == "bad_seat": response["data"]["buy_fives"][0] = []
    elif defect == "outer": response = []
    else: del response["data"]
    serve(monkeypatch, response)
    with pytest.raises(SourceError):
        source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=15)


@pytest.mark.parametrize("status", [None, True, False, 0, -1, 1.0, "0", {}, []])
def test_bad_status_never_converts_to_success(monkeypatch, status):
    for fixture, call in [(_LIST, lambda: source.dragon_tiger_list("2026-09-30", timeout=15)), (_DETAIL, lambda: source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=15))]:
        response = deepcopy(fixture)
        response["code"] = status
        serve(monkeypatch, response)
        with pytest.raises(SourceError): call()


@pytest.mark.parametrize("timeout", [True, None, 0, -1, float("inf"), "15"])
def test_source_timeout_validates_without_request(monkeypatch, timeout):
    calls = serve(monkeypatch, _LIST)
    with pytest.raises(ValueError): source.dragon_tiger_list("2026-09-30", timeout=timeout)
    with pytest.raises(ValueError): source.dragon_tiger_detail("301139", "2026-09-30", "100420668", timeout=timeout)
    assert not calls


def test_transport_source_error_propagates_once(monkeypatch):
    calls = []
    error = SourceError("aigupiao", "网络请求失败")
    def request(*args, **kwargs):
        calls.append(args)
        raise error
    monkeypatch.setattr(source, "get_json", request)
    with pytest.raises(SourceError) as caught:
        FinchX().fund_flow.dragon_tiger_detail("301139", "2026-09-30", "100420668")
    assert caught.value is error and len(calls) == 1


@pytest.mark.parametrize("value", ['2026-09-30', '20260930', '2026/09/30', '2026-09-30 15:30:00', '20260930 15:30:00', '2026/09/30 15:30:00'])
def test_all_date_string_formats_query_same_event_date(monkeypatch, value):
    calls = serve(monkeypatch, _LIST)
    FinchX().fund_flow.dragon_tiger_list(value)
    assert parse_qs(urlsplit(calls[0][0]).query)["day"] == ["2026-09-30"]
    calls = serve(monkeypatch, _DETAIL)
    FinchX().fund_flow.dragon_tiger_detail("301139", value, "100420668")
    assert parse_qs(urlsplit(calls[0][0]).query)["day"] == ["2026-09-30"]
