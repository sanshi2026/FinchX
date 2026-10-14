"""易观原生关键词搜索；正文来自搜索业务行或同 ID 正式详情。"""

import json
import math
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import unquote, urlencode, urljoin, urlsplit

from finchx._common import http
from finchx._common.errors import SourceError
from finchx._common.report_text import plain_text, to_markdown

SOURCE = "analysys"
_BASE = "https://www.analysys.cn"
_SEARCH = _BASE + "/es/eaapi"
_BEIJING = timezone(timedelta(hours=8))
_HEADERS = {**http.DEFAULT_HEADERS, "Referer": _BASE + "/es/search"}


def _identity(value) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise SourceError(SOURCE, "研报身份缺失或无效")
    return value


def _optional_text(value, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SourceError(SOURCE, f"研报{field}格式无效")
    return plain_text(value) or None


def _publication_date(value) -> str | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value):
                raise ValueError
            # eaapi 的 newsdate 为毫秒时间戳，官网按北京时间展示。
            return datetime.fromtimestamp(value / 1000, _BEIJING).date().isoformat()
        if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", value):
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").date().isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    raise SourceError(SOURCE, "研报发布日期格式无效")


class _PDFLinks(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.urls = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden += 1
        if self.hidden or tag != "a":
            return
        href = dict(attrs).get("href", "")
        if not href or re.search(r"[\s\\\x00-\x1f\x7f]", href):
            return
        url = urljoin(self.base_url, href)
        try:
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
                return
            if parts.path.lower().endswith(".pdf") and url not in self.urls:
                self.urls.append(url)
        except ValueError:
            pass

    def handle_endtag(self, tag):
        if self.hidden and tag in {"script", "style", "noscript", "template"}:
            self.hidden -= 1


def _body(html, url: str) -> tuple[str | None, list[str] | None]:
    if html is None or html == "":
        return None, None
    if not isinstance(html, str):
        raise SourceError(SOURCE, "研报正文格式无效")
    content = to_markdown(html, base_url=url, source=SOURCE)
    if content is None:
        return None, None
    parser = _PDFLinks(url)
    parser.feed(html)
    parser.close()
    return content, parser.urls


def _resource_url(value, url: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or re.search(r"[\\\x00-\x1f\x7f]|[^\S ]", value):
        raise SourceError(SOURCE, "研报资源路径无效")
    try:
        value.encode("utf-8")
        result = urljoin(url, value.replace(" ", "%20"))
        parts = urlsplit(result)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise ValueError
        parts.port
        return result
    except (ValueError, UnicodeError):
        raise SourceError(SOURCE, "研报资源路径无效") from None


def _attachments(row: dict, identity: str, url: str) -> list[str]:
    entries = row.get("articleext1")
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise SourceError(SOURCE, "研报附件格式无效")
    urls = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SourceError(SOURCE, "研报附件格式无效")
        if entry.get("ename") != "pdf":
            continue
        if _identity(entry.get("articleid")) != identity:
            raise SourceError(SOURCE, "研报附件身份不一致")
        link = _resource_url(entry.get("text"), url)
        # 只接纳实际 PDF 路径，不把登录、表单下载或 SWF 地址猜成 PDF。
        if urlsplit(link).path.lower().endswith(".pdf") and link not in urls:
            urls.append(link)
    return urls


def _candidate(row: dict, *, detail_read: bool = False) -> dict:
    if not isinstance(row, dict):
        raise SourceError(SOURCE, "研报列表记录格式无效")
    identity = _identity(row.get("id"))
    title = _optional_text(row.get("maintitle"), "标题")
    url = _BASE + "/article/detail/" + identity
    content, pdf_urls = _body(row.get("content"), url)
    content_type = "webpage" if content is not None else None
    if content is None:
        images = row.get("images")
        if images is not None and not isinstance(images, list):
            raise SourceError(SOURCE, "研报图片格式无效")
        links = []
        for image in images or []:
            if not isinstance(image, dict):
                raise SourceError(SOURCE, "研报图片格式无效")
            # 官方生产 imgDir 原样使用 path；由正式页面 URL 解析相对路径。
            link = _resource_url(image.get("path"), url)
            if link not in links:
                links.append(link)
        summary = row.get("summary")
        if summary is not None and not isinstance(summary, str):
            raise SourceError(SOURCE, "研报摘要格式无效")
        summary = to_markdown(summary or "", base_url=url, source=SOURCE)
        content = "\n\n".join(([summary] if summary else []) + [f"![]({link})" for link in links]) or None
        content_type = "webpage" if links else "summary" if content else None
    attachments = _attachments(row, identity, url)
    # 列表空附件不能证明正式页没有正文；仅摘要也仍须补正式详情。
    if pdf_urls is not None or detail_read or attachments or (content_type == "webpage" and "articleext1" in row):
        pdf_urls = list(dict.fromkeys((pdf_urls or []) + attachments))
    return {
        "source": SOURCE,
        "title": title,
        # source 是来源明确给出的机构名；author 可能是个人，不能替代机构。
        "institute": _optional_text(row.get("source"), "机构"),
        "publication_date": _publication_date(row.get("newsdate")),
        "url": url,
        "content": content,
        "content_type": content_type,
        "pdf_urls": pdf_urls,
        "_id": identity,
        "_detail_read": detail_read or (content is not None and pdf_urls is not None) or bool(pdf_urls),
    }


def search_page(keyword: str, cursor: int, *, timeout: float) -> tuple[list[dict], int | None]:
    """使用来源自己的关键词匹配；只以真实空页确认耗尽。"""
    url = _SEARCH + "?" + urlencode({"keyword": keyword, "page": cursor})
    payload = http.get_json(url, timeout=timeout, headers=_HEADERS, source=SOURCE)
    if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
        raise SourceError(SOURCE, "研报搜索响应结构无效")
    if payload.get("keyword") != keyword:
        raise SourceError(SOURCE, "研报搜索关键词不一致")
    rows = [_candidate(row) for row in payload["list"]]
    return rows, cursor + 1 if rows else None


def get_detail(candidate: dict, *, timeout: float) -> dict:
    """已有正文直接复用；缺正文时只补读同 ID 的正式公开页面。"""
    result = dict(candidate)
    if result.get("_detail_read") and result.get("pdf_urls") is not None:
        return result
    identity = _identity(result.get("_id"))
    url = _BASE + "/article/detail/" + identity
    html = http.get_text(url, timeout=timeout, headers=_HEADERS, source=SOURCE)
    # 正式页面的初始状态是 JSON，不执行脚本；article 为 URI 编码 JSON。
    marker = re.search(r"window\.__INITIAL_STATE__\s*=\s*", html)
    if marker is None:
        raise SourceError(SOURCE, "研报详情初始化数据缺失")
    try:
        state, _ = json.JSONDecoder().raw_decode(html[marker.end():])
        if not isinstance(state, dict) or state.get("isError") is True:
            raise ValueError
        encoded = state.get("article")
        if not isinstance(encoded, str):
            raise ValueError
        row = json.loads(unquote(encoded, encoding="utf-8", errors="strict"))
    except (ValueError, UnicodeError):
        raise SourceError(SOURCE, "研报详情初始化数据无效") from None
    detail = _candidate(row, detail_read=True)
    if detail["_id"] != identity:
        raise SourceError(SOURCE, "研报详情身份不一致")
    if detail["content"] is None and not detail["pdf_urls"]:
        raise SourceError(SOURCE, "研报详情正文缺失")
    detail["_detail_fields"] = tuple(field for field in ("title", "institute", "publication_date")
                                      if detail[field] is not None)
    # 搜索已有的可选元信息不因详情省略而丢失；不从其他日期别名猜测。
    for field in ("institute", "publication_date"):
        if detail[field] is None:
            detail[field] = result.get(field)
    result.update(detail)
    return result
