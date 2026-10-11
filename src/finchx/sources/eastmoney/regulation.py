"""东方财富监管名单、异常波动报告与模型预测。"""

from datetime import datetime
import re
from urllib.parse import urlencode

from finchx._common import http
from finchx._common.convert import parse_date, to_number, validate_timeout
from finchx._common.errors import SourceError

SOURCE = "东方财富监管数据"
PAGE_SIZE = 200
_DC_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
_DY_URL = "https://dycalchis.eastmoney.com/price-anomaly/"
_WATCH_URL = "https://mobappconfig.securities.eastmoney.com/emcfg/stock_monitor.json"
_HEADERS = {**http.DEFAULT_HEADERS, "Referer": "https://emh5.eastmoney.com/"}
_CODE = re.compile(r"[0-9]{6}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DATETIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
_RECORD_COLUMNS = (
    "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,UNUSUAL_TYPE,START_DATE,END_DATE,"
    "INFO_CODE,NOTICE_DATE,UNUSUAL_REASON,UNUSUAL_REASON_TYPE,MRAKET_TYPE,"
    "PREDICT_START_DATE,PREDICT_END_DATE,IS_HIS"
)
_HISTORY_COLUMNS = (
    "SECUCODE,IS_SYSDATE,SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,MARKET_CODE,"
    "CHANGE_RATE,MAX_DAYS,DEVUATION_VALUE,CHANGE_RATE_TARGET,IS_HAPPEN,"
    "UNUSUAL_TYPE,IS_POSITIVE,RANK_TYPE"
)
_RULES = {
    1: "主板连续10个交易日内4次出现同向异常波动",
    2: "创业板连续10个交易日内3次出现同向异常波动",
    3: "科创板连续10个交易日内3次出现同向异常波动",
    4: "连续十个交易日内日收盘价涨跌幅偏离值累计达到+100%",
    5: "连续十个交易日内日收盘价涨跌幅偏离值累计达到-50%",
    6: "连续三十个交易日内日收盘价涨跌幅偏离值累计达到+200%",
    7: "连续三十个交易日内日收盘价涨跌幅偏离值累计达到-70%",
    8: "北交所连续10个交易日内3次出现同向异常波动",
    40: "连续十个交易日内日收盘价涨跌幅偏离值累计达到+150%",
    50: "连续十个交易日内日收盘价涨跌幅偏离值累计达到-60%",
    60: "连续30个交易日内日收盘价涨跌幅偏离值累计达到+300%",
    70: "连续30个交易日内日收盘价涨跌幅偏离值累计达到-75%",
}


def _fail(message: str) -> None:
    raise SourceError(SOURCE, message)


def _text(value, field: str, *, required: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            _fail(f"字段 {field} 缺失")
        return None
    if not isinstance(value, str) or not value.strip():
        _fail(f"字段 {field} 不是有效文本")
    return value


def _integer(value, field: str) -> int:
    if isinstance(value, bool):
        _fail(f"字段 {field} 不是非负整数")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    _fail(f"字段 {field} 不是非负整数")


def _flag(value, field: str) -> bool | None:
    if value is None or value in ("", "--", "-"):
        return None
    number = _integer(value, field)
    if number not in (0, 1):
        _fail(f"字段 {field} 不是来源 0/1 标记")
    return bool(number)


def _date(value, field: str, *, required: bool = False, compact: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            _fail(f"字段 {field} 缺失")
        return None
    if compact:
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
            _fail(f"字段 {field} 不是有效来源日期")
    else:
        if not isinstance(value, str):
            _fail(f"字段 {field} 不是有效来源日期")
        if _DATETIME.fullmatch(value):
            try:
                datetime(
                    int(value[:4]), int(value[5:7]), int(value[8:10]),
                    int(value[11:13]), int(value[14:16]), int(value[17:19]),
                )
            except ValueError:
                _fail(f"字段 {field} 不是有效来源日期时间")
            value = value[:10]
        elif not _DATE.fullmatch(value):
            _fail(f"字段 {field} 不是有效来源日期")
    try:
        return parse_date(value, field).isoformat()
    except ValueError as exc:
        raise SourceError(SOURCE, f"字段 {field} 不是有效来源日期") from exc


def _exchange(code) -> str:
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        _fail("证券代码不是六位 ASCII 数字字符串")
    if code.startswith(("60", "68", "90", "50", "51", "52", "56", "58")):
        return "sh"
    if code.startswith(("00", "20", "30", "15", "16")):
        return "sz"
    if code.startswith(("43", "83", "87", "88", "92")):
        return "bj"
    _fail(f"无法核实证券代码所属交易所：{code}")


def _market_identity(code, market, *, watch: bool = False) -> str:
    exchange = _exchange(code)
    if watch:
        expected = {"sh": "1", "sz": "0", "bj": "B"}[exchange]
        if market != expected:
            _fail("重点监控证券的 MARKET 与代码身份不符")
    elif _integer(market, "market") != (1 if exchange == "sh" else 0):
        _fail("证券的市场标记与代码身份不符")
    return exchange


def _dc_identity(raw: dict) -> tuple[str, str, str]:
    code = raw.get("SECURITY_CODE")
    exchange = _exchange(code)
    if raw.get("SECUCODE") != f"{code}.{exchange.upper()}":
        _fail("SECUCODE 与证券代码身份不符")
    if "MARKET_CODE" in raw:
        _market_identity(code, raw["MARKET_CODE"])
    if "MRAKET_TYPE" in raw and raw["MRAKET_TYPE"] != {
        "sh": "上交所", "sz": "深交所", "bj": "北交所",
    }[exchange]:
        _fail("MRAKET_TYPE 与证券身份不符")
    return code, exchange, _text(raw.get("SECURITY_NAME_ABBR"), "SECURITY_NAME_ABBR", required=True)


def _number(raw: dict, field: str, *, integer: bool = False, nonnegative: bool = False):
    return to_number(raw.get(field), field, source=SOURCE, integer=integer, nonnegative=nonnegative)


def _record(raw: dict, event_type: str) -> dict:
    code, exchange, name = _dc_identity(raw)
    if raw.get("UNUSUAL_TYPE") != {"ordinary": "001", "severe": "002"}[event_type]:
        _fail("公告的异常波动类型与请求不符")
    severe = event_type == "severe"
    status = _flag(raw.get("IS_HIS"), "IS_HIS") if severe else None
    return {
        "code": code, "exchange": exchange, "name": name, "event_type": event_type,
        "start_date": _date(raw.get("START_DATE"), "START_DATE"),
        "end_date": _date(raw.get("END_DATE"), "END_DATE"),
        "announcement_date": _date(raw.get("NOTICE_DATE"), "NOTICE_DATE", required=True),
        "announcement_id": _text(raw.get("INFO_CODE"), "INFO_CODE", required=True),
        "reason": _text(raw.get("UNUSUAL_REASON"), "UNUSUAL_REASON"),
        "reason_type": _text(raw.get("UNUSUAL_REASON_TYPE"), "UNUSUAL_REASON_TYPE"),
        "monitor_start_date": _date(raw.get("PREDICT_START_DATE"), "PREDICT_START_DATE") if severe else None,
        "monitor_end_date": _date(raw.get("PREDICT_END_DATE"), "PREDICT_END_DATE") if severe else None,
        "monitor_status": None if status is None else ("current" if status else "history"),
    }


def _history(raw: dict) -> dict:
    code, exchange, name = _dc_identity(raw)
    direction = _flag(raw.get("IS_POSITIVE"), "IS_POSITIVE")
    return {
        "code": code, "exchange": exchange, "name": name,
        "date": _date(raw.get("TRADE_DATE"), "TRADE_DATE", required=True),
        "change_percent": _number(raw, "CHANGE_RATE"),
        "window_days": _number(raw, "MAX_DAYS", integer=True, nonnegative=True),
        "deviation_percent": _number(raw, "DEVUATION_VALUE"),
        "trigger_change_percent": _number(raw, "CHANGE_RATE_TARGET"),
        "is_triggered": _flag(raw.get("IS_HAPPEN"), "IS_HAPPEN"),
        "rule": _text(raw.get("UNUSUAL_TYPE"), "UNUSUAL_TYPE", required=True),
        "direction": None if direction is None else ("up" if direction else "down"),
        "is_current": _flag(raw.get("IS_SYSDATE"), "IS_SYSDATE"),
    }


def _prediction(raw: dict, observation_date: str) -> dict:
    code = raw.get("c")
    exchange = _market_identity(code, raw.get("m"))
    board_id = _integer(raw.get("s"), "s")
    expected_board = 6 if exchange == "bj" else 5 if code.startswith("68") else 4 if code.startswith("30") else 1
    if board_id != expected_board:
        _fail("预测板块与证券身份不符或未经确认")
    rule_id = _integer(raw.get("e"), "e")
    if rule_id in (4, 5, 6, 7):
        if board_id == 6:
            rule_id *= 10
    elif rule_id != {1: 1, 4: 2, 5: 3, 6: 8}[board_id]:
        _fail("预测规则与来源板块不符或未经确认")
    scenario = _integer(raw.get("o"), "o")
    if scenario not in (0, 1, 2):
        _fail("预测场景不是来源 0/1/2 标记")
    return {
        "code": code, "exchange": exchange, "name": _text(raw.get("n"), "n", required=True),
        "date": observation_date, "board": {1: "main", 4: "chinext", 5: "star", 6: "bse"}[board_id],
        "rule": _RULES[rule_id],
        "window_days": _number(raw, "d", integer=True, nonnegative=True),
        "deviation_percent": _number(raw, "x"),
        "trigger_change_percent": _number(raw, "t"),
        "change_percent": _number(raw, "a"),
        "scenario": "next_session" if scenario == 2 else "current",
        "is_triggered": None if scenario == 2 else bool(scenario),
    }


def _count(raw: dict, observation_date: str) -> dict:
    code = raw.get("c")
    return {
        "code": code, "exchange": _market_identity(code, raw.get("m")),
        "name": _text(raw.get("n"), "n", required=True), "date": observation_date,
        "price": _number(raw, "p", nonnegative=True), "change_percent": _number(raw, "a"),
        "abnormal_count": _number(raw, "t", integer=True, nonnegative=True),
        "max_deviation_percent": _number(raw, "x"),
    }


def _page(payload, page: int, *, dc: bool) -> tuple[list, int, int, str | None]:
    if not isinstance(payload, dict):
        _fail("分页响应不是字典")
    if dc:
        if payload.get("success") is not True or _integer(payload.get("code"), "code") != 0:
            _fail("异常波动报告返回失败状态")
        data = payload.get("result")
        if not isinstance(data, dict):
            _fail("报告 result 结构损坏")
        observation_date = None
        page_field = "pageNumber"
    else:
        if _integer(payload.get("result"), "result") != 0:
            _fail("预测统计返回失败状态")
        data = payload
        observation_date = _date(data.get("date"), "date", required=True, compact=True)
        page_field = "pageNo"
    for block in (payload, data):
        if page_field in block and _integer(block[page_field], page_field) != page:
            _fail("来源页码与请求页码不符")
    count = _integer(data.get("count"), "count")
    pages = _integer(data.get("pages"), "pages")
    expected_pages = (count + PAGE_SIZE - 1) // PAGE_SIZE
    if pages != expected_pages and not (count == 0 and pages == 1):
        _fail("来源 pages 与 count 不一致")
    rows = data.get("data")
    if not isinstance(rows, list):
        _fail("分页 data 不是列表")
    expected_length = min(PAGE_SIZE, max(0, count - (page - 1) * PAGE_SIZE))
    if len(rows) != expected_length:
        _fail("分页提前短页或记录数量异常")
    return rows, count, pages, observation_date


def _merge(rows: list, records: dict, parse_row, key) -> None:
    seen = set()
    for raw in rows:
        if not isinstance(raw, dict):
            _fail("业务记录不是字典")
        row = parse_row(raw)
        identity = key(row)
        if identity in seen:
            _fail("来源同页出现重复业务记录")
        seen.add(identity)
        records[identity] = row


def _dc_report(report: str, columns: str, filter_text: str, sort_columns: str,
               sort_types: tuple[str, ...], parse_row, key, *, timeout: float) -> list[dict]:
    seconds = validate_timeout(timeout)
    records = {}
    target = None
    target_pages = None
    for direction in sort_types:
        page = 1
        while True:
            params = {
                "reportName": report, "columns": columns, "quoteColumns": "", "filter": filter_text,
                "pageNumber": page, "pageSize": PAGE_SIZE, "sortColumns": sort_columns,
                "sortTypes": direction, "source": "SECURITIES", "client": "APP",
            }
            payload = http.get_json(_DC_URL + "?" + urlencode(params), timeout=seconds, headers=_HEADERS, source=SOURCE)
            rows, count, pages, _ = _page(payload, page, dc=True)
            if target is None:
                target, target_pages = count, pages
            elif (count, pages) != (target, target_pages):
                _fail("来源 count/pages 在分页或补取期间变化")
            _merge(rows, records, parse_row, key)
            if len(records) > target:
                _fail("唯一业务记录数超过来源 count")
            if len(records) == target:
                return list(records.values())
            if page >= pages:
                break
            page += 1
    _fail("补取三轮后仍未取齐来源 count 声明的业务记录")


def _dy_list(resource: str, parse_row, key, *, timeout: float) -> list[dict]:
    seconds = validate_timeout(timeout)
    records = {}
    target = None
    snapshot = None
    for direction in (1, 0, 1):
        page = 1
        while True:
            params = {"team": "h5", "product": "EastMoney", "client": "WAP", "version": "9001",
                      "name": "WAP", "user": "123", "pageSize": PAGE_SIZE, "pageNo": page}
            if resource == "list":
                params.update(riseOnly=0, showBJS=1)
            else:
                params.update(sortKey=0, sortDir=direction)
            payload = http.get_json(_DY_URL + resource + "?" + urlencode(params), timeout=seconds, headers=_HEADERS, source=SOURCE)
            rows, count, pages, observation_date = _page(payload, page, dc=False)
            current = (count, pages, observation_date)
            if target is None:
                target, snapshot = count, current
            elif current != snapshot:
                _fail("来源 count/pages/date 在分页或补取期间变化")
            _merge(rows, records, lambda row: parse_row(row, observation_date), key)
            if len(records) > target:
                _fail("唯一业务记录数超过来源 count")
            if len(records) == target:
                return list(records.values())
            if page >= pages:
                break
            page += 1
    _fail("补取三轮后仍未取齐来源 count 声明的业务记录")


def watchlist(*, timeout: float) -> list[dict]:
    seconds = validate_timeout(timeout)
    payload = http.get_json(_WATCH_URL, timeout=seconds, headers=_HEADERS, source=SOURCE)
    if not isinstance(payload, list):
        _fail("重点监控名单不是列表")
    rows = []
    seen = set()
    for raw in payload:
        if not isinstance(raw, dict):
            _fail("重点监控记录不是字典")
        code = raw.get("STKCODE")
        exchange = _market_identity(code, raw.get("MARKET"), watch=True)
        row = {
            "code": code, "exchange": exchange, "name": _text(raw.get("STKNAME"), "STKNAME", required=True),
            "monitor_start_date": _date(raw.get("VALIDATESTARTDATE"), "VALIDATESTARTDATE"),
            "expected_end_date": _date(raw.get("VALIDATEENDDATE"), "VALIDATEENDDATE"),
            "source_url": _text(raw.get("LINK_URL"), "LINK_URL"),
        }
        identity = (exchange, code, row["monitor_start_date"], row["expected_end_date"])
        if identity in seen:
            _fail("重点监控名单有重复证券监控区间")
        seen.add(identity)
        rows.append(row)
    return rows


def abnormal_records(event_type: str = "ordinary", *, timeout: float) -> list[dict]:
    if not isinstance(event_type, str) or event_type not in {"ordinary", "severe"}:
        raise ValueError("event_type 必须是 ordinary 或 severe")
    event_id = {"ordinary": "001", "severe": "002"}[event_type]
    return _dc_report(
        "RPT_APP_UNUSUALBASIC", _RECORD_COLUMNS, f'(UNUSUAL_TYPE="{event_id}")',
        "NOTICE_DATE,END_DATE,SECURITY_CODE,INFO_CODE", ("-1,-1,1,1", "1,1,-1,-1", "-1,-1,1,1"),
        lambda raw: _record(raw, event_type),
        lambda row: (row["exchange"], row["code"], row["event_type"], row["announcement_id"]), timeout=timeout,
    )


def abnormal_prediction_history(*, timeout: float) -> list[dict]:
    return _dc_report(
        "RPT_WATCH_UNUSUAL_FLUCTUATE", _HISTORY_COLUMNS, "", "TRADE_DATE,SECURITY_CODE,UNUSUAL_TYPE",
        ("-1,1,1", "1,-1,-1", "-1,1,1"), _history,
        lambda row: (row["exchange"], row["code"], row["date"], row["rule"]), timeout=timeout,
    )


def severe_predictions(*, timeout: float) -> list[dict]:
    return _dy_list("list", _prediction,
                    lambda row: (row["exchange"], row["code"], row["rule"], row["scenario"]), timeout=timeout)


def abnormal_counts(*, timeout: float) -> list[dict]:
    return _dy_list("count", _count, lambda row: (row["exchange"], row["code"]), timeout=timeout)
