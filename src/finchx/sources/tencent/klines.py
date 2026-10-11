"""腾讯日 K 线，按结束日期向前取完请求区间。"""

from datetime import date, timedelta
from decimal import Decimal
import json
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import parse_date_parameter, resolve_code, to_decimal, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

ENDPOINT = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://finance.qq.com/"}
_PAGE_SIZE = 800
_SERIES = {None: ("kline_day", "day", "none"), "qfq": ("kline_dayqfq", "qfqday", "qfq"), "hfq": ("kline_dayhfq", "hfqday", "hfq")}
_ASSIGNMENT = re.compile(r"\s*([A-Za-z_$][\w$]*)\s*=\s*(.*?)\s*;?\s*", re.DOTALL)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _reject_constant(value: str) -> None:
    raise ValueError(f"非法 JSON 数字 {value}")


def _page(text: str, symbol: str, variable: str, series: str) -> list[Any]:
    value = text.strip()
    matched = _ASSIGNMENT.fullmatch(value)
    if matched is not None:
        if matched[1] != variable:
            raise SourceError("tencent", "日 K 线响应变量与请求不一致")
        value = matched[2]
    elif not value.startswith("{"):
        raise SourceError("tencent", "日 K 线响应不是预期赋值文本或 JSON")
    try:
        document = json.loads(value, parse_float=Decimal, parse_constant=_reject_constant)
    except (ValueError, TypeError) as exc:
        raise SourceError("tencent", "日 K 线响应不是有效 JSON") from exc
    if not isinstance(document, dict):
        raise SourceError("tencent", "日 K 线响应外层结构无效")
    status = document.get("code")
    if isinstance(status, bool) or status not in (0, 200, "0", "200"):
        raise SourceError("tencent", "日 K 线来源状态失败或缺失")
    data = document.get("data")
    if not isinstance(data, dict) or not isinstance(data.get(symbol), dict):
        raise SourceError("tencent", "日 K 线响应缺少请求标的身份")
    rows = data[symbol].get(series)
    if not isinstance(rows, list):
        raise SourceError("tencent", f"日 K 线缺少有效的 {series} 序列；不替换为其他复权序列")
    return rows


def _bar(raw: Any) -> tuple[date, dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) < 6:
        raise SourceError("tencent", "日 K 线行结构无效，需要日期与五项基本行情")
    if not isinstance(raw[0], str) or not _DATE.fullmatch(raw[0]):
        raise SourceError("tencent", "日 K 线日期格式无效")
    try:
        day = date.fromisoformat(raw[0])
    except ValueError as exc:
        raise SourceError("tencent", "日 K 线日期无效") from exc
    values = {field: to_decimal(raw[index], field, source="tencent") for field, index in {"open": 1, "close": 2, "high": 3, "low": 4}.items()}
    for field, value in values.items():
        if value is not None and value < 0:
            raise SourceError("tencent", f"日 K 线 {field} 不得为负数")
    high, low = values["high"], values["low"]
    if high is not None and any(value is not None and value > high for value in values.values()):
        raise SourceError("tencent", "日 K 线最高价小于其他有效价格")
    if low is not None and any(value is not None and value < low for value in values.values()):
        raise SourceError("tencent", "日 K 线最低价大于其他有效价格")
    return day, {
        "date": day.isoformat(),
        "open": to_number(values["open"], "open", source="tencent"),
        "high": to_number(high, "high", source="tencent"),
        "low": to_number(low, "low", source="tencent"),
        "close": to_number(values["close"], "close", source="tencent"),
        "volume": to_number(raw[5], "volume", source="tencent", scale=2, integer=True, nonnegative=True),
        "amount": to_number(raw[8] if len(raw) > 8 else None, "amount", source="tencent", scale=4, nonnegative=True),
    }


def ohlcv(
    code: str, start_date: date | str, end_date: date | str, adjustment: str | None = None,
    *, kind: str = "stock", timeout: float,
) -> list[dict[str, Any]]:
    """返回首尾包含的日 K 线；不足一页或空页表示来源已耗尽。"""
    symbol = resolve_code(code, kind)
    start = parse_date_parameter(start_date, "start_date", allow_date_object=True)
    end = parse_date_parameter(end_date, "end_date", allow_date_object=True)
    if start > end:
        raise ValueError("start_date 不得晚于 end_date")
    if adjustment is not None and (not isinstance(adjustment, str) or adjustment not in {"qfq", "hfq"}):
        raise ValueError("adjustment 必须是 None、qfq 或 hfq")
    if kind == "index" and adjustment is not None:
        raise ValueError("指数日 K 线 adjustment 必须为 None")
    seconds = validate_timeout(timeout)
    variable, series, mode = _SERIES[adjustment]
    cursor = end
    collected: dict[date, dict[str, Any]] = {}
    seen: set[date] = set()
    while True:
        params = {"_var": variable, "param": f"{symbol},day,,{cursor.isoformat()},{_PAGE_SIZE},{mode}"}
        text = get_text(f"{ENDPOINT}?{urlencode(params)}", timeout=seconds, headers=_HEADERS, source="tencent")
        page = _page(text, symbol, variable, series)
        if not page:
            break
        dates = []
        for raw in page:
            day, row = _bar(raw)
            if day > cursor:
                raise SourceError("tencent", "日 K 线返回了请求结束日期之后的日期")
            if day in seen:
                raise SourceError("tencent", f"日 K 线日期重复：{day.isoformat()}")
            seen.add(day)
            dates.append(day)
            if start <= day <= end:
                collected[day] = row
        earliest = min(dates)
        if earliest <= start or len(page) < _PAGE_SIZE:
            break
        next_end = earliest - timedelta(days=1)
        if next_end >= cursor:
            raise SourceError("tencent", "日 K 线分页日期没有向前推进")
        cursor = next_end
    return [collected[day] for day in sorted(collected)]
