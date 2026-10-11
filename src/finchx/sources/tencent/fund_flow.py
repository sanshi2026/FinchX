"""腾讯个股资金流，一次请求返回快照、累计分时和日序列。"""

from datetime import date, datetime
import re
from urllib.parse import urlencode

from finchx._common.convert import resolve_code, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json

ENDPOINT = "https://proxy.finance.qq.com/cgi/cgi-bin/fundflow/hsfundtab"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://finance.qq.com/"}
_TYPES = "historyFundFlow,fiveDayFundFlow,todayFundTrend,todayFundFlow"
_SNAPSHOT_FIELDS = {
    "main_net_inflow": "mainNetIn",
    "main_inflow": "mainIn",
    "main_outflow": "mainOut",
    "main_inflow_percent": "mainInRate",
    "main_outflow_percent": "mainOutRate",
    "retail_inflow": "retailIn",
    "retail_outflow": "retailOut",
    "retail_inflow_percent": "retailInRate",
    "retail_outflow_percent": "retailOutRate",
    "super_large_net_inflow": "superFlow",
    "large_net_inflow": "bigFlow",
    "medium_net_inflow": "normalFlow",
    "small_net_inflow": "smallFlow",
}
_INTRADAY_FIELDS = {
    "price": "Price",
    "cumulative_main_net_inflow": "MainNetInflow",
    "cumulative_retail_net_inflow": "RetailNetInflow",
    "cumulative_super_large_net_inflow": "SuperNetInflow",
    "cumulative_large_net_inflow": "BigNetInflow",
    "cumulative_medium_net_inflow": "NormalNetInflow",
    "cumulative_small_net_inflow": "SmallNetInflow",
    "cumulative_main_inflow": "MainInflow",
    "cumulative_main_outflow": "MainOutflow",
}
_NONNEGATIVE = {
    "price", "main_inflow", "main_outflow", "retail_inflow", "retail_outflow",
    "main_inflow_percent", "main_outflow_percent", "retail_inflow_percent", "retail_outflow_percent",
    "cumulative_main_inflow", "cumulative_main_outflow",
}


def _numbers(raw: dict, fields: dict[str, str], context: str) -> dict[str, float | None]:
    """源金额已经是元，占比已经是百分点，不再次缩放。"""
    return {
        field: to_number(raw.get(source_field), f"{context}.{source_field}", source="tencent",
                         nonnegative=field in _NONNEGATIVE)
        for field, source_field in fields.items()
    }


def _intraday(raw: dict) -> tuple[str, list[dict]]:
    source_rows = raw.get("minList")
    if not isinstance(source_rows, list) or not source_rows:
        raise SourceError("tencent", "todayFundTrend.minList 必须包含可确定交易日的分时数据")
    rows = []
    seen: set[str] = set()
    dates: set[str] = set()
    for index, raw_row in enumerate(source_rows):
        context = f"todayFundTrend.minList[{index}]"
        if not isinstance(raw_row, dict):
            raise SourceError("tencent", f"{context} 必须是对象")
        source_time = raw_row.get("time")
        if not isinstance(source_time, str) or not re.fullmatch(r"[0-9]{12}", source_time):
            raise SourceError("tencent", f"{context}.time 必须是有效 YYYYMMDDHHMM 时间")
        try:
            timestamp = datetime(int(source_time[:4]), int(source_time[4:6]), int(source_time[6:8]),
                                 int(source_time[8:10]), int(source_time[10:]))
        except ValueError as exc:
            raise SourceError("tencent", f"{context}.time 必须是有效 YYYYMMDDHHMM 时间") from exc
        if source_time in seen:
            raise SourceError("tencent", f"分时重复时间点：{source_time}")
        seen.add(source_time)
        day = timestamp.date().isoformat()
        dates.add(day)
        rows.append({"date": day, "time": f"{timestamp.hour:02d}:{timestamp.minute:02d}",
                     **_numbers(raw_row, _INTRADAY_FIELDS, context)})
    if len(dates) != 1:
        raise SourceError("tencent", "todayFundTrend 分时必须属于同一个来源交易日")
    return next(iter(dates)), sorted(rows, key=lambda row: (row["date"], row["time"]))


def _daily(raw: dict, days: int) -> list[dict]:
    source_rows = raw.get("oneDayKlineList")
    if not isinstance(source_rows, list):
        raise SourceError("tencent", "historyFundFlow.oneDayKlineList 必须是列表")
    if len(source_rows) > days:
        raise SourceError("tencent", f"历史日序列超过请求 days={days}")
    rows = []
    seen: set[str] = set()
    for index, raw_row in enumerate(source_rows):
        context = f"historyFundFlow.oneDayKlineList[{index}]"
        if not isinstance(raw_row, dict):
            raise SourceError("tencent", f"{context} 必须是对象")
        day = raw_row.get("date")
        if not isinstance(day, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
            raise SourceError("tencent", f"{context}.date 必须是有效 ISO 日期")
        try:
            date.fromisoformat(day)
        except ValueError as exc:
            raise SourceError("tencent", f"{context}.date 必须是有效 ISO 日期") from exc
        if day in seen:
            raise SourceError("tencent", f"日序列重复日期：{day}")
        seen.add(day)
        rows.append({"date": day, **_numbers(raw_row, {"price": "price", "main_net_inflow": "mainNetIn"}, context)})
    return sorted(rows, key=lambda row: row["date"])


def stock(code: str, days: int = 20, *, timeout: float) -> dict:
    """读取沪深股票资金流；日序列保留来源实际提供的日期。"""
    symbol = resolve_code(code, kind="stock")
    if type(days) is not int or not 1 <= days <= 50:
        raise ValueError("days 必须是 1 至 50 的整数")
    timeout = validate_timeout(timeout)
    params = {"code": symbol, "type": _TYPES, "klineNeedDay": days}
    payload = get_json(f"{ENDPOINT}?{urlencode(params)}", timeout=timeout, headers=_HEADERS, source="tencent")
    if not isinstance(payload, dict):
        raise SourceError("tencent", "资金流响应外层必须是对象")
    status = payload.get("code")
    if not (type(status) is int and status == 0 or isinstance(status, str) and status == "0"):
        raise SourceError("tencent", "资金流来源 code 表示请求失败")
    if payload.get("msg") != "ok":
        raise SourceError("tencent", "资金流来源 msg 未表示成功")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SourceError("tencent", "资金流响应缺少有效 data 对象")
    blocks = {}
    for key in ("todayFundFlow", "todayFundTrend", "historyFundFlow"):
        block = data.get(key)
        if not isinstance(block, dict):
            raise SourceError("tencent", f"资金流缺少有效 {key} 对象")
        if key != "historyFundFlow" or "stockCode" in block:
            if block.get("stockCode") != symbol:
                raise SourceError("tencent", f"{key}.stockCode 与请求的 {symbol} 不一致")
        blocks[key] = block
    day, intraday = _intraday(blocks["todayFundTrend"])
    snapshot = {"date": day, **_numbers(blocks["todayFundFlow"], _SNAPSHOT_FIELDS, "todayFundFlow")}
    return {"code": code, "exchange": symbol[:2], "snapshot": snapshot,
            "intraday": intraday, "daily": _daily(blocks["historyFundFlow"], days)}
