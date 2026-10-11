"""爱股票龙虎榜事件与营业部席位；每次调用读取一份来源响应。"""

import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import parse_date_parameter, resolve_code, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json

_BASE = "https://app.aigupiao.com/goapi/dragon_tiger/"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://www.aigupiao.com/"}
_SOURCE = "aigupiao"
_IDENTITY = re.compile(r"(sh|sz|bj)([0-9]{6})")
_DIGITS = re.compile(r"[0-9]+")
_NUMBERS = {
    "close_price": "close_price", "change_percent": "change_rate",
    "amount": "accum_amount", "total_buy": "total_buy", "total_net": "total_net",
}


def _date(value: str) -> str:
    return parse_date_parameter(value, "date").isoformat()


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None or isinstance(value, str) and not value.strip():
        if not required:
            return None
    elif isinstance(value, str):
        return value
    raise SourceError(_SOURCE, f"字段 {field} 必须是{'非空' if required else ''}字符串")


def _integer(value: Any, field: str, *, required: bool = False) -> int | None:
    if value is None or isinstance(value, str) and value.strip() in {"", "--", "-"}:
        if not required:
            return None
    elif type(value) is int and value >= 0:
        return value
    elif isinstance(value, str) and _DIGITS.fullmatch(value):
        try:
            return int(value)
        except ValueError:
            pass
    raise SourceError(_SOURCE, f"字段 {field} 必须是非负整数{'或空值' if not required else ''}")


def _identity(value: Any) -> tuple[str, str]:
    matched = _IDENTITY.fullmatch(value) if isinstance(value, str) else None
    if matched is None:
        raise SourceError(_SOURCE, "字段 code 必须明确包含 sh、sz 或 bj 与六位 ASCII 证券代码")
    return matched[2], matched[1]


def _status(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise SourceError(_SOURCE, "龙虎榜响应外层结构无效")
    code = payload.get("code")
    if not (type(code) is int and code == 1 or isinstance(code, str) and code == "1"):
        raise SourceError(_SOURCE, "龙虎榜来源状态表示请求失败")
    return payload


def _summary(raw: dict) -> dict:
    code, exchange = _identity(raw.get("code"))
    result = {"code": code, "exchange": exchange, "name": _text(raw.get("name"), "name", required=True)}
    for field, key in _NUMBERS.items():
        result[field] = to_number(raw.get(key), key, source=_SOURCE,
                                  nonnegative=field in {"close_price", "amount", "total_buy"})
    result["explanation"] = _text(raw.get("explanation"), "explanation", required=True)
    return result


def dragon_tiger_list(date: str, *, timeout: float) -> list[dict]:
    """读取精确日期来源提供的完整事件列表，count 核对唯一证券数。"""
    day, seconds = _date(date), validate_timeout(timeout)
    url = _BASE + "lists?" + urlencode({"day": day, "source": "pc"})
    payload = _status(get_json(url, timeout=seconds, headers=_HEADERS, source=_SOURCE))
    count = _integer(payload.get("count"), "count", required=True)
    data = payload.get("data")
    if not isinstance(data, list):
        raise SourceError(_SOURCE, "龙虎榜列表 data 必须是数组")
    rows, identities, securities = [], set(), set()
    for raw in data:
        if not isinstance(raw, dict):
            raise SourceError(_SOURCE, "龙虎榜列表事件结构无效")
        row = _summary(raw)
        trade_id = raw.get("trade_id")
        if not isinstance(trade_id, str) or not _DIGITS.fullmatch(trade_id):
            raise SourceError(_SOURCE, "字段 trade_id 必须是非空 ASCII 数字字符串")
        identity = (row["exchange"], row["code"], trade_id)
        if identity in identities:
            raise SourceError(_SOURCE, "龙虎榜事件 code、exchange、trade_id 重复")
        identities.add(identity)
        securities.add(identity[:2])
        row["trade_id"] = trade_id
        row["period_label"] = _text(raw.get("three_day_flag"), "three_day_flag")
        row["theme_id"] = _integer(raw.get("theme_id"), "theme_id")
        row["theme_name"] = _text(raw.get("theme_name"), "theme_name")
        rows.append(row)
    if len(securities) != count:
        raise SourceError(_SOURCE, "龙虎榜列表唯一证券数与来源 count 不符")
    return sorted(rows, key=lambda row: (row["code"], row["exchange"], row["trade_id"]))


def _seats(raw: Any, field: str) -> list[dict]:
    if not isinstance(raw, list):
        raise SourceError(_SOURCE, f"字段 {field} 必须是营业部席位数组")
    rows = []
    for seat in raw:
        if not isinstance(seat, dict):
            raise SourceError(_SOURCE, f"字段 {field} 的席位结构无效")
        rows.append({
            "seat_name": _text(seat.get("name"), f"{field}.name", required=True),
            "seat_code": _text(seat.get("code"), f"{field}.code"),
            "buy_amount": to_number(seat.get("buy"), f"{field}.buy", source=_SOURCE, nonnegative=True),
            "sell_amount": to_number(seat.get("sell"), f"{field}.sell", source=_SOURCE, nonnegative=True),
            "net_amount": to_number(seat.get("net"), f"{field}.net", source=_SOURCE),
        })
    return rows


def dragon_tiger_detail(code: str, date: str, trade_id: str, *, timeout: float) -> dict:
    """以已核市场映射直达事件详情，不额外请求列表或行情。"""
    symbol, day, seconds = resolve_code(code), _date(date), validate_timeout(timeout)
    if not isinstance(trade_id, str) or not _DIGITS.fullmatch(trade_id):
        raise ValueError("trade_id 必须是非空 ASCII 数字字符串")
    url = _BASE + "deal_detail?" + urlencode({"day": day, "code": symbol, "trade_id": trade_id})
    payload = _status(get_json(url, timeout=seconds, headers=_HEADERS, source=_SOURCE))
    data = payload.get("data")
    if data == []:
        raise SourceError(_SOURCE, "来源没有与 code、date、trade_id 对应的龙虎榜详情")
    if not isinstance(data, dict):
        raise SourceError(_SOURCE, "龙虎榜详情 data 必须是对象")
    if data.get("code") != symbol:
        raise SourceError(_SOURCE, "龙虎榜详情 code 与请求的完整证券身份不符")
    result = _summary(data)
    result["total_sell"] = to_number(data.get("total_sell"), "total_sell", source=_SOURCE, nonnegative=True)
    result["buy_seats"] = _seats(data.get("buy_fives"), "buy_fives")
    result["sell_seats"] = _seats(data.get("sell_fives"), "sell_fives")
    return result
