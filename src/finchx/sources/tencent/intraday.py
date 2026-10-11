"""腾讯股票与指数分时：保留来源日期和累计值，按相邻点求差。"""

from datetime import date
from decimal import Decimal, localcontext
import json
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import resolve_code, to_decimal, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

_DAY_URL = "https://web.ifzq.gtimg.cn/appstock/app/day/query"
_MINUTE_URL = "https://web.ifzq.gtimg.cn/appstock/app/minute/query"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://finance.qq.com/"}
_ASSIGNMENT = re.compile(r"\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(\{.*\})\s*;?\s*", re.S)
_DATE = re.compile(r"(?:[0-9]{8}|[0-9]{4}-[0-9]{2}-[0-9]{2})")
_TIME = re.compile(r"[0-9]{3,4}")
_INDEX_SYMBOLS = {"sh000001", "sz399001", "sz399006"}


def _fail(reason: str) -> None:
    raise SourceError("tencent", reason)


def _decode(text: str, variable: str) -> tuple[dict[str, Any], bool]:
    matched = _ASSIGNMENT.fullmatch(text)
    if matched is None or matched[1] != variable:
        _fail("分时响应缺少或不匹配预期的变量包装")
    try:
        document = json.loads(matched[2], parse_float=Decimal)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SourceError("tencent", "分时响应不是有效的 JSON") from exc
    if not isinstance(document, dict):
        _fail("分时响应外层结构无效")
    code = document.get("code")
    success = type(code) is int and code in {0, 200} or isinstance(code, str) and code in {"0", "200"}
    if "code" in document and not success:
        _fail("分时来源状态表示请求失败")
    return document, success


def _source_date(value: Any) -> str:
    text = str(value) if type(value) is int else value
    if not isinstance(text, str) or not _DATE.fullmatch(text):
        _fail("分时来源日期必须是 YYYYMMDD 或 YYYY-MM-DD")
    try:
        compact = text.replace("-", "")
        return date(int(compact[:4]), int(compact[4:6]), int(compact[6:])).isoformat()
    except ValueError as exc:
        raise SourceError("tencent", "分时来源日期无效") from exc


def _source_time(value: Any) -> str:
    text = str(value) if type(value) is int else value
    if not isinstance(text, str) or not _TIME.fullmatch(text):
        _fail("分时来源时间必须是 HHMM")
    text = text.zfill(4)
    hour, minute = int(text[:2]), int(text[2:])
    if hour > 23 or minute > 59:
        _fail("分时来源时间无效")
    return f"{hour:02d}:{minute:02d}"


def _difference(current: Decimal, previous: Decimal) -> Decimal:
    # 日累计额相减先保留十进制精度，避免浮点抵消误差。
    with localcontext() as context:
        context.prec = max(28, current.adjusted() - min(current.as_tuple().exponent, previous.as_tuple().exponent) + 2)
        return current - previous


def _parse_days(days: Any, *, explicit_success: bool, five_day: bool) -> list[dict]:
    if not isinstance(days, list):
        _fail("分时来源交易日列表结构无效")
    if not days and not explicit_success:
        _fail("分时来源缺少明确成功状态的空列表")
    dates: set[str] = set()
    points = []
    for day in days:
        if not isinstance(day, dict):
            _fail("分时来源交易日结构无效")
        day_date = _source_date(day.get("date"))
        if day_date in dates:
            _fail(f"分时来源交易日期重复：{day_date}")
        dates.add(day_date)
        raw_points = day.get("data")
        if not isinstance(raw_points, list) or not raw_points and not explicit_success:
            _fail(f"{day_date} 分时来源点列表结构无效")
        seen_times: set[str] = set()
        for raw in raw_points:
            cells = raw.split() if isinstance(raw, str) else raw
            if not isinstance(cells, list) or len(cells) != 4:
                _fail(f"{day_date} 分时来源点必须包含时间、价格、累计量和累计额")
            point_time = _source_time(cells[0])
            if point_time in seen_times:
                _fail(f"分时来源日期时间重复：{day_date} {point_time}")
            seen_times.add(point_time)
            context = f"{day_date} {point_time}"
            price = to_number(cells[1], context + " price", source="tencent", nonnegative=True)
            volume = to_number(cells[2], context + " cumulative_volume", source="tencent", scale=2, integer=True, nonnegative=True)
            amount = to_decimal(cells[3], context + " cumulative_amount", source="tencent")
            # 金额既需用于精确差分，也需验证能转换为有限业务浮点数。
            to_number(amount, context + " cumulative_amount", source="tencent", nonnegative=True)
            points.append((day_date, point_time, price, volume, amount))
    selected_dates = set(sorted(dates)[-5:] if five_day else sorted(dates)[-1:])
    result = []
    previous_date = None
    previous_volume = previous_amount = None
    known_volume = known_amount = None
    for day_date, point_time, price, volume, amount in sorted(points, key=lambda row: row[:2]):
        first = day_date != previous_date
        if first:
            previous_volume = previous_amount = known_volume = known_amount = None
        if volume is not None and known_volume is not None and volume < known_volume:
            _fail(f"{day_date} {point_time} 日累计成交量倒退")
        if amount is not None and known_amount is not None and amount < known_amount:
            _fail(f"{day_date} {point_time} 日累计成交额倒退")
        delta_volume = volume if first else None if volume is None or previous_volume is None else volume - previous_volume
        delta_amount = amount if first else None if amount is None or previous_amount is None else _difference(amount, previous_amount)
        if day_date in selected_dates:
            result.append({
                "date": day_date,
                "time": point_time,
                "price": price,
                "volume": delta_volume,
                "amount": to_number(delta_amount, "amount", source="tencent", nonnegative=True),
                "cumulative_volume": volume,
                "cumulative_amount": to_number(amount, "cumulative_amount", source="tencent", nonnegative=True),
            })
        previous_date, previous_volume, previous_amount = day_date, volume, amount
        if volume is not None:
            known_volume = volume
        if amount is not None:
            known_amount = amount
    return result


def _fetch(code: str, *, kind: str, five_day: bool, minute: bool, timeout: float) -> list[dict]:
    symbol = resolve_code(code, kind)
    if kind == "index" and symbol not in _INDEX_SYMBOLS:
        raise ValueError("指数分时仅支持 000001、399001、399006")
    seconds = validate_timeout(timeout)
    variable = f"min_data_{symbol}" if minute else f"fdays_data_{symbol}"
    endpoint = _MINUTE_URL if minute else _DAY_URL
    url = f"{endpoint}?{urlencode({'_var': variable, 'code': symbol})}"
    text = get_text(url, timeout=seconds, headers=_HEADERS, source="tencent")
    document, success = _decode(text, variable)
    data = document.get("data")
    if not isinstance(data, dict) or not isinstance(data.get(symbol), dict):
        _fail(f"分时来源未返回请求标的：{symbol}")
    series = data[symbol].get("data")
    if minute:
        if not isinstance(series, dict):
            _fail("指数分时来源单日结构无效")
        series = [series]
    return _parse_days(series, explicit_success=success, five_day=five_day)


def equity_intraday(code: str, *, timeout: float) -> list[dict]:
    """沪深股票最近一个来源交易日的分时点。"""
    return _fetch(code, kind="stock", five_day=False, minute=False, timeout=timeout)


def equity_intraday_5d(code: str, *, timeout: float) -> list[dict]:
    """沪深股票最近最多五个来源交易日的分时点。"""
    return _fetch(code, kind="stock", five_day=True, minute=False, timeout=timeout)


def index_intraday(code: str, *, timeout: float) -> list[dict]:
    """已支持指数最近一个来源交易日的分时点。"""
    return _fetch(code, kind="index", five_day=False, minute=True, timeout=timeout)


def index_intraday_5d(code: str, *, timeout: float) -> list[dict]:
    """已支持指数最近最多五个来源交易日的分时点。"""
    return _fetch(code, kind="index", five_day=True, minute=False, timeout=timeout)
