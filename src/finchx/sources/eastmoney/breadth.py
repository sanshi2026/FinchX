"""东方财富涨跌分布，按来源完整分桶客观求和。"""

from datetime import date
import json
import re
import time
from typing import Any
from urllib.parse import urlencode

from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

ENDPOINT = "https://push2ex.eastmoney.com/getTopicZDFenBu"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://quote.eastmoney.com/ztb/detail"}
_JSONP = re.compile(r"\s*finchxEastmoney\s*\((.*)\)\s*;?\s*", re.S)
_INTEGER = re.compile(r"[0-9]+")
# 与东方财富当前官方页面的分桶展示逐项一致。
_BUCKETS = {
    -11: "跌停", -10: "低于-9%(未跌停)", -9: "-9%--8%", -8: "-8%--7%",
    -7: "-7%--6%", -6: "-6%--5%", -5: "-5%--4%", -4: "-4%--3%",
    -3: "-3%--2%", -2: "-2%--1%", -1: "-1%--0%", 0: "0%",
    1: "0%-1%", 2: "1%-2%", 3: "2%-3%", 4: "3%-4%", 5: "4%-5%",
    6: "5%-6%", 7: "6%-7%", 8: "7%-8%", 9: "8%-9%",
    10: "高于9%(未涨停)", 11: "涨停",
}


def _count(value: Any, bucket: str) -> int:
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and _INTEGER.fullmatch(value.strip()):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise SourceError("eastmoney", f"分桶 {bucket} 的数量无法读取") from exc
    raise SourceError("eastmoney", f"分桶 {bucket} 的数量必须是非负整数")


def em_breadth(*, timeout: float) -> dict:
    params = {"cb": "finchxEastmoney", "ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztzt", "_": int(time.time() * 1000)}
    text = get_text(f"{ENDPOINT}?{urlencode(params)}", timeout=timeout, headers=_HEADERS, source="eastmoney")
    matched = _JSONP.fullmatch(text)
    if matched is None:
        raise SourceError("eastmoney", "涨跌分布响应不是预期的 finchxEastmoney JSONP")
    try:
        payload = json.loads(matched[1])
    except (json.JSONDecodeError, ValueError) as exc:
        raise SourceError("eastmoney", "涨跌分布响应不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise SourceError("eastmoney", "涨跌分布响应外层结构无效")
    rc = payload.get("rc")
    if not (type(rc) is int and rc == 0 or isinstance(rc, str) and rc.strip() == "0"):
        raise SourceError("eastmoney", "涨跌分布来源 rc 表示请求失败")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SourceError("eastmoney", "涨跌分布响应缺少有效的 data 对象")
    qdate = data.get("qdate")
    date_text = str(qdate) if type(qdate) is int else qdate
    if not isinstance(date_text, str) or not re.fullmatch(r"[0-9]{8}", date_text):
        raise SourceError("eastmoney", "qdate 必须是来源提供的有效 YYYYMMDD 日期")
    try:
        day = date(int(date_text[:4]), int(date_text[4:6]), int(date_text[6:]))
    except ValueError as exc:
        raise SourceError("eastmoney", "qdate 必须是来源提供的有效 YYYYMMDD 日期") from exc
    distribution = data.get("fenbu")
    if not isinstance(distribution, list) or len(distribution) != len(_BUCKETS):
        raise SourceError("eastmoney", "fenbu 必须包含全部 23 个唯一分桶")
    counts: dict[int, int] = {}
    expected_keys = {str(code) for code in _BUCKETS}
    for raw in distribution:
        if not isinstance(raw, dict) or len(raw) != 1:
            raise SourceError("eastmoney", "fenbu 每行必须包含一个分桶")
        key = next(iter(raw))
        if key not in expected_keys:
            raise SourceError("eastmoney", "fenbu 返回了未确认的分桶")
        code = int(key)
        if code in counts:
            raise SourceError("eastmoney", f"fenbu 分桶 {key} 重复")
        counts[code] = _count(raw[key], key)
    if set(counts) != set(_BUCKETS):
        raise SourceError("eastmoney", "fenbu 分桶不完整")
    advancing = sum(counts[code] for code in range(1, 12))
    declining = sum(counts[code] for code in range(-11, 0))
    unchanged = counts[0]
    return {
        "date": day.isoformat(), "advancing": advancing, "declining": declining,
        "unchanged": unchanged, "total": advancing + declining + unchanged,
        "limit_up_count": counts[11], "limit_down_count": counts[-11],
        "up_over_9_percent_count": counts[10], "down_over_9_percent_count": counts[-10],
        "distribution": [{"range": _BUCKETS[code], "count": counts[code]} for code in sorted(counts)],
    }
