"""涨跌停池的业务转换和完整取数；真实行片段保存在本地 fixture。"""

from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import FinchX, SourceError
from finchx.sources.eastmoney import pools

_ROWS = json.loads((Path(__file__).parent / "fixtures" / "limit_pool_rows.json").read_text(encoding="utf-8"))
_COMMON = {"date", "code", "exchange", "name", "price", "change_percent", "amount",
           "float_market_cap", "market_cap", "turnover_rate", "industry"}
_EXTRA = {
    "limit_up_pool": {"consecutive_limit_up_days", "first_limit_up_time", "last_limit_up_time",
                      "limit_up_queue_amount", "limit_up_break_count", "limit_up_stats_days", "limit_up_stats_count"},
    "limit_down_pool": {"pe", "limit_down_queue_amount", "last_limit_down_time", "board_traded_amount",
                        "consecutive_limit_down_days", "limit_down_open_count"},
    "broken_limit_pool": {"limit_up_price", "amplitude", "change_speed_percent", "first_limit_up_time",
                          "limit_up_break_count", "limit_up_stats_days", "limit_up_stats_count"},
    "yesterday_limit_up_pool": {"limit_up_price", "amplitude", "change_speed_percent", "yesterday_first_limit_up_time",
                               "yesterday_consecutive_limit_up_days", "limit_up_stats_days", "limit_up_stats_count"},
    "strong_pool": {"limit_up_price", "is_sixty_day_high", "selection_reason", "volume_ratio",
                    "change_speed_percent", "limit_up_stats_days", "limit_up_stats_count"},
}


def envelope(rows, *, total=None, qdate=20261008):
    return {"rc": 0, "data": {"qdate": qdate, "tc": len(rows) if total is None else total, "pool": rows}}


def serve(monkeypatch, responses, *, breadth=None):
    """隔离网络，保留 URL、超时和每次实际请求以验证分页。"""
    remaining = iter(responses)
    requests = []

    def fake(url, **kwargs):
        parsed = urlparse(url)
        requests.append((parsed.path.lstrip("/"), parse_qs(parsed.query), kwargs))
        payload = breadth if parsed.path.endswith("getTopicZDFenBu") else next(remaining)
        if payload is None:
            payload = {"rc": 0, "data": {"qdate": 20261008}}
        return payload if isinstance(payload, str) else "finchxEastmoney(" + json.dumps(payload) + ");"

    monkeypatch.setattr(pools, "get_text", fake)
    return requests


def fetch(monkeypatch, name, raw):
    serve(monkeypatch, [envelope([raw])])
    return getattr(FinchX().market, name)()[0]


@pytest.mark.parametrize("name", list(_EXTRA))
def test_real_source_rows_have_only_business_fields_and_source_units(monkeypatch, name):
    raw = deepcopy(_ROWS[name][0])
    raw["unknown_new_field"] = {"anything": True}
    row = fetch(monkeypatch, name, raw)
    assert set(row) == _COMMON | _EXTRA[name]
    assert row["date"] == "2026-10-08"
    assert row["code"] == raw["c"] and row["exchange"] == "sz"
    assert row["name"] == raw["n"] and row["industry"] == raw["hybk"]
    assert row["price"] == raw["p"] / 1000
    assert row["change_percent"] == raw["zdp"]
    assert row["amount"] == float(raw["amount"])
    assert row["float_market_cap"] == float(raw["ltsz"])
    assert row["market_cap"] == float(raw["tshare"])
    assert row["turnover_rate"] == raw["hs"]
    assert type(row["price"]) is float
    if name == "limit_down_pool":
        assert row["pe"] == raw["pe"] and "pe_ttm" not in row
        assert row["board_traded_amount"] == raw["fba"]
        assert row["last_limit_down_time"] == "14:24:00"
    elif name == "strong_pool":
        assert row["is_sixty_day_high"] is True
        assert row["selection_reason"] == "60日新高"
        assert row["price"] < row["limit_up_price"] and "is_limit_up" not in row
    elif name == "limit_up_pool":
        assert row["first_limit_up_time"] == "10:43:00"
        assert row["limit_up_break_count"] == 0
        assert row["limit_up_queue_amount"] == raw["fund"]
    elif name == "broken_limit_pool":
        assert row["first_limit_up_time"] == "09:31:03"
    else:
        assert row["yesterday_first_limit_up_time"] == "13:11:24"
        assert row["date"] == "2026-10-08"  # 观察日不会冒充昨日事件日期。


@pytest.mark.parametrize("name", ["limit_up_pool", "strong_pool"])
def test_real_beijing_m_zero_is_preserved(monkeypatch, name):
    raw = deepcopy(_ROWS[name][1])
    assert raw["c"] == "920627" and raw["m"] == 0
    row = fetch(monkeypatch, name, raw)
    assert row["code"] == "920627" and row["exchange"] == "bj"


@pytest.mark.parametrize("code,market,exchange", [
    ("600519", 1, "sh"), ("688001", "1", "sh"), ("000001", 0, "sz"), ("300001", "0", "sz"),
    ("430001", 0, "bj"), ("830001", 0, "bj"), ("870001", 0, "bj"), ("880001", 0, "bj"), ("920627", 0, "bj"),
])
def test_valid_market_identity_does_not_require_optional_fields(monkeypatch, code, market, exchange):
    row = fetch(monkeypatch, "limit_up_pool", {"c": code, "m": market})
    assert row["exchange"] == exchange and row["code"] == code
    assert all(value is None for key, value in row.items() if key not in {"date", "code", "exchange"})


@pytest.mark.parametrize("name", list(_EXTRA))
def test_zero_values_are_preserved_and_zero_time_is_missing(monkeypatch, name):
    raw = {"c": "000001", "m": 0, "n": "ST示例", "hybk": "", "p": "0", "zdp": 0,
           "amount": 0, "ltsz": "0", "tshare": 0, "hs": 0, "lbc": 0, "fund": 0, "zbc": 0,
           "fbt": 0, "lbt": "0", "pe": -1, "fba": 0, "days": 0, "oc": 0, "ztp": 0,
           "zf": 0, "zs": -0.25, "yfbt": 0, "ylbc": 0, "nh": 0, "cc": 2, "lb": 0,
           "zttj": {"days": 0, "ct": "0"}}
    row = fetch(monkeypatch, name, raw)
    for key in ["price", "change_percent", "amount", "float_market_cap", "market_cap", "turnover_rate"]:
        assert row[key] == 0 and type(row[key]) is float
    assert row["name"] == "ST示例" and row["industry"] is None
    for key in set(row) & {"first_limit_up_time", "last_limit_up_time", "last_limit_down_time", "yesterday_first_limit_up_time"}:
        assert row[key] is None
    for key in set(row) & {"limit_up_stats_days", "limit_up_stats_count", "limit_up_break_count",
                          "consecutive_limit_up_days", "consecutive_limit_down_days", "limit_down_open_count"}:
        assert row[key] == 0 and type(row[key]) is int
    if name == "strong_pool":
        assert row["is_sixty_day_high"] is False
        assert row["selection_reason"] == "近期多次涨停"
    if name == "limit_down_pool":
        assert row["pe"] == -1
    if "change_speed_percent" in row:
        assert row["change_speed_percent"] == -0.25


@pytest.mark.parametrize("missing", [None, "", "--", "-"])
def test_missing_optional_numbers_remain_none(monkeypatch, missing):
    raw = {"c": "000001", "m": 0, "p": missing, "amount": missing, "fbt": missing,
           "zttj": missing, "zbc": missing, "n": missing}
    row = fetch(monkeypatch, "limit_up_pool", raw)
    for key in ["price", "amount", "first_limit_up_time", "limit_up_stats_days", "limit_up_stats_count", "limit_up_break_count", "name"]:
        assert row[key] is None


@pytest.mark.parametrize("code,market", [
    ("600519", 0), ("000001", 1), ("920627", 1), ("399001", 0), ("123456", 0),
    ("sh600519", 1), ("０００００１", 0), (1, 0), ("00001", 0), ("000001", True), ("000001", 0.0),
])
def test_invalid_identity_fails_instead_of_dropping_row(monkeypatch, code, market):
    with pytest.raises(SourceError):
        fetch(monkeypatch, "limit_up_pool", {"c": code, "m": market})


@pytest.mark.parametrize("field,value", [
    ("p", True), ("p", "NaN"), ("amount", float("inf")), ("ltsz", {}), ("tshare", -1), ("hs", -0.1),
    ("p", -1), ("amount", -1), ("fund", -1), ("zdp", "abc"), ("n", 1), ("hybk", []),
    ("lbc", 1.0), ("lbc", True), ("zbc", "1.5"), ("zbc", -1),
])
def test_bad_known_business_fields_fail(monkeypatch, field, value):
    with pytest.raises(SourceError, match=field):
        fetch(monkeypatch, "limit_up_pool", {"c": "000001", "m": 0, field: value})


@pytest.mark.parametrize("value,expected", [(93000, "09:30:00"), ("093103", "09:31:03"), (235959, "23:59:59"), (1, "00:00:01")])
def test_time_uses_valid_source_hhmmss(monkeypatch, value, expected):
    assert fetch(monkeypatch, "limit_up_pool", {"c": "000001", "m": 0, "fbt": value})["first_limit_up_time"] == expected


@pytest.mark.parametrize("value", [True, 93000.0, "09:30:00", -1, 240000, 126000, 125960])
def test_invalid_time_fails(monkeypatch, value):
    with pytest.raises(SourceError, match="fbt"):
        fetch(monkeypatch, "limit_up_pool", {"c": "000001", "m": 0, "fbt": value})


@pytest.mark.parametrize("stats,days,count", [
    ({}, None, None), ({"days": 1}, 1, None), ({"ct": "0"}, None, 0),
    ({"days": None, "ct": 0}, None, 0), ({"days": 0, "ct": None}, 0, None),
])
def test_missing_stats_leaf_does_not_discard_valid_stock(monkeypatch, stats, days, count):
    row = fetch(monkeypatch, "limit_up_pool", {"c": "000001", "m": 0, "zttj": stats})
    assert row["limit_up_stats_days"] == days and row["limit_up_stats_count"] == count


@pytest.mark.parametrize("stats", [[], 1, True, {"days": 1, "ct": True}, {"days": "1.0", "ct": 1}, {"days": 1, "ct": -1}])
def test_invalid_stats_object_fails(monkeypatch, stats):
    with pytest.raises(SourceError, match="zttj"):
        fetch(monkeypatch, "limit_up_pool", {"c": "000001", "m": 0, "zttj": stats})


@pytest.mark.parametrize("field,value", [("nh", 2), ("nh", True), ("nh", 1.0), ("cc", 0), ("cc", 4), ("cc", True), ("lb", -1)])
def test_strong_flags_and_selection_reason_are_strict(monkeypatch, field, value):
    with pytest.raises(SourceError, match=field):
        fetch(monkeypatch, "strong_pool", {"c": "000001", "m": 0, field: value})


def test_strong_third_reason_and_missing_flag(monkeypatch):
    row = fetch(monkeypatch, "strong_pool", {"c": "000001", "m": 0, "cc": "3"})
    assert row["selection_reason"] == "60日新高且近期多次涨停"
    assert row["is_sixty_day_high"] is None


def test_cross_page_overlap_repaired_and_later_real_row_updates(monkeypatch):
    monkeypatch.setattr(pools, "_PAGE_SIZE", 2)
    a, b, c, d = [{"c": f"00000{i}", "m": 0, "amount": i} for i in range(1, 5)]
    updated_b = {**b, "amount": 22}
    requests = serve(monkeypatch, [envelope([a, b], total=4), envelope([updated_b, c], total=4), envelope([d, c], total=4)])
    result = FinchX(timeout=7).market.limit_up_pool()
    assert [row["code"] for row in result] == ["000001", "000002", "000003", "000004"]
    assert result[1]["amount"] == 22
    assert [query["sort"][0] for _, query, _ in requests[1:]] == ["c:asc", "c:asc", "c:desc"]
    assert [query["Pageindex"][0] for _, query, _ in requests[1:]] == ["0", "1", "0"]
    assert all(kwargs["timeout"] == 7 for _, _, kwargs in requests)


def test_third_round_can_finish_but_never_returns_partial(monkeypatch):
    monkeypatch.setattr(pools, "_PAGE_SIZE", 2)
    a, b, c, d = [{"c": f"00000{i}", "m": 0} for i in range(1, 5)]
    responses = [envelope(page, total=4) for page in [[a, b], [b, c], [b, c], [c, a], [d, a]]]
    requests = serve(monkeypatch, responses)
    assert len(FinchX().market.strong_pool()) == 4
    assert [query["sort"][0] for _, query, _ in requests[1:]] == ["c:asc", "c:asc", "c:desc", "c:desc", "c:asc"]
    incomplete = [envelope(page, total=4) for page in [[a, b], [b, c]] * 3]
    requests = serve(monkeypatch, incomplete)
    with pytest.raises(SourceError, match="三轮.*tc=4.*3"):
        FinchX().market.strong_pool()
    assert len(requests) == 7  # 一次日期请求及有界的三轮分页。


def test_complete_multiple_pages_request_latest_date_and_return_sorted(monkeypatch):
    monkeypatch.setattr(pools, "_PAGE_SIZE", 2)
    raw = [{"c": "920627", "m": 0}, {"c": "600519", "m": 1}, {"c": "000001", "m": 0}]
    requests = serve(monkeypatch, [envelope(raw[:2], total="3"), envelope(raw[2:], total=3)])
    rows = FinchX().market.limit_down_pool()
    assert [(row["code"], row["exchange"]) for row in rows] == [("000001", "sz"), ("600519", "sh"), ("920627", "bj")]
    for endpoint, query, kwargs in requests[1:]:
        assert endpoint == "getTopicDTPool" and query["date"] == ["20261008"]
        assert query["pagesize"] == ["2"] and query["cb"] == ["finchxEastmoney"]
        assert query["dpt"] == ["wz.ztzt"] and kwargs["source"] == "eastmoney"


@pytest.mark.parametrize("name", list(_EXTRA))
def test_zero_total_returns_empty_and_no_caching(monkeypatch, name):
    requests = serve(monkeypatch, [envelope([]), envelope([])])
    api = FinchX().market
    assert getattr(api, name)() == [] and getattr(api, name)() == []
    assert len(requests) == 4 and requests[0][0] == requests[2][0] == "getTopicZDFenBu"


@pytest.mark.parametrize("change,match", [
    ({"tc": 2}, "tc.*漂移"), ({"qdate": 20261009}, "qdate"), ({"pool": []}, "页长度"),
    ({"pool": [{"c": "000003", "m": 0}, {"c": "000004", "m": 0}]}, "页长度"),
])
def test_page_count_date_and_short_or_excess_page_errors(monkeypatch, change, match):
    monkeypatch.setattr(pools, "_PAGE_SIZE", 2)
    second = envelope([{"c": "000003", "m": 0}], total=3)
    second["data"].update(change)
    serve(monkeypatch, [envelope([{"c": "000001", "m": 0}, {"c": "000002", "m": 0}], total=3), second])
    with pytest.raises(SourceError, match=match):
        FinchX().market.limit_up_pool()


def test_same_page_duplicate_is_an_error(monkeypatch):
    serve(monkeypatch, [envelope([{"c": "000001", "m": 0}] * 2)])
    with pytest.raises(SourceError, match="同页重复"):
        FinchX().market.limit_up_pool()


def test_unique_count_above_stable_source_total_fails(monkeypatch):
    monkeypatch.setattr(pools, "_PAGE_SIZE", 2)
    a, b, c, d, e = [{"c": f"00000{i}", "m": 0} for i in range(1, 6)]
    serve(monkeypatch, [envelope([a, b], total=4), envelope([b, c], total=4), envelope([d, e], total=4)])
    with pytest.raises(SourceError, match="超过.*tc=4"):
        FinchX().market.limit_up_pool()


@pytest.mark.parametrize("payload,match", [
    ([], "外层"), ({"data": {}}, "rc"), ({"rc": True, "data": {}}, "rc"),
    ({"rc": 1, "data": {}}, "请求失败"), ({"rc": "oops", "data": {}}, "rc"),
    ({"rc": 0, "data": []}, "data"), ({"rc": 0, "data": {}}, "tc"),
    (envelope([], total=True), "tc"), (envelope([], total=0.0), "tc"), (envelope([], total=-1), "tc"),
    (envelope([], qdate="20260230"), "qdate"), (envelope([], qdate=True), "qdate"),
    ({"rc": 0, "data": {"tc": 0, "qdate": 20261008, "pool": None}}, "pool"),
    (envelope([None]), "股票行"), ("otherCallback({});", "JSONP"), ("finchxEastmoney({broken});", "JSON"),
])
def test_bad_envelope_fails_clearly(monkeypatch, payload, match):
    serve(monkeypatch, [payload])
    with pytest.raises(SourceError, match=match):
        FinchX().market.limit_up_pool()


def test_latest_date_must_come_from_valid_breadth_response(monkeypatch):
    requests = serve(monkeypatch, [], breadth={"rc": 0, "data": {"qdate": "20260230"}})
    with pytest.raises(SourceError, match="qdate"):
        FinchX().market.limit_up_pool()
    assert len(requests) == 1


@pytest.mark.parametrize("name", list(_EXTRA))
def test_market_methods_forward_client_timeout(monkeypatch, name):
    calls = []
    sentinel = [{"code": "000001"}]
    monkeypatch.setattr(pools, name, lambda **kwargs: calls.append(kwargs) or sentinel)
    assert getattr(FinchX(timeout=8).market, name)() is sentinel
    assert calls == [{"timeout": 8.0}]


def test_consecutive_market_method_forwards_timeout(monkeypatch):
    from finchx.sources.aigupiao import consecutive
    calls = []
    sentinel = [{"code": "000001"}]
    monkeypatch.setattr(consecutive, "consecutive_limit_up", lambda **kwargs: calls.append(kwargs) or sentinel)
    assert FinchX(timeout=6).market.consecutive_limit_up() is sentinel
    assert calls == [{"timeout": 6.0}]
