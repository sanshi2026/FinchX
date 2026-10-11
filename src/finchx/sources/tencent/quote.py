"""腾讯单标的行情与五档盘口，仅解析本接口使用的来源列。"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from finchx._common.convert import resolve_code, to_decimal, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

ENDPOINT = "https://qt.gtimg.cn"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://finance.qq.com/"}
_ASSIGNMENT = re.compile(r'\s*v_((?:sh|sz|bj)[0-9]{6})="([^"\r\n]*)";?\s*')
_TIME = re.compile(r"[0-9]{14}")
_SHANGHAI = timezone(timedelta(hours=8))


def _fields(symbol: str, *, timeout: float, minimum: int) -> list[str]:
    text = get_text(
        f"{ENDPOINT}/q={symbol}", timeout=timeout, headers=_HEADERS,
        source="tencent", encoding="gbk",
    )
    matched = _ASSIGNMENT.fullmatch(text)
    if matched is None:
        raise SourceError("tencent", "行情响应不是有效的单标的赋值文本")
    if matched[1] != symbol:
        raise SourceError("tencent", "行情响应代码与请求身份不一致")
    fields = matched[2].split("~")
    if len(fields) < minimum:
        raise SourceError("tencent", f"行情响应结构不完整：需要至少 {minimum} 列")
    if fields[2] != symbol[2:]:
        raise SourceError("tencent", "行情内容的代码与请求身份不一致")
    return fields


def _identity(symbol: str, fields: list[str]) -> dict[str, Any]:
    text = fields[30].strip()
    if text in {"", "--", "-"}:
        source_time = None
    else:
        if not _TIME.fullmatch(text):
            raise SourceError("tencent", "行情来源时间不是 YYYYMMDDHHMMSS")
        try:
            source_time = datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=_SHANGHAI).isoformat()
        except ValueError as exc:
            raise SourceError("tencent", "行情来源时间不是有效日期时间") from exc
    return {"code": symbol[2:], "exchange": symbol[:2], "name": fields[1] or None, "time": source_time}


def quote_snapshot(code: str, *, kind: str = "stock", timeout: float) -> dict[str, Any]:
    """读取股票或已验证指数的实时行情；金额元、成交量股。"""
    symbol = resolve_code(code, kind)
    seconds = validate_timeout(timeout)
    fields = _fields(symbol, timeout=seconds, minimum=58)
    row = _identity(symbol, fields)
    for field, index in {
        "price": 3, "previous_close": 4, "open": 5, "high": 33, "low": 34,
        "price_change": 31, "change_percent": 32,
    }.items():
        row[field] = to_number(fields[index], field, source="tencent", nonnegative=field not in {"price_change", "change_percent"})
    volume = to_decimal(fields[6], "volume", source="tencent")
    duplicate = to_decimal(fields[36], "duplicate_volume", source="tencent")
    if volume is not None and duplicate is not None and volume != duplicate:
        raise SourceError("tencent", "行情两处成交量不一致")
    row["volume"] = to_number(volume if volume is not None else duplicate, "volume", source="tencent", scale=2, integer=True, nonnegative=True)
    row["amount"] = to_number(fields[57], "amount", source="tencent", scale=4, nonnegative=True)
    return row


def orderbook(code: str, *, timeout: float) -> dict[str, Any]:
    """保留来源买卖各五档，包括零档位和缺失值。"""
    symbol = resolve_code(code, "stock")
    seconds = validate_timeout(timeout)
    fields = _fields(symbol, timeout=seconds, minimum=31)
    row = _identity(symbol, fields)
    for side, start in (("bids", 9), ("asks", 19)):
        levels = []
        for level in range(1, 6):
            index = start + (level - 1) * 2
            levels.append({
                "level": level,
                "price": to_number(fields[index], f"{side}{level}.price", source="tencent", nonnegative=True),
                "volume": to_number(fields[index + 1], f"{side}{level}.volume", source="tencent", scale=2, integer=True, nonnegative=True),
            })
        row[side] = levels
    return row
