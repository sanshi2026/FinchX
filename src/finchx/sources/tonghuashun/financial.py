"""同花顺一种财务报表的实际报告期与完整业务科目。"""

from datetime import date
from decimal import Decimal
import json
import re

from finchx._common.convert import parse_date_parameter, resolve_code, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

SOURCE = "tonghuashun.financial"
ENDPOINT = "https://basic.10jqka.com.cn/api/stock/finance/{}_{}.json"
_STATEMENTS = {
    "balance_sheet": "debt",
    "income_statement": "benefit",
    "cash_flow_statement": "cash",
}
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_VALUE = re.compile(
    r"([+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|"
    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?))(万亿|亿|万)?(元)?"
)
_MISSING = {"", "--", "-", "—", "－", "N/A", "n/a"}
_AMOUNT_UNITS = {"元": 0, "万元": 4, "亿元": 8, "万亿元": 12}
_GROUP_TITLES = {
    "流动资产", "非流动资产", "流动负债", "非流动负债", "资产", "负债",
    "所有者权益（或股东权益）", "所有者权益（或股东权益", "六、每股收益",
    "一、经营活动产生的现金流量", "二、投资活动产生的现金流量",
    "三、筹资活动产生的现金流量", "补充资料：",
    "1、将净利润调节为经营活动现金流量：",
    "2、不涉及现金收支的重大投资和筹资活动：",
    "3、现金及现金等价物净变动情况：",
}


def _fail(reason: str) -> None:
    raise SourceError(SOURCE, reason)


def _date_text(value: object, field: str, *, argument: bool = False) -> str:
    if argument:
        return parse_date_parameter(value, field).isoformat()
    if isinstance(value, str) and _DATE.fullmatch(value):
        try:
            date.fromisoformat(value)
        except ValueError:
            pass
        else:
            return value
    _fail(f"{field} 必须是有效的 ISO 日期字符串")


def _reject_constant(value: str) -> None:
    _fail(f"JSON 数值 {value} 不是有限数字")


def _json(text: object, field: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        _fail(f"{field} 必须是非空 JSON 文本")
    try:
        result = json.loads(text, parse_float=Decimal, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise SourceError(SOURCE, f"{field} 不是有效 JSON") from exc
    if not isinstance(result, dict):
        _fail(f"{field} 必须是 JSON 对象")
    return result


def _unit(value: object, field: str) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str):
        _fail(f"{field} 必须是单位文本或空值")
    unit = value.strip()
    if not unit:
        return None, 0
    if unit not in _AMOUNT_UNITS:
        _fail(f"{field} 不是已确认的财务报表金额单位")
    return "元", _AMOUNT_UNITS[unit]


def _value(raw: object, field: str, bare_scale: int) -> float | None:
    if raw is False or raw is None:
        return None
    scale = bare_scale
    if isinstance(raw, str):
        raw = raw.strip()
        if raw in _MISSING:
            return None
        match = _VALUE.fullmatch(raw)
        if match is None:
            _fail(f"{field} 不是有效财务报表数值")
        magnitude, suffix = match.group(2), match.group(3)
        if magnitude is not None or suffix is not None:
            scale = {None: 0, "万": 4, "亿": 8, "万亿": 12}[magnitude]
        raw = match.group(1).replace(",", "")
    return to_number(raw, field, source=SOURCE, scale=scale)


def _parse(text: str) -> list[dict]:
    payload = _json(text, "财务报表响应")
    if "code" in payload:
        status = payload["code"]
        if not (type(status) is int and status == 0 or isinstance(status, str) and status == "0"):
            _fail("财务报表来源 code 表示请求失败")
    data = _json(payload.get("flashData"), "flashData")
    title, report = data.get("title"), data.get("report")
    if not isinstance(title, list) or not isinstance(report, list) or len(title) < 2 or len(title) != len(report):
        _fail("flashData.title/report 必须是行数相同的非空矩阵")
    if not isinstance(title[0], str) or not title[0].strip():
        _fail("flashData.title[0] 必须是科目标题文本")
    if not isinstance(report[0], list) or not report[0]:
        _fail("flashData.report[0] 必须是非空报告期列表")
    periods = [_date_text(value, f"flashData.report[0][{index}]")
               for index, value in enumerate(report[0])]
    if len(set(periods)) != len(periods):
        _fail("财务报表存在重复报告期")
    names = []
    for index in range(1, len(title)):
        row = title[index]
        if not isinstance(row, list) or not row or not isinstance(row[0], str) or not row[0].strip():
            _fail(f"flashData.title[{index}] 必须提供非空科目名称")
        names.append(row[0].strip())
    for index, row in enumerate(report):
        if not isinstance(row, list) or len(row) != len(periods):
            _fail(f"flashData.report[{index}] 与报告期列数不一致")
    starts = [index + 1 for index, name in enumerate(names) if name == "报表全部指标"]
    if len(starts) != 1:
        _fail("财务报表缺少唯一的报表全部指标分区")
    start = starts[0]
    if any(value != "" for value in report[start]):
        _fail("报表全部指标分区标题包含数值，来源结构异常")
    core = [index + 1 for index, name in enumerate(names) if name == "报表核心指标"]
    if start == 1 and core:
        _fail("核心摘要分区不能位于报表全部指标之后")
    if start > 1:
        if core != [1] or any(value != "" for value in report[1]):
            _fail("报表全部指标之前缺少明确的唯一核心摘要分区")
        if any(not name.startswith("*") or not name[1:].strip() for name in names[1:start - 1]):
            _fail("核心摘要分区含有不属于星号摘要的科目")
    # 分区之前是来源重复核心摘要；不根据科目同名、星号或数值相等去重。
    items_by_period = [[] for _ in periods]
    for index in range(start + 1, len(title)):
        name = names[index - 1]
        values = report[index]
        # 粗体和可点击曲线标记属于显示用途，不能用于筛掉业务科目。
        if name in _GROUP_TITLES and all(value == "" for value in values):
            continue
        unit, scale = _unit(title[index][1] if len(title[index]) > 1 else None,
                            f"flashData.title[{index}].unit")
        for column, raw in enumerate(values):
            items_by_period[column].append({
                "name": name, "unit": unit,
                "value": _value(raw, f"flashData.report[{index}][{column}]", scale),
            })
    if not items_by_period[0]:
        _fail("报表全部指标分区没有业务科目")
    return sorted(({"period_end": period, "items": items_by_period[column]}
                   for column, period in enumerate(periods)),
                  key=lambda row: row["period_end"], reverse=True)


def statements(code: str, statement: str, period_end: str | None = None,
               max_periods: int | None = None, *, timeout: float) -> list[dict]:
    """一次读取选定报表，按真实报告期降序返回完整业务科目。"""
    resolve_code(code, kind="stock")
    if not isinstance(statement, str) or statement not in _STATEMENTS:
        raise ValueError("statement 必须是 balance_sheet、income_statement 或 cash_flow_statement")
    if period_end is not None:
        period_end = _date_text(period_end, "period_end", argument=True)
    if max_periods is not None and (type(max_periods) is not int or max_periods <= 0):
        raise ValueError("max_periods 必须是非布尔正整数或 None")
    seconds = validate_timeout(timeout)
    headers = {
        **DEFAULT_HEADERS, "Referer": f"https://basic.10jqka.com.cn/{code}/finance.html",
        "X-Requested-With": "XMLHttpRequest",
    }
    rows = _parse(get_text(ENDPOINT.format(code, _STATEMENTS[statement]),
                           timeout=seconds, headers=headers, source=SOURCE))
    if period_end is not None:
        rows = [row for row in rows if row["period_end"] == period_end]
        if not rows:
            raise ValueError(f"来源未提供 period_end={period_end} 的财务报表")
    return rows if max_periods is None else rows[:max_periods]
