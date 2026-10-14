"""东方财富原生关键词研报搜索及正式网页摘要。"""

from datetime import datetime
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlencode, urljoin, urlsplit

from finchx._common import http
from finchx._common.errors import SourceError
from finchx._common.report_text import to_markdown

_SOURCE = "eastmoney"
_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
_DETAIL_URL = "http://data.eastmoney.com/report/zw_stock.jshtml"
_CALLBACK = "research"
_PAGE_SIZE = 20
_HEADERS = {**http.DEFAULT_HEADERS, "Referer": "https://so.eastmoney.com/"}
_ID = re.compile(r"AP[0-9]+", re.ASCII)


class _Page(HTMLParser):
    """只收集已核摘要容器、正式标题及原文链接。"""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []
        self.parts = []
        self.title_parts = []
        self.pdf_urls = []
        self.content_depth = None
        self.title_depth = None
        self.content_count = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if self.content_depth is not None:
            self.parts.append(self.get_starttag_text())
        if values.get("id") == "ctx-content":
            self.content_count += 1
            self.content_depth = len(self.stack)
        if values.get("id") == "zw-title":
            self.title_depth = len(self.stack)
        if tag == "a" and "pdf-link" in (values.get("class") or "").split():
            self.pdf_urls.append(values.get("href"))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag not in self.stack:
            return
        depth = len(self.stack) - 1 - self.stack[::-1].index(tag)
        if self.content_depth is not None:
            if depth == self.content_depth:
                self.content_depth = None
            else:
                self.parts.append(f"</{tag}>")
        if self.title_depth is not None and depth == self.title_depth:
            self.title_depth = None
        del self.stack[depth:]

    def handle_data(self, data):
        if self.content_depth is not None:
            self.parts.append(data)
        if self.title_depth is not None:
            self.title_parts.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _text(value, label):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SourceError(_SOURCE, f"研报{label}格式无效")
    parser = _Plain()
    parser.feed(value)
    return "".join(parser.parts).strip() or None


def _date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?: [0-9]{2}:[0-9]{2}:[0-9]{2})?", value, re.ASCII):
        raise SourceError(_SOURCE, "研报发布日期格式无效")
    try:
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S" if " " in value else "%Y-%m-%d")
    except ValueError as exc:
        raise SourceError(_SOURCE, "研报发布日期无效") from exc
    return value[:10]


def search_page(keyword: str, cursor: int, *, timeout: float) -> tuple[list[dict], int | None]:
    param = {"uid": "", "keyword": keyword, "type": ["researchReport"], "client": "web", "clientVersion": "curr", "clientType": "web", "param": {"researchReport": {"client": "web", "pageSize": _PAGE_SIZE, "pageIndex": cursor}}}
    url = _SEARCH_URL + "?" + urlencode({"cb": _CALLBACK, "param": json.dumps(param, ensure_ascii=False, separators=(",", ":"))})
    body = http.get_text(url, timeout=timeout, headers=_HEADERS, source=_SOURCE)
    match = re.fullmatch(r"\s*research\s*\((.*)\)\s*;?\s*", body, re.S)
    if match is None:
        raise SourceError(_SOURCE, "研报搜索响应不是有效的 JSONP")
    try:
        data = json.loads(match[1])
    except (json.JSONDecodeError, ValueError) as exc:
        raise SourceError(_SOURCE, "研报搜索响应不是有效的 JSON") from exc
    if not isinstance(data, dict) or type(data.get("code")) is not int or data["code"] != 0 or data.get("bizCode") not in (None, "", 0):
        raise SourceError(_SOURCE, "研报搜索状态异常或来源拒绝访问")
    result = data.get("result")
    rows = result.get("researchReport") if isinstance(result, dict) else None
    total = data.get("hitsTotal")
    if not isinstance(rows, list) or type(total) is not int or total < 0:
        raise SourceError(_SOURCE, "研报搜索结果结构无效")
    reports = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("code"), str) or not _ID.fullmatch(row["code"]):
            raise SourceError(_SOURCE, "研报搜索身份无效")
        reports.append({"source": _SOURCE, "title": _text(row.get("title"), "标题"), "institute": _text(row.get("source"), "机构"), "publication_date": _date(row.get("date")), "url": _DETAIL_URL + "?" + urlencode({"infocode": row["code"]}), "content": None, "content_type": None, "pdf_urls": None, "_id": row["code"], "_date_text": row.get("date")})
    return reports, None if not rows or cursor * _PAGE_SIZE >= total else cursor + 1


def _link(value, base_url):
    if not isinstance(value, str) or not value.strip():
        return None
    url = urljoin(base_url, value.strip())
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() or ord(c) < 32 for c in url):
            return None
        parsed.port
    except ValueError:
        return None
    return url


def get_detail(candidate: dict, *, timeout: float) -> dict:
    url = candidate["url"]
    body = http.get_text(url, timeout=timeout, headers=_HEADERS, source=_SOURCE)
    page = _Page()
    page.feed(body)
    if page.content_count > 1 or page.content_depth is not None:
        raise SourceError(_SOURCE, "研报摘要结构无效")
    # 正式网页内嵌的 JSON 仅作身份与可选元信息核对，不执行脚本。
    metadata = {}
    marker = re.search(r"\bvar\s+zwinfo\s*=\s*", body)
    if marker:
        try:
            metadata, _ = json.JSONDecoder().raw_decode(body[marker.end():])
        except ValueError as exc:
            raise SourceError(_SOURCE, "研报详情身份数据损坏") from exc
        if not isinstance(metadata, dict):
            raise SourceError(_SOURCE, "研报详情身份数据损坏")
    identities = []
    if metadata.get("info_code") is not None:
        identities.append(metadata["info_code"])
    identities.extend(re.findall(r"\bvar\s+_us_zixun_Id\s*=\s*['\"]([^'\"]+)['\"]", body))
    if any(identity != candidate["_id"] for identity in identities):
        raise SourceError(_SOURCE, "研报详情身份与搜索记录不一致")
    pdf_urls = []
    for value in page.pdf_urls:
        link = _link(value, url)
        if link is not None and link not in pdf_urls:
            pdf_urls.append(link)
    content = to_markdown("".join(page.parts), base_url=url, source=_SOURCE) if page.content_count else None
    if not content and not pdf_urls:
        raise SourceError(_SOURCE, "研报详情缺少可读摘要及原文链接，或来源限制访问")
    output = dict(candidate)
    output.update(content=content, content_type="summary" if content else None, pdf_urls=pdf_urls)
    title = _text("".join(page.title_parts), "标题") or _text(metadata.get("notice_title"), "标题")
    if title is not None:
        output["title"] = title
    if metadata.get("source_sample_name") not in (None, ""):
        output["institute"] = _text(metadata["source_sample_name"], "机构")
    if metadata.get("notice_date") not in (None, ""):
        output["publication_date"] = _date(metadata["notice_date"])
    return output
