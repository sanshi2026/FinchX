"""同花顺公开新闻、社区文章、视频与专题；不保存会话或结果。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from http.client import HTTPException
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS
from finchx._common.news import BEIJING_TZ
from finchx.sources.tonghuashun._article_url import classify_article_url, encode_news_seq

_SOURCE = "同花顺文章"
_ZONE = BEIJING_TZ
_MAX_BYTES = 4_000_000
_NEWS_API = "https://news.10jqka.com.cn/mobile_api/news/article/page/v2/WEB/"
_SHARE_API = "https://t.10jqka.com.cn/m/post/getPostShareData/?pid="
_SHORT_API = "https://t.10jqka.com.cn/m/shortview/getShortViewDetail?pid="
_VOID = {"br", "hr", "img", "meta", "link", "input", "source", "area", "base", "wbr"}
_BLOCKED = {"script", "style", "noscript", "iframe", "object", "embed", "form", "button", "input", "svg"}
_EXCLUDE = {"comment", "comments", "comment-list", "reply", "reply-list", "related", "recommend", "recommend-list", "ad", "advertisement", "toolbar", "share-box", "disclaimer", "statement", "risk-tip", "risk-tips", "post-detail-qshint"}
_PARAGRAPHS = {"p", "div", "li", "tr", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}


def _fail(reason: str):
    raise SourceError(_SOURCE, reason)


def _object(value, field_name: str) -> dict:
    if not isinstance(value, dict):
        _fail(f"{field_name} 结构无效")
    return value


def _text(value, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(f"{field_name} 文本类型无效")
    return _clean(value) or None


def _clean(value: str) -> str:
    value = unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    lines = [re.sub(r"[\t\r\f\v ]+", " ", line).strip() for line in value.splitlines()]
    return "\n\n".join(line for line in lines if line).strip()


def _url(value, field_name: str, base: str | None = None) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        _fail(f"{field_name} URL 无效")
    if value.startswith("//"):
        value = "https:" + value
    if base is not None:
        value = urljoin(base, value)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        _fail(f"{field_name} URL 无效")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None or (port is not None and not 1 <= port <= 65535):
        _fail(f"{field_name} URL 无效")
    return value


def _timestamp(value, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
            _fail(f"{field_name} 时间戳无效")
        return datetime.fromtimestamp(value, timezone.utc).astimezone(_ZONE).isoformat(timespec="seconds")
    except (ValueError, OSError, OverflowError):
        _fail(f"{field_name} 时间戳无效")


def _source_time(value) -> tuple[str | None, str | None]:
    text = _text(value, "来源时间")
    if text is None:
        return None, None
    full = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})[ T]([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?(Z|[+-][0-9]{2}:[0-9]{2})?", text)
    if full:
        try:
            datetime(*(int(full[i]) for i in range(1, 6)), int(full[6] or 0))
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            parsed = parsed.replace(tzinfo=_ZONE) if parsed.tzinfo is None else parsed.astimezone(_ZONE)
        except ValueError:
            _fail("来源完整发表时间无效")
        return parsed.isoformat(timespec="seconds" if full[6] is not None else "minutes"), None
    if re.match(r"[0-9]{4}[-/]", text):
        _fail("来源完整发表时间格式无效")
    # Relative or yearless source text stays literal; it cannot become a date.
    if re.fullmatch(r"[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}(?::[0-9]{2})?", text):
        try:
            datetime.strptime("2000-" + text, "%Y-%m-%d %H:%M:%S" if len(text) == 14 else "%Y-%m-%d %H:%M")
        except ValueError:
            _fail("来源缺年时间无效")
    relative_clock = re.fullmatch(r"(?:今天|昨天|前天) ([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?", text)
    if relative_clock and (int(relative_clock[1]) > 23 or int(relative_clock[2]) > 59 or relative_clock[3] is not None and int(relative_clock[3]) > 59):
        _fail("来源相对日期的时刻无效")
    return None, text


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list = field(default_factory=list)


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag.lower(), {k.lower():v or "" for k,v in attrs})
        self.stack[-1].children.append(node)
        if node.tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag.lower():
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _tree(markup: str) -> _Node:
    parser = _Tree()
    parser.feed(markup)
    parser.close()
    return parser.root


def _nodes(root):
    for child in root.children:
        if isinstance(child, _Node):
            yield child
            yield from _nodes(child)


def _classes(node):
    return set(node.attrs.get("class", "").lower().split())


def _body(root: _Node, base: str, *, exclude: bool = True) -> tuple[str | None, list[str], list[str]]:
    pieces, images, videos = [], [], []

    def visit(node):
        classes = _classes(node)
        if node.tag in _BLOCKED or (exclude and (classes & _EXCLUDE or any(c.startswith(("comment-", "reply-", "recommend-", "advert-")) for c in classes))):
            return
        if node.tag == "img":
            value = node.attrs.get("src") or node.attrs.get("data-src")
            if value:
                image = _url(value, "正文图片", base)
                if image not in images:
                    images.append(image)
        if node.tag in {"video", "source"}:
            value = node.attrs.get("src")
            if value:
                video = _url(value, "正文视频", base)
                if video not in videos:
                    videos.append(video)
        if node.tag == "br":
            pieces.append("\n")
        for child in node.children:
            if isinstance(child, str):
                pieces.append(child)
            else:
                visit(child)
        if node.tag in _PARAGRAPHS:
            pieces.append("\n")
        elif node.tag in {"td", "th"}:
            pieces.append(" | ")
    visit(root)
    content = _clean("".join(pieces)) or None
    if content and re.match(r"^(请登录|登录后查看|访问受限|无权访问|access denied|forbidden)", content, re.I):
        _fail("来源正文访问受限")
    return content, images, videos


def _markup(value, base: str):
    if value is None:
        return None, [], []
    if not isinstance(value, str):
        _fail("正文 HTML 类型无效")
    if re.search(r"&lt;\s*/?\s*(?:p|div|img|br|span|table)\b", value, re.I):
        value = unescape(value)
    return _body(_tree(value), base)


def _result(content_type: str, **values):
    result = dict.fromkeys(("content_type", "title", "published_at", "source_time", "source_name", "author", "original_url", "content", "image_urls", "video_urls", "cover_url", "disclaimer", "related_entities"))
    result.update(content_type=content_type, **values)
    for name in ("image_urls", "video_urls"):
        if result[name] is None:
            result[name] = []
    if not (result["content"] or result["image_urls"] or result["video_urls"]):
        _fail("来源没有可读正文或有效图片、视频")
    return result


def _entities(value):
    if value is None:
        return None
    if not isinstance(value, list):
        _fail("关联对象数组无效")
    result = []
    for row in value:
        row = _object(row, "关联对象")
        code = _text(row.get("stockCode"), "关联对象代码")
        name = _text(row.get("stockName"), "关联对象名称")
        market = row.get("marketId")
        if isinstance(market, int) and not isinstance(market, bool):
            market = str(market)
        market = _text(market, "关联对象市场")
        if code is None or market is None:
            _fail("关联对象缺少必要来源身份")
        result.append({"code":code, "name":name, "market":market})
    return result


class _ReadError(SourceError):
    def __init__(self, reason, *, fallback=False):
        super().__init__(_SOURCE, reason)
        self.fallback = fallback


def _transport_target(original: str, target: str):
    # API transports retain their exact route; public pages retain their identity.
    if original.startswith((_NEWS_API, _SHARE_API, _SHORT_API)):
        if target != original:
            _fail("详情 API 跳转改变来源身份或地址")
        return
    try:
        first = classify_article_url(original)
        last = classify_article_url(target)
    except ValueError:
        _fail("文章跳转到未核来源地址")
    if (first[0] != last[0] or first[2] != last[2] or urlsplit(original).hostname != urlsplit(target).hostname or first[3] is not None and first[3] != last[3] or urlsplit(target).scheme != "https"):
        _fail("文章跳转改变来源身份")


class _Redirect(HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        _transport_target(req.full_url, target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def _read(url: str, *, timeout: float) -> str:
    headers = {**DEFAULT_HEADERS, "Accept":"application/json,text/html,*/*", "Referer":"https://news.10jqka.com.cn/"}
    request = Request(url, headers=headers, method="GET")
    try:
        with build_opener(_Redirect()).open(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise _ReadError(f"HTTP 状态 {response.status}", fallback=response.status == 404 or response.status >= 500)
            _transport_target(url, response.geturl())
            raw = response.read(_MAX_BYTES + 1)
            if len(raw) > _MAX_BYTES:
                _fail("详情响应超过读取上限")
            encoding = response.headers.get_content_charset()
    except HTTPError as exc:
        exc.close()
        raise _ReadError(f"HTTP 状态 {exc.code}", fallback=exc.code == 404 or exc.code >= 500) from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise _ReadError(f"网络请求失败（{type(exc).__name__}）", fallback=True) from exc
    try:
        return raw.decode(encoding or "utf-8-sig")
    except (UnicodeDecodeError, LookupError) as exc:
        raise SourceError(_SOURCE, "来源文本编码无效") from exc


def _json(url, timeout):
    try:
        payload = json.loads(_read(url, timeout=timeout))
    except json.JSONDecodeError as exc:
        raise SourceError(_SOURCE, "详情响应不是有效 JSON") from exc
    return _object(payload, "详情响应")


def _news_detail(detail, seq: str, base: str):
    detail = _object(detail, "新闻详情")
    article = _object(detail.get("article"), "article")
    if article.get("seq") != seq:
        _fail("新闻正文身份与输入链接不一致")
    if "encodedSeq" in article and article["encodedSeq"] is not None and article["encodedSeq"] != encode_news_seq(seq):
        _fail("新闻 encoded 身份冲突")
    info = detail.get("statusInfo")
    if info is not None:
        outcome = _object(info, "statusInfo").get("outcome")
        if type(outcome) is not int or outcome != 0:
            _fail("新闻来源状态失败")
    media = article.get("media")
    if media is not None:
        media = _object(media, "article.media")
    settings = detail.get("pageSettings")
    if settings is not None:
        settings = _object(settings, "pageSettings")
    modules = detail.get("relatedModules")
    if modules is not None:
        modules = _object(modules, "relatedModules")
    content, images, videos = _markup(article.get("content"), base)
    return _result("news", title=_text(article.get("title"), "标题"), published_at=_timestamp(article.get("ctime"), "ctime"), source_name=_text(media.get("name") if media is not None else None, "媒体名称"), author=_text(article.get("author"), "作者"), original_url=_url(article.get("sourceUrl"), "原文链接"), content=content, image_urls=images, video_urls=videos, disclaimer=_text(settings.get("disclaimer") if settings is not None else None, "免责声明"), related_entities=_entities(modules.get("associatedStocks") if modules is not None else None))


def _news_payload(payload, seq, base):
    status = payload.get("status_code")
    if type(status) is not int or status != 0:
        _fail("新闻接口状态无效或请求失败")
    detail = _object(payload.get("data"), "data")
    if "detailData" in detail:
        detail = _object(detail["detailData"], "detailData")
    return _news_detail(detail, seq, base)


def _community_payload(payload, seq, base):
    if type(payload.get("errorCode")) is not int or payload["errorCode"] != 0:
        _fail("社区公开分享来源状态失败或访问受限")
    data = _object(_object(payload.get("result"), "result").get("data"), "result.data")
    post = _object(data.get("post"), "post")
    if post.get("hotKey") != "sns_post_" + seq:
        _fail("社区正文身份与输入链接不一致")
    content, images, videos = _markup(post.get("content"), base)
    flag = post.get("hasVideo")
    if flag is not None and (type(flag) is not int or flag not in (0, 1)):
        _fail("hasVideo 状态无效")
    video = _url(post.get("video"), "视频")
    if flag == 1 and video is None:
        _fail("视频标记缺少有效视频地址")
    if flag == 0 and video is not None:
        _fail("视频标记与地址冲突")
    if video is not None:
        videos = list(dict.fromkeys([*(videos or []), video]))
    if videos is None and flag is not None:
        videos = []
    published, literal = _source_time(post.get("time"))
    video_cover = _url(post.get("videoCover"), "视频封面")
    share_cover = _url(post.get("shareCover"), "分享封面")
    return _result("video" if video and content is None and not images else "article", title=_text(post.get("title"), "标题"), published_at=published, source_time=literal, author=_text(post.get("groupName"), "发布账号"), content=content, image_urls=images, video_urls=videos, cover_url=video_cover if video_cover is not None else share_cover)


def _short_identity(value, seq, field_name):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or value != seq:
        _fail(f"短文 {field_name} 与输入身份冲突")


def _short_entities(markup, base):
    if markup is None:
        return None
    if re.search(r"&lt;\s*/?\s*(?:p|div|img|br|span|a)\b", markup, re.I):
        markup = unescape(markup)
    result, seen = [], set()
    def visit(node):
        classes = _classes(node)
        if node.tag in _BLOCKED or classes & _EXCLUDE:
            return
        attrs = node.attrs
        is_entity = attrs.get("data-hx-tag") == "stock"
        has_identity = "data-code" in attrs or "data-marketid" in attrs
        # _dollar_ 仅为展示样式；普通链接文字不需要证券身份或跳转地址。
        if is_entity or has_identity:
            code = _text(attrs.get("data-code"), "短文关联代码")
            market = _text(attrs.get("data-marketid"), "短文关联市场")
            name = _text(attrs.get("data-name"), "短文关联名称")
            if code is None or market is None:
                _fail("短文结构化关联缺少必要来源身份")
            identity = (code, market)
            if identity not in seen:
                seen.add(identity)
                result.append({"code":code, "name":name, "market":market})
        for child in node.children:
            if isinstance(child, _Node):
                visit(child)
    visit(_tree(markup))
    return result if result else None


def _short_payload(payload, seq, base):
    if type(payload.get("errorCode")) is not int or payload["errorCode"] != 0:
        _fail("短文公开来源状态失败或访问受限")
    result = _object(payload.get("result"), "短文 result")
    tag = _object(result.get("tagObj"), "短文 tagObj")
    if type(tag.get("type")) is not int or tag["type"] != 3:
        _fail("短文来源类型与输入不一致")
    _short_identity(tag.get("id"), seq, "tagObj.id")
    pack = _object(result.get("dataPack"), "短文 dataPack")
    info = _object(pack.get("contentInfo"), "短文 contentInfo")
    _short_identity(info.get("pid"), seq, "contentInfo.pid")
    data = _object(result.get("contentData"), "短文 contentData")
    if info.get("hotKey") != "sns_post_" + seq or data.get("hotKey") != "sns_post_" + seq:
        _fail("短文必要 hotKey 身份冲突")
    modules = result.get("modules")
    if not isinstance(modules, list):
        _fail("短文 modules 必要结构无效")
    selected = {"creative":[], "disclaimer":[]}
    for module in modules:
        module = _object(module, "短文 module")
        name = module.get("name")
        if isinstance(name, str) and name in selected:
            selected[name].append(_object(module.get("data"), f"短文 {name}.data"))
    if len(selected["creative"]) != 1 or len(selected["disclaimer"]) > 1:
        _fail("短文必要业务模块缺失或重复")
    creator = selected["creative"][0]
    if creator.get("hotKey") != "sns_post_" + seq:
        _fail("短文创作者模块身份冲突")
    disclaimer = selected["disclaimer"][0].get("disclaimer") if selected["disclaimer"] else None
    content, images, videos = _markup(data.get("content"), base)
    additional_images = data.get("imgs")
    if additional_images is not None:
        if not isinstance(additional_images, list):
            _fail("短文图片数组无效")
        for image in additional_images:
            image = _url(image, "短文图片")
            if image is None:
                _fail("短文图片数组包含空地址")
            if image not in images:
                images.append(image)
    flag = data.get("isHasVideo")
    if flag is not None and (type(flag) is not int or flag not in (0, 1)):
        _fail("短文视频标记无效")
    video = _url(data.get("videoSrc"), "短文视频")
    if flag == 1 and video is None or flag == 0 and video is not None:
        _fail("短文视频标记与地址冲突")
    if video is not None and video not in videos:
        videos.append(video)
    published = _timestamp(data.get("postTimestamp"), "短文 postTimestamp")
    full_time, literal = _source_time(data.get("time"))
    if published is None:
        published = full_time
    else:
        literal = None
    related_modules = result.get("relatedModules")
    if related_modules is not None:
        related_modules = _object(related_modules, "短文 relatedModules")
    related = _entities(related_modules["associatedStocks"]) if related_modules is not None and "associatedStocks" in related_modules else _short_entities(data.get("content"), base)
    return _result("article", title=_text(info.get("title"), "短文标题"), published_at=published, source_time=literal, author=_text(creator.get("name"), "短文作者"), content=content, image_urls=images, video_urls=videos, cover_url=_url(data.get("videoCover"), "短文视频封面"), disclaimer=_text(disclaimer, "短文免责声明"), related_entities=related)


def _meta(root, *keys):
    for node in _nodes(root):
        if node.tag == "meta" and (node.attrs.get("property") or node.attrs.get("name") or node.attrs.get("itemprop")) in keys:
            return _text(node.attrs.get("content"), "页面元信息")
    return None


def _class_text(root, classes):
    for node in _nodes(root):
        if _classes(node) & classes:
            return _body(node, "https://news.10jqka.com.cn/", exclude=False)[0]
    return None


def _title(root):
    value = _meta(root, "og:title", "twitter:title")
    if value is not None:
        return value
    for tag in ("h1", "title"):
        for node in _nodes(root):
            if node.tag == tag:
                text = _body(node, "https://news.10jqka.com.cn/", exclude=False)[0]
                return re.sub(r"\s*[-_|｜]\s*(同花顺|10jqka).*$", "", text, flags=re.I) if text is not None else None
    return None


def _script_values(markup: str) -> dict[str, list]:
    """读取已核字面 JSON 声明；字符串、注释和解码后的 JSON 内容均跳过。"""
    result = {"activity": [], "activityId": [], "__PAGE_DATA__": []}
    decoder = json.JSONDecoder()
    declaration = re.compile(r"(?:(?:var|let|const)\s+(activityId|activity)|(?:window\.)?(__PAGE_DATA__))\s*=\s*")
    for node in _nodes(_tree(markup)):
        if node.tag != "script":
            continue
        script = "".join(child for child in node.children if isinstance(child, str))
        i = 0
        while i < len(script):
            if script.startswith("//", i):
                end = script.find("\n", i+2)
                i = len(script) if end < 0 else end+1
                continue
            if script.startswith("/*", i):
                end = script.find("*/", i+2)
                i = len(script) if end < 0 else end+2
                continue
            if script[i] in "\"'`":
                quote = script[i]
                i += 1
                while i < len(script):
                    if script[i] == "\\":
                        i += 2
                    elif script[i] == quote:
                        i += 1
                        break
                    else:
                        i += 1
                continue
            match = declaration.match(script, i) if i == 0 or not (script[i-1].isalnum() or script[i-1] in "_$") else None
            if match is None:
                i += 1
                continue
            name = match[1] or match[2]
            start = match.end()
            while start < len(script) and script[start].isspace():
                start += 1
            try:
                value, end = decoder.raw_decode(script, start)
            except json.JSONDecodeError as exc:
                raise SourceError(_SOURCE, "页面必要 JSON 声明损坏") from exc
            result[name].append(value)
            # The whole JSON literal is consumed once, including prose that looks like JS.
            i = end
    return result


def _json_after(markup, name):
    values = _script_values(markup)[name]
    if not values:
        return None
    if len(values) != 1:
        _fail("页面存在重复必要 JSON 声明")
    return _object(values[0], "页面 JSON")


def _page_identity(root, seq: str, url: str):
    for node in _nodes(root):
        if node.tag == "link" and node.attrs.get("rel") == "canonical" or node.tag == "meta" and node.attrs.get("property") == "og:url":
            value = node.attrs.get("href") if node.tag == "link" else node.attrs.get("content")
            if value:
                _transport_target(url, _url(value, "页面文章身份", url))
        pid = node.attrs.get("data-pid") if node.tag == "body" or "globle-param" in _classes(node) else None
        if pid is not None and pid != seq:
            _fail("页面社区身份冲突")


def _html_article(markup, seq, url, *, community=False):
    root = _tree(markup)
    _page_identity(root, seq, url)
    state = _json_after(markup, "__PAGE_DATA__") if not community else None
    if state is not None:
        if "__NEWS_DETAIL_DATA__" in state:
            state = _object(state["__NEWS_DETAIL_DATA__"], "__NEWS_DETAIL_DATA__")
        if "detailData" in state:
            state = _object(state["detailData"], "detailData")
        return _news_detail(state, seq, url)
    choices = ({"post-text-main", "content-main"} if community else {"news-content", "news-content-parsed", "article-content"})
    candidates = [n for n in _nodes(root) if _classes(n) & choices]
    if not candidates and not community:
        _fail("页面未提供已核正文结构")
    # Nested aliases describe one body; use its outermost explicit body once.
    body = candidates[0] if candidates else _Node("article")
    if candidates and any(candidate is not body and candidate not in list(_nodes(body)) for candidate in candidates):
        _fail("页面存在互不相属的多个正文结构")
    content, images, videos = _body(body, url)
    if community and not (content or images or videos):
        video_nodes = [n for n in _nodes(root) if "pc-video" in _classes(n)]
        for node in video_nodes:
            value = _url(node.attrs.get("data-videohref"), "页面视频", url)
            if value is not None:
                videos.append(value)
    raw_time = _meta(root, "article:published_time", "publishdate", "publish_date", "datepublished")
    if raw_time is None and community:
        day = _class_text(root, {"detail-date"})
        clock = _class_text(root, {"detail-time"})
        raw_time = " ".join(x for x in (day, clock) if x is not None) or _class_text(root, {"ctime"})
    if raw_time is None:
        raw_time = _class_text(root, {"publish-time", "pub-time", "article-time"})
    published, literal = _source_time(raw_time)
    return _result("video" if community and videos and content is None and not images else "article" if community else "news", title=_title(root), published_at=published, source_time=literal, source_name=_class_text(root, {"media-name", "source-name", "article-source"}), author=_meta(root, "author") or _class_text(root, {"post-author", "article-author", "news-author", "circle-name"}), content=content, image_urls=images, video_urls=videos, cover_url=_url(_meta(root, "og:image"), "页面封面", url), disclaimer=_class_text(root, {"disclaimer", "statement", "risk-tip", "risk-tips", "post-detail-qshint"}))


def _deep(markup, url):
    root = _tree(markup)
    mains = [n for n in _nodes(root) if n.tag == "main"]
    if len(mains) != 1:
        _fail("专题缺少唯一主体")
    main = mains[0]
    heroes = [n for n in main.children if isinstance(n, _Node) and "hero" in _classes(n)]
    sections = [n for n in main.children if isinstance(n, _Node) and n.tag == "section" and re.fullmatch(r"sec(?:[0-9]+|-[a-z]+)", n.attrs.get("id", ""))]
    if len(heroes) != 1 or not sections:
        _fail("专题必要公开正文结构损坏")
    content, images, videos = _body(_Node("article", children=[heroes[0], *sections]), url)
    footers = [n for n in main.children if isinstance(n, _Node) and n.tag == "footer"]
    footer = _body(footers[0], url, exclude=False)[0] if len(footers) == 1 else None
    attribution, marker, disclaimer = footer.partition("免责声明") if footer is not None else ("", "", "")
    if attribution.strip():
        content = "\n\n".join(x for x in (content, attribution.strip()) if x)
    related = []
    for node in _nodes(_Node("article", children=[heroes[0], *sections])):
        if "stock-link" in _classes(node):
            code = _text(node.attrs.get("data-code"), "专题关联代码")
            name = _text(node.attrs.get("data-name"), "专题关联名称")
            market = _text(node.attrs.get("data-market"), "专题关联市场")
            if code is None or name is None:
                _fail("专题关联身份损坏")
            row = {"code":code, "name":name, "market":market}
            if row not in related:
                related.append(row)
    return _result("topic", title=_title(heroes[0]), content=content, image_urls=images, video_urls=videos, disclaimer=(marker + disclaimer).strip() or None, related_entities=related if related else None)


def _mams(markup, seq, url):
    declarations = _script_values(markup)
    ids = declarations["activityId"]
    if len(ids) != 1 or type(ids[0]) is not int or str(ids[0]) != seq:
        _fail("活动专题身份与输入不一致")
    activity_values = declarations["activity"]
    if len(activity_values) > 1:
        _fail("活动专题存在重复必要 JSON 声明")
    activity = _object(activity_values[0], "activity") if activity_values else None
    if activity is None:
        _fail("活动专题缺少公开组件")
    page = _object(activity.get("page"), "activity.page")
    components = page.get("components")
    if not isinstance(components, list):
        _fail("活动专题组件列表无效")
    bodies = []
    for component in components:
        detail = _object(_object(component, "活动组件").get("detail"), "活动组件.detail")
        name = detail.get("name")
        if name != "ai-html-component":
            continue
        text = detail.get("text")
        if not isinstance(text, str):
            _fail("活动公开正文组件无效")
        if '\\"' in text or '\\n' in text:
            try:
                text = json.loads('"' + text + '"')
            except json.JSONDecodeError:
                _fail("活动正文转义无效")
        bodies.append(_tree(text))
    if not bodies:
        _fail("活动专题没有已核正文组件")
    content, images, videos = _body(_Node("article", children=bodies), url)
    return _result("topic", title=_title(_tree(markup)), content=content, image_urls=images, video_urls=videos)


def ths_get(url: str, *, timeout: float) -> dict:
    kind, canonical, seq, _ = classify_article_url(url)
    seconds = validate_timeout(timeout)
    if kind == "article_short":
        return _short_payload(_json(_SHORT_API + seq, seconds), seq, canonical)
    if kind == "news":
        if len(seq) <= 16:
            try:
                payload = _json(_NEWS_API + encode_news_seq(seq), seconds)
            except _ReadError as exc:
                if not exc.fallback:
                    raise
            else:
                return _news_payload(payload, seq, canonical)
        return _html_article(_read(canonical, timeout=seconds), seq, canonical)
    if kind == "article":
        try:
            payload = _json(_SHARE_API + seq, seconds)
        except _ReadError as exc:
            if not exc.fallback:
                raise
        else:
            return _community_payload(payload, seq, canonical)
        return _html_article(_read(canonical, timeout=seconds), seq, canonical, community=True)
    markup = _read(canonical, timeout=seconds)
    if kind == "topic_mams":
        return _mams(markup, seq, canonical)
    return _deep(markup, canonical)
