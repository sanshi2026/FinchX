"""问财文字快照及来源网页正文；PDF 仅返回原文链接。"""

import re
from urllib.parse import parse_qsl, urlsplit

from finchx._common import http
from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from ._values import SOURCE, business_url, json_object, source_time, status, text

_DETAIL = "https://ms.10jqka.com.cn/gateway/unified-wap/v1/information/notice-detail"
_PATH = "/businesspage-outer/research-report/index.html"


class _IdentityError(SourceError):
    """不能将另一份快照当作所请求的正文。"""


def _duid(url):
    if not isinstance(url, str) or not url or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == "\\" for c in url):
        raise ValueError("url 必须为合法的官方研报链接")
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or parts.hostname != "ms.10jqka.com.cn" or parts.path != _PATH:
            raise ValueError
        if re.search(r"%(?![0-9a-fA-F]{2})", url):
            raise ValueError
        fragment_query = parts.fragment.split("?", 1)[1] if "?" in parts.fragment else ""
        pairs = parse_qsl(parts.query, keep_blank_values=True, encoding="utf-8", errors="strict")
        pairs += parse_qsl(fragment_query, keep_blank_values=True, encoding="utf-8", errors="strict")
        if any(any(ord(c) < 32 or ord(c) == 127 or c == "\\" for c in key + value) for key, value in pairs):
            raise ValueError
        ids = [value for key, value in pairs if key == "duid"]
        if not ids:
            return None
        if len(ids) != 1 or not re.fullmatch(r"[0-9A-Za-z_-]+", ids[0]):
            raise ValueError
        return ids[0]
    except (ValueError, UnicodeError):
        raise ValueError("url 必须含唯一研报 duid，且来自已支持的官方页面") from None


def _optional(value, parser=text):
    try:
        return parser(value)
    except SourceError:
        return None


def _input_url(url):
    try:
        parsed = business_url(url)
        if parsed != url or not parsed:
            raise ValueError
        return urlsplit(url)
    except (SourceError, ValueError):
        raise ValueError("url 必须为合法的 HTTP(S) 链接") from None


def _hints(uid, channel):
    if uid is not None and (not isinstance(uid, str) or not re.fullmatch(r"[0-9A-Za-z_-]+", uid)):
        raise ValueError("uid 必须为非空 ASCII 来源身份字符串或 None")
    if channel is not None and channel not in ("report", "announcement", "news"):
        raise ValueError("channel 必须为 report、announcement、news 或 None")


def _native(url, duid, kind, seconds):
    document = http.post_form_json(
        _DETAIL, data={"type": kind, "duid": duid, "query_source": "guide", "query": "*:*"},
        timeout=seconds, headers={**http.DEFAULT_HEADERS, "Origin": "https://ms.10jqka.com.cn", "Referer": url},
        source=SOURCE, follow_redirects=False,
    )
    document = json_object(document)
    status(document)
    data = json_object(document.get("data"))
    word = json_object(data.get("wordData"))
    if word.get("UID") != duid:
        raise _IdentityError(SOURCE, "文档身份与请求 uid 不一致")
    content = _optional(word.get("content"))
    link = _optional(data.get("site_url"), business_url) or _optional(word.get("URL"), business_url)
    if content is None:
        return None, link
    return {
        "title": _optional(word.get("title")),
        "publication_date": _optional(word.get("pubtime"), source_time),
        "institute": _optional(word.get("organize")),
        "researcher": _optional(word.get("researcher")),
        "content": content.replace("\r\n", "\n").replace("\r", "\n"),
        "original_url": link,
        "file_type": _optional(word.get("ext")),
    }, link


def _read_url(url, seconds):
    parts = _input_url(url)
    if parts.hostname == "stock.finance.sina.com.cn" and parts.path.startswith("/stock/go.php/vReport_Show/"):
        from finchx.sources.sina.report import get_report as sina_report
        try:
            return sina_report(url, timeout=seconds)
        except ValueError:
            pass  # 来源专用路由不支持时仍可读取合法原网页。
    # 已有公告文字接口先于 PDF 链接，身份仍由原来源解析与核对。
    from finchx.sources.eastmoney import disclosure
    try:
        disclosure._input_url(url)
    except ValueError:
        pass
    else:
        try:
            item = disclosure.em_get(url, timeout=seconds)
        except SourceError:
            pass
        else:
            if item.get("content"):
                return {"title": item.get("title"), "publication_date": item.get("notice_date"),
                        "institute": None, "researcher": None, "content": item["content"],
                        "original_url": url, "file_type": None}
    from ._document import read_document
    return read_document(url, timeout=seconds)


def get_report(url, *, uid=None, channel=None, timeout):
    """读取来源正文；可用搜索身份优先读取已核问财文字快照。"""
    parts = _input_url(url)
    _hints(uid, channel)
    seconds = validate_timeout(timeout)
    route_uid, route_channel = None, None
    if parts.hostname == "ms.10jqka.com.cn" and parts.path == _PATH:
        route_uid, route_channel = _duid(url), "report"
    elif parts.hostname in ("www.iwencai.com", "iwencai.com"):
        match = re.fullmatch(r"/viewswf/findnote/([0-9A-Za-z_-]+)\.html", parts.path)
        if match:
            route_uid, route_channel = match[1], "announcement"
    if route_uid is not None:
        if uid is not None and uid != route_uid:
            raise ValueError("uid 与已核来源路由身份冲突")
        uid, channel = route_uid, route_channel
    if uid is not None and channel in ("report", "announcement"):
        try:
            result, link = _native(url, uid, "notice" if channel == "announcement" else "report", seconds)
        except _IdentityError:
            raise
        except SourceError:
            # 快照身份冲突必须明确失败；其它不可读快照可读取原始来源。
            pass
        else:
            if result is not None:
                return result
            if link is not None:
                return _read_url(link, seconds)
    return _read_url(url, seconds)
