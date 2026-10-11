"""合并股票资金流的公开接线、来源单位与必要结构验证。"""

from copy import deepcopy
import inspect
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import FinchX, SourceError
from finchx.sources.tencent import fund_flow

_FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "fund_flow_600519.json").read_text(encoding="utf-8"))
_SNAPSHOT = {
    "main_net_inflow": "mainNetIn", "main_inflow": "mainIn", "main_outflow": "mainOut",
    "main_inflow_percent": "mainInRate", "main_outflow_percent": "mainOutRate",
    "retail_inflow": "retailIn", "retail_outflow": "retailOut",
    "retail_inflow_percent": "retailInRate", "retail_outflow_percent": "retailOutRate",
    "super_large_net_inflow": "superFlow", "large_net_inflow": "bigFlow",
    "medium_net_inflow": "normalFlow", "small_net_inflow": "smallFlow",
}
_INTRADAY = {
    "price": "Price", "cumulative_main_net_inflow": "MainNetInflow",
    "cumulative_retail_net_inflow": "RetailNetInflow", "cumulative_super_large_net_inflow": "SuperNetInflow",
    "cumulative_large_net_inflow": "BigNetInflow", "cumulative_medium_net_inflow": "NormalNetInflow",
    "cumulative_small_net_inflow": "SmallNetInflow", "cumulative_main_inflow": "MainInflow",
    "cumulative_main_outflow": "MainOutflow",
}


def payload():
    return deepcopy(_FIXTURE)


def serve(monkeypatch, response):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return deepcopy(response)
    monkeypatch.setattr(fund_flow, "get_json", request)
    return calls


def test_namespace_has_three_entries_and_stock_forwards_timeout(monkeypatch):
    calls = []
    sentinel = {"code": "600519"}
    def source(code, days=20, *, timeout):
        calls.append((code, days, timeout))
        return sentinel
    monkeypatch.setattr(fund_flow, "stock", source)
    api = FinchX(timeout=2.5)
    assert api.fund_flow.stock("600519") is sentinel
    assert api.fund_flow.stock("000001", 7) is sentinel
    assert calls == [("600519", 20, 2.5), ("000001", 7, 2.5)]
    assert list(inspect.signature(api.fund_flow.stock).parameters) == ["code", "days"]
    assert [key for key, value in vars(type(api.fund_flow)).items() if not key.startswith("_") and callable(value)] == ["stock", "dragon_tiger_list", "dragon_tiger_detail"]
    for name in ["fund_flow_snapshot", "fund_flow_intraday", "fund_flow_daily"]:
        assert not hasattr(api.market, name) and not hasattr(api.fund_flow, name)


def test_real_fixture_units_fixed_fields_and_single_fresh_request(monkeypatch):
    calls = serve(monkeypatch, payload())
    api = FinchX(timeout=7).fund_flow
    row = api.stock("600519", days=7)
    assert set(row) == {"code", "exchange", "snapshot", "intraday", "daily"}
    assert row["code"] == "600519" and row["exchange"] == "sh"
    assert set(row["snapshot"]) == {"date", *_SNAPSHOT}
    assert row["snapshot"]["date"] == "2026-10-08"
    assert all(set(point) == {"date", "time", *_INTRADAY} for point in row["intraday"])
    assert all(set(point) == {"date", "price", "main_net_inflow"} for point in row["daily"])
    assert row["snapshot"]["main_inflow"] == 1714388884.0
    assert row["snapshot"]["main_net_inflow"] == -114334536.0
    assert row["snapshot"]["main_inflow_percent"] == 27.0
    assert row["snapshot"]["retail_outflow_percent"] == 21.0
    assert row["intraday"][0]["cumulative_main_inflow"] == 136637961.0
    assert row["intraday"][1]["cumulative_main_inflow"] == 186410433.0  # 来源累计，未变成分钟差额。
    assert row["intraday"][0]["price"] == 1246.95
    assert row["daily"][-1] == {"date": "2026-10-08", "price": 1255.79, "main_net_inflow": -114334536.0}
    for point in [row["snapshot"], *row["intraday"], *row["daily"]]:
        assert all(type(value) is float for key, value in point.items() if key not in {"date", "time"})
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url.split("?")[0] == fund_flow.ENDPOINT
    params = parse_qs(urlparse(url).query)
    assert params["code"] == ["sh600519"] and params["klineNeedDay"] == ["7"]
    assert {"todayFundFlow", "todayFundTrend", "historyFundFlow"} <= set(params["type"][0].split(","))
    assert kwargs["timeout"] == 7.0 and kwargs["source"] == "tencent"
    assert api.stock("600519", days=7) == row and len(calls) == 2


@pytest.mark.parametrize("days", [1, 2, 7, 20, 21, 30, 50])
def test_verified_window_values_and_source_short_history(monkeypatch, days):
    response = payload()
    source = response["data"]["historyFundFlow"]["oneDayKlineList"][-days:]
    response["data"]["historyFundFlow"]["oneDayKlineList"] = source
    calls = serve(monkeypatch, response)
    row = FinchX().fund_flow.stock("600519", days)
    assert len(row["daily"]) == len(source) <= days
    assert parse_qs(urlparse(calls[0][0]).query)["klineNeedDay"] == [str(days)]
    assert len(calls) == 1


@pytest.mark.parametrize("code,symbol", [("600519", "sh600519"), ("688001", "sh688001"), ("000001", "sz000001"), ("300001", "sz300001")])
def test_stock_identity_supported_prefixes(monkeypatch, code, symbol):
    response = payload()
    for key in ["todayFundFlow", "todayFundTrend"]:
        response["data"][key]["stockCode"] = symbol
    calls = serve(monkeypatch, response)
    row = FinchX().fund_flow.stock(code)
    assert (row["code"], row["exchange"]) == (code, symbol[:2])
    assert parse_qs(urlparse(calls[0][0]).query)["code"] == [symbol]


@pytest.mark.parametrize("kwargs", [
    {"code": 600519}, {"code": True}, {"code": None}, {"code": "６００５１９"},
    {"code": "60051"}, {"code": "sh600519"}, {"code": " 600519"}, {"code": "920001"},
    {"code": "399001"}, {"days": True}, {"days": False}, {"days": 0}, {"days": -1},
    {"days": 51}, {"days": 60}, {"days": 1.0}, {"days": "20"}, {"days": None},
])
def test_invalid_parameters_fail_before_request(monkeypatch, kwargs):
    calls = serve(monkeypatch, payload())
    with pytest.raises(ValueError):
        FinchX().fund_flow.stock(**({"code": "600519"} | kwargs))
    assert calls == []


@pytest.mark.parametrize("timeout", [True, 0, -1, float("inf"), None, "15"])
def test_source_timeout_validated_before_request(monkeypatch, timeout):
    calls = serve(monkeypatch, payload())
    with pytest.raises(ValueError):
        fund_flow.stock("600519", timeout=timeout)
    assert calls == []


@pytest.mark.parametrize("missing", [None, "", "--", "-", " "])
def test_missing_business_leaves_remain_none(monkeypatch, missing):
    response = payload()
    for key in _SNAPSHOT.values():
        response["data"]["todayFundFlow"][key] = missing
    for point in response["data"]["todayFundTrend"]["minList"]:
        for key in _INTRADAY.values():
            point[key] = missing
    for point in response["data"]["historyFundFlow"]["oneDayKlineList"]:
        for key in ["price", "mainNetIn"]:
            point[key] = missing
    serve(monkeypatch, response)
    row = FinchX().fund_flow.stock("600519")
    for point in [row["snapshot"], *row["intraday"], *row["daily"]]:
        assert all(value is None for key, value in point.items() if key not in {"date", "time"})


def test_absent_optional_leaves_do_not_drop_points(monkeypatch):
    response = payload()
    response["data"]["todayFundFlow"] = {"stockCode": "sh600519"}
    response["data"]["todayFundTrend"]["minList"] = [{"time": "202610080930"}]
    response["data"]["historyFundFlow"]["oneDayKlineList"] = [{"date": "2026-09-30"}]
    serve(monkeypatch, response)
    row = FinchX().fund_flow.stock("600519")
    assert row["snapshot"]["date"] == "2026-10-08"
    assert row["intraday"] == [{"date": "2026-10-08", "time": "09:30", **dict.fromkeys(_INTRADAY)}]
    assert row["daily"] == [{"date": "2026-09-30", "price": None, "main_net_inflow": None}]


def test_zero_and_decreasing_negative_cumulative_net_are_source_facts(monkeypatch):
    response = payload()
    for key in _SNAPSHOT.values():
        response["data"]["todayFundFlow"][key] = 0
    points = response["data"]["todayFundTrend"]["minList"]
    for index, point in enumerate(points):
        for field, key in _INTRADAY.items():
            point[key] = -(index + 1) if "net_inflow" in field else 0
    for point in response["data"]["historyFundFlow"]["oneDayKlineList"]:
        point.update(price=0, mainNetIn=-2)
    serve(monkeypatch, response)
    row = FinchX().fund_flow.stock("600519")
    assert all(value == 0.0 and type(value) is float for key, value in row["snapshot"].items() if key != "date")
    assert [point["cumulative_main_net_inflow"] for point in row["intraday"]] == [-1.0, -2.0, -3.0]
    assert row["intraday"][0]["price"] == 0.0 and row["daily"][0]["main_net_inflow"] == -2.0


def test_ignored_blocks_unknown_values_and_arithmetic_disagreements_do_not_fail(monkeypatch):
    response = payload()
    response["data"].update(fiveDayFundFlow={"bad": True}, unknown_block=["未知"], prec={}, activeFlow=True)
    response["data"]["todayFundFlow"].update(summary="坏摘要", mainNetIn="-1", mainInRate="0", unknown=True)
    response["data"]["historyFundFlow"]["summary"] = ["坏汇总"]
    for point in response["data"]["historyFundFlow"]["oneDayKlineList"]:
        point["avgIn"] = {"不确认含义": True}
    serve(monkeypatch, response)
    row = FinchX().fund_flow.stock("600519")
    assert row["snapshot"]["main_net_inflow"] == -1.0
    assert set(row["snapshot"]) == {"date", *_SNAPSHOT}
    assert all(set(point) == {"date", "price", "main_net_inflow"} for point in row["daily"])


def test_dates_and_times_sorted_snapshot_date_anchored_to_trend(monkeypatch):
    response = payload()
    points = response["data"]["todayFundTrend"]["minList"]
    for point in points:
        point["time"] = "20260918" + point["time"][8:]
    points.reverse()
    response["data"]["historyFundFlow"]["oneDayKlineList"].reverse()
    serve(monkeypatch, response)
    row = FinchX().fund_flow.stock("600519")
    assert row["snapshot"]["date"] == "2026-09-18"
    assert [point["time"] for point in row["intraday"]] == ["09:30", "09:31", "15:00"]
    assert [point["date"] for point in row["daily"]] == sorted(point["date"] for point in row["daily"])
    assert row["daily"][-1]["date"] == "2026-10-08"


def test_explicit_empty_daily_supported_without_inventing_dates(monkeypatch):
    response = payload()
    response["data"]["historyFundFlow"]["oneDayKlineList"] = []
    serve(monkeypatch, response)
    row = FinchX().fund_flow.stock("600519")
    assert row["daily"] == [] and row["snapshot"]["date"] == "2026-10-08"


@pytest.mark.parametrize("defect", [
    "outer", "code", "code_bool", "code_missing", "msg", "data", "today_missing", "trend_missing", "history_missing",
    "today_identity", "trend_identity", "history_identity", "today_identity_missing", "trend_identity_missing",
    "trend_empty", "trend_structure", "trend_row", "time_missing", "time_int", "time_format", "time_invalid", "time_duplicate", "cross_day",
    "history_structure", "history_row", "date_missing", "date_format", "date_invalid", "date_duplicate", "history_excess",
])
def test_necessary_identity_date_and_structure_errors_fail(monkeypatch, defect):
    response = payload()
    data = response["data"]
    trend = data["todayFundTrend"]["minList"]
    daily = data["historyFundFlow"]["oneDayKlineList"]
    if defect == "outer": response = []
    elif defect == "code": response["code"] = 1
    elif defect == "code_bool": response["code"] = False
    elif defect == "code_missing": del response["code"]
    elif defect == "msg": response["msg"] = "failed"
    elif defect == "data": response["data"] = []
    elif defect in {"today_missing", "trend_missing", "history_missing"}:
        del data[{"today": "todayFundFlow", "trend": "todayFundTrend", "history": "historyFundFlow"}[defect.split("_")[0]]]
    elif "identity" in defect:
        key = {"today": "todayFundFlow", "trend": "todayFundTrend", "history": "historyFundFlow"}[defect.split("_")[0]]
        if defect.endswith("missing"): del data[key]["stockCode"]
        else: data[key]["stockCode"] = "sz000001"
    elif defect == "trend_empty": data["todayFundTrend"]["minList"] = []
    elif defect == "trend_structure": data["todayFundTrend"]["minList"] = {}
    elif defect == "trend_row": trend[0] = []
    elif defect == "time_missing": del trend[0]["time"]
    elif defect == "time_int": trend[0]["time"] = 202610080930
    elif defect == "time_format": trend[0]["time"] = "2026-10-08 09:30"
    elif defect == "time_invalid": trend[0]["time"] = "202602300930"
    elif defect == "time_duplicate": trend[1]["time"] = trend[0]["time"]
    elif defect == "cross_day": trend[1]["time"] = "202610090931"
    elif defect == "history_structure": data["historyFundFlow"]["oneDayKlineList"] = None
    elif defect == "history_row": daily[0] = "不是对象"
    elif defect == "date_missing": del daily[0]["date"]
    elif defect == "date_format": daily[0]["date"] = "20260918"
    elif defect == "date_invalid": daily[0]["date"] = "2026-02-30"
    elif defect == "date_duplicate": daily[1]["date"] = daily[0]["date"]
    elif defect == "history_excess": daily.extend(deepcopy(daily) * 3)
    serve(monkeypatch, response)
    with pytest.raises(SourceError) as caught:
        FinchX().fund_flow.stock("600519")
    assert caught.value.source == "tencent"


@pytest.mark.parametrize("block,field,value", [
    ("snapshot", "mainNetIn", True), ("snapshot", "mainIn", -1), ("snapshot", "retailOut", -1),
    ("snapshot", "mainInRate", "NaN"), ("snapshot", "retailOutRate", -1), ("snapshot", "bigFlow", []),
    ("intraday", "Price", -1), ("intraday", "Price", False), ("intraday", "MainInflow", -1),
    ("intraday", "MainOutflow", "-Infinity"), ("intraday", "MainNetInflow", "NaN"),
    ("intraday", "SuperNetInflow", {}), ("daily", "price", -1), ("daily", "price", float("inf")),
    ("daily", "mainNetIn", True), ("daily", "mainNetIn", "不是数字"),
])
def test_invalid_known_numbers_and_negative_gross_values_fail(monkeypatch, block, field, value):
    response = payload()
    if block == "snapshot": response["data"]["todayFundFlow"][field] = value
    elif block == "intraday": response["data"]["todayFundTrend"]["minList"][0][field] = value
    else: response["data"]["historyFundFlow"]["oneDayKlineList"][0][field] = value
    serve(monkeypatch, response)
    with pytest.raises(SourceError) as caught:
        FinchX().fund_flow.stock("600519")
    assert caught.value.source == "tencent" and field in caught.value.reason


def test_source_error_is_propagated_without_retry(monkeypatch):
    calls = []
    error = SourceError("tencent", "源请求失败")
    def request(*args, **kwargs):
        calls.append(args)
        raise error
    monkeypatch.setattr(fund_flow, "get_json", request)
    with pytest.raises(SourceError) as caught:
        FinchX().fund_flow.stock("600519")
    assert caught.value is error and len(calls) == 1
