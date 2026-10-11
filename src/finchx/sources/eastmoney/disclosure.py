"""东方财富公告目录与现成多页正文；不读取附件文件或保存结果。"""

from datetime import date, datetime, time
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from finchx._common.convert import parse_date_time_string, resolve_code, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_json
from finchx._common.news import BEIJING_TZ, validate_limit

_LIST_ENDPOINT = "https://np-anotice-stock.eastmoney.com/api/security/ann"
_DETAIL_ENDPOINT = "https://np-cnotice-stock.eastmoney.com/api/content/ann"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://data.eastmoney.com/"}
_PAGE_SIZE = 100
_MAX_REQUESTS = 1000
_MAX_DETAIL_PAGES = 1000
_AN = r"AN[0-9]{12,24}"
_SOURCE_TIME = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})(?::([0-9]{1,6}))?")
_CATEGORY_NODES = {
    "重大事项": (5, None), "财务报告": (1, None), "融资公告": (2, None),
    "风险提示": (3, None), "资产重组": (6, None), "信息变更": (4, None), "持股变动": (7, None),
    "重大合同": (5, 7), "投资相关": (5, 8), "股权激励": (5, 9),
    "定期报告": (1, 1), "利润分配": (1, 13), "业绩预告": (1, 5), "业绩快报": (1, 6),
    "增发": (2, 3), "新股发行": (2, 2), "配股": (2, 4),
    "要约收购": (6, 10), "吸收合并": (6, 11), "回购": (6, 12),
}


def _fail(reason):
    raise SourceError("eastmoney", reason)


def _text(value, field, *, required=False):
    if value is None or isinstance(value, str) and not value.strip():
        if required:
            _fail(f"{field} 缺少必要文字")
        return None
    if not isinstance(value, str):
        _fail(f"{field} 必须是文字或空值")
    return value


def _integer(value, field, *, minimum=0):
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        result = int(value)
    else:
        _fail(f"{field} 必须是非布尔整数")
    if result < minimum:
        _fail(f"{field} 低于合法范围")
    return result


def _source_time(value, field):
    value = _text(value, field)
    if value is None:
        return None
    match = _SOURCE_TIME.fullmatch(value)
    if not match:
        _fail(f"{field} 不是已核来源时刻格式")
    try:
        stamp = datetime.strptime(match[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BEIJING_TZ)
    except ValueError as exc:
        raise SourceError("eastmoney", f"{field} 日期时刻无效") from exc
    # 来源的冒号小数格式转换为ISO小数，保留来源实际位数（包括000）。
    return stamp.isoformat() if match[2] is None else stamp.strftime("%Y-%m-%dT%H:%M:%S") + "." + match[2] + "+08:00"


def _notice_date(value):
    value = _text(value, "notice_date")
    if value is None:
        return None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        candidate = value
    elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", value):
        _source_time(value, "notice_date")
        candidate = value[:10]
    else:
        _fail("notice_date 不是已核来源日期格式")
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError as exc:
        raise SourceError("eastmoney", "notice_date 日期无效") from exc


def _window(since, until):
    def bound(value, name, upper):
        if value is None:
            return None
        if isinstance(value, datetime):
            raise ValueError(f"{name} 不接受 datetime 对象")
        parsed = value if isinstance(value, date) else parse_date_time_string(value, name)
        if isinstance(parsed, datetime):
            return parsed.replace(tzinfo=BEIJING_TZ, microsecond=999999 if upper else 0)
        return datetime.combine(parsed, time.max if upper else time.min, BEIJING_TZ)
    lower, upper = bound(since, "since", False), bound(until, "until", True)
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("since 不得晚于 until")
    return lower, upper


def _matches(row, lower, upper):
    if lower is None and upper is None:
        return True
    if row["source_time"] is not None:
        stamp = datetime.fromisoformat(row["source_time"])
        return (lower is None or stamp >= lower) and (upper is None or stamp <= upper)
    day = row["notice_date"]
    if day is None:
        _fail("公告缺少来源时刻与公告日期，无法确认时间筛选范围")
    return (lower is None or day >= lower.date().isoformat()) and (upper is None or day <= upper.date().isoformat())


def _categories(categories):
    if categories is None:
        return [None]
    if not isinstance(categories, (list, tuple)) or not categories:
        raise ValueError("categories 必须是非空中文分类列表或元组，或 None")
    if any(not isinstance(label, str) or label not in _CATEGORY_NODES for label in categories):
        raise ValueError("categories 包含未支持的东方财富公告分类")
    labels = list(dict.fromkeys(categories))
    parents = {_CATEGORY_NODES[label][0] for label in labels if _CATEGORY_NODES[label][1] is None}
    return [_CATEGORY_NODES[label] for label in labels
            if _CATEGORY_NODES[label][1] is None or _CATEGORY_NODES[label][0] not in parents]


def _securities(values, *, detail=False):
    if values is None:
        return None
    if not isinstance(values, list):
        _fail("公告关联证券必须是数组或空值")
    result, seen = [], set()
    code_key, market_key = ("stock", "market_uni") if detail else ("stock_code", "market_code")
    for raw in values:
        if not isinstance(raw, dict):
            _fail("公告关联证券行必须是对象")
        code = _text(raw.get(code_key), code_key, required=True)
        market = _text(raw.get(market_key), market_key, required=True)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", code) or not re.fullmatch(r"[0-9]+", market):
            _fail("公告关联证券身份无效")
        if market in {"0", "1"} and not re.fullmatch(r"[0-9]{6}", code):
            _fail("沪深关联证券代码必须是六位ASCII数字")
        identity = market, code
        if identity in seen:
            _fail("公告关联证券身份重复")
        seen.add(identity)
        result.append({"code": code, "market": market, "name": _text(raw.get("short_name"), "short_name")})
    return result


def _list_row(raw, code, market):
    if not isinstance(raw, dict):
        _fail("公告目录行必须是对象")
    identity = raw.get("art_code")
    if not isinstance(identity, str) or not re.fullmatch(_AN, identity):
        _fail("公告目录 art_code 身份无效")
    securities = _securities(raw.get("codes"))
    if securities and not any(s["code"] == code and s["market"] == market for s in securities):
        _fail("公告目录关联证券与查询code冲突")
    columns = raw.get("columns")
    if columns is not None:
        if not isinstance(columns, list):
            _fail("公告分类必须是数组或空值")
        normalized = []
        for column in columns:
            if not isinstance(column, dict):
                _fail("公告分类行必须是对象")
            normalized.append({"code": _text(column.get("column_code"), "column_code"),
                               "name": _text(column.get("column_name"), "column_name")})
        columns = normalized
    title_ch, title = _text(raw.get("title_ch"), "title_ch"), _text(raw.get("title"), "title")
    return {"id": identity, "title": title_ch if title_ch is not None else title,
            "notice_date": _notice_date(raw.get("notice_date")),
            "source_time": _source_time(raw.get("eiTime"), "eiTime"),
            "url": f"https://data.eastmoney.com/notices/detail/{code}/{identity}.html",
            "categories": columns, "related_securities": securities}


def _data(payload):
    if not isinstance(payload, dict):
        _fail("公告响应必须是对象")
    success = payload.get("success")
    if not (type(success) is int and success == 1 or type(success) is str and success == "1") or payload.get("error") not in (None, ""):
        _fail("公告来源未表示成功")
    if not isinstance(payload.get("data"), dict):
        _fail("公告响应缺少必要data对象")
    return payload["data"]


def _branch(code, market, node, seconds, budget, *, limit=None, lower=None, upper=None):
    rows, total = {}, None
    for _ in range(3):
        page, seen_pages, stalled = 1, set(), 0
        while True:
            budget[0] += 1
            if budget[0] > _MAX_REQUESTS:
                _fail("公告目录达到读取防护预算，尚未确认完成")
            params = {"page_size": _PAGE_SIZE, "page_index": page, "market_code": market,
                      "stock_list": code, "client_source": "web"}
            if node is not None:
                params["f_node"] = node[0]
                if node[1] is not None:
                    params["s_node"] = node[1]
            data = _data(get_json(_LIST_ENDPOINT + "?" + urlencode(params), timeout=seconds, headers=_HEADERS, source="eastmoney"))
            if _integer(data.get("page_index"), "page_index", minimum=1) != page or _integer(data.get("page_size"), "page_size", minimum=1) != _PAGE_SIZE:
                _fail("公告目录响应分页与请求不一致")
            count = _integer(data.get("total_hits"), "total_hits")
            if total is not None and count != total:
                _fail("公告目录 total_hits 在分页期间变化")
            total = count
            source_rows = data.get("list")
            expected = min(_PAGE_SIZE, max(0, total - (page - 1) * _PAGE_SIZE))
            if not isinstance(source_rows, list) or len(source_rows) != expected:
                _fail("公告目录页长度与声明窗口不一致")
            parsed = [_list_row(raw, code, market) for raw in source_rows]
            ids = [row["id"] for row in parsed]
            if len(set(ids)) != len(ids):
                _fail("公告目录同页身份重复")
            batch = frozenset(ids)
            if ids and batch in seen_pages:
                _fail("公告目录重复整页，分页停滞")
            seen_pages.add(batch)
            fresh = set(ids) - rows.keys()
            stalled = 0 if fresh else stalled + 1
            for row in parsed:
                rows[row["id"]] = row
            if len(rows) > total:
                _fail("公告目录唯一数超过声明total_hits")
            if limit is not None:
                matched = [row for row in rows.values() if _matches(row, lower, upper)]
                if len(matched) >= limit:
                    return matched[:limit]
            if page * _PAGE_SIZE >= total:
                if len(rows) == total:
                    return list(rows.values()) if limit is None else matched
                break
            if stalled >= 3:
                _fail("公告目录分页持续无新身份")
            page += 1
    _fail("公告目录三轮补取后唯一数仍不足声明total_hits")



def _compatible_securities(left, right):
    if left is None or right is None:
        return True
    first = {(row["market"], row["code"]): row["name"] for row in left}
    second = {(row["market"], row["code"]): row["name"] for row in right}
    return first.keys() == second.keys() and all(
        first[key] is None or second[key] is None or first[key] == second[key] for key in first
    )


def _compatible_value(left, right, field):
    if left is None or right is None:
        return True
    if field == "related_securities":
        return _compatible_securities(left, right)
    if field == "source_time":
        return datetime.fromisoformat(left) == datetime.fromisoformat(right)
    return left == right


def _merge_detail_metadata(first, current):
    for key, value in current.items():
        if not _compatible_value(first[key], value, key):
            _fail("公告详情各页必要业务字段不一致")
        if first[key] is None:
            first[key] = value
        elif key == "related_securities" and value is not None:
            names = {(row["market"], row["code"]): row["name"] for row in value}
            for row in first[key]:
                if row["name"] is None:
                    row["name"] = names[(row["market"], row["code"])]


def em_list(code: str, limit: int = 20, since=None, until=None, categories=None, *, timeout: float) -> list[dict]:
    """单分类按来源顺序取至目标；多独立分类完整合并后按公告日期排序。"""
    symbol = resolve_code(code)
    maximum = validate_limit(limit)
    lower, upper = _window(since, until)
    nodes, seconds = _categories(categories), validate_timeout(timeout)
    market, budget = ("1" if symbol.startswith("sh") else "0"), [0]
    if len(nodes) == 1:
        return _branch(code, market, nodes[0], seconds, budget, limit=maximum, lower=lower, upper=upper)
    merged = {}
    for node in nodes:
        for row in _branch(code, market, node, seconds, budget):
            previous = merged.get(row["id"])
            if previous is not None and any(not _compatible_value(previous[key], row[key], key) for key in ("title", "notice_date", "related_securities")):
                _fail("不同分类的同公告业务身份冲突")
            merged[row["id"]] = row
    ordered = sorted(merged.values(), key=lambda row: (row["notice_date"] is not None, row["notice_date"] or "", row["id"]), reverse=True)
    return [row for row in ordered if _matches(row, lower, upper)][:maximum]


def _url_parts(url, *, source_attachment=False):
    if not isinstance(url, str) or not url or "\\" in url or any(c.isspace() or ord(c) < 33 or 127 <= ord(c) <= 159 for c in url):
        raise ValueError("url 必须是合法的公告HTTP(S)链接")
    try:
        parts = urlsplit(url)
        if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
                or parts.password is not None or not source_attachment and (parts.port is not None or "#" in url)):
            raise ValueError
        if source_attachment:
            parts.port  # Validate a provided port without rejecting legal source links.
        if parts.netloc.endswith(":"):
            raise ValueError
    except ValueError as exc:
        raise ValueError("公告url的主机、认证信息、端口或片段无效") from exc
    return parts


def _input_url(url):
    parts = _url_parts(url)
    if parts.hostname == "data.eastmoney.com" and "?" not in url:
        match = re.fullmatch(r"/notices/detail/(?:([0-9]{6})/)?(" + _AN + r")\.html", parts.path)
        if match:
            return match[2], match[1], None
    if parts.hostname == "np-info.eastmoney.com" and parts.path == "/wap/notice/":
        query = parse_qs(parts.query, keep_blank_values=True)
        if re.fullmatch(r"infocode=" + _AN, parts.query) and list(query) == ["infocode"]:
            return query["infocode"][0], None, None
    if parts.hostname == "pdf.dfcfw.com":
        match = re.fullmatch(r"/pdf/(H2|H22)_(" + _AN + r")_([1-9][0-9]*)\.pdf", parts.path)
        if match and ("?" not in url or re.fullmatch(r"[0-9]+\.pdf", parts.query)):
            return match[2], None, parts.path
    raise ValueError("url 不是已核官方公告详情、移动公告或H2/H22公告附件链接")


def _attachment_url(value, field, *, required=False):
    value = _text(value, field, required=required)
    if value is None:
        return None
    try:
        _url_parts(value, source_attachment=True)
    except ValueError as exc:
        raise SourceError("eastmoney", f"{field} 不是合法来源附件URL") from exc
    return value


def _attachment_type(value):
    value = _text(value, "attach_type")
    if value is None:
        return None
    if not re.fullmatch(r"[0-9]+", value):
        _fail("attach_type 不是合法来源类别标记")
    return "pdf" if value == "0" else None


def _size(value):
    return None if value is None or value == "" else _integer(value, "attach_size")


def _merge_attachment(result, url, size, kind):
    if url is None:
        return
    previous = result.get(url)
    if previous is None:
        result[url] = {"url": url, "size_kb": size, "type": kind}
    else:
        for key, value in (("size_kb", size), ("type", kind)):
            if previous[key] is not None and value is not None and previous[key] != value:
                _fail("同附件URL的来源大小或类别冲突")
            if value is not None:
                previous[key] = value


def _attachments(data, result):
    values = data.get("attach_list")
    if values is not None and not isinstance(values, list):
        _fail("attach_list 必须是数组或空值")
    for raw in values or []:
        if not isinstance(raw, dict):
            _fail("附件行必须是对象")
        _merge_attachment(result, _attachment_url(raw.get("attach_url"), "attach_url", required=True),
                          _size(raw.get("attach_size")), _attachment_type(raw.get("attach_type")))
    kind = _attachment_type(data.get("attach_type"))
    _merge_attachment(result, _attachment_url(data.get("attach_url"), "attach_url"), _size(data.get("attach_size")), kind)
    # web地址不同只能确认来源PDF原文用途，不能串配其他文件的大小。
    _merge_attachment(result, _attachment_url(data.get("attach_url_web"), "attach_url_web"), None, kind)


def em_get(url: str, *, timeout: float) -> dict:
    """按同一公告AN读取来源全部正文页，不读取PDF文件或目录。"""
    identity, code, pdf_path = _input_url(url)
    seconds = validate_timeout(timeout)
    first, count, texts, seen_texts, attachments = None, None, [], set(), {}
    array_present = False
    for page in range(1, _MAX_DETAIL_PAGES + 1):
        params = {"art_code": identity, "client_source": "web", "page_index": page}
        data = _data(get_json(_DETAIL_ENDPOINT + "?" + urlencode(params), timeout=seconds, headers=_HEADERS, source="eastmoney"))
        if data.get("art_code") != identity:
            _fail("公告详情art_code与输入身份冲突")
        pages = _integer(data.get("page_size"), "page_size", minimum=1)
        if pages > _MAX_DETAIL_PAGES or count is not None and count != pages:
            _fail("公告详情页数非法或在分页期间变化")
        count = pages
        metadata = {"title": _text(data.get("notice_title"), "notice_title"),
                    "notice_date": _notice_date(data.get("notice_date")),
                    "source_time": _source_time(data.get("eitime"), "eitime"),
                    "related_securities": _securities(data.get("security"), detail=True)}
        if first is None:
            first = metadata
        else:
            _merge_detail_metadata(first, metadata)
        value = _text(data.get("notice_content"), "notice_content")
        text = None if value is None else value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if text:
            if text in seen_texts:
                _fail("公告详情重复正文页")
            seen_texts.add(text)
        texts.append(text)
        array_present = array_present or data.get("attach_list") is not None
        _attachments(data, attachments)
        if page >= count:
            break
    else:
        _fail("公告详情达到正文分页防护预算")
    if any(texts) and not all(texts):
        _fail("公告详情部分正文页缺失，不能返回不完整正文")
    if not any(texts) and not attachments:
        _fail("公告详情既无正文也无有效附件")
    if code is not None and not any(s["code"] == code for s in first["related_securities"] or []):
        _fail("公告详情关联证券与URL代码冲突")
    if pdf_path is not None and not any(urlsplit(a["url"]).hostname == "pdf.dfcfw.com" and urlsplit(a["url"]).path == pdf_path for a in attachments.values()):
        _fail("输入PDF路径、文件族或序号不属于该公告真实附件")
    return {"title": first["title"], "notice_date": first["notice_date"], "source_time": first["source_time"],
            "content": "\n\n".join(texts) if all(texts) else None,
            "related_securities": first["related_securities"],
            "attachments": list(attachments.values()) if attachments or array_present else None}
