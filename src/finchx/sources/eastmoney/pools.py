"""东方财富最新涨跌停相关池，完整取数后直接返回业务字段。"""

from datetime import date
import json
import re
import time
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

_BASE_URL = "https://push2ex.eastmoney.com/"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://quote.eastmoney.com/ztb/detail"}
_JSONP = re.compile(r"\s*finchxEastmoney\s*\((.*)\)\s*;?\s*", re.S)
_INTEGER = re.compile(r"[0-9]+")
_PAGE_SIZE = 1000
_ENDPOINTS = {
    "limit_up_pool": "getTopicZTPool",
    "limit_down_pool": "getTopicDTPool",
    "broken_limit_pool": "getTopicZBPool",
    "yesterday_limit_up_pool": "getYesterdayZTPool",
    "strong_pool": "getTopicQSPool",
}
_REASONS = {1: "60日新高", 2: "近期多次涨停", 3: "60日新高且近期多次涨停"}


def _missing(value: Any) -> bool:
    return value is None or isinstance(value, str) and value.strip() in {"", "--", "-"}


def _integer(value: Any, field: str, *, optional: bool = False) -> int | None:
    if optional and _missing(value):
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and _INTEGER.fullmatch(value.strip()):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise SourceError("eastmoney", f"字段 {field} 无法读取整数") from exc
    raise SourceError("eastmoney", f"字段 {field} 必须是非负整数")


def _date(value: Any) -> date:
    text = str(value) if type(value) is int else value
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]{8}", text):
        raise SourceError("eastmoney", "qdate 必须是来源提供的有效 YYYYMMDD 日期")
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError as exc:
        raise SourceError("eastmoney", "qdate 必须是来源提供的有效 YYYYMMDD 日期") from exc


def _request(endpoint: str, *, timeout: float, **params: Any) -> dict:
    query = {"cb": "finchxEastmoney", "ut": "7eea3edcaed734bea9cbfc24409ed989",
             "dpt": "wz.ztzt", "_": int(time.time() * 1000), **params}
    text = get_text(f"{_BASE_URL}{endpoint}?{urlencode(query)}", timeout=timeout,
                    headers=_HEADERS, source="eastmoney")
    matched = _JSONP.fullmatch(text)
    if matched is None:
        raise SourceError("eastmoney", "响应不是预期的 finchxEastmoney JSONP")
    try:
        payload = json.loads(matched[1])
    except (json.JSONDecodeError, ValueError) as exc:
        raise SourceError("eastmoney", "响应不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise SourceError("eastmoney", "响应外层结构无效")
    if _integer(payload.get("rc"), "rc") != 0:
        raise SourceError("eastmoney", "来源 rc 表示请求失败")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SourceError("eastmoney", "响应缺少有效的 data 对象")
    return data


def _text(value: Any, field: str) -> str | None:
    if _missing(value):
        return None
    if not isinstance(value, str):
        raise SourceError("eastmoney", f"字段 {field} 必须是字符串或空值")
    return value


def _time(value: Any, field: str) -> str | None:
    number = _integer(value, field, optional=True)
    if number is None or number == 0:
        return None
    hour, minute, second = number // 10000, number // 100 % 100, number % 100
    if hour > 23 or minute > 59 or second > 59:
        raise SourceError("eastmoney", f"字段 {field} 必须是有效 HHMMSS 时间")
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _identity(raw: dict) -> tuple[str, str]:
    code = raw.get("c")
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
        raise SourceError("eastmoney", "股票 c 必须是六位 ASCII 数字字符串")
    if code.startswith(("60", "68")):
        exchange, market = "sh", 1
    elif code.startswith(("00", "30")):
        exchange, market = "sz", 0
    elif code.startswith(("43", "83", "87", "88", "92")):
        exchange, market = "bj", 0
    else:
        raise SourceError("eastmoney", f"无法确定股票 {code} 所属交易所")
    if _integer(raw.get("m"), "m") != market:
        raise SourceError("eastmoney", f"股票 {code} 的代码与 m 市场标记矛盾")
    return exchange, code


def _stats(raw: dict) -> dict[str, int | None]:
    stats = raw.get("zttj")
    if _missing(stats):
        days, count = None, None
    elif isinstance(stats, dict):
        days = _integer(stats.get("days"), "zttj.days", optional=True)
        count = _integer(stats.get("ct"), "zttj.ct", optional=True)
    else:
        raise SourceError("eastmoney", "zttj 必须是有效的统计对象或空值")
    return {"limit_up_stats_days": days, "limit_up_stats_count": count}


def _row(raw: dict, day: date, pool: str) -> dict:
    exchange, code = _identity(raw)

    def number(key: str, *, scale: int = 0, nonnegative: bool = False):
        return to_number(raw.get(key), key, source="eastmoney", scale=scale, nonnegative=nonnegative)

    result = {
        "date": day.isoformat(), "code": code, "exchange": exchange,
        "name": _text(raw.get("n"), "n"), "price": number("p", scale=-3, nonnegative=True),
        "change_percent": number("zdp"), "amount": number("amount", nonnegative=True),
        "float_market_cap": number("ltsz", nonnegative=True), "market_cap": number("tshare", nonnegative=True),
        "turnover_rate": number("hs", nonnegative=True), "industry": _text(raw.get("hybk"), "hybk"),
    }
    if pool == "limit_down_pool":
        result.update({
            "pe": number("pe"), "limit_down_queue_amount": number("fund", nonnegative=True),
            "last_limit_down_time": _time(raw.get("lbt"), "lbt"),
            "board_traded_amount": number("fba", nonnegative=True),
            "consecutive_limit_down_days": _integer(raw.get("days"), "days", optional=True),
            "limit_down_open_count": _integer(raw.get("oc"), "oc", optional=True),
        })
        return result
    result.update(_stats(raw))
    if pool == "limit_up_pool":
        result.update({
            "consecutive_limit_up_days": _integer(raw.get("lbc"), "lbc", optional=True),
            "first_limit_up_time": _time(raw.get("fbt"), "fbt"),
            "last_limit_up_time": _time(raw.get("lbt"), "lbt"),
            "limit_up_queue_amount": number("fund", nonnegative=True),
            "limit_up_break_count": _integer(raw.get("zbc"), "zbc", optional=True),
        })
    else:
        result["limit_up_price"] = number("ztp", scale=-3, nonnegative=True)
        result["change_speed_percent"] = number("zs")
        if pool == "broken_limit_pool":
            result.update({"amplitude": number("zf", nonnegative=True),
                           "first_limit_up_time": _time(raw.get("fbt"), "fbt"),
                           "limit_up_break_count": _integer(raw.get("zbc"), "zbc", optional=True)})
        elif pool == "yesterday_limit_up_pool":
            result.update({"amplitude": number("zf", nonnegative=True),
                           "yesterday_first_limit_up_time": _time(raw.get("yfbt"), "yfbt"),
                           "yesterday_consecutive_limit_up_days": _integer(raw.get("ylbc"), "ylbc", optional=True)})
        else:
            high = _integer(raw.get("nh"), "nh", optional=True)
            reason = _integer(raw.get("cc"), "cc", optional=True)
            if high not in {None, 0, 1}:
                raise SourceError("eastmoney", "nh 必须是 0、1 或空值")
            if reason is not None and reason not in _REASONS:
                raise SourceError("eastmoney", "cc 必须是已确认的 1、2、3 或空值")
            result.update({"is_sixty_day_high": None if high is None else bool(high),
                           "selection_reason": None if reason is None else _REASONS[reason],
                           "volume_ratio": number("lb", nonnegative=True)})
    return result


def _pool(pool: str, *, timeout: float) -> list[dict]:
    timeout = validate_timeout(timeout)
    day = _date(_request("getTopicZDFenBu", timeout=timeout).get("qdate"))
    date_param = f"{day.year:04d}{day.month:02d}{day.day:02d}"
    target: int | None = None
    rows: dict[tuple[str, str], dict] = {}
    for order in ("c:asc", "c:desc", "c:asc"):
        page_index, received = 0, 0
        while target is None or received < target:
            data = _request(_ENDPOINTS[pool], timeout=timeout, date=date_param,
                            Pageindex=page_index, pagesize=_PAGE_SIZE, sort=order)
            total = _integer(data.get("tc"), "tc")
            if target is None:
                target = total
            elif total != target:
                raise SourceError("eastmoney", f"{pool} 分页 tc 漂移：{target} -> {total}")
            if _date(data.get("qdate")) != day:
                raise SourceError("eastmoney", f"{pool} 分页 qdate 与最新来源日期不一致")
            raw_rows = data.get("pool")
            if not isinstance(raw_rows, list):
                raise SourceError("eastmoney", f"{pool} 缺少有效 pool 列表")
            expected = min(_PAGE_SIZE, target - received)
            if len(raw_rows) != expected:
                raise SourceError("eastmoney", f"{pool} 页长度不完整：预期 {expected}，实际 {len(raw_rows)}")
            seen: set[tuple[str, str]] = set()
            for raw in raw_rows:
                if not isinstance(raw, dict):
                    raise SourceError("eastmoney", f"{pool} 股票行必须是对象")
                row = _row(raw, day, pool)
                identity = row["exchange"], row["code"]
                if identity in seen:
                    raise SourceError("eastmoney", f"{pool} 同页重复股票：{identity[0]}{identity[1]}")
                seen.add(identity)
                rows[identity] = row
            if len(rows) > target:
                raise SourceError("eastmoney", f"{pool} 唯一股票数超过来源 tc={target}")
            received += len(raw_rows)
            page_index += 1
            if len(rows) == target:
                return sorted(rows.values(), key=lambda row: (row["code"], row["exchange"]))
    raise SourceError("eastmoney", f"{pool} 三轮补取仍不完整：来源 tc={target}，实际唯一股票 {len(rows)}")


def limit_up_pool(*, timeout: float) -> list[dict]:
    """读取最新涨停池。"""
    return _pool("limit_up_pool", timeout=timeout)


def limit_down_pool(*, timeout: float) -> list[dict]:
    """读取最新跌停池。"""
    return _pool("limit_down_pool", timeout=timeout)


def broken_limit_pool(*, timeout: float) -> list[dict]:
    """读取最新炸板池。"""
    return _pool("broken_limit_pool", timeout=timeout)


def yesterday_limit_up_pool(*, timeout: float) -> list[dict]:
    """读取最新观察日期的昨日涨停池。"""
    return _pool("yesterday_limit_up_pool", timeout=timeout)


def strong_pool(*, timeout: float) -> list[dict]:
    """读取最新强势股池。"""
    return _pool("strong_pool", timeout=timeout)
