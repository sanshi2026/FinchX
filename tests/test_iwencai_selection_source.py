"""当前官方 JS 协议的明确构造重放；不代表有效 Cookie 认证成功。"""

import copy
import json
from types import MappingProxyType

import pytest

from finchx import SourceError
from finchx.sources.iwencai import selection as source


def table(rows, *, columns=None, extra=None):
    return {"chart_type": "jgyXuanguTable1", "show_type": "jgyXuanguTable1", "data": {
        "columns": columns or [
            {"key": "股票代码", "label": "code", "type": "STR"},
            {"key": "股票简称", "label": "name", "type": "STR"},
            {"key": "涨跌幅[20261008]", "type": "FLOAT", "unit": "%"},
        ], "datas": rows, "meta": {"extra": {
            "query_type": "stock", "row_count": 800, "code_count": 900,
            "condition": "实际来源条件", "query": "来源解释问句",
            "token": "not-forwarded", "per_page": 50, "stock_code_list": ["not-forwarded"],
            **(extra or {}),
        }},
    }}


def row(code="000001.SZ", value=0):
    return {"股票代码": code, "股票简称": "样本证券", "涨跌幅[20261008]": value}


def stream(component, *, finished=True):
    frames = [{"type": "answer", "section": {"show_type": "result_page", "is_last": True,
              "result_page": {"components": [component]}}}]
    if finished:
        frames.append({"type": "answer", "is_last": True, "section": {"show_type": "signal"}})
    return "".join("data: " + json.dumps(frame, ensure_ascii=False) + "\n\n" for frame in frames)


def replay(monkeypatch, initial, pages=()):
    calls = []
    pages = iter(pages)
    def request(url, **kwargs):
        calls.append((url, kwargs))
        if url == source._STREAM:
            return initial
        return next(pages)
    monkeypatch.setattr(source.http, "post_text", request)
    monkeypatch.setattr(source.http, "post_json", request)
    return calls


def rendered(component):
    return {"status_code": 0, "answer": json.dumps({"components": [component]}, ensure_ascii=False)}


def select(limit=100, **kwargs):
    return source.select("动态选股条件", limit, cookies=kwargs.get("cookies", "invalid-test-cookie=1"), timeout=2)


def test_select_current_payload_full_first_page_reuse_and_source_order(monkeypatch):
    calls = replay(monkeypatch, stream(table([row("000002.SZ"), row("000001.SZ")])) )
    result = select(1)
    assert result == [{"code": "000002", "exchange": "sz", "name": "样本证券", "涨跌幅[20261008](%)": 0}]
    assert len(calls) == 1
    url, request = calls[0]
    assert url == source._STREAM and request["follow_redirects"] is False
    payload = request["data"]
    assert payload["dialog_model"] == "CUSTOMER_AGENT" and payload["default_fallback"] is False
    assert payload["agent_tools"] == [{"tool_id": "FinQuery", "tool_param": {"domain": "stock", "perpage": 50}}]
    assert payload["events"] == [{"event_type": "user_input", "event_name": "normal_agent", "content": {}}]
    assert payload["agent_id"] == "MaSzyUwyyl" and payload["version"] == "3.4.1"
    assert "session_id" not in payload and "user_id" not in payload


def test_dynamic_columns_keep_dates_units_all_business_types_and_ignore_raw_fields(monkeypatch):
    columns = [{"key": "股票代码", "label": "other||code"}, {"key": "股票简称", "label": "name"},
               {"key": "opaque[20261008]", "unit": "亿元", "timestamp": "20261008"},
               {"key": "成交额[20261009]", "unit": "元"}, {"key": "排名"},
               {"key": "新业务"}, {"key": "缺失值"}, {"key": "百分比", "unit": "%"}]
    raw = {"股票代码": "920001.BJ", "股票简称": None, "opaque[20261008]": "1.00000001",
           "成交额[20261009]": 0, "排名": 0, "新业务": {"零": 0, "缺": None, "组": [False, "原文"]},
           "百分比": "12.5", "internal_unused": "不输出"}
    component = table([raw], columns=columns, extra={"iwc_column_info": {"opaque[20261008]": {"index_meta": {"label": "成交额"}}}})
    replay(monkeypatch, stream(component))
    result = select(1)[0]
    assert result == {"code": "920001", "exchange": "bj", "name": None,
                      "成交额(亿元)[20261008]": "1.00000001", "成交额[20261009](元)": 0,
                      "排名": 0, "新业务": raw["新业务"], "缺失值": None, "百分比(%)": "12.5"}


@pytest.mark.parametrize("code_column_first", [False, True])
def test_amount_rank_moving_average_query_keeps_hq_identity_and_all_business_columns(monkeypatch, code_column_first):
    # 回调中 股票代码/code/market_code 的关系来自当前官网 JS；业务样本为构造重放。
    query = "成交额排名前200，非ST，最新价>ma5>ma10>ma20"
    columns = [{"key": "股票代码", "label": "other||code"}, {"key": "股票简称", "label": "name"},
               {"key": "code"}, {"key": "market_code"},
               {"key": "成交额排名[20261009]", "type": "INT"},
               {"key": "成交额[20261009]", "type": "FLOAT", "unit": "元"},
               {"key": "最新价", "type": "FLOAT", "unit": "元"},
               {"key": "5日均线", "type": "FLOAT", "unit": "元"},
               {"key": "10日均线", "type": "FLOAT", "unit": "元"},
               {"key": "20日均线", "type": "FLOAT", "unit": "元"}, {"key": "是否ST"}]
    if code_column_first:
        columns.insert(0, columns.pop(2))
    raw = {"股票代码": "600000.SH", "股票简称": "样本证券", "code": "600000", "market_code": 17,
           "成交额排名[20261009]": 0, "成交额[20261009]": 0, "最新价": "12.5000",
           "5日均线": "12.4000", "10日均线": "12.3000", "20日均线": "12.2000", "是否ST": False}
    calls = replay(monkeypatch, stream(table([raw], columns=columns, extra={"row_count": 1, "query": query})),
                   [rendered(table([], columns=columns, extra={"row_count": 1}))])
    result = source.select(query, limit=100, cookies="invalid-test-cookie=1", timeout=2)
    assert result == [{"code": "600000", "exchange": "sh", "name": "样本证券",
                       "成交额排名[20261009]": 0, "成交额[20261009](元)": 0, "最新价(元)": "12.5000",
                       "5日均线(元)": "12.4000", "10日均线(元)": "12.3000",
                       "20日均线(元)": "12.2000", "是否ST": False}]
    assert calls[0][1]["data"]["question"] == query
    assert [call[1]["data"]["page"] for call in calls[1:]] == [2]


def test_declared_identity_alias_columns_are_checked_and_emitted_once(monkeypatch):
    columns = [{"key": "股票代码"}, {"key": "code"}, {"key": "证券标识", "label": "other||code"},
               {"key": "股票简称"}, {"key": "证券名称", "label": "other||name"},
               {"key": "market_code"}, {"key": "市场标识", "label": "market"}, {"key": "指标"}]
    raw = {"股票代码": "920001.BJ", "code": "920001", "证券标识": "920001.BJ",
           "股票简称": "样本证券", "证券名称": "样本证券", "market_code": 151, "市场标识": "151", "指标": 0}
    replay(monkeypatch, stream(table([raw], columns=columns)))
    assert select(1) == [{"code": "920001", "exchange": "bj", "name": "样本证券", "指标": 0}]


def test_hq_code_column_can_supply_explicit_identity_with_market_marker(monkeypatch):
    columns = [{"key": "code"}, {"key": "market_code"}, {"key": "股票简称", "label": "name"}, {"key": "指标"}]
    replay(monkeypatch, stream(table([{"code": "600000", "market_code": 17, "股票简称": None, "指标": 0}], columns=columns)))
    assert select(1) == [{"code": "600000", "exchange": "sh", "name": None, "指标": 0}]


@pytest.mark.parametrize("change", [
    {"code": "600001"}, {"code": "600000.SZ"}, {"code": 600000}, {"code": "６０００００"},
    {"证券标识": "600001.SH"}, {"市场标识": 33}, {"市场标识": False},
    {"证券名称": "另一个名称"}, {"证券名称": 0},
])
def test_identity_alias_conflicts_and_bad_types_still_fail(monkeypatch, change):
    columns = [{"key": "股票代码", "label": "code"}, {"key": "code"},
               {"key": "证券标识", "label": "code"}, {"key": "股票简称", "label": "name"},
               {"key": "证券名称", "label": "name"}, {"key": "市场标识", "label": "market"}]
    raw = {"股票代码": "600000.SH", "code": "600000", "证券标识": "600000.SH",
           "股票简称": "样本证券", "证券名称": "样本证券", "市场标识": 17, **change}
    replay(monkeypatch, stream(table([raw], columns=columns)))
    with pytest.raises(SourceError):
        select(1)


@pytest.mark.parametrize("column", [{"key": "股票代码", "label": "code||name"},
                                    {"key": "code", "label": "name"}, {"key": "market_code", "label": "code"}])
def test_identity_column_role_conflicts_fail(monkeypatch, column):
    replay(monkeypatch, stream(table([row()], columns=[column])))
    with pytest.raises(SourceError, match="角色冲突"):
        select(1)


@pytest.mark.parametrize("title", ["code", "exchange", "name"])
def test_reserved_business_titles_are_not_guessed_as_identity_aliases(monkeypatch, title):
    columns = [{"key": "股票代码", "label": "code"}, {"key": "独立业务指标"}]
    extra = {"iwc_column_info": {"独立业务指标": {"index_meta": {"label": title}}}}
    replay(monkeypatch, stream(table([row()], columns=columns, extra=extra)))
    with pytest.raises(SourceError, match="动态业务列与固定身份字段冲突"):
        select(1)


def test_duplicate_business_titles_remain_source_error(monkeypatch):
    columns = [{"key": "股票代码", "label": "code"}, {"key": "指标一"}, {"key": "指标二"}]
    extra = {"iwc_column_info": {key: {"index_meta": {"label": "同一指标"}} for key in ("指标一", "指标二")}}
    replay(monkeypatch, stream(table([row()], columns=columns, extra=extra)))
    with pytest.raises(SourceError, match="业务名称冲突"):
        select(1)


def test_cross_page_overlap_later_whole_row_update_short_page_not_exhaustion(monkeypatch):
    pages = [rendered(table([row("000001.SZ", 2), row("920001.BJ", None)], extra={"row_count": 3})),
             rendered(table([], extra={"row_count": 3}))]
    calls = replay(monkeypatch, stream(table([row("000001.SZ", 1)], extra={"row_count": 3})), pages)
    result = select(10)
    assert [r["code"] for r in result] == ["000001", "920001"]
    assert result[0]["涨跌幅[20261008](%)"] == 2 and result[1]["涨跌幅[20261008](%)"] is None
    assert [c[1]["data"]["page"] for c in calls[1:]] == [2, 3]
    for url, request in calls[1:]:
        assert url == source._RENDER and request["follow_redirects"] is False
        assert request["data"]["query"] == "来源解释问句" and request["data"]["query_type"] == "stock"
        assert not {"token", "per_page", "stock_code_list"}.intersection(request["data"])
        assert request["data"]["condition"] == "实际来源条件"


def test_valid_empty_final_stock_table_returns_empty(monkeypatch):
    calls = replay(monkeypatch, stream(table([], extra={"row_count": 0})))
    assert select() == [] and len(calls) == 1


@pytest.mark.parametrize("marker,code,exchange", [(17, "900001", "sh"), (33, "200001", "sz"), (151, "920001", "bj"), ("151", "430001", "bj")])
def test_explicit_market_preserves_stock_families(monkeypatch, marker, code, exchange):
    raw = row(code)
    raw["market_code"] = marker
    replay(monkeypatch, stream(table([raw])))
    assert select(1)[0]["exchange"] == exchange


@pytest.mark.parametrize("bad", [None, True, 0, -1, 1.5, "1"])
def test_bad_limit_before_request(monkeypatch, bad):
    replay(monkeypatch, "unused")
    with pytest.raises(ValueError):
        select(bad)


@pytest.mark.parametrize("cookies", [None, "", "x=1\r\nAuthorization: leak", {"x;": "1"}, {"x": "1; leak=1"}, {"x": 1}, {"x": "a\nb"}])
def test_bad_cookie_before_request(monkeypatch, cookies):
    calls = replay(monkeypatch, "unused")
    with pytest.raises(ValueError):
        select(cookies=cookies)
    assert calls == []


def test_cookie_mapping_is_per_call_and_not_in_output(monkeypatch):
    calls = replay(monkeypatch, stream(table([row()])))
    secret = "invalid-secret-for-offline-test"
    result = select(1, cookies=MappingProxyType({"x": secret, "empty": ""}))
    assert calls[0][1]["headers"]["Cookie"] == f"x={secret}; empty="
    assert secret not in str(result)


@pytest.mark.parametrize("bad_row", [
    {"股票代码": "customer600001data", "股票简称": "坏身份"},
    {"股票代码": "６００００１.SH"}, {"股票代码": "000001"},
    {"股票代码": "000001.SZ", "market_code": 17}, {"股票代码": "000001.SZ", "market_code": []},
    {"股票代码": "000001.SZ", "code": "000002"}, {"股票代码": "000001.SZ", "股票简称": 0},
    {"股票代码": "000001.SZ", "涨跌幅[20261008]": True},
    {"股票代码": "000001.SZ", "涨跌幅[20261008]": "NaN"},
    "broken-row",
])
def test_limit_cannot_hide_bad_later_row(monkeypatch, bad_row):
    replay(monkeypatch, stream(table([row("000002.SZ"), bad_row])))
    with pytest.raises(SourceError):
        select(1)


def test_no_arbitrary_code_named_column_identity_guess(monkeypatch):
    component = table([{"公告代码": "600001.SH"}], columns=[{"key": "公告代码"}])
    replay(monkeypatch, stream(component))
    with pytest.raises(SourceError):
        select(1)


@pytest.mark.parametrize("mutate", [
    lambda t: t["data"].update(datas=None),
    lambda t: t["data"].update(columns=[]),
    lambda t: t["data"]["meta"]["extra"].update(query_type="hkstock"),
    lambda t: t["data"]["meta"]["extra"].update(row_count=True),
    lambda t: t["data"]["columns"].append(t["data"]["columns"][0]),
    lambda t: t["data"].update(datas=[row(), row()]),
])
def test_final_table_structure_damage_fails(monkeypatch, mutate):
    component = table([row()]); mutate(component)
    replay(monkeypatch, stream(component))
    with pytest.raises(SourceError):
        select(1)


@pytest.mark.parametrize("body", [
    stream(table([row()]), finished=False), "data: {bad-json}\n\n", "data: [DONE]\n\n",
    'data: {"is_last":true,"extra":{"status_code":-1935}}\n\n',
    'data: {"is_last":true,"section":{"show_type":"plain_text","content":"无法选股"}}\n\n',
])
def test_incomplete_or_error_stream_cannot_be_success(monkeypatch, body):
    replay(monkeypatch, body)
    with pytest.raises(SourceError):
        select(1)


def test_unrelated_display_components_do_not_replace_stock_table(monkeypatch):
    body = stream(table([row()]))
    value = json.loads(body.splitlines()[0][6:])
    value["section"]["result_page"]["components"].insert(0, {"chart_type": "futureExtra", "data": {"unvalidated": []}})
    body = "data: " + json.dumps(value) + "\n\n" + body.split("\n\n", 1)[1]
    replay(monkeypatch, body)
    assert len(select(1)) == 1


@pytest.mark.parametrize("later_total", [100, 2])
def test_early_empty_page_or_count_drift_not_partial(monkeypatch, later_total):
    replay(monkeypatch, stream(table([row()], extra={"row_count": 100})),
           [rendered(table([], extra={"row_count": later_total}))])
    with pytest.raises(SourceError, match="提前空页|漂移"):
        select(200)


def test_declared_zero_with_nonempty_page_fails_before_limit(monkeypatch):
    replay(monkeypatch, stream(table([row()], extra={"row_count": 0})))
    with pytest.raises(SourceError, match="超过"):
        select(1)


def test_formula_metadata_preserves_distinct_business_columns(monkeypatch):
    columns = [{"key": "股票代码", "label": "code"}, {"key": "指标1", "unit": "%"},
               {"key": "指标2", "unit": "%"}, {"key": "formula", "source": "calc", "unit": "元"}]
    extra = {"iwc_column_info": {"指标1": {"index_meta": {"label": "涨幅", "index_number": "区间1"}},
                                "指标2": {"index_meta": {"label": "涨幅", "index_number": "区间2"}},
                                "formula": {"index_meta": {"index_number": "收盘价-开盘价"}}}}
    component = table([{"股票代码": "000001.SZ", "指标1": 0, "指标2": None, "formula": "1.2300"}], columns=columns, extra=extra)
    replay(monkeypatch, stream(component))
    assert select(1)[0] == {"code": "000001", "exchange": "sz", "name": None,
                            "涨幅 区间1(%)": 0, "涨幅 区间2(%)": None, "收盘价-开盘价(元)": "1.2300"}


def test_stalled_page_and_budget_stop_fail_without_partial(monkeypatch):
    replay(monkeypatch, stream(table([row()])), [rendered(table([row()]))])
    with pytest.raises(SourceError, match="没有推进"):
        select(2)
    monkeypatch.setattr(source, "_MAX_PAGES", 1)
    replay(monkeypatch, stream(table([row()])))
    with pytest.raises(SourceError, match="防护预算"):
        select(2)


def test_later_auth_failure_does_not_return_first_page(monkeypatch):
    replay(monkeypatch, stream(table([row()])), [{"status_code": -1935, "status_msg": "invalid-secret-for-offline-test"}])
    with pytest.raises(SourceError) as caught:
        select(2)
    assert "invalid-secret-for-offline-test" not in str(caught.value)


def test_transport_and_json_errors_do_not_expose_caller_cookie(monkeypatch):
    secret = "invalid-secret-for-offline-test"
    def broken(*args, **kwargs):
        raise SourceError("mock", secret)
    monkeypatch.setattr(source.http, "post_text", broken)
    with pytest.raises(SourceError) as caught:
        select(cookies=f"x={secret}")
    assert secret not in str(caught.value) and caught.value.__context__ is None
    replay(monkeypatch, f"data: {secret}\n\n")
    with pytest.raises(SourceError) as caught:
        select(cookies=f"x={secret}")
    assert caught.value.__context__ is None
