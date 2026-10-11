"""腾讯当前/下一交易日偏离模型；有真实前后价格的股票缺口推定停牌。"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
import re
import warnings
from typing import Callable
from urllib.parse import urlencode

from finchx._common.convert import parse_date_parameter, resolve_code, to_decimal, validate_timeout
from finchx._common.deviation import PRICE_BASIS, calculate_window
from finchx._common.errors import SourceError
from finchx._common.http import get_text
from finchx.sources.tencent import company, klines, quote

_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_SHANGHAI = timezone(timedelta(hours=8))
_BENCHMARKS = {
    "60": ("sse_main_board", "000002", "sh", "上证A指"),
    "68": ("star", "000688", "sh", "科创50"),
    "00": ("szse_main_board", "399107", "sz", "深证A指"),
    "30": ("chinext", "399102", "sz", "创业板综"),
}


def _fail(reason: str) -> None:
    raise SourceError("deviation", reason)


def _date(value: object, field: str, *, parameter: bool = False) -> date:
    if parameter:
        return parse_date_parameter(value, field)
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    _fail(f"{field} 不是有效 ISO 日期")


def _positive(value: object, field: str) -> Decimal:
    result = to_decimal(value, field, source="deviation")
    if result is None or result <= 0:
        _fail(f"{field} 必须是有限正数")
    return result


def _now() -> datetime:
    return datetime.now(_SHANGHAI)


def _quote_input(row: object, code: str, exchange: str) -> tuple[dict, datetime]:
    if not isinstance(row, dict) or row.get("code") != code or row.get("exchange") != exchange:
        _fail("报价身份与请求不一致")
    stamp = row.get("time")
    if not isinstance(stamp, str):
        _fail("报价缺少来源时间")
    try:
        source_time = datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise SourceError("deviation", "报价来源时间无效") from exc
    if source_time.utcoffset() != timedelta(hours=8):
        _fail("报价来源时间必须明确为北京时间")
    now = _now()
    if source_time > now + timedelta(minutes=1):
        _fail("报价来源时间在未来")
    if source_time.time() < time(9, 15):
        _fail("报价来源时间早于交易会话")
    # 休市/跨日保留的最新源报价不按分钟时限过期；当日会话才检查新鲜度。
    if source_time.date() == now.date() and time(9, 15) <= now.time() < time(15):
        if time(11, 30) <= now.time() < time(13):
            if source_time.time() < time(11, 15):
                _fail("午休报价未覆盖上午交易会话")
        elif now - source_time > timedelta(minutes=20):
            _fail("交易会话报价已过期")
    _positive(row.get("price"), "quote.price")
    return row, source_time


def _latest_pair(
    initial: tuple[dict, datetime], code: str, exchange: str,
    benchmark_code: str, benchmark_exchange: str, *, timeout: float,
) -> tuple[tuple[dict, datetime], tuple[dict, datetime]]:
    index = initial
    for attempt in range(2):
        stock = _quote_input(quote.quote_snapshot(code, timeout=timeout), code, exchange)
        checked = _quote_input(
            quote.quote_snapshot(benchmark_code, kind="index", timeout=timeout),
            benchmark_code, benchmark_exchange,
        )
        if stock[1].date() == index[1].date() == checked[1].date():
            return stock, checked
        index = checked
    _fail("有限重读后股票与指数报价观察日期仍不一致")


def _calendar(rows: object, start: date, end: date) -> list[date]:
    if not isinstance(rows, list):
        _fail("交易日历必须是列表")
    marks = {}
    for row in rows:
        if not isinstance(row, dict) or type(row.get("is_trading_day")) is not bool:
            _fail("交易日历缺少显式布尔交易标记")
        day = _date(row.get("date"), "calendar.date")
        if day in marks or not start <= day <= end:
            _fail("交易日历日期重复或超出请求范围")
        marks[day] = row["is_trading_day"]
    if len(marks) != (end - start).days + 1:
        _fail("交易日历未覆盖请求范围内的每个自然日")
    return [day for day in sorted(marks) if marks[day]]


def _validate_latest_session(
    latest: date, stock: tuple[dict, datetime], index: tuple[dict, datetime],
    sessions: list[date], calendar_end: date, calendar: Callable[..., list[dict]],
) -> None:
    """时钟只验证真实源报价是否覆盖已开始的会话，不生成观察日期。"""
    now = _now()
    if now.date() > calendar_end:
        start = date.fromordinal(max(1, now.date().toordinal() - 45))
        recent = _calendar(calendar(start, now.date()), start, now.date())
    else:
        recent = sessions
    begun = [day for day in recent if day < now.date()
             or day == now.date() and now.time() >= time(9, 15)]
    if not begun or latest != max(begun):
        _fail("报价来源日期未覆盖日历已确认的最新开始交易会话")
    if latest < now.date() or now.time() >= time(15):
        if any(item[1].time() < time(14, 57) for item in (stock, index)):
            _fail("已结束交易会话的报价未覆盖收盘附近")


def _prices(
    rows: object, field: str, start: date, end: date, trading_dates: set[date],
) -> dict[date, Decimal]:
    if not isinstance(rows, list):
        _fail(f"{field} 日线结构无效")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            _fail(f"{field} 日线行结构无效")
        day = _date(row.get("date"), f"{field}.date")
        if day in result or not start <= day <= end:
            _fail(f"{field} 日线日期重复或超出请求范围")
        if day not in trading_dates:
            _fail("股票或指数日线日期与日历非交易标记冲突")
        result[day] = _positive(row.get("close"), f"{field}.close")
    return result


def _listing_date(code: str, *, timeout: float) -> date:
    """只解析简况身份和上市日，不执行无关财务业务块。"""
    symbol = resolve_code(code)
    params = {"code": symbol, "app": "official_website"}
    data = company._decode(get_text(
        f"{company.INFO_ENDPOINT}?{urlencode(params)}", timeout=timeout,
        headers=company._HEADERS, source="tencent",
    ), "jiankuang")
    comparison = data.get("hydb")
    identity = comparison.get("stock") if isinstance(comparison, dict) else None
    if (not isinstance(identity, dict) or identity.get("stockcode") != code
            or identity.get("sc") != symbol[:2]):
        _fail("上市日期来源缺少匹配的股票身份")
    profile = data.get("gsjj")
    if not isinstance(profile, dict):
        _fail("上市边界缺少公司简况")
    return _date(profile.get("riqi"), "gsjj.riqi")


def _coverage(short_history: bool, halt: bool) -> str:
    if short_history and halt:
        return "short_history_and_halt_inferred_from_missing_kline"
    if halt:
        return "halt_inferred_from_missing_kline"
    return "short_history" if short_history else "complete"


def deviation(
    code: str, windows: tuple[int, ...] | list[int] = (10, 30),
    end_date: str | None = None, *, timeout: float,
    calendar: Callable[..., list[dict]],
) -> dict:
    """一次调用取齐必要价格；缺口推定须有真实锚点，损坏仍整次失败。"""
    symbol = resolve_code(code)
    if (not isinstance(windows, (tuple, list)) or not windows
            or any(type(item) is not int or item not in (10, 30) for item in windows)
            or len(set(windows)) != len(windows)):
        raise ValueError("windows 必须是非空、不重复且仅含整数10/30的 list 或 tuple")
    requested = None if end_date is None else _date(end_date, "end_date", parameter=True)
    seconds = validate_timeout(timeout)
    board, benchmark_code, benchmark_exchange, benchmark_name = _BENCHMARKS[code[:2]]
    index_quote = _quote_input(
        quote.quote_snapshot(benchmark_code, kind="index", timeout=seconds),
        benchmark_code, benchmark_exchange,
    )
    latest = index_quote[1].date()
    stock_quote = None
    if requested is None or requested >= latest:
        stock_quote, index_quote = _latest_pair(
            index_quote, code, symbol[:2], benchmark_code, benchmark_exchange,
            timeout=seconds,
        )
        latest = index_quote[1].date()
    cutoff = latest if requested is None else requested
    # 历史和下一交易日边界都来自日历；请求范围按业务日期扩展，不造交易标记。
    start = date.fromordinal(max(1, cutoff.toordinal() - (max(windows) * 5 + 45)))
    end = date.fromordinal(min(date.max.toordinal(), cutoff.toordinal() + 45))
    sessions = _calendar(calendar(start, end), start, end)
    previous = [day for day in sessions if day <= cutoff]
    if not previous:
        _fail("截止日期之前无可确认的交易日")
    observed = previous[-1]
    if observed > latest:
        raise ValueError("end_date 超过来源最新可确认的观察交易日")
    following = [day for day in sessions if day > observed]
    if not following:
        _fail("日历不能确认次一交易日")
    if len(previous) < max(windows) + 1:
        _fail("日历不能确认所需历史统计边界")
    required = previous[-(max(windows) + 1):]
    live = observed == latest
    if live:
        if stock_quote is None:
            stock_quote, index_quote = _latest_pair(
                index_quote, code, symbol[:2], benchmark_code, benchmark_exchange,
                timeout=seconds,
            )
        if stock_quote[1].date() != observed or index_quote[1].date() != observed:
            _fail("取日历期间报价观察日期发生变化")
        _validate_latest_session(latest, stock_quote, index_quote, sessions, end, calendar)
    history_start = required[0]
    trading_dates = set(sessions)
    stock = _prices(klines.ohlcv(
        code, history_start, observed, "qfq", timeout=seconds,
    ), "stock_qfq", history_start, observed, trading_dates)
    benchmark = _prices(klines.ohlcv(
        benchmark_code, history_start, observed, kind="index", timeout=seconds,
    ), "benchmark", history_start, observed, trading_dates)
    # 原请求边界可能落在停牌段里；最多一次扩至同份日历已验证的边界。
    # 扩取整份 qfq 后再统一锚定，避免拼接两次请求的不同复权尺度。
    if history_start not in stock or live and not any(day < observed for day in stock):
        stock = _prices(klines.ohlcv(
            code, start, observed, "qfq", timeout=seconds,
        ), "stock_qfq", start, observed, trading_dates)
    if live:
        if stock_quote[1].date() != observed or index_quote[1].date() != observed:
            _fail("取历史价格期间观察日期发生变化")
        stock_price = _positive(stock_quote[0].get("price"), "stock.price")
        benchmark_level = _positive(index_quote[0].get("price"), "benchmark.price")
        bridge_days = [day for day in stock if day < observed]
        if not bridge_days:
            _fail("缺少报价桥接所需的最后实际前复权收盘价")
        bridge_day = max(bridge_days)
        with localcontext() as context:
            context.prec = 40
            scale = _positive(stock_quote[0].get("previous_close"), "stock.previous_close") / stock[bridge_day]
            stock[observed] = stock_price / scale
        benchmark[observed] = benchmark_level
        stock_time, benchmark_time = stock_quote[0]["time"], index_quote[0]["time"]
    else:
        if observed not in stock or observed not in benchmark:
            _fail("历史观察日缺少股票或指数收盘价")
        raw = _prices(klines.ohlcv(
            code, observed, observed, timeout=seconds,
        ), "stock_raw", observed, observed, trading_dates)
        if observed not in raw:
            _fail("历史观察日缺少不复权价格锚点")
        stock_price, benchmark_level = raw[observed], benchmark[observed]
        with localcontext() as context:
            context.prec = 40
            scale = stock_price / stock[observed]
        stock_time = benchmark_time = None
    # 前缀只有真实上市日才能解释；其余缺口须被前后实际股票价括住。
    missing_stock = [day for day in required if day not in stock]
    listing = None
    actual = sorted(stock)
    prefix = [day for day in missing_stock if not actual or day < actual[0]]
    if prefix:
        listing = _listing_date(code, timeout=seconds)
        if (not actual or actual[0] != listing
                or any(day >= listing for day in prefix)):
            _fail("股票日线前缀不足缺少真实上市边界或停牌前价格锚点")
    halt_dates = [day for day in missing_stock if listing is None or day >= listing]
    if any(not any(point < day for point in actual)
           or not any(point > day for point in actual) for day in halt_dates):
        _fail("股票日线缺口没有前后实际价格锚点")
    if any(day not in benchmark for day in required if listing is None or day >= listing):
        _fail("必要统计日期缺少指数收盘价")
    rows = []
    for window in windows:
        for scenario in ("current", "next_session"):
            count = window + (0 if scenario == "next_session" else 1)
            selected = previous[-count:]
            short_history = listing is not None and any(day < listing for day in selected)
            if listing is not None:
                selected = [day for day in selected if day >= listing]
            inferred = tuple(day for day in selected if day in halt_dates)
            first_baselines = None
            if inferred:
                last_gap = inferred[-1]
                resume = next(day for day in selected if day > last_gap)
                stock_base = max(day for day in actual if day < resume)
                index_base = previous[previous.index(resume) - 1]
                if index_base not in benchmark:
                    _fail("复牌首日缺少前一市场交易日指数基准")
                first_baselines = (stock_base, index_base)
                selected = [index_base] + [day for day in selected if day >= resume]
            coverage = _coverage(short_history, bool(inferred))
            rows.append(calculate_window(
                stock, benchmark, selected, window_days=window, scenario=scenario,
                target_date=following[0] if scenario == "next_session" else observed,
                stock_price=stock_price, benchmark_level=benchmark_level,
                scale=scale, coverage_status=coverage,
                stock_time=stock_time, benchmark_time=benchmark_time,
                first_baselines=first_baselines, inferred_halt_dates=inferred,
            ))
    inferred = sorted({day for row in rows for day in row["inferred_halt_dates"]})
    result = {
        "code": code, "exchange": symbol[:2], "board": board,
        "end_date": observed.isoformat(),
        "benchmark": {"code": benchmark_code, "exchange": benchmark_exchange, "name": benchmark_name},
        "price_basis": PRICE_BASIS,
        "coverage_status": _coverage(any(row["coverage_status"].startswith("short_history") for row in rows), bool(inferred)),
        "inferred_halt_dates": inferred,
        "windows": rows,
    }
    # 全部窗口及数值成功后才发提示；警告过滤为 error 时保留 UserWarning。
    if inferred:
        affected = []
        for row in rows:
            if row["inferred_halt_dates"]:
                scene = "当前" if row["scenario"] == "current" else "次一交易日"
                detail = f"{row['window_days']}日窗口/{scene}场景"
                status = "窗口完整" if row["window_status"] == "complete" else "窗口不足"
                detail += f"（可用统计日{row['available_trading_days']}天，{status}）"
                affected.append(detail)
        warnings.warn(
            "股票日线缺口推定为停牌，未核对交易所停牌公告；缺口日期："
            + "、".join(inferred) + "；受影响：" + "、".join(affected),
            UserWarning, stacklevel=3,
        )
    return result
