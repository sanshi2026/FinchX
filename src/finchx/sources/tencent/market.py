"""腾讯 A 股分页行情与必要的业务单位转换。"""

from decimal import Decimal, DecimalException, localcontext
import math
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json

ENDPOINT = "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://finance.qq.com/"}
_PAGE_SIZE = 100
_STOCK_TYPES = {"GP-A", "GP-A-KCB", "GP-A-CYB", "GP"}
_CODE = re.compile(r"(sh|sz|bj)([0-9]{6})")
_INTEGER = re.compile(r"[0-9]+")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_MISSING = {"", "--", "-"}
# 倍率以十进制指数表达：手转股、万元转元、亿元转元。
_FIELDS = {
    "price": ("zxj", 0),
    "price_change": ("zd", 0),
    "change_percent": ("zdf", 0),
    "volume": ("volume", 2),
    "amount": ("turnover", 4),
    "turnover_rate": ("hsl", 0),
    "market_cap": ("zsz", 8),
    "float_market_cap": ("ltsz", 8),
    "pe_ttm": ("pe_ttm", 0),
    "change_percent_5d": ("zdf_d5", 0),
    "change_percent_10d": ("zdf_d10", 0),
    "change_percent_20d": ("zdf_d20", 0),
    "change_percent_60d": ("zdf_d60", 0),
    "change_percent_52w": ("zdf_w52", 0),
    "change_percent_ytd": ("zdf_y", 0),
    "amplitude": ("zf", 0),
    "volume_ratio": ("lb", 0),
    "main_net_inflow": ("zljlr", 4),
    "main_inflow": ("zllr", 4),
    "main_outflow": ("zllc", 4),
    "main_inflow_5d": ("zllr_d5", 4),
    "main_outflow_5d": ("zllc_d5", 4),
}
_NONNEGATIVE = {"price", "volume", "amount", "turnover_rate", "market_cap", "float_market_cap", "amplitude", "volume_ratio"}


def _optional_number(value: Any, field: str, scale: int, context: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value in _MISSING:
            return None
        if not _NUMBER.fullmatch(value):
            raise SourceError("tencent", f"{context} 字段 {field} 不是有效数字")
    elif isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise SourceError("tencent", f"{context} 字段 {field} 不是有效数字")
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise SourceError("tencent", f"{context} 字段 {field} 必须是有限数字")
        if field in _NONNEGATIVE and number < 0:
            raise SourceError("tencent", f"{context} 字段 {field} 不得为负数")
        with localcontext() as decimal_context:
            decimal_context.prec = max(28, len(number.as_tuple().digits) + scale)
            number *= Decimal(10) ** scale
        if field == "volume":
            if number != number.to_integral_value():
                raise SourceError("tencent", f"{context} 成交量无法转换为整数股")
            return int(number)
        result = float(number)
    except (DecimalException, ValueError, OverflowError) as exc:
        raise SourceError("tencent", f"{context} 字段 {field} 无法进行数值转换") from exc
    if not math.isfinite(result):
        raise SourceError("tencent", f"{context} 字段 {field} 超出有限浮点数范围")
    return result


def _parse_row(raw: Any, context: str) -> dict[str, str | float | int | None]:
    if not isinstance(raw, dict):
        raise SourceError("tencent", f"{context} 行结构无效")
    source_code = raw.get("code")
    identity = _CODE.fullmatch(source_code) if isinstance(source_code, str) else None
    if identity is None:
        raise SourceError("tencent", f"{context} code 必须包含 sh、sz 或 bj 前缀及六位 ASCII 数字")
    if not isinstance(raw.get("stock_type"), str) or raw["stock_type"] not in _STOCK_TYPES:
        raise SourceError("tencent", f"{context} stock_type 不是已确认的 A 股类型")
    name = raw.get("name")
    if name is not None and not isinstance(name, str):
        raise SourceError("tencent", f"{context} name 必须是字符串或空值")
    row: dict[str, str | float | int | None] = {
        "code": identity[2],
        "exchange": identity[1],
        "name": name if name is not None and name.strip() else None,
    }
    for field, (source_field, scale) in _FIELDS.items():
        row[field] = _optional_number(raw.get(source_field), field, scale, context)
    return row


def _check_status(obj: dict[str, Any], context: str) -> None:
    error = obj.get("error")
    if isinstance(error, bool) or error not in (None, "", 0):
        raise SourceError("tencent", f"{context} error 表示来源失败")
    for key in ("code", "status"):
        if key not in obj:
            continue
        value = obj[key]
        success = (
            type(value) is int and value in (0, 200)
            or isinstance(value, str) and value.strip().casefold() in {"0", "200", "ok", "success"}
        )
        if not success:
            raise SourceError("tencent", f"{context} {key} 状态表示来源失败")


def _nonnegative_integer(value: Any, field: str, offset: int) -> int:
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and _INTEGER.fullmatch(value.strip()):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise SourceError("tencent", f"offset={offset} 的 {field} 无法读取") from exc
    raise SourceError("tencent", f"offset={offset} 的 {field} 必须是非负整数")


def _parse_page(payload: Any, offset: int) -> tuple[list[Any], int]:
    if not isinstance(payload, dict):
        raise SourceError("tencent", f"offset={offset} 响应外层结构无效")
    _check_status(payload, f"offset={offset} 响应外层")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SourceError("tencent", f"offset={offset} 响应缺少有效的 data 对象")
    _check_status(data, f"offset={offset} data")
    page = data.get("rank_list")
    if not isinstance(page, list):
        raise SourceError("tencent", f"offset={offset} rank_list 必须是列表")
    total = _nonnegative_integer(data.get("total"), "total", offset)
    if "offset" in data:
        response_offset = _nonnegative_integer(data["offset"], "offset", offset)
        if response_offset != offset:
            raise SourceError("tencent", f"响应 offset 不匹配：请求 {offset}，返回 {response_offset}")
    return page, total


def _get_rank_page(*, timeout: float, sort_type: str, direct: str, offset: int, count: int) -> tuple[list[Any], int]:
    params = {
        "_appver": "11.17.0", "board_code": "aStock", "sort_type": sort_type,
        "direct": direct, "offset": offset, "count": count,
    }
    payload = get_json(f"{ENDPOINT}?{urlencode(params)}", timeout=timeout, headers=_HEADERS, source="tencent")
    return _parse_page(payload, offset)


def _complete_quotes(*, timeout: float, sort_type: str, direct: str) -> list[dict[str, str | float | int | None]]:
    rows: dict[tuple[str, str], dict[str, str | float | int | None]] = {}
    expected_total: int | None = None
    rounds = (
        (sort_type, direct),
        ("turnover", "up" if direct == "down" else "down"),
        ("volume", "up" if (sort_type, direct) == ("volume", "down") else "down"),
    )
    for round_number, (round_sort, round_direct) in enumerate(rounds, start=1):
        offset = 0
        while expected_total is None or offset < expected_total:
            count = _PAGE_SIZE if expected_total is None else min(_PAGE_SIZE, expected_total - offset)
            page, total = _get_rank_page(
                timeout=timeout, sort_type=round_sort, direct=round_direct, offset=offset, count=count,
            )
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise SourceError("tencent", f"第 {round_number} 轮分页 total 发生变化：原为 {expected_total}，offset={offset} 返回 {total}")
            wanted = min(count, total - offset)
            if len(page) != wanted:
                raise SourceError("tencent", f"offset={offset} 分页行数不完整或超出范围：应为 {wanted}，实际 {len(page)}")
            page_seen: set[tuple[str, str]] = set()
            for position, raw in enumerate(page):
                row = _parse_row(raw, f"offset={offset} 第 {position + 1} 行")
                identity = (row["exchange"], row["code"])
                if identity in page_seen:
                    raise SourceError("tencent", f"offset={offset} 同页股票身份重复：{row['exchange']}{row['code']}")
                page_seen.add(identity)
                # 实时排名会跨页移动；后读行更新真实行情，不凭去重结果声称全量。
                rows[identity] = row
            if len(rows) > expected_total:
                raise SourceError("tencent", f"唯一股票数量 {len(rows)} 超过来源声明 total={expected_total}")
            offset += len(page)
        if len(rows) == expected_total:
            return list(rows.values())
    raise SourceError("tencent", f"交易行情完整性失败：最多 3 轮取数后，来源声明 {expected_total} 只股票，实际取得 {len(rows)} 只唯一股票；未返回不完整数据")


def all_quotes(*, timeout: float) -> list[dict[str, str | float | int | None]]:
    return _complete_quotes(timeout=timeout, sort_type="turnover", direct="down")


def _ranked_quotes(
    *, sort_type: str, direct: str, limit: int, timeout: float,
) -> list[dict[str, str | float | int | None]]:
    expected_total: int | None = None
    target: int | None = None
    best_unique_count = 0

    # A finite ranking reads only the requested source-ranked window. If live
    # movement creates cross-page overlap, extend the window and retry the same
    # source ordering; never fill a ranking with rows from another sort order.
    for _ in range(3):
        rows: dict[tuple[str, str], dict[str, str | float | int | None]] = {}
        offset = 0
        overlaps = 0
        while expected_total is None or offset < expected_total:
            if target is None:
                count = min(_PAGE_SIZE, limit)
            else:
                if len(rows) >= target:
                    return list(rows.values())
                boundary = min(expected_total, target + overlaps)
                if offset >= boundary:
                    break
                count = min(_PAGE_SIZE, boundary - offset)

            page, total = _get_rank_page(
                timeout=timeout, sort_type=sort_type, direct=direct, offset=offset, count=count,
            )
            if expected_total is None:
                expected_total = total
                target = min(limit, total)
            elif total != expected_total:
                raise SourceError("tencent", f"来源 total 发生变化：原为 {expected_total}，offset={offset} 返回 {total}")

            wanted = min(count, total - offset)
            if len(page) != wanted:
                raise SourceError("tencent", f"offset={offset} 分页行数不完整或超出范围：应为 {wanted}，实际 {len(page)}")

            page_seen: set[tuple[str, str]] = set()
            for position, raw in enumerate(page):
                row = _parse_row(raw, f"offset={offset} 第 {position + 1} 行")
                identity = (row["exchange"], row["code"])
                if identity in page_seen:
                    raise SourceError("tencent", f"offset={offset} 同页股票身份重复：{row['exchange']}{row['code']}")
                page_seen.add(identity)
                if identity in rows:
                    overlaps += 1
                rows[identity] = row
            offset += len(page)
            best_unique_count = max(best_unique_count, len(rows))

            if target == 0 or len(rows) >= target:
                return list(rows.values())

        # The requested window ended before enough unique rows were collected.
        # A fresh pass in the same Tencent ranking may recover rows shifted by
        # live updates. Do not return a partial ranking if all three passes fail.
        if target == 0:
            return []

    raise SourceError(
        "tencent",
        f"排名完整性失败：按来源排序最多读取 3 轮，目标 {target} 只，最多取得 {best_unique_count} 只唯一股票；未返回不完整数据",
    )


def ranking(*, criterion: str, direction: str, limit: int | None, timeout: float) -> list[dict[str, str | float | int | None]]:
    sort_type = {"amount": "turnover", "change_percent": "priceRatio", "volume": "volume"}[criterion]
    direct = "down" if direction == "desc" else "up"
    rows = (
        _complete_quotes(timeout=timeout, sort_type=sort_type, direct=direct)
        if limit is None else
        _ranked_quotes(sort_type=sort_type, direct=direct, limit=limit, timeout=timeout)
    )
    # 同值先按身份稳定排列；缺失排序项在两个方向均置末尾，不补成零。
    rows.sort(key=lambda row: (row["exchange"], row["code"]))
    known = [row for row in rows if row[criterion] is not None]
    missing = [row for row in rows if row[criterion] is None]
    known.sort(key=lambda row: row[criterion], reverse=direction == "desc")
    ordered = known + missing
    return ordered if limit is None else ordered[:limit]
