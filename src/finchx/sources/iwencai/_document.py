"""读取公开 HTML 正文或保留 PDF 原文链接，不执行页面脚本。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from http.client import HTTPException
import codecs
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS

SOURCE = "iwencai"
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_IGNORE = {"script", "style", "nav", "aside", "footer", "form", "button", "select", "textarea", "noscript", "iframe", "svg", "canvas", "template"}
_BLOCK = {"p", "div", "section", "article", "main", "li", "ul", "ol", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "pre", "dl", "dt", "dd"}
_BODY_NAMES = {
    "js_content", "art_contextbox", "quick_content", "content_article", "blk_container",
    "articlebody", "article_body", "article-body", "article_content", "article-content",
    "articlecontent", "post-content", "entry-content", "post_content", "entry_content",
    "news-content", "news_content", "newsbody", "news_body", "text_content", "text-content",
}
_INNER_BODIES = {"js_content", "art_contextbox", "quick_content", "content_article", "blk_container", "articlebody", "article_body", "article-body"}
_NOISE = re.compile(r"(?:^|[\s_-])(?:nav|navigation|sidebar|footer|comment|comments|share|sharing|social|advert|advertisement|ads|ad|recommend|recommended|related|pagination|download|toolbar)(?:$|[\s_-])", re.I)
_BEIJING = timezone(timedelta(hours=8))
_NO_BODY = "页面没有可确认的可读正文，可能为登录、验证、下载页面或动态空壳"


def _fail(message):
    raise SourceError(SOURCE, message)


def _url(value):
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == "\\" for c in value):
        raise ValueError("url 必须为合法的 HTTP(S) 链接")
    try:
        p = urlsplit(value)
        if p.scheme.lower() not in ("http", "https") or not p.hostname or p.port == 0:
            raise ValueError
        if re.search(r"%(?![0-9a-fA-F]{2})", value):
            raise ValueError
        p.port
        return value
    except ValueError:
        raise ValueError("url 必须为合法的 HTTP(S) 链接") from None


def _request_url(value):
    p = urlsplit(value)
    return urlunsplit((p.scheme, p.netloc.encode("idna").decode("ascii"), quote(p.path, safe="/%:@!$&'()*+,;=-._~"), quote(p.query, safe="%=&[]:/?+;,@!$'()*~-._"), ""))


def _pdf_link(url):
    p = urlsplit(url)
    if p.path.lower().endswith(".pdf"):
        return True
    for key, value in parse_qsl(p.query, keep_blank_values=True):
        if key.lower() == "filename" and value.lower().endswith(".pdf"):
            return True
        if key == "bo":
            try:
                obj = json.loads(value)
            except (ValueError, TypeError):
                continue
            if isinstance(obj, dict) and isinstance(obj.get("fileName"), str) and obj["fileName"].lower().endswith(".pdf"):
                return True
    return False


def _pdf_result(url):
    return dict(title=None, publication_date=None, institute=None, researcher=None,
                content=None, original_url=url, file_type="pdf")


def _fetch(url, timeout):
    request = Request(_request_url(url), headers={**DEFAULT_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.5"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                _fail(f"HTTP 请求失败（状态码 {response.status}）")
            final_url = _url(response.geturl())
            content_type = response.headers.get("Content-Type", "")
            if content_type.split(";", 1)[0].strip().lower() == "application/pdf" or _pdf_link(final_url):
                return None, content_type, final_url
            prefix = response.read(4096)
            if prefix.lstrip().startswith(b"%PDF-"):
                return None, content_type, final_url
            return prefix + response.read(), content_type, final_url
    except HTTPError as exc:
        raise SourceError(SOURCE, f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException, UnicodeError) as exc:
        raise SourceError(SOURCE, f"网络请求失败（{type(exc).__name__}）") from exc
    except ValueError as exc:
        raise SourceError(SOURCE, "来源返回了无效的最终链接") from exc


def _decode(body, content_type):
    encodings = []
    if body.startswith(b"\xef\xbb\xbf"):
        encodings.append("utf-8-sig")
    header = re.search(r"charset\s*=\s*[\"']?([^\s;\"']+)", content_type, re.I)
    if header:
        encodings.append(header.group(1))
    for tag in re.findall(rb"<meta\b[^>]*>", body[:16384], re.I):
        declaration = re.search(rb"charset\s*=\s*[\"']?([^\s;\"'/>]+)", tag, re.I)
        if declaration:
            try:
                encodings.append(declaration.group(1).decode("ascii", "strict"))
            except UnicodeDecodeError:
                continue
    # Some publishers declare GB2312 while serving the compatible GBK superset.
    encodings.extend(["utf-8", "gb18030"])
    for encoding in dict.fromkeys(encodings):
        try:
            normalized = codecs.lookup(encoding).name
            if normalized in {"gb2312", "gbk"}:
                normalized = "gb18030"
            return body.decode(normalized, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
    _fail("响应正文编码无法读取")


@dataclass
class _Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: object = field(default=None, repr=False)


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        if tag == "p" and self.stack[-1].tag == "p":
            self.stack.pop()
        node = _Node(tag, {key: value or "" for key, value in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed([child for child in current.children if isinstance(child, _Node)]))


def _noise(node):
    if node.tag in {"root", "html", "body"}:
        return False
    return node.tag in _IGNORE or bool(_NOISE.search(node.attrs.get("id", "") + " " + node.attrs.get("class", "")))


def _visible_nodes(node):
    stack = [node]
    while stack:
        current = stack.pop()
        if _noise(current):
            continue
        yield current
        stack.extend(reversed([child for child in current.children if isinstance(child, _Node)]))


def _text(node, *, excluded=(), omit_links=False):
    output = []
    stack = [(node, False)]
    while stack:
        item, closing = stack.pop()
        if isinstance(item, str):
            output.append(item)
        elif closing:
            if item.tag in {"td", "th"}:
                output.append("\t")
            elif item.tag in _BLOCK:
                output.append("\n")
        elif id(item) not in excluded and not _noise(item) and not (omit_links and item.tag == "a"):
            if item.tag == "br":
                output.append("\n")
            else:
                if item.tag in _BLOCK:
                    output.append("\n")
                stack.append((item, True))
                stack.extend((child, False) for child in reversed(item.children))
    return "\n".join(line.strip() for line in re.sub(r"[ \u00a0\u3000]+", " ", "".join(output)).splitlines() if line.strip())


def _date(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    match = re.fullmatch(r"([0-9]{4})[-/]([0-9]{1,2})[-/]([0-9]{1,2})(?:[ T]([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?(Z|[+-][0-9]{2}:[0-9]{2})?)?", value)
    if not match:
        return None
    y, m, d, hour, minute, second, offset = match.groups()
    try:
        day = datetime(int(y), int(m), int(d))
        if hour is None:
            return day.date().isoformat()
        datetime(int(y), int(m), int(d), int(hour), int(minute), int(second or 0))
        formatted = f"{day.date().isoformat()}T{hour}:{minute}" + (f":{second}" if second is not None else "")
        result = datetime.fromisoformat(formatted + ("+00:00" if offset == "Z" else offset or "+08:00")).astimezone(_BEIJING)
        return result.isoformat(timespec="seconds" if second is not None else "minutes")
    except ValueError:
        return None


def _metadata(nodes, selected):
    metas = {}
    for n in nodes:
        if n.tag == "meta":
            key = n.attrs.get("property") or n.attrs.get("name") or n.attrs.get("itemprop")
            if key and n.attrs.get("content"):
                metas.setdefault(key.lower(), n.attrs["content"].strip())
    headings = [n for n in _walk(selected) if n.tag == "h1"] if selected else []
    headings += [n for n in nodes if n.tag == "h1"]
    title = next((_text(n) for n in headings if _text(n)), None) or metas.get("og:title") or next((_text(n) for n in nodes if n.tag == "title" and _text(n)), None)
    date_values = [metas.get(key) for key in ("article:published_time", "datepublished", "pubdate", "publishdate", "bytedance:published_time")]
    institute = metas.get("institute") or metas.get("organize")
    researcher = metas.get("researcher") or metas.get("analyst")
    for node in nodes:
        attrs = node.attrs
        prop = attrs.get("itemprop", "").lower().split()
        if "datepublished" in prop or attrs.get("class", "").lower() in {"published", "publish-time", "pubtime"}:
            date_values.append(attrs.get("datetime") or attrs.get("content") or _text(node))
        labels = attrs.get("class", "").split()
        if "time-from" in labels or attrs.get("id") == "publish_time":
            date_values.extend(_text(child) for child in node.children if isinstance(child, _Node))
            date_values.append(_text(node))
        if "creab" in labels:
            for child in node.children:
                if isinstance(child, _Node):
                    label = _text(child)
                    if label.startswith("机构："):
                        institute = label[3:].strip() or None
                    elif label.startswith("研究员："):
                        researcher = label[4:].strip() or None
                    elif label.startswith("日期："):
                        date_values.append(label[3:].strip())
    return title, next((result for value in date_values if (result := _date(value))), None), institute, researcher


def _body_score(node):
    names = {node.attrs.get("id", "").lower(), *node.attrs.get("class", "").lower().split()}
    if names & _INNER_BODIES:
        return 140
    if names & _BODY_NAMES:
        return 120
    if "articlebody" in node.attrs.get("itemprop", "").lower().split():
        return 130
    if node.tag == "article":
        return 100
    if node.tag == "main" or node.attrs.get("role") == "main":
        return 70
    if node.tag in {"div", "section"} and names & {"content", "article", "post", "正文"}:
        return 50
    return 0


def _blocked(text):
    compact = re.sub(r"\s+", "", text).lower()
    return bool(re.fullmatch(r"(?:用户|账号|账户)?(?:登录|登陆)(?:请输入(?:账号|用户名|密码))*|验证码|安全验证|环境异常|点击下载(?:文件|报告|pdf)?|下载(?:文件|报告|pdf)", compact)) or len(compact) < 500 and bool(re.search(r"(?:请|必须|需要)(?:先)?(?:登录|登陆|完成验证|输入验证码)|访问(?:受限|异常)|安全验证|环境异常|click(?:here)?todownload|请开启javascript|请启用javascript|点击下载(?:文件|报告|pdf)|下载文件后", compact))


def _pdf_targets(node, final_url):
    targets = []
    for current in _walk(node):
        attribute = {"a": "href", "iframe": "src", "embed": "src", "object": "data"}.get(current.tag)
        value = current.attrs.get(attribute) if attribute else None
        ancestors = _ancestors(current, node)
        if any(n.tag in _IGNORE - {"iframe"} or _NOISE.search(re.sub(r"(?:^|[\s_-])download(?=$|[\s_-])", "", n.attrs.get("id", "") + " " + n.attrs.get("class", ""), flags=re.I)) for n in ancestors):
            continue
        if value and (_pdf_link(value) or current.attrs.get("type", "").lower() == "application/pdf"):
            try:
                target = _url(urljoin(final_url, value))
            except ValueError:
                continue
            if target not in targets:
                targets.append(target)
    return targets


def _ancestors(node, stop):
    while node is not None:
        yield node
        if node is stop:
            break
        node = node.parent


def _pdf_wrapper(node, final_url):
    targets = _pdf_targets(node, final_url)
    if len(targets) != 1:
        return None
    headings = {id(n) for n in _walk(node) if n.tag in {"h1", "h2", "h3", "object", "embed", "iframe"}}
    prose = _text(node, excluded=headings, omit_links=True)
    if not prose or _blocked(prose):
        return targets[0]
    return None


def _jsonld(nodes):
    for node in nodes:
        if node.tag != "script" or node.attrs.get("type", "").lower() != "application/ld+json":
            continue
        try:
            value = json.loads("".join(c for c in node.children if isinstance(c, str)))
        except (ValueError, TypeError):
            continue
        stack = [value]
        while stack:
            obj = stack.pop()
            if isinstance(obj, list):
                stack.extend(reversed(obj))
            elif isinstance(obj, dict):
                types = obj.get("@type", [])
                types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
                body = obj.get("articleBody")
                if any(isinstance(t, str) and t.rsplit("/", 1)[-1] in {"Article", "NewsArticle", "Report"} for t in types) and isinstance(body, str) and body.strip():
                    if _blocked(body):
                        continue
                    def optional(key):
                        return obj[key].strip() or None if isinstance(obj.get(key), str) else None
                    return dict(title=optional("headline") or optional("name"), publication_date=_date(obj.get("datePublished")), institute=optional("institute"), researcher=optional("researcher"), content=body.replace("\r\n", "\n").replace("\r", "\n").strip(), original_url=None, file_type=None)
                stack.extend(reversed(list(obj.values())))
    return None


def _extract(body, content_type, final_url):
    markup = _decode(body, content_type)
    parser = _Tree()
    try:
        parser.feed(markup)
        parser.close()
    except (ValueError, RecursionError) as exc:
        raise SourceError(SOURCE, "HTML 正文无法解析") from exc
    nodes = list(_walk(parser.root))
    candidates = []
    pdf_candidates = []
    for node in nodes:
        score = _body_score(node)
        if score and not any(_noise(n) for n in _ancestors(node, parser.root)):
            pdf = _pdf_wrapper(node, final_url)
            if pdf:
                pdf_candidates.append(pdf)
                continue
            content = _text(node)
            prose = _text(node, omit_links=True)
            if content and (prose or score >= 100) and not _blocked(content):
                candidates.append((score, len(content), node, content))
    if not candidates:
        # Actual prose, rather than a character count, distinguishes a short body.
        for node in nodes:
            if node.tag not in {"body", "div", "section"} or any(_noise(n) for n in _ancestors(node, parser.root)):
                continue
            paragraphs = [_text(n, omit_links=True) for n in _visible_nodes(node) if n.tag == "p"]
            if any(paragraphs):
                content = _text(node)
                if content and not _blocked(content):
                    candidates.append((10, len(content), node, content))
    if not candidates:
        json_body = _jsonld(nodes)
        if json_body:
            return json_body
        pdfs = set(pdf_candidates)
        if len(pdfs) == 1:
            return _pdf_result(next(iter(pdfs)))
        if len(pdfs) > 1:
            _fail("页面只有多个不同 PDF 链接，无法确定单篇正文文档")
        pdf = _pdf_wrapper(parser.root, final_url)
        if pdf:
            return _pdf_result(pdf)
        _fail(_NO_BODY)
    _, _, selected, content = max(candidates, key=lambda row: row[:2])
    title, publication_date, institute, researcher = _metadata(nodes, selected)
    targets = _pdf_targets(selected, final_url)
    original_url = targets[0] if len(targets) == 1 else None
    return dict(title=title, publication_date=publication_date, institute=institute,
                researcher=researcher, content=content, original_url=original_url,
                file_type="pdf" if original_url else None)


def _operate_target(url):
    parts = urlsplit(url)
    if parts.hostname != "basic.10jqka.com.cn" or parts.path != "/astockpc/astockmain/index.html":
        return None
    route, separator, query = parts.fragment.partition("?")
    if route not in {"/operate", "operate"} or not separator:
        return None
    pairs = parse_qsl(query, keep_blank_values=True)
    codes = [value for key, value in pairs if key == "code"]
    markets = [value for key, value in pairs if key == "marketid"]
    if len(codes) != 1 or not re.fullmatch(r"[0-9]{6}", codes[0]) or len(markets) > 1:
        return None
    # The official route metadata maps /operate to /operate.html.
    return f"https://basic.10jqka.com.cn/{codes[0]}/operate.html", codes[0], markets[0] if markets else None


def _operate(body, content_type, code, market):
    parser = _Tree()
    parser.feed(_decode(body, content_type))
    nodes = list(_walk(parser.root))
    inputs = {n.attrs.get("id"): n.attrs.get("value") for n in nodes if n.tag == "input"}
    if inputs.get("stockCode") != code or market is not None and inputs.get("marketId") != market:
        _fail("公开经营分析正文与请求股票身份不一致")
    blocks = [n for n in nodes if n.attrs.get("stat", "").startswith("operate_")]
    excluded = set()
    for block in blocks:
        for node in _walk(block):
            classes = node.attrs.get("class", "").split()
            if "m_tab" in classes or "m_tab_content" in classes and re.search(r"display\s*:\s*none", node.attrs.get("style", ""), re.I):
                excluded.add(id(node))
            if node.tag == "a" and set(classes) & {"more", "less"}:
                excluded.add(id(node))
            if node.tag == "p" and any(isinstance(c, _Node) and c.tag == "a" and "more" in c.attrs.get("class", "").split() for c in node.children):
                # This source provides the complete counterpart in the next p.
                if any(isinstance(c, _Node) and c.tag == "p" and "none" in c.attrs.get("class", "").split() for c in node.parent.children):
                    excluded.add(id(node))
    content = "\n".join(value for block in blocks if (value := _text(block, excluded=excluded)))
    if not content or _blocked(content):
        _fail("公开经营分析页面没有可读业务正文")
    title = next((_text(n) for n in nodes if n.tag == "title" and _text(n)), None)
    return dict(title=title, publication_date=None, institute=None, researcher=None,
                content=content, original_url=None, file_type=None)


def read_document(url, *, timeout):
    """读取合法 HTTP(S) 页面正文；纯 PDF 仅返回实际链接。"""
    _url(url)
    seconds = validate_timeout(timeout)
    if _pdf_link(url):
        return _pdf_result(url)
    body, content_type, final_url = _fetch(url, seconds)
    if body is None:
        return _pdf_result(final_url)
    target = _operate_target(url)
    if target:
        try:
            return _extract(body, content_type, final_url)
        except SourceError as exc:
            if exc.reason != _NO_BODY:
                raise
        # The supplied SPA has no text; its official old page has the same business.
        old_url, code, market = target
        old_body, old_type, old_final = _fetch(old_url, seconds)
        if old_body is None:
            _fail("经营分析来源没有返回公开 HTML 正文")
        return _operate(old_body, old_type, code, market)
    try:
        return _extract(body, content_type, final_url)
    except SourceError as exc:
        final = urlsplit(final_url)
        if exc.reason == _NO_BODY and final.hostname == "mp.weixin.qq.com" and final.path == "/mp/wappoc_appmsgcaptcha":
            raise SourceError(SOURCE, "微信返回了访问验证页面，当前请求未取得文章正文") from None
        raise
