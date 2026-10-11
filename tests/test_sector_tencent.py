"""腾讯板块真实响应及来源结构、身份、单位边界。"""

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import SourceError
from finchx.sources.tencent import sector

_FIXTURES = Path(__file__).parent / "fixtures"
_SECTORS = json.loads((_FIXTURES / "sector_tencent_sectors_600519.json").read_text(encoding="utf-8"))
_INDUSTRY_TEXT = (_FIXTURES / "sector_tencent_industry_600519.json").read_text(encoding="utf-8")
_INDUSTRY = json.loads(_INDUSTRY_TEXT)
_SECTOR_KEYS = {"sector_type", "sector_code", "sector_name", "change_percent", "level", "tag"}
_INDUSTRY_KEYS = {
    "code", "exchange", "industry_code", "industry_name", "pe", "eps", "float_market_cap",
    "pe_rank", "eps_rank", "float_market_cap_rank", "industry_count",
    "industry_avg_pe", "industry_avg_eps", "industry_avg_float_market_cap",
    "market_avg_pe", "market_avg_eps", "market_avg_float_market_cap",
}


def serve(monkeypatch, response, *, industry=False):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        if industry:
            return response if isinstance(response, str) else "gg_hypm=" + json.dumps(response)
        return deepcopy(response)
    monkeypatch.setattr(sector, "get_text" if industry else "get_json", request)
    return calls


def test_sectors_real_capture_complete_fixed_fields_and_one_fresh_request(monkeypatch):
    calls = serve(monkeypatch, _SECTORS)
    rows = sector.tx_sectors("600519", timeout=7)
    assert len(rows) == 23
    assert all(set(row) == _SECTOR_KEYS for row in rows)
    assert [row["sector_type"] for row in rows] == ["area"] + ["industry"] * 2 + ["concept"] * 20
    assert rows[0] == {"sector_type": "area", "sector_code": "03001173",
                       "sector_name": "贵州", "change_percent": -0.02, "level": None, "tag": None}
    assert rows[1]["sector_code"] == "01801120" and rows[1]["level"] == 1
    assert rows[2]["sector_name"] == "白酒Ⅱ" and rows[2]["level"] == 2
    baijiu = next(row for row in rows if row["sector_code"] == "02B20001")
    assert baijiu["tag"] == "走势最相关" and baijiu["change_percent"] == -0.46
    assert next(row for row in rows if row["sector_code"] == "02003596")["tag"] == "涨停19"
    for block, kind in [("area", "area"), ("plate", "industry"), ("concept", "concept")]:
        observed = {row["sector_code"]: row for row in rows if row["sector_type"] == kind}
        assert set(observed) == {raw["id"] for raw in _SECTORS["data"][block]}
        for raw in _SECTORS["data"][block]:
            row = observed[raw["id"]]
            assert row["sector_name"] == raw["name"] and row["change_percent"] == float(raw["zdf"])
            assert row["level"] == (int(raw["level"]) if "level" in raw else None)
            assert row["tag"] == (raw.get("tag") or None)
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url.split("?")[0] == sector.SECTORS_ENDPOINT
    assert parse_qs(urlparse(url).query) == {"code": ["sh600519"], "app": ["wzq"], "zdf": ["1"]}
    assert kwargs["timeout"] == 7.0 and kwargs["source"] == "tencent"
    assert sector.tx_sectors("600519", timeout=7) == rows and len(calls) == 2


def test_sectors_keeps_yesterday_missing_zero_extra_fields_and_type_identity(monkeypatch):
    raw = {"code": "0", "msg": "", "data": {
        "area": [{"id": "same"}], "plate": [{"code": "same", "level": 0, "zdf": 0}],
        "concept": [{"id": "z", "name": "昨日涨停", "tag": "涨停0", "zdf": "0", "extra": {}},
                    {"id": "a", "name": "", "tag": "", "zdf": "--"}], "unknown": False}, "extra": 1}
    serve(monkeypatch, raw)
    rows = sector.tx_sectors("600519", timeout=1)
    assert [(row["sector_type"], row["sector_code"]) for row in rows] == [
        ("area", "same"), ("industry", "same"), ("concept", "a"), ("concept", "z")]
    assert rows[0]["sector_name"] is None and rows[0]["change_percent"] is None
    assert rows[1]["level"] == 0 and rows[1]["change_percent"] == 0.0
    assert rows[2]["sector_name"] is None and rows[2]["tag"] is None and rows[2]["change_percent"] is None
    assert rows[3]["sector_name"] == "昨日涨停" and rows[3]["tag"] == "涨停0"


def test_explicit_empty_sectors_are_valid(monkeypatch):
    serve(monkeypatch, {"code": 0, "msg": "", "data": {"area": [], "plate": [], "concept": []}})
    assert sector.tx_sectors("000001", timeout=1) == []


@pytest.mark.parametrize("code", [600519, True, None, "６００５１９", "60051", "sh600519", " 600519", "600519 ", "920001", "399001"])
@pytest.mark.parametrize("industry", [False, True])
def test_invalid_codes_fail_before_network(monkeypatch, code, industry):
    calls = serve(monkeypatch, _INDUSTRY if industry else _SECTORS, industry=industry)
    with pytest.raises(ValueError):
        (sector.tx_industry_comparison if industry else sector.tx_sectors)(code, timeout=1)
    assert not calls


@pytest.mark.parametrize("timeout", [True, None, "15", 0, -1, float("inf"), float("nan")])
@pytest.mark.parametrize("industry", [False, True])
def test_invalid_timeout_fails_before_network(monkeypatch, timeout, industry):
    calls = serve(monkeypatch, _INDUSTRY if industry else _SECTORS, industry=industry)
    with pytest.raises(ValueError):
        (sector.tx_industry_comparison if industry else sector.tx_sectors)("600519", timeout=timeout)
    assert not calls


@pytest.mark.parametrize("block", ["area", "plate", "concept"])
@pytest.mark.parametrize("value", [None, {}, "", False])
def test_sectors_required_lists_cannot_be_missing_or_wrong_type(monkeypatch, block, value):
    raw = deepcopy(_SECTORS)
    if value is None:
        raw["data"].pop(block)
    else:
        raw["data"][block] = value
    serve(monkeypatch, raw)
    with pytest.raises(SourceError, match=block):
        sector.tx_sectors("600519", timeout=1)


@pytest.mark.parametrize("row", [None, [], {"name": "无代码"}, {"id": ""}, {"id": 1}, {"id": True},
                                {"id": "x y"}, {"id": "x", "code": "y"}, {"id": "x", "code": False},
                                {"id": "x", "name": 0}, {"id": "x", "tag": False},
                                {"id": "x", "zdf": True}, {"id": "x", "zdf": float("inf")},
                                {"id": "x", "level": 1.5}, {"id": "x", "level": True}, {"id": "x", "level": -1}])
def test_sectors_bad_known_fields_fail(monkeypatch, row):
    raw = deepcopy(_SECTORS)
    raw["data"]["concept"] = [row]
    serve(monkeypatch, raw)
    with pytest.raises(SourceError):
        sector.tx_sectors("600519", timeout=1)


def test_duplicate_same_type_sector_fails(monkeypatch):
    raw = deepcopy(_SECTORS)
    raw["data"]["concept"].append(deepcopy(raw["data"]["concept"][0]))
    serve(monkeypatch, raw)
    with pytest.raises(SourceError, match="重复"):
        sector.tx_sectors("600519", timeout=1)


@pytest.mark.parametrize("industry", [False, True])
@pytest.mark.parametrize("update", [{"code": True}, {"code": 1}, {"code": 0.0}, {"code": None}, {"msg": None}, {"data": []}])
def test_source_failure_status_and_root_shape_fail(monkeypatch, industry, update):
    raw = deepcopy(_INDUSTRY if industry else _SECTORS)
    raw.update(update)
    serve(monkeypatch, raw, industry=industry)
    with pytest.raises(SourceError):
        (sector.tx_industry_comparison if industry else sector.tx_sectors)("600519", timeout=1)


def test_industry_real_capture_units_all_fields_one_fresh_request(monkeypatch):
    calls = serve(monkeypatch, "gg_hypm=" + _INDUSTRY_TEXT, industry=True)
    row = sector.tx_industry_comparison("600519", timeout=2.5)
    assert set(row) == _INDUSTRY_KEYS
    assert row == {
        "code": "600519", "exchange": "sh", "industry_code": "012010", "industry_name": "酿酒",
        "pe": 49.91, "eps": 17.99, "float_market_cap": 2188925000000.0,
        "pe_rank": 23, "eps_rank": 1, "float_market_cap_rank": 1, "industry_count": 35,
        "industry_avg_pe": 54.644, "industry_avg_eps": 2.244,
        "industry_avg_float_market_cap": 71796400000.0,
        "market_avg_pe": 52.12, "market_avg_eps": 0.263, "market_avg_float_market_cap": 30982999999.999996,
    }
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url.split("?")[0] == sector.INDUSTRY_ENDPOINT
    assert parse_qs(urlparse(url).query) == {"code": ["sh600519"], "_var": ["gg_hypm"]}
    assert kwargs["timeout"] == 2.5 and kwargs["source"] == "tencent"
    assert sector.tx_industry_comparison("600519", timeout=2.5) == row and len(calls) == 2


def test_industry_real_json_decimal_is_scaled_before_float(monkeypatch):
    serve(monkeypatch, "gg_hypm=" + _INDUSTRY_TEXT, industry=True)
    row = sector.tx_industry_comparison("600519", timeout=1)
    # 原始 JSON 的市场均值是 309.82999999999998；先转 float 会变为 309.83。
    expected = float(Decimal("309.82999999999998") * Decimal("100000000"))
    assert row["market_avg_float_market_cap"] == expected
    assert row["market_avg_float_market_cap"] != float(Decimal(str(_INDUSTRY["data"]["shsz_avg"]["avg_zsz"])) * Decimal("100000000"))


@pytest.mark.parametrize("code,symbol", [("600519", "sh600519"), ("688001", "sh688001"), ("000001", "sz000001"), ("300001", "sz300001")])
@pytest.mark.parametrize("industry", [False, True])
def test_supported_stock_prefixes_preserve_request_identity(monkeypatch, code, symbol, industry):
    raw = deepcopy(_INDUSTRY if industry else _SECTORS)
    if industry:
        raw["data"]["data"]["sclx"] = "1" if symbol.startswith("sh") else "51"
    calls = serve(monkeypatch, raw, industry=industry)
    result = (sector.tx_industry_comparison if industry else sector.tx_sectors)(code, timeout=1)
    if industry:
        assert result["code"] == code and result["exchange"] == symbol[:2]
    else:
        assert len(result) == 23 and all(set(row) == _SECTOR_KEYS for row in result)
        assert result[0]["sector_code"] == "03001173" and result[0]["sector_name"] == "贵州"
    assert parse_qs(urlparse(calls[0][0]).query)["code"] == [symbol]
    assert len(calls) == 1


def test_industry_negative_pe_eps_zero_ranks_missing_and_unknown_fields(monkeypatch):
    raw = {"code": "0", "msg": "OK", "data": {"hyinfo": {"dm": "000001", "unknown": {}},
           "data": {"sclx": "51", "syl": -1, "mgsy": "-2", "zsz": 0},
           "pm": {"syl_pm": 0, "mgsy_pm": "0", "zsz_pm": 0},
           "plate_avg": {"count": 0, "avg_syl": "--", "avg_mgsy": -3}, "shsz_avg": {}, "extra": []}}
    serve(monkeypatch, raw, industry=True)
    row = sector.tx_industry_comparison("000001", timeout=1)
    assert row["exchange"] == "sz" and row["industry_code"] == "000001" and row["industry_name"] is None
    assert row["pe"] == -1 and row["eps"] == -2 and row["industry_avg_eps"] == -3
    assert row["pe_rank"] == row["eps_rank"] == row["float_market_cap_rank"] == row["industry_count"] == 0
    assert row["float_market_cap"] == 0.0 and row["industry_avg_pe"] is None and row["market_avg_pe"] is None
    assert "date" not in row and "time" not in row and "pe_ttm" not in row and "market_cap" not in row


@pytest.mark.parametrize("text", ["", "{}", "gg_hypm=[]", "other={}", "gg_hypm={}; alert(1)",
                                 "gg_hypm={bad}", "gg_hypm={\"x\":NaN}", "gg_hypm={\"x\":Infinity}"])
def test_industry_rejects_malformed_assignment_or_executable_suffix(monkeypatch, text):
    serve(monkeypatch, text, industry=True)
    with pytest.raises(SourceError):
        sector.tx_industry_comparison("600519", timeout=1)


def test_industry_accepts_whitespace_and_optional_semicolon(monkeypatch):
    serve(monkeypatch, " \n gg_hypm = " + json.dumps(_INDUSTRY) + " ;\n", industry=True)
    assert sector.tx_industry_comparison("600519", timeout=1)["industry_code"] == "012010"


@pytest.mark.parametrize("block", ["hyinfo", "data", "pm", "plate_avg", "shsz_avg"])
@pytest.mark.parametrize("value", [None, [], False])
def test_industry_required_blocks_fail(monkeypatch, block, value):
    raw = deepcopy(_INDUSTRY)
    if value is None:
        raw["data"].pop(block)
    else:
        raw["data"][block] = value
    serve(monkeypatch, raw, industry=True)
    with pytest.raises(SourceError, match=block):
        sector.tx_industry_comparison("600519", timeout=1)


@pytest.mark.parametrize("market_type", ["51", 1, True, "0"])
def test_industry_exchange_mismatch_fails(monkeypatch, market_type):
    raw = deepcopy(_INDUSTRY)
    raw["data"]["data"]["sclx"] = market_type
    serve(monkeypatch, raw, industry=True)
    with pytest.raises(SourceError, match="交易所"):
        sector.tx_industry_comparison("600519", timeout=1)


@pytest.mark.parametrize("block,key,value", [
    ("hyinfo", "dm", None), ("hyinfo", "dm", ""), ("hyinfo", "dm", 12010), ("hyinfo", "hymc", 1),
    ("data", "syl", True), ("data", "mgsy", []), ("data", "zsz", -1), ("data", "zsz", "Infinity"),
    ("pm", "syl_pm", True), ("pm", "mgsy_pm", 1.2), ("pm", "zsz_pm", -1),
    ("plate_avg", "count", -1), ("plate_avg", "count", 2.3), ("plate_avg", "count", True),
    ("plate_avg", "avg_syl", {}), ("plate_avg", "avg_zsz", -1), ("shsz_avg", "avg_zsz", -1),
])
def test_industry_invalid_known_leaf_fields_fail(monkeypatch, block, key, value):
    raw = deepcopy(_INDUSTRY)
    raw["data"][block][key] = value
    serve(monkeypatch, raw, industry=True)
    with pytest.raises(SourceError):
        sector.tx_industry_comparison("600519", timeout=1)


def test_industry_source_message_must_be_ok(monkeypatch):
    raw = deepcopy(_INDUSTRY)
    raw["msg"] = "failed"
    serve(monkeypatch, raw, industry=True)
    with pytest.raises(SourceError, match="msg"):
        sector.tx_industry_comparison("600519", timeout=1)
