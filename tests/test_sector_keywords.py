"""东方财富关键词的真实字段、源身份和缺失统计语义。"""

from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest

from finchx import FinchX, SourceError
from finchx.sources.eastmoney import keywords

_FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sector_em_keywords_600519.json").read_text(encoding="utf-8"))
_FIELDS = {"keyword_code", "keyword_name", "hit_count", "calculated_at"}


def payload():
    return deepcopy(_FIXTURE)


def serve(monkeypatch, response):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return deepcopy(response)
    monkeypatch.setattr(keywords, "post_json", request)
    return calls


def test_all_real_source_rows_exact_business_fields_and_post(monkeypatch):
    response = payload()
    response["data"][0]["flag"] = {"未知": True}
    response["data"][0]["new_field"] = ["未知"]
    calls = serve(monkeypatch, response)
    rows = FinchX(timeout=20).sector.em_keywords("600519")
    assert len(rows) == len(response["data"]) == 5
    assert [row["keyword_code"] for row in rows] == ["BK0896", "BK0999", "BK0811", "BK0665", "BK0834"]
    assert rows[0] == {
        "keyword_code": "BK0896", "keyword_name": "白酒",
        "hit_count": 4536, "calculated_at": "2026-10-08T16:00:00+08:00",
    }
    assert [row["keyword_name"] for row in rows] == ["白酒", "茅指数", "超级品牌", "电商概念", "乡村振兴"]
    assert [row["hit_count"] for row in rows] == [4536, 201, 80, 41, 2]
    assert all(set(row) == _FIELDS and type(row["hit_count"]) is int for row in rows)
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == keywords.ENDPOINT
    assert kwargs["data"] == {"srcSecurityCode": "SH600519"}
    assert kwargs["timeout"] == 20.0 and kwargs["source"] == "eastmoney"
    assert list(inspect.signature(FinchX().sector.em_keywords).parameters) == ["code"]


def test_source_order_is_not_resorted_and_every_call_is_fresh(monkeypatch):
    response = payload()
    response["data"].reverse()
    calls = serve(monkeypatch, response)
    api = FinchX().sector
    first = api.em_keywords("600519")
    second = api.em_keywords("600519")
    assert first == second and len(calls) == 2
    assert [row["keyword_code"] for row in first] == [raw["conceptId"] for raw in response["data"]]


@pytest.mark.parametrize("code,symbol", [("600519", "SH600519"), ("688001", "SH688001"), ("000001", "SZ000001"), ("300001", "SZ300001")])
def test_verified_stock_prefixes_keep_source_request_identity(monkeypatch, code, symbol):
    response = payload()
    for raw in response["data"]:
        raw["srcSecurityCode"] = symbol
    calls = serve(monkeypatch, response)
    rows = keywords.em_keywords(code, timeout=3)
    assert len(rows) == len(response["data"]) and all(set(row) == _FIELDS for row in rows)
    assert calls[0][0] == keywords.ENDPOINT
    assert calls[0][1]["data"] == {"srcSecurityCode": symbol}


@pytest.mark.parametrize("code", [None, True, 600519, "60051", "６００５１９", "sh600519", " 600519", "399001", "920001"])
def test_invalid_or_unsupported_code_fails_before_request(monkeypatch, code):
    calls = serve(monkeypatch, payload())
    with pytest.raises(ValueError):
        FinchX().sector.em_keywords(code)
    assert calls == []


@pytest.mark.parametrize("timeout", [True, None, 0, -1, float("inf"), "15"])
def test_source_timeout_validates_before_request(monkeypatch, timeout):
    calls = serve(monkeypatch, payload())
    with pytest.raises(ValueError):
        keywords.em_keywords("600519", timeout=timeout)
    assert calls == []


@pytest.mark.parametrize("missing", [None, "", " ", "--", "-"])
def test_optional_source_values_remain_none_without_dropping_keywords(monkeypatch, missing):
    response = payload()
    response["data"] = [response["data"][0]]
    response["data"][0].update(conceptName=missing, hitCount=missing, calcTime=missing)
    serve(monkeypatch, response)
    row = keywords.em_keywords("600519", timeout=15)[0]
    assert set(row) == _FIELDS
    assert row["keyword_code"] == "BK0896"
    assert row["keyword_name"] is None and row["hit_count"] is None and row["calculated_at"] is None


def test_absent_leaves_and_real_zero_are_distinct(monkeypatch):
    response = payload()
    response["data"] = [
        {"srcSecurityCode": "SH600519", "conceptId": "BK0001"},
        {"srcSecurityCode": "SH600519", "conceptId": "BK0002", "hitCount": 0},
    ]
    serve(monkeypatch, response)
    rows = keywords.em_keywords("600519", timeout=15)
    assert rows[0]["hit_count"] is None
    assert rows[1]["hit_count"] == 0 and type(rows[1]["hit_count"]) is int


def test_success_empty_data_is_a_valid_list(monkeypatch):
    response = payload()
    response.update(code="0", status="0")
    response["data"] = []
    calls = serve(monkeypatch, response)
    assert keywords.em_keywords("600519", timeout=15) == [] and len(calls) == 1


@pytest.mark.parametrize("value,expected", [("2024-02-29 00:00:00", "2024-02-29T00:00:00+08:00"), ("2026-10-08 23:59:59", "2026-10-08T23:59:59+08:00")])
def test_source_time_boundary_precision_and_timezone(monkeypatch, value, expected):
    response = payload()
    response["data"][0]["calcTime"] = value
    serve(monkeypatch, response)
    assert keywords.em_keywords("600519", timeout=15)[0]["calculated_at"] == expected


@pytest.mark.parametrize("field,value", [
    ("conceptName", 123), ("conceptName", True), ("hitCount", True), ("hitCount", False),
    ("hitCount", -1), ("hitCount", 1.0), ("hitCount", 1.5), ("hitCount", "1.5"),
    ("hitCount", float("nan")), ("hitCount", float("inf")), ("hitCount", "NaN"), ("hitCount", {}),
    ("calcTime", "2026-02-29 16:00:00"), ("calcTime", "2026-10-08T16:00:00"),
    ("calcTime", "2026-10-08 24:00:00"), ("calcTime", "2026-10-08 16:00:60"),
    ("calcTime", "2026-10-08 16:00"), ("calcTime", "２０２６-10-08 16:00:00"),
    ("calcTime", True), ("calcTime", 20261008160000),
    ("conceptId", "bk0896"), ("conceptId", "BK896"), ("conceptId", "BK０８９６"), ("conceptId", None),
    ("srcSecurityCode", "SH000001"), ("srcSecurityCode", "600519"), ("srcSecurityCode", None),
])
def test_invalid_known_fields_or_identity_fail(monkeypatch, field, value):
    response = payload()
    response["data"][0][field] = value
    serve(monkeypatch, response)
    with pytest.raises(SourceError) as caught:
        keywords.em_keywords("600519", timeout=15)
    assert caught.value.source == "eastmoney" and field in caught.value.reason


def test_repeated_keyword_id_does_not_silently_deduplicate(monkeypatch):
    response = payload()
    response["data"].append(deepcopy(response["data"][0]))
    serve(monkeypatch, response)
    with pytest.raises(SourceError, match="conceptId 重复"):
        keywords.em_keywords("600519", timeout=15)


@pytest.mark.parametrize("defect", ["outer", "code_missing", "code_bool", "code_error", "status_missing", "status_bool", "status_error", "data_missing", "data_null", "data_object", "row"])
def test_bad_success_status_or_missing_data_is_not_an_empty_result(monkeypatch, defect):
    response = payload()
    if defect == "outer": response = []
    elif defect == "code_missing": del response["code"]
    elif defect == "code_bool": response["code"] = False
    elif defect == "code_error": response["code"] = 1
    elif defect == "status_missing": del response["status"]
    elif defect == "status_bool": response["status"] = False
    elif defect == "status_error": response["status"] = -1
    elif defect == "data_missing": del response["data"]
    elif defect == "data_null": response["data"] = None
    elif defect == "data_object": response["data"] = {}
    elif defect == "row": response["data"][0] = []
    serve(monkeypatch, response)
    with pytest.raises(SourceError) as caught:
        keywords.em_keywords("600519", timeout=15)
    assert caught.value.source == "eastmoney"


def test_transport_error_propagates_once_without_retry(monkeypatch):
    calls = []
    error = SourceError("eastmoney", "网络失败")
    def request(*args, **kwargs):
        calls.append(args)
        raise error
    monkeypatch.setattr(keywords, "post_json", request)
    with pytest.raises(SourceError) as caught:
        FinchX().sector.em_keywords("600519")
    assert caught.value is error and len(calls) == 1
