"""Tonghuashun article-detail APIs and server-rendered community articles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import escape, unescape
from html.parser import HTMLParser
from http.cookies import SimpleCookie
import hashlib
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from finchx.collectors.errors import SourceUnavailable, Timeout
from finchx.contracts import Source
from finchx.datasets.article_detail import (
    ArticleDetailRequest,
    is_usable_article_body,
    normalize_http_url,
    unwrap_markdown_url,
)
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, build_headers


NEWS_DETAIL_API = "https://news.10jqka.com.cn/mobile_api/news/article/page/v2/WEB/{}"
ZIBO_PAGE_ROOT = "https://t.10jqka.com.cn/pid_{}.shtml"
ZIBO_MOBILE_PAGE_ROOT = "https://t.10jqka.com.cn/m/zhibo/pid_{}.shtml"
_ARTICLE_HTML_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
_ARTICLE_HTML_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)
ARTICLE_PROVIDER_ID = "tonghuashun.articles"
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_BLOCKED_TAGS = frozenset(
    {"script", "style", "noscript", "iframe", "object", "embed", "form", "button", "input", "svg"}
)
_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
_ALLOWED_TAGS = frozenset(
    {
        "a", "abbr", "b", "blockquote", "br", "caption", "cite", "code", "col",
        "colgroup", "dd", "del", "div", "dl", "dt", "em", "figcaption", "figure",
        "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p",
        "pre", "q", "s", "small", "span", "strong", "sub", "sup", "table", "tbody",
        "td", "th", "thead", "tr", "u", "ul",
    }
)
_SAFE_ATTRS = frozenset({"alt", "class", "colspan", "height", "href", "rowspan", "src", "title", "width"})
_REMOVE_CLASS_TOKENS = frozenset(
    {
        "comment", "comments", "comment-list", "comment-list-wrap", "comment-area", "comment-box",
        "reply", "reply-list", "reply-area", "disclaimer", "statement", "risk-tip", "risk-tips",
        "recommend", "recommend-list", "related", "related-news", "related-article", "footer",
        "toolbar", "share", "share-box", "ad", "advertisement", "advert", "brokers_hidden",
    }
)
_BLOCK_RE = re.compile(r"^(?:免责声明|风险提示|本文观点仅供参考)(?:[:：\s]|$)")
_ENCODE_MODULUS = 100_000_000_000


class ArticleDetailSourceError(ProviderError):
    """Source-side failure with a stable classification for cache and batch use."""

    def __init__(self, source: Source, reason: str, *, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(source, reason)


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    children: list["_Node | str"]


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {}, [])
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.casefold(), {key.casefold(): value or "" for key, value in attrs}, [])
        self.stack[-1].children.append(node)
        if tag.casefold() not in _VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


def encode_news_seq(content_id: str | int) -> str:
    """Encode the confirmed WEB article sequence identifier."""

    seq = str(content_id)
    if not re.fullmatch(r"\d{6,16}", seq):
        raise ValueError("news content ID must contain 6 to 16 digits")
    value = str((int(seq) * 2_147_483_647) % _ENCODE_MODULUS).zfill(11)
    checksum = str(sum(int(digit) for digit in seq) % 10)
    digest = hashlib.md5(f"{seq}{checksum}".encode("ascii")).hexdigest()
    return f"{digest[:4]}{value}{checksum}{digest[-3:]}"


def _parse_tree(markup: str) -> _Node:
    parser = _TreeParser()
    parser.feed(markup)
    parser.close()
    return parser.root


_ENCODED_CONTENT_TAG = re.compile(
    r"&lt;\s*/?\s*(?:a|b|blockquote|br|div|em|h[1-6]|hr|i|img|li|ol|p|span|strong|table|td|th|tr|u|ul)(?=[\s/&gt;])",
    re.IGNORECASE,
)


def _parse_content_tree(markup: str) -> _Node:
    """Parse HTML fragments that sometimes arrive with tags entity-escaped."""

    if _ENCODED_CONTENT_TAG.search(markup):
        markup = unescape(markup)
    return _parse_tree(markup)


def _descendants(node: _Node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _descendants(child)


def _classes(node: _Node) -> set[str]:
    return {value.casefold() for value in node.attrs.get("class", "").split()}


def _text_content(node: _Node) -> str:
    pieces: list[str] = []
    def visit(current: _Node) -> None:
        for child in current.children:
            if isinstance(child, str):
                pieces.append(child)
            elif child.tag not in _BLOCKED_TAGS:
                if child.tag == "br":
                    pieces.append("\n")
                visit(child)
                if child.tag in {"p", "div", "li", "tr", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}:
                    pieces.append("\n")
                elif child.tag in {"td", "th"}:
                    pieces.append(" | ")
    visit(node)
    return _clean_text("".join(pieces))


def _clean_text(value: str) -> str:
    value = unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    lines = [re.sub(r"[\t\r\f\v ]+", " ", line).strip() for line in value.splitlines()]
    compact: list[str] = []
    for line in lines:
        if line:
            if compact and compact[-1]:
                compact.append("")
            compact.append(line)
    return "\n".join(compact).strip()


def _safe_url(value: str, base_url: str) -> str | None:
    value = unwrap_markdown_url(value)
    if not value or value.casefold().startswith(("javascript:", "data:", "vbscript:")):
        return None
    absolute = urljoin(base_url, value)
    return normalize_http_url(absolute)


_MARKET_JUMP_FRAGMENT = re.compile(r"^\*f:[A-Za-z0-9._-]+:sc\*#$", re.IGNORECASE)


def _is_market_jump(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        (parsed.hostname or "").casefold() in {"news.10jqka.com.cn", "stock.10jqka.com.cn"}
        and bool(_MARKET_JUMP_FRAGMENT.fullmatch(parsed.fragment))
    )


def _has_blocked_class(node: _Node) -> bool:
    classes = _classes(node)
    if classes.intersection(_REMOVE_CLASS_TOKENS) or any(
        token.startswith(("comment", "reply", "disclaim", "statement", "risk-tip", "recommend", "related", "advert", "ad-"))
        for token in classes
    ):
        return True
    text = _text_content(node)
    return bool(text and _BLOCK_RE.match(text))


def _has_visible_content(node: _Node, *, base_url: str) -> bool:
    """Whether a sanitized node contains text or a safe image worth retaining."""

    for child in node.children:
        if isinstance(child, str):
            if _clean_text(child):
                return True
            continue
        if child.tag in _BLOCKED_TAGS or _has_blocked_class(child):
            continue
        if child.tag == "img":
            if _safe_url(child.attrs.get("src", ""), base_url):
                return True
            continue
        if child.tag in {"br", "hr"}:
            continue
        if _has_visible_content(child, base_url=base_url):
            return True
    return False


def _serialize(node: _Node, *, base_url: str, top_level: bool = False) -> str:
    output: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            output.append(escape(unescape(child), quote=False))
            continue
        tag = child.tag
        if tag in _BLOCKED_TAGS or _has_blocked_class(child):
            continue
        if tag not in _VOID_TAGS and not _has_visible_content(child, base_url=base_url):
            continue
        if tag == "a":
            href = child.attrs.get("href", "")
            safe_href = _safe_url(href, base_url)
            if safe_href is None or _is_market_jump(safe_href):
                output.append(_serialize(child, base_url=base_url))
                continue
        # Span wrappers in source articles only carry presentation classes;
        # retain their text/images without keeping the redundant element.
        safe_tag = tag if tag in _ALLOWED_TAGS and tag != "span" else None
        attrs: list[tuple[str, str]] = []
        if safe_tag:
            for name, value in child.attrs.items():
                if name not in _SAFE_ATTRS or name == "class" or not value:
                    continue
                if name in {"width", "height"}:
                    continue
                if name in {"href", "src"}:
                    safe_value = _safe_url(value, base_url)
                    if safe_value is None:
                        continue
                    attrs.append((name, safe_value))
                else:
                    attrs.append((name, value))
        if safe_tag:
            attr_text = "".join(f' {name}="{escape(value, quote=True)}"' for name, value in attrs)
            output.append(f"<{safe_tag}{attr_text}>")
        output.append(_serialize(child, base_url=base_url))
        if safe_tag and tag not in _VOID_TAGS:
            output.append(f"</{safe_tag}>")
    serialized = "".join(output)
    if node.tag in {"p", "div", "li", "tr", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}:
        return serialized.strip()
    return serialized


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if self.skip_depth:
            if tag not in _VOID_TAGS:
                self.skip_depth += 1
            return
        if tag in {"script", "style", "iframe", "svg"}:
            self.skip_depth = 1
        elif tag == "br":
            self.parts.append("\n")
        elif tag in {"p", "div", "li", "tr", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag.casefold() in {"p", "div", "li", "tr", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def _text_from_html(markup: str) -> str:
    parser = _TextParser()
    parser.feed(markup)
    parser.close()
    return _clean_text("".join(parser.parts))


def _content_markup(node: _Node, *, base_url: str) -> tuple[str, str]:
    markup = _serialize(node, base_url=base_url)
    markup = re.sub(r"(</(?:p|div|li|blockquote|h[1-6]|tr|table|ul|ol)>)\s+(?=<)", r"\1", markup)
    return markup.strip(), _text_from_html(markup)


def _node_by_class(root: _Node, required: set[str]) -> list[_Node]:
    return [node for node in _descendants(root) if required.issubset(_classes(node))]


def _select_content(root: _Node, *, zhibo: bool) -> _Node | None:
    if zhibo:
        candidates = _node_by_class(root, {"wdwrap", "post-text-main", "ql-editor"})
        if candidates:
            return candidates[0]
    candidates = _node_by_class(root, {"news-content", "article-content"})
    if candidates:
        return candidates[0]
    candidates = _node_by_class(root, {"news-content-parsed"})
    if candidates:
        return candidates[0]
    candidates = _node_by_class(root, {"article-content"})
    return candidates[0] if candidates else None


def _meta(root: _Node, *names: str) -> str | None:
    wanted = {name.casefold() for name in names}
    for node in _descendants(root):
        if node.tag != "meta":
            continue
        key = (node.attrs.get("property") or node.attrs.get("name") or node.attrs.get("itemprop") or "").casefold()
        content = node.attrs.get("content", "").strip()
        if key in wanted and content:
            return content
    return None


def _class_text(root: _Node, tokens: set[str]) -> str | None:
    for node in _descendants(root):
        if _classes(node).intersection(tokens):
            value = _text_content(node)
            if value:
                return value
    return None


def _disclaimer(root: _Node, state_value: Any = None) -> str | None:
    if isinstance(state_value, str) and _clean_text(state_value):
        return _clean_text(state_value)
    for node in _descendants(root):
        classes = _classes(node)
        if classes.intersection({"disclaimer", "statement", "risk-tip", "risk-tips", "post-detail-qshint"}):
            text = _text_content(node)
            if text:
                return text
    for node in _descendants(root):
        text = _text_content(node)
        if text and _BLOCK_RE.match(text):
            return text
    return None


def _comments(root: _Node) -> list[str]:
    candidates = [
        node for node in _descendants(root)
        if _classes(node).intersection({"comment-item", "reply-item", "comment-content", "reply-content", "comment-text"})
    ]
    if not candidates:
        candidates = [node for node in _descendants(root) if _classes(node).intersection({"comment-list", "comments", "reply-list"})]
    result = []
    for node in candidates:
        text = _text_content(node)
        if text and text not in result:
            result.append(text)
    return result


def _date_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo and value.utcoffset() is not None else value.replace(tzinfo=_SHANGHAI)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        stamp = float(value)
        if stamp > 10_000_000_000:
            stamp /= 1000
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("/", "-")
    if text.isdigit() and len(text) >= 10:
        return _date_time(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                return None
    return parsed if parsed.tzinfo and parsed.utcoffset() is not None else parsed.replace(tzinfo=_SHANGHAI)


def _json_object_after(source: str, marker: str) -> Mapping[str, Any] | None:
    index = source.find(marker)
    if index < 0:
        return None
    start = source.find("{", index + len(marker))
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(source[start:])
    except (ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _detail_state(root: _Node, html: str) -> Mapping[str, Any] | None:
    state = _json_object_after(html, "__PAGE_DATA__")
    if state is None:
        return None
    news = state.get("__NEWS_DETAIL_DATA__")
    if isinstance(news, Mapping):
        detail = news.get("detailData")
        return detail if isinstance(detail, Mapping) else news
    detail = state.get("detailData")
    return detail if isinstance(detail, Mapping) else state


def _detail_fields(detail: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], Any, Any, list[Mapping[str, Any]]]:
    article: Mapping[str, Any] = {}
    disclaimer: Any = None
    ai_summary: Any = None
    related: list[Mapping[str, Any]] = []
    if detail is None:
        return article, disclaimer, ai_summary, related
    candidate = detail.get("article")
    if not isinstance(candidate, Mapping) and isinstance(detail.get("detailData"), Mapping):
        candidate = detail["detailData"].get("article")
    if isinstance(candidate, Mapping):
        article = candidate
    settings = detail.get("pageSettings")
    if isinstance(settings, Mapping):
        disclaimer = settings.get("disclaimer")
    modules = detail.get("relatedModules")
    if isinstance(modules, Mapping):
        summary = modules.get("aiSummary")
        if isinstance(summary, Mapping):
            ai_summary = summary.get("content")
        stocks = modules.get("associatedStocks")
        if isinstance(stocks, list):
            related = [item for item in stocks if isinstance(item, Mapping)]
    return article, disclaimer, ai_summary, related


def _article_datetime(article: Mapping[str, Any], root: _Node) -> datetime | None:
    for key in ("ctime", "publishedAt", "publishTime", "createTime", "time"):
        parsed = _date_time(article.get(key))
        if parsed is not None:
            return parsed
    value = _meta(root, "article:published_time", "publishdate", "publish_date", "datepublished")
    if value:
        parsed = _date_time(value)
        if parsed is not None:
            return parsed
    for node in _descendants(root):
        if node.tag == "time" and node.attrs.get("datetime"):
            parsed = _date_time(node.attrs["datetime"])
            if parsed is not None:
                return parsed
        if _classes(node).intersection({"publish-time", "pub-time", "time", "article-time"}):
            parsed = _date_time(_text_content(node))
            if parsed is not None:
                return parsed
    return None


def _zhibo_datetime(root: _Node) -> datetime | None:
    published_date = _class_text(root, {"detail-date"})
    published_time = _class_text(root, {"detail-time"})
    if published_date and published_time:
        return _date_time(f"{published_date} {published_time}")
    return None


def _detail_stock_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        symbol = row.get("symbol") or row.get("code") or row.get("stockCode")
        name = row.get("name") or row.get("stockName") or row.get("securityName")
        if not symbol or not name:
            continue
        normalized.append(
            {
                "symbol": str(symbol),
                "name": str(name),
                "instrumentId": row.get("instrumentId"),
                "changePct": row.get("changePct", row.get("rise_and_fall")),
                "sourceMarket": row.get("sourceMarket", row.get("stockMarket", row.get("marketId"))),
            }
        )
    return normalized


def _find_title(root: _Node) -> str | None:
    value = _meta(root, "og:title", "twitter:title")
    if value:
        return _clean_text(value)
    for node in _descendants(root):
        if node.tag == "h1":
            text = _text_content(node)
            if text:
                return text
    for node in _descendants(root):
        if node.tag == "title":
            text = _text_content(node)
            if text:
                return re.sub(r"\s*[-_|｜]\s*(同花顺|10jqka).*$", "", text, flags=re.IGNORECASE).strip()
    return None


def _extract_html_page(html: str, *, page_url: str, zhibo: bool) -> dict[str, Any] | None:
    root = _parse_tree(html)
    detail = _detail_state(root, html) if not zhibo else None
    article, state_disclaimer, ai_summary, related = _detail_fields(detail)
    content = article.get("content") if isinstance(article.get("content"), str) else None
    method = "embedded_state" if content else "dom"
    content_node: _Node | None
    if content:
        content_root = _parse_content_tree(content)
        content_node = content_root
    else:
        content_node = _select_content(root, zhibo=zhibo)
    if content_node is None:
        return None
    content_html, content_text = _content_markup(content_node, base_url=page_url)
    if not content_html or not is_usable_article_body(content_html, content_text):
        return None
    media = article.get("media") if isinstance(article.get("media"), Mapping) else {}
    title = (
        (_class_text(root, {"detail-title"}) if zhibo else None)
        or article.get("title")
        or _meta(root, "og:title", "twitter:title")
        or _find_title(root)
    )
    author = (
        article.get("author")
        or _meta(root, "author")
        or _class_text(root, {"post-author", "author", "article-author", "news-author"})
    )
    source_name = (media.get("name") if isinstance(media, Mapping) else None) or _meta(root, "og:site_name") or _class_text(root, {"media-name", "source-name", "article-source"})
    disclaimer = _disclaimer(root, state_disclaimer)
    comments = _comments(root) if zhibo else []
    published_at = (_zhibo_datetime(root) if zhibo else None) or _article_datetime(article, root)
    seq = article.get("seq")
    if seq not in (None, ""):
        content_id = str(seq)
    else:
        content_id = None
    if zhibo:
        pid_match = re.search(r"(?:pid[_=]|data-pid=[\"'])(\d+)", html, flags=re.IGNORECASE)
        if pid_match:
            content_id = pid_match.group(1)
    return {
        "contentId": content_id,
        "contentType": "zhibo" if zhibo else "news",
        "title": _clean_text(str(title)) if title else None,
        "contentHtml": content_html,
        "contentText": content_text,
        "publishedAt": published_at,
        "sourceName": _clean_text(str(source_name)) if source_name else None,
        "author": _clean_text(str(author)) if author else None,
        "sourceUrl": page_url,
        "pageUrl": page_url,
        "aiSummary": _clean_text(str(ai_summary)) if ai_summary else None,
        "disclaimer": disclaimer,
        "comments": comments,
        "relatedStocks": _detail_stock_rows(related),
        "fetchMethod": method,
        "rawHash": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }


class THSArticleDetailProvider:
    """Fetch standard THS news via JSON and zhibo via server-rendered HTML."""

    provider_id = ARTICLE_PROVIDER_ID

    def __init__(
        self,
        opener: Callable[..., Any] | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._open = opener or urlopen
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout = timeout
        self._source = Source(providerId=self.provider_id)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_article_detail(self, request: ArticleDetailRequest) -> dict[str, Any]:
        if not isinstance(request, ArticleDetailRequest):
            raise ValueError("request must be an ArticleDetailRequest")
        if request.content_type == "zhibo":
            result = self._fetch_zhibo(request)
        else:
            result = self._fetch_news(request)
        if str(result.get("contentId") or request.content_id) != request.content_id:
            raise ArticleDetailSourceError(
                self._source,
                f"article response ID {result.get('contentId')!r} does not match requested contentId {request.content_id!r}",
                error_code="id_mismatch",
            )
        if not result.get("title") or not is_usable_article_body(
            str(result.get("contentHtml") or ""),
            result.get("contentText"),
        ):
            raise ArticleDetailSourceError(
                self._source,
                "article source returned no usable title or body",
                error_code="parse_error",
            )
        result["contentId"] = request.content_id
        result["capturedAt"] = self._clock()
        return result

    def _fetch_news(self, request: ArticleDetailRequest) -> dict[str, Any]:
        api_url = NEWS_DETAIL_API.format(quote(encode_news_seq(request.content_id), safe=""))
        api_error: ArticleDetailSourceError | None = None
        public_page_url = request.url
        try:
            payload = self._json_get(api_url, referer="https://news.10jqka.com.cn/")
            article, state_disclaimer, ai_summary, related = _detail_fields(self._unwrap_detail(payload))
            seq = str(article.get("seq") or "")
            if seq and seq != request.content_id:
                raise ArticleDetailSourceError(
                    self._source,
                    f"news detail API returned seq {seq!r} for requested contentId {request.content_id!r}",
                    error_code="id_mismatch",
                )
            content = article.get("content")
            if isinstance(content, str) and content.strip():
                content_html, content_text = _content_markup(
                    _parse_content_tree(content),
                    base_url=public_page_url or "https://news.10jqka.com.cn/",
                )
                if content_html and is_usable_article_body(content_html, content_text):
                    media = article.get("media") if isinstance(article.get("media"), Mapping) else {}
                    return {
                        "contentId": seq or request.content_id,
                        "contentType": "news",
                        "title": _clean_text(str(article.get("title") or "")) or None,
                        "contentHtml": content_html,
                        "contentText": content_text,
                        "publishedAt": _date_time(article.get("ctime")),
                        "sourceName": media.get("name") if isinstance(media, Mapping) else None,
                        "author": _clean_text(str(article.get("author") or "")) or None,
                        "sourceUrl": api_url,
                        "pageUrl": public_page_url,
                        "aiSummary": _clean_text(str(ai_summary)) if ai_summary else None,
                        "disclaimer": _disclaimer(_parse_tree(""), state_disclaimer),
                        "comments": [],
                        "relatedStocks": _detail_stock_rows(related),
                        "fetchMethod": "detail_api",
                        "rawHash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    }
            api_error = ArticleDetailSourceError(
                self._source,
                "news detail API response has no article body",
                error_code="parse_error",
            )
        except ArticleDetailSourceError as exc:
            if exc.error_code == "id_mismatch":
                raise
            api_error = exc
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            api_error = ArticleDetailSourceError(
                self._source,
                f"news detail API payload could not be parsed: {type(exc).__name__}",
                error_code="parse_error",
            )

        fallback_url = request.url
        if fallback_url is not None:
            try:
                page_html = self._html_get(fallback_url, referer="https://news.10jqka.com.cn/")
                page = _extract_html_page(page_html, page_url=fallback_url, zhibo=False)
                if page and page.get("title") and is_usable_article_body(
                    str(page.get("contentHtml") or ""), page.get("contentText")
                ):
                    if page.get("contentId") not in (None, request.content_id):
                        raise ArticleDetailSourceError(
                            self._source,
                            "news page ID does not match requested contentId",
                            error_code="id_mismatch",
                        )
                    page["contentId"] = request.content_id
                    return page
            except ArticleDetailSourceError as page_error:
                if page_error.error_code in {"blocked", "unauthorized", "rate_limited", "id_mismatch"}:
                    raise page_error
        if api_error is not None:
            raise api_error
        raise ArticleDetailSourceError(
            self._source,
            "news detail API and article page contained no usable body",
            error_code="parse_error",
        )

    def _fetch_zhibo(self, request: ArticleDetailRequest) -> dict[str, Any]:
        # Prefer the public desktop article page. Some IDs redirect or fail on
        # the mobile share route, so try that route only as a fallback.
        canonical_url = request.url
        mobile_url = ZIBO_MOBILE_PAGE_ROOT.format(request.content_id)
        last_error: BaseException | None = None
        failures: list[str] = []
        route_errors: list[BaseException] = []
        page: dict[str, Any] | None = None
        page_url = canonical_url
        for candidate_url in (canonical_url, mobile_url):
            try:
                html = self._html_get(
                    candidate_url,
                    referer="https://t.10jqka.com.cn/",
                    browser_headers=True,
                )
            except (ArticleDetailSourceError, SourceUnavailable, Timeout) as exc:
                last_error = exc
                route_errors.append(exc)
                failures.append(f"{candidate_url}: {exc}")
                continue
            candidate_page = _extract_html_page(html, page_url=candidate_url, zhibo=True)
            if candidate_page is None or not candidate_page.get("title"):
                last_error = ArticleDetailSourceError(
                    self._source,
                    "zhibo article HTML did not contain a recognized article body",
                    error_code="blocked" if _looks_blocked(html) else "parse_error",
                )
                route_errors.append(last_error)
                failures.append(f"{candidate_url}: {last_error}")
                continue
            candidate_id = candidate_page.get("contentId")
            if candidate_id and candidate_id != request.content_id:
                last_error = ArticleDetailSourceError(
                    self._source,
                    f"zhibo page ID {candidate_id!r} does not match requested contentId {request.content_id!r}",
                    error_code="id_mismatch",
                )
                route_errors.append(last_error)
                failures.append(f"{candidate_url}: {last_error}")
                continue
            page = candidate_page
            page_url = candidate_url
            break
        if page is None:
            failure_summary = "; ".join(failures)
            # Prefer an observed identity/auth/block response over a
            # secondary not-found/parse failure from the other route.
            error_priority = {
                "id_mismatch": 6,
                "blocked": 5,
                "unauthorized": 4,
                "rate_limited": 3,
                "network_error": 2,
                "fetch_error": 2,
                "not_found": 1,
                "parse_error": 0,
            }
            article_errors = [exc for exc in route_errors if isinstance(exc, ArticleDetailSourceError)]
            if article_errors:
                best_error = max(article_errors, key=lambda exc: error_priority.get(exc.error_code, 2))
                raise ArticleDetailSourceError(
                    self._source,
                    f"zhibo article routes failed: {failure_summary}",
                    error_code=best_error.error_code,
                ) from best_error
            if isinstance(last_error, Timeout):
                raise Timeout(f"zhibo article routes timed out: {failure_summary}") from last_error
            if isinstance(last_error, SourceUnavailable):
                raise SourceUnavailable(f"zhibo article routes unavailable: {failure_summary}") from last_error
            if last_error is not None:
                raise last_error
            raise ArticleDetailSourceError(
                self._source,
                "zhibo article HTML did not contain a recognized article body",
                error_code="parse_error",
            )
        page["contentId"] = request.content_id
        page["contentType"] = "zhibo"
        page["sourceUrl"] = page_url
        page["pageUrl"] = canonical_url
        page["fetchMethod"] = "zhibo_html"
        return page

    @staticmethod
    def _unwrap_detail(payload: Any) -> Mapping[str, Any]:
        current = payload
        for _ in range(5):
            if not isinstance(current, Mapping):
                break
            if isinstance(current.get("detailData"), Mapping):
                return current["detailData"]
            if isinstance(current.get("article"), Mapping):
                return current
            current = current.get("data")
        raise ValueError("news detail response is missing detailData.article")

    def _json_get(self, url: str, *, referer: str) -> Mapping[str, Any]:
        body = self._request_bytes(
            url,
            accept="application/json, text/javascript, */*;q=0.8",
            referer=referer,
        )
        try:
            payload = json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArticleDetailSourceError(
                self._source,
                f"news detail API returned malformed JSON ({type(exc).__name__})",
                error_code="parse_error",
            ) from exc
        if not isinstance(payload, Mapping):
            raise ArticleDetailSourceError(
                self._source,
                "news detail API returned a non-object JSON payload",
                error_code="parse_error",
            )
        return payload

    def _html_get(self, url: str, *, referer: str, browser_headers: bool = False) -> str:
        extra_headers = (
            {"User-Agent": _ARTICLE_HTML_USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
            if browser_headers
            else None
        )
        body = self._request_bytes(
            url,
            accept=_ARTICLE_HTML_ACCEPT if browser_headers else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            referer=referer,
            extra_headers=extra_headers,
        )
        return body.decode("utf-8", "replace")

    def _request_bytes(
        self,
        url: str,
        *,
        accept: str,
        referer: str,
        extra_headers: Mapping[str, str] | None = None,
    ) -> bytes:
        request_url = url
        cookie: str | None = None
        for attempt in range(2):
            headers = build_headers(accept=accept, referer=referer, extra=extra_headers)
            if cookie is not None:
                headers["Cookie"] = cookie
            request = Request(request_url, headers=headers, method="GET")
            try:
                response = self._open(request, timeout=self._timeout)
                with response if hasattr(response, "__enter__") else _ResponseContext(response) as stream:
                    status = getattr(stream, "status", None) or stream.getcode()
                    body = stream.read()
                break
            except HTTPError as exc:
                challenge = _zhibo_challenge_cookie(exc, url) if attempt == 0 else None
                if challenge is not None:
                    request_url, cookie = challenge
                    continue
                error_code = {
                    401: "unauthorized",
                    403: "blocked",
                    404: "not_found",
                    429: "rate_limited",
                }.get(exc.code, "network_error" if exc.code >= 500 else "fetch_error")
                final_url = exc.geturl() or request_url
                location = exc.headers.get("Location") if exc.headers else None
                reason = f"upstream HTTP {exc.code} at {final_url}"
                if location:
                    reason += f" (redirect Location: {location})"
                raise ArticleDetailSourceError(
                    self._source,
                    reason,
                    error_code=error_code,
                ) from exc
            except TimeoutError as exc:
                raise Timeout(f"Tonghuashun article request timed out at {request_url}: {type(exc).__name__}") from exc
            except (URLError, OSError) as exc:
                raise SourceUnavailable(
                    f"Tonghuashun article transport failure at {request_url}: {type(exc).__name__}: {exc}"
                ) from exc
        if not isinstance(status, int) or not 200 <= status < 300:
            error_code = {
                401: "unauthorized",
                403: "blocked",
                404: "not_found",
                429: "rate_limited",
            }.get(status, "network_error" if isinstance(status, int) and status >= 500 else "fetch_error")
            raise ArticleDetailSourceError(self._source, f"upstream HTTP {status}", error_code=error_code)
        if not body:
            raise ArticleDetailSourceError(self._source, "upstream returned an empty response", error_code="parse_error")
        return body


class _ResponseContext:
    def __init__(self, response: Any) -> None:
        self.response = response

    def __enter__(self) -> Any:
        return self.response

    def __exit__(self, *exc: Any) -> None:
        close = getattr(self.response, "close", None)
        if callable(close):
            close()


def _looks_blocked(page_html: str) -> bool:
    lower = page_html.casefold()
    return any(marker in lower for marker in ("access denied", "forbidden", "请登录", "登录后查看", "访问受限", "风控验证"))


def _zhibo_challenge_cookie(error: HTTPError, requested_url: str) -> tuple[str, str] | None:
    """Accept only the short cookie issued by the public article's 401 challenge."""

    if error.code != 401:
        return None
    final_url = error.geturl() or requested_url
    if (urlsplit(requested_url).hostname or "").casefold() != "t.10jqka.com.cn":
        return None
    if (urlsplit(final_url).hostname or "").casefold() != "t.10jqka.com.cn":
        return None
    if not re.fullmatch(r"/pid_\d+\.shtml", urlsplit(final_url).path):
        return None
    for header in error.headers.get_all("Set-Cookie", []) if error.headers else []:
        parsed = SimpleCookie()
        try:
            parsed.load(header)
        except Exception:
            continue
        morsel = parsed.get("vvvv")
        if morsel and re.fullmatch(r"[A-Za-z0-9._~-]{1,128}", morsel.value):
            return final_url, f"vvvv={morsel.value}"
    return None


__all__ = [
    "ARTICLE_PROVIDER_ID",
    "NEWS_DETAIL_API",
    "ArticleDetailSourceError",
    "THSArticleDetailProvider",
    "encode_news_seq",
]
