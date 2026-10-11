"""使用库的真实 SSE 交易日期，扩展为每个自然日。"""

from datetime import date, datetime
from importlib import import_module

from finchx._common.errors import SourceError

SOURCE = "pandas_market_calendars"


def trading_calendar(start: date, end: date) -> list[dict[str, str | bool]]:
    try:
        mcal = import_module("pandas_market_calendars")
    except ImportError as exc:
        raise SourceError(SOURCE, "缺少可选日历依赖，请安装 finchx[calendar]") from exc
    except Exception as exc:
        raise SourceError(SOURCE, f"日历依赖加载失败（{type(exc).__name__}：{exc}）") from exc
    try:
        calendar = mcal.get_calendar("SSE")
        valid_days = calendar.valid_days(start_date=start.isoformat(), end_date=end.isoformat())
        sessions: set[date] = set()
        for session in valid_days:
            day = session.date()
            if not isinstance(day, date) or isinstance(day, datetime) or not start <= day <= end:
                raise ValueError("交易日期超出请求范围或结构无效")
            if day in sessions:
                raise ValueError("交易日期重复")
            sessions.add(day)
    except Exception as exc:
        raise SourceError(SOURCE, f"SSE 交易日期生成失败（{type(exc).__name__}：{exc}）") from exc
    result = []
    # 通过序数扩展自然日，不在最后一天再加 timedelta，支持 date.max。
    for ordinal in range(start.toordinal(), end.toordinal() + 1):
        day = date.fromordinal(ordinal)
        result.append({
            "date": day.isoformat(),
            "is_trading_day": day in sessions,
        })
    return result
