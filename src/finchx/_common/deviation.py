"""偏离值模型的十进制计算；触发价沿用最大偏离区间的基准。"""

from datetime import date
from decimal import Decimal, DecimalException, ROUND_CEILING, localcontext

from finchx._common.convert import to_number
from finchx._common.errors import SourceError

PRICE_BASIS = "qfq_stock_anchored_to_price_date__raw_index"


def calculate_window(
    stock: dict[date, Decimal], benchmark: dict[date, Decimal],
    sessions: list[date], *, window_days: int, scenario: str,
    target_date: date, stock_price: Decimal, benchmark_level: Decimal,
    scale: Decimal, coverage_status: str,
    stock_time: str | None, benchmark_time: str | None,
    first_baselines: tuple[date, date] | None = None,
    inferred_halt_dates: tuple[date, ...] = (),
) -> dict:
    """连续统计段；复牌首日允许股票与指数使用各自的真实基准日。"""
    if len(sessions) < 2:
        raise SourceError("deviation", "至少需要两个可比价格点")
    with localcontext() as context:
        context.prec = 40
        stop = len(sessions) if scenario == "next_session" else len(sessions) - 1
        maximum = None
        for position in range(1, stop):
            stock_base, index_base = (first_baselines if position == 1 and first_baselines
                                      else (sessions[position - 1], sessions[position - 1]))
            sb, ib = stock[stock_base] * scale, benchmark[index_base]
            sr = stock_price / sb - 1
            ir = benchmark_level / ib - 1
            candidate = (sr - ir, position, sb, ib, sr, ir, stock_base, index_base)
            # 日期顺序遍历；同值保留最早基准，不为其他候选计算触发价。
            if maximum is None or candidate[0] > maximum[0]:
                maximum = candidate
        if maximum is None and len(sessions) == 2:
            stock_base, index_base = first_baselines or (sessions[0], sessions[0])
            sb, ib = stock[stock_base] * scale, benchmark[index_base]
            sr, ir = stock_price / sb - 1, benchmark_level / ib - 1
            maximum = (sr - ir, 1, sb, ib, sr, ir, stock_base, index_base)
        threshold = Decimal(1 if window_days == 10 else 2)
        theoretical = maximum[2] * (threshold + benchmark_level / maximum[3])
        if not theoretical.is_finite() or theoretical <= 0:
            raise SourceError("deviation", "理论触发价不是有限正数")
        try:
            rounded = theoretical.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        except DecimalException as exc:
            raise SourceError("deviation", "理论触发价无法按分向上进位") from exc

        def number(value: Decimal, field: str) -> float:
            return to_number(value, field, source="deviation")

        start_price = (stock_price if maximum[1] == len(sessions) - 1
                       else stock[sessions[maximum[1]]] * scale)
        expected = window_days - (1 if scenario == "next_session" else 0)
        status = "complete"
        if len(sessions) - 1 < expected:
            if inferred_halt_dates:
                status = ("partial_short_history_and_inferred_halt"
                          if coverage_status == "short_history_and_halt_inferred_from_missing_kline"
                          else "partial_after_inferred_halt")
            else:
                status = "partial_short_history"
        return {
            "window_days": window_days,
            "scenario": scenario,
            "price_date": sessions[-1].isoformat(),
            "target_date": target_date.isoformat(),
            "available_trading_days": len(sessions) - 1,
            "window_status": status,
            "coverage_status": coverage_status,
            "inferred_halt_dates": [day.isoformat() for day in inferred_halt_dates],
            "stock_price": number(stock_price, "stock_price"),
            "benchmark_level": number(benchmark_level, "benchmark_level"),
            "stock_price_type": "quote" if stock_time is not None else "daily_close",
            "benchmark_value_type": "quote" if benchmark_time is not None else "daily_close",
            "stock_time": stock_time,
            "benchmark_time": benchmark_time,
            "start_date": sessions[maximum[1]].isoformat(),
            "stock_baseline_date": maximum[6].isoformat(),
            "benchmark_baseline_date": maximum[7].isoformat(),
            "trading_days": len(sessions) - maximum[1],
            "stock_baseline_price": number(maximum[2], "stock_baseline_price"),
            "window_start_price": number(start_price, "window_start_price"),
            "benchmark_baseline_level": number(maximum[3], "benchmark_baseline_level"),
            "stock_change_percent": number(maximum[4] * 100, "stock_change_percent"),
            "benchmark_change_percent": number(maximum[5] * 100, "benchmark_change_percent"),
            "deviation_percent": number(maximum[0] * 100, "deviation_percent"),
            "threshold_percent": 100 if window_days == 10 else 200,
            "theoretical_trigger_price": number(theoretical, "theoretical_trigger_price"),
            "trigger_price": number(rounded, "trigger_price"),
            "remaining_change_percent": number((rounded / stock_price - 1) * 100, "remaining_change_percent"),
        }
