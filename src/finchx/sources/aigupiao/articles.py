"""爱股票公开题材频道文章及单篇正文。"""

from datetime import datetime
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json, get_text
from finchx._common.news import BEIJING_TZ, validate_limit

_SOURCE = "aigupiao"
_BASE = "https://www.aigupiao.com"
_HEADERS = {**DEFAULT_HEADERS, "Referer": _BASE + "/"}
_MAX_PAGES = 1000
_LIVE_KINDS = {"free", "charge", "vip"}


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None or isinstance(value, str) and not value.strip():
        if not required:
            return None
    elif isinstance(value, str):
        return value
    raise SourceError(_SOURCE, f"字段 {field} 必须是{'非空' if required else ''}字符串")


def _identity(value: Any, field: str) -> str:
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
        return value
    raise SourceError(_SOURCE, f"字段 {field} 必须是有效的来源文章身份")


def _array(raw: dict, field: str) -> list | None:
    value = raw.get(field)
    if value is None or isinstance(value, list):
        return value
    raise SourceError(_SOURCE, f"字段 {field} 必须是数组或空值")


def _published(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if type(value) is int or isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        try:
            return datetime.fromtimestamp(int(value), BEIJING_TZ).isoformat(timespec="seconds")
        except (OverflowError, ValueError, OSError) as exc:
            raise SourceError(_SOURCE, "rec_time 不是有效的来源时间") from exc
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}(?::[0-9]{2})?", value):
        try:
            moment = datetime(
                int(value[:4]), int(value[5:7]), int(value[8:10]),
                int(value[11:13]), int(value[14:16]), int(value[17:19]) if len(value) == 19 else 0,
                tzinfo=BEIJING_TZ,
            )
            return moment.isoformat(timespec="seconds" if len(value) == 19 else "minutes")
        except ValueError as exc:
            raise SourceError(_SOURCE, "rec_time 不是有效的来源时间") from exc
    raise SourceError(_SOURCE, "rec_time 必须是来源 Unix 秒整数、完整日期时间或空值")


def _media_url(value: Any, field: str) -> str:
    text = _text(value, field, required=True)
    try:
        parsed = urlsplit(text)
    except ValueError as exc:
        raise SourceError(_SOURCE, f"字段 {field} 媒体地址无效") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SourceError(_SOURCE, f"字段 {field} 媒体地址无效")
    return text


class _Body(HTMLParser):
    """仅抽取来源正文文字与原图片链接，不执行页面内容。"""

    _blocks = {"p", "div", "section", "article", "blockquote", "li", "ul", "ol",
               "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.images: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag in self._blocks or tag == "br":
            self.parts.append("\n")
        elif tag in {"td", "th"} and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\t")
        if tag == "img":
            values = dict(attrs)
            src = values.get("src") or values.get("data-src")
            if src is not None:
                self.images.append(_media_url(src, "正文 img"))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in self._blocks:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data.replace("\r\n", "\n").replace("\r", "\n"))

    def result(self) -> tuple[str | None, list[str]]:
        lines = [re.sub(r"[^\S\n\t]+", " ", line).strip() for line in "".join(self.parts).splitlines()]
        content = "\n".join(line for line in lines if line)
        return content or None, list(dict.fromkeys(self.images))


def _html(value: Any, field: str) -> tuple[str | None, list[str]]:
    text = _text(value, field)
    if text is None:
        return None, []
    parser = _Body()
    try:
        parser.feed(text)
        parser.close()
    except (ValueError, AssertionError) as exc:
        raise SourceError(_SOURCE, f"字段 {field} 正文结构无效") from exc
    return parser.result()


def _first_text(raw: dict, fields: tuple[str, ...]) -> str | None:
    values = [_text(raw.get(field), field) for field in fields]
    return next((value for value in values if value is not None), None)


def _content(raw: dict, fields: tuple[str, ...], *, image_field: str) -> tuple[str | None, list[str]]:
    if not any(field in raw for field in fields):
        raise SourceError(_SOURCE, "文章缺少必要正文结构")
    value = _first_text(raw, fields)
    content, images = _html(value, "正文")
    explicit = _array(raw, image_field)
    if explicit is not None:
        images.extend(_media_url(image, image_field) for image in explicit)
    return content, list(dict.fromkeys(images))


def _topics(raw: dict) -> list[str] | None:
    items = _array(raw, "topic")
    if items is None:
        return None
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise SourceError(_SOURCE, "topic 条目结构无效")
        result.append(_text(item.get("title"), "topic.title", required=True))
    return result


def _securities(raw: dict) -> list[dict] | None:
    items = _array(raw, "stock_info")
    if items is None:
        return None
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise SourceError(_SOURCE, "stock_info 条目结构无效")
        kind = item.get("kind")
        if kind == "stock":
            result.append({"symbol": _text(item.get("code"), "stock_info.code", required=True),
                           "name": _text(item.get("name"), "stock_info.name")})
        elif kind == "theme":
            _text(item.get("name"), "stock_info.name")
        elif "kind" not in item and "code" not in item and "l_id" in item:
            # 官网正文自动链接的发布账号与证券共用 stock_info；不是证券身份。
            account_id = item["l_id"]
            if type(account_id) is int and account_id > 0:
                pass
            else:
                _identity(account_id, "stock_info.l_id")
            _text(item.get("name"), "stock_info.name", required=True)
        else:
            raise SourceError(_SOURCE, "stock_info 出现未确认的关联类型")
    return result


def _audio_url(raw: dict) -> str | None:
    # voice 为来源正文的公开音频 JSON；时长口径未核，不输出或推算。
    voice = _text(raw.get("voice"), "voice")
    voice_url = None
    if voice is not None:
        try:
            value = json.loads(voice)
        except json.JSONDecodeError as exc:
            raise SourceError(_SOURCE, "voice 不是有效的公开音频 JSON") from exc
        if not isinstance(value, dict):
            raise SourceError(_SOURCE, "voice 必须是公开音频对象")
        voice_url = _media_url(value.get("url"), "voice.url")
    audio = _text(raw.get("audio"), "audio")
    audio_url = None if audio is None else _media_url(audio, "audio")
    return voice_url or audio_url


def _business(raw: dict, *, author: Any, title: Any, body_fields: tuple[str, ...], image_field: str) -> dict:
    content, images = _content(raw, body_fields, image_field=image_field)
    summary, _ = _html(_first_text(raw, ("brief_pc", "brief")), "摘要")
    return {"title": _text(title, "文章标题"), "published_at": _published(raw.get("rec_time")),
            "author": _text(author, "作者"), "summary": summary, "content": content,
            "image_urls": images, "audio_url": _audio_url(raw), "category": _text(raw.get("article_category_name"), "article_category_name"),
            "topics": _topics(raw), "related_securities": _securities(raw)}


def _list_page(payload: Any) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("rslt") != "succ" or payload.get("code") != "x0000":
        raise SourceError(_SOURCE, "文章频道来源状态表示请求失败")
    items = payload.get("data_list")
    if not isinstance(items, list):
        raise SourceError(_SOURCE, "文章频道 data_list 必须是数组")
    rows = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("msg"), dict) or not isinstance(item.get("live"), dict):
            raise SourceError(_SOURCE, "文章频道条目结构无效")
        raw = item["msg"]
        identity = _identity(raw.get("id"), "msg.id")
        kind = raw.get("kind")
        if kind == "user_msg":
            route = "dynamic"
        elif isinstance(kind, str) and kind in _LIVE_KINDS:
            route = "view"
        else:
            raise SourceError(_SOURCE, "文章频道出现未确认的文章类型")
        row = {"url": f"{_BASE}/{route}/detail/{identity}",
               **_business(raw, author=item["live"].get("title"), title=raw.get("title"),
                           body_fields=("content_pc", "content"), image_field="image")}
        rows.append(row)
    if len({row["url"] for row in rows}) != len(rows):
        raise SourceError(_SOURCE, "文章频道同页身份重复")
    return rows


def agp_topic_articles(limit: int = 20, sort: str = "newest", *, timeout: float) -> list[dict]:
    """按官网最新或热门顺序读取最多 limit 篇题材频道文章。"""
    target = validate_limit(limit)
    if not isinstance(sort, str) or sort not in {"newest", "hot"}:
        raise ValueError("sort 必须是 newest 或 hot")
    seconds = validate_timeout(timeout)
    collected = {}
    for page in range(1, _MAX_PAGES + 1):
        url = _BASE + "/Api/News/articleList?" + urlencode({"number": 10, "division": 1, "page": page,
                                                         "article_type": 1, "article_order_by": sort})
        rows = _list_page(get_json(url, timeout=seconds, headers=_HEADERS, source=_SOURCE))
        if not rows:
            return list(collected.values())[:target]
        if not any(row["url"] not in collected for row in rows):
            raise SourceError(_SOURCE, "文章频道分页停滞，没有新的文章身份")
        for row in rows:
            collected[row["url"]] = row
        if len(collected) >= target:
            return list(collected.values())[:target]
    raise SourceError(_SOURCE, "文章频道分页达到防护上限，不能确认请求范围已完成")


def _url(url: Any) -> tuple[str, str, str]:
    message = "url 必须是爱股票官方 dynamic/detail/<id> 或 view/detail/<id> 文章地址"
    if not isinstance(url, str) or re.search(r"[\s\\\x00-\x1f\x7f]", url):
        raise ValueError(message)
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or parsed.netloc != "www.aigupiao.com"
                or parsed.fragment):
            raise ValueError(message)
        match = re.fullmatch(r"/(dynamic|view)/detail/([1-9][0-9]*)", parsed.path)
        if match and not parsed.query:
            route, identity = match.groups()
        elif parsed.path == "/Dynamic/user_dynamic_detail":
            pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
            if len(pairs) != 1 or pairs[0][0] != "o_id" or not re.fullmatch(r"[1-9][0-9]*", pairs[0][1]):
                raise ValueError(message)
            route, identity = "dynamic", pairs[0][1]
        else:
            raise ValueError(message)
    except ValueError as exc:
        raise ValueError(message) from exc
    return route, identity, f"{_BASE}/{route}/detail/{identity}"


class _Scripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[str] = []
        self.current: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.current = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current.append(data)


def _embedded(scripts: list[str], name: str) -> dict:
    found = []
    for script in scripts:
        for match in re.finditer(r"(?m)^\s*var\s+" + re.escape(name) + r"\s*=\s*", script):
            try:
                value, end = json.JSONDecoder().raw_decode(script, match.end())
            except json.JSONDecodeError as exc:
                raise SourceError(_SOURCE, f"网页 {name} 不是有效的公开 JSON") from exc
            if not isinstance(value, dict) or script[end:].lstrip()[:1] not in {";", ","}:
                raise SourceError(_SOURCE, f"网页 {name} 结构无效")
            found.append(value)
    if len(found) != 1:
        raise SourceError(_SOURCE, f"网页缺少唯一有效的 {name}")
    return found[0]


def agp_get(url: str, *, timeout: float) -> dict:
    """读取同次公开页面及其必要详情响应，不回填目录或登录数据。"""
    route, identity, canonical = _url(url)
    seconds = validate_timeout(timeout)
    page = get_text(canonical, timeout=seconds, headers=_HEADERS, source=_SOURCE)
    parser = _Scripts()
    parser.feed(page)
    parser.close()
    raw = _embedded(parser.scripts, "rslt_content")
    if _identity(raw.get("id"), "id") != identity:
        raise SourceError(_SOURCE, "文章网页身份与请求不一致")
    if route == "dynamic":
        if not isinstance(raw.get("kind"), str) or raw["kind"] not in {"user_msg", "express"}:
            raise SourceError(_SOURCE, "动态文章类型与请求不一致")
        result = _business(raw, author=raw.get("nickname"), title=raw.get("title"),
                           body_fields=("content_edit", "content"), image_field="image")
        for field in ("image_1", "image_2", "image_3"):
            image = _text(raw.get(field), field)
            if image is not None:
                result["image_urls"].append(_media_url(image, field))
        result["image_urls"] = list(dict.fromkeys(result["image_urls"]))
    else:
        if not isinstance(raw.get("kind"), str) or raw["kind"] not in _LIVE_KINDS:
            raise SourceError(_SOURCE, "直播文章类型与请求不一致")
        live_id = _identity(raw.get("l_id"), "l_id")
        md = _text(_embedded(parser.scripts, "_Libs").get("md"), "公开页面 md", required=True)
        endpoint = _BASE + "/api/live.php?" + urlencode({"act": "load_detail", "id": live_id,
                                                        "oid": identity, "source": "pc", "md": md})
        payload = get_json(endpoint, timeout=seconds, headers=_HEADERS, source=_SOURCE)
        if not isinstance(payload, dict) or payload.get("rslt") != "succ":
            raise SourceError(_SOURCE, "文章详情来源状态表示请求失败")
        items = payload.get("show_detail")
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            raise SourceError(_SOURCE, "文章详情 show_detail 必须是唯一文章对象")
        raw = items[0]
        if _identity(raw.get("id"), "id") != identity or _identity(raw.get("live_id"), "live_id") != live_id:
            raise SourceError(_SOURCE, "文章详情身份与请求不一致")
        if not isinstance(raw.get("kind"), str) or raw["kind"] not in _LIVE_KINDS:
            raise SourceError(_SOURCE, "文章详情类型无效")
        result = _business(raw, author=raw.get("title"), title=raw.get("biaoti"),
                           body_fields=("content_edit", "content"), image_field="image_url")
    result["ai_summary"], _ = _html(raw.get("ai_summary"), "ai_summary")
    result["disclaimer"], _ = _html(raw.get("disclaimer"), "disclaimer")
    return result
