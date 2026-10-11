"""东方财富股票关键词，按来源顺序返回统计值。"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from finchx._common.convert import resolve_code, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, post_json

ENDPOINT = "https://emappdata.eastmoney.com/stockrank/getHotStockRankList"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://quote.eastmoney.com/"}
_KEYWORD_CODE = re.compile(r"BK[0-9]{4}")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
_TZ = timezone(timedelta(hours=8))


def _missing(value: Any) -> bool:
    return value is None or isinstance(value, str) and value.strip() in {"", "--", "-"}


def _hit_count(value: Any) -> int | None:
    if _missing(value):
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise SourceError("eastmoney", "hitCount 数量无法读取") from exc
    raise SourceError("eastmoney", "hitCount 必须是非负整数或空值")


def _calculated_at(value: Any) -> str | None:
    if _missing(value):
        return None
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        raise SourceError("eastmoney", "calcTime 必须是 YYYY-MM-DD HH:MM:SS 来源时间或空值")
    try:
        timestamp = datetime(
            int(value[:4]), int(value[5:7]), int(value[8:10]),
            int(value[11:13]), int(value[14:16]), int(value[17:19]), tzinfo=_TZ,
        )
    except ValueError as exc:
        raise SourceError("eastmoney", "calcTime 来源时间无效") from exc
    return timestamp.isoformat()


def em_keywords(code: str, *, timeout: float) -> list[dict]:
    """读取沪深股票关键词；不将来源统计数量解释为新闻篇数。"""
    symbol = resolve_code(code, kind="stock")
    seconds = validate_timeout(timeout)
    source_code = symbol.upper()
    payload = post_json(ENDPOINT, data={"srcSecurityCode": source_code}, timeout=seconds,
                        headers=_HEADERS, source="eastmoney")
    if not isinstance(payload, dict):
        raise SourceError("eastmoney", "关键词响应外层必须是对象")
    for key in ("code", "status"):
        value = payload.get(key)
        if not (type(value) is int and value == 0 or isinstance(value, str) and value == "0"):
            raise SourceError("eastmoney", f"关键词来源 {key} 未表示成功")
    source_rows = payload.get("data")
    if not isinstance(source_rows, list):
        raise SourceError("eastmoney", "关键词响应缺少有效 data 列表")
    rows = []
    seen = set()
    for raw in source_rows:
        if not isinstance(raw, dict):
            raise SourceError("eastmoney", "关键词来源行必须是对象")
        if raw.get("srcSecurityCode") != source_code:
            raise SourceError("eastmoney", "关键词来源 srcSecurityCode 与请求身份不一致")
        keyword_code = raw.get("conceptId")
        if not isinstance(keyword_code, str) or not _KEYWORD_CODE.fullmatch(keyword_code):
            raise SourceError("eastmoney", "conceptId 必须是 BK 与四位 ASCII 数字")
        if keyword_code in seen:
            raise SourceError("eastmoney", f"关键词来源 conceptId 重复：{keyword_code}")
        seen.add(keyword_code)
        name = raw.get("conceptName")
        if _missing(name):
            name = None
        elif not isinstance(name, str):
            raise SourceError("eastmoney", "conceptName 必须是文字或空值")
        rows.append({
            "keyword_code": keyword_code,
            "keyword_name": name, "hit_count": _hit_count(raw.get("hitCount")),
            "calculated_at": _calculated_at(raw.get("calcTime")),
        })
    return rows
