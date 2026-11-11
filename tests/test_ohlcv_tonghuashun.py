"""同花顺 HXKline 日线来源的身份、请求与返回字段测试。"""

from datetime import datetime, timedelta, timezone
import inspect
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import FinchX, SourceError
from finchx._common import proxy
from finchx.sources.tonghuashun import klines


def dictionary(code, *, label="沪A", market="17", hq_code=None, extras=()):
    # Deliberately reorder source columns: parsing must follow `head`, not fixed indexes.
    head = [
        {"id": "market_label"}, {"id": "stock_name"}, {"id": "hq_market"},
        {"id": "hq_code"}, {"id": "function_bit"},
    ]
    rows = [[label, "标的", market, hq_code or code, "00000"]]
    rows.extend([[extra_label, "关联标的", extra_market, extra_code, "10000"] for extra_code, extra_market, extra_label in extras])
    return {"status_code": 0, "status_msg": "success", "data": {"head": head, "body": rows}}


def quote_document(code, market, rows, *, fields=("1", "7", "8", "9", "11", "13", "19"), status=0):
    return {
        "status_code": status,
        "status_msg": "ok",
        "data": {
            "quote_data": [{"market": market, "code": code, "data_fields": list(fields), "value": rows}],
            "fail_params": None,
        },
    }


def ms(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone(timedelta(hours=8))).timestamp() * 1000)


def install(monkeypatch, *, info, documents):
    gets, posts = [], []

    def get_json(url, **kwargs):
        gets.append((url, kwargs))
        return info

    def post_json(url, **kwargs):
        posts.append((url, kwargs))
        return documents.pop(0)

    monkeypatch.setattr(klines, "get_json", get_json)
    monkeypatch.setattr(klines, "post_json", post_json)
    return gets, posts


def test_public_source_parameter_defaults_to_tencent_and_is_keyword_only():
    signature = inspect.signature(FinchX().market.ohlcv)
    assert signature.parameters["source"].default == "tencent"
    assert signature.parameters["source"].kind is inspect.Parameter.KEYWORD_ONLY


def test_st_stock_and_long_beijing_market_are_selected_from_dictionary(monkeypatch):
    gets, posts = install(
        monkeypatch,
        info=dictionary("600745", label="ST", market="22"),
        documents=[quote_document("600745", "22", [[ms("2026-11-10"), 11.75, 12.15, 11.64, 12.04, 39077000, 464372050]])],
    )
    rows = FinchX().market.ohlcv("600745", "2026-11-10", "2026-11-10", source="tonghuashun")
    assert rows == [{"date": "2026-11-10", "open": 11.75, "high": 12.15, "low": 11.64, "close": 12.04, "volume": 39077000, "amount": 464372050.0}]
    assert parse_qs(urlparse(gets[0][0]).query)["query"] == ["600745"]
    assert posts[0][1]["data"]["code_list"] == [{"codes": ["600745"], "market": "22"}]


def test_beijing_stock_uses_dictionary_market_without_prefix_filter(monkeypatch):
    _, posts = install(
        monkeypatch,
        info=dictionary("920002", label="京A", market="151"),
        documents=[quote_document("920002", "151", [[ms("2026-11-10"), 10, 11, 9, 10, 100, 1000]])],
    )
    assert FinchX().market.ohlcv("920002", "2026-11-10", "2026-11-10", source="tonghuashun")[0]["close"] == 10
    assert posts[0][1]["data"]["code_list"] == [{"codes": ["920002"], "market": "151"}]


def test_index_alias_and_board_kind_select_source_identity(monkeypatch):
    gets, posts = install(
        monkeypatch,
        info=dictionary("000001", label="深A", market="33", extras=(("1A0001", "16", "沪指"),)),
        documents=[quote_document("1A0001", "16", [[ms("2026-11-10"), 3655.66, 3672.18, 3653.98, 3660.04, 13425068000, 211103590000]])],
    )
    rows = FinchX().market.ohlcv("000001", "2026-11-10", "2026-11-10", kind="index", source="tonghuashun")
    assert rows[0]["close"] == 3660.04
    assert posts[0][1]["data"]["code_list"] == [{"codes": ["1A0001"], "market": "16"}]

    for board_code in ("883902", "885573"):
        gets, posts = install(
            monkeypatch,
            info=dictionary(board_code, label="板块", market="48"),
            documents=[quote_document(board_code, "48", [[ms("2026-11-10"), 355.858, 371.564, 355.858, 362.84, 915624690, 123840608000]])],
        )
        rows = FinchX().market.ohlcv(board_code, "2026-11-10", "2026-11-10", kind="index", source="tonghuashun")
        assert rows[0]["amount"] == 123840608000.0
        assert posts[0][1]["data"]["code_list"] == [{"codes": [board_code], "market": "48"}]


def test_dynamic_data_fields_dates_and_negative_adjusted_prices(monkeypatch):
    fields = ("19", "1", "13", "11", "9", "7", "8")
    raw = [1000000, ms("2026-11-09"), 200, -0.5, -2, -1, 0]
    _, posts = install(
        monkeypatch,
        info=dictionary("600519"),
        documents=[quote_document("600519", "17", [raw], fields=fields)],
    )
    rows = FinchX().market.ohlcv(
        "600519", "2026-11-09", "2026-11-09", "qfq", source="tonghuashun",
    )
    assert rows == [{"date": "2026-11-09", "open": -1.0, "high": 0.0, "low": -2.0, "close": -0.5, "volume": 200, "amount": 1000000.0}]
    request = posts[0][1]["data"]
    assert request["data_fields"] == ["1", "7", "8", "9", "11", "13", "19"]
    assert request["adjust_type"] == "forward"
    assert request["begin_time"] == ms("2026-11-09")
    assert request["end_time"] == ms("2026-11-09")
    assert request["time_period"] == "day_1" and request["trade_date"] == -1


def test_missing_optional_volume_and_amount_fields_remain_none(monkeypatch):
    fields = ("1", "7", "8", "9", "11")
    raw = [ms("2026-11-10"), 1, 2, 0, 1]
    _, posts = install(
        monkeypatch,
        info=dictionary("600519"),
        documents=[quote_document("600519", "17", [raw], fields=fields)],
    )
    row = FinchX().market.ohlcv("600519", "2026-11-10", "2026-11-10", source="tonghuashun")[0]
    assert row["volume"] is None and row["amount"] is None
    assert posts[0][1]["data"]["data_fields"] == ["1", "7", "8", "9", "11", "13", "19"]


def test_hfq_maps_to_backward_without_changing_the_seven_public_fields(monkeypatch):
    _, posts = install(
        monkeypatch,
        info=dictionary("600519"),
        documents=[quote_document("600519", "17", [[ms("2026-11-10"), 1438.23, 1444.5, 1431.26, 1439, 2303784, 3316078800]])],
    )
    rows = FinchX().market.ohlcv("600519", "2026-11-10", "2026-11-10", "hfq", source="tonghuashun")
    assert set(rows[0]) == {"date", "open", "high", "low", "close", "volume", "amount"}
    assert posts[0][1]["data"]["adjust_type"] == "backward"


@pytest.mark.parametrize("fail_params", [
    None, {}, [], {"begin_time": 1, "code_list": [{"market": "17", "codes": ["600519"]}]},
])
def test_ambiguous_empty_window_uses_one_same_identity_lookback_probe(monkeypatch, fail_params):
    empty = {"status_code": 0, "status_msg": "ok", "data": {"quote_data": [], "fail_params": fail_params}}
    probe = quote_document("600519", "17", [[ms("2026-11-10"), 1438.23, 1444.5, 1431.26, 1439, 2303784, 3316078800]])
    _, posts = install(monkeypatch, info=dictionary("600519"), documents=[empty, probe])
    assert FinchX().market.ohlcv("600519", "2026-11-01", "2026-11-03", source="tonghuashun") == []
    first, second = (entry[1]["data"] for entry in posts)
    assert first["code_list"] == second["code_list"]
    assert first["adjust_type"] == second["adjust_type"] == "actual"
    assert second["begin_time"] == -1 and second["end_time"] == ms("2026-11-03")


def test_ambiguous_empty_window_fails_if_probe_is_unusable_or_inside_range(monkeypatch):
    empty = {"status_code": 0, "status_msg": "ok", "data": {"quote_data": [], "fail_params": {}}}
    cases = [
        {"status_code": 0, "status_msg": "ok", "data": {"quote_data": [], "fail_params": {}}},
        quote_document("wrong", "17", [[ms("2026-11-10"), 1, 2, 0, 1, 1, 1]]),
        quote_document("600519", "17", [[ms("2026-11-02"), 1, 2, 0, 1, 1, 1]]),
    ]
    for probe in cases:
        install(monkeypatch, info=dictionary("600519"), documents=[empty, probe])
        with pytest.raises(SourceError):
            FinchX().market.ohlcv("600519", "2026-11-01", "2026-11-03", source="tonghuashun")


def test_empty_response_with_mismatched_echoed_identity_fails_without_probe(monkeypatch):
    empty = {
        "status_code": 0,
        "data": {
            "quote_data": [],
            "fail_params": {"code_list": [{"market": "22", "codes": ["600519"]}]},
        },
    }
    _, posts = install(monkeypatch, info=dictionary("600519"), documents=[empty])
    with pytest.raises(SourceError):
        FinchX().market.ohlcv("600519", "2026-11-01", "2026-11-03", source="tonghuashun")
    assert len(posts) == 1


def test_empty_response_with_unidentified_nonempty_fail_params_fails(monkeypatch):
    empty = {"status_code": 0, "data": {"quote_data": [], "fail_params": {"begin_time": 1}}}
    _, posts = install(monkeypatch, info=dictionary("600519"), documents=[empty])
    with pytest.raises(SourceError):
        FinchX().market.ohlcv("600519", "2026-11-01", "2026-11-03", source="tonghuashun")
    assert len(posts) == 1


@pytest.mark.parametrize("document", [
    quote_document("wrong", "17", [[ms("2026-11-10"), 1, 2, 0, 1, 1, 1]]),
    quote_document("600519", "99", [[ms("2026-11-10"), 1, 2, 0, 1, 1, 1]]),
    quote_document("600519", "17", [[ms("2026-11-10"), 1, 2, 0, 1, 1, 1]], status=1),
])
def test_status_and_response_identity_are_checked(monkeypatch, document):
    install(monkeypatch, info=dictionary("600519"), documents=[document])
    with pytest.raises(SourceError):
        FinchX().market.ohlcv("600519", "2026-11-10", "2026-11-10", source="tonghuashun")


def test_same_code_different_kind_is_not_misidentified(monkeypatch):
    gets, posts = install(
        monkeypatch,
        info=dictionary("000001", label="深A", market="33", extras=(("1A0001", "16", "沪指"),)),
        documents=[quote_document("000001", "33", [[ms("2026-11-10"), 1, 2, 0, 1, 1, 1]])],
    )
    with pytest.raises(SourceError):
        FinchX().market.ohlcv("000001", "2026-11-10", "2026-11-10", kind="index", source="tonghuashun")
    assert len(gets) == 1
    assert posts[0][1]["data"]["code_list"] == [{"codes": ["1A0001"], "market": "16"}]


def test_http_calls_inherit_client_use_proxy_setting(monkeypatch):
    observed = []

    def get_json(url, **kwargs):
        observed.append(proxy._use_proxy.get())
        return dictionary("600519")

    def post_json(url, **kwargs):
        observed.append(proxy._use_proxy.get())
        return quote_document("600519", "17", [[ms("2026-11-10"), 1, 2, 0, 1, 1, 1]])

    monkeypatch.setattr(klines, "get_json", get_json)
    monkeypatch.setattr(klines, "post_json", post_json)
    FinchX(use_proxy=False).market.ohlcv("600519", "2026-11-10", "2026-11-10", source="tonghuashun")
    assert observed == [False, False]


@pytest.mark.parametrize("kwargs", [
    {"code": "92001"}, {"kind": "other"}, {"source": "auto"},
    {"adjustment": "none"}, {"adjustment": True}, {"adjustment": []},
    {"kind": "index", "adjustment": "qfq"}, {"start_date": "2026-11-11"},
])
def test_invalid_parameters_fail_before_http(monkeypatch, kwargs):
    gets, posts = install(monkeypatch, info=dictionary("600519"), documents=[])
    values = {"code": "600519", "start_date": "2026-11-09", "end_date": "2026-11-10", "source": "tonghuashun", **kwargs}
    with pytest.raises(ValueError):
        FinchX().market.ohlcv(**values)
    assert gets == [] and posts == []


def test_multiple_stock_identities_are_not_arbitrarily_selected(monkeypatch):
    info = dictionary("600519", extras=(("600519", "22", "ST"),))
    gets, posts = install(monkeypatch, info=info, documents=[])
    with pytest.raises(SourceError):
        FinchX().market.ohlcv("600519", "2026-11-10", "2026-11-10", source="tonghuashun")
    assert len(gets) == 1 and posts == []


def test_fund_identity_is_not_misidentified_as_stock(monkeypatch):
    info = dictionary("510300", label="沪基", market="20")
    gets, posts = install(monkeypatch, info=info, documents=[])
    with pytest.raises(SourceError):
        FinchX().market.ohlcv("510300", "2026-11-10", "2026-11-10", source="tonghuashun")
    assert len(gets) == 1 and posts == []
