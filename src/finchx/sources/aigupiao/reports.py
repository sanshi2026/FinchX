"""爱股票匿名研报目录与独立网页摘要，不下载原报告。"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import math
import re
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlsplit

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json, get_text, post_form_json
from finchx._common.news import BEIJING_TZ

_SOURCE = "aigupiao"
_LIST = "https://app.aigupiao.com/goapi/report/search"
_INDUSTRIES = "https://app.aigupiao.com/v2/report/getIndustryInfos"
_DETAIL = "http://101.35.29.159:82/report/detail_m.php?id="
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://report.aigupiao.com/"}
_MAX_ROWS = 100
_MAX_BEFORE = 253402300799


def _text(value: Any, name: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise SourceError(_SOURCE, f"字段 {name} 必须是字符串或空值")


def _identity(value: Any, name: str, *, positive: bool = False) -> str:
    if type(value) is int and value >= 0:
        value = str(value)
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        if not positive or int(value) > 0:
            return value
    raise SourceError(_SOURCE, f"字段 {name} 必须是有效 ASCII 数字身份")


def _integer(value: Any, name: str) -> int:
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    if type(value) is not int or value < 0:
        raise SourceError(_SOURCE, f"字段 {name} 必须是非负整数")
    return value


def _filter(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if (not isinstance(value, str) or len(value) > 2000
            or re.search(r"[\x00-\x1f\x7f]", value)):
        raise ValueError(f"{name} 必须是最多 2000 字符且无控制字符的字符串或 None")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} 必须是有效 Unicode 字符串") from exc
    return value.strip() or None


def _publication_text(value: Any) -> str | None:
    text = _text(value, "pub_time")
    if text is None or text == "":
        return text
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8}", text):
            # Python 3.10 仅接受带连字符的 ISO 日期；来源原文仍原样保留。
            normalized = f"{text[:4]}-{text[4:6]}-{text[6:]}" if len(text) == 8 else text
            date.fromisoformat(normalized)
        elif re.fullmatch(r"[0-9]{2}-[0-9]{2}", text):
            # 校验月日而不填造来源缺失的年份；闰日仍是有效月日。
            date.fromisoformat("2000-" + text)
        else:
            raise ValueError
    except ValueError as exc:
        raise SourceError(_SOURCE, "pub_time 不是有效来源日期文字") from exc
    return text


def _recorded(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SourceError(_SOURCE, "rec_time 必须是完整来源 UTC 时间或空值")
    match = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(\.[0-9]+)?Z", value)
    if match is None:
        raise SourceError(_SOURCE, "rec_time 不是有效来源 UTC 时间")
    try:
        stamp = match[1]
        moment = datetime(
            int(stamp[:4]), int(stamp[5:7]), int(stamp[8:10]),
            int(stamp[11:13]), int(stamp[14:16]), int(stamp[17:19]),
            tzinfo=timezone.utc,
        ).astimezone(BEIJING_TZ)
    except (ValueError, OverflowError) as exc:
        raise SourceError(_SOURCE, "rec_time 不是有效来源 UTC 时间") from exc
    return moment.isoformat(timespec="seconds")[:-6] + (match[2] or "") + "+08:00"


def _rating(value: Any) -> Any:
    if value is None or isinstance(value, str) or type(value) is int:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise SourceError(_SOURCE, "rating 必须是有效来源评级文字、有限数值或空值")


def _industry(value: str, *, timeout: float) -> str:
    payload = get_json(_INDUSTRIES, timeout=timeout, headers=_HEADERS, source=_SOURCE)
    _success(payload)
    items = payload.get("list")
    if not isinstance(items, list) or not 0 < len(items) <= 10000:
        raise SourceError(_SOURCE, "行业字典必须是非空的合法数组")
    matches = set()
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get("symbol"), str)
                or re.fullmatch(r"[0-9]{1,64}", item["symbol"]) is None
                or not isinstance(item.get("name"), str) or not item["name"].strip()):
            raise SourceError(_SOURCE, "行业字典名称或代码结构无效")
        pair = (item["symbol"], item["name"].strip())
        if value in pair:
            matches.add(pair)
    if len(matches) != 1:
        raise ValueError("industry 不在当前来源行业字典中或存在歧义")
    return next(iter(matches))[0]


def _success(payload: Any) -> None:
    if (not isinstance(payload, dict) or type(payload.get("code")) is not int
            or payload["code"] != 0 or payload.get("status") != "succ"):
        raise SourceError(_SOURCE, "研报来源状态表示请求失败")


def _page(payload: Any, *, before: int, kind: str, industry: str | None) -> list[tuple[str, int, dict]]:
    _success(payload)
    # 这两个计数随 before 变化，只校验结构，不宣称全库完整数量。
    _integer(payload.get("total"), "total")
    _integer(payload.get("last_page"), "last_page")
    items = payload.get("data")
    if not isinstance(items, list) or len(items) > _MAX_ROWS:
        raise SourceError(_SOURCE, "研报 data 必须是防护范围内的完整数组")
    template = payload.get("inv_url")
    # 官网本身以固定已核模板构建链接；可选响应模板不提供时不丢业务行。
    if template is not None and template != "" and template != _DETAIL:
        raise SourceError(_SOURCE, "研报详情链接模板未获确认")
    rows, seen = [], set()
    previous = None
    for item in items:
        if not isinstance(item, dict):
            raise SourceError(_SOURCE, "研报目录条目必须是对象")
        identity = _identity(item.get("inv_id"), "inv_id", positive=True)
        if identity in seen:
            raise SourceError(_SOURCE, "研报目录同页 inv_id 重复")
        seen.add(identity)
        position = _integer(item.get("sort_time"), "sort_time")
        if position > _MAX_BEFORE or before and position >= before:
            raise SourceError(_SOURCE, "研报来源未遵守排他 before 边界")
        if previous is not None and position > previous:
            raise SourceError(_SOURCE, "研报目录未按 sort_time 降序返回")
        previous = position
        ref_kind = _text(item.get("ref_kind"), "ref_kind")
        ref_code = _text(item.get("ref_symbol"), "ref_symbol")
        symbol = _text(item.get("stock_code"), "stock_code")
        if kind == "stock" and ref_kind != "stock":
            raise SourceError(_SOURCE, "来源未遵守个股研报类别筛选")
        if kind == "industry" and ref_kind not in {"industry", "行业"}:
            raise SourceError(_SOURCE, "来源未遵守行业研报类别筛选")
        if industry is not None and ref_code != industry:
            raise SourceError(_SOURCE, "来源未遵守精确行业代码筛选")
        theme = item.get("theme_id")
        if theme is not None:
            _identity(theme, "theme_id")
        row = {"url": _DETAIL + identity, "title": _text(item.get("title"), "title"),
               "kind": ref_kind, "ref_code": ref_code, "name": _text(item.get("name"), "name"),
               "institute": _text(item.get("institute"), "institute"), "rating": _rating(item.get("rating")),
               "publication_date_text": _publication_text(item.get("pub_time")),
               "recorded_at": _recorded(item.get("rec_time")), "symbol": symbol, "theme_id": theme}
        rows.append((identity, position, row))
    return rows


def _url(url: Any) -> str:
    message = "url 必须是已核爱股票研报 detail_m.php?id=ASCII数字 地址"
    if not isinstance(url, str) or "#" in url or re.search(r"[\s\\\x00-\x1f\x7f]", url):
        raise ValueError(message)
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        if (parsed.scheme != "http" or parsed.netloc != "101.35.29.159:82"
                or parsed.path != "/report/detail_m.php" or parsed.fragment
                or re.fullmatch(r"id=[0-9]+", parsed.query) is None
                or len(pairs) != 1 or pairs[0][0] != "id"
                or re.fullmatch(r"[0-9]+", pairs[0][1]) is None):
            raise ValueError(message)
    except ValueError as exc:
        raise ValueError(message) from exc
    return pairs[0][1]


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list = field(default_factory=list)


class _HTML(HTMLParser):
    _void = {"br", "hr", "img", "meta", "link", "input", "wbr", "source", "embed", "area", "base", "param", "col"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = _Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in self._void:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag and tag not in self._void:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _walk(node: _Node):
    yield node
    for child in node.children:
        if isinstance(child, _Node):
            yield from _walk(child)


def _plain(node: _Node, excluded: set[int] | None = None) -> str:
    blocks = {"div", "p", "br", "li", "ul", "ol", "section", "blockquote", "pre", "table", "tr",
              "h1", "h2", "h3", "h4", "h5", "h6"}

    def text(current: _Node) -> str:
        if current.tag in {"script", "style", "noscript", "template"} or excluded and id(current) in excluded:
            return ""
        value = "".join(child if isinstance(child, str) else text(child) for child in current.children)
        if current.tag in {"td", "th"}:
            return value + "\t"
        return "\n" + value + "\n" if current.tag in blocks else value

    return "\n".join(re.sub(r"[ \r\f\v]+", " ", line).strip()
                     for line in text(node).splitlines() if line.strip())


def _pdf(href: str, url: str) -> str | None:
    if re.search(r"[\s\\\x00-\x1f\x7f]", href):
        raise SourceError(_SOURCE, "来源 PDF 地址含非法字符")
    resolved = urljoin(url, href)
    try:
        parsed = urlsplit(resolved)
        port = parsed.port
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or port is not None and not 1 <= port <= 65535):
            raise ValueError
    except ValueError as exc:
        raise SourceError(_SOURCE, "来源 PDF 地址无效") from exc
    if not parsed.path.lower().endswith(".pdf"):
        return None
    return href if urlsplit(href).scheme else resolved


def _detail(page: str, *, url: str, identity: str) -> dict:
    parser = _HTML()
    parser.feed(page)
    parser.close()
    nodes = list(_walk(parser.root))
    for node in nodes:
        if node.tag == "script" and node.attrs.get("src"):
            try:
                parsed = urlsplit(node.attrs["src"])
            except ValueError as exc:
                raise SourceError(_SOURCE, "研报网页脚本地址结构无效") from exc
            if parsed.hostname == "app.aigupiao.com" and parsed.path == "/goapi/report/add_read_records":
                pairs = parse_qsl(parsed.query, keep_blank_values=True)
                values = [value for key, value in pairs if key == "inv_id"]
                if values != [identity]:
                    raise SourceError(_SOURCE, "研报网页身份与请求不一致")
    summaries = [node for node in nodes if "text01" in node.attrs.get("class", "").split()]
    views = [node for node in nodes if "View_tex" in node.attrs.get("class", "").split()]
    if not summaries and not views:
        raise SourceError(_SOURCE, "研报页面缺少已核摘要与 PDF 区域")
    summary_nodes = [node for summary in summaries for node in _walk(summary)]
    titles = [node for node in summary_nodes if node.tag in {"h1", "h2"}]
    labels = "研究机构|机构|研究员|分析师|发布时间|发布日期|日期"
    metadata = [node for node in summary_nodes if node.tag in {"span", "p"}
                and re.match(rf"^(?:{labels})\s*[:：]", _plain(node))]
    values = {}
    mapping = {"研究机构": "institute", "机构": "institute", "研究员": "researcher", "分析师": "researcher",
               "发布时间": "publication_date", "发布日期": "publication_date", "日期": "publication_date"}
    for node in metadata:
        for match in re.finditer(rf"(?:^|\s)({labels})\s*[:：]\s*(.*?)(?=\s+(?:{labels})\s*[:：]|\n|$)", _plain(node)):
            key, value = mapping[match[1]], match[2].strip() or None
            if key in values and values[key] != value:
                raise SourceError(_SOURCE, "研报页面元信息相互冲突")
            values[key] = value
    publication = values.get("publication_date")
    if publication is not None:
        try:
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", publication) is None:
                raise ValueError
            date.fromisoformat(publication)
        except ValueError as exc:
            raise SourceError(_SOURCE, "研报页面明示发布日期无效") from exc
    excluded = {id(node) for node in metadata + titles[:1]}
    summary = "\n".join(_plain(node, excluded) for node in summaries).strip() or None
    if not titles:
        titles = [node for node in nodes if node.tag == "h1"] or [node for node in nodes if node.tag == "title"]
    title = (_plain(titles[0]) or None) if titles else None
    pdfs = []
    for view in views:
        for node in _walk(view):
            if node.tag == "a" and node.attrs.get("href"):
                link = _pdf(node.attrs["href"], url)
                if link is not None and link not in pdfs:
                    pdfs.append(link)
    if summary is None and not pdfs:
        raise SourceError(_SOURCE, "研报页面没有可读摘要或 PDF 链接")
    return {"title": title, "publication_date": publication, "institute": values.get("institute"),
            "researcher": values.get("researcher"), "summary": summary, "pdf_urls": pdfs}


def _get_detail(url: str, *, timeout: float) -> dict:
    """只读取该研报网页的独立摘要和原 PDF 链接。"""
    identity = _url(url)
    page = get_text(url, timeout=validate_timeout(timeout), headers={**_HEADERS, "Accept": "text/html,application/xhtml+xml"},
                    source=_SOURCE, follow_redirects=False)
    return _detail(page, url=url, identity=identity)
