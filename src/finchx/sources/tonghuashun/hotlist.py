"""同花顺当前股票、板块、可转债与 ETF 热榜。"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json, post_json

_SOURCE = "tonghuashun"
_BASE = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/"
_STOCK = _BASE + "stock"
_NEW_STOCK = "https://eq.10jqka.com.cn/open/api/hot_list/rank/v1/new_stock.txt"
_PLATE = _BASE + "plate"
_BOND = _BASE + "bond"
_INDEX = "https://dq.10jqka.com.cn/fuyao/fund_fe_tools/fund/v1/index_sector"
_RECOMMEND = "https://fund.10jqka.com.cn/quotation/fund/recommend/v1/batch/single"
_INDEX_ETF_QUOTES = "https://fund.10jqka.com.cn/datahub/dataapi/fetch/outer/v1/specific_data"
_POOL = "https://fund.10jqka.com.cn/quotation/fund_pool/v2/query"
_METRICS = "https://fund.10jqka.com.cn/quotation/temp/data_api/fetch/v1/specific_data"
_TAGS = "https://dataq.10jqka.com.cn/dataapi/tagservice/fetch/v1/tag_data"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://eq.10jqka.com.cn/webpage/ths-hot-list/index.html"}
_FUND_HEADERS = {**_HEADERS, "Source-Id": "ths-hot-list"}
_STOCK_TYPES = {"popular": "normal", "rising": "skyrocket", "technical": "tech", "value": "value", "trend": "trend"}
_POOL_KEYS = {
    "popular": "347c9f28-8a67-48a7-8c05-380ff8e595c7",
    "t0": "fa2c6ba4-c243-4057-af9a-3dfe2d98d73b",
    "price_limit_20": "8dfbaf18-9408-331a-93cd-1b2174e64619",
    "cross_border": "8c2b110c-8913-4fc0-bd31-0d298e9d2ff2",
    "commodity": "847cee32-8433-4d62-b379-833410f600c1",
}
_TAG_KEYS = ("ifund_etf_t0", "ifund_biz_FS34806_tech_side", "ifund_biz_FS34806_fund_side")
_CODE = re.compile(r"[0-9]{6}")
_INDEX_CODE = re.compile(r"([0-9]+):([A-Za-z0-9]+)")
_UPDATED = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
_POOL_PAGE_SIZE = 10000
_MAX_POOL_PAGES = 1000
_POOL_ROUNDS = 3


def _fail(reason: str) -> None:
    raise SourceError(_SOURCE, reason)


def _object(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        _fail(f"{field} 必须是对象")
    return value


def _array(value: Any, field: str) -> list:
    if not isinstance(value, list):
        _fail(f"{field} 必须是数组")
    return value


def _status(payload: Any) -> dict:
    value = _object(payload, "来源响应")
    status = value.get("status_code")
    if type(status) not in {int, str} or status not in {0, "0"}:
        _fail("来源未返回明确成功状态")
    if "success" in value and value["success"] is not True:
        _fail("来源 success 状态不是成功")
    return value


def _get(url: str, timeout: float) -> dict:
    return _status(get_json(url, timeout=timeout, headers=_HEADERS, source=_SOURCE))


def _post(url: str, data: dict, timeout: float, *, fund: bool = False) -> dict:
    return _status(post_json(url, data=data, timeout=timeout,
                             headers=_FUND_HEADERS if fund else _HEADERS, source=_SOURCE))


def _limit(value: Any) -> int | None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError("limit 必须是非布尔正整数或 None")
    return value


def _choice(value: Any, name: str, choices: set | dict) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{name} 必须是 {'/'.join(sorted(choices))}")
    return value


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None or isinstance(value, str) and not value.strip():
        if not required:
            return None
    elif isinstance(value, str):
        return value
    _fail(f"字段 {field} 必须是{'非空' if required else ''}字符串")


def _integer(value: Any, field: str, *, positive: bool = False) -> int:
    if type(value) is int:
        number = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        number = int(value)
    else:
        _fail(f"字段 {field} 必须是整数")
    if number < (1 if positive else 0):
        _fail(f"字段 {field} 必须是{'正' if positive else '非负'}整数")
    return number


def _market(value: Any, field: str) -> str:
    return str(_integer(value, field, positive=True))


def _code(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _CODE.fullmatch(value):
        _fail(f"字段 {field} 必须是六位 ASCII 数字字符串")
    return value


def _security(code: Any, market: Any, kind: str) -> tuple[str, str]:
    code = _code(code, kind + ".code")
    market = _market(market, kind + ".market")
    if kind == "stock":
        exchange = {"17": "sh", "33": "sz", "151": "bj"}.get(market)
        prefixes = {}
    elif kind == "bond":
        exchange = {"19": "sh", "35": "sz"}.get(market)
        prefixes = {"sh": ("11",), "sz": ("12",)}
    else:
        exchange = {"20": "sh", "36": "sz"}.get(market)
        prefixes = {"sh": ("5",), "sz": ("1",)}
    if exchange is None or kind != "stock" and not code.startswith(prefixes[exchange]):
        _fail(f"{kind} 的来源市场与证券代码身份无效或冲突")
    return code, exchange


def _fund_identity(value: Any, field: str) -> tuple[str, str, str]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+:[0-9]{6}", value):
        _fail(f"字段 {field} 必须是完整市场:ETF代码")
    market, code = value.split(":")
    code, exchange = _security(code, market, "etf")
    if market != str(int(market)):
        _fail(f"字段 {field} 的市场身份无效")
    return value, code, exchange


def _rank(raw: dict) -> int:
    value = raw.get("display_order")
    return _integer(raw.get("order") if value is None else value, "rank", positive=True)


def _empty_related_market(value: Any) -> bool:
    if isinstance(value, bool):
        _fail("关联 ETF 的来源市场类型无效")
    if value is None or value == "":
        return True
    return _integer(value, "etf_market_id") == 0


def _number(value: Any, field: str, *, nonnegative: bool = False, integer: bool = False):
    return to_number(value, field, source=_SOURCE, nonnegative=nonnegative, integer=integer)


def _strings(value: Any, field: str) -> list[str] | None:
    if value is None:
        return None
    return [_text(item, field, required=True) for item in _array(value, field)]


def _updated(value: Any) -> str | None:
    text = _text(value, "update_time")
    if text is None:
        return None
    if not _UPDATED.fullmatch(text):
        _fail("来源 update_time 不是有效秒时刻")
    try:
        moment = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise SourceError(_SOURCE, "来源 update_time 日期时刻无效") from exc
    return moment.replace(tzinfo=timezone(timedelta(hours=8))).isoformat()


def _ranked(rows: list, parser, limit: int | None) -> list[dict]:
    result = []
    identities = set()
    ranks = set()
    for raw in rows:
        identity, row = parser(_object(raw, "榜单行"))
        if identity in identities or row["rank"] in ranks:
            _fail("同份榜单存在重复身份或名次")
        identities.add(identity)
        ranks.add(row["rank"])
        result.append(row)
    result.sort(key=lambda row: row["rank"])
    return result if limit is None else result[:limit]


def _stock_row(raw: dict, category: str) -> tuple[tuple, dict]:
    code, exchange = _security(raw.get("code"), raw.get("market"), "stock")
    tag = raw.get("tag")
    if tag is not None:
        tag = _object(tag, "tag")
    tag = tag or {}
    row = {
        "rank": _rank(raw), "code": code, "exchange": exchange,
        "name": _text(raw.get("name"), "name"),
        "change_percent": _number(raw.get("rise_and_fall"), "rise_and_fall"),
        "heat": _number(raw.get("rate"), "rate", nonnegative=True),
        "rank_change": _number(raw.get("hot_rank_chg"), "hot_rank_chg", integer=True),
        "concept_tags": _strings(tag.get("concept_tag"), "concept_tag"),
        "popularity_tag": _text(tag.get("popularity_tag"), "popularity_tag"),
        "analysis_title": _text(raw.get("analyse_title"), "analyse_title"),
        "analysis": _text(raw.get("analyse"), "analyse"),
        "search_count": _number(raw.get("search_cnt"), "search_cnt", nonnegative=True, integer=True),
        "updated_at": _updated(raw.get("update_time")),
        "issue_pe": _number(raw.get("pe"), "pe") if category == "new" else None,
    }
    return (exchange, code), row


def stocks(category: str = "popular", period: str | None = None, limit: int | None = 20, *, timeout: float) -> list[dict]:
    category = _choice(category, "category", set(_STOCK_TYPES) | {"new"})
    limit = _limit(limit)
    seconds = validate_timeout(timeout)
    if period is None:
        period = "1h" if category in {"popular", "rising"} else "24h"
    _choice(period, "period", {"1h", "24h"})
    if category not in {"popular", "rising"} and period != "24h":
        raise ValueError("new/technical/value/trend 仅支持 period='24h'")
    url = _NEW_STOCK if category == "new" else _STOCK + "?" + urlencode({
        "stock_type": "a", "list_type": _STOCK_TYPES[category], "type": "hour" if period == "1h" else "day"})
    data = _object(_get(url, seconds).get("data"), "data")
    return _ranked(_array(data.get("stock_list"), "stock_list"), lambda row: _stock_row(row, category), limit)


def _plate_row(raw: dict) -> tuple[str, dict]:
    code = _code(raw.get("code"), "plate.code")
    if _market(raw.get("market_id"), "market_id") != "48":
        _fail("板块来源市场身份无效")
    related_code = _text(raw.get("etf_product_id"), "etf_product_id")
    related_market = raw.get("etf_market_id")
    if related_code is not None:
        related_code, related_exchange = _security(related_code, related_market, "etf")
    else:
        related_exchange = None
        if not _empty_related_market(related_market):
            _fail("关联 ETF 缺少代码身份")
    row = {
        "rank": _rank(raw), "sector_code": code, "name": _text(raw.get("name"), "name"),
        "change_percent": _number(raw.get("rise_and_fall"), "rise_and_fall"),
        "heat": _number(raw.get("rate"), "rate", nonnegative=True),
        "rank_change": _number(raw.get("hot_rank_chg"), "hot_rank_chg", integer=True),
        "tag": _text(raw.get("tag"), "tag"), "hot_tag": _text(raw.get("hot_tag"), "hot_tag"),
        "related_etf_code": related_code, "related_etf_exchange": related_exchange,
        "related_etf_name": _text(raw.get("etf_name"), "etf_name"),
        "related_etf_change_percent": _number(raw.get("etf_rise_and_fall"), "etf_rise_and_fall"),
    }
    return code, row


def _metric_data(payload: dict, required: tuple[str, ...], *, field: str) -> tuple[dict, list]:
    data = _object(payload.get("data"), field)
    indexes = _array(data.get("indexes"), field + ".indexes")
    positions = {}
    for position, entry in enumerate(indexes):
        entry = _object(entry, field + ".indexes 行")
        name = _text(entry.get("index_id"), "index_id", required=True)
        idx = _integer(entry.get("idx", position), "index.idx")
        if idx in positions or name in positions.values():
            _fail("指标定义存在重复身份")
        positions[idx] = name
    if not set(required) <= set(positions.values()):
        _fail("来源缺少必要指标定义")
    return positions, _array(data.get("data"), field + ".data")


def _values(raw: dict, indexes: dict, required: tuple[str, ...]) -> dict:
    result = {name: None for name in required}
    seen = set()
    for item in _array(raw.get("values"), "values"):
        item = _object(item, "values 行")
        idx = _integer(item.get("idx"), "values.idx")
        if idx in seen:
            _fail("同一证券存在重复指标")
        seen.add(idx)
        name = indexes.get(idx)
        if name in result:
            result[name] = item.get("value")
    return result


def _index_sectors(timeout: float, limit: int | None) -> list[dict]:
    payload = _post(_INDEX, {"page_info": {"page_begin": 0, "page_size": 20}}, timeout)
    needed = ("security_name", "price_change_ratio_pct", "ths-hot-data-minute-attention-rate")
    indexes, raw_rows = _metric_data(payload, needed, field="指数板块")
    rows = []
    seen = set()
    unique_id = ""
    for position, value in enumerate(raw_rows, 1):
        raw = _object(value, "指数板块行")
        code = _text(raw.get("code"), "index.code", required=True)
        if not _INDEX_CODE.fullmatch(code) or code in seen:
            _fail("指数板块来源身份无效或重复")
        seen.add(code)
        values = _values(raw, indexes, needed)
        if not unique_id:
            for key in ("uniqueId", "unique_id", "id"):
                if isinstance(raw.get(key), str) and raw[key].strip():
                    unique_id = raw[key]
                    break
        rows.append({
            "rank": position, "sector_code": code,
            "name": _text(values["security_name"], "security_name"),
            "change_percent": _number(values["price_change_ratio_pct"], "price_change_ratio_pct"),
            "heat": _number(values["ths-hot-data-minute-attention-rate"], "attention-rate", nonnegative=True),
            "rank_change": None, "tag": None, "hot_tag": None,
            "related_etf_code": None, "related_etf_exchange": None,
            "related_etf_name": None, "related_etf_change_percent": None,
        })
    if not rows:
        return []
    recommended = _array(_post(_RECOMMEND, {"stockCodeList": [row["sector_code"] for row in rows],
                                           "uniqueId": unique_id}, timeout).get("data"), "ETF推荐")
    recommendations = {}
    funds = set()
    for item in recommended:
        item = _object(item, "ETF推荐行")
        identity = _text(item.get("stockCode"), "stockCode", required=True)
        if identity not in seen or identity in recommendations:
            _fail("ETF推荐的指数身份冲突或重复")
        code = _text(item.get("etfCode"), "etfCode")
        market = item.get("etfMarket")
        if code is None:
            if not _empty_related_market(market):
                _fail("ETF推荐缺少代码身份")
            recommendations[identity] = (None, None, _text(item.get("etfName"), "etfName"), None)
        else:
            code, exchange = _security(code, market, "etf")
            full_code = _market(market, "etfMarket") + ":" + code
            funds.add(full_code)
            recommendations[identity] = (code, exchange, _text(item.get("etfName"), "etfName"), full_code)
    quotes = {}
    if funds:
        payload = _post(_INDEX_ETF_QUOTES, {
            "data_key": "101", "enable_default": False,
            "indexes": [{"index_id": "security_name"}, {"index_id": "price_change_ratio_pct"}],
            "code_selectors": {"include": [{"type": "stock_code", "values": sorted(funds)}]},
        }, timeout)
        needed = ("price_change_ratio_pct",)
        indexes, quoted = _metric_data(payload, needed, field="关联ETF行情")
        for item in quoted:
            item = _object(item, "关联ETF行情行")
            identity, _, _ = _fund_identity(item.get("code"), "quote.code")
            if identity not in funds or identity in quotes:
                _fail("关联 ETF 行情身份冲突或重复")
            values = _values(item, indexes, needed)
            quotes[identity] = _number(values["price_change_ratio_pct"], "price_change_ratio_pct")
        if set(quotes) != funds:
            _fail("关联 ETF 行情身份不完整")
    for row in rows:
        recommendation = recommendations.get(row["sector_code"])
        if recommendation is not None:
            code, exchange, name, full_code = recommendation
            row.update(related_etf_code=code, related_etf_exchange=exchange,
                       related_etf_name=name, related_etf_change_percent=quotes.get(full_code))
    return rows if limit is None else rows[:limit]


def sectors(sector_type: str = "concept", limit: int | None = 20, *, timeout: float) -> list[dict]:
    sector_type = _choice(sector_type, "sector_type", {"concept", "industry", "index"})
    limit = _limit(limit)
    seconds = validate_timeout(timeout)
    if sector_type == "index":
        return _index_sectors(seconds, limit)
    data = _object(_get(_PLATE + "?" + urlencode({"type": sector_type}), seconds).get("data"), "data")
    return _ranked(_array(data.get("plate_list"), "plate_list"), _plate_row, limit)


def _bond_row(raw: dict) -> tuple[tuple, dict]:
    code, exchange = _security(raw.get("code"), raw.get("market"), "bond")
    return (exchange, code), {
        "rank": _rank(raw), "code": code, "exchange": exchange,
        "name": _text(raw.get("name"), "name"),
        "change_percent": _number(raw.get("rise_and_fall"), "rise_and_fall"),
        "heat": _number(raw.get("hot"), "hot", nonnegative=True),
    }


def convertible_bonds(limit: int | None = 20, *, timeout: float) -> list[dict]:
    limit = _limit(limit)
    seconds = validate_timeout(timeout)
    return _ranked(_array(_get(_BOND, seconds).get("data"), "data"), _bond_row, limit)


def _pool_page(payload: dict, offset: int) -> tuple[int, list[tuple[str, dict]], int]:
    data = _object(payload.get("data"), "基金池 data")
    total = _integer(data.get("total"), "pool.total")
    if _integer(data.get("offset"), "pool.offset") != offset:
        _fail("基金池来源偏移与请求不一致")
    declared_size = _integer(data.get("limit"), "pool.limit", positive=True)
    indexes = _array(data.get("indexes"), "pool.indexes")
    positions = {}
    for idx, definition in enumerate(indexes):
        name = _text(_object(definition, "pool.indexes 行").get("type"), "pool.indexes.type", required=True)
        if name in positions:
            _fail("基金池字段定义重复")
        positions[name] = idx
    if not {"code", "etfName", "subMarket", "tradeCode"} <= positions.keys():
        _fail("基金池缺少必要字段定义")
    raw_rows = _array(data.get("itemList"), "pool.itemList")
    if len(raw_rows) > declared_size or len(raw_rows) > total - offset:
        _fail("基金池页面数量超过声明")
    result = []
    seen = set()
    for raw in raw_rows:
        raw = _array(raw, "基金池行")
        if len(raw) != len(indexes):
            _fail("基金池行与字段定义不匹配")
        identity, code, exchange = _fund_identity(raw[positions["code"]], "pool.code")
        if identity in seen:
            _fail("同页基金池身份重复")
        seen.add(identity)
        market = raw[positions["subMarket"]]
        if market is not None and market != "":
            if _market(market, "subMarket") != identity.split(":")[0]:
                _fail("基金池市场身份冲突")
        if _code(raw[positions["tradeCode"]], "tradeCode") != code:
            _fail("基金池交易代码身份冲突")
        result.append((identity, {"code": code, "exchange": exchange,
                                  "name": _text(raw[positions["etfName"]], "etfName")}))
    if len(raw_rows) != min(declared_size, max(0, total - offset)):
        _fail("基金池提前短页")
    return total, result, len(raw_rows)


def _fund_pool(category: str, timeout: float) -> dict:
    result = {}
    total = None
    pages = 0
    for _ in range(_POOL_ROUNDS):
        offset = 0
        while total is None or offset < total:
            pages += 1
            if pages > _MAX_POOL_PAGES:
                _fail("基金池分页达到防护预算，不能返回部分榜单")
            payload = _post(_POOL, {"businessPoolKey": _POOL_KEYS[category], "custom": {
                "fieldList": ["etfName", "subMarket", "tradeCode"], "offset": offset, "limit": _POOL_PAGE_SIZE,
            }}, timeout)
            count, rows, length = _pool_page(payload, offset)
            if total is not None and count != total:
                _fail("基金池 total 在分页期间变化")
            total = count
            result.update(rows)
            if len(result) > total:
                _fail("基金池唯一身份数超过声明")
            offset += length
            if length == 0:
                break
        if len(result) == total:
            return result
    _fail("基金池跨页补取后身份仍不完整")


def _fund_metrics(pool: dict, timeout: float) -> list[tuple[str, dict]]:
    identities = list(pool)
    if not identities:
        return []
    payload = _post(_METRICS, {
        "code_selectors": {"include": [{"type": "stock_code", "values": identities}]},
        "indexes": [{"index_id": "price_change_ratio_pct"}, {"index_id": "ths-hot-data-day-attention-rate"}],
        "sort": [{"idx": 1, "order": "desc"}],
        "page_info": {"page_begin": 0, "page_size": len(identities)},
    }, timeout, fund=True)
    needed = ("price_change_ratio_pct", "ths-hot-data-day-attention-rate")
    indexes, raw_rows = _metric_data(payload, needed, field="ETF指标")
    if _integer(payload["data"].get("total"), "metrics.total") != len(pool):
        _fail("ETF指标声明数量与完整基金池不一致")
    result = []
    seen = set()
    for item in raw_rows:
        raw = _object(item, "ETF指标行")
        identity, _, _ = _fund_identity(raw.get("code"), "metrics.code")
        if identity not in pool or identity in seen:
            _fail("ETF指标身份冲突或重复")
        seen.add(identity)
        values = _values(raw, indexes, needed)
        row = {**pool[identity],
               "change_percent": _number(values["price_change_ratio_pct"], "price_change_ratio_pct"),
               "heat": _number(values["ths-hot-data-day-attention-rate"], "attention-rate", nonnegative=True)}
        result.append((identity, row))
    if seen != pool.keys():
        _fail("ETF指标身份未完整覆盖基金池")
    result.sort(key=lambda item: (item[1]["heat"] is None,
                -item[1]["heat"] if item[1]["heat"] is not None else 0,
                item[1]["exchange"], item[1]["code"]))
    return result


def _fund_tags(identities: list[str], timeout: float) -> dict:
    if not identities:
        return {}
    payload = _post(_TAGS, {
        "code_selectors": {"include": [{"type": "stock_code", "values": identities}]},
        "tag_infos": [{"tag_key": key} for key in _TAG_KEYS],
    }, timeout, fund=True)
    data = _object(payload.get("data"), "ETF标签 data")
    positions = {}
    definitions = data.get("tag_infos")
    if definitions is not None:
        for position, definition in enumerate(_array(definitions, "tag_infos")):
            definition = _object(definition, "tag_infos 行")
            key = _text(definition.get("tag_key"), "tag_infos.tag_key", required=True)
            idx = _integer(definition.get("idx", position), "tag_infos.idx")
            if idx in positions:
                _fail("标签定义索引重复")
            positions[idx] = key
    result = {}
    expected = set(identities)
    for item in _array(data.get("data"), "ETF标签 data.data"):
        raw = _object(item, "ETF标签行")
        identity, _, _ = _fund_identity(raw.get("code"), "tags.code")
        if identity not in expected or identity in result:
            _fail("ETF标签身份冲突或重复")
        groups = raw.get("values")
        if groups is None:
            result[identity] = None
            continue
        tags = []
        seen = set()
        missing = False
        provided = not groups
        for group in _array(groups, "ETF标签 values"):
            group = _object(group, "ETF标签组")
            key = group.get("tag_key")
            defined_key = None
            if "idx" in group:
                defined_key = positions.get(_integer(group["idx"], "tag.idx"))
            if key is not None:
                key = _text(key, "tag_key", required=True)
                if defined_key is not None and key != defined_key:
                    _fail("标签标识与定义索引冲突")
            else:
                key = defined_key
                if key is None and "idx" not in group:
                    _fail("ETF标签组缺少标识")
            if key not in _TAG_KEYS:
                continue
            if key in seen:
                _fail("同一 ETF 标签组重复")
            seen.add(key)
            values = _strings(group.get("show_tag"), "show_tag")
            if values is None:
                missing = True
            else:
                provided = True
                tags.extend(values)
        result[identity] = list(dict.fromkeys(tags)) if tags or provided and not missing else None
    if result.keys() != expected:
        _fail("ETF标签身份未完整覆盖所选榜单")
    return result


def etfs(category: str = "popular", limit: int | None = 20, *, timeout: float) -> list[dict]:
    category = _choice(category, "category", _POOL_KEYS)
    limit = _limit(limit)
    seconds = validate_timeout(timeout)
    ranked = _fund_metrics(_fund_pool(category, seconds), seconds)
    selected = ranked if limit is None else ranked[:limit]
    tags = _fund_tags([identity for identity, _ in selected], seconds)
    return [{"rank": position, **row, "tags": tags[identity]}
            for position, (identity, row) in enumerate(selected, 1)]
