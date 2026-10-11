"""爱股票最新连板列表，保留来源业务值并核对完整分页。"""

from datetime import date
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx.sources.aigupiao.sentiment import _amount, _count

ENDPOINT = "https://app.aigupiao.com/stock/getAnalysisInfo"
_HEADERS = {**DEFAULT_HEADERS, "Accept": "application/json, text/plain, */*", "Referer": "https://www.aigupiao.com/"}
_PAGE_SIZE = 500
_CODE = re.compile(r"(sh|sz|bj)([0-9]{6})", re.I)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TIME = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?")
_MISSING = {"", "--", "-"}


def _fail(reason: str) -> None:
    raise SourceError("aigupiao", reason)


def _missing(value: Any) -> bool:
    return value is None or isinstance(value, str) and value.strip() in _MISSING


def _text(value: Any, field: str) -> str | None:
    if _missing(value):
        return None
    if not isinstance(value, str):
        _fail(f"字段 {field} 必须是文字或空值")
    return value


def _parse_row(raw: Any) -> dict:
    if not isinstance(raw, dict):
        _fail("连板列表行必须是对象")
    code = raw.get("code")
    identity = _CODE.fullmatch(code) if isinstance(code, str) else None
    if identity is None:
        _fail("连板股票身份必须为显式 sh/sz/bj 与六位 ASCII 代码")
    source_date = raw.get("day")
    if not isinstance(source_date, str) or not _DATE.fullmatch(source_date):
        _fail("连板来源 day 必须是 YYYY-MM-DD 日期")
    try:
        day = date.fromisoformat(source_date).isoformat()
    except ValueError as exc:
        raise SourceError("aigupiao", "连板来源 day 日期无效") from exc
    flag = raw.get("series_limit_up")
    if _missing(flag):
        consecutive = None
    elif flag == "yes":
        consecutive = True
    elif flag == "no":
        consecutive = False
    else:
        _fail("连板来源 series_limit_up 必须是 yes/no 或空值")
    limit_time = _text(raw.get("limit_up_time"), "limit_up_time")
    if limit_time is not None and not _TIME.fullmatch(limit_time):
        _fail("连板来源 limit_up_time 必须是 HH:MM 或 HH:MM:SS")
    return {
        "date": day,
        "code": identity[2],
        "exchange": identity[1].lower(),
        "name": _text(raw.get("name"), "name"),
        "price": to_number(raw.get("last_price"), "price", source="aigupiao", nonnegative=True),
        "price_change": to_number(raw.get("chg"), "price_change", source="aigupiao"),
        "change_percent": to_number(raw.get("change_pct"), "change_percent", source="aigupiao"),
        "turnover_rate": to_number(raw.get("turnover_rate"), "turnover_rate", source="aigupiao", nonnegative=True),
        "amount": _amount(raw.get("amount"), "amount"),
        "market_cap": to_number(raw.get("whole"), "market_cap", source="aigupiao", scale=8, nonnegative=True),
        "float_shares": _count(raw.get("ltg"), "float_shares"),
        "total_shares": _count(raw.get("zgb"), "total_shares"),
        "limit_up_time": limit_time,
        "consecutive_limit_up_days": _count(raw.get("x_series_limit_up"), "consecutive_limit_up_days"),
        "is_consecutive_limit_up": consecutive,
        "state": _text(raw.get("state"), "state"),
        "previous_consecutive_limit_up_days": _count(raw.get("last_day_continuous_up_times"), "previous_consecutive_limit_up_days"),
        "theme_name": _text(raw.get("theme_name"), "theme_name"),
    }


def _parse_page(payload: Any) -> tuple[list, int]:
    if not isinstance(payload, dict):
        _fail("连板响应外层必须是对象")
    code = payload.get("code")
    if not (type(code) is int and code == 0 or isinstance(code, str) and code.strip() == "0") or payload.get("status") != "success":
        _fail("连板来源状态表示请求失败")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        _fail("连板响应缺少有效的 data/list")
    total = _count(data.get("total"), "total")
    if total is None:
        _fail("连板响应必须提供 total")
    return data["list"], total


def consecutive_limit_up(*, timeout: float) -> list[dict]:
    """读取来源最新交易日的完整连板列表，不替换日期或派生连板数。"""
    seconds = validate_timeout(timeout)
    rows: dict[tuple[str, str], dict] = {}
    expected_total = None
    expected_date = None
    for round_number in range(1, 4):
        page_number = 1
        offset = 0
        while expected_total is None or offset < expected_total:
            params = {
                "number": _PAGE_SIZE, "page": page_number, "type": "series_limit_up",
                "source": "pc", "st_stock": "n", "new_stock": "n",
                "sort_type": "limit_up_state", "sort_mode": "desc",
            }
            payload = get_json(f"{ENDPOINT}?{urlencode(params)}", timeout=seconds, headers=_HEADERS, source="aigupiao")
            page, total = _parse_page(payload)
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                _fail(f"第 {round_number} 轮连板分页 total 漂移：原为 {expected_total}，返回 {total}")
            wanted = min(_PAGE_SIZE, total - offset)
            if len(page) != wanted:
                _fail(f"第 {page_number} 页连板行数不完整或超出范围：应为 {wanted}，实际 {len(page)}")
            page_seen = set()
            for raw in page:
                row = _parse_row(raw)
                if expected_date is None:
                    expected_date = row["date"]
                elif row["date"] != expected_date:
                    _fail(f"连板来源交易日期不一致：原为 {expected_date}，返回 {row['date']}")
                identity = (row["exchange"], row["code"])
                if identity in page_seen:
                    _fail(f"第 {page_number} 页连板股票身份重复：{row['exchange']}{row['code']}")
                page_seen.add(identity)
                rows[identity] = row
            if len(rows) > expected_total:
                _fail(f"连板唯一股票数 {len(rows)} 超过来源 total={expected_total}")
            offset += len(page)
            page_number += 1
        if len(rows) == expected_total:
            return list(rows.values())
    _fail(f"连板完整性失败：最多 3 轮后，来源声明 {expected_total} 只股票，实际取得 {len(rows)} 只；未返回不完整数据")
