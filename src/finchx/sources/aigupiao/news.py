"""爱股票公开快讯，保留官网正文与证券、题材及媒体关联。"""

from datetime import datetime
import math
import re
from typing import Any
from urllib.parse import urlencode

from finchx._common.convert import to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx._common.news import BEIJING_TZ, in_window, validate_limit, validate_window

_SOURCE = "aigupiao"
_ENDPOINT = "https://apis.aigupiao.com/Express/express_list/"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://www.aigupiao.com/"}
_PAGE_SIZE = 20
_MAX_PAGES = 1000


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None or isinstance(value, str) and not value.strip():
        if not required:
            return None
    elif isinstance(value, str):
        return value
    raise SourceError(_SOURCE, f"字段 {field} 必须是{'非空' if required else ''}字符串")


def _array(raw: dict, field: str) -> list | None:
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, list):
        return value
    raise SourceError(_SOURCE, f"字段 {field} 必须是数组或空值")


def _relations(raw: dict) -> tuple[list | None, list | None]:
    items = _array(raw, "stock_infos")
    if items is None:
        return None, None
    securities, themes = [], []
    for item in items:
        if not isinstance(item, dict):
            raise SourceError(_SOURCE, "stock_infos 条目结构无效")
        if item.get("kind") == "stock":
            securities.append({"symbol": _text(item.get("code"), "stock_infos.code", required=True),
                               "name": _text(item.get("name"), "stock_infos.name")})
        elif item.get("kind") == "theme":
            themes.append({"id": _text(item.get("id"), "stock_infos.id", required=True),
                           "name": _text(item.get("content"), "stock_infos.content")})
        else:
            raise SourceError(_SOURCE, "stock_infos 出现未确认的关联类型")
    return securities, themes


def _topics(raw: dict) -> list | None:
    items = _array(raw, "topic")
    if items is None:
        return None
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise SourceError(_SOURCE, "topic 条目结构无效")
        result.append({"id": _text(item.get("id"), "topic.id", required=True),
                       "name": _text(item.get("title"), "topic.title")})
    return result


def _video(raw: dict) -> dict | None:
    item = raw.get("video")
    if item is None:
        return None
    if not isinstance(item, dict) or "kind" not in item:
        raise SourceError(_SOURCE, "video 必须是含 kind 的对象或空值")
    kind = item["kind"]
    if kind == "":
        return None
    if kind != "small_video":
        raise SourceError(_SOURCE, "video 出现未确认的媒体类型")
    return {"url": _text(item.get("video"), "video.video", required=True),
            "thumbnail_url": _text(item.get("video_img"), "video.video_img"),
            "cover_url": _text(item.get("video_cover_img"), "video.video_cover_img"),
            "duration_seconds": to_number(item.get("video_len"), "video.video_len", source=_SOURCE, nonnegative=True)}


def _attachments(raw: dict) -> list | None:
    items = _array(raw, "file")
    if items is None:
        return None
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise SourceError(_SOURCE, "file 条目结构无效")
        result.append({"name": _text(item.get("file_name"), "file.file_name"),
                       "type": _text(item.get("file_type"), "file.file_type"),
                       "url": _text(item.get("file_link"), "file.file_link", required=True)})
    return result


def _page(payload: Any) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("rslt") != "succ":
        raise SourceError(_SOURCE, "快讯来源状态表示请求失败")
    data = payload.get("data")
    if data == []:
        return []
    if not isinstance(data, dict):
        raise SourceError(_SOURCE, "快讯 data 必须是日期分组对象")
    result = []
    for group in data.values():
        if not isinstance(group, dict) or not isinstance(group.get("data"), list):
            raise SourceError(_SOURCE, "快讯日期分组结构无效")
        for raw in group["data"]:
            if not isinstance(raw, dict):
                raise SourceError(_SOURCE, "快讯条目结构无效")
            result.append(raw)
    return result


def _moment(value: Any) -> datetime:
    if type(value) is not int and not (isinstance(value, str) and re.fullmatch(r"[0-9]+", value)):
        raise SourceError(_SOURCE, "rec_time 必须是 Unix 秒整数")
    try:
        return datetime.fromtimestamp(int(value), BEIJING_TZ)
    except (ValueError, OverflowError, OSError) as exc:
        raise SourceError(_SOURCE, "rec_time 不是有效的来源时间") from exc


def _row(raw: dict, moment: datetime) -> dict:
    important = raw.get("important")
    if important is not None and important not in ("yes", "no"):
        raise SourceError(_SOURCE, "important 必须是 yes、no 或空值")
    content = _text(raw.get("web_content"), "web_content", required=True).replace("\r\n", "\n")
    title = _text(raw.get("title"), "title")
    if title is None:
        matched = re.match(r"^【([^【】\r\n]+)】", content)
        title = matched[1] if matched else None
    securities, themes = _relations(raw)
    images = _array(raw, "image")
    return {"id": _text(raw.get("id"), "id", required=True), "title": title,
            "published_at": moment.isoformat(timespec="seconds"), "content": content,
            "important": None if important is None else important == "yes",
            "url": _text(raw.get("url"), "url"), "related_securities": securities,
            "related_themes": themes, "related_topics": _topics(raw),
            "image_urls": None if images is None else [_text(image, "image", required=True) for image in images],
            "video": _video(raw), "attachments": _attachments(raw)}


def agp_list(limit: int = 20, since: str | None = None, until: str | None = None, *, timeout: float) -> list[dict]:
    """在北京时间闭区间内按来源顺序取最多 limit 条；分页失败不返回部分结果。"""
    target = validate_limit(limit)
    lower, upper = validate_window(since, until)
    seconds = validate_timeout(timeout)
    before = 0 if upper is None else math.floor(upper.timestamp()) + 1
    collected, seen = {}, set()
    previous_oldest = None
    for _ in range(_MAX_PAGES):
        url = _ENDPOINT + "?" + urlencode({"before": before, "source": "pc", "web_data": "yes",
                                          "number": _PAGE_SIZE, "division": "", "express_show_type": 1})
        raw_rows = _page(get_json(url, timeout=seconds, headers=_HEADERS, source=_SOURCE))
        if not raw_rows:
            return [row for row, moment in collected.values() if in_window(moment, lower, upper)][:target]
        moments = [_moment(raw.get("rec_time")) for raw in raw_rows]
        rows = [_row(raw, moment) for raw, moment in zip(raw_rows, moments)]
        identities = [row["id"] for row in rows]
        if len(set(identities)) != len(identities):
            raise SourceError(_SOURCE, "快讯同页 id 重复")
        if any(left < right for left, right in zip(moments, moments[1:])):
            raise SourceError(_SOURCE, "快讯来源页未按发布时间降序排列")
        if before and any(moment.timestamp() >= before for moment in moments):
            raise SourceError(_SOURCE, "快讯来源时间违反 before 排他上界")
        if previous_oldest is not None and moments[0] > previous_oldest:
            raise SourceError(_SOURCE, "快讯跨页发布时间顺序损坏")
        if not set(identities).difference(seen):
            raise SourceError(_SOURCE, "快讯分页停滞，没有新的新闻身份")
        seen.update(identities)
        for row, moment in zip(rows, moments):
            collected[row["id"]] = (row, moment)
        matched = [row for row, moment in collected.values() if in_window(moment, lower, upper)]
        if len(matched) >= target or lower is not None and moments[0] < lower:
            return matched[:target]
        next_before = int(moments[-1].timestamp())
        if before and next_before >= before:
            raise SourceError(_SOURCE, "快讯分页 before 未推进")
        before, previous_oldest = next_before, moments[-1]
    raise SourceError(_SOURCE, "快讯分页达到防护上限，不能确认请求范围已完成")
