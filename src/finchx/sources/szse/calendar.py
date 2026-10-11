"""深交所逐月日历，严格验证来源显式标记。"""

import calendar
from datetime import date
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx._common.errors import SourceError

ENDPOINT = "https://www.szse.cn/api/report/exchange/onepersistenthour/monthList"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://www.szse.cn/aboutus/calendar/"}
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _parse_month(payload: Any, year: int, month: int) -> dict[date, bool]:
    month_label = f"{year:04d}-{month:02d}"
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise SourceError("szse", f"{month_label} 响应缺少有效的 data 日历列表")
    rows: dict[date, bool] = {}
    for position, raw in enumerate(payload["data"]):
        if not isinstance(raw, dict):
            raise SourceError("szse", f"{month_label} 第 {position + 1} 行结构无效")
        text = raw.get("jyrq")
        if not isinstance(text, str) or not _ISO_DATE.fullmatch(text):
            raise SourceError("szse", f"{month_label} 第 {position + 1} 行 jyrq 日期无效")
        try:
            day = date.fromisoformat(text)
        except ValueError as exc:
            raise SourceError("szse", f"{month_label} 第 {position + 1} 行 jyrq 日期无效") from exc
        if (day.year, day.month) != (year, month):
            raise SourceError("szse", f"{month_label} 返回了其他月份的日期 {text}")
        if day in rows:
            raise SourceError("szse", f"{month_label} 日期重复：{text}")
        if not isinstance(raw.get("jybz"), str) or raw["jybz"] not in {"0", "1"}:
            raise SourceError("szse", f"{text} 的 jybz 必须是字符串 0 或 1")
        rows[day] = raw["jybz"] == "1"
    expected = {date(year, month, day) for day in range(1, calendar.monthrange(year, month)[1] + 1)}
    missing = expected - rows.keys()
    if missing:
        raise SourceError("szse", f"{month_label} 缺少 {len(missing)} 天日历，首个缺失日期为 {min(missing).isoformat()}")
    return rows


def trading_calendar(start: date, end: date, *, timeout: float) -> list[dict[str, str | bool]]:
    result: list[dict[str, str | bool]] = []
    year, month = start.year, start.month
    while True:
        url = f"{ENDPOINT}?{urlencode({'month': f'{year:04d}-{month:02d}'})}"
        payload = get_json(url, timeout=timeout, headers=_HEADERS, source="szse")
        rows = _parse_month(payload, year, month)
        for day, is_trading_day in sorted(rows.items()):
            if start <= day <= end:
                result.append({
                    "date": day.isoformat(),
                    "is_trading_day": is_trading_day,
                })
        # 在最后一个请求月份立即停止，避免 date.max 的年份溢出。
        if (year, month) == (end.year, end.month):
            break
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result
