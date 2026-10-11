"""同花顺社区 Tcode 话题中的新闻、文章与观点目录。"""

from datetime import datetime
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx._common.news import BEIJING_TZ, validate_limit
from finchx.sources.tonghuashun._article_url import classify_article_url

_SOURCE = "tonghuashun"
_API = "https://t.10jqka.com.cn/lgt/topic/open/api/topic_info/v3/recommend_list"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://t.10jqka.com.cn/"}
_PAGE_SIZE = 15
_MAX_PAGES = 1000


def _topic_code(url: str) -> str:
    if not isinstance(url, str) or not url or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("topic_url 必须是合法的同花顺社区话题 URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("topic_url 无效") from exc
    query = parse_qs(parsed.query, keep_blank_values=True)
    code = query.get("code", [])
    if (parsed.scheme not in {"http", "https"}
            or parsed.hostname != "t.10jqka.com.cn"
            or parsed.username is not None or parsed.password is not None
            or port not in (None, 443 if parsed.scheme == "https" else 80)
            or parsed.path not in {"/lgt/main/frontend-main-service/topic/index.html", "/m/topic/index.html"}
            or len(code) != 1
            or not re.fullmatch(r"T[A-Za-z0-9]{6}", code[0])):
        raise ValueError("topic_url 仅支持含 Tcode 的同花顺社区话题链接")
    return code[0]


def _fail(message: str) -> None:
    raise SourceError(_SOURCE, message)


def _text(value, field: str) -> str | None:
    if value is None or isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, str):
        return value
    _fail(f"{field} 必须是字符串或空值")


def _block(raw: dict, field: str) -> dict:
    value = raw.get(field)
    if value is None:
        return {}
    if not isinstance(value, dict):
        _fail(f"{field} 结构损坏")
    return value


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _plain(value, field: str) -> str | None:
    text = _text(value, field)
    if text is None:
        return None
    parser = _PlainText()
    parser.feed(text)
    return "\n".join(line.strip() for line in "".join(parser.parts).replace("\r", "\n").splitlines() if line.strip()) or None


def _published(value) -> str | None:
    if value is None or value == "":
        return None
    if type(value) is not int and not (isinstance(value, str) and re.fullmatch(r"[0-9]+", value)):
        _fail("info.time 必须是来源毫秒整数或空值")
    try:
        milliseconds = int(value)
        if milliseconds < 0:
            _fail("info.time 不能为负")
        moment = datetime.fromtimestamp(milliseconds // 1000, BEIJING_TZ)
        moment = moment.replace(microsecond=milliseconds % 1000 * 1000)
        return moment.isoformat(timespec="milliseconds" if moment.microsecond else "seconds")
    except (OverflowError, ValueError, OSError) as exc:
        raise SourceError(_SOURCE, "info.time 不是有效的来源时间") from exc


def _row(raw: dict) -> tuple[tuple[int, str], dict | None]:
    if not isinstance(raw, dict) or not isinstance(raw.get("info"), dict):
        _fail("目录行缺少必要 info 结构")
    info = raw["info"]
    kind, identity = info.get("type"), info.get("id")
    if type(kind) is not int:
        _fail("目录业务类型必须是来源整数")
    if kind not in {1, 2, 3, 8}:
        _fail(f"目录出现未经核实的业务类型（type={kind}）")
    if not isinstance(identity, str) or not re.fullmatch(r"[1-9][0-9]{5,19}", identity):
        _fail("目录来源身份无效")
    if "unique" in info and info["unique"] != f"{identity}_{kind}":
        _fail("目录 unique 与业务身份冲突")
    if kind == 1:
        if info.get("subject") != "state" or info.get("like_key") != f"group_post_{identity}":
            _fail("目录讨论类型与明确业务身份冲突")
        return (kind, identity), None
    expected_subject = {8: "news", 2: "snslivepost", 3: "snsview"}[kind]
    expected_like = f"seq_{identity}" if kind == 8 else f"sns_post_{identity}"
    if info.get("subject") != expected_subject or info.get("like_key") != expected_like:
        _fail("目录业务类型与明确文章身份冲突")
    if kind == 8:
        try:
            url = info.get("jump_url")
            url_kind, _, url_id, _ = classify_article_url(url)
        except ValueError as exc:
            raise SourceError(_SOURCE, "目录新闻链接无效") from exc
        if url_kind != "news" or url_id != identity:
            _fail("目录新闻链接与来源身份冲突")
        news = _block(raw, "news")
        source = _text(news.get("source"), "news.source")
        if source is not None:
            source = re.sub(r"^\s*来源\s*", "", source).strip() or None
        summary = _plain(news.get("content"), "news.content")
    else:
        # mp contentId 是不透明身份，不能当作数字 pid；同份明确 sns_post 身份给出公开 pid。
        url = (f"https://t.10jqka.com.cn/lgt/short_view/index.html?pid={identity}" if kind == 3
               else f"https://t.10jqka.com.cn/pid_{identity}.shtml")
        source = None
        summary = _plain(_block(raw, "abstract").get("content"), "abstract.content")
    title = _block(raw, "title").get("content")
    author = _block(raw, "author").get("name")
    # 两种社区文章的真实业务身份均为 sns_post_ID，原 unique 仍按原 type 核验。
    return (8 if kind == 8 else 2, identity), {
        "url": url,
        "content_type": "news" if kind == 8 else "article",
        "title": _text(title, "title.content"),
        "published_at": _published(info.get("time")),
        "source_name": source,
        "author": _text(author, "author.name"),
        "summary": summary,
    }


def ths_list(topic_url: str, limit: int = 20, *, timeout: float) -> list[dict]:
    """依来源顺序读取一个 Tcode 话题的新闻、文章与观点目录。"""
    code = _topic_code(topic_url)
    maximum = validate_limit(limit)
    seconds = validate_timeout(timeout)
    rows: dict[tuple[int, str], dict] = {}
    consumed: set[tuple[int, str]] = set()
    query_type, page, stalled = "recommend", 1, 0
    for _ in range(_MAX_PAGES):
        url = _API + "?" + urlencode({"code": code, "page": page, "pageSize": _PAGE_SIZE, "queryType": query_type})
        payload = get_json(url, timeout=seconds, headers=_HEADERS, source=_SOURCE)
        if not isinstance(payload, dict) or type(payload.get("status_code")) is not int or payload["status_code"] != 0:
            _fail("目录来源状态失败")
        data = payload.get("data")
        if not isinstance(data, dict) or type(data.get("has_next")) is not bool:
            _fail("目录分页结构损坏")
        key = "list_recommend" if query_type == "recommend" else "list_feed"
        source_rows = data.get(key)
        if key not in data and data["has_next"] is False:
            source_rows = []
        if not isinstance(source_rows, list):
            _fail("目录缺少完整来源数组")
        parsed = [_row(row) for row in source_rows]
        identities = [identity for identity, _ in parsed]
        if len(set(identities)) != len(identities):
            _fail("同页目录业务身份重复")
        fresh = set(identities) - consumed
        consumed.update(identities)
        for identity, row in parsed:
            if row is not None:
                rows[identity] = row
        if len(rows) >= maximum:
            return list(rows.values())[:maximum]
        if not data["has_next"]:
            if query_type == "feed":
                return list(rows.values())
            query_type, page, stalled = "feed", 1, 0
        else:
            stalled = 0 if fresh else stalled + 1
            if stalled >= 3:
                _fail("目录分页持续无进展")
            page += 1
    _fail("目录达到读取防护预算，尚未确认完成")
