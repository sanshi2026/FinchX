"""当前官网原生股票筛选流程与动态业务列。"""

import math
import re

from finchx._common import http
from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError
from ._values import SOURCE, cookie_header, fail, json_object, limit_value, query_text, status, text

_STREAM = "https://www.iwencai.com/gateway/aime/stream-query"
_RENDER = "https://www.iwencai.com/gateway/render/encrypt/getData"
_SOURCE = "ths_iwencai_pc_xuangu"
_PAGE_SIZE = 50
_MAX_PAGES = 200
_TABLE = "jgyXuanguTable1"
_MARKETS = {17: "sh", 33: "sz", 151: "bj"}


def _request(url, data, headers, timeout, *, stream=False):
    failed = False
    try:
        method = http.post_text if stream else http.post_json
        result = method(url, data=data, headers=headers, timeout=timeout, source=SOURCE, follow_redirects=False)
    except SourceError:
        failed = True
    if failed:
        fail("选股请求失败或认证失效")
    return result


def _stream_table(body):
    """只接受已完成原生流中的完整股票表，截断流不能充当成功。"""
    if not isinstance(body, str):
        fail("选股流文本结构损坏")
    frames = re.split(r"\r?\n\r?\n", body)
    table = None
    completed = False
    for frame in frames:
        lines = [line[5:].strip() for line in frame.splitlines() if line.startswith("data:")]
        if not lines:
            continue
        value = "".join(lines)
        if value == "[DONE]":
            continue
        document = json_object(value)
        status(document, required=False)
        if "extra" in document:
            status(json_object(document["extra"]), required=False)
        if completed:
            fail("选股完成标记后仍有业务响应")
        if "is_last" in document and not isinstance(document["is_last"], bool):
            fail("选股完成标记类型无效")
        section = document.get("section")
        if section is not None:
            section = json_object(section)
            if section.get("show_type") == "result_page":
                if "is_last" in section and not isinstance(section["is_last"], bool):
                    fail("表格完成标记类型无效")
                # 部分渲染块尚未完成时不解析业务表；最终块仍须完整。
                if section.get("is_last") is not False:
                    candidate = _component(section.get("result_page"), required=False)
                    if candidate is not None:
                        table = candidate
        if document.get("is_last") is True:
            completed = True
    if not completed or table is None:
        fail("选股未返回完整最终股票表")
    return table


def _component(answer, *, required=True):
    answer = json_object(answer)
    components = answer.get("components")
    if not isinstance(components, list):
        fail("来源表格组件数组损坏")
    matches = []
    for component in components:
        if not isinstance(component, dict):
            fail("来源组件对象损坏")
        if component.get("show_type") == _TABLE or component.get("chart_type") == _TABLE:
            matches.append(component)
    if len(matches) > 1:
        fail("股票表格身份不唯一")
    if not matches:
        if required:
            fail("来源没有已支持的股票表格")
        return None
    return matches[0]


def _native(value):
    """保来源业务类型和精度，只拒绝不能表示的 JSON 值。"""
    if isinstance(value, float) and not math.isfinite(value):
        fail("动态指标不是有限值")
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError:
                fail("动态指标编码无效")
        return value
    if isinstance(value, list):
        return [_native(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _native(item) for key, item in value.items()}
    fail("动态指标业务结构损坏")


def _column_title(column, info):
    key = column["key"]
    definition = info.get(key, {})
    definition = json_object(definition)
    index_meta = json_object(definition["index_meta"]) if definition.get("index_meta") is not None else {}
    label = text(index_meta.get("label"))
    index_number = text(index_meta.get("index_number"))
    title = label or key
    if index_number:
        title = index_number if column.get("source") == "calc" else title + " " + index_number
    unit = text(column.get("unit"))
    if unit and f"({unit})" not in title and f"（{unit}）" not in title:
        title += f"({unit})"
    # 官方 schema 中 key 的日期和 timestamp 是独立业务标识，均不从问句猜。
    dates = re.findall(r"\[[^\[\]]+\]", key)
    for value in dates:
        if value not in title:
            title += value
    timestamp = column.get("timestamp")
    if timestamp not in (None, ""):
        if isinstance(timestamp, bool) or not isinstance(timestamp, (str, int)):
            fail("来源列日期标识类型无效")
        suffix = f"[{timestamp}]"
        if suffix not in title:
            title += suffix
    if title in ("code", "exchange", "name"):
        fail("动态业务列与固定身份字段冲突")
    return title


def _column_role(key, labels):
    roles = set(labels).intersection({"code", "name", "market"})
    # 官网 JGY 回调同时读取展示代码 股票代码、行情代码 code 和 market_code。
    # 这些精确源字段属于身份；不按包含“代码”或显示标题猜测业务列。
    fixed_role = {"股票代码": "code", "code": "code", "股票简称": "name", "market_code": "market"}.get(key)
    if fixed_role:
        roles.add(fixed_role)
    if len(roles) > 1:
        fail("来源股票身份列角色冲突")
    return next(iter(roles), None)


def _identity(raw, code_keys, market_keys):
    codes, exchanges = set(), set()
    # code 即使未列在 columns 中，也是官网使用的行情身份，存在时须核对。
    for key in dict.fromkeys([*code_keys, "code"]):
        if raw.get(key) is None:
            continue
        identifier = text(raw[key], required=True)
        match = re.fullmatch(r"([0-9]{6})(?:\.(SH|SZ|BJ))?", identifier)
        if match is None:
            fail("股票代码不是来源明确的六位 ASCII 身份")
        code, suffix = match.groups()
        codes.add(code)
        if suffix:
            exchanges.add(suffix.lower())
    if len(codes) != 1:
        fail("来源股票代码缺失或身份冲突")
    for key in dict.fromkeys([*market_keys, "market_code"]):
        marker = raw.get(key)
        if marker is None:
            continue
        if isinstance(marker, str) and re.fullmatch(r"[0-9]+", marker):
            marker = int(marker)
        if type(marker) is not int or marker not in _MARKETS:
            fail("来源股票市场标记无效")
        exchanges.add(_MARKETS[marker])
    if len(exchanges) != 1:
        fail("来源股票交易所缺失或身份冲突")
    return codes.pop(), exchanges.pop()


def _name(raw, keys):
    names = {value for key in keys if (value := text(raw.get(key))) is not None}
    if len(names) > 1:
        fail("来源股票名称身份冲突")
    return names.pop() if names else None


def _page(component):
    data = json_object(component.get("data"))
    meta = json_object(data.get("meta"))
    extra = json_object(meta.get("extra"))
    if "query_type" in extra and extra["query_type"] != "stock":
        fail("返回表格不是股票筛选领域")
    if "row_count" not in extra:
        fail("来源表格声明总业务行数缺失")
    for name in ("row_count", "code_count"):
        if name in extra and (isinstance(extra[name], bool) or not isinstance(extra[name], int) or extra[name] < 0):
            fail("来源计数类型无效")
    columns, raw = data.get("columns"), data.get("datas")
    if not isinstance(columns, list) or not columns or not isinstance(raw, list):
        fail("来源股票表格必要结构损坏")
    if len(raw) > extra["row_count"]:
        fail("来源单页业务行数超过表格声明总数")
    info = extra.get("iwc_column_info", {})
    info = json_object(info)
    keys = set()
    code_keys, name_keys, market_keys = [], [], []
    business_columns = []
    titles = set()
    for column in columns:
        column = json_object(column)
        key = text(column.get("key"), required=True)
        if key in keys:
            fail("来源表格列重复")
        keys.add(key)
        label = text(column.get("label"))
        labels = label.split("||") if label else []
        role = _column_role(key, labels)
        if role == "code":
            code_keys.append(key)
        elif role == "name":
            name_keys.append(key)
        elif role == "market":
            market_keys.append(key)
        else:
            title = _column_title(column, info)
            if title in titles:
                fail("来源动态列业务名称冲突")
            titles.add(title)
            business_columns.append((key, title, column.get("type")))
    if not code_keys:
        fail("来源股票身份列缺失")
    rows, seen = [], set()
    for item in raw:
        item = json_object(item)
        code, exchange = _identity(item, code_keys, market_keys)
        identity = exchange, code
        if identity in seen:
            fail("同页股票身份重复")
        seen.add(identity)
        row = {"code": code, "exchange": exchange, "name": _name(item, name_keys)}
        for key, title, kind in business_columns:
            value = _native(item.get(key))
            # 只有明确数值 schema 才验证数值，不将中文列名猜成金额/比例。
            if kind in ("INT", "FLOAT", "DOUBLE", "NUMBER") and value is not None and value != "":
                if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                    fail("明确数值指标类型无效")
                try:
                    finite = math.isfinite(float(value))
                except (ValueError, OverflowError):
                    finite = False
                if not finite:
                    fail("明确数值指标无效")
            row[title] = value
        rows.append(row)
    return extra, rows


def select(query, limit=100, *, cookies, timeout):
    query = query_text(query)
    limit_value(limit)
    cookie = cookie_header(cookies)
    seconds = validate_timeout(timeout)
    headers = {**http.DEFAULT_HEADERS, "Cookie": cookie, "Origin": "https://www.iwencai.com",
               "Referer": "https://www.iwencai.com/screener", "X-Source": _SOURCE,
               "Accept": "text/event-stream, application/json"}
    payload = {
        "question": query, "default_fallback": False, "input_type": "click",
        "entity_info": {"device_type": "pc", "comefrom": None}, "source": _SOURCE,
        "dialog_model": "CUSTOMER_AGENT", "version": "3.4.1",
        "agent_tools": [{"tool_id": "FinQuery", "tool_param": {"domain": "stock", "perpage": _PAGE_SIZE}}],
        "events": [{"event_type": "user_input", "event_name": "normal_agent", "content": {}}],
        "add_info": {}, "agent_id": "MaSzyUwyyl", "agent_name": "",
    }
    component = _stream_table(_request(_STREAM, payload, headers, seconds, stream=True))
    descriptor, page_rows = _page(component)
    total = descriptor["row_count"]
    read_count = 0
    params = {key: value for key, value in descriptor.items() if key not in {"token", "per_page", "stock_code_list"}}
    params.update({"query": text(descriptor.get("query")) or query, "query_type": "stock", "source": _SOURCE})
    rows = {}
    for page in range(1, _MAX_PAGES + 1):
        if page > 1:
            document = json_object(_request(_RENDER, {**params, "page": page, "perpage": _PAGE_SIZE}, headers, seconds))
            status(document)
            page_extra, page_rows = _page(_component(document.get("answer")))
            if page_extra["row_count"] != total:
                fail("来源表格声明总业务行数漂移")
        if not page_rows:
            # row_count 是官网 tableAllCount，不机械当作唯一证券数。
            if read_count < total:
                fail("来源提前空页，未读齐声明业务行数")
            return list(rows.values())[:limit]
        read_count += len(page_rows)
        previous = len(rows)
        for row in page_rows:
            rows[row["exchange"], row["code"]] = row
        if len(rows) == previous:
            fail("选股分页没有推进")
        if len(rows) >= limit:
            return list(rows.values())[:limit]
    fail("选股分页达到防护预算，未取得目标或合法耗尽")
