"""研报网页片段的客观文字转换，不执行网页内容。"""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


def _link(value: str, base_url: str) -> str | None:
    if not value or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        return None
    result = urljoin(base_url, value)
    try:
        parsed = urlsplit(result)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return result
    except ValueError:
        pass
    return None


class _Markdown(HTMLParser):
    def __init__(self, base_url: str, source: str, *, plain: bool = False):
        super().__init__(convert_charrefs=True)
        self.base_url, self.source, self.plain = base_url, source, plain
        self.parts, self.links = [], []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag in {"p", "div", "section", "article", "ul", "ol", "blockquote", "table", "tr"}:
            self.parts.append("\n\n")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n" + ("" if self.plain else "- "))
        elif re.fullmatch("h[1-6]", tag):
            self.parts.append("\n\n" + ("" if self.plain else "#" * int(tag[1]) + " "))
        elif tag == "img" and not self.plain:
            # data-original 是来源真实正文图；占位 src 不能遮蔽它。
            link = next((link for key in ("data-original", "data-src", "src")
                         if (link := _link(attrs.get(key) or "", self.base_url))), None)
            if link:
                alt = (attrs.get("alt") or "").replace("[", "\\[").replace("]", "\\]")
                self.parts.append(f"![{alt}]({link})")
        elif tag == "a":
            link = _link(attrs.get("href", ""), self.base_url)
            self.links.append(link)
            if link and not self.plain:
                self.parts.append("[")
        elif tag in {"td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if self.hidden:
            if tag in {"script", "style", "noscript", "template"}:
                self.hidden -= 1
            return
        if tag == "a" and self.links:
            link = self.links.pop()
            if link and not self.plain:
                self.parts.append(f"]({link})")
        elif tag in {"p", "div", "section", "article", "ul", "ol", "blockquote", "table", "tr"} or re.fullmatch("h[1-6]", tag):
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(re.sub(r"\s+", " ", data))


def to_markdown(html: str, *, base_url: str, source: str) -> str | None:
    """保留段落、标题、列表和真实图片地址；空片段返回 None。"""
    parser = _Markdown(base_url, source)
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() or None


def plain_text(html: str) -> str:
    """去掉来源搜索高亮等标签，保留可读文字。"""
    parser = _Markdown("", "", plain=True)
    parser.feed(html)
    parser.close()
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()
