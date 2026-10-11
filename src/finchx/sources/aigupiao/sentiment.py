"""爱股票公开情绪指标，只做来源显示单位的必要转换。"""

import re
import time
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import to_number
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json

ENDPOINT = "https://igp-img-upload-1251605428.cos.ap-shanghai.myqcloud.com/cos_data/market_sentiment_list_client.json"
_HEADERS = {**DEFAULT_HEADERS, "Accept": "text/javascript, application/javascript, */*; q=0.01", "Referer": "https://www.10jqka.com.cn/"}
_MISSING = {"", "--", "-"}
_AMOUNT = re.compile(r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)(万亿|亿|万|元)?")
_AMOUNT_SCALE = {None: 0, "元": 0, "万": 4, "亿": 8, "万亿": 12}
_COUNTS = {
    "stop_trading_count": "stop_trad_stock_num",
    "one_limit_up_count": "one_limit_up_stock_num",
    "two_limit_up_count": "two_limit_up_stock_num",
    "three_limit_up_count": "three_limit_up_stock_num",
    "high_limit_up_count": "high_limit_up_stock_num",
}
_PERCENTS = {
    "turnover_change_percent": "turnover_chg",
    "median_change_percent": "median_val",
    "blast_break_percent": "blast_break_pct",
    "previous_limit_up_break_change_percent": "limit_up_break_chg_pct",
    "two_limit_up_promotion_percent": "two_limit_up_stock_rate",
    "three_limit_up_promotion_percent": "three_limit_up_stock_rate",
    "high_limit_up_promotion_percent": "high_limit_up_stock_rate",
    "previous_limit_up_theme_change_percent": "raising_limit_theme_chg_pct",
    "previous_consecutive_limit_up_theme_change_percent": "repetition_limit_theme_chg_pct",
}
_AMOUNTS = {"total_turnover": "total_turnover", "forecasted_turnover": "forecasted_turnover", "turnover_change_amount": "turnover_growing_data"}


def _display_number(value: Any, field: str, suffix: str) -> float | None:
    if isinstance(value, str):
        value = value.strip()
        if value.endswith(suffix):
            value = value[:-len(suffix)].strip()
            if not value:
                raise SourceError("aigupiao", f"字段 {field} 缺少显示单位前的数字")
    return to_number(value, field, source="aigupiao")


def _amount(value: Any, field: str) -> float | None:
    scale = 0
    if isinstance(value, str):
        value = value.strip()
        if value not in _MISSING:
            matched = _AMOUNT.fullmatch(value)
            if matched is None:
                raise SourceError("aigupiao", f"字段 {field} 金额单位或数字无效")
            value, scale = matched[1], _AMOUNT_SCALE[matched[2]]
    return to_number(value, field, source="aigupiao", scale=scale, nonnegative=field != "turnover_change_amount")


def _count(value: Any, field: str) -> int | None:
    if value is None or isinstance(value, str) and value.strip() in _MISSING:
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise SourceError("aigupiao", f"字段 {field} 数量无法读取") from exc
    raise SourceError("aigupiao", f"字段 {field} 必须是非负整数或空值")


def agp_sentiment(*, timeout: float) -> dict[str, float | int | None]:
    url = f"{ENDPOINT}?{urlencode({'ts': int(time.time() * 1000)})}"
    payload = get_json(url, timeout=timeout, headers=_HEADERS, source="aigupiao")
    if not isinstance(payload, dict):
        raise SourceError("aigupiao", "情绪响应外层结构无效")
    code = payload.get("code")
    if not (type(code) is int and code == 0 or isinstance(code, str) and code.strip() == "0") or payload.get("status") != "success":
        raise SourceError("aigupiao", "情绪来源状态表示请求失败")
    data = payload.get("data")
    known = {"market_temperature", *_COUNTS.values(), *_PERCENTS.values(), *_AMOUNTS.values()}
    if not isinstance(data, dict) or not data or not known.intersection(data):
        raise SourceError("aigupiao", "情绪响应缺少包含已知业务字段的 data 对象")
    row: dict[str, float | int | None] = {"market_temperature": _display_number(data.get("market_temperature"), "market_temperature", "°C")}
    for field, source_field in _AMOUNTS.items():
        row[field] = _amount(data.get(source_field), field)
    for field, source_field in _PERCENTS.items():
        row[field] = _display_number(data.get(source_field), field, "%")
    for field, source_field in _COUNTS.items():
        row[field] = _count(data.get(source_field), field)
    return row
