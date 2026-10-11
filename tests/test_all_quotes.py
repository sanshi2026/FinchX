"""腾讯分页行情的隔离测试，不依赖线上排名稳定性。"""

from copy import deepcopy
import math
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import FinchX, SourceError
from finchx.sources.tencent import market as tencent


FIELDS = {
    "code", "exchange", "name", "price", "price_change", "change_percent", "volume", "amount",
    "turnover_rate", "market_cap", "float_market_cap", "pe_ttm", "change_percent_5d",
    "change_percent_10d", "change_percent_20d", "change_percent_60d", "change_percent_52w",
    "change_percent_ytd", "amplitude", "volume_ratio", "main_net_inflow", "main_inflow",
    "main_outflow", "main_inflow_5d", "main_outflow_5d",
}


def source_row(code="sz300308", **overrides):
    row = {
        "code": code, "stock_type": "GP-A-CYB", "name": "测试股票", "zxj": "775.35",
        "zd": "-33.09", "zdf": "-4.09", "volume": "246207.00", "turnover": "1968658",
        "hsl": "2.22", "zsz": "9132.92", "ltsz": "8605.90", "pe_ttm": "44.65",
        "zdf_d5": "-15.95", "zdf_d10": "-14.59", "zdf_d20": "-5.72", "zdf_d60": "-31.28",
        "zdf_w52": "92.74", "zdf_y": "27.32", "zf": "7.71", "lb": "1.45",
        "zljlr": "-139915.08", "zllr": "1208291.94", "zllc": "1348207.02",
        "zllr_d5": "5069626.59", "zllc_d5": "5834170.33", "pn": "未知", "speed": "未知",
    }
    row.update(overrides)
    return row


def envelope(rows, *, total=None, offset=0):
    return {"code": 0, "data": {"rank_list": rows, "total": len(rows) if total is None else total, "offset": offset}}


def mock_payload(monkeypatch, payload):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return deepcopy(payload)
    monkeypatch.setattr(tencent, "get_json", request)
    return calls


def test_business_fields_and_units(monkeypatch):
    mock_payload(monkeypatch, envelope([source_row()]))
    row = FinchX().market.all_quotes()[0]
    assert row == {
        "code": "300308", "exchange": "sz", "name": "测试股票", "price": 775.35,
        "price_change": -33.09, "change_percent": -4.09, "volume": 24620700,
        "amount": 19686580000.0, "turnover_rate": 2.22, "market_cap": 913292000000.0,
        "float_market_cap": 860590000000.0, "pe_ttm": 44.65, "change_percent_5d": -15.95,
        "change_percent_10d": -14.59, "change_percent_20d": -5.72, "change_percent_60d": -31.28,
        "change_percent_52w": 92.74, "change_percent_ytd": 27.32, "amplitude": 7.71,
        "volume_ratio": 1.45, "main_net_inflow": -1399150800.0, "main_inflow": 12082919400.0,
        "main_outflow": 13482070200.0, "main_inflow_5d": 50696265900.0, "main_outflow_5d": 58341703300.0,
    }
    assert set(row) == FIELDS
    assert type(row["volume"]) is int
    assert all(type(value) is float and math.isfinite(value) for key, value in row.items() if key not in {"code", "exchange", "name", "volume"})


@pytest.mark.parametrize("volume,expected", [("3369989.69", 336998969), ("0.29", 29), ("12345678901234567890123456789.01", 1234567890123456789012345678901)])
def test_volume_uses_exact_decimal_before_integer(monkeypatch, volume, expected):
    mock_payload(monkeypatch, envelope([source_row(volume=volume)]))
    assert FinchX().market.all_quotes()[0]["volume"] == expected


@pytest.mark.parametrize("missing", [None, "", "--", "-", "  "])
def test_missing_numbers_and_name_preserve_identity(monkeypatch, missing):
    row = source_row()
    for key in row:
        if key not in {"code", "stock_type", "name"}:
            row[key] = missing
    del row["name"]
    mock_payload(monkeypatch, envelope([row]))
    result = FinchX().market.all_quotes()
    assert len(result) == 1
    assert result[0]["code"] == "300308" and result[0]["exchange"] == "sz"
    assert set(result[0]) == FIELDS
    assert all(value is None for key, value in result[0].items() if key not in {"code", "exchange"})


def test_absent_optional_fields_are_null(monkeypatch):
    mock_payload(monkeypatch, envelope([{"code": "bj920001", "stock_type": "GP"}]))
    row = FinchX().market.all_quotes()[0]
    assert row["code"] == "920001" and row["exchange"] == "bj"
    assert all(value is None for key, value in row.items() if key not in {"code", "exchange"})


@pytest.mark.parametrize("name", ["ST测试", "退市测试", "", None])
def test_names_and_zero_quotes_do_not_filter_rows(monkeypatch, name):
    raw = source_row(name=name)
    for key in raw:
        if key not in {"code", "stock_type", "name"}:
            raw[key] = "0"
    mock_payload(monkeypatch, envelope([raw]))
    row = FinchX().market.all_quotes()[0]
    assert row["name"] == (name if name else None)
    assert row["price"] == 0.0 and row["volume"] == 0
    assert all(value == 0 for key, value in row.items() if key not in {"code", "exchange", "name"})


def test_legal_negative_changes_and_fund_values_are_preserved(monkeypatch):
    raw = source_row(pe_ttm="-1.23", zljlr="-2.34", zllr="-3.45", zllc="-4.56", zllr_d5="-5.67", zllc_d5="-6.78")
    mock_payload(monkeypatch, envelope([raw]))
    row = FinchX().market.all_quotes()[0]
    assert row["pe_ttm"] == -1.23 and row["main_net_inflow"] == -23400.0
    assert [row[key] for key in ("main_inflow", "main_outflow", "main_inflow_5d", "main_outflow_5d")] == [-34500.0, -45600.0, -56700.0, -67800.0]


@pytest.mark.parametrize("field", ["zxj", "volume", "turnover", "hsl", "zsz", "ltsz", "zf", "lb"])
def test_negative_nonnegative_fields_fail(monkeypatch, field):
    mock_payload(monkeypatch, envelope([source_row(**{field: "-1"})]))
    with pytest.raises(SourceError, match="不得为负数"):
        FinchX().market.all_quotes()


@pytest.mark.parametrize("value", [True, False, "NaN", "Inf", "-Infinity", float("nan"), float("inf"), "不是数字", [], {}, "1_000", "1e10000"])
def test_invalid_numeric_values_fail(monkeypatch, value):
    mock_payload(monkeypatch, envelope([source_row(zxj=value)]))
    with pytest.raises(SourceError) as caught:
        FinchX().market.all_quotes()
    assert caught.value.source == "tencent"
    assert "price" in caught.value.reason


def test_fractional_share_fails(monkeypatch):
    mock_payload(monkeypatch, envelope([source_row(volume="0.001")]))
    with pytest.raises(SourceError, match="整数股"):
        FinchX().market.all_quotes()


@pytest.mark.parametrize("code,stock_type", [("sh600000", "GP-A"), ("sh688825", "GP-A-KCB"), ("sz300308", "GP-A-CYB"), ("bj920001", "GP")])
def test_supported_identity_types(monkeypatch, code, stock_type):
    mock_payload(monkeypatch, envelope([source_row(code, stock_type=stock_type)]))
    row = FinchX().market.all_quotes()[0]
    assert row["code"] == code[2:] and row["exchange"] == code[:2]


@pytest.mark.parametrize("defect", ["prefix", "short", "unicode", "missing_code", "missing_type", "not_stock", "name", "row"])
def test_invalid_identity_or_row_fails(monkeypatch, defect):
    raw = source_row()
    if defect == "prefix":
        raw["code"] = "hk600000"
    elif defect == "short":
        raw["code"] = "sz00001"
    elif defect == "unicode":
        raw["code"] = "sz３００３０８"
    elif defect == "missing_code":
        del raw["code"]
    elif defect == "missing_type":
        del raw["stock_type"]
    elif defect == "not_stock":
        raw["stock_type"] = "ZS"
    elif defect == "name":
        raw["name"] = 123
    else:
        raw = []
    mock_payload(monkeypatch, envelope([raw]))
    with pytest.raises(SourceError):
        FinchX().market.all_quotes()


def test_multiple_pages_final_size_timeout_and_new_requests(monkeypatch):
    source = [{"code": f"sh{number:06d}", "stock_type": "GP-A"} for number in range(205)]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        offset, count = int(params["offset"][0]), int(params["count"][0])
        calls.append((offset, count, kwargs["timeout"]))
        assert url.startswith(tencent.ENDPOINT + "?")
        assert params["_appver"] == ["11.17.0"] and params["board_code"] == ["aStock"]
        assert params["sort_type"] == ["turnover"] and params["direct"] == ["down"]
        assert kwargs["source"] == "tencent" and kwargs["headers"]["Referer"] == "https://finance.qq.com/"
        return envelope(source[offset:offset + count], total="205", offset=str(offset))
    monkeypatch.setattr(tencent, "get_json", request)
    api = FinchX(timeout=2.5).market
    first = api.all_quotes()
    second = api.all_quotes()
    assert first == second
    assert [row["code"] for row in first] == [f"{number:06d}" for number in range(205)]
    assert calls == [(0, 100, 2.5), (100, 100, 2.5), (200, 5, 2.5)] * 2


def test_empty_universe(monkeypatch):
    calls = mock_payload(monkeypatch, envelope([], total=0))
    assert FinchX().market.all_quotes() == []
    assert len(calls) == 1


@pytest.mark.parametrize("defect", ["outer", "data", "rank_list", "status_outer", "status_inner", "status_bool", "status_null", "error", "error_bool", "negative_total", "float_total", "bool_total", "missing_total", "wrong_offset", "null_offset", "early_empty", "short", "too_many", "zero_with_rows"])
def test_invalid_page_envelope_fails(monkeypatch, defect):
    payload = envelope([source_row()])
    if defect == "outer":
        payload = []
    elif defect == "data":
        payload["data"] = []
    elif defect == "rank_list":
        payload["data"]["rank_list"] = {}
    elif defect == "status_outer":
        payload["code"] = 1619377101
    elif defect == "status_inner":
        payload["data"]["status"] = "failed"
    elif defect == "status_bool":
        payload["code"] = True
    elif defect == "status_null":
        payload["code"] = None
    elif defect == "error":
        payload["data"]["error"] = "来源失败"
    elif defect == "error_bool":
        payload["data"]["error"] = False
    elif defect == "negative_total":
        payload["data"]["total"] = -1
    elif defect == "float_total":
        payload["data"]["total"] = 1.0
    elif defect == "bool_total":
        payload["data"]["total"] = True
    elif defect == "missing_total":
        del payload["data"]["total"]
    elif defect == "wrong_offset":
        payload["data"]["offset"] = 1
    elif defect == "null_offset":
        payload["data"]["offset"] = None
    elif defect == "early_empty":
        payload["data"]["rank_list"] = []
    elif defect == "short":
        payload["data"]["total"] = 2
    elif defect == "too_many":
        payload["data"]["rank_list"] *= 2
    else:
        payload["data"]["total"] = 0
    mock_payload(monkeypatch, payload)
    with pytest.raises(SourceError) as caught:
        FinchX().market.all_quotes()
    assert caught.value.source == "tencent"


@pytest.mark.parametrize("defect", ["duplicate_page", "unrepaired_overlap", "total_drift", "later_empty"])
def test_pagination_failure_never_returns_partial_or_deduplicated_rows(monkeypatch, defect):
    source = [{"code": f"sz{number:06d}", "stock_type": "GP"} for number in range(101)]
    calls = []
    def request(url, **kwargs):
        offset = int(parse_qs(urlparse(url).query)["offset"][0])
        calls.append(offset)
        if offset == 0:
            rows = deepcopy(source[:100])
            if defect == "duplicate_page":
                rows[1] = rows[0]
            return envelope(rows, total=101, offset=offset)
        total = 102 if defect == "total_drift" else 101
        rows = [source[0]] if defect == "unrepaired_overlap" else source[100:]
        if defect == "later_empty":
            rows = []
        return envelope(rows, total=total, offset=offset)
    monkeypatch.setattr(tencent, "get_json", request)
    with pytest.raises(SourceError) as caught:
        FinchX().market.all_quotes()
    if defect == "unrepaired_overlap":
        assert calls == [0, 100] * 3
        assert "最多 3 轮" in caught.value.reason and "实际取得 100" in caught.value.reason


def test_optional_status_and_offset_may_be_absent(monkeypatch):
    payload = envelope([source_row()])
    del payload["code"]
    del payload["data"]["offset"]
    mock_payload(monkeypatch, payload)
    assert len(FinchX().market.all_quotes()) == 1


def test_transport_error_keeps_source_context(monkeypatch):
    error = SourceError("tencent", "网络请求失败")
    def request(*args, **kwargs):
        raise error
    monkeypatch.setattr(tencent, "get_json", request)
    with pytest.raises(SourceError) as caught:
        FinchX().market.all_quotes()
    assert caught.value is error


@pytest.mark.parametrize("repair_round", [2, 3])
def test_moving_pages_are_repaired_with_all_stocks_and_latest_values(monkeypatch, repair_round):
    source = [source_row(f"sh{number:06d}", zxj="1") for number in range(101)]
    rounds = [("turnover", "down"), ("turnover", "up"), ("volume", "down")]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        order = (params["sort_type"][0], params["direct"][0])
        current_round = rounds.index(order) + 1
        offset = int(params["offset"][0])
        calls.append((order, offset))
        rows = deepcopy(source[offset:offset + int(params["count"][0])])
        if offset == 100 and current_round < repair_round:
            rows = [deepcopy(source[0])]  # 跨页重复，100号身份被实时移动遗漏。
        for row in rows:
            row["zxj"] = str(current_round)
        return envelope(rows, total=101, offset=offset)
    monkeypatch.setattr(tencent, "get_json", request)
    rows = FinchX().market.all_quotes()
    assert {row["code"] for row in rows} == {f"{number:06d}" for number in range(101)}
    assert len(rows) == 101
    assert all(row["price"] == float(repair_round) for row in rows)
    assert calls == [(order, offset) for order in rounds[:repair_round] for offset in (0, 100)]


@pytest.mark.parametrize("defect", ["total_drift", "too_many_unique", "same_page_duplicate"])
def test_repair_round_integrity_is_still_required(monkeypatch, defect):
    source = [source_row(f"sh{number:06d}") for number in range(102)]
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        offset = int(params["offset"][0])
        if params["direct"] == ["down"]:
            rows = source[:100] if offset == 0 else [source[0]]
            return envelope(rows, total=101, offset=offset)
        rows = deepcopy(source[:100])
        if defect == "too_many_unique":
            rows[-2:] = source[100:102]
        elif defect == "same_page_duplicate":
            rows[1] = rows[0]
        return envelope(rows, total=102 if defect == "total_drift" else 101, offset=offset)
    monkeypatch.setattr(tencent, "get_json", request)
    with pytest.raises(SourceError):
        FinchX().market.all_quotes()


@pytest.mark.parametrize("criterion,source_field,sort_type", [("amount", "turnover", "turnover"), ("change_percent", "zdf", "priceRatio"), ("volume", "volume", "volume")])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_ranking_orders_business_metric_and_keeps_missing_last(monkeypatch, criterion, source_field, sort_type, direction):
    source = [
        source_row("sz300001", **{source_field: "2"}),
        source_row("sh600002", **{source_field: "2"}),
        source_row("bj920001", **{source_field: None}),
        source_row("sh600001", **{source_field: "0"}),
    ]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        calls.append((params["sort_type"][0], params["direct"][0]))
        return envelope(source)
    monkeypatch.setattr(tencent, "get_json", request)
    rows = FinchX().market.ranking(criterion, direction, None)
    expected = ["600001", "600002", "300001", "920001"] if direction == "asc" else ["600002", "300001", "600001", "920001"]
    assert [row["code"] for row in rows] == expected
    assert rows[-1][criterion] is None
    assert all(set(row) == FIELDS for row in rows)
    assert calls == [(sort_type, "up" if direction == "asc" else "down")]


@pytest.mark.parametrize("limit,expected", [(1, 1), (50, 3), (None, 3)])
def test_ranking_limits_without_dropping_missing_values(monkeypatch, limit, expected):
    source = [source_row("sh600002", zdf="0"), source_row("sh600001", zdf="-1"), source_row("sh600003", zdf=None)]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        offset, count = int(params["offset"][0]), int(params["count"][0])
        calls.append((offset, count))
        return envelope(source[offset:offset + count], total=len(source), offset=offset)
    monkeypatch.setattr(tencent, "get_json", request)
    rows = FinchX().market.ranking(limit=limit)
    assert len(rows) == expected
    assert rows[0]["code"] == "600002"
    if expected == 3:
        assert rows[-1]["change_percent"] is None
    assert calls == [(0, min(tencent._PAGE_SIZE, limit if limit is not None else tencent._PAGE_SIZE))]


@pytest.mark.parametrize("kwargs", [
    {"criterion": "price"}, {"criterion": []}, {"direction": "down"}, {"direction": True},
    {"limit": 0}, {"limit": -1}, {"limit": True}, {"limit": 1.0}, {"limit": "50"},
])
def test_invalid_ranking_parameters_fail_before_request(monkeypatch, kwargs):
    calls = mock_payload(monkeypatch, envelope([]))
    with pytest.raises(ValueError):
        FinchX().market.ranking(**kwargs)
    assert calls == []


def test_ranking_uses_source_sort_and_reads_only_requested_window(monkeypatch):
    source = [source_row(f"sh{number:06d}", zdf=str(number)) for number in range(100, -1, -1)]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        offset = int(params["offset"][0])
        count = int(params["count"][0])
        order = (params["sort_type"][0], params["direct"][0])
        calls.append((order, offset, count))
        return envelope(deepcopy(source[offset:offset + count]), total=len(source), offset=offset)
    monkeypatch.setattr(tencent, "get_json", request)
    rows = FinchX().market.ranking(limit=3)
    assert [row["code"] for row in rows] == ["000100", "000099", "000098"]
    assert [row["change_percent"] for row in rows] == [100.0, 99.0, 98.0]
    assert calls == [(('priceRatio', 'down'), 0, 3)]


def test_finite_ranking_reads_only_enough_pages(monkeypatch):
    source = [source_row(f"sh{number:06d}", zdf=str(number)) for number in range(149, -1, -1)]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        offset, count = int(params["offset"][0]), int(params["count"][0])
        calls.append((offset, count))
        return envelope(deepcopy(source[offset:offset + count]), total=len(source), offset=offset)
    monkeypatch.setattr(tencent, "get_json", request)
    rows = FinchX().market.ranking(limit=101)
    assert [row["code"] for row in rows[:2]] == ["000149", "000148"]
    assert [row["code"] for row in rows[-2:]] == ["000050", "000049"]
    assert len(rows) == 101
    assert calls == [(0, 100), (100, 1)]


def test_finite_ranking_extends_source_window_for_cross_page_overlap(monkeypatch):
    source = [source_row(f"sh{number:06d}", zdf=str(number)) for number in range(199, -1, -1)]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        offset, count = int(params["offset"][0]), int(params["count"][0])
        calls.append((offset, count))
        if offset == 100:
            rows = [deepcopy(source[99])]
        elif offset == 101:
            rows = [deepcopy(source[100])]
        else:
            rows = deepcopy(source[offset:offset + count])
        return envelope(rows, total=len(source), offset=offset)
    monkeypatch.setattr(tencent, "get_json", request)
    rows = FinchX().market.ranking(limit=101)
    assert len(rows) == 101
    assert [row["code"] for row in rows[-2:]] == ["000100", "000099"]
    assert calls == [(0, 100), (100, 1), (101, 1)]
