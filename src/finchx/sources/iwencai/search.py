"""SkillHub 独立语义检索，单次 size 最大 50。"""

from finchx._common import http
from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from ._values import SOURCE, business_url, credential, fail, json_object, limit_value, number, query_text, source_time, status, text

_SEARCH = "https://openapi.iwencai.com/v1/comprehensive/search"
_URL_KEYS = ("url", "link", "document_url", "documentUrl", "report_url", "reportUrl")


def search(query, channel="report", limit=50, *, api_key, timeout):
    query = query_text(query)
    limit_value(limit, maximum=50)
    if not isinstance(channel, str) or channel not in ("report", "announcement", "news"):
        raise ValueError("channel 必须为 report、announcement 或 news")
    key = credential(api_key, "api_key")
    headers = {
        **http.DEFAULT_HEADERS, "Authorization": f"Bearer {key}",
        "X-Claw-Call-Type": "normal", "X-Claw-Skill-Id": f"{channel}-search",
        "X-Claw-Skill-Version": "1.0.1", "X-Claw-Plugin-Id": "none", "X-Claw-Plugin-Version": "none",
    }
    failed = False
    try:
        document = http.post_json(_SEARCH, data={"channels": [channel], "app_id": "AIME_SKILL", "query": query, "size": limit},
                                  timeout=validate_timeout(timeout), headers=headers, source=SOURCE, follow_redirects=False)
    except SourceError:
        failed = True
    if failed:
        fail("检索请求失败或认证失效")
    document = json_object(document)
    status(document)
    raw = document.get("data")
    if not isinstance(raw, list):
        fail("检索结果数组结构损坏")
    rows = {}
    for item in raw:
        item = json_object(item)
        uid = text(item.get("uid"), required=True)
        extra = item.get("extra")
        if extra is None or extra == "":
            extra = {}
        else:
            extra = json_object(extra)
        urls = [business_url(mapping[name]) for mapping in (item, extra) for name in _URL_KEYS if name in mapping]
        urls = [value for value in urls if value is not None]
        if len(set(urls)) > 1:
            fail("同条检索结果链接冲突")
        rows[uid] = {
            "uid": uid, "title": text(item.get("title")),
            "published_at": source_time(item.get("publish_date")),
            "url": urls[0] if urls else None, "score": number(item.get("score")),
        }
    return list(rows.values())[:limit]
