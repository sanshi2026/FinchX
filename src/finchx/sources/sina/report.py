"""独立读取新浪研报网页的主体文字，不下载文件。"""

from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
import re
from urllib.parse import parse_qsl, urljoin, urlsplit

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

_SOURCE = "sina"
_HOST = "stock.finance.sina.com.cn"
_PATH = re.compile(r"/stock/go\.php/vReport_Show/kind/[^/]+/rptid/([0-9]+)/index\.phtml")


def _fail(reason):
    raise SourceError(_SOURCE, reason)


def _identity(url):
    if not isinstance(url, str) or not url or re.search(r"[\x00-\x20\x7f\\]", url):
        raise ValueError("url 必须为合法的新浪研报页面链接")
    try:
        parts = urlsplit(url)
        if (parts.scheme not in ("http", "https") or parts.hostname != _HOST
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 80 if parts.scheme == "http" else 443)):
            raise ValueError
        match = _PATH.fullmatch(parts.path)
        if match is None or re.search(r"%(?![0-9A-Fa-f]{2})", url):
            raise ValueError
        # 来源定位由路径决定；查询/片段中的普通展示参数无需硬编码名单。
        pairs = parse_qsl(parts.query, keep_blank_values=True, encoding="utf-8", errors="strict")
        if any(re.search(r"[\x00-\x1f\x7f\\]", key + value) for key, value in pairs):
            raise ValueError
        return match[1]
    except (ValueError, UnicodeError):
        raise ValueError("url 必须为合法的新浪 vReport_Show 研报页面链接") from None


@dataclass
class _Node:
    tag: str
    attrs: dict
    parent: "_Node | None" = None
    children: list = field(default_factory=list)

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def walk(self):
        pending = [self]
        while pending:
            node = pending.pop()
            yield node
            pending.extend(child for child in reversed(node.children) if isinstance(child, _Node))

    def text(self):
        if self.tag in ("script", "style", "noscript", "iframe", "button"):
            return ""
        if self.tag == "br":
            return "\n"
        value = "".join(child.text() if isinstance(child, _Node) else child for child in self.children)
        return "\n" + value + "\n" if self.tag in ("p", "div", "li", "tr", "blockquote") else value


class _Tree(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.root = self.current = _Node("root", {})
        if not isinstance(markup, str):
            _fail("研报页面不是有效文本")
        try:
            self.feed(markup)
            self.close()
        except (ValueError, RecursionError):
            _fail("研报主体 HTML 结构损坏")

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self.current)
        self.current.children.append(node)
        if tag not in ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"):
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, value):
        self.current.children.append(value)


def _text(node):
    try:
        value = node.text().replace("\xa0", " ")
    except RecursionError:
        _fail("研报主体嵌套超过防护范围")
    value = re.sub(r"[ \t]+\n|\n[ \t]+", "\n", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip() or None


def _source_identity(root, url, identity):
    # 本轮真实页面没有数字 ID 标记，不从正文或标题制造研报身份。
    for node in root.walk():
        href = None
        if node.tag == "link" and "canonical" in node.attrs.get("rel", "").lower().split():
            href = node.attrs.get("href")
        elif node.tag == "meta" and node.attrs.get("property", "").lower() == "og:url":
            href = node.attrs.get("content")
        if not href:
            continue
        target = urljoin(url, href)
        try:
            candidate = _identity(target)
        except ValueError:
            # 不属于可验证研报路由的可选元信息不作为正文硬门槛。
            continue
        if candidate != identity:
            _fail("网页明示研报身份与请求不一致")


def _metadata(container):
    values = {"日期": set(), "机构": set(), "研究员": set()}
    for block in container.children:
        if not isinstance(block, _Node) or not block.has_class("creab"):
            continue
        for node in block.walk():
            if node.tag != "span":
                continue
            value = _text(node)
            if value is None:
                continue
            match = re.match(r"^(日期|机构|研究员)\s*[：:]\s*(.*)$", value, flags=re.S)
            if match is not None and match[2].strip():
                values[match[1]].add(match[2].strip())
    resolved = {key: next(iter(items)) if len(items) == 1 else None for key, items in values.items()}
    published = resolved["日期"]
    if published is not None:
        try:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", published):
                raise ValueError
            published = date.fromisoformat(published).isoformat()
        except ValueError:
            published = None
    return published, resolved["机构"], resolved["研究员"]


def get_report(url, *, timeout):
    identity = _identity(url)
    markup = get_text(url, timeout=validate_timeout(timeout), headers={**DEFAULT_HEADERS, "Referer": "https://stock.finance.sina.com.cn/"},
                      source=_SOURCE, encoding="gbk", follow_redirects=False)
    root = _Tree(markup).root
    _source_identity(root, url, identity)
    bodies = [node for node in root.walk() if node.has_class("blk_container")
              and node.parent is not None and node.parent.has_class("content")]
    if len(bodies) != 1:
        _fail("没有唯一可读的研报主体")
    body = bodies[0]
    content = _text(body)
    if content is None or re.match(r"^(?:该研报已删除|研报不存在|报告不存在|未找到该研报|您访问的页面不存在)(?:[，。！!\s]|$)", content):
        _fail("来源没有可用研报正文")
    container = body.parent
    titles = {_text(child) for child in container.children if isinstance(child, _Node) and child.tag == "h1"}
    titles.discard(None)
    title = next(iter(titles)) if len(titles) == 1 else None
    publication_date, institute, researcher = _metadata(container)
    return {"title": title, "publication_date": publication_date, "institute": institute,
            "researcher": researcher, "content": content, "original_url": None, "file_type": None}
