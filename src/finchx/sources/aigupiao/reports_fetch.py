"""聚合研报使用的爱股票原生关键词检索。"""

from datetime import date
from html import escape
import re

from finchx._common.errors import SourceError
from finchx._common.report_text import to_markdown
from finchx.sources.aigupiao import reports as old


def search_page(keyword: str, cursor: int, *, timeout: float) -> tuple[list[dict], int | None]:
    payload = old.post_form_json(
        old._LIST, data={"before": cursor, "kind": "all", "u_id": 0,
                         "symbol": "", "limit": 20, "keyword": keyword},
        timeout=timeout, headers=old._HEADERS, source="aigupiao",
    )
    old._success(payload)
    items = payload.get("data")
    if not isinstance(items, list):
        raise SourceError("aigupiao", "研报检索条目不是数组")
    rows, positions = [], []
    for item in items:
        if not isinstance(item, dict):
            raise SourceError("aigupiao", "研报检索条目必须是对象")
        identity = old._identity(item.get("inv_id"), "inv_id", positive=True)
        position = old._integer(item.get("sort_time"), "sort_time")
        row = {"title": old._text(item.get("title"), "title"),
               "institute": old._text(item.get("institute"), "institute"),
               "publication_date_text": old._publication_text(item.get("pub_time")),
               "url": old._DETAIL + identity}
        publication = row["publication_date_text"]
        if publication and len(publication) in {8, 10}:
            publication = date.fromisoformat(publication).isoformat()
        else:
            publication = None
        rows.append({"source": "aigupiao", "title": row["title"], "institute": row["institute"],
                     "publication_date": publication, "url": row["url"], "content": None,
                     "content_type": None, "pdf_urls": None, "_id": identity,
                     "_date_text": row["publication_date_text"]})
        positions.append(position)
    if not rows:
        return [], None
    next_cursor = min(positions)
    return rows, next_cursor


def _html(node, excluded: set[int]) -> str:
    if isinstance(node, str):
        return escape(node)
    if id(node) in excluded:
        return ""
    attrs = "".join(f' {key}="{escape(value, quote=True)}"' for key, value in node.attrs.items())
    children = "".join(_html(child, excluded) for child in node.children)
    return f"<{node.tag}{attrs}>{children}</{node.tag}>"


def get_detail(candidate: dict, *, timeout: float) -> dict:
    url = candidate["url"]
    identity = old._url(url)
    page = old.get_text(url, timeout=timeout, headers={**old._HEADERS, "Accept": "text/html,application/xhtml+xml"},
                        source="aigupiao", follow_redirects=False)
    parser = old._HTML()
    parser.feed(page)
    parser.close()
    summaries = [node for node in old._walk(parser.root) if "text01" in node.attrs.get("class", "").split()]
    titles = [node for summary in summaries for node in old._walk(summary) if node.tag in {"h1", "h2"}]
    excluded = {id(node) for node in titles[:1]}
    for summary in summaries:
        for node in old._walk(summary):
            if node.tag in {"span", "p"} and re.match(
                r"^(?:研究机构|机构|研究员|分析师|发布时间|发布日期|日期)\s*[:：]", old._plain(node)
            ):
                excluded.add(id(node))
    content = to_markdown("".join(_html(node, excluded) for node in summaries), base_url=url, source="aigupiao")
    try:
        detail = old._detail(page, url=url, identity=identity)
    except SourceError as exc:
        if exc.reason != "研报页面没有可读摘要或 PDF 链接" or not content:
            raise
        # 原接口只认纯文字；新接口保留已核摘要区的纯图正文。
        detail = {"title": None, "institute": None, "publication_date": None, "pdf_urls": []}
        titles = [node for summary in summaries for node in old._walk(summary) if node.tag in {"h1", "h2"}]
        if titles:
            detail["title"] = old._plain(titles[0]) or None
        labels = "研究机构|机构|研究员|分析师|发布时间|发布日期|日期"
        mapping = {"研究机构": "institute", "机构": "institute", "研究员": "researcher", "分析师": "researcher",
                   "发布时间": "publication_date", "发布日期": "publication_date", "日期": "publication_date"}
        for summary in summaries:
            for node in old._walk(summary):
                text = old._plain(node) if node.tag in {"span", "p"} else ""
                if re.match(rf"^(?:{labels})\s*[:：]", text):
                    for match in re.finditer(rf"(?:^|\s)({labels})\s*[:：]\s*(.*?)(?=\s+(?:{labels})\s*[:：]|\n|$)", text):
                        detail[mapping[match[1]]] = match[2].strip() or None
    result = dict(candidate)
    for key in ("title", "institute", "publication_date"):
        if detail[key] is not None:
            result[key] = detail[key]
    result["_detail_fields"] = tuple(key for key in ("title", "institute", "publication_date") if detail[key] is not None)
    result.update(content=content, content_type="summary" if content else None,
                  pdf_urls=detail["pdf_urls"], _detail_read=True)
    return result
