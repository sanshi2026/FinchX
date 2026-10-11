"""连板字段、来源分页和缺失语义的隔离验证。"""

from copy import deepcopy
from urllib.parse import parse_qs, urlparse

import pytest

from finchx import SourceError
from finchx.sources.aigupiao import consecutive


FIELDS = {
    "date", "code", "exchange", "name", "price", "price_change", "change_percent",
    "turnover_rate", "amount", "market_cap", "float_shares", "total_shares",
    "limit_up_time", "consecutive_limit_up_days", "is_consecutive_limit_up", "state",
    "previous_consecutive_limit_up_days", "theme_name",
}


def source_row(code="sh600825", **changes):
    # 来自已保存真实响应的首行；未知字段不进入返回契约。
    row = {
        "last_price": 11.39, "change_pct": 10.048, "code": code, "name": "新华传媒",
        "limit_up_time": "09:30", "day": "2026-10-08", "x_series_limit_up": 8,
        "series_limit_up": "yes", "state": "8连板", "last_day_continuous_up_times": 0,
        "turnover_rate": "0.54", "amount": "64324548.00", "whole": "119.01",
        "chg": "1.040", "ltg": 1044887872, "zgb": 1044887872,
        "theme_id": 998, "theme_name": "昨日连板",
    }
    row.update(changes)
    return row


def envelope(rows, total=None):
    return {"status": "success", "code": "0", "message": "success", "data": {"total": len(rows) if total is None else total, "list": rows}}


def stub(monkeypatch, payload):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return deepcopy(payload)
    monkeypatch.setattr(consecutive, "get_json", request)
    return calls


def test_real_source_row_exact_fields_units_and_request(monkeypatch):
    calls = stub(monkeypatch, envelope([source_row()]))
    rows = consecutive.consecutive_limit_up(timeout=2.5)
    assert rows == [{
        "date": "2026-10-08", "code": "600825", "exchange": "sh", "name": "新华传媒",
        "price": 11.39, "price_change": 1.04, "change_percent": 10.048,
        "turnover_rate": 0.54, "amount": 64324548.0, "market_cap": 11901000000.0,
        "float_shares": 1044887872, "total_shares": 1044887872, "limit_up_time": "09:30",
        "consecutive_limit_up_days": 8, "is_consecutive_limit_up": True,
        "state": "8连板", "previous_consecutive_limit_up_days": 0, "theme_name": "昨日连板",
    }]
    assert set(rows[0]) == FIELDS
    url, kwargs = calls[0]
    assert urlparse(url).scheme == "https" and url.split("?")[0] == consecutive.ENDPOINT
    assert parse_qs(urlparse(url).query) == {
        "number": ["500"], "page": ["1"], "type": ["series_limit_up"], "source": ["pc"],
        "st_stock": ["n"], "new_stock": ["n"], "sort_type": ["limit_up_state"], "sort_mode": ["desc"],
    }
    assert kwargs["timeout"] == 2.5 and kwargs["source"] == "aigupiao"
    assert kwargs["headers"]["Referer"] == "https://www.aigupiao.com/"


@pytest.mark.parametrize("missing", [None, "", " ", "--", "-"])
def test_optional_missing_values_keep_identity_row(monkeypatch, missing):
    raw = {key: missing for key in source_row()}
    raw.update(code="bj920001", day="2024-02-29", theme_id={"未知": True}, extra=["未知"])
    stub(monkeypatch, envelope([raw]))
    row = consecutive.consecutive_limit_up(timeout=15)[0]
    assert set(row) == FIELDS
    assert (row["date"], row["code"], row["exchange"]) == ("2024-02-29", "920001", "bj")
    assert all(value is None for key, value in row.items() if key not in {"date", "code", "exchange"})


def test_absent_business_fields_do_not_drop_row(monkeypatch):
    stub(monkeypatch, envelope([{"code": "sz000001", "day": "2026-09-30"}]))
    row = consecutive.consecutive_limit_up(timeout=15)[0]
    assert row["date"] == "2026-09-30" and row["code"] == "000001"
    assert all(value is None for key, value in row.items() if key not in {"date", "code", "exchange"})


def test_zero_and_source_counts_not_inferred_from_state(monkeypatch):
    raw = source_row(name="ST退市测试", last_price=0, chg=0, change_pct=0, turnover_rate=0,
        amount=0, whole=0, ltg=0, zgb=0, x_series_limit_up=0, state="20天8板",
        series_limit_up="no", last_day_continuous_up_times=0)
    stub(monkeypatch, envelope([raw]))
    row = consecutive.consecutive_limit_up(timeout=15)[0]
    assert row["name"] == "ST退市测试" and row["state"] == "20天8板"
    assert row["is_consecutive_limit_up"] is False
    for key in ["float_shares", "total_shares", "consecutive_limit_up_days", "previous_consecutive_limit_up_days"]:
        assert row[key] == 0 and type(row[key]) is int
    for key in ["price", "price_change", "change_percent", "turnover_rate", "amount", "market_cap"]:
        assert row[key] == 0 and type(row[key]) is float


@pytest.mark.parametrize("amount,expected", [("2.35万亿", 2350000000000.0), ("2.35亿", 235000000.0), ("2.35万", 23500.0), ("2.35元", 2.35), (2.35, 2.35)])
def test_amount_display_units_and_negative_changes(monkeypatch, amount, expected):
    stub(monkeypatch, envelope([source_row(amount=amount, chg="-1.23", change_pct="-2.34")]))
    row = consecutive.consecutive_limit_up(timeout=15)[0]
    assert row["amount"] == expected and row["price_change"] == -1.23 and row["change_percent"] == -2.34


@pytest.mark.parametrize("limit_time", ["00:00", "23:59", "09:30:00", "15:14:59"])
def test_time_precision_preserved_and_no_market_cap_guess(monkeypatch, limit_time):
    stub(monkeypatch, envelope([source_row(limit_up_time=limit_time, whole="0", x_series_limit_up=4, state="未确认")]))
    row = consecutive.consecutive_limit_up(timeout=15)[0]
    assert row["limit_up_time"] == limit_time and row["market_cap"] == 0.0
    assert row["consecutive_limit_up_days"] == 4


@pytest.mark.parametrize("changes", [
    {"code": None}, {"code": 600825}, {"code": "600825"}, {"code": "hk600825"}, {"code": "sh６００８２５"},
    {"day": None}, {"day": "20260229"}, {"day": "2026-02-29"}, {"day": True},
    {"series_limit_up": True}, {"series_limit_up": "unknown"}, {"series_limit_up": 0},
    {"limit_up_time": "24:00"}, {"limit_up_time": "09:30:60"}, {"limit_up_time": "930"},
    {"name": 123}, {"state": []}, {"theme_name": {}}, {"last_price": -1},
    {"change_pct": "NaN"}, {"chg": float("inf")}, {"turnover_rate": True},
    {"amount": "-1亿"}, {"amount": "2美元"}, {"whole": -1}, {"whole": "Infinity"},
    {"ltg": -1}, {"zgb": True}, {"ltg": 1.5}, {"x_series_limit_up": -1},
    {"x_series_limit_up": "1.5"}, {"last_day_continuous_up_times": -1},
])
def test_bad_identity_or_known_business_values_fail(monkeypatch, changes):
    stub(monkeypatch, envelope([source_row(**changes)]))
    with pytest.raises(SourceError) as caught:
        consecutive.consecutive_limit_up(timeout=15)
    assert caught.value.source == "aigupiao"


@pytest.mark.parametrize("payload", [
    [], {}, {"code": False, "status": "success", "data": {"total": 0, "list": []}},
    {"code": 0, "status": "failed", "data": {"total": 0, "list": []}},
    {"code": 0, "status": "success", "data": []},
    {"code": 0, "status": "success", "data": {"list": []}},
    envelope([], total=-1), envelope([], total=True), envelope([], total=0.0),
    envelope([None]), envelope([], total=1), envelope([source_row()], total=0),
])
def test_invalid_envelope_or_short_page_fails(monkeypatch, payload):
    stub(monkeypatch, payload)
    with pytest.raises(SourceError):
        consecutive.consecutive_limit_up(timeout=15)


def test_full_multiple_pages_and_every_call_fresh(monkeypatch):
    source = [source_row(f"sh{number:06d}") for number in range(501)]
    calls = []
    def request(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        page = int(params["page"][0])
        assert params["number"] == ["500"]
        calls.append((page, kwargs["timeout"]))
        return envelope(source[(page - 1) * 500:page * 500], total="501")
    monkeypatch.setattr(consecutive, "get_json", request)
    first = consecutive.consecutive_limit_up(timeout=3)
    assert first == consecutive.consecutive_limit_up(timeout=3)
    assert len(first) == 501 and len({row["code"] for row in first}) == 501
    assert calls == [(1, 3.0), (2, 3.0)] * 2


@pytest.mark.parametrize("repair_round", [2, 3])
def test_cross_page_overlap_repaired_with_latest_rows(monkeypatch, repair_round):
    monkeypatch.setattr(consecutive, "_PAGE_SIZE", 2)
    calls = []
    def request(url, **kwargs):
        page = int(parse_qs(urlparse(url).query)["page"][0])
        round_number = len(calls) // 2 + 1
        calls.append(page)
        codes = ["sh600001", "sz000001"] if page == 1 else ["sh600001" if round_number < repair_round else "bj920001"]
        return envelope([source_row(code, last_price=round_number) for code in codes], total=3)
    monkeypatch.setattr(consecutive, "get_json", request)
    rows = consecutive.consecutive_limit_up(timeout=15)
    assert {(row["exchange"], row["code"]) for row in rows} == {("sh", "600001"), ("sz", "000001"), ("bj", "920001")}
    assert all(row["price"] == float(repair_round) for row in rows)
    assert calls == [1, 2] * repair_round


@pytest.mark.parametrize("defect", ["overlap", "same_page", "total", "date", "short", "too_many_unique"])
def test_pagination_corruption_never_returns_partial(monkeypatch, defect):
    monkeypatch.setattr(consecutive, "_PAGE_SIZE", 2)
    calls = []
    def request(url, **kwargs):
        page = int(parse_qs(urlparse(url).query)["page"][0])
        round_number = len(calls) // 2 + 1
        calls.append(page)
        rows = [source_row("sh600001"), source_row("sz000001")] if page == 1 else [source_row("sh600001")]
        total = 3
        if defect == "same_page":
            rows = [source_row("sh600001")] * 2 if page == 1 else rows
        elif defect == "total" and page == 2:
            total = 4
        elif defect == "date" and page == 2:
            rows[0]["day"] = "2026-09-30"
        elif defect == "short" and page == 2:
            rows = []
        elif defect == "too_many_unique" and round_number == 2:
            rows = [source_row("sh600002"), source_row("sh600003")] if page == 1 else [source_row("bj920001")]
        return envelope(rows, total=total)
    monkeypatch.setattr(consecutive, "get_json", request)
    with pytest.raises(SourceError) as caught:
        consecutive.consecutive_limit_up(timeout=15)
    if defect == "overlap":
        assert calls == [1, 2] * 3 and "最多 3 轮" in caught.value.reason


def test_explicit_success_empty_universe(monkeypatch):
    calls = stub(monkeypatch, envelope([]))
    assert consecutive.consecutive_limit_up(timeout=15) == [] and len(calls) == 1


def test_date_drift_in_repair_round_fails(monkeypatch):
    monkeypatch.setattr(consecutive, "_PAGE_SIZE", 2)
    calls = []
    def request(url, **kwargs):
        page = int(parse_qs(urlparse(url).query)["page"][0])
        day = "2026-10-08" if len(calls) < 2 else "2026-10-09"
        calls.append(page)
        codes = ["sh600001", "sz000001"] if page == 1 else ["sh600001"]
        return envelope([source_row(code, day=day) for code in codes], total=3)
    monkeypatch.setattr(consecutive, "get_json", request)
    with pytest.raises(SourceError, match="日期不一致"):
        consecutive.consecutive_limit_up(timeout=15)
    assert calls == [1, 2, 1]


@pytest.mark.parametrize("timeout", [True, 0, -1, float("inf"), "15", None])
def test_bad_timeout_before_request(monkeypatch, timeout):
    calls = stub(monkeypatch, envelope([]))
    with pytest.raises(ValueError):
        consecutive.consecutive_limit_up(timeout=timeout)
    assert calls == []


def test_transport_failure_preserves_exception(monkeypatch):
    error = SourceError("aigupiao", "网络错误")
    def request(*args, **kwargs):
        raise error
    monkeypatch.setattr(consecutive, "get_json", request)
    with pytest.raises(SourceError) as caught:
        consecutive.consecutive_limit_up(timeout=15)
    assert caught.value is error
