"""同花顺 HXKline 日线。"""

from datetime import date, datetime, timedelta, timezone
import re
from urllib.parse import urlencode
from typing import Any

from finchx._common.convert import parse_date_parameter, to_decimal, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json, post_json

_DICT_ENDPOINT = "https://news.10jqka.com.cn/app/headline/mobi-stockdict/v1/search/"
_KLINE_ENDPOINT = "https://quota-h.10jqka.com.cn/fuyao/common_hq_aggr/quote/v1/single_kline"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://stock.10jqka.com.cn/"}
_FIELDS = ("1", "7", "8", "9", "11", "13", "19")
_ADJUSTMENTS = {None: "actual", "qfq": "forward", "hfq": "backward"}
_SHANGHAI = timezone(timedelta(hours=8))
_UTC = timezone.utc
_INDEX_ALIASES = {"000001": "1A0001", "000002": "1A0002", "000688": "1B0688"}
_CODE = re.compile(r"[0-9]{6}")


def _day_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=_SHANGHAI).timestamp() * 1000)


def _identity(code: str, kind: str, *, timeout: float) -> tuple[str, str]:
    params = urlencode({
        "isrealcode": "1", "associate": "1", "json": "1", "markettype": "2", "query": code,
    })
    document = get_json(f"{_DICT_ENDPOINT}?{params}", timeout=timeout, headers=_HEADERS, source="tonghuashun")
    status = document.get("status_code") if isinstance(document, dict) else None
    if status not in (0, "0", "success") or isinstance(status, bool):
        raise SourceError("tonghuashun", "行情字典来源状态失败或缺失")
    data = document.get("data")
    head, body = (data.get("head"), data.get("body")) if isinstance(data, dict) else (None, None)
    if not isinstance(head, list) or not isinstance(body, list):
        raise SourceError("tonghuashun", "行情字典响应结构无效")
    columns: dict[str, int] = {}
    for index, item in enumerate(head):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise SourceError("tonghuashun", "行情字典字段定义无效")
        if item["id"] in columns:
            raise SourceError("tonghuashun", "行情字典字段定义重复")
        columns[item["id"]] = index
    if not {"hq_code", "hq_market", "market_label"}.issubset(columns):
        raise SourceError("tonghuashun", "行情字典缺少代码、市场或类型字段")

    def cell(row: Any, name: str) -> Any:
        index = columns[name]
        return row[index] if isinstance(row, list) and len(row) > index else None

    candidates = []
    expected_code = code if kind == "stock" else _INDEX_ALIASES.get(code, code)
    for row in body:
        if not isinstance(row, list):
            raise SourceError("tonghuashun", "行情字典记录结构无效")
        hq_code, market, label = (cell(row, name) for name in ("hq_code", "hq_market", "market_label"))
        if not isinstance(hq_code, str) or not isinstance(market, (str, int)) or isinstance(market, bool):
            continue
        market = str(market)
        if not hq_code or not market.isdecimal() or not isinstance(label, str) or not label:
            continue
        index_like = label == "板块" or label.endswith("指")
        non_stock = index_like or label.endswith(("基", "债"))
        if kind == "stock" and hq_code == expected_code and not non_stock:
            candidates.append((hq_code, market))
        elif kind == "index" and hq_code == expected_code and index_like:
            # The dictionary's Shanghai index aliases are stable source codes; all other
            # index or board identities must match the requested code exactly.
            candidates.append((hq_code, market))
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1:
        raise SourceError("tonghuashun", f"行情字典未能唯一确认 {kind} 身份：{code}")
    return candidates[0]


def _request(
    code: str, market: str, begin_time: int, end_time: int, adjustment: str,
    *, timeout: float,
) -> Any:
    return post_json(
        _KLINE_ENDPOINT,
        data={
            "code_list": [{"codes": [code], "market": market}],
            "data_fields": list(_FIELDS),
            "trade_class": "intraday",
            "time_period": "day_1",
            "trade_date": -1,
            "begin_time": begin_time,
            "end_time": end_time,
            "adjust_type": adjustment,
        },
        timeout=timeout,
        headers=_HEADERS,
        source="tonghuashun",
        follow_redirects=False,
    )


def _payload(document: Any) -> tuple[list[dict[str, Any]], Any]:
    if not isinstance(document, dict):
        raise SourceError("tonghuashun", "日 K 线响应外层结构无效")
    status = document.get("status_code")
    if isinstance(status, bool) or not isinstance(status, int) or status != 0:
        raise SourceError("tonghuashun", "日 K 线来源状态失败或缺失")
    data = document.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("quote_data"), list):
        raise SourceError("tonghuashun", "日 K 线响应缺少 quote_data")
    return data["quote_data"], data.get("fail_params")


def _values(record: dict[str, Any], code: str, market: str) -> list[dict[str, Any]]:
    if record.get("code") != code or str(record.get("market")) != market:
        raise SourceError("tonghuashun", "日 K 线响应的代码或市场与请求不一致")
    fields = record.get("data_fields")
    values = record.get("value")
    if not isinstance(fields, list) or not isinstance(values, list):
        raise SourceError("tonghuashun", "日 K 线字段或数据结构无效")
    if any(not isinstance(field, str) for field in fields) or len(set(fields)) != len(fields):
        raise SourceError("tonghuashun", "日 K 线字段定义重复或无效")
    positions = {field: index for index, field in enumerate(fields)}
    if any(field not in positions for field in ("1", "7", "8", "9", "11")):
        raise SourceError("tonghuashun", "日 K 线缺少请求字段")
    rows = []
    for raw in values:
        if not isinstance(raw, list) or len(raw) != len(fields):
            raise SourceError("tonghuashun", "日 K 线数据行与字段数量不一致")
        timestamp = to_decimal(raw[positions["1"]], "timestamp", source="tonghuashun")
        if timestamp is None or timestamp != timestamp.to_integral_value():
            raise SourceError("tonghuashun", "日 K 线时间戳无效")
        try:
            instant = datetime(1970, 1, 1, tzinfo=_UTC) + timedelta(milliseconds=int(timestamp))
            day = instant.astimezone(_SHANGHAI).date()
        except (OverflowError, ValueError) as exc:
            raise SourceError("tonghuashun", "日 K 线时间戳无效") from exc

        prices = {
            name: to_decimal(raw[positions[field]], name, source="tonghuashun")
            for name, field in (("open", "7"), ("high", "8"), ("low", "9"), ("close", "11"))
        }
        high, low = prices["high"], prices["low"]
        if high is not None and any(value is not None and value > high for value in prices.values()):
            raise SourceError("tonghuashun", "日 K 线最高价小于其他有效价格")
        if low is not None and any(value is not None and value < low for value in prices.values()):
            raise SourceError("tonghuashun", "日 K 线最低价大于其他有效价格")
        rows.append({
            "date": day.isoformat(),
            "open": to_number(prices["open"], "open", source="tonghuashun"),
            "high": to_number(high, "high", source="tonghuashun"),
            "low": to_number(low, "low", source="tonghuashun"),
            "close": to_number(prices["close"], "close", source="tonghuashun"),
            "volume": to_number(raw[positions["13"]], "volume", source="tonghuashun", integer=True, nonnegative=True) if "13" in positions else None,
            "amount": to_number(raw[positions["19"]], "amount", source="tonghuashun", nonnegative=True) if "19" in positions else None,
        })
    return rows


def _response_rows(document: Any, code: str, market: str, *, empty_ok: bool = False) -> tuple[list[dict[str, Any]], bool]:
    records, fail_params = _payload(document)
    if fail_params is not None and not isinstance(fail_params, (dict, list)):
        raise SourceError("tonghuashun", "日 K 线 fail_params 结构无效")
    if not records:
        if empty_ok:
            if isinstance(fail_params, dict) and fail_params:
                expected = [{"market": market, "codes": [code]}]
                if fail_params.get("code_list") != expected:
                    raise SourceError("tonghuashun", "空行情来源回显的代码或市场与请求不一致")
            elif isinstance(fail_params, list) and fail_params:
                raise SourceError("tonghuashun", "空行情来源无法确认请求身份")
            return [], True
        raise SourceError("tonghuashun", "日 K 线响应没有有效行情身份")
    if fail_params not in (None, {}, []) or len(records) != 1 or not isinstance(records[0], dict):
        raise SourceError("tonghuashun", "日 K 线响应记录与请求不一致")
    return _values(records[0], code, market), False


def ohlcv(
    code: str, start_date: date | str, end_date: date | str, adjustment: str | None = None,
    *, kind: str = "stock", timeout: float,
) -> list[dict[str, Any]]:
    """使用行情字典确认唯一身份后读取首尾包含的日线。"""
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise ValueError("code 必须是六位 ASCII 数字字符串")
    if not isinstance(kind, str) or kind not in {"stock", "index"}:
        raise ValueError("kind 必须是 stock 或 index")
    start = parse_date_parameter(start_date, "start_date", allow_date_object=True)
    end = parse_date_parameter(end_date, "end_date", allow_date_object=True)
    if start > end:
        raise ValueError("start_date 不得晚于 end_date")
    if adjustment is not None and (not isinstance(adjustment, str) or adjustment not in _ADJUSTMENTS):
        raise ValueError("adjustment 必须是 None、qfq 或 hfq")
    if kind == "index" and adjustment is not None:
        raise ValueError("指数日 K 线 adjustment 必须为 None")
    seconds = validate_timeout(timeout)
    hq_code, market = _identity(code, kind, timeout=seconds)
    begin_time, end_time = _day_ms(start), _day_ms(end)
    document = _request(hq_code, market, begin_time, end_time, _ADJUSTMENTS[adjustment], timeout=seconds)
    rows, ambiguous_empty = _response_rows(document, hq_code, market, empty_ok=True)
    if ambiguous_empty:
        probe = _request(hq_code, market, -1, end_time, _ADJUSTMENTS[adjustment], timeout=seconds)
        probe_rows, probe_empty = _response_rows(probe, hq_code, market, empty_ok=True)
        if probe_empty or not probe_rows:
            raise SourceError("tonghuashun", "日 K 线空窗探测未返回可确认的行情身份")
        if any(start.isoformat() <= row["date"] <= end.isoformat() for row in probe_rows):
            raise SourceError("tonghuashun", "空窗探测发现请求区间内行情，与原响应矛盾")
        return []
    filtered = [row for row in rows if start.isoformat() <= row["date"] <= end.isoformat()]
    dates = [row["date"] for row in filtered]
    if len(set(dates)) != len(dates):
        raise SourceError("tonghuashun", "日 K 线日期重复")
    return sorted(filtered, key=lambda row: row["date"])
