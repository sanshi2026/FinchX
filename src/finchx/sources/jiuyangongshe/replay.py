"""韭研公社官方复盘，保留题材、股票与解析原文。"""

from datetime import date as Date
import json
from contextlib import suppress
import time
import re
from typing import Any

from finchx._common.convert import parse_date_parameter, to_number, validate_timeout
from finchx._common.errors import SourceError

SOURCE = "jiuyangongshe"
_ORIGIN = "https://www.jiuyangongshe.com"
_API = "https://web-api.jiuyangongshe.com/jystock-app/api/v1/action/"
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_IDENTITY = re.compile(r"(sh|sz|bj)([0-9]{6})", re.IGNORECASE)
_TIME = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]")


def _source_date(value: Any, field: str) -> str:
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        try:
            Date.fromisoformat(value)
            return value
        except ValueError:
            pass
    raise SourceError(SOURCE, f"字段 {field} 不是有效的 ISO 日期")


def _text(value: Any, field: str, *, optional: bool = False) -> str | None:
    if optional and (value is None or value == ""):
        return None
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise SourceError(SOURCE, f"字段 {field} 不是有效文本")
    return value


def _count(value: Any, field: str) -> int:
    number = to_number(value, field, source=SOURCE, integer=True, nonnegative=True)
    if number is None:
        raise SourceError(SOURCE, f"字段 {field} 缺失计数")
    return number


def _response_data(document: Any, label: str) -> Any:
    if not isinstance(document, dict):
        raise SourceError(SOURCE, f"{label} 响应不是对象")
    code = document.get("errCode")
    if isinstance(code, bool) or not isinstance(code, (int, str)):
        raise SourceError(SOURCE, f"{label} 缺失或损坏 errCode")
    if code in (1, "1"):
        raise SourceError(SOURCE, f"{label} 登录失效（errCode=1），请更新 session")
    if code in (110, "110"):
        raise SourceError(SOURCE, f"{label} token/signature 无效（errCode=110）")
    if code not in (0, "0"):
        # 不复制来源 msg；来源错误文本可能回显请求认证信息。
        safe_code = (str(code) if type(code) is int and 0 <= code <= 9999 else
                     code if type(code) is str and re.fullmatch(r"[0-9]{1,4}", code) else None)
        detail = f"（errCode={safe_code}）" if safe_code is not None else ""
        raise SourceError(SOURCE, f"{label} 来源返回错误状态{detail}")
    if "data" not in document:
        raise SourceError(SOURCE, f"{label} 缺失 data")
    return document["data"]


def _stock(raw: Any, label: str) -> dict:
    if not isinstance(raw, dict):
        raise SourceError(SOURCE, f"{label} 不是对象")
    identity = raw.get("code")
    match = _IDENTITY.fullmatch(identity) if isinstance(identity, str) else None
    if match is None:
        raise SourceError(SOURCE, f"{label}.code 缺失明确 sh/sz/bj 证券身份")
    article = raw.get("article")
    if not isinstance(article, dict) or not isinstance(article.get("action_info"), dict):
        raise SourceError(SOURCE, f"{label}.article.action_info 结构损坏")
    info = article["action_info"]
    clock = _text(info.get("time"), f"{label}.time", optional=True)
    if clock is not None and not _TIME.fullmatch(clock):
        raise SourceError(SOURCE, f"{label}.time 不是有效的 HH:MM:SS 时刻")
    return {
        "code": match.group(2),
        "exchange": match.group(1).lower(),
        "name": _text(raw.get("name"), f"{label}.name"),
        "price": to_number(info.get("price"), f"{label}.price", source=SOURCE,
                           scale=-2, nonnegative=True),
        "change_percent": to_number(info.get("shares_range"), f"{label}.shares_range",
                                    source=SOURCE, scale=-2),
        "limit_up_time": clock,
        "streak_text": _text(info.get("num"), f"{label}.num", optional=True),
        "explanation": _text(info.get("expound"), f"{label}.expound", optional=True),
    }


def _parse_replay(count_document: Any, field_document: Any, requested_date: str | None) -> dict:
    count = _response_data(count_document, "count-pc")
    if not isinstance(count, dict):
        raise SourceError(SOURCE, "count-pc data 结构损坏")
    trade_date = _source_date(count.get("date"), "count-pc.date")
    if requested_date is not None and trade_date > requested_date:
        raise SourceError(SOURCE, "count-pc 实际日期晚于请求日期")
    all_count = _count(count.get("all"), "count-pc.all")
    data = _response_data(field_document, "action/field")
    if not isinstance(data, list):
        raise SourceError(SOURCE, "action/field data 不是列表")
    if all_count > 0 and not data:
        raise SourceError(SOURCE, "官网声明存在解析但 field 列表为空")
    themes = []
    identities = set()
    for index, raw in enumerate(data):
        label = f"theme[{index}]"
        if not isinstance(raw, dict):
            raise SourceError(SOURCE, f"{label} 不是对象")
        if _source_date(raw.get("date"), f"{label}.date") != trade_date:
            raise SourceError(SOURCE, f"{label} 日期与 count-pc 不一致")
        name = _text(raw.get("name"), f"{label}.name")
        declared = _count(raw.get("count"), f"{label}.count")
        if index == 0 and name == "简图" and "list" not in raw:
            # 官网的首项简图不是题材股票列表。
            continue
        raw_stocks = raw.get("list")
        if not isinstance(raw_stocks, list):
            raise SourceError(SOURCE, f"{label}.list 不是完整列表")
        if declared > 0 and not raw_stocks:
            raise SourceError(SOURCE, f"{label} 声明存在股票但列表为空")
        theme_id = _text(raw.get("action_field_id"), f"{label}.action_field_id")
        if theme_id in identities:
            raise SourceError(SOURCE, "题材身份重复")
        identities.add(theme_id)
        stocks = []
        seen = set()
        for stock_index, raw_stock in enumerate(raw_stocks):
            stock = _stock(raw_stock, f"{label}.stocks[{stock_index}]")
            identity = stock["exchange"], stock["code"]
            if identity in seen:
                raise SourceError(SOURCE, f"{label} 内证券身份重复")
            seen.add(identity)
            stocks.append(stock)
        themes.append({"name": name,
                       "reason": _text(raw.get("reason"), f"{label}.reason", optional=True),
                       "stocks": stocks})
    if all_count > 0 and not any(theme["stocks"] for theme in themes):
        raise SourceError(SOURCE, "官网声明存在解析但未提供题材股票列表")
    return {"date": trade_date, "themes": themes}


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SourceError(SOURCE, "缺少可选浏览器依赖，请安装 finchx[jygs] 并运行 python -m playwright install chromium") from None
    return sync_playwright


def _capture(url: str, session: str, timeout: float, headless: bool) -> tuple[dict, dict, str, str]:
    """执行官网动态签名流程，只捕获点击全部解析产生的两份响应。"""
    sync_playwright = _load_playwright()
    deadline = time.monotonic() + timeout
    records = []
    requests = {}
    stage = "浏览器启动"

    def remaining() -> int:
        milliseconds = int((deadline - time.monotonic()) * 1000)
        if milliseconds <= 0:
            raise SourceError(SOURCE, f"官网复盘{stage}超时")
        return milliseconds

    def http_failure(status: Any) -> str | None:
        if type(status) is not int or not 100 <= status <= 599:
            return "HTTP 状态损坏"
        return f"HTTP {status}" if not 200 <= status < 300 else None

    def on_request(request):
        endpoint = request.url.split("?", 1)[0]
        if endpoint not in {_API + "count-pc", _API + "field"}:
            return
        record = {"endpoint": endpoint, "label": endpoint.rsplit("/", 1)[-1],
                  "error": None, "document": None, "complete": False}
        try:
            payload = json.loads(request.post_data)
            if request.method != "POST" or not isinstance(payload, dict):
                raise ValueError
            record["date"] = _source_date(payload.get("date"), "官网请求.date")
            if endpoint.endswith("/field") and (isinstance(payload.get("pc"), bool) or payload.get("pc") != 1):
                raise ValueError
        except (ValueError, TypeError, SourceError):
            record["error"] = f"官网复盘 {record['label']} 请求日期或参数结构损坏"
        records.append(record)
        requests[request] = record

    def on_response(response):
        record = requests.get(response.request)
        if record is None:
            return
        try:
            failure = http_failure(response.status)
            if failure is not None:
                record["error"] = f"官网复盘 {record['label']} 请求失败（{failure}）"
            else:
                record["document"] = response.json()
        except Exception:
            record["error"] = f"官网复盘 {record['label']} 响应不是有效 JSON"
        finally:
            record["complete"] = True

    def on_request_failed(request):
        record = requests.get(request)
        if record is not None:
            # 不读取 failure：浏览器的原始失败信息可能包含 URL 或认证信息。
            record["error"] = f"官网复盘 {record['label']} 请求失败（未取得 HTTP 响应）"
            record["complete"] = True

    browser = context = None
    try:
        with sync_playwright() as runtime:
            try:
                browser = runtime.chromium.launch(headless=headless, timeout=remaining())
                stage = "初始化上下文/页面"
                remaining()
                context = browser.new_context()
                remaining()
                context.add_cookies([
                    {"name": "SESSION", "value": session, "domain": domain, "path": "/"}
                    for domain in ("www.jiuyangongshe.com", "web-api.jiuyangongshe.com")
                ])
                remaining()
                page = context.new_page()
                stage = "打开页面"
                navigation = page.goto(url, wait_until="domcontentloaded", timeout=remaining())
                if navigation is not None:
                    failure = http_failure(navigation.status)
                    if failure is not None:
                        raise SourceError(SOURCE, f"官网复盘打开页面失败（{failure}）")
                # SSR 的标签可能先可见，需等官网绑定点击事件后再切换。
                stage = "等待初始化"
                page.wait_for_function(
                    "() => Boolean(window.$nuxt && window.$nuxt._isMounted)",
                    timeout=remaining(),
                )
                # 导航阶段的 SSR/初始请求不充当点击后取得的业务链。
                page.on("request", on_request)
                page.on("response", on_response)
                page.on("requestfailed", on_request_failed)
                stage = "点击全部异动解析"
                page.get_by_text("全部异动解析", exact=True).first.click(timeout=remaining())
                while True:
                    completed = [record for record in records if record["error"] or record["complete"]]
                    for record in completed:
                        if record["error"]:
                            raise SourceError(SOURCE, record["error"])
                        _response_data(record["document"], record["endpoint"].rsplit("/", 1)[-1])
                    counts = [record for record in completed if record["endpoint"].endswith("/count-pc")]
                    fields = [record for record in completed if record["endpoint"].endswith("/field")]
                    if counts and fields:
                        # 一次点击应只有一条链，不能混合来源不明的多次更新。
                        if len(counts) != 1 or len(fields) != 1 or len(records) != 2:
                            raise SourceError(SOURCE, "官网复盘请求链不唯一")
                        count, field = counts[0], fields[0]
                        if records.index(count) > records.index(field):
                            raise SourceError(SOURCE, "官网 field 未关联此前 count-pc")
                        stage = "等待 count-pc/field 响应"
                        remaining()
                        return count["document"], field["document"], count["date"], field["date"]
                    stage = "等待 field 响应" if counts else "等待 count-pc 响应"
                    page.wait_for_timeout(min(100, remaining()))
            finally:
                if context is not None:
                    with suppress(Exception):
                        context.close()
                if browser is not None:
                    with suppress(Exception):
                        browser.close()
    except SourceError as exc:
        raise exc from None
    except Exception as exc:
        message = str(exc).lower()
        if stage == "浏览器启动" and ("executable doesn't exist" in message or "executable does not exist" in message):
            reason = "官网复盘浏览器启动失败：缺少 Chromium，请运行 python -m playwright install chromium"
        elif "timeout" in type(exc).__name__.lower():
            reason = f"官网复盘{stage}超时"
        else:
            reason = f"官网复盘{stage}失败"
        # 浏览器异常可能含 cookie 或请求信息，不能回显或作为异常链返回。
        raise SourceError(SOURCE, reason) from None


def jygs_replay(date: str | None = None, *, session: str, headless: bool = False, timeout: float) -> dict:
    """SESSION 仅用于单次临时浏览器，日期由官网 count-pc 确定。"""
    if date is not None:
        date = parse_date_parameter(date, "date").isoformat()
    if not isinstance(session, str) or not re.fullmatch(r"[!#$%&'()*+\-./0-9:<=>?@A-Z\[\]^_`a-z{|}~]+", session):
        raise ValueError("session 必须是非空 SESSION 值，不包含空白、分号、逗号或控制字符")
    if type(headless) is not bool:
        raise ValueError("headless 必须是布尔值")
    seconds = validate_timeout(timeout)
    url = f"{_ORIGIN}/action" + (f"/{date}" if date is not None else "")
    count, field, count_date, field_date = _capture(url, session, seconds, headless)
    count_data = _response_data(count, "count-pc")
    if not isinstance(count_data, dict):
        raise SourceError(SOURCE, "count-pc data 结构损坏")
    actual = _source_date(count_data.get("date"), "count-pc.date")
    if field_date != actual or actual > count_date or (date is not None and count_date > date):
        raise SourceError(SOURCE, "官网 count-pc 与 field 请求日期未关联同一次复盘")
    return _parse_replay(count, field, date)
