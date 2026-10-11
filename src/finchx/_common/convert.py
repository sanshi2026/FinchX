"""必要的日期类型规范化。"""

from datetime import date, datetime
from decimal import Decimal, DecimalException, localcontext
import math
import re
from typing import Any

from finchx._common.errors import SourceError

_DATE_PATTERN = re.compile(r"(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8}|[0-9]{4}/[0-9]{2}/[0-9]{2})")
_DATE_TIME_PATTERN = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8}|[0-9]{4}/[0-9]{2}/[0-9]{2})"
    r"(?: ([0-9]{2}):([0-9]{2}):([0-9]{2}))?"
)


def parse_date_time_string(value: str, name: str) -> date | datetime:
    """严格解析三种日期及其可选秒时刻，不接受时区或空白扩展。"""
    match = _DATE_TIME_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match:
        digits = match[1].replace("-", "").replace("/", "")
        try:
            day = date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
            if match[2] is None:
                return day
            return datetime(day.year, day.month, day.day, *(int(match[i]) for i in (2, 3, 4)))
        except ValueError:
            pass
    raise ValueError(
        f"{name} 必须是有效的 YYYY-MM-DD、YYYYMMDD、YYYY/MM/DD 日期字符串，"
        "或上述日期加空格 HH:MM:SS 的北京时间字符串"
    )


def parse_date_parameter(value: date | str, name: str, *, allow_date_object: bool = False) -> date:
    """按天入参完整验证时刻后取日期，保留原有日期对象支持边界。"""
    if allow_date_object and isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = parse_date_time_string(value, name)
    return parsed.date() if isinstance(parsed, datetime) else parsed


def parse_date(value: date | str, name: str) -> date:
    """接受日期或三种精确格式，不隐式截断时间或容忍空白。"""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and _DATE_PATTERN.fullmatch(value):
        digits = value.replace("-", "").replace("/", "")
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
        except ValueError:
            pass
    raise ValueError(f"{name} 必须是有效的 date 或 YYYY-MM-DD、YYYYMMDD、YYYY/MM/DD 日期字符串；不接受 datetime")


_CODE = re.compile(r"[0-9]{6}")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_INDEX_EXCHANGES = {
    "000001": "sh", "000002": "sh", "000688": "sh",
    "399001": "sz", "399006": "sz", "399102": "sz", "399107": "sz",
}


def resolve_code(code: str, kind: str = "stock") -> str:
    """将已确认支持的六位代码转换为腾讯的带交易所代码。"""
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise ValueError("code 必须是六位 ASCII 数字字符串")
    if not isinstance(kind, str) or kind not in {"stock", "index"}:
        raise ValueError("kind 必须是 stock 或 index")
    if kind == "index":
        exchange = _INDEX_EXCHANGES.get(code)
    elif code.startswith(("60", "68")):
        exchange = "sh"
    elif code.startswith(("00", "30")):
        exchange = "sz"
    else:
        exchange = None
    if exchange is None:
        raise ValueError(f"无法确定已支持的 {kind} 代码所属交易所：{code}")
    return exchange + code


def validate_timeout(timeout: float) -> float:
    """来源函数独立调用时也先验证每次请求的超时秒数。"""
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("timeout 必须是有限的正数（秒）")
    try:
        seconds = float(timeout)
    except OverflowError as exc:
        raise ValueError("timeout 必须是有限的正数（秒）") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("timeout 必须是有限的正数（秒）")
    return seconds


def to_decimal(value: Any, field: str, *, source: str) -> Decimal | None:
    """缺失转为空值，有限来源数字以十进制保留。"""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value in {"", "--", "-"}:
            return None
        if not _NUMBER.fullmatch(value):
            raise SourceError(source, f"字段 {field} 不是有效数字")
    elif isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise SourceError(source, f"字段 {field} 不是有效数字")
    try:
        number = Decimal(str(value))
    except (DecimalException, ValueError, OverflowError) as exc:
        raise SourceError(source, f"字段 {field} 无法读取数值") from exc
    if not number.is_finite():
        raise SourceError(source, f"字段 {field} 必须是有限数字")
    return number


def to_number(
    value: Any, field: str, *, source: str, scale: int = 0,
    integer: bool = False, nonnegative: bool = False,
) -> float | int | None:
    """精确完成单位换算后返回普通数字，不把缺失补成零。"""
    number = to_decimal(value, field, source=source)
    if number is None:
        return None
    if nonnegative and number < 0:
        raise SourceError(source, f"字段 {field} 不得为负数")
    try:
        with localcontext() as context:
            context.prec = max(28, len(number.as_tuple().digits) + max(scale, 0))
            number *= Decimal(10) ** scale
        if integer:
            if number != number.to_integral_value():
                raise SourceError(source, f"字段 {field} 无法转换为整数")
            return int(number)
        result = float(number)
    except (DecimalException, ValueError, OverflowError) as exc:
        raise SourceError(source, f"字段 {field} 无法进行数值转换") from exc
    if not math.isfinite(result):
        raise SourceError(source, f"字段 {field} 超出有限浮点数范围")
    return result
