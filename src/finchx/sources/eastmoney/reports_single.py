"""东方财富独立研报读取：原生关键词搜索或无关键词目录。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import re
from urllib.parse import urlencode

from finchx._common import http
from finchx._common.convert import parse_date_parameter, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.report_text import to_markdown
from finchx.sources.eastmoney import reports as legacy

_SOURCE = "eastmoney"
_FIELDS = ("url", "title", "publication_date", "institute", "content", "content_type",
           "pdf_urls", "info_code", "column_type", "report_type", "researcher",
           "institute_code", "institute_full_name", "stock_code", "stock_name", "market",
           "securities", "industry_code", "industry_name", "rating", "pdf_pages")
_ROUTES = {"个股研报": "zw_stock", "行业研报": "zw_industry", "策略报告": "zw_strategy",
           "宏观研究": "zw_macresearch", "宏观策略": "zw_macresearch", "券商晨会": "zw_brokerreport"}
_HEADERS = {**http.DEFAULT_HEADERS, "Referer": "https://data.eastmoney.com/report/"}


def _integer(value, label):
    if type(value) is int and value >= 0:
        return value
    raise SourceError(_SOURCE, f"研报{label}格式无效")


def _catalog_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}", value, re.ASCII):
        raise SourceError(_SOURCE, "研报目录发布日期格式无效")
    try:
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError as exc:
        raise SourceError(_SOURCE, "研报目录发布日期无效") from exc
    return value[:10]


def _catalog_page(page, start, end, *, timeout):
    params = {"cb": "research", "pageSize": 20, "pageNo": page, "fields": "",
              "qType": "*", "author": "*", "orgCode": "*", "beginTime": start or "", "endTime": end or ""}
    url = "https://reportapi.eastmoney.com/report/dg?" + urlencode(params)
    body = http.get_text(url, timeout=timeout, headers=_HEADERS, source=_SOURCE)
    match = re.fullmatch(r"\s*research\s*\((.*)\)\s*;?\s*", body, re.S)
    if match is None:
        raise SourceError(_SOURCE, "研报目录响应不是有效的 JSONP")
    try:
        payload = json.loads(match[1])
    except ValueError as exc:
        raise SourceError(_SOURCE, "研报目录响应不是有效的 JSON") from exc
    if not isinstance(payload, dict):
        raise SourceError(_SOURCE, "研报目录结构无效")
    total = _integer(payload.get("hits"), "目录数量")
    pages = _integer(payload.get("TotalPage"), "目录页数")
    current = _integer(payload.get("pageNo"), "目录页码")
    rows = payload.get("data")
    if current != page or not isinstance(rows, list) or len(rows) > 20 or len(rows) > total or (total and pages == 0):
        raise SourceError(_SOURCE, "研报目录分页结构无效")
    expected_pages = (total + 19) // 20
    expected_rows = min(20, max(0, total - (page - 1) * 20))
    if (pages != expected_pages and not (total == 0 and pages == 1)) or len(rows) != expected_rows:
        raise SourceError(_SOURCE, "研报目录数量、页数与当前页条数不一致，来源未完成")
    output, identities = [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("infoCode"), str) or not legacy._ID.fullmatch(row["infoCode"]):
            raise SourceError(_SOURCE, "研报目录身份无效")
        identity = row["infoCode"]
        if identity in identities:
            raise SourceError(_SOURCE, "研报目录同页身份重复")
        identities.add(identity)
        category = legacy._text(row.get("columnType"), "类别")
        if category not in _ROUTES:
            raise SourceError(_SOURCE, "研报目录类别无法确认")
        item = dict.fromkeys(_FIELDS)
        item.update(info_code=identity, title=legacy._text(row.get("title"), "标题"),
                    publication_date=_catalog_date(row.get("publishDate")),
                    institute=legacy._text(row.get("orgSName"), "机构"), column_type=category,
                    url="https://data.eastmoney.com/report/" + _ROUTES[category] + ".jshtml?" + urlencode({"infocode": identity}))
        for field, native in (("researcher", "researcher"), ("institute_code", "orgCode"),
                              ("institute_full_name", "orgName"), ("stock_code", "stockCode"),
                              ("stock_name", "stockName"), ("market", "market"),
                              ("industry_code", "industryCode"), ("industry_name", "industryName")):
            item[field] = legacy._text(row.get(native), field)
        if row.get("reportType") not in (None, ""):
            item["report_type"] = _integer(row["reportType"], "类型")
        output.append(item)
    return output, None if not rows or page >= pages else page + 1


def _search_page(keyword, page, *, timeout):
    params = {"uid": "", "keyword": keyword, "type": ["researchReport"], "client": "web",
              "clientVersion": "curr", "clientType": "web",
              "param": {"researchReport": {"client": "web", "pageSize": 20, "pageIndex": page}}}
    url = legacy._SEARCH_URL + "?" + urlencode({"cb": "research", "param": json.dumps(params, ensure_ascii=False, separators=(",", ":"))})
    body = http.get_text(url, timeout=timeout, headers=legacy._HEADERS, source=_SOURCE)
    match = re.fullmatch(r"\s*research\s*\((.*)\)\s*;?\s*", body, re.S)
    if match is None:
        raise SourceError(_SOURCE, "研报搜索响应不是有效的 JSONP")
    try:
        payload = json.loads(match[1])
    except ValueError as exc:
        raise SourceError(_SOURCE, "研报搜索响应不是有效的 JSON") from exc
    if not isinstance(payload, dict) or type(payload.get("code")) is not int or payload["code"] != 0 or payload.get("bizCode") not in (None, "", 0):
        raise SourceError(_SOURCE, "研报搜索状态异常或来源拒绝访问")
    total = _integer(payload.get("hitsTotal"), "搜索数量")
    result = payload.get("result")
    rows = result.get("researchReport") if isinstance(result, dict) else None
    if not isinstance(rows, list) or len(rows) > 20 or len(rows) > total:
        raise SourceError(_SOURCE, "研报搜索结果结构无效")
    if not rows and (page - 1) * 20 < total:
        raise SourceError(_SOURCE, "研报搜索提前结束，来源未完成")
    output, identities = [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("code"), str) or not legacy._ID.fullmatch(row["code"]):
            raise SourceError(_SOURCE, "研报搜索身份无效")
        identity = row["code"]
        if identity in identities:
            raise SourceError(_SOURCE, "研报搜索同页身份重复")
        identities.add(identity)
        item = dict.fromkeys(_FIELDS)
        item.update(info_code=identity, title=legacy._text(row.get("title"), "标题"),
                    institute=legacy._text(row.get("source"), "机构"),
                    publication_date=legacy._date(row.get("date")),
                    stock_name=legacy._text(row.get("stockName"), "股票名称"),
                    url=legacy._DETAIL_URL + "?" + urlencode({"infocode": identity}))
        output.append(item)
    return output, None if not rows or page * 20 >= total else page + 1


class _Page(legacy._Page):
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "ctx-content" in (values.get("class") or "").split() and values.get("id") != "ctx-content":
            attrs = [(key, value) for key, value in attrs if key != "id"] + [("id", "ctx-content")]
        super().handle_starttag(tag, attrs)


def _detail(candidate, *, timeout):
    body = http.get_text(candidate["url"], timeout=timeout, headers=_HEADERS, source=_SOURCE)
    parser = _Page()
    parser.feed(body)
    if parser.content_count > 1 or parser.content_depth is not None:
        raise SourceError(_SOURCE, "研报摘要结构无效")
    marker = re.search(r"\bvar\s+zwinfo\s*=\s*", body)
    if marker is None:
        raise SourceError(_SOURCE, "研报详情缺少正式身份")
    try:
        metadata, _ = json.JSONDecoder().raw_decode(body[marker.end():])
    except ValueError as exc:
        raise SourceError(_SOURCE, "研报详情身份数据损坏") from exc
    if not isinstance(metadata, dict) or metadata.get("info_code") != candidate["info_code"]:
        raise SourceError(_SOURCE, "研报详情身份与目录或搜索记录不一致")
    identities = re.findall(r"\bvar\s+_us_zixun_Id\s*=\s*['\"]([^'\"]+)['\"]", body)
    if any(value != candidate["info_code"] for value in identities):
        raise SourceError(_SOURCE, "研报详情身份与目录或搜索记录不一致")
    item = dict(candidate)
    item["title"] = legacy._text("".join(parser.title_parts), "标题") or legacy._text(metadata.get("notice_title"), "标题") or item["title"]
    for field, native in (("institute", "source_sample_name"), ("researcher", "researcher"),
                          ("institute_code", "company_code")):
        if metadata.get(native) not in (None, ""):
            item[field] = legacy._text(metadata[native], field)
    if metadata.get("notice_date") not in (None, ""):
        item["publication_date"] = legacy._date(metadata["notice_date"])
    item["content"] = to_markdown("".join(parser.parts), base_url=item["url"], source=_SOURCE) if parser.content_count else None
    item["content_type"] = "summary" if item["content"] else None
    item["pdf_urls"] = []
    for value in parser.pdf_urls:
        link = legacy._link(value, item["url"])
        if link is not None and link not in item["pdf_urls"]:
            item["pdf_urls"].append(link)
    if not item["content"] and not item["pdf_urls"]:
        raise SourceError(_SOURCE, "研报详情缺少可读摘要及原文链接，或来源限制访问")
    if metadata.get("attach_pages") not in (None, ""):
        value = metadata["attach_pages"]
        if isinstance(value, str) and re.fullmatch(r"[0-9]+", value, re.ASCII):
            value = int(value)
        item["pdf_pages"] = _integer(value, "PDF页数")
    if metadata.get("security") is not None:
        securities = metadata["security"]
        if not isinstance(securities, list):
            raise SourceError(_SOURCE, "研报相关证券格式无效")
        item["securities"] = []
        for security in securities:
            if not isinstance(security, dict):
                raise SourceError(_SOURCE, "研报相关证券格式无效")
            item["securities"].append({"code": legacy._text(security.get("stock"), "证券代码"),
                                        "name": legacy._text(security.get("short_name"), "证券名称"),
                                        "market_code": legacy._text(security.get("market_uni"), "证券市场标记")})
    return item


def em_fetch(limit=20, keyword=None, start_date=None, end_date=None, *, timeout):
    """读取至多 limit 条研报；错误整次失败，不返回不完整的成功列表。"""
    if type(limit) is not int or limit <= 0:
        raise ValueError("limit 必须是正整数")
    if keyword is not None:
        if not isinstance(keyword, str):
            raise ValueError("keyword 必须是字符串或 None")
        try:
            keyword.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("keyword 必须是有效 Unicode 字符串") from exc
        if keyword.strip() and any(ord(char) < 32 or ord(char) == 127 for char in keyword):
            raise ValueError("keyword 不能含控制字符")
        keyword = keyword.strip() or None
    start = parse_date_parameter(start_date, "start_date").isoformat() if start_date is not None else None
    end = parse_date_parameter(end_date, "end_date").isoformat() if end_date is not None else None
    if start and end and start > end:
        raise ValueError("start_date 不能晚于 end_date")
    seconds = validate_timeout(timeout)
    seen, details, positions, candidates = set(), {}, {}, {}
    cursor, stagnant = 1, 0

    def eligible(row):
        day = row["publication_date"]
        return not ((start and (day is None or day < start)) or (end and (day is None or day > end)))

    def business_key(row):
        return (("business", row["title"], row["institute"], row["publication_date"])
                if row["title"] and row["institute"] and row["publication_date"]
                else ("id", row["info_code"]))

    def quality(row):
        return (row["publication_date"] or "", int(row["info_code"] in details),
                bool(row["content"]) + bool(row["pdf_urls"]))

    def groups():
        grouped = {}
        for identity, original in candidates.items():
            row = details.get(identity, original)
            if identity in details and not eligible(row):
                continue
            grouped.setdefault(business_key(row), []).append(row)
        ordered = []
        for key, members in grouped.items():
            representative = max(members, key=quality)
            ordered.append((key, members, representative))
        ordered.sort(key=lambda group: (group[2]["publication_date"] is None,
                     -int(group[2]["publication_date"].replace("-", "")) if group[2]["publication_date"] else 0,
                     positions[group[2]["info_code"]]))
        return ordered

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="finchx-em-reports") as executor:
        while cursor is not None:
            if keyword:
                rows, next_cursor = _search_page(keyword, cursor, timeout=seconds)
            else:
                rows, next_cursor = _catalog_page(cursor, start, end, timeout=seconds)
            if next_cursor is not None and (type(next_cursor) is not int or next_cursor <= cursor):
                raise SourceError(_SOURCE, "研报分页游标未推进，来源未完成")
            fresh = False
            for row in rows:
                identity = row["info_code"]
                if identity not in seen:
                    fresh = True
                    positions[identity] = len(positions)
                seen.add(identity)
                if eligible(row) or row["publication_date"] is None:
                    candidates[identity] = row
            stagnant = 0 if fresh else stagnant + 1
            if next_cursor is not None and stagnant >= 3:
                raise SourceError(_SOURCE, "研报分页持续停滞，来源未完成")
            # 已选业务组内的副本须全部确认；详情改标题或日期后重新分组补位。
            required = set()
            while True:
                selected = groups()[:limit]
                for _, members, _ in selected:
                    required.update(row["info_code"] for row in members if row["info_code"] not in details)
                pending = sorted((identity for identity in required if identity not in details), key=positions.__getitem__)
                if not pending:
                    break
                batch = pending[:4]
                jobs = [executor.submit(_detail, candidates[identity], timeout=seconds) for identity in batch]
                for identity, job in zip(batch, jobs):
                    details[identity] = job.result()
            selected = groups()[:limit]
            if len(selected) >= limit or next_cursor is None:
                return [{field: group[2][field] for field in _FIELDS} for group in selected]
            cursor = next_cursor
