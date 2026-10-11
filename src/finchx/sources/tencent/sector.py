"""腾讯股票所属板块与行业比较，各接口每次读取一份来源响应。"""

import json
from decimal import Decimal
import re
from urllib.parse import urlencode

from finchx._common.convert import resolve_code, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json, get_text

SECTORS_ENDPOINT = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/stockinfo/plateNew"
INDUSTRY_ENDPOINT = "https://proxy.finance.qq.com/ifzqgtimg/appstock/hs/hypm/get"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://gu.qq.com/"}
_ASSIGNMENT = re.compile(r"\s*gg_hypm\s*=\s*(\{.*\})\s*;?\s*", re.DOTALL)
_SECTOR_TYPES = (("area", "area"), ("plate", "industry"), ("concept", "concept"))
_INDUSTRY_FIELDS = {
    "pe": ("data", "syl"),
    "eps": ("data", "mgsy"),
    "float_market_cap": ("data", "zsz"),
    "pe_rank": ("pm", "syl_pm"),
    "eps_rank": ("pm", "mgsy_pm"),
    "float_market_cap_rank": ("pm", "zsz_pm"),
    "industry_count": ("plate_avg", "count"),
    "industry_avg_pe": ("plate_avg", "avg_syl"),
    "industry_avg_eps": ("plate_avg", "avg_mgsy"),
    "industry_avg_float_market_cap": ("plate_avg", "avg_zsz"),
    "market_avg_pe": ("shsz_avg", "avg_syl"),
    "market_avg_eps": ("shsz_avg", "avg_mgsy"),
    "market_avg_float_market_cap": ("shsz_avg", "avg_zsz"),
}
_INTEGERS = {"pe_rank", "eps_rank", "float_market_cap_rank", "industry_count"}
_MARKET_CAPS = {"float_market_cap", "industry_avg_float_market_cap", "market_avg_float_market_cap"}


def _data(payload: object, context: str, *, industry: bool = False) -> dict:
    if not isinstance(payload, dict):
        raise SourceError("tencent", f"{context} 响应外层必须是对象")
    status = payload.get("code")
    if not (type(status) is int and status == 0 or isinstance(status, str) and status == "0"):
        raise SourceError("tencent", f"{context} 来源 code 表示请求失败")
    if not isinstance(payload.get("msg"), str) or industry and payload["msg"] != "OK":
        raise SourceError("tencent", f"{context} 来源 msg 无效")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SourceError("tencent", f"{context} 响应缺少有效 data 对象")
    return data


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise SourceError("tencent", f"{field} 必须是非空且不含空白的来源代码")
    return value


def _text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SourceError("tencent", f"{field} 必须是文本")
    return value.strip() or None


def tx_sectors(code: str, *, timeout: float) -> list[dict]:
    """返回股票所属地域、行业及概念，保留来源标签与百分点涨跌幅。"""
    symbol = resolve_code(code, kind="stock")
    timeout = validate_timeout(timeout)
    params = {"code": symbol, "app": "wzq", "zdf": "1"}
    payload = get_json(f"{SECTORS_ENDPOINT}?{urlencode(params)}", timeout=timeout,
                       headers=_HEADERS, source="tencent")
    data = _data(payload, "plateNew")
    rows = []
    identities = set()
    for block, sector_type in _SECTOR_TYPES:
        raw_rows = data.get(block)
        if not isinstance(raw_rows, list):
            raise SourceError("tencent", f"plateNew data.{block} 必须是列表")
        group = []
        for index, raw in enumerate(raw_rows):
            context = f"data.{block}[{index}]"
            if not isinstance(raw, dict):
                raise SourceError("tencent", f"plateNew {context} 必须是对象")
            source_id, source_code = raw.get("id"), raw.get("code")
            if source_id is not None:
                source_id = _identity(source_id, f"{context}.id")
            if source_code is not None:
                source_code = _identity(source_code, f"{context}.code")
            if source_id is not None and source_code is not None and source_id != source_code:
                raise SourceError("tencent", f"plateNew {context}.id 与 code 不一致")
            sector_code = _identity(source_id if source_id is not None else source_code, f"{context}.id/code")
            identity = (sector_type, sector_code)
            if identity in identities:
                raise SourceError("tencent", f"plateNew 重复板块身份：{sector_type}/{sector_code}")
            identities.add(identity)
            group.append({
                "sector_type": sector_type,
                "sector_code": sector_code,
                "sector_name": _text(raw.get("name"), f"{context}.name"),
                "change_percent": to_number(raw.get("zdf"), f"{context}.zdf", source="tencent"),
                "level": to_number(raw.get("level"), f"{context}.level", source="tencent", integer=True, nonnegative=True),
                "tag": _text(raw.get("tag"), f"{context}.tag"),
            })
        rows.extend(sorted(group, key=lambda row: row["sector_code"]))
    return rows


def _reject_constant(value: str) -> None:
    raise ValueError(f"非法 JSON 常量：{value}")


def tx_industry_comparison(code: str, *, timeout: float) -> dict:
    """返回来源行业指标、排名和均值，不推断报告期或排名方向。"""
    symbol = resolve_code(code, kind="stock")
    timeout = validate_timeout(timeout)
    params = {"code": symbol, "_var": "gg_hypm"}
    text = get_text(f"{INDUSTRY_ENDPOINT}?{urlencode(params)}", timeout=timeout,
                    headers=_HEADERS, source="tencent")
    match = _ASSIGNMENT.fullmatch(text) if isinstance(text, str) else None
    if match is None:
        raise SourceError("tencent", "hypm 响应必须是有效 gg_hypm JSON 赋值")
    try:
        payload = json.loads(match.group(1), parse_float=Decimal, parse_constant=_reject_constant)
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise SourceError("tencent", "hypm 赋值内容不是有效 JSON") from exc
    data = _data(payload, "hypm", industry=True)
    for block in ("hyinfo", "data", "pm", "plate_avg", "shsz_avg"):
        if not isinstance(data.get(block), dict):
            raise SourceError("tencent", f"hypm data.{block} 必须是对象")
    market_type = data["data"].get("sclx")
    if market_type is not None and market_type != {"sh": "1", "sz": "51"}[symbol[:2]]:
        raise SourceError("tencent", "hypm data.data.sclx 与请求交易所不一致")
    row = {
        "code": code,
        "exchange": symbol[:2],
        "industry_code": _identity(data["hyinfo"].get("dm"), "data.hyinfo.dm"),
        "industry_name": _text(data["hyinfo"].get("hymc"), "data.hyinfo.hymc"),
    }
    # gu.qq.com 当前引用的官方脚本：st.gtimg.com/quotes/hs-fund/bundle.13362df9.js。
    # Rank 组件将这三个 zsz 值直接显示为“亿”；保留 JSON 十进制到换算后再转 float。
    # 官方显示口径为流通 A 股市值，不依据旧版注释解释为总市值。
    for field, (block, source_field) in _INDUSTRY_FIELDS.items():
        row[field] = to_number(data[block].get(source_field), f"data.{block}.{source_field}",
                               source="tencent", scale=8 if field in _MARKET_CAPS else 0,
                               integer=field in _INTEGERS, nonnegative=field in _INTEGERS | _MARKET_CAPS)
    return row
