"""同花顺当前热门话题与热门文章，按各榜单真实顺序返回。"""

import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from finchx._common.convert import to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx._common.news import validate_limit
from finchx.sources.tonghuashun._article_url import classify_article_url

_SOURCE = "tonghuashun"
_TOPIC_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/topic"
_ARTICLE_URL = "https://ai.iwencai.com/index/urp/getdata/basic"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://eq.10jqka.com.cn/"}
_PAGE_SIZE = 30
_MAX_PAGES = 1000
_TOPIC_PATHS = {"/lgt/main/frontend-main-service/topic/index.html", "/m/topic/index.html"}


def _fail(reason: str) -> None:
    raise SourceError(_SOURCE, reason)


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None or isinstance(value, str) and not value.strip():
        if not required:
            return None
    elif isinstance(value, str):
        return value
    _fail(f"字段 {field} 必须是{'非空' if required else ''}字符串")


def _integer(value: Any, field: str, *, positive: bool = False) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        result = int(value)
    else:
        _fail(f"字段 {field} 必须是整数")
    if result < (1 if positive else 0):
        _fail(f"字段 {field} 必须是{'正' if positive else '非负'}整数")
    return result


def _status(payload: Any) -> dict:
    if not isinstance(payload, dict):
        _fail("响应必须是对象")
    if type(payload.get("status_code")) not in {int, str} or payload["status_code"] not in {0, "0"}:
        _fail("来源未返回明确成功状态")
    return payload


def _url(value: Any, field: str) -> str:
    text = _text(value, field, required=True)
    if text.startswith("//"):
        text = "https:" + text
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise SourceError(_SOURCE, f"字段 {field} 地址无效") from exc
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or any(char.isspace() or ord(char) < 32 for char in text) or "\\" in text
            or port not in {None, 443 if parsed.scheme == "https" else 80}):
        _fail(f"字段 {field} 地址无效")
    return text


def _market(value: Any, field: str) -> str | None:
    if value is None:
        return None
    _integer(value, field)
    return str(value)


def _topic_securities(info: dict) -> list[dict] | None:
    values = info.get("att_stock")
    if values is None:
        return None
    if not isinstance(values, list):
        _fail("attach_info.att_stock 必须是数组或空值")
    result = []
    for raw in values:
        if not isinstance(raw, dict):
            _fail("话题关联证券结构无效")
        code = _text(raw.get("code"), "att_stock.code", required=True)
        market = _market(raw.get("market_id"), "att_stock.market_id")
        result.append({
            "code": code, "exchange": {"17": "sh", "33": "sz"}.get(market),
            "name": _text(raw.get("name"), "att_stock.name", required=True),
            "change_percent": to_number(raw.get("rise_and_fall"), "rise_and_fall", source=_SOURCE),
        })
    return result


def _topic_row(raw: Any) -> tuple[tuple[str, str], dict]:
    if not isinstance(raw, dict):
        _fail("话题行必须是对象")
    kind = raw.get("type")
    identity = _text(raw.get("code"), "topic.code", required=True)
    url = _url(raw.get("jump_url"), "jump_url")
    parsed = urlsplit(url)
    if kind == "topic":
        if (not re.fullmatch(r"T[A-Za-z0-9]{6}", identity)
                or parsed.hostname != "t.10jqka.com.cn" or parsed.path not in _TOPIC_PATHS
                or parse_qs(parsed.query, keep_blank_values=True).get("code") != [identity]
                or parsed.fragment):
            _fail("话题代码与公开目录链接身份不一致")
        target_type = "topic_list"
    elif kind == "deep_topic":
        if (not re.fullmatch(r"dt_[0-9A-Z]{26}", identity)
                or parsed.hostname != "news.10jqka.com.cn"
                or parsed.path != "/deep-topic/topic/" + identity or parsed.query or parsed.fragment):
            _fail("专题代码与公开专题链接身份不一致")
        target_type = "content"
    else:
        _fail("未确认的话题业务类型")
    info = raw.get("attach_info")
    if info is None:
        info = {}
    if not isinstance(info, dict):
        _fail("attach_info 必须是对象或空值")
    subtitle = _text(raw.get("subtitle"), "subtitle")
    attached_subtitle = _text(info.get("att_sub_title"), "att_sub_title")
    return (kind, identity), {
        "rank": None, "title": _text(raw.get("title"), "title"),
        "summary": _text(raw.get("description"), "description"),
        "subtitle": subtitle if subtitle is not None else attached_subtitle,
        "heat": to_number(raw.get("hot_value"), "hot_value", source=_SOURCE, nonnegative=True),
        "url": url, "target_type": target_type, "related_securities": _topic_securities(info),
    }


def _topics(limit: int, timeout: float) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    seen_pages: set[tuple[tuple[str, str], ...]] = set()
    stalled = 0
    for page in range(1, _MAX_PAGES + 1):
        payload = _status(get_json(_TOPIC_URL + "?" + urlencode({"page": page, "page_size": _PAGE_SIZE}),
                                   timeout=timeout, headers=_HEADERS, source=_SOURCE))
        data = payload.get("data")
        rows = data.get("topic_list") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            _fail("来源缺少 topic_list 数组")
        parsed = [_topic_row(raw) for raw in rows]
        identities = tuple(identity for identity, _ in parsed)
        if len(set(identities)) != len(identities):
            _fail("同页话题身份重复")
        if not parsed:
            break
        if identities in seen_pages:
            _fail("话题分页重复整批，没有进展")
        seen_pages.add(identities)
        old_size = len(merged)
        merged.update(parsed)
        stalled = stalled + 1 if len(merged) == old_size else 0
        if stalled >= 3:
            _fail("话题分页持续没有新身份")
        if len(merged) >= limit:
            break
    else:
        _fail("话题分页达到防护预算，未确认耗尽")
    result = list(merged.values())
    for rank, row in enumerate(result, 1):
        row["rank"] = rank
    return result[:limit]


def _article_entities(raw: dict) -> list[dict] | None:
    values = raw.get("stockInfo")
    if values is None:
        return None
    if not isinstance(values, list):
        _fail("stockInfo 必须是数组或空值")
    result = []
    for item in values:
        if not isinstance(item, dict):
            _fail("文章关联对象结构无效")
        result.append({
            "code": _text(item.get("stockCode"), "stockCode", required=True),
            "name": _text(item.get("stockName"), "stockName", required=True),
            "market": _market(item.get("stockMarket"), "stockMarket"),
            "change_percent": to_number(item.get("stockZdf"), "stockZdf", source=_SOURCE),
        })
    return result


def _article_row(raw: Any) -> tuple[tuple[str, str], dict]:
    if not isinstance(raw, dict):
        _fail("热文行必须是对象")
    kind = raw.get("newsType")
    identity = _text(raw.get("newsId"), "newsId", required=True)
    if not isinstance(kind, str) or kind not in {"news", "snslivepost"} or not re.fullmatch(r"[0-9]+", identity):
        _fail("热文业务身份无效")
    urls = raw.get("contentUrl")
    if not isinstance(urls, list) or not urls:
        _fail("热文缺少公开 contentUrl 数组")
    checked = [_url(value, "contentUrl") for value in urls]
    for url in checked:
        try:
            target_kind, _, target_id, _ = classify_article_url(url)
        except ValueError as exc:
            raise SourceError(_SOURCE, "热文公开链接无法识别") from exc
        if target_id != identity or target_kind != {"news": "news", "snslivepost": "article"}[kind]:
            _fail("热文链接与来源文章身份冲突")
    comment = to_number(raw.get("commentRatio"), "commentRatio", source=_SOURCE)
    likes = to_number(raw.get("zanRatio"), "zanRatio", source=_SOURCE)
    tag = "评论火爆" if comment is not None and 0 < comment <= 30 else (
        "点赞激增" if likes is not None and 0 < likes <= 15 else None)
    return (kind, identity), {
        "rank": _integer(raw.get("rank"), "rank", positive=True),
        "title": _text(raw.get("title"), "title"),
        "heat": to_number(raw.get("score"), "score", source=_SOURCE, nonnegative=True),
        "tag": tag, "url": checked[0], "related_entities": _article_entities(raw),
    }


def _articles(limit: int, timeout: float) -> list[dict]:
    payload = _status(get_json(_ARTICLE_URL + "?" + urlencode({"tag": "同花顺热榜_新热文", "appName": "thsHotList"}),
                               timeout=timeout, headers=_HEADERS, source=_SOURCE))
    answer = payload.get("answer")
    components = answer.get("components") if isinstance(answer, dict) else None
    if not isinstance(components, list) or len(components) != 1 or not isinstance(components[0], dict):
        _fail("热文缺少唯一排名业务块")
    data = components[0].get("data")
    rows = data.get("datas") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        _fail("热文缺少完整排名数组")
    meta = data.get("meta")
    if meta is not None:
        if not isinstance(meta, dict):
            _fail("热文排名声明结构无效")
        if "total" in meta and _integer(meta["total"], "total") != len(rows):
            _fail("热文实际窗口数量与声明不一致")
        if "extra" in meta:
            _status(meta["extra"])
    parsed = [_article_row(raw) for raw in rows]
    if len({identity for identity, _ in parsed}) != len(parsed):
        _fail("热文文章身份重复")
    if len({row["rank"] for _, row in parsed}) != len(parsed):
        _fail("热文名次重复")
    return sorted((row for _, row in parsed), key=lambda row: row["rank"])[:limit]


def hot_content(content_type: str = "topic", limit: int = 20, *, timeout: float) -> list[dict]:
    """读取当前热门话题或文章，不请求各条正文或讨论评论。"""
    if not isinstance(content_type, str) or content_type not in {"topic", "article"}:
        raise ValueError("content_type 必须是 topic 或 article")
    count = validate_limit(limit)
    seconds = validate_timeout(timeout)
    return _topics(count, seconds) if content_type == "topic" else _articles(count, seconds)
