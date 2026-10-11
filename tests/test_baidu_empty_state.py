"""百度来源窗口耗尽的真实空数组状态及失败边界。"""

from copy import deepcopy
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx._common.news import BEIJING_TZ
from finchx.sources.baidu import news as bd

# 公开 /selfselect/expressnews?rn=20&pn=760 返回的真实耗尽响应。
_EMPTY_RESPONSE = {"QueryID": "2561346637", "ResultCode": "3402", "Result": []}


def test_real_empty_array_result_is_official_exhaustion():
    assert bd._page(deepcopy(_EMPTY_RESPONSE)) == []


@pytest.mark.parametrize("result", [[{"loc": "residual-business"}], [None], "", False, 0,
                                   {"content": []}, {"content": {"list": ""}},
                                   {"content": {"list": [{"loc": "residual-business"}]}}])
def test_empty_status_with_business_or_wrong_type_still_fails(result):
    with pytest.raises(SourceError, match="冲突"):
        bd._page({**_EMPTY_RESPONSE, "Result": result})


@pytest.mark.parametrize("status", [False, True, None, "1", "fail"])
def test_other_or_boolean_status_is_not_exhaustion(status):
    with pytest.raises(SourceError, match="请求失败"):
        bd._page({**_EMPTY_RESPONSE, "ResultCode": status})


def test_success_status_empty_array_outer_result_is_still_damaged():
    with pytest.raises(SourceError, match="expressnews"):
        bd._page({"ResultCode": "0", "Result": []})


def _rows(start, count):
    moment = datetime(2026, 10, 8, 20, tzinfo=BEIJING_TZ)
    return [{"loc": f"opaque-{i}", "publish_time": str(int((moment - timedelta(seconds=i)).timestamp())),
             "content": {"items": [{"type": "text", "data": "来源正文"}]}, "important": "0"}
            for i in range(start, start + count)]


def _success(rows):
    return {"ResultCode": "0", "Result": {"type": "expressnews", "content": {"list": rows}}}


def test_requested_1000_date_window_returns_actual_unique_rows_on_official_empty(monkeypatch):
    first, second = _rows(0, 20), _rows(18, 20)
    second[0]["provider"] = "后读来源值"
    payloads = iter([_success(first), _success(second), deepcopy(_EMPTY_RESPONSE)])
    calls = []
    def fetch(url, **kwargs):
        calls.append(parse_qs(urlsplit(url).query)["pn"])
        return next(payloads)
    monkeypatch.setattr(bd, "get_json", fetch)
    result = bd.bd_list(limit=1000, since="2026-10-01", until="2026-10-08", timeout=17)
    assert len(result) == 38
    assert result[18]["provider"] == "后读来源值"
    assert [row["id"] for row in result] == [f"opaque-{i}" for i in range(38)]
    assert calls == [["0"], ["20"], ["40"]]


def test_official_empty_first_page_returns_empty_without_clock_fill(monkeypatch):
    monkeypatch.setattr(bd, "get_json", lambda *args, **kwargs: deepcopy(_EMPTY_RESPONSE))
    assert bd.bd_list(limit=1000, since="2026-10-01", until="2026-10-08", timeout=17) == []


def test_nonempty_business_on_empty_status_never_returns_collected_partial(monkeypatch):
    payloads = iter([_success(_rows(0, 20)), {**_EMPTY_RESPONSE, "Result": [{"loc": "residual-business"}]}])
    monkeypatch.setattr(bd, "get_json", lambda *args, **kwargs: next(payloads))
    with pytest.raises(SourceError, match="冲突"):
        bd.bd_list(limit=1000, since="2026-10-01", until="2026-10-08", timeout=17)
