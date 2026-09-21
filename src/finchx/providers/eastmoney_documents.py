"""EastMoney source adapters for individual-stock news and disclosures.

The module intentionally keeps source fields in typed Provider rows.  Public
Dataset models are produced by the normalizers in ``finchx.datasets`` and do
not expose EastMoney query parameters or wire-field names.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import re
from typing import Any, NoReturn
from urllib.parse import urlencode

from finchx.contracts import Source
from finchx.datasets.disclosure import (
    DisclosureSearchRequest,
    _ProviderDisclosureAttachment,
    _ProviderDisclosureCategory,
    _ProviderDisclosureRow,
    _ProviderDisclosureSecurity,
)
from finchx.datasets.news import NewsSearchRequest, _ProviderNewsRow
from finchx.entities import Exchange, InstrumentId, Market, InstrumentKind
from finchx.providers.eastmoney_market import (
    _EastmoneyTransport,
    _EastmoneyTransportFailure,
    _UrllibEastmoneyTransport,
)
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, build_headers, http_status_failure_reason


EASTMONEY_NEWS_LIST_ENDPOINT = "https://np-listapi.eastmoney.com/comm/web/getListInfo"
EASTMONEY_NEWS_DETAIL_ENDPOINT = "https://finance.eastmoney.com/a"
EASTMONEY_DISCLOSURE_LIST_ENDPOINT = "https://np-anotice-stock.eastmoney.com/api/security/ann"
EASTMONEY_DISCLOSURE_CONTENT_ENDPOINT = "https://np-cnotice-stock.eastmoney.com/api/content/ann"
EASTMONEY_DISCLOSURE_PAGE_ENDPOINT = "https://data.eastmoney.com/notices/detail"

_TIMEZONE = timezone(timedelta(hours=8))
_JSONP = re.compile(r"^\s*[A-Za-z_$][A-Za-z0-9_$.]*\s*\((.*)\)\s*;?\s*$", re.DOTALL)
_NEWS_ID = re.compile(r"^[0-9]{12,24}$")
_DISCLOSURE_ID = re.compile(r"^AN[0-9]{12,24}$")
_NEWS_ROW_FIELDS = frozenset(
    {"Art_ShowTime", "Art_Code", "Np_dst", "Art_Title", "Art_SortStart", "Art_OriginUrl", "Art_Url"}
)
_DISCLOSURE_ROW_FIELDS = frozenset(
    {
        "art_code", "codes", "columns", "display_time", "eiTime", "language",
        "listing_state", "notice_date", "product_code", "sort_date", "source_type",
        "title", "title_ch", "title_en",
    }
)
_DISCLOSURE_SECURITY_FIELDS = frozenset(
    {"ann_type", "inner_code", "market_code", "short_name", "stock_code"}
)
_DISCLOSURE_COLUMN_FIELDS = frozenset({"column_code", "column_name"})
_CONTENT_FIELDS = frozenset(
    {
        "art_code", "attach_list", "attach_list_ch", "attach_list_en", "attach_size",
        "attach_type", "attach_url", "attach_url_web", "eitime", "extend", "is_ai_summary",
        "is_rich", "is_rich2", "language", "notice_content", "notice_date", "notice_title",
        "page_size", "page_size_ch", "page_size_cht", "page_size_en", "security", "short_name",
    }
)
_CONTENT_ATTACHMENT_FIELDS = frozenset({"attach_size", "attach_type", "attach_url", "seq"})
_CONTENT_SECURITY_FIELDS = frozenset(
    {"market_uni", "short_name", "short_name_ch", "short_name_cht", "short_name_en", "stock"}
)


@dataclass(frozen=True)
class _ProviderDocumentPage:
    rows: tuple[Any, ...]
    page_index: int
    page_size: int
    total_hits: int | None
    request_url: str
    next_page_token: str | None = None


@dataclass(frozen=True)
class _ParsedNewsHtml:
    title: str
    published_at: datetime | None
    source_name: str | None
    content_text: str


class _Node:
    def __init__(self, tag: str = "__root__", attrs: Mapping[str, str] | None = None) -> None:
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children: list[_Node | str] = []


class _HtmlTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node()
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.casefold(), {key.casefold(): value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        if tag.casefold() not in {"br", "img", "hr", "meta", "input", "link"}:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self._stack[-1].tag == tag.casefold():
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        wanted = tag.casefold()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == wanted:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1].children.append(data)


def _walk(node: _Node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _walk(child)


def _plain_text(node: _Node) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag not in {"script", "style", "noscript"}:
            parts.append(_plain_text(child))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


_BLOCK_TAGS = {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"}
_SKIP_CLASSES = {"ad_context1", "ad_context2", "ad_context3", "ad_context4"}


def _render_content(node: _Node) -> str:
    if node.tag in {"script", "style", "noscript"}:
        return ""
    classes = set(node.attrs.get("class", "").split())
    if classes & _SKIP_CLASSES or node.attrs.get("id") in {"ad_context1", "ad_context2", "ad_context3", "ad_context4"}:
        return ""
    if node.tag == "br":
        return "\n"
    if node.tag == "tr":
        cells = []
        for child in node.children:
            if isinstance(child, _Node) and child.tag in {"td", "th"}:
                text = _render_content(child).strip()
                if text:
                    cells.append(text)
        return " | ".join(cells) + "\n"
    if node.tag in {"td", "th"}:
        return "".join(_render_content(child) if isinstance(child, _Node) else child for child in node.children)
    body = "".join(_render_content(child) if isinstance(child, _Node) else child for child in node.children)
    if node.tag in _BLOCK_TAGS or node.tag == "table":
        return body.strip() + "\n"
    return body


def _find_by_id(root: _Node, identifier: str) -> _Node | None:
    for node in _walk(root):
        if node.attrs.get("id") == identifier:
            return node
    return None


def _find_class(root: _Node, class_name: str) -> _Node | None:
    for node in _walk(root):
        if class_name in node.attrs.get("class", "").split():
            return node
    return None


def _parse_html_news(text: str, *, document_id: str) -> _ParsedNewsHtml:
    parser = _HtmlTreeParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise ValueError(f"news HTML parser failed: {type(exc).__name__}") from exc
    body = _find_by_id(parser.root, "ContentBody")
    if body is None:
        raise ValueError("news HTML omitted #ContentBody")
    content = re.sub(r"\n{3,}", "\n\n", _render_content(body)).strip()
    if not content:
        raise ValueError("news HTML ContentBody was empty")
    topbox = _find_by_id(parser.root, "topbox")
    title_node = _find_class(topbox, "title") if topbox is not None else _find_class(parser.root, "title")
    title = _plain_text(title_node) if title_node is not None else ""
    if not title:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
        title = re.sub(r"\s*[_-]\s*东方财富网\s*$", "", title_match.group(1)).strip() if title_match else ""
    if not title:
        raise ValueError("news HTML omitted a title")
    full_text = _plain_text(parser.root)
    time_match = re.search(r"([0-9]{4})年([0-9]{2})月([0-9]{2})日\s*([0-9]{2}):([0-9]{2})", full_text)
    published = None
    if time_match:
        published = datetime(
            *(int(item) for item in time_match.groups()), tzinfo=_TIMEZONE
        )
    source_match = re.search(r"(?:来源|文章来源)：\s*([^\s责任编辑<]+)", full_text)
    source_name = source_match.group(1).strip() if source_match else None
    return _ParsedNewsHtml(title, published, source_name, content)


class _EastmoneyDocumentProviderBase:
    def __init__(
        self,
        transport: _EastmoneyTransport | None = None,
        *,
        clock: Any | None = None,
        headers: Mapping[str, str],
    ) -> None:
        self._transport = transport or _UrllibEastmoneyTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._headers = dict(headers)

    def _request_json(
        self,
        endpoint: str,
        params: Mapping[str, str | int],
    ) -> tuple[dict[str, Any], str]:
        request_url = f"{endpoint}?{urlencode(params)}" if params else endpoint
        try:
            response = self._transport.get(
                endpoint,
                params=params,
                headers=self._headers,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
        except _EastmoneyTransportFailure as exc:
            self._fail(f"EastMoney transport failure: {exc}")
        except Exception as exc:
            self._fail(f"EastMoney transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"EastMoney returned {status_reason}")
        if not response.text.strip():
            self._fail("EastMoney returned an empty body")
        candidate = response.text.strip()
        matched = _JSONP.fullmatch(candidate)
        if matched is not None:
            candidate = matched.group(1)
        try:
            document = json.loads(candidate)
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"EastMoney response is malformed JSON/JSONP ({type(exc).__name__})")
        if not isinstance(document, dict):
            self._fail("EastMoney JSON/JSONP root must be an object")
        return document, request_url

    def _captured_at(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return value

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)


class EastmoneyNewsProvider(_EastmoneyDocumentProviderBase):
    """EastMoney individual-stock news list plus server-rendered HTML detail."""

    def __init__(self, transport: _EastmoneyTransport | None = None, *, clock: Any | None = None) -> None:
        super().__init__(
            transport,
            clock=clock,
            headers=build_headers(referer="https://finance.eastmoney.com/"),
        )
        self._source = Source(providerId="eastmoney.news", sourceUrl=EASTMONEY_NEWS_LIST_ENDPOINT)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_news_page(self, request: NewsSearchRequest) -> _ProviderDocumentPage:
        if not isinstance(request, NewsSearchRequest):
            self._fail("request must be a NewsSearchRequest")
        market_code = "1" if request.instrument_id.exchange is Exchange.SSE else "0"
        params = {
            "cfh": 1,
            "client": "web",
            "mTypeAndCode": f"{market_code}.{request.instrument_id.code}",
            "type": 1,
            "pageSize": request.page_size,
            "pageIndex": request.page,
        }
        document, request_url = self._request_json(EASTMONEY_NEWS_LIST_ENDPOINT, params)
        if set(document) != {"code", "message", "data"}:
            self._fail("EastMoney news list root fields drifted")
        if document.get("code") not in (1, "1") or not isinstance(document.get("message"), str):
            self._fail(f"EastMoney news list indicates failure: {document.get('message')!r}")
        data = document.get("data")
        if data is None:
            return _ProviderDocumentPage((), request.page, request.page_size, None, request_url)
        if not isinstance(data, dict) or set(data) != {"page_index", "totle_hits", "list", "page_size"}:
            self._fail("EastMoney news list data fields drifted")
        page_index = self._integer(data.get("page_index"), "news.data.page_index")
        if page_index != request.page:
            self._fail("EastMoney news list page identity mismatch")
        actual_page_size = self._integer(data.get("page_size"), "news.data.page_size")
        total_hits = self._integer(data.get("totle_hits"), "news.data.totle_hits")
        if actual_page_size != request.page_size:
            self._fail("EastMoney news list page_size was silently clamped")
        if actual_page_size < 1 or actual_page_size > 200:
            self._fail("EastMoney news list page_size is outside the safe bound")
        if total_hits < 0:
            self._fail("EastMoney news list totle_hits cannot be negative")
        raw_rows = data.get("list")
        if not isinstance(raw_rows, list):
            self._fail("EastMoney news list must contain an array")
        rows: list[_ProviderNewsRow] = []
        for index, raw in enumerate(raw_rows):
            if not isinstance(raw, dict) or set(raw) != _NEWS_ROW_FIELDS:
                self._fail(f"EastMoney news row {index} fields drifted")
            document_id = self._text(raw.get("Art_Code"), f"news.list[{index}].Art_Code")
            if _NEWS_ID.fullmatch(document_id) is None:
                self._fail(f"EastMoney news row {index} has an invalid Art_Code")
            title = self._text(raw.get("Art_Title"), f"news.list[{index}].Art_Title")
            published = self._source_datetime(raw.get("Art_ShowTime"), f"news.list[{index}].Art_ShowTime")
            url = self._text(raw.get("Art_Url"), f"news.list[{index}].Art_Url")
            original = self._text(raw.get("Art_OriginUrl"), f"news.list[{index}].Art_OriginUrl")
            sort_start = self._text(raw.get("Art_SortStart"), f"news.list[{index}].Art_SortStart")
            if not sort_start.isdigit():
                self._fail(f"EastMoney news row {index}.Art_SortStart must be numeric text")
            rows.append(
                _ProviderNewsRow(
                    instrument_id=request.instrument_id,
                    document_id=document_id,
                    title=title,
                    published_at=published,
                    url=url,
                    original_url=original,
                    source_name=None,
                    content_text=None,
                    source_url=request_url,
                    captured_at=self._captured_at(),
                    sort_start=sort_start,
                    np_dst=self._text(raw.get("Np_dst"), f"news.list[{index}].Np_dst"),
                )
            )
        return _ProviderDocumentPage(tuple(rows), page_index, actual_page_size, total_hits, request_url)

    def fetch_raw_news_document(self, document_id: str) -> _ProviderNewsRow:
        if not isinstance(document_id, str) or _NEWS_ID.fullmatch(document_id) is None:
            self._fail("news document ID must be a numeric EastMoney Art_Code")
        url = f"{EASTMONEY_NEWS_DETAIL_ENDPOINT}/{document_id}.html"
        try:
            response = self._transport.get(
                url,
                params={},
                headers=build_headers(referer="https://finance.eastmoney.com/"),
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
        except _EastmoneyTransportFailure as exc:
            self._fail(f"EastMoney news detail transport failure: {exc}")
        except Exception as exc:
            self._fail(f"EastMoney news detail transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"EastMoney news detail returned {status_reason}")
        if not response.text.strip():
            self._fail("EastMoney news detail returned an empty body")
        try:
            parsed = _parse_html_news(response.text, document_id=document_id)
        except ValueError as exc:
            self._fail(str(exc))
        captured = self._captured_at()
        return _ProviderNewsRow(
            instrument_id=None,
            document_id=document_id,
            title=parsed.title,
            published_at=parsed.published_at,
            url=url,
            original_url=None,
            source_name=parsed.source_name,
            content_text=parsed.content_text,
            source_url=url,
            captured_at=captured,
        )

    fetch_raw_list = fetch_raw_news_page
    fetch_raw_document = fetch_raw_news_document
    fetch_content = fetch_raw_news_document

    def _integer(self, value: object, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            self._fail(f"{label} must be an integer")
        try:
            result = int(str(value))
        except ValueError:
            self._fail(f"{label} must be an integer")
        return result

    def _text(self, value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            self._fail(f"{label} must be non-empty text")
        return value

    def _source_datetime(self, value: object, label: str) -> datetime:
        if not isinstance(value, str):
            self._fail(f"{label} must be a source datetime")
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_TIMEZONE)
        except ValueError:
            self._fail(f"{label} is not YYYY-MM-DD HH:MM:SS")


class EastmoneyDisclosureProvider(_EastmoneyDocumentProviderBase):
    """EastMoney individual-stock disclosure list and paginated content API."""

    def __init__(self, transport: _EastmoneyTransport | None = None, *, clock: Any | None = None) -> None:
        super().__init__(
            transport,
            clock=clock,
            headers=build_headers(referer="https://data.eastmoney.com/"),
        )
        self._source = Source(providerId="eastmoney.disclosure", sourceUrl=EASTMONEY_DISCLOSURE_LIST_ENDPOINT)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_disclosure_page(self, request: DisclosureSearchRequest) -> _ProviderDocumentPage:
        if not isinstance(request, DisclosureSearchRequest):
            self._fail("request must be a DisclosureSearchRequest")
        market_code = "1" if request.instrument_id.exchange is Exchange.SSE else "0"
        params = {
            "page_size": request.page_size,
            "page_index": request.page,
            "market_code": market_code,
            "stock_list": request.instrument_id.code,
            "client_source": "web",
        }
        document, request_url = self._request_json(EASTMONEY_DISCLOSURE_LIST_ENDPOINT, params)
        if set(document) != {"data", "error", "success"}:
            self._fail("EastMoney disclosure list root fields drifted")
        if document.get("success") not in (1, "1") or document.get("error") not in ("", None):
            self._fail(f"EastMoney disclosure list indicates failure: {document.get('error')!r}")
        data = document.get("data")
        if data is None:
            return _ProviderDocumentPage((), request.page, request.page_size, None, request_url)
        if not isinstance(data, dict) or set(data) != {"list", "page_index", "page_size", "total_hits"}:
            self._fail("EastMoney disclosure list data fields drifted")
        page_index = self._integer(data.get("page_index"), "disclosure.data.page_index")
        if page_index != request.page:
            self._fail("EastMoney disclosure list page identity mismatch")
        actual_page_size = self._integer(data.get("page_size"), "disclosure.data.page_size")
        total_hits = self._integer(data.get("total_hits"), "disclosure.data.total_hits")
        if actual_page_size != request.page_size:
            self._fail("EastMoney disclosure list page_size was silently clamped")
        if actual_page_size < 1 or actual_page_size > 200:
            self._fail("EastMoney disclosure list page_size is outside the safe bound")
        if total_hits < 0:
            self._fail("EastMoney disclosure list total_hits cannot be negative")
        raw_rows = data.get("list")
        if not isinstance(raw_rows, list):
            self._fail("EastMoney disclosure list must contain an array")
        rows: list[_ProviderDisclosureRow] = []
        for index, raw in enumerate(raw_rows):
            rows.append(self._parse_disclosure_list_row(raw, index, request_url, request.instrument_id))
        return _ProviderDocumentPage(tuple(rows), page_index, actual_page_size, total_hits, request_url)

    def fetch_raw_disclosure_document(self, document_id: str) -> _ProviderDisclosureRow:
        if not isinstance(document_id, str) or _DISCLOSURE_ID.fullmatch(document_id) is None:
            self._fail("disclosure document ID must be an AN-prefixed EastMoney art_code")
        contents: list[str] = []
        first: dict[str, Any] | None = None
        attachments: dict[tuple[int | None, str], _ProviderDisclosureAttachment] = {}
        for page_index in range(1, 1001):
            params = {"art_code": document_id, "client_source": "web", "page_index": page_index}
            document, request_url = self._request_json(EASTMONEY_DISCLOSURE_CONTENT_ENDPOINT, params)
            if set(document) not in ({"data", "success"}, {"data", "error", "success"}):
                self._fail("EastMoney disclosure content root fields drifted")
            if document.get("success") not in (1, "1") or document.get("error") not in ("", None):
                self._fail(f"EastMoney disclosure content indicates failure: {document.get('error')!r}")
            data = document.get("data")
            if not isinstance(data, dict) or set(data) != _CONTENT_FIELDS:
                self._fail(f"EastMoney disclosure content page {page_index} fields drifted")
            if self._text(data.get("art_code"), "content.art_code") != document_id:
                self._fail("EastMoney disclosure content identity mismatch")
            page_count = self._integer(data.get("page_size"), "content.page_size")
            if page_count < 1 or page_count > 1000:
                self._fail("EastMoney disclosure content page_size is outside the safe bound")
            if first is None:
                first = data
            elif page_count != self._integer(first.get("page_size"), "content.page_size"):
                self._fail("EastMoney disclosure content page_size changed between pages")
            notice_content = data.get("notice_content")
            if not isinstance(notice_content, str) or not notice_content.strip():
                self._fail(f"EastMoney disclosure content page {page_index} was empty")
            page_text = notice_content.strip()
            if page_text in contents:
                self._fail(f"EastMoney disclosure content page {page_index} repeated an earlier page")
            contents.append(page_text)
            self._parse_content_attachments(data, attachments)
            if page_index >= page_count:
                break
        else:
            self._fail("EastMoney disclosure content exceeded the safe page bound")
        assert first is not None
        securities = self._parse_content_securities(first.get("security"), "content.security")
        title = self._text(first.get("notice_title"), "content.notice_title")
        notice_date = self._parse_date(first.get("notice_date"), "content.notice_date")
        ei_time = self._parse_source_datetime(first.get("eitime"), "content.eitime", required=False)
        return _ProviderDisclosureRow(
            document_id=document_id,
            title=title,
            notice_date=notice_date,
            published_candidate=None,
            display_time=None,
            ei_time=ei_time,
            sort_date=None,
            categories=(),
            securities=securities,
            source_type=None,
            content_text="\n\n".join(contents),
            attachments=tuple(attachments.values()),
            source_url=f"{EASTMONEY_DISCLOSURE_CONTENT_ENDPOINT}?{urlencode({'art_code': document_id, 'client_source': 'web', 'page_index': 1})}",
            captured_at=self._captured_at(),
        )

    fetch_raw_list = fetch_raw_disclosure_page
    fetch_raw_document = fetch_raw_disclosure_document
    fetch_content = fetch_raw_disclosure_document

    def _parse_disclosure_list_row(
        self,
        raw: object,
        index: int,
        request_url: str,
        requested_instrument: InstrumentId,
    ) -> _ProviderDisclosureRow:
        if not isinstance(raw, dict) or set(raw) != _DISCLOSURE_ROW_FIELDS:
            self._fail(f"EastMoney disclosure row {index} fields drifted")
        document_id = self._text(raw.get("art_code"), f"disclosure.list[{index}].art_code")
        if _DISCLOSURE_ID.fullmatch(document_id) is None:
            self._fail(f"EastMoney disclosure row {index} has an invalid art_code")
        codes = raw.get("codes")
        columns = raw.get("columns")
        if not isinstance(codes, list) or not codes:
            self._fail(f"EastMoney disclosure row {index}.codes must be a non-empty array")
        if not isinstance(columns, list):
            self._fail(f"EastMoney disclosure row {index}.columns must be an array")
        securities = self._parse_list_securities(codes, index)
        if requested_instrument not in [item.instrument_id for item in securities]:
            self._fail("EastMoney disclosure list identity mismatch")
        categories = []
        for category_index, item in enumerate(columns):
            if not isinstance(item, dict) or set(item) != _DISCLOSURE_COLUMN_FIELDS:
                self._fail(f"EastMoney disclosure row {index}.columns[{category_index}] fields drifted")
            categories.append(
                _ProviderDisclosureCategory(
                    code=self._text(item.get("column_code"), "disclosure.column_code"),
                    name=self._text(item.get("column_name"), "disclosure.column_name"),
                )
            )
        title = self._text(raw.get("title_ch") or raw.get("title"), f"disclosure.list[{index}].title")
        display_time = self._parse_source_datetime(
            raw.get("display_time"), f"disclosure.list[{index}].display_time"
        )
        return _ProviderDisclosureRow(
            document_id=document_id,
            title=title,
            notice_date=self._parse_date(raw.get("notice_date"), f"disclosure.list[{index}].notice_date"),
            published_candidate=display_time,
            display_time=display_time,
            ei_time=self._parse_source_datetime(raw.get("eiTime"), f"disclosure.list[{index}].eiTime"),
            sort_date=self._parse_source_datetime(raw.get("sort_date"), f"disclosure.list[{index}].sort_date"),
            categories=tuple(categories),
            securities=tuple(securities),
            source_type=self._text(raw.get("source_type"), f"disclosure.list[{index}].source_type"),
            content_text=None,
            attachments=(),
            source_url=request_url,
            captured_at=self._captured_at(),
        )

    def _parse_list_securities(self, raw: list[object], index: int) -> list[_ProviderDisclosureSecurity]:
        result = []
        for security_index, item in enumerate(raw):
            if not isinstance(item, dict) or set(item) != _DISCLOSURE_SECURITY_FIELDS:
                self._fail(f"EastMoney disclosure row {index}.codes[{security_index}] fields drifted")
            result.append(self._security(item, f"disclosure.codes[{security_index}]"))
        return result

    def _parse_content_securities(self, raw: object, label: str) -> tuple[_ProviderDisclosureSecurity, ...]:
        if not isinstance(raw, list) or not raw:
            self._fail(f"EastMoney {label} must be a non-empty array")
        result = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or set(item) != _CONTENT_SECURITY_FIELDS:
                self._fail(f"EastMoney {label}[{index}] fields drifted")
            stock = self._text(item.get("stock"), f"{label}[{index}].stock")
            market = self._text(item.get("market_uni"), f"{label}[{index}].market_uni")
            result.append(
                _ProviderDisclosureSecurity(
                    instrument_id=self._source_instrument(stock, market, f"{label}[{index}].stock"),
                    short_name=self._text(item.get("short_name"), f"{label}[{index}].short_name"),
                    ann_type="",
                    inner_code="",
                )
            )
        return tuple(result)

    def _security(self, item: Mapping[str, object], label: str) -> _ProviderDisclosureSecurity:
        market = self._text(item.get("market_code"), f"{label}.market_code")
        code = self._text(item.get("stock_code"), f"{label}.stock_code")
        return _ProviderDisclosureSecurity(
            instrument_id=self._source_instrument(code, market, label),
            short_name=self._text(item.get("short_name"), f"{label}.short_name"),
            ann_type=self._text(item.get("ann_type"), f"{label}.ann_type"),
            inner_code=self._text(item.get("inner_code"), f"{label}.inner_code"),
        )

    def _source_instrument(self, code: str, market: str, label: str) -> InstrumentId:
        if not re.fullmatch(r"[0-9]{6}", code):
            self._fail(f"{label} has an invalid stock code")
        if market == "1":
            exchange = Exchange.SSE
        elif market == "0":
            exchange = Exchange.SZSE
        else:
            self._fail(f"{label} has an unverified market_code {market!r}")
        return InstrumentId(code=code, market=Market.CN_A, kind=InstrumentKind.EQUITY, exchange=exchange)

    def _parse_content_attachments(
        self,
        data: Mapping[str, object],
        result: dict[tuple[int | None, str], _ProviderDisclosureAttachment],
    ) -> None:
        raw_list = data.get("attach_list")
        if not isinstance(raw_list, list):
            self._fail("EastMoney content attach_list must be an array")
        for index, item in enumerate(raw_list):
            if not isinstance(item, dict) or set(item) != _CONTENT_ATTACHMENT_FIELDS:
                self._fail(f"EastMoney content attach_list[{index}] fields drifted")
            url = self._text(item.get("attach_url"), f"content.attach_list[{index}].attach_url")
            sequence = self._integer(item.get("seq"), f"content.attach_list[{index}].seq")
            size = self._integer(item.get("attach_size"), f"content.attach_list[{index}].attach_size")
            result[(sequence, url)] = _ProviderDisclosureAttachment(
                sequence=sequence,
                size=size,
                attachment_type=self._text(item.get("attach_type"), f"content.attach_list[{index}].attach_type"),
                url=url,
                web_url=None,
            )
        if not result and isinstance(data.get("attach_url_web"), str) and data.get("attach_url_web"):
            url = str(data["attach_url_web"])
            result[(None, url)] = _ProviderDisclosureAttachment(None, None, None, url, url)

    def _parse_date(self, value: object, label: str) -> date:
        text = self._text(value, label)
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            self._fail(f"{label} is not an ISO calendar date")

    def _parse_source_datetime(self, value: object, label: str, *, required: bool = True) -> datetime | None:
        if value is None or value == "":
            if required:
                self._fail(f"{label} is required")
            return None
        if not isinstance(value, str):
            self._fail(f"{label} must be source datetime text")
        candidate = value.strip()
        match = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})(?::([0-9]{1,6}))?", candidate)
        if match is None:
            self._fail(f"{label} is not a supported source datetime")
        fraction = (match.group(2) or "").ljust(6, "0")
        try:
            parsed = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_TIMEZONE)
        except ValueError:
            self._fail(f"{label} is not a valid source datetime")
        return parsed.replace(microsecond=int(fraction)) if fraction else parsed

    def _integer(self, value: object, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            self._fail(f"{label} must be an integer")
        try:
            return int(str(value))
        except ValueError:
            self._fail(f"{label} must be an integer")

    def _text(self, value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            self._fail(f"{label} must be non-empty text")
        return value


__all__ = [
    "EASTMONEY_DISCLOSURE_CONTENT_ENDPOINT",
    "EASTMONEY_DISCLOSURE_LIST_ENDPOINT",
    "EASTMONEY_NEWS_DETAIL_ENDPOINT",
    "EASTMONEY_NEWS_LIST_ENDPOINT",
    "EastmoneyDisclosureProvider",
    "EastmoneyNewsProvider",
]
