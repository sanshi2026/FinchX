"""爱股票目录与正式摘要的单来源批量读取。"""

from datetime import date
from concurrent.futures import ThreadPoolExecutor

from finchx._common.convert import parse_date_parameter, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.news import validate_limit
from finchx.sources.aigupiao import reports as old

_FIELDS = ("url", "title", "kind", "ref_code", "name", "institute", "rating",
           "publication_date_text", "recorded_at", "symbol", "theme_id",
           "publication_date", "researcher", "summary", "pdf_urls")
_BATCH = 50
# 仅在已实测可接受的批量范围内恢复同秒边界，不把它称为来源上限。
_RECOVERY_LIMITS = (100, 200, 1000)


def _page(before, size, kind, keyword, industry, timeout):
    payload = old.post_form_json(
        old._LIST, data={"before": before, "kind": kind, "u_id": 0,
                         "symbol": industry or "", "limit": size, "keyword": keyword or ""},
        timeout=timeout, headers=old._HEADERS, source="aigupiao",
    )
    old._success(payload)
    items = payload.get("data")
    if not isinstance(items, list) or len(items) > size:
        raise SourceError("aigupiao", "研报目录条目不是请求范围内的完整数组")
    rows, seen, previous = [], set(), None
    # 复用已有业务字段校验；单次放大请求不受旧目录的100行防护限制。
    for start in range(0, max(1, len(items)), 100):
        part = dict(payload, data=items[start:start + 100])
        for identity, position, row in old._page(part, before=before, kind=kind, industry=industry):
            if identity in seen or previous is not None and position > previous:
                raise SourceError("aigupiao", "研报目录身份重复或时间顺序无效")
            seen.add(identity)
            previous = position
            rows.append((identity, position, row))
    total = old._integer(payload.get("total"), "total")
    last_page = old._integer(payload.get("last_page"), "last_page")
    if total < len(rows) or not rows and total:
        raise SourceError("aigupiao", "研报目录条目与本次剩余数量相互矛盾")
    return rows, total, last_page


def _pages(size, kind, keyword, industry, timeout):
    rows, total, last_page = _page(0, size, kind, keyword, industry, timeout)
    if not rows:
        return
    yield rows
    while True:
        if total == len(rows) and last_page == total // size:
            return
        boundary = rows[-1][1]
        if boundary >= old._MAX_BEFORE:
            raise SourceError("aigupiao", "研报同秒边界无法继续确认")
        known = {identity for identity, position, _ in rows if position == boundary}
        sizes = sorted(value for value in {size, _BATCH, *_RECOVERY_LIMITS}
                       if value >= max(size, len(known)))
        for request_size in sizes:
            overlap, total, last_page = _page(boundary + 1, request_size, kind, keyword, industry, timeout)
            found = {identity for identity, position, _ in overlap if position == boundary}
            exhausted = total == len(overlap) and last_page == total // request_size
            crossed = any(position < boundary for _, position, _ in overlap)
            if not known <= found and (exhausted or crossed):
                raise SourceError("aigupiao", "研报同秒重叠页未保留已确认身份")
            known.update(found)
            # 有限请求可在当前秒已取得足够报告后结束；只有继续越过该秒才需确认完整。
            yield overlap
            if exhausted:
                return
            if crossed:
                rows, size = overlap, request_size
                break
        else:
            raise SourceError("aigupiao", "研报同秒分页无法确认完整，未跳过边界")


def _key(identity, row):
    if row["title"] and row["institute"] and row["publication_date"]:
        return ("report", row["title"], row["institute"], row["publication_date"])
    return ("identity", identity)


def _quality(row, position):
    day = row["publication_date"]
    return (day is None, -int(day.replace("-", "")) if day else 0,
            -(bool(row["summary"]) + bool(row["pdf_urls"])), position)


def agp_fetch(limit: int = 20, kind: str = "all", keyword: str | None = None,
              industry: str | None = None, *, start_date: str | None = None,
              end_date: str | None = None, timeout: float) -> list[dict]:
    """读取目录及每条正式摘要；必要请求失败不返回不完整列表。"""
    target = validate_limit(limit)
    seconds = validate_timeout(timeout)
    if not isinstance(kind, str) or kind not in {"all", "stock", "industry"}:
        raise ValueError("kind 必须是 all、stock 或 industry")
    keyword, industry = old._filter(keyword, "keyword"), old._filter(industry, "industry")
    if kind == "stock" and industry is not None:
        raise ValueError("industry 不能与 kind='stock' 同用")
    start = parse_date_parameter(start_date, "start_date").isoformat() if start_date is not None else None
    end = parse_date_parameter(end_date, "end_date").isoformat() if end_date is not None else None
    if start and end and start > end:
        raise ValueError("start_date 不能晚于 end_date")
    if industry is not None:
        industry = old._industry(industry, timeout=seconds)
        kind = "industry"
    catalogs, details, positions = {}, {}, {}

    def merge(identity):
        candidate = catalogs[identity]
        row = dict(candidate)
        text = candidate["publication_date_text"]
        normalized = f"{text[:4]}-{text[4:6]}-{text[6:]}" if text and len(text) == 8 else text
        row.update(publication_date=date.fromisoformat(normalized).isoformat()
                   if text and len(text) in {8, 10} else None,
                   researcher=None, summary=None, pdf_urls=None)
        if identity in details:
            detail = details[identity]
            for key in ("researcher", "summary", "pdf_urls"):
                row[key] = detail[key]
            for key in ("title", "institute", "publication_date"):
                if detail[key]:
                    row[key] = detail[key]
        return row

    def groups():
        grouped = {}
        for identity in catalogs:
            row = merge(identity)
            day = row["publication_date"]
            if identity in details and ((start and (day is None or day < start))
                                        or (end and (day is None or day > end))):
                continue
            grouped.setdefault(_key(identity, row), []).append((identity, row))
        selected = []
        for members in grouped.values():
            representative = min(members, key=lambda item: _quality(item[1], positions[item[0]]))
            selected.append((members, representative))
        selected.sort(key=lambda group: _quality(group[1][1], positions[group[1][0]]))
        return selected[:target]

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="finchx-agp-reports") as executor:
        for rows in _pages(min(20, target), kind, keyword, industry, seconds):
            for identity, _, candidate in rows:
                if identity not in positions:
                    positions[identity] = len(positions)
                catalogs[identity] = dict(candidate)
            # 已选组在本页内的副本都必须确认；正式详情改变分组或日期后重新补位。
            required = set()
            while True:
                selected = groups()
                for members, _ in selected:
                    required.update(identity for identity, _ in members if identity not in details)
                pending = sorted(required - details.keys(), key=positions.__getitem__)
                if not pending:
                    break
                batch = pending[:4]
                jobs = [executor.submit(old._get_detail, catalogs[identity]["url"], timeout=seconds)
                        for identity in batch]
                for identity, job in zip(batch, jobs):
                    details[identity] = job.result()
            selected = groups()
            if len(selected) >= target:
                return [{key: representative[1][key] for key in _FIELDS} for _, representative in selected]
    return [{key: representative[1][key] for key in _FIELDS} for _, representative in groups()]
