"""账户关注动态中的回复全文；认证仅用于当次官方请求。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlencode, urljoin, urlsplit

from finchx._common.convert import parse_date_time_string, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text
from finchx._common.news import BEIJING_TZ, in_window, validate_limit

_SOURCE = "taoguba"
_BASE = "https://www.tgb.cn/"
_FEED = _BASE + "super/spefocus/friendActions"
_FULL = _BASE + "topic/getReplyContent"
_PAGE_SIZE = 20
_MAX_PAGES = 1000
_MAX_REQUESTS = 3000
_MAX_BYTES = 4 * 1024 * 1024
_GATES = ("登录可查看全文", "登录后查看全文", "该回复已删除", "该跟帖已删除")


def _fail(reason):
    raise SourceError(_SOURCE, reason)


def _cookies(value):
    if isinstance(value, Mapping):
        if not value:
            raise ValueError("cookies 不能为空")
        parts = []
        for key, item in value.items():
            if (not isinstance(key, str) or re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) is None
                    or not isinstance(item, str) or ";" in item):
                raise ValueError("cookies 必须是合法字符串键值字典")
            parts.append(key + "=" + item)
        value = "; ".join(parts)
    if (not isinstance(value, str) or not value.strip()
            or re.search(r"[\x00-\x1f\x7f]", value)):
        raise ValueError("cookies 必须是无控制字符的非空字符串或字符串键值字典")
    try:
        value.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError("cookies 必须是合法 HTTP Cookie 字符串") from exc
    return value.strip()


def _window(since, until):
    bounds = []
    for value, name, upper in ((since, "since", False), (until, "until", True)):
        if value is None:
            bounds.append(None)
            continue
        if isinstance(value, date) and not isinstance(value, datetime):
            parsed = value
        else:
            parsed = parse_date_time_string(value, name)
        bounds.append(parsed.replace(tzinfo=BEIJING_TZ) if isinstance(parsed, datetime)
                      else datetime.combine(parsed, time.max if upper else time.min, BEIJING_TZ))
    if bounds[0] is not None and bounds[1] is not None and bounds[0] > bounds[1]:
        raise ValueError("since 不得晚于 until")
    return tuple(bounds)


def _id(value, name, *, optional=False):
    if optional and (value is None or value == ""):
        return None
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,64}", value) is None or int(value) <= 0:
        _fail(f"{name} 不是有效 ASCII 数字身份")
    return value


def _text(value, name):
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(f"{name} 必须是文字或空值")
    return value if value.strip() else None


def _moment(value):
    text = _text(value, "actionDate")
    if text is None:
        return None, None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}(?::[0-9]{2})?", text) is None:
        _fail("actionDate 不是有效来源完整日期时刻")
    try:
        moment = datetime(
            int(text[:4]), int(text[5:7]), int(text[8:10]),
            int(text[11:13]), int(text[14:16]), int(text[17:19]) if len(text) == 19 else 0,
            tzinfo=BEIJING_TZ,
        )
    except ValueError:
        _fail("actionDate 不是有效来源完整日期时刻")
    return moment, moment.isoformat(timespec="seconds" if len(text) == 19 else "minutes")


def _success(payload):
    if not isinstance(payload, dict):
        _fail("响应必须是 JSON 对象")
    for envelope in (payload, payload.get("dto")):
        if not isinstance(envelope, dict):
            continue
        for key in ("status", "success", "rslt"):
            if key in envelope and envelope[key] is not True and envelope[key] not in ("success", "succ", "true"):
                _fail("来源拒绝访问或认证失效")
        if str(envelope.get("code", "")) in ("401", "403", "-1"):
            _fail("来源拒绝访问或认证失效")


@dataclass
class _Activity:
    reply_id: str
    topic_id: str
    post_id: str
    moment: datetime | None
    row: dict
    quoted: bool
    quote_username: str | None


def _feed_page(payload):
    _success(payload)
    dto = payload.get("dto")
    if not isinstance(dto, dict):
        _fail("动态必须包含有效 dto 对象")
    size = dto.get("size")
    if "size" in dto and not (
            type(size) is int and size >= 0
            or isinstance(size, str) and re.fullmatch(r"0|[1-9][0-9]*", size) is not None):
        _fail("动态 size 不是有效非负整数标记")
    empty_size = type(size) is int and size == 0 or type(size) is str and size == "0"
    records = dto.get("record")
    if empty_size and isinstance(records, list) and records:
        _fail("动态 size=0 与非空 record 冲突")
    # 成功空数组保留原耗尽能力；缺失/空 record 仅兼容官方明确 size=0。
    if records is None or isinstance(records, list) and not records:
        if payload.get("status") is True and (empty_size or isinstance(records, list)):
            return [], set(), None
        _fail("空动态缺少明确成功空数组或 size=0 标记，不能确定耗尽")
    if not isinstance(records, list) or len(records) > 1000:
        _fail("动态必须包含完整 dto.record 数组，不能将未知结构当作耗尽")
    activities, action_ids = [], set()
    next_cursor = None
    for item in records:
        if not isinstance(item, dict):
            _fail("动态条目必须是对象")
        action_id = _id(item.get("actionID"), "actionID")
        if action_id in action_ids:
            _fail("同页动态 actionID 重复")
        action_ids.add(action_id)
        next_cursor = action_id
        action = _text(item.get("actionName"), "actionName")
        if action is None:
            _fail("动态缺失 actionName，无法确定回复身份")
        if action != "R":
            continue
        reply_id = _id(item.get("otherID"), "otherID")
        topic_id = _id(item.get("objectID"), "objectID")
        post_id = item.get("newTopicID")
        if not isinstance(post_id, str) or re.fullmatch(r"[A-Za-z0-9]{1,128}", post_id) is None:
            _fail("newTopicID 不是有效主题身份")
        moment, timestamp = _moment(item.get("actionDate"))
        user_id = _id(item.get("userID"), "userID", optional=True)
        username = _text(item.get("userName"), "userName")
        _text(item.get("body"), "body")  # 摘要只验证，不能用它回填全文。
        quote_text = _text(item.get("quoteContent"), "quoteContent")
        quote_user = _text(item.get("quoteUserName"), "quoteUserName")
        post_url = _BASE + "a/" + post_id
        row = dict(reply_id=reply_id, user_id=user_id, username=username,
                   reply_time=timestamp, content=None, image_urls=[], post_url=post_url,
                   url=post_url + "/" + reply_id + "#" + reply_id,
                   parent_reply_id=None, parent_username=None, parent_content=None,
                   parent_image_urls=None)
        activities.append(_Activity(reply_id, topic_id, post_id, moment, row,
                                    quote_text is not None or quote_user is not None, quote_user))
    return activities, action_ids, next_cursor


@dataclass
class _Node:
    tag: str
    attrs: dict
    parent: "_Node | None" = None
    children: list = field(default_factory=list)

    def walk(self):
        pending = [self]
        while pending:
            node = pending.pop()
            yield node
            pending.extend(child for child in reversed(node.children) if isinstance(child, _Node))

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def raw_text(self):
        return "".join(child.raw_text() if isinstance(child, _Node) else child for child in self.children)

    def text(self):
        if self.tag in ("script", "style"):
            return ""
        if self.tag == "br":
            return "\n"
        value = "".join(child.text() if isinstance(child, _Node) else child for child in self.children)
        return "\n" + value + "\n" if self.tag in ("div", "p", "li", "tr", "blockquote") else value


class _Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.current = _Node("root", {})
        try:
            self.feed(html)
            self.close()
        except (ValueError, RecursionError):
            _fail("正文 HTML 结构损坏")

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

    def handle_data(self, data):
        self.current.children.append(data)


def _body(node):
    try:
        text = node.text().strip()
    except RecursionError:
        _fail("正文 HTML 嵌套超过防护范围")
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if any(marker in text for marker in _GATES):
        _fail("正文已删除或需要额外访问权限")
    images = []
    for child in node.walk():
        if child.tag != "img":
            continue
        raw = child.attrs.get("data-original") or child.attrs.get("src")
        if not raw or re.search(r"[\x00-\x20\x7f\\]", raw):
            _fail("正文图片地址损坏")
        url = urljoin(_BASE, raw)
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in ("http", "https") and bool(parsed.hostname) and parsed.username is None
            parsed.port
        except ValueError:
            valid = False
        if not valid:
            _fail("正文图片地址损坏")
        if url not in images:
            images.append(url)
    if not text and not images:
        _fail("来源未提供可用回复全文")
    return text or None, images


@dataclass
class _Reply:
    body: tuple | None
    expandable: bool
    has_quote: bool
    parent_id: str | None
    parent_username: str | None
    parent_body: tuple | None


def _page(html, topic_id):
    root = _Tree(html).root
    scripts = "\n".join(node.raw_text() for node in root.walk() if node.tag == "script")
    ids = set(re.findall(r"\bvar\s+topicTopicID2\s*=\s*([0-9]+)\s*;", scripts))
    if ids != {topic_id}:
        _fail("主题页面身份与动态不一致")
    replies = {}
    for node in root.walk():
        match = re.fullmatch(r"reply([0-9]+)", node.attrs.get("id", ""))
        if not match or not node.has_class("comment-data-text"):
            continue
        reply_id = _id(match[1], "页面 replyID")
        container = node.parent
        while container is not None and not container.has_class("comment-data"):
            container = container.parent
        if container is None or reply_id in replies:
            _fail("页面回复容器缺失或回复身份重复")
        controls = [child for child in container.walk() if child.attrs.get("data-reply-id") == reply_id
                    and child.attrs.get("data-topic-id") == topic_id]
        if not controls:
            _fail("页面回复身份没有对应主题")
        quote_nodes = [child for child in container.walk() if child.has_class("comment-data-quote")]
        if len(quote_nodes) > 1:
            _fail("页面引用结构歧义")
        parent_id = parent_username = parent_body = None
        if quote_nodes:
            quote = quote_nodes[0]
            parent_ids = {_id(child.attrs["data-quote-id"], "data-quote-id")
                          for child in quote.walk() if "data-quote-id" in child.attrs}
            # 官网动态生成的同一展开按钮使用数字函数参数，静态模板使用 data 属性。
            for child in quote.walk():
                call = re.fullmatch(
                    r"\s*(?:more|less)QuoteContent\(\s*this\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)\s*;?\s*",
                    child.attrs.get("onclick", ""))
                if call:
                    if _id(call[1], "引用 topicID") != topic_id:
                        _fail("引用展开主题身份与动态不一致")
                    parent_ids.add(_id(call[2], "引用 replyID"))
            if len(parent_ids) > 1:
                _fail("页面引用缺少明确唯一父回复身份")
            parent_id = next(iter(parent_ids), None)
            if parent_id == reply_id:
                _fail("回复不能引用自身")
            names = []
            for child in quote.walk():
                if child.tag != "a" or re.fullmatch(r"/blog/[0-9]+", child.attrs.get("href", "")) is None:
                    continue
                ancestor = child.parent
                in_content = False
                while ancestor is not None and ancestor is not quote:
                    in_content |= ancestor.has_class("quote-content")
                    ancestor = ancestor.parent
                if not in_content:
                    names.append(child.raw_text().strip())
            parent_username = names[0] if len(names) == 1 else None
            contents = [child for child in quote.walk() if child.has_class("quote-content")]
            content_nodes = {id(child) for content in contents for child in content.walk()}
            # 官网把引用文字原样放在 data-quote-text；须补抓的引用另附展开控件。
            # 无展开的正式正文节点可以直接保留，父编号仍只取明确身份。
            needs_expand = any(
                child.has_class("data-quote-zk")
                or child.attrs.get("onclick", "").lstrip().startswith(("moreQuoteContent", "lessQuoteContent"))
                or child.tag == "a" and child.raw_text().strip() in ("展开", "[展开]", "收起", "[收起]")
                for child in quote.walk()
                if id(child) not in content_nodes)
            if (parent_id is None and len(contents) == 1
                    and contents[0].has_class("data-quote-text") and not needs_expand):
                try:
                    parent_body = _body(contents[0])
                except SourceError:
                    pass  # 无关引用候选不可用，只有目标需要它时才拒绝。
        expandable = any(child.attrs.get("onclick", "").startswith("moreReplyContent") for child in container.walk())
        try:
            body = _body(node)
        except SourceError:
            # 页面候选不可用时，准确目标仍可用官方展开请求取得全文；
            # 无关回复的空白、删除或权限提示不影响目标定位。
            body, expandable = None, True
        replies[reply_id] = _Reply(body, expandable, bool(quote_nodes), parent_id, parent_username, parent_body)
    return replies


def tgb_replies(limit=20, since=None, until=None, *, cookies, timeout):
    """读取当前账户动态的唯一匹配回复，正文及引用均要求全文。"""
    if limit is not None:
        validate_limit(limit)
    lower, upper = _window(since, until)
    seconds, cookie = validate_timeout(timeout), _cookies(cookies)
    headers = {**DEFAULT_HEADERS, "Referer": _BASE, "X-Requested-With": "XMLHttpRequest", "Cookie": cookie}
    requests = 0

    def read(url, params=None):
        nonlocal requests
        requests += 1
        if requests > _MAX_REQUESTS:
            _fail("请求达到防护预算，不能返回不完整结果")
        if urlsplit(url).hostname != "www.tgb.cn":
            _fail("认证请求不得离开官方主机")
        if params:
            url += "?" + urlencode(params)
        text = get_text(url, timeout=seconds, headers=headers, source=_SOURCE, follow_redirects=False)
        if len(text.encode("utf-8")) > _MAX_BYTES:
            _fail("响应超过防护大小")
        return text

    def read_json(url, params):
        try:
            return json.loads(read(url, params))
        except (ValueError, RecursionError):
            _fail("响应不是有效 JSON")

    observed, action_ids, post_topics, topic_posts = {}, set(), {}, {}
    cursor, seen_cursors = "0", {"0"}
    matching = []
    for _ in range(_MAX_PAGES):
        payload = read_json(_FEED, dict(perPageNum=_PAGE_SIZE, actionID=cursor, type="A"))
        page, ids, next_cursor = _feed_page(payload)
        if not ids:
            break
        if ids <= action_ids or next_cursor in seen_cursors:
            _fail("动态分页停滞，不能返回不完整结果")
        action_ids.update(ids)
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        for activity in page:
            if (activity.post_id in post_topics and post_topics[activity.post_id] != activity.topic_id
                    or activity.topic_id in topic_posts and topic_posts[activity.topic_id] != activity.post_id):
                _fail("主题数字身份与链接身份冲突")
            post_topics[activity.post_id] = activity.topic_id
            topic_posts[activity.topic_id] = activity.post_id
            previous = observed.get(activity.reply_id)
            if previous is not None and (previous.topic_id, previous.post_id) != (activity.topic_id, activity.post_id):
                _fail("同一回复的主题身份冲突")
            observed[activity.reply_id] = activity
        matching = []
        for activity in observed.values():
            if (lower is not None or upper is not None) and activity.moment is None:
                _fail("缺少回复时间，无法确定时间筛选归属")
            if activity.moment is None or in_window(activity.moment, lower, upper):
                matching.append(activity)
        if limit is not None and len(matching) >= limit:
            break
    else:
        _fail("动态分页达到防护预算，不能返回不完整结果")
    selected = matching[:limit] if observed else []
    full = {}

    def expand(topic_id, reply_id):
        key = (topic_id, reply_id)
        if key not in full:
            payload = read_json(_FULL, dict(topicID=topic_id, replyID=reply_id))
            if not isinstance(payload, dict) or payload.get("status") is not True:
                _fail("回复全文访问失败或认证失效")
            html = payload.get("dto")
            if not isinstance(html, str):
                _fail("回复全文 dto 必须是 HTML 字符串")
            body = _Tree(html).root
            if any(node.attrs.get("onclick", "").startswith("moreReplyContent") for node in body.walk()):
                _fail("官方展开响应仍包含未展开正文")
            full[key] = _body(body)
        return full[key]

    # 先准备必要页面，再按动态源序输出，避免无引用目标在前时提前展开。
    groups = {}
    for activity in selected:
        groups.setdefault(activity.post_id, []).append(activity)
    pages = {}
    for post_id, targets in groups.items():
        quoted = [activity for activity in targets if activity.quoted]
        if not quoted and len(targets) < 2:
            continue
        topic_id = targets[0].topic_id
        html = read(targets[0].row["post_url"])
        # 可选批量页优化遇到合法无身份页时仍可精确读正文；引用页必须核身份。
        if not quoted and not re.search(r"\bvar\s+topicTopicID2\s*=", html):
            continue
        known = _page(html, topic_id)
        pages[post_id] = known
        for activity in quoted:
            if activity.reply_id not in known:
                known.update(_page(read(activity.row["url"].split("#")[0]), topic_id))
            reply = known.get(activity.reply_id)
            if reply is None or reply.parent_id is None and reply.parent_body is None:
                _fail("明确引用的回复未找到准确父回复身份")
        for activity in targets:
            reply = known.get(activity.reply_id)
            if reply is not None and reply.has_quote and reply.parent_id is None and reply.parent_body is None:
                _fail("已观察到引用但缺少准确父回复身份")
        for reply_id, candidate in known.items():
            if not candidate.expandable and candidate.body is not None:
                full.setdefault((topic_id, reply_id), candidate.body)

    output = []
    for activity in selected:
        row = activity.row.copy()
        reply = pages.get(activity.post_id, {}).get(activity.reply_id)
        if activity.quoted or reply is not None and reply.has_quote:
            row["parent_reply_id"] = reply.parent_id
            row["parent_username"] = reply.parent_username or activity.quote_username
            row["parent_content"], row["parent_image_urls"] = (
                expand(activity.topic_id, reply.parent_id) if reply.parent_id is not None else reply.parent_body)
        row["content"], row["image_urls"] = expand(activity.topic_id, activity.reply_id)
        output.append(row)
    return output
