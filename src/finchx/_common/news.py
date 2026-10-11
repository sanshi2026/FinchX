"""新闻接口必要的数量与北京时间范围校验。"""

from datetime import datetime, time, timedelta, timezone
from finchx._common.convert import parse_date_time_string


BEIJING_TZ = timezone(timedelta(hours=8))


def validate_limit(limit: int) -> int:
    """新闻数量仅接受非布尔正整数，不设来源之外的数量上限。"""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit 必须是非布尔正整数")
    return limit


def _bound(value: str | None, name: str, *, upper: bool) -> datetime | None:
    if value is None:
        return None
    parsed = parse_date_time_string(value, name)
    if isinstance(parsed, datetime):
        return parsed.replace(tzinfo=BEIJING_TZ, microsecond=999999 if upper else 0)
    return datetime.combine(parsed, time.max if upper else time.min, BEIJING_TZ)


def validate_window(
    since: str | None, until: str | None,
) -> tuple[datetime | None, datetime | None]:
    """闭区间含日期全天或指定秒；None 不使用本机时间补边界。"""
    lower = _bound(since, "since", upper=False)
    upper = _bound(until, "until", upper=True)
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("since 不得晚于 until")
    return lower, upper


def in_window(
    published_at: datetime, since: datetime | None, until: datetime | None,
) -> bool:
    """已验证的来源时刻按绝对时间与闭区间比较，不依赖本机时区。"""
    return (since is None or published_at >= since) and (until is None or published_at <= until)
