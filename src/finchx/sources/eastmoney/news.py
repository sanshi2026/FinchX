"""东方财富个股文章目录与文章网页，不保存结果。"""

from datetime import datetime
from html.parser import HTMLParser
from http.client import HTTPException
from ipaddress import ip_address
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from finchx._common.convert import resolve_code, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx._common.news import BEIJING_TZ, in_window, validate_limit, validate_window

ENDPOINT = "https://np-listapi.eastmoney.com/comm/web/getListInfo"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://quote.eastmoney.com/"}
_PAGE_SIZE = 20
_MAX_PAGES = 250
_ID = re.compile(r"[0-9]+")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
_HEAD_TIME = re.compile(r"([0-9]{4})年([0-9]{2})月([0-9]{2})日\s+([0-9]{2}:[0-9]{2}(?::[0-9]{2})?)")
_CMS_HOSTS = {"finance.eastmoney.com", "stock.eastmoney.com", "money.eastmoney.com", "insurance.eastmoney.com",
              "hk.eastmoney.com", "biz.eastmoney.com"}


def _fail(reason):
    raise SourceError("eastmoney", reason)


def _optional_text(value, field):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        _fail(f"{field} 必须是文字或空值")
    return value


def _source_time(value):
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        _fail("Art_ShowTime 必须是有效的来源日期时间")
    try:
        return datetime(
            int(value[:4]), int(value[5:7]), int(value[8:10]),
            int(value[11:13]), int(value[14:16]), int(value[17:19]), tzinfo=BEIJING_TZ,
        )
    except ValueError as exc:
        raise SourceError("eastmoney", "Art_ShowTime 日期时间无效") from exc


def _url_parts(value, *, hosts=None, allow_port=False):
    if not isinstance(value, str) or not value or "\\" in value or any(c.isspace() or ord(c) < 33 or 127 <= ord(c) <= 159 for c in value):
        raise ValueError("url 必须是业务链接的 http/https URL")
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
        if (parsed.scheme not in {"http", "https"} or parsed.username is not None
                or parsed.password is not None or not host or parsed.netloc.endswith(":")
                or not allow_port and port is not None or hosts is not None and host not in hosts):
            raise ValueError
        if "[" in parsed.netloc or "]" in parsed.netloc:
            if not re.fullmatch(r"\[[^\]]+\](?::[0-9]+)?", parsed.netloc):
                raise ValueError
            bracketed_host = parsed.netloc[1:].split("]", 1)[0]
            if bracketed_host.startswith("v"):
                if not re.fullmatch(r"v[0-9A-Fa-f]+\..+", bracketed_host):
                    raise ValueError
            elif ip_address(bracketed_host).version != 6:
                raise ValueError
        if ":" in host:
            ip_address(host)
        else:
            domain = host.encode("idna").decode("ascii")
            if len(domain) > 253 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                                        for label in domain.rstrip(".").split(".")):
                raise ValueError
    except (ValueError, UnicodeError) as exc:
        raise ValueError("url 的主机、认证信息或端口无效") from exc
    return parsed


def _article_url(value):
    parsed = _url_parts(value, hosts=_CMS_HOSTS | {"caifuhao.eastmoney.com"})
    host = parsed.hostname
    if host == "caifuhao.eastmoney.com":
        match = re.fullmatch(r"/news/([0-9]+)", parsed.path)
    else:
        match = re.fullmatch(r"/a/([0-9]+)\.html", parsed.path)
    if match is None or parsed.query or parsed.fragment:
        raise ValueError("url 必须是已支持的东方财富文章 URL，不含查询、片段或端口")
    return match.group(1), urlunsplit(("https", host, parsed.path, "", ""))


def _directory_url(value, identity):
    """目录链接不触发网页读取；仅已核路由编号可与目录身份比较。"""
    parsed = _url_parts(value, allow_port=True)
    if parsed.hostname == "caifuhao.eastmoney.com":
        match = re.fullmatch(r"/news/([0-9]+)", parsed.path)
    elif parsed.hostname in _CMS_HOSTS:
        match = re.fullmatch(r"/a/([0-9]+)\.html", parsed.path)
    else:
        match = None
    if match is not None and match.group(1) != identity:
        _fail("Art_Url 与 Art_Code 身份冲突")
    return value


def _parse_row(raw):
    if not isinstance(raw, dict):
        _fail("文章目录行必须是对象")
    identity = raw.get("Art_Code")
    if not isinstance(identity, str) or not _ID.fullmatch(identity):
        _fail("Art_Code 必须是非空 ASCII 数字身份")
    timestamp = _source_time(raw.get("Art_ShowTime"))
    article_url = _optional_text(raw.get("Art_Url"), "Art_Url")
    if article_url is not None:
        try:
            _directory_url(article_url, identity)
        except ValueError as exc:
            raise SourceError("eastmoney", "Art_Url 不是有效的来源业务地址") from exc
    return {
        "id": identity, "title": _optional_text(raw.get("Art_Title"), "Art_Title"),
        "published_at": timestamp.isoformat(), "url": article_url,
        "author": _optional_text(raw.get("Author"), "Author"),
    }, timestamp


def em_list(
    code: str, limit: int = 20, since: str | None = None, until: str | None = None,
    *, timeout: float,
) -> list[dict]:
    """按来源顺序读取个股目录，limit 为时间筛选后最多唯一篇数。"""
    symbol = resolve_code(code)
    limit = validate_limit(limit)
    lower, upper = validate_window(since, until)
    seconds = validate_timeout(timeout)
    market = "1" if symbol.startswith("sh") else "0"
    rows = {}
    all_ids = set()
    total = None
    previous_oldest = None
    ordered = True
    for page in range(1, _MAX_PAGES + 1):
        params = {"cfh": 1, "client": "web", "mTypeAndCode": f"{market}.{code}",
                  "type": 1, "pageSize": _PAGE_SIZE, "pageIndex": page}
        payload = get_json(f"{ENDPOINT}?{urlencode(params)}", timeout=seconds,
                           headers=_HEADERS, source="eastmoney")
        if not isinstance(payload, dict) or type(payload.get("code")) is not int or payload["code"] != 1:
            _fail("文章目录来源未表示成功")
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("list"), list):
            _fail("文章目录缺少有效 data/list")
        for field, expected in (("page_index", page), ("page_size", _PAGE_SIZE)):
            if type(data.get(field)) is not int or data[field] != expected:
                _fail(f"文章目录 {field} 与请求分页不一致")
        count = data.get("totle_hits")
        if type(count) is not int or count < 0:
            _fail("totle_hits 必须是非负整数")
        if total is not None and total != count:
            _fail("文章目录 totle_hits 在分页期间变化")
        total = count
        expected_size = min(_PAGE_SIZE, max(0, total - (page - 1) * _PAGE_SIZE))
        source_rows = data["list"]
        if len(source_rows) != expected_size:
            _fail("文章目录页长度与来源窗口不一致")
        parsed = [_parse_row(raw) for raw in source_rows]
        page_ids = [row["id"] for row, _ in parsed]
        if len(set(page_ids)) != len(page_ids):
            _fail("文章目录同页身份重复")
        timestamps = [stamp for _, stamp in parsed]
        # 非降序来源仍可完整扫描窗口，但不得据下界提前结束。
        if any(a < b for a, b in zip(timestamps, timestamps[1:])):
            ordered = False
        if previous_oldest is not None and timestamps:
            new_times = [stamp for row, stamp in parsed if row["id"] not in all_ids]
            if any(stamp > previous_oldest for stamp in new_times):
                ordered = False
        if timestamps:
            previous_oldest = min(timestamps)
        fresh = set(page_ids) - all_ids
        if source_rows and not fresh:
            _fail("文章目录分页未取得新身份，来源停滞")
        all_ids.update(page_ids)
        if len(all_ids) > total:
            _fail("文章目录唯一身份数超过来源窗口")
        for row, stamp in parsed:
            rows[row["id"]] = (row, stamp)
        matched = [row for row, stamp in rows.values() if in_window(stamp, lower, upper)]
        if len(matched) >= limit:
            return matched[:limit]
        if page * _PAGE_SIZE >= total:
            if len(all_ids) != total:
                _fail("文章目录分页重叠导致来源窗口未完整取齐")
            return matched
        if lower is not None and ordered and timestamps and all(stamp < lower for stamp in timestamps):
            return matched
    _fail("文章目录达到分页防护预算，不能确认查询已完成")


class _Redirect(HTTPRedirectHandler):
    def __init__(self, identity):
        self.identity = identity

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            identity, checked = _article_url(newurl)
        except ValueError as exc:
            raise SourceError("eastmoney", "文章重定向地址无效") from exc
        if identity != self.identity:
            _fail("文章重定向身份与请求不一致")
        return super().redirect_request(req, fp, code, msg, headers, checked)


def _get_html(url, identity, timeout):
    request = Request(url, headers=_HEADERS, method="GET")
    try:
        with build_opener(_Redirect(identity)).open(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                _fail(f"HTTP 请求失败（状态码 {response.status}）")
            final_id, _ = _article_url(response.geturl())
            if final_id != identity:
                _fail("文章响应地址身份与请求不一致")
            return response.read().decode(response.headers.get_content_charset() or "utf-8")
    except HTTPError as exc:
        raise SourceError("eastmoney", f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException, UnicodeError, LookupError, ValueError) as exc:
        raise SourceError("eastmoney", f"文章网页读取失败（{type(exc).__name__}）") from exc


class _Node:
    def __init__(self, tag="root", attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []
        self.closed = tag in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self.stack[-1].children.append(node)
        if not node.closed:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack[-1].closed = True
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack[index].closed = True
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _walk(node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _walk(child)


def _find(node, *, identity=None, class_name=None):
    found = [item for item in _walk(node) if (identity is not None and item.attrs.get("id") == identity) or
             (class_name is not None and class_name in (item.attrs.get("class") or "").split())]
    if len(found) > 1:
        _fail("文章必要结构重复")
    return found[0] if found else None


def _text(node):
    if node is None:
        return ""
    return re.sub(r"\s+", " ", "".join(child if isinstance(child, str) else _text(child)
                                       for child in node.children if not isinstance(child, _Node) or child.tag not in {"script", "style"})).strip()


_SKIP_CLASSES = {"ad_context1", "ad_context2", "ad_context3", "ad_context4", "em_media", "addContent"}
_SKIP_IDS = _SKIP_CLASSES | {"zwaddcontent", "relate_stocks_founds", "imgBulletinAdv1"}
_BLOCKS = {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "table"}


def _content(node, base_url, images):
    if node.tag in {"script", "style", "noscript", "iframe"} or _SKIP_CLASSES.intersection((node.attrs.get("class") or "").split()) or node.attrs.get("id") in _SKIP_IDS:
        return ""
    if node.tag == "img":
        value = node.attrs.get("src")
        if value:
            try:
                resolved = urljoin(base_url, value)
                parts = urlsplit(resolved)
            except ValueError as exc:
                raise SourceError("eastmoney", "正文图片地址无效") from exc
            if parts.scheme not in {"http", "https"} or not parts.hostname:
                _fail("正文图片地址无效")
            if resolved not in images:
                images.append(resolved)
        return ""
    if node.tag == "br":
        return "\n"
    if node.tag == "tr":
        return " | ".join(_content(child, base_url, images).strip() for child in node.children
                          if isinstance(child, _Node) and child.tag in {"th", "td"}) + "\n"
    value = "".join(re.sub(r"\s+", " ", child) if isinstance(child, str) else _content(child, base_url, images)
                    for child in node.children)
    if node.tag in _BLOCKS:
        return value.strip() + "\n\n"
    return value


def _parse_header_time(text):
    match = _HEAD_TIME.fullmatch(text)
    if not match:
        _fail("文章头部日期时间无效")
    clock = match[4]
    try:
        stamp = datetime(
            int(match[1]), int(match[2]), int(match[3]),
            int(clock[:2]), int(clock[3:5]), int(clock[6:8]) if len(clock) == 8 else 0,
            tzinfo=BEIJING_TZ,
        )
    except ValueError as exc:
        raise SourceError("eastmoney", "文章头部日期时间无效") from exc
    return stamp.isoformat(timespec="seconds" if len(match[4]) == 8 else "minutes")


def _published_from_header(text, *, cfh):
    if cfh and text.startswith("修改于"):
        # 来源只披露修改时间时不能把它当作发布时间。
        _parse_header_time(text[3:].strip())
        return None
    return _parse_header_time(text)


def _parse_html(text, identity, url):
    tree = _Tree()
    try:
        tree.feed(text)
        tree.close()
    except Exception as exc:
        raise SourceError("eastmoney", "文章 HTML 无法解析") from exc
    cfh = urlsplit(url).hostname == "caifuhao.eastmoney.com"
    scripts = [_text_script(n) for n in _walk(tree.root) if n.tag == "script"]
    script = "\n".join(scripts)
    if cfh:
        objects = re.findall(r"\b(?:var|let|const)\s+accountInfo\s*=\s*\{(.*?)\}", script, re.DOTALL)
        identities = []
        for account in objects:
            values = re.findall(r"(?:^|,)\s*(?://[^\n]*\n\s*)?articleid\s*:\s*['\"]([0-9]+)['\"]", account)
            if len(values) != 1:
                _fail("文章 accountInfo 缺少唯一合法 articleid")
            identities.extend(values)
    else:
        identities = re.findall(r"\b(?:var|let|const)\s+(?:_NewsId|HTML_NewsId)\s*=\s*['\"]([0-9]+)['\"]", script)
    if not identities or any(value != identity for value in identities):
        _fail("文章网页身份缺失或与 URL 冲突")
    body = _find(tree.root, identity="ContentBody")
    if cfh and body is None:
        body = _find(tree.root, class_name="article-body")
    header = _find(tree.root, class_name="article-head") if cfh else _find(tree.root, identity="topbox")
    if body is None or header is None or not body.closed or not header.closed:
        _fail("文章缺少完整的正文或头部结构")
    title_node = _find(header, class_name="article-title" if cfh else "title")
    title = _text(title_node)
    if title_node is None or not title_node.closed or not title:
        _fail("文章头部标题缺失或结构不完整")
    metadata = _find(header, class_name="article-meta" if cfh else "infos")
    if metadata is None or not metadata.closed:
        _fail("文章头部元信息结构缺失或不完整")
    time_nodes = [node for node in _walk(metadata) if ("txt" if cfh else "item") in (node.attrs.get("class") or "").split()]
    if not time_nodes:
        _fail("文章头部日期位置缺失")
    time_text = _text(time_nodes[0])
    published = _published_from_header(time_text, cfh=cfh) if time_text else None
    source_name = None
    author = None
    for node in _walk(metadata):
        classes = (node.attrs.get("class") or "").split()
        value = _text(node)
        if (cfh and "txt" in classes) or (not cfh and "item" in classes):
            if node is time_nodes[0]:
                continue
            if _HEAD_TIME.fullmatch(value) or cfh and value.startswith("修改于"):
                _fail("文章头部日期时间重复")
            elif value.startswith(("来源：", "来源:")):
                source_name = value[3:].strip() or None
            elif value.startswith(("作者：", "作者:")):
                author = value[3:].strip() or None
    if cfh:
        author_node = _find(metadata, class_name="auth")
        author = _text(author_node) or None
    images = []
    content = "\n".join(line.strip() for line in _content(body, url, images).splitlines())
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    if not content and not images:
        _fail("文章正文为空")
    return {"id": identity, "title": title, "published_at": published, "source_name": source_name,
            "author": author, "content": content, "image_urls": images}


def _text_script(node):
    return "".join(child for child in node.children if isinstance(child, str))


def em_get(url: str, *, timeout: float) -> dict:
    """读取目录中的一个文章网页，身份与正文必须由同份来源确认。"""
    identity, checked = _article_url(url)
    seconds = validate_timeout(timeout)
    return _parse_html(_get_html(checked, identity, seconds), identity, checked)
