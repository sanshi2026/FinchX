"""同花顺概念目录、点位快照和日线。"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

from finchx._common.convert import parse_date, parse_date_parameter, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

SOURCE = "tonghuashun.concept"
LIST_URL = "https://q.10jqka.com.cn/gn/"
DETAIL_URL = "https://q.10jqka.com.cn/gn/detail/code/{}/"
QUOTE_URL = "https://d.10jqka.com.cn/v2/realhead/bk_{}/last.js"
KLINE_URL = "https://d.10jqka.com.cn/v4/line/bk_{}/01/{}.js"
HEADERS = {**DEFAULT_HEADERS, "Referer": LIST_URL}
_CHINA = timezone(timedelta(hours=8))
_CODE = re.compile(r"[0-9]{6}")
_QUOTE_ID = re.compile(r"[0-9]{5,10}")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def _fail(reason: str) -> None:
    raise SourceError(SOURCE, reason)


class _Node:
    def __init__(self, tag: str, attrs: dict | None = None) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[_Node | str] = []

    def text(self) -> str:
        return "".join(child.text() if isinstance(child, _Node) else child for child in self.children)

    def find(self, tag: str):
        for child in self.children:
            if isinstance(child, _Node):
                if child.tag == tag:
                    yield child
                yield from child.find(tag)


class _HTML(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]
        self.feed(text)
        self.close()

    def handle_starttag(self, tag: str, attrs: list) -> None:
        node = _Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _name(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} 必须是非空文本")
    return " ".join(value.split())


def _identity(value, field: str, pattern=_CODE) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        _fail(f"{field} 身份无效")
    return value


def _validate_code(code: str) -> None:
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise ValueError("code 必须是六位 ASCII 数字概念详情页代码")


def _get(url: str, timeout: float) -> str:
    return get_text(url, timeout=timeout, headers=HEADERS, source=SOURCE, encoding="gb18030")


def _reject_constant(value: str):
    _fail(f"JSON 数值 {value} 不是有限数字")


def _json(text: str) -> dict:
    try:
        payload = json.loads(text, parse_float=Decimal, parse_constant=_reject_constant)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SourceError(SOURCE, "响应不是有效的 JSON 对象") from exc
    if not isinstance(payload, dict):
        _fail("响应必须是 JSON 对象")
    return payload


def _parse_jsonp(text: str) -> dict:
    if not isinstance(text, str):
        _fail("JSONP 响应不是文本")
    match = re.fullmatch(r"\s*[A-Za-z_$][A-Za-z0-9_.$]*\s*\(\s*(\{.*\})\s*\)\s*;?\s*", text, re.S)
    if match is None:
        _fail("响应不是有效的 JSONP")
    return _json(match.group(1))


def _parse_directory(text: str) -> list[dict]:
    root = _HTML(text).root
    names: dict[str, str] = {}

    def add(code, name):
        code = _identity(code, "概念 code")
        name = _name(name, "概念 name")
        if code in names and names[code] != name:
            _fail(f"概念 {code} 名称冲突")
        names[code] = name

    for anchor in root.find("a"):
        href = anchor.attrs.get("href")
        if not isinstance(href, str):
            continue
        try:
            url = urlsplit(urljoin(LIST_URL, href))
        except ValueError:
            continue
        if url.scheme not in {"http", "https"} or url.netloc.lower() != "q.10jqka.com.cn":
            continue
        match = re.fullmatch(r"/gn/detail/code/([0-9]{6})/", url.path)
        if match:
            add(match.group(1), anchor.text())
        elif url.path.startswith("/gn/detail/code/"):
            _fail("概念详情链接 code 身份无效")

    sections = [node for node in root.find("input") if node.attrs.get("id") == "gnSection"]
    if len(sections) > 1:
        _fail("概念目录 gnSection 重复")
    quote_codes: dict[str, str] = {}
    page_quotes: dict[str, str] = {}
    if sections:
        payload = _json(sections[0].attrs.get("value"))
        for row in payload.values():
            if not isinstance(row, dict):
                _fail("gnSection 概念行不是对象")
            code = _identity(row.get("cid"), "gnSection cid")
            quote_id = _identity(row.get("platecode"), "gnSection platecode", _QUOTE_ID)
            if code in page_quotes and page_quotes[code] != quote_id:
                _fail(f"概念 {code} 行情身份冲突")
            if quote_id in quote_codes and quote_codes[quote_id] != code:
                _fail(f"概念行情 {quote_id} 详情身份冲突")
            page_quotes[code], quote_codes[quote_id] = quote_id, code
            add(code, row.get("platename"))
    if not names:
        _fail("概念目录没有有效概念记录")
    return [{"code": code, "name": names[code]} for code in sorted(names)]


def _parse_detail(text: str, code: str) -> tuple[str, str, str | None]:
    root = _HTML(text).root
    inputs = {}
    for node in root.find("input"):
        key = node.attrs.get("id")
        if key in {"requestQuery", "clid"}:
            if key in inputs:
                _fail(f"详情身份 {key} 重复")
            inputs[key] = node.attrs.get("value")
    if inputs.get("requestQuery") != f"code/{code}":
        _fail("详情页 code 与请求不一致")
    quote_id = _identity(inputs.get("clid"), "详情 clid", _QUOTE_ID)
    headings = []
    for node in root.find("div"):
        if "board-hq" in (node.attrs.get("class") or "").split():
            headings.extend(node.find("h3"))
    if len(headings) != 1:
        _fail("详情页没有唯一概念行情标题")
    heading = headings[0]
    spans = list(heading.find("span"))
    if len(spans) != 1 or spans[0].text().strip() != quote_id:
        _fail("详情页概念行情身份不一致")
    name = _name("".join(child.text() if isinstance(child, _Node) else child for child in heading.children if child is not spans[0]), "详情 name")
    flows = []
    for node in root.find("dl"):
        labels = list(node.find("dt"))
        if any(label.text().strip() == "资金净流入(亿)" for label in labels):
            values = list(node.find("dd"))
            if len(labels) != 1 or len(values) != 1:
                _fail("详情资金净流入结构无效")
            flows.append(values[0].text().strip())
    if len(flows) > 1:
        _fail("详情资金净流入重复")
    return name, quote_id, flows[0] if flows else None


def _source_time(value) -> tuple[str | None, str | None]:
    if value is None or value in ("", "-", "--"):
        return None, None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}(?::[0-9]{2})?", value):
        _fail("updateTime 日期时间无效")
    try:
        timestamp = datetime(
            int(value[:4]), int(value[5:7]), int(value[8:10]),
            int(value[11:13]), int(value[14:16]), int(value[17:19]) if len(value) == 19 else 0,
            tzinfo=_CHINA,
        )
    except ValueError as exc:
        raise SourceError(SOURCE, "updateTime 日期时间无效") from exc
    precision = "seconds" if len(value) == 19 else "minutes"
    return timestamp.date().isoformat(), timestamp.time().isoformat(timespec=precision)


def ths_concept_list(*, timeout: float) -> list[dict]:
    """读取概念目录，每行只返回详情页代码和名称。"""
    seconds = validate_timeout(timeout)
    return _parse_directory(_get(LIST_URL, seconds))


def ths_concept_quote_snapshot(code: str, *, timeout: float) -> dict:
    """读取单个概念点位及成交、资金和涨跌家数。"""
    _validate_code(code)
    seconds = validate_timeout(timeout)
    name, quote_id, flow = _parse_detail(_get(DETAIL_URL.format(code), seconds), code)
    items = _parse_jsonp(_get(QUOTE_URL.format(quote_id), seconds)).get("items")
    if not isinstance(items, dict):
        _fail("快照缺少 items 对象")
    if _identity(items.get("5"), "快照行情 code", _QUOTE_ID) != quote_id:
        _fail("快照行情 code 与详情不一致")
    if _name(items.get("name"), "快照 name") != name:
        _fail("快照概念 name 与详情不一致")
    observation_date, observation_time = _source_time(items.get("updateTime"))
    result = {"code": code, "name": name, "date": observation_date, "time": observation_time}
    for field, key in (("index_level", "10"), ("previous_close", "6"), ("open", "7"), ("high", "8"), ("low", "9"), ("level_change", "264648"), ("change_percent", "199112"), ("volume", "13"), ("amount", "19")):
        result[field] = to_number(items.get(key), field, source=SOURCE, integer=field == "volume", nonnegative=field not in {"level_change", "change_percent"})
    # 官方详情标记净流入为亿元；realhead 成交量为股、成交额为元。
    result["net_inflow"] = to_number(flow, "net_inflow", source=SOURCE, scale=8)
    for field, key in (("up_count", "38"), ("down_count", "39")):
        result[field] = to_number(items.get(key), field, source=SOURCE, integer=True, nonnegative=True)
    return result


def _parse_bars(payload: dict, name: str) -> list[dict]:
    if "name" in payload and _name(payload["name"], "日线 name") != name:
        _fail("日线概念 name 与详情不一致")
    data = payload.get("data")
    if not isinstance(data, str):
        _fail("日线 data 必须是 CSV 文本")
    rows = []
    seen = set()
    if not data.strip():
        return rows
    for line in data.split(";"):
        if not line.strip():
            continue
        columns = line.split(",")
        if len(columns) < 7 or not re.fullmatch(r"[0-9]{8}", columns[0]):
            _fail("日线行结构或日期无效")
        try:
            bar_date = parse_date(columns[0], "日线 date").isoformat()
        except ValueError as exc:
            raise SourceError(SOURCE, "日线 date 无效") from exc
        if bar_date in seen:
            _fail(f"同份日线响应日期 {bar_date} 重复")
        seen.add(bar_date)
        row = {"date": bar_date}
        for field, value in zip(("open", "high", "low", "close", "volume", "amount"), columns[1:7]):
            row[field] = to_number(value, field, source=SOURCE, integer=field == "volume", nonnegative=True)
        rows.append(row)
    return rows


def ths_concept_ohlcv(code: str, start_date: date | str, end_date: date | str, *, timeout: float) -> list[dict]:
    """按包含首尾的日期范围读取概念日线，不制造缺失交易日。"""
    _validate_code(code)
    start = parse_date_parameter(start_date, "start_date", allow_date_object=True)
    end = parse_date_parameter(end_date, "end_date", allow_date_object=True)
    if start > end:
        raise ValueError("start_date 不得晚于 end_date")
    seconds = validate_timeout(timeout)
    name, quote_id, _ = _parse_detail(_get(DETAIL_URL.format(code), seconds), code)
    rows_by_date = {}
    start_iso, end_iso = start.isoformat(), end.isoformat()
    for year in range(start.year, end.year + 1):
        payload = _parse_jsonp(_get(KLINE_URL.format(quote_id, year), seconds))
        for row in _parse_bars(payload, name):
            if not row["date"].startswith(f"{year:04d}-"):
                _fail("年度日线出现其他年份日期")
            if start_iso <= row["date"] <= end_iso:
                rows_by_date[row["date"]] = row
    # 时钟仅决定是否需要最新滚动文件，结果日期始终来自 CSV。
    current_year = datetime.now(_CHINA).year
    if start.year <= current_year <= end.year:
        payload = _parse_jsonp(_get(KLINE_URL.format(quote_id, "last"), seconds))
        for row in _parse_bars(payload, name):
            if start_iso <= row["date"] <= end_iso:
                rows_by_date[row["date"]] = row
    return [rows_by_date[key] for key in sorted(rows_by_date)]
