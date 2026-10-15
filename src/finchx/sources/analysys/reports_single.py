"""易观独立研报：原生关键词搜索或热门分析目录及正式详情。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import re
from urllib.parse import unquote, urlencode

from finchx._common import http
from finchx._common.convert import parse_date_parameter, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.report_text import to_markdown
from finchx.sources.analysys import reports as old

_SOURCE = "analysys"
_FIELDS = ("url", "title", "publication_date", "published_at", "institute", "content",
           "content_type", "summary", "pdf_urls", "report_id", "column_id", "classify",
           "author", "keywords", "field", "first_field")
_HEADERS = {**http.DEFAULT_HEADERS, "Referer": old._BASE + "/article/analysis"}
_FALLBACK_FIELDS = ("title", "institute", "publication_date", "published_at", "summary", "column_id",
                    "classify", "author", "keywords", "field", "first_field")


def _published(value):
    if value is None or value == "":
        return None, None
    if not isinstance(value, str):
        raise SourceError(_SOURCE, "研报发布时间格式无效")
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value, re.ASCII):
            day = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
            return day, day
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", value, re.ASCII):
            stamp = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return stamp.date().isoformat(), stamp.replace(tzinfo=old._BEIJING).isoformat()
    except ValueError:
        pass
    raise SourceError(_SOURCE, "研报发布时间格式无效")


def _column(value):
    if value is None or value == "":
        return None
    if type(value) is int and value >= 0 or isinstance(value, str) and re.fullmatch(r"[0-9]+", value, re.ASCII):
        return value
    raise SourceError(_SOURCE, "研报栏目身份格式无效")


def _record(row):
    if not isinstance(row, dict):
        raise SourceError(_SOURCE, "研报业务记录结构无效")
    identity = old._identity(row.get("id"))
    url = old._BASE + "/article/detail/" + identity
    day, stamp = _published(row.get("publishdate"))
    content, links = old._body(row.get("content"), url)
    content_type = "webpage" if content is not None else None
    if content is None:
        images = row.get("images")
        if images is not None and not isinstance(images, list):
            raise SourceError(_SOURCE, "研报图片格式无效")
        image_urls = []
        for image in images or []:
            if not isinstance(image, dict):
                raise SourceError(_SOURCE, "研报图片格式无效")
            link = old._resource_url(image.get("path"), url)
            if link not in image_urls:
                image_urls.append(link)
        raw_summary = row.get("summary")
        if raw_summary is not None and not isinstance(raw_summary, str):
            raise SourceError(_SOURCE, "研报摘要格式无效")
        summary_body = to_markdown(raw_summary or "", base_url=url, source=_SOURCE)
        content = "\n\n".join(([summary_body] if summary_body else []) + [f"![]({link})" for link in image_urls]) or None
        content_type = "webpage" if image_urls else "summary" if content else None
    pdf_urls = list(dict.fromkeys((links or []) + old._attachments(row, identity, url)))
    return dict(zip(_FIELDS, (
        url, old._optional_text(row.get("maintitle"), "标题"), day, stamp,
        old._optional_text(row.get("source"), "机构"), content, content_type,
        old._optional_text(row.get("summary"), "摘要"), pdf_urls, identity,
        _column(row.get("columnid", row.get("columnId"))),
        old._optional_text(row.get("classify"), "分析分类"),
        old._optional_text(row.get("author"), "作者"),
        old._optional_text(row.get("keywords"), "关键词"),
        old._optional_text(row.get("field"), "领域"),
        old._optional_text(row.get("firstField"), "一级领域"),
    )))


def _page(keyword, cursor, *, timeout):
    if keyword is None:
        url = old._BASE + "/article/pager?" + urlencode({"p": cursor, "columnId": "8,22"})
        headers = _HEADERS
    else:
        url = old._SEARCH + "?" + urlencode({"keyword": keyword, "page": cursor})
        headers = old._HEADERS
    payload = http.get_json(url, timeout=timeout, headers=headers, source=_SOURCE)
    if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
        raise SourceError(_SOURCE, "研报目录或搜索响应结构无效")
    native_rows = payload["list"]
    if keyword is not None:
        if payload.get("keyword") != keyword:
            raise SourceError(_SOURCE, "研报搜索关键词不一致")
        next_cursor = cursor + 1 if native_rows else None
    else:
        total, pages = payload.get("total"), payload.get("pages")
        if type(total) is not int or total < 0 or type(pages) is not int or pages < 0 or pages != (total + 9) // 10:
            raise SourceError(_SOURCE, "研报目录分页计数无效")
        expected = min(10, max(0, total - (cursor - 1) * 10))
        if len(native_rows) != expected:
            raise SourceError(_SOURCE, "研报目录行数与分页计数不一致")
        next_cursor = cursor + 1 if cursor < pages else None
    rows = [_record(row) for row in native_rows]
    if len({row["report_id"] for row in rows}) != len(rows):
        raise SourceError(_SOURCE, "研报同页身份重复")
    return rows, next_cursor


def _detail(candidate, *, timeout):
    body = http.get_text(candidate["url"], timeout=timeout, headers=_HEADERS, source=_SOURCE)
    marker = re.search(r"window\.__INITIAL_STATE__\s*=\s*", body)
    if marker is None:
        raise SourceError(_SOURCE, "研报详情初始化数据缺失")
    try:
        state, _ = json.JSONDecoder().raw_decode(body[marker.end():])
        if not isinstance(state, dict) or state.get("isError") is True or not isinstance(state.get("article"), str):
            raise ValueError
        native = json.loads(unquote(state["article"], encoding="utf-8", errors="strict"))
    except (ValueError, UnicodeError):
        raise SourceError(_SOURCE, "研报详情初始化数据无效") from None
    detail = _record(native)
    if detail["report_id"] != candidate["report_id"]:
        raise SourceError(_SOURCE, "研报详情身份与目录或搜索记录不一致")
    if detail["content"] is None and not detail["pdf_urls"]:
        raise SourceError(_SOURCE, "研报详情正文及真实附件均缺失，或来源限制访问")
    detail["_detail_fields"] = tuple(field for field in _FALLBACK_FIELDS if detail[field] is not None)
    for field in _FALLBACK_FIELDS:
        if detail[field] is None:
            detail[field] = candidate[field]
    return detail


def analysys_fetch(limit=20, keyword=None, start_date=None, end_date=None, *, timeout):
    """读取易观报告，按 publishdate 筛选；每次网络请求使用客户端超时。"""
    if type(limit) is not int or limit <= 0:
        raise ValueError("limit 必须是非布尔正整数")
    if keyword is not None:
        if not isinstance(keyword, str):
            raise ValueError("keyword 必须是字符串或 None")
        try:
            keyword.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("keyword 必须是有效 Unicode 字符串") from exc
        if any(ord(char) < 32 or ord(char) == 127 for char in keyword):
            raise ValueError("keyword 不能含控制字符")
        keyword = keyword.strip() or None
    start = parse_date_parameter(start_date, "start_date").isoformat() if start_date is not None else None
    end = parse_date_parameter(end_date, "end_date").isoformat() if end_date is not None else None
    if start and end and start > end:
        raise ValueError("start_date 不能晚于 end_date")
    seconds = validate_timeout(timeout)
    candidates, details, positions = {}, {}, {}
    cursor, stagnant = 1, 0

    def eligible(row):
        day = row["publication_date"]
        return not ((start and (day is None or day < start)) or (end and (day is None or day > end)))

    def effective(identity):
        original = candidates[identity]
        row = dict(details.get(identity, original))
        if identity in details:
            authority = details[identity].get("_detail_fields", _FALLBACK_FIELDS)
            for field in _FALLBACK_FIELDS:
                if field not in authority:
                    row[field] = original[field]
        return row

    def groups():
        grouped = {}
        for identity in candidates:
            row = effective(identity)
            if identity in details and not eligible(row):
                continue
            key = (("business", row["title"], row["institute"], row["publication_date"])
                   if row["title"] and row["institute"] and row["publication_date"] else ("id", identity))
            grouped.setdefault(key, []).append(row)
        selected = []
        for members in grouped.values():
            representative = max(members, key=lambda row: (row["publication_date"] or "",
                                 bool(row["content"]) + bool(row["pdf_urls"]), -positions[row["report_id"]]))
            selected.append((members, representative))
        selected.sort(key=lambda group: (group[1]["publication_date"] is None,
                      -int(group[1]["publication_date"].replace("-", "")) if group[1]["publication_date"] else 0,
                      positions[group[1]["report_id"]]))
        return selected[:limit]

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="finchx-analysys-reports") as executor:
        while cursor is not None:
            rows, next_cursor = _page(keyword, cursor, timeout=seconds)
            if next_cursor is not None and (type(next_cursor) is not int or next_cursor <= cursor):
                raise SourceError(_SOURCE, "研报分页游标未推进，来源未完成")
            fresh = False
            for row in rows:
                identity = row["report_id"]
                if identity not in positions:
                    positions[identity] = len(positions)
                    fresh = True
                candidates[identity] = row
            stagnant = 0 if fresh else stagnant + 1
            if next_cursor is not None and stagnant >= 3:
                raise SourceError(_SOURCE, "研报分页持续停滞，来源未完成")
            required = set()
            while True:
                selected = groups()
                for members, _ in selected:
                    required.update(row["report_id"] for row in members if row["report_id"] not in details)
                pending = sorted(required - details.keys(), key=positions.__getitem__)
                if not pending:
                    break
                batch = pending[:4]
                jobs = [executor.submit(_detail, candidates[identity], timeout=seconds) for identity in batch]
                for identity, job in zip(batch, jobs):
                    details[identity] = job.result()
            selected = groups()
            # 仅无词目录的完整页可用日期下界结束；先确认本页正式详情，
            # 缺日期或详情改回范围均不能把该页当作已越过下界。
            below_start = (keyword is None and start is not None and len(rows) == 10
                           and all(row["report_id"] in details
                                   and effective(row["report_id"])["publication_date"] is not None
                                   and effective(row["report_id"])["publication_date"] < start
                                   for row in rows))
            if len(selected) >= limit or next_cursor is None or below_start:
                return [{field: representative[field] for field in _FIELDS} for _, representative in selected]
            cursor = next_cursor
