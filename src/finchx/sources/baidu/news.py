"""百度股市通公开快讯，正文只取同份响应的已确认文字条目。"""

from datetime import datetime
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx._common.news import BEIJING_TZ, in_window, validate_limit, validate_window

_SOURCE = "baidu"
_ENDPOINT = "https://finance.pae.baidu.com/selfselect/expressnews"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://gushitong.baidu.com/expressnews"}
_PAGE_SIZE = 20
_MAX_PAGES = 1000


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None or isinstance(value, str) and not value.strip():
        if not required:
            return None
    elif isinstance(value, str):
        return value
    raise SourceError(_SOURCE, f"字段 {field} 必须是{'非空' if required else ''}字符串")


def _relations(raw: dict) -> list | None:
    items = raw.get("entity")
    if items is None:
        return None
    if not isinstance(items, list):
        raise SourceError(_SOURCE, "entity 必须是数组或空值")
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise SourceError(_SOURCE, "entity 条目结构无效")
        result.append({"code": _text(item.get("code"), "entity.code", required=True),
                       "name": _text(item.get("name"), "entity.name"),
                       "market": _text(item.get("market"), "entity.market", required=True)})
    return result


def _content(raw: dict) -> str:
    content = raw.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("items"), list) or not content["items"]:
        raise SourceError(_SOURCE, "快讯 content.items 必须是非空文字数组")
    parts = []
    for item in content["items"]:
        if not isinstance(item, dict) or item.get("type") != "text":
            raise SourceError(_SOURCE, "content.items 出现结构损坏或未确认的内容类型")
        parts.append(_text(item.get("data"), "content.items.data", required=True))
    return "".join(parts)


def _page(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        raise SourceError(_SOURCE, "快讯响应外层结构无效")
    code = payload.get("ResultCode")
    if type(code) is int:
        code = str(code)
    if code == "3402":
        result = payload.get("Result")
        # 官网在偏移超过当前快讯窗口后返回 3402 / Result=[]。
        if result is None or result == {} or isinstance(result, list) and not result:
            return []
        if isinstance(result, dict):
            content = result.get("content")
            if content is None or isinstance(content, dict) and content.get("list") in (None, []):
                return []
        raise SourceError(_SOURCE, "快讯空状态与返回业务结构冲突")
    if code != "0":
        raise SourceError(_SOURCE, "快讯来源状态表示请求失败")
    result = payload.get("Result")
    if not isinstance(result, dict) or result.get("type") != "expressnews":
        raise SourceError(_SOURCE, "快讯 Result 必须明确为 expressnews")
    content = result.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("list"), list):
        raise SourceError(_SOURCE, "快讯 content.list 必须是数组")
    return content["list"]


def _moment(value: Any) -> datetime:
    if type(value) is not int and not (isinstance(value, str) and re.fullmatch(r"[0-9]+", value)):
        raise SourceError(_SOURCE, "publish_time 必须是 Unix 秒整数")
    try:
        return datetime.fromtimestamp(int(value), BEIJING_TZ)
    except (ValueError, OverflowError, OSError) as exc:
        raise SourceError(_SOURCE, "publish_time 不是有效的来源时间") from exc


def _row(raw: Any, moment: datetime) -> dict:
    important = raw.get("important")
    if important is not None and not (type(important) is int and important in (0, 1) or isinstance(important, str) and important in ("0", "1")):
        raise SourceError(_SOURCE, "important 必须是 0、1 或空值")
    content = _content(raw)
    title = _text(raw.get("title"), "title")
    if title is None:
        matched = re.match(r"^【([^【】\r\n]+)】", content)
        title = matched[1] if matched else None
    return {"id": _text(raw.get("loc"), "loc", required=True), "title": title,
            "published_at": moment.isoformat(timespec="seconds"), "content": content,
            "important": None if important is None else str(important) == "1",
            "url": _text(raw.get("third_url"), "third_url"),
            "provider": _text(raw.get("provider"), "provider"), "tag": _text(raw.get("tag"), "tag"),
            "related_securities": _relations(raw)}


def bd_list(limit: int = 20, since: str | None = None, until: str | None = None, *, timeout: float) -> list[dict]:
    """从来源最新页扫描北京时间闭区间；源偏移使用完整页行数。"""
    target = validate_limit(limit)
    lower, upper = validate_window(since, until)
    seconds = validate_timeout(timeout)
    collected, seen = {}, set()
    offset, previous_oldest = 0, None
    for _ in range(_MAX_PAGES):
        url = _ENDPOINT + "?" + urlencode({"rn": _PAGE_SIZE, "pn": offset, "tag": "",
                                          "filterByUserStocks": 0, "finClientType": "pc"})
        raw_rows = _page(get_json(url, timeout=seconds, headers=_HEADERS, source=_SOURCE))
        if not raw_rows:
            return [row for row, moment in collected.values() if in_window(moment, lower, upper)][:target]
        if not all(isinstance(raw, dict) for raw in raw_rows):
            raise SourceError(_SOURCE, "快讯条目结构无效")
        moments = [_moment(raw.get("publish_time")) for raw in raw_rows]
        rows = [_row(raw, moment) for raw, moment in zip(raw_rows, moments)]
        identities = [row["id"] for row in rows]
        if len(set(identities)) != len(identities):
            raise SourceError(_SOURCE, "快讯同页 loc 重复")
        if any(left < right for left, right in zip(moments, moments[1:])):
            raise SourceError(_SOURCE, "快讯来源页未按发布时间降序排列")
        new_moments = [moment for row, moment in zip(rows, moments) if row["id"] not in seen]
        if not new_moments:
            raise SourceError(_SOURCE, "快讯分页停滞，没有新的新闻身份")
        if previous_oldest is not None and new_moments[0] > previous_oldest:
            raise SourceError(_SOURCE, "快讯跨页发布时间顺序损坏")
        seen.update(identities)
        for row, moment in zip(rows, moments):
            collected[row["id"]] = (row, moment)
        matched = [row for row, moment in collected.values() if in_window(moment, lower, upper)]
        if len(matched) >= target or lower is not None and moments[0] < lower:
            return matched[:target]
        offset += len(raw_rows)
        previous_oldest = moments[-1]
    raise SourceError(_SOURCE, "快讯分页达到防护上限，不能确认请求范围已完成")
