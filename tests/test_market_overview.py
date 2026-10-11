"""市场涨跌分布与情绪接口的来源协议、单位及缺失值测试。"""

from copy import deepcopy
import json
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import FinchX, SourceError
from finchx.sources.eastmoney import breadth
from finchx.sources.aigupiao import sentiment


def breadth_payload():
    counts = {code: 0 for code in range(-11, 12)}
    counts.update({-11: 3, -10: 8, 0: 4, 10: 7, 11: 2})
    return {"rc": 0, "data": {"qdate": 20261008, "fenbu": [{str(code): counts[code]} for code in reversed(range(-11, 12))]}}


def mock_breadth(monkeypatch, payload):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return f"finchxEastmoney({json.dumps(payload)});"
    monkeypatch.setattr(breadth, "get_text", request)
    return calls


def test_breadth_official_ranges_nine_percent_boundaries_and_totals(monkeypatch):
    calls = mock_breadth(monkeypatch, breadth_payload())
    api = FinchX(timeout=2.5).market
    row = api.em_breadth()
    assert set(row) == {"date", "advancing", "declining", "unchanged", "total", "limit_up_count", "limit_down_count", "up_over_9_percent_count", "down_over_9_percent_count", "distribution"}
    assert row["date"] == "2026-10-08"
    assert (row["advancing"], row["declining"], row["unchanged"], row["total"]) == (9, 11, 4, 24)
    assert (row["limit_up_count"], row["limit_down_count"]) == (2, 3)
    assert (row["up_over_9_percent_count"], row["down_over_9_percent_count"]) == (7, 8)
    assert [entry["range"] for entry in row["distribution"]] == [
        "跌停", "低于-9%(未跌停)", "-9%--8%", "-8%--7%", "-7%--6%", "-6%--5%",
        "-5%--4%", "-4%--3%", "-3%--2%", "-2%--1%", "-1%--0%", "0%",
        "0%-1%", "1%-2%", "2%-3%", "3%-4%", "4%-5%", "5%-6%", "6%-7%",
        "7%-8%", "8%-9%", "高于9%(未涨停)", "涨停",
    ]
    assert all(set(entry) == {"range", "count"} and type(entry["count"]) is int for entry in row["distribution"])
    assert row["total"] == sum(entry["count"] for entry in row["distribution"])
    assert api.em_breadth() == row
    assert len(calls) == 2
    params = parse_qs(urlparse(calls[0][0]).query)
    assert params["cb"] == ["finchxEastmoney"]
    assert params["ut"] == ["7eea3edcaed734bea9cbfc24409ed989"] and params["dpt"] == ["wz.ztzt"]
    assert calls[0][1]["timeout"] == 2.5 and calls[0][1]["source"] == "eastmoney"


def test_breadth_zero_counts_string_integers_and_leap_source_date(monkeypatch):
    payload = {"rc": "0", "data": {"qdate": "20240229", "fenbu": [{str(code): "0"} for code in range(-11, 12)]}}
    mock_breadth(monkeypatch, payload)
    row = FinchX().market.em_breadth()
    assert row["date"] == "2024-02-29"
    assert all(value == 0 for key, value in row.items() if key not in {"date", "distribution"})
    assert all(entry["count"] == 0 for entry in row["distribution"])


@pytest.mark.parametrize("defect", ["outer", "rc", "rc_bool", "data", "date_missing", "date_format", "date_invalid", "date_bool", "fenbu", "missing_bucket", "duplicate_bucket", "unknown_bucket", "row", "multiple_keys", "count_missing", "count_bool", "count_float", "count_negative"])
def test_breadth_corruption_fails_instead_of_inventing_buckets(monkeypatch, defect):
    payload = breadth_payload()
    data = payload["data"]
    if defect == "outer":
        payload = []
    elif defect == "rc":
        payload["rc"] = 1
    elif defect == "rc_bool":
        payload["rc"] = False
    elif defect == "data":
        payload["data"] = None
    elif defect == "date_missing":
        del data["qdate"]
    elif defect == "date_format":
        data["qdate"] = "2026-10-08"
    elif defect == "date_invalid":
        data["qdate"] = "20260229"
    elif defect == "date_bool":
        data["qdate"] = True
    elif defect == "fenbu":
        data["fenbu"] = {}
    elif defect == "missing_bucket":
        data["fenbu"].pop()
    elif defect == "duplicate_bucket":
        data["fenbu"][1] = data["fenbu"][0]
    elif defect == "unknown_bucket":
        data["fenbu"][0] = {"12": 3}
    elif defect == "row":
        data["fenbu"][0] = None
    elif defect == "multiple_keys":
        data["fenbu"][0]["10"] = 0
    else:
        values = {"count_missing": None, "count_bool": True, "count_float": 1.0, "count_negative": -1}
        data["fenbu"][0] = {"11": values[defect]}
    mock_breadth(monkeypatch, payload)
    with pytest.raises(SourceError) as caught:
        FinchX().market.em_breadth()
    assert caught.value.source == "eastmoney"


@pytest.mark.parametrize("text", ['otherCallback({"rc":0});', '{"rc":0}', "finchxEastmoney(not-json);", "finchxEastmoney({}); trailing"])
def test_breadth_requires_exact_callback_and_valid_json(monkeypatch, text):
    monkeypatch.setattr(breadth, "get_text", lambda *args, **kwargs: text)
    with pytest.raises(SourceError):
        FinchX().market.em_breadth()


def sentiment_payload():
    return {"code": "0", "status": "success", "data": {
        "market_temperature": "29°C", "total_turnover": "1.67万亿", "forecasted_turnover": "1.69万亿",
        "turnover_growing_data": "2482亿", "turnover_chg": "17.51%", "median_val": "-1.10%",
        "blast_break_pct": "44%", "limit_up_break_chg_pct": "-4.68%", "stop_trad_stock_num": 15,
        "one_limit_up_stock_num": 31, "two_limit_up_stock_num": 3, "three_limit_up_stock_num": 3,
        "high_limit_up_stock_num": 3, "two_limit_up_stock_rate": "6%", "three_limit_up_stock_rate": "50%",
        "high_limit_up_stock_rate": "42%", "raising_limit_theme_chg_pct": "-0.03%", "repetition_limit_theme_chg_pct": "4.77%",
    }}


def mock_sentiment(monkeypatch, payload):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return deepcopy(payload)
    monkeypatch.setattr(sentiment, "get_json", request)
    return calls


def test_sentiment_business_fields_chinese_amounts_and_percentage_points(monkeypatch):
    calls = mock_sentiment(monkeypatch, sentiment_payload())
    api = FinchX(timeout=3.5).market
    row = api.agp_sentiment()
    assert row == {
        "market_temperature": 29.0, "total_turnover": 1670000000000.0,
        "forecasted_turnover": 1690000000000.0, "turnover_change_amount": 248200000000.0,
        "turnover_change_percent": 17.51, "median_change_percent": -1.1, "blast_break_percent": 44.0,
        "previous_limit_up_break_change_percent": -4.68, "stop_trading_count": 15,
        "one_limit_up_count": 31, "two_limit_up_count": 3, "three_limit_up_count": 3,
        "high_limit_up_count": 3, "two_limit_up_promotion_percent": 6.0,
        "three_limit_up_promotion_percent": 50.0, "high_limit_up_promotion_percent": 42.0,
        "previous_limit_up_theme_change_percent": -0.03, "previous_consecutive_limit_up_theme_change_percent": 4.77,
    }
    assert all(type(value) is int if key.endswith("_count") else type(value) is float for key, value in row.items())
    assert api.agp_sentiment() == row and len(calls) == 2
    assert parse_qs(urlparse(calls[0][0]).query)["ts"][0].isdigit()
    assert calls[0][1]["timeout"] == 3.5 and calls[0][1]["source"] == "aigupiao"
    assert calls[0][1]["headers"]["Referer"] == "https://www.10jqka.com.cn/"


@pytest.mark.parametrize("value,expected", [("2.35万亿", 2350000000000.0), ("2.35亿", 235000000.0), ("2.35万", 23500.0), ("2.35元", 2.35), ("0", 0.0), ("-2.35亿", -235000000.0)])
def test_sentiment_amount_units_and_legal_negative_change(monkeypatch, value, expected):
    mock_sentiment(monkeypatch, {"code": 0, "status": "success", "data": {"turnover_growing_data": value}})
    assert FinchX().market.agp_sentiment()["turnover_change_amount"] == expected


@pytest.mark.parametrize("missing", [None, "", "--", "-"])
def test_sentiment_optional_missing_fields_and_zero_are_distinct(monkeypatch, missing):
    payload = {"code": 0, "status": "success", "data": {"market_temperature": missing, "stop_trad_stock_num": "0", "turnover_chg": "0%", "未知字段": "不输出"}}
    mock_sentiment(monkeypatch, payload)
    row = FinchX().market.agp_sentiment()
    assert row["market_temperature"] is None
    assert row["stop_trading_count"] == 0 and type(row["stop_trading_count"]) is int
    assert row["turnover_change_percent"] == 0.0
    assert all(value is None for key, value in row.items() if key not in {"stop_trading_count", "turnover_change_percent"})
    assert "未知字段" not in row


@pytest.mark.parametrize("field,value", [
    ("market_temperature", True), ("market_temperature", "NaN°C"), ("market_temperature", "°C"),
    ("total_turnover", "-1亿"), ("forecasted_turnover", "-1万"), ("total_turnover", "2美元"),
    ("total_turnover", float("inf")), ("total_turnover", "1e10000亿"), ("turnover_chg", "%"),
    ("median_val", "Inf%"), ("stop_trad_stock_num", True), ("stop_trad_stock_num", 1.0),
    ("stop_trad_stock_num", "1.5"), ("stop_trad_stock_num", -1),
])
def test_sentiment_invalid_business_values_fail(monkeypatch, field, value):
    mock_sentiment(monkeypatch, {"code": 0, "status": "success", "data": {field: value}})
    with pytest.raises(SourceError) as caught:
        FinchX().market.agp_sentiment()
    assert caught.value.source == "aigupiao"


@pytest.mark.parametrize("payload", [[], {"code": 1, "status": "success", "data": {"market_temperature": "29°C"}}, {"code": False, "status": "success", "data": {"market_temperature": "29°C"}}, {"code": 0, "status": "failed", "data": {"market_temperature": "29°C"}}, {"code": 0, "status": "success", "data": None}, {"code": 0, "status": "success", "data": {}}, {"code": 0, "status": "success", "data": {"未知": 1}}])
def test_sentiment_invalid_envelope_or_unknown_only_data_fails(monkeypatch, payload):
    mock_sentiment(monkeypatch, payload)
    with pytest.raises(SourceError):
        FinchX().market.agp_sentiment()
