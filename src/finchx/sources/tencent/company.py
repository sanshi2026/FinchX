"""腾讯公司简况与流通股东；每次调用独立读取一份来源响应。"""

from datetime import date
from decimal import Decimal
import json
import re
from urllib.parse import urlencode

from finchx._common.convert import resolve_code, to_number, validate_timeout
from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_text

INFO_ENDPOINT = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/stockinfo/jiankuang"
FLOAT_SHAREHOLDERS_ENDPOINT = "https://proxy.finance.qq.com/ifzqgtimg/appstock/hs/ltgd/get"
_HEADERS = {**DEFAULT_HEADERS, "Referer": "https://stockapp.finance.qq.com/"}
_JSONP = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*\s*\(\s*(\{.*\})\s*\)\s*;?", re.DOTALL)
_ASSIGNMENT = re.compile(r"v_liutonggd\s*=\s*(\{.*\})\s*;?", re.DOTALL)
_DISPLAY_NUMBER = re.compile(
    r"([+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|"
    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?))([万亿]?)(股|户|元|%)?"
)
_MISSING = {"", "--", "-"}
_FINANCIAL_NUMBER = re.compile(
    r"([+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|"
    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?))(万亿|亿|万)?(元|%)?"
)
_REVENUE_UNITS = {"元": 0, "万元": 4, "亿元": 8, "万亿元": 12}
_REPORT_PERIOD = re.compile(r"[0-9]{4}(?:一季报|中报|三季报|年报)")


def _fail(reason: str) -> None:
    raise SourceError("tencent", reason)


def _reject_constant(value: str) -> None:
    raise ValueError(f"非法 JSON 常量：{value}")


def _decode(text: object, context: str, *, assignment: bool = False) -> dict:
    if not isinstance(text, str) or not text.strip():
        _fail(f"{context} 响应必须是非空 JSON 文本")
    candidate = text.strip()
    if not candidate.startswith("{"):
        match = _ASSIGNMENT.fullmatch(candidate) if assignment else None
        if match is None:
            match = _JSONP.fullmatch(candidate)
        if match is None:
            _fail(f"{context} 响应不是有效 JSON 或 JSONP")
        candidate = match.group(1)
    try:
        payload = json.loads(candidate, parse_float=Decimal, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise SourceError("tencent", f"{context} 响应不是有效 JSON") from exc
    if not isinstance(payload, dict):
        _fail(f"{context} 响应外层必须是对象")
    status = payload.get("code")
    if not (type(status) is int and status == 0 or isinstance(status, str) and status == "0"):
        _fail(f"{context} 来源 code 表示请求失败")
    if not isinstance(payload.get("msg"), str):
        _fail(f"{context} 来源 msg 必须是文本")
    data = payload.get("data")
    if not isinstance(data, dict):
        _fail(f"{context} 响应缺少有效 data 对象")
    return data


def _text(value: object, field: str, *, required: bool = False) -> str | None:
    if value is None:
        result = None
    elif not isinstance(value, str):
        _fail(f"{field} 必须是文本")
    else:
        result = value.strip()
        if result in _MISSING:
            result = None
    if required and result is None:
        _fail(f"{field} 必须是非空文本")
    return result


def _date(value: object, field: str, *, required: bool = False) -> str | None:
    result = _text(value, field, required=required)
    if result is None:
        return None
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", result):
        _fail(f"{field} 必须是有效 ISO 日期")
    try:
        date.fromisoformat(result)
    except ValueError as exc:
        raise SourceError("tencent", f"{field} 必须是有效 ISO 日期") from exc
    return result


def _period_label(value: object, field: str) -> str | None:
    if type(value) is int and 1000 <= value <= 9999:
        return str(value)
    return _text(value, field)


def _number(value: object, field: str, *, unit: str = "", integer: bool = False,
            nonnegative: bool = True) -> float | int | None:
    scale = 0
    if isinstance(value, str):
        value = value.strip()
        if value not in _MISSING:
            match = _DISPLAY_NUMBER.fullmatch(value)
            if match is None or match.group(3) not in (None, unit):
                _fail(f"{field} 不是有效来源数值或单位不符")
            if unit == "%" and match.group(2):
                _fail(f"{field} 百分比不得带万或亿单位")
            scale = {"": 0, "万": 4, "亿": 8}[match.group(2)]
            value = match.group(1).replace(",", "")
    return to_number(value, field, source="tencent", scale=scale,
                     integer=integer, nonnegative=nonnegative)


def _rows(value: object, field: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        _fail(f"{field} 必须是对象列表")
    return value


def _stock_identity(data: dict, symbol: str) -> None:
    # 股票身份与财务业务分别验证，不读取行业内部编号或额外行情指标。
    hydb = data.get("hydb")
    stock = hydb.get("stock") if isinstance(hydb, dict) else None
    if isinstance(stock, dict):
        for field, expected in (("stockcode", symbol[2:]), ("sc", symbol[:2])):
            if field in stock and stock[field] is not None and stock[field] != expected:
                _fail(f"data.hydb.stock.{field} 与请求股票身份不一致")


def _financial_number(value: object, field: str, *, percent: bool = False,
                      amount: bool = True, nonnegative: bool = False,
                      bare_scale: int = 0) -> float | None:
    scale = bare_scale
    if isinstance(value, str):
        value = value.strip()
        if value not in _MISSING:
            match = _FINANCIAL_NUMBER.fullmatch(value)
            suffixes = (None, "%") if percent else (None, "元") if amount else (None,)
            if match is None or match.group(3) not in suffixes:
                _fail(f"{field} 不是有效财务数值或单位不符")
            magnitude, suffix = match.group(2), match.group(3)
            if percent and magnitude:
                _fail(f"{field} 百分比不得带金额单位")
            if not percent and not amount and magnitude:
                _fail(f"{field} 估值比率不得带金额单位")
            # 数值自带金额单位时已给出尺度，不能再乘外层 unit。
            if magnitude is not None or suffix == "元":
                scale = {None: 0, "万": 4, "亿": 8, "万亿": 12}[magnitude]
            value = match.group(1).replace(",", "")
    return to_number(value, field, source="tencent", scale=scale,
                     nonnegative=nonnegative)


def _financial_period(value: object, field: str, *, annual: bool = False) -> str:
    period = _text(value, field, required=True)
    pattern = r"[0-9]{4}" if annual else _REPORT_PERIOD
    if re.fullmatch(pattern, period) is None or not 1000 <= int(period[:4]) <= 9999:
        _fail(f"{field} 不是有效来源报告期")
    return period


def _financial_summary(data: dict) -> dict:
    summary = data.get("zyzb")
    if not isinstance(summary, dict) or not isinstance(summary.get("detail"), dict):
        _fail("data.zyzb 及 data.zyzb.detail 必须是对象")
    detail = summary["detail"]
    context = "data.zyzb.detail"
    revenue_field = "yyzsr" if "yyzsr" in detail else "yysr"
    growth_field = "zsrzzl" if "zsrzzl" in detail else "srzzl"
    current = {
        "period": _financial_period(summary.get("date"), "data.zyzb.date"),
        "eps": _financial_number(detail.get("mgsy"), f"{context}.mgsy"),
        "revenue": _financial_number(detail.get(revenue_field), f"{context}.{revenue_field}", nonnegative=True),
        "revenue_change_percent": _financial_number(detail.get(growth_field), f"{context}.{growth_field}", percent=True),
        "net_profit": _financial_number(detail.get("jlr"), f"{context}.jlr"),
        "net_profit_change_percent": _financial_number(detail.get("jlrzzl"), f"{context}.jlrzzl", percent=True),
        "book_value_per_share": _financial_number(detail.get("mgjzc"), f"{context}.mgjzc"),
        "net_assets": _financial_number(detail.get("jzc"), f"{context}.jzc"),
        "goodwill": _financial_number(detail.get("sy"), f"{context}.sy", nonnegative=True),
        "goodwill_to_net_assets_percent": _financial_number(detail.get("sy_jzc"), f"{context}.sy_jzc", percent=True),
        "roe_percent": _financial_number(detail.get("jzcsyl"), f"{context}.jzcsyl", percent=True),
        "debt_ratio_percent": _financial_number(detail.get("zcfzl"), f"{context}.zcfzl", percent=True, nonnegative=True),
        "pe_ttm": _financial_number(detail.get("syl"), f"{context}.syl", amount=False),
        "pb": _financial_number(detail.get("sjl"), f"{context}.sjl", amount=False),
    }
    history = []
    seen = set()
    for index, row in enumerate(_rows(data.get("hytrend"), "data.hytrend")):
        context = f"data.hytrend[{index}]"
        period = _financial_period(row.get("date"), f"{context}.date", annual=True)
        if period in seen:
            _fail(f"data.hytrend 存在重复报告期：{period}")
        seen.add(period)
        revenue_field = "f_yyzsr" if "f_yyzsr" in row else "f_yysr"
        growth_field = "t_yyzsr" if "t_yyzsr" in row else "t_yysr"
        history.append({
            "period": period,
            "revenue": _financial_number(row.get(revenue_field), f"{context}.{revenue_field}", nonnegative=True),
            "revenue_change_percent": _financial_number(row.get(growth_field), f"{context}.{growth_field}", percent=True),
            "net_profit": _financial_number(row.get("f_jlr"), f"{context}.f_jlr"),
            "net_profit_change_percent": _financial_number(row.get("t_jlr"), f"{context}.t_jlr", percent=True),
            "eps": _financial_number(row.get("f_mgsy"), f"{context}.f_mgsy"),
            "eps_change_percent": _financial_number(row.get("t_mgsy"), f"{context}.t_mgsy", percent=True),
        })
    return {"current": current, "history": history}


def _revenue_items(rows: object, context: str) -> list[dict]:
    result = []
    for index, row in enumerate(_rows(rows, context)):
        field = f"{context}[{index}]"
        unit = _text(row.get("unit"), f"{field}.unit")
        income = row.get("income")
        scale = 0
        if unit is not None:
            if unit not in _REVENUE_UNITS:
                _fail(f"{field}.unit 不是已确认的主营收入金额单位")
            scale = _REVENUE_UNITS[unit]
        elif income is not None and not (isinstance(income, str) and income.strip() in _MISSING):
            match = _FINANCIAL_NUMBER.fullmatch(income.strip()) if isinstance(income, str) else None
            if match is None or match.group(2) is None and match.group(3) != "元":
                _fail(f"{field}.income 缺少可确定金额尺度的单位")
        result.append({
            "name": _text(row.get("name"), f"{field}.name", required=True),
            "unit": unit,
            "revenue": _financial_number(income, f"{field}.income", nonnegative=True, bare_scale=scale),
            "revenue_share_percent": _financial_number(row.get("zb"), f"{field}.zb", percent=True, nonnegative=True),
        })
    return result


def _revenue_breakdown(data: dict) -> list[dict]:
    result = []
    seen_periods = set()
    dimensions = {"sector": "industry", "product": "product", "region": "region"}
    for index, row in enumerate(_rows(data.get("zysr"), "data.zysr")):
        context = f"data.zysr[{index}]"
        period = _financial_period(row.get("date"), f"{context}.date")
        if period in seen_periods:
            _fail(f"data.zysr 存在重复报告期：{period}")
        seen_periods.add(period)
        seen_dimensions = set()
        for group_index, group in enumerate(_rows(row.get("detail"), f"{context}.detail")):
            field = f"{context}.detail[{group_index}]"
            source_dimension = _text(group.get("type"), f"{field}.type", required=True)
            if source_dimension not in dimensions:
                _fail(f"{field}.type 不是已确认的主营构成维度")
            if source_dimension in seen_dimensions:
                _fail(f"{context} 存在重复主营构成维度：{source_dimension}")
            seen_dimensions.add(source_dimension)
            result.append({
                "period": period, "dimension": dimensions[source_dimension],
                "items": _revenue_items(group.get("detail"), f"{field}.detail"),
                "other_items": _revenue_items(group.get("others", []), f"{field}.others"),
            })
    return result


def _industry_comparison(data: dict) -> dict:
    comparison = data.get("hydb")
    if not isinstance(comparison, dict):
        _fail("data.hydb 必须是对象")
    for group in ("stock", "hy", "hymax", "hymin"):
        if not isinstance(comparison.get(group), dict):
            _fail(f"data.hydb.{group} 必须是对象")
    metrics = []
    for metric, leaf, unit in (
        ("eps", "mgsy", "元/股"), ("revenue", "yysr", "元"),
        ("net_profit", "jlr", "元"), ("book_value_per_share", "mgjzc", "元/股"),
        ("roe_percent", "jzcsyl", "%"),
    ):
        values = {
            output: _financial_number(comparison[group].get(leaf), f"data.hydb.{group}.{leaf}",
                                      percent=unit == "%", nonnegative=metric == "revenue")
            for output, group in (("company_value", "stock"), ("industry_average", "hy"),
                                  ("industry_max", "hymax"), ("industry_min", "hymin"))
        }
        metrics.append({"metric": metric, "unit": unit, **values})
    return {
        "period": _financial_period(comparison.get("date"), "data.hydb.date"),
        "period_end": _date(comparison["stock"].get("date"), "data.hydb.stock.date"),
        "industry_name": _text(comparison.get("hyname"), "data.hydb.hyname"),
        "metrics": metrics,
    }


def info(code: str, *, timeout: float) -> dict:
    """一次读取公司简况、财务摘要、主营构成及财报行业对比。"""
    symbol = resolve_code(code, kind="stock")
    timeout = validate_timeout(timeout)
    params = {"code": symbol, "app": "official_website"}
    data = _decode(get_text(f"{INFO_ENDPOINT}?{urlencode(params)}", timeout=timeout,
                            headers=_HEADERS, source="tencent"), "jiankuang")
    _stock_identity(data, symbol)
    for block in ("gsjj", "gdgb"):
        if not isinstance(data.get(block), dict):
            _fail(f"data.{block} 必须是对象")
    blocks = {block: _rows(data.get(block), f"data.{block}")
              for block in ("ggjj", "ggzjc", "fhsp", "huigou")}
    profile, capital = data["gsjj"], data["gdgb"]
    total = capital.get("zgb_r")
    if total is None or isinstance(total, str) and total.strip() in _MISSING:
        total = capital.get("zgb")
    executives = []
    for index, raw in enumerate(blocks["ggjj"]):
        context = f"data.ggjj[{index}]"
        roles = _text(raw.get("zw"), f"{context}.zw")
        executives.append({
            "name": _text(raw.get("gg"), f"{context}.gg", required=True),
            "roles": None if roles is None else [role.strip() for role in re.split(r"[,，、]", roles) if role.strip()],
            "shares": _number(raw.get("cgs"), f"{context}.cgs", unit="股", integer=True),
            "compensation": _number(raw.get("xc"), f"{context}.xc", unit="元"),
        })
    changes = []
    for index, raw in enumerate(blocks["ggzjc"]):
        context = f"data.ggzjc[{index}]"
        changes.append({
            "announcement_date": _date(raw.get("date"), f"{context}.date"),
            "person_name": _text(raw.get("gg"), f"{context}.gg"),
            "share_change": _number(raw.get("bdl"), f"{context}.bdl", unit="股", integer=True, nonnegative=False),
            "average_price": _number(raw.get("jj"), f"{context}.jj", unit="元"),
        })
    dividends = []
    for index, raw in enumerate(blocks["fhsp"]):
        context = f"data.fhsp[{index}]"
        dividends.append({
            "period": _period_label(raw.get("nd"), f"{context}.nd"),
            "announcement_date": _date(raw.get("date"), f"{context}.date"),
            "stock_dividend_per_10": _number(raw.get("sg"), f"{context}.sg", unit="股"),
            "capitalization_per_10": _number(raw.get("zz"), f"{context}.zz", unit="股"),
            "cash_dividend_per_10": _number(raw.get("fh"), f"{context}.fh", unit="元"),
            "rights_issue_per_10": _number(raw.get("pg"), f"{context}.pg", unit="股"),
            "record_date": _date(raw.get("djr"), f"{context}.djr"),
            "ex_date": _date(raw.get("cqr"), f"{context}.cqr"),
            "description": _text(raw.get("content"), f"{context}.content"),
        })
    repurchases = []
    for index, raw in enumerate(blocks["huigou"]):
        context = f"data.huigou[{index}]"
        repurchases.append({
            "date": _date(raw.get("REP_DATE"), f"{context}.REP_DATE"),
            "quantity": _number(raw.get("REDEMPTION_QUANTITY"), f"{context}.REDEMPTION_QUANTITY", unit="股", integer=True),
            "average_price": _number(raw.get("REDEEN_AVG_PRICE"), f"{context}.REDEEN_AVG_PRICE", unit="元"),
            "currency": _text(raw.get("CURRENCY"), f"{context}.CURRENCY"),
            "fund_amount": _number(raw.get("FUND"), f"{context}.FUND", unit="元"),
            "market": _text(raw.get("MARKET"), f"{context}.MARKET"),
        })
    return {
        "code": code, "exchange": symbol[:2],
        "profile": {
            "company_name": _text(profile.get("gsmz"), "data.gsjj.gsmz"),
            "business_description": _text(profile.get("yw"), "data.gsjj.yw"),
            "issue_price": _number(profile.get("jg"), "data.gsjj.jg", unit="元"),
            "listing_date": _date(profile.get("riqi"), "data.gsjj.riqi"),
        },
        "executives": executives, "executive_share_changes": changes,
        "share_capital": {
            "total_shares": _number(total, "data.gdgb.zgb_r/zgb", unit="股", integer=True),
            "float_shares": _number(capital.get("ltgb"), "data.gdgb.ltgb", unit="股", integer=True),
        },
        "shareholder_summary": {
            "shareholder_count": _number(capital.get("gdrs"), "data.gdgb.gdrs", unit="户", integer=True),
            "average_shares_per_holder": _number(capital.get("rjcg"), "data.gdgb.rjcg", unit="股"),
            "shareholder_count_change_percent": _number(capital.get("gdrshb"), "data.gdgb.gdrshb", unit="%", nonnegative=False),
            "top10_holder_percent": _number(capital.get("gdzb"), "data.gdgb.gdzb", unit="%"),
            "top10_float_holder_percent": _number(capital.get("ltgdzb"), "data.gdgb.ltgdzb", unit="%"),
        },
        "dividends": dividends, "repurchases": repurchases,
        "financial_summary": _financial_summary(data),
        "revenue_breakdown": _revenue_breakdown(data),
        "industry_comparison": _industry_comparison(data),
    }


def float_shareholders(code: str, year: int | None = None, *, timeout: float) -> list[dict]:
    """读取来源最近报告期或指定支持年份的流通股东，保留来源持有比例。"""
    symbol = resolve_code(code, kind="stock")
    if year is not None and (type(year) is not int or not 1000 <= year <= 9999):
        raise ValueError("year 必须是四位整数或 None")
    timeout = validate_timeout(timeout)
    params = {"type": "ltgd", "_var": "v_liutonggd", "code": symbol}
    if year is not None:
        params["year"] = year
    data = _decode(get_text(f"{FLOAT_SHAREHOLDERS_ENDPOINT}?{urlencode(params)}", timeout=timeout,
                            headers=_HEADERS, source="tencent"), "ltgd", assignment=True)
    periods = _rows(data.get("data"), "data.data")
    if year is not None:
        history = data.get("history")
        if not isinstance(history, list) or any(not isinstance(item, str) or not re.fullmatch(r"[0-9]{4}", item) for item in history):
            _fail("data.history 必须是有效年份文本列表")
        if str(year) not in history:
            raise ValueError(f"来源未提供 year={year} 的流通股东数据")
    elif len(periods) > 4:
        _fail("ltgd 默认响应超过四个报告期")
    results = []
    seen_periods = set()
    for index, period in enumerate(periods):
        context = f"data.data[{index}]"
        period_end = _date(period.get("pdt"), f"{context}.pdt", required=True)
        if period_end in seen_periods:
            _fail(f"ltgd 重复报告期：{period_end}")
        seen_periods.add(period_end)
        if year is not None and int(period_end[:4]) != year:
            _fail("ltgd 返回报告期与请求年份不一致")
        rows = _rows(period.get("rows"), f"{context}.rows")
        seen_holders = set()
        for row_index, raw in enumerate(rows):
            row_context = f"{context}.rows[{row_index}]"
            name = _text(raw.get("gdmc"), f"{row_context}.gdmc", required=True)
            share_type = _text(raw.get("gfxz"), f"{row_context}.gfxz")
            identity = (name, share_type)
            if identity in seen_holders:
                _fail(f"ltgd 同报告期重复股东：{name}")
            seen_holders.add(identity)
            results.append({
                "period_end": period_end,
                "holder_name": name,
                "shares": _number(raw.get("cgsl"), f"{row_context}.cgsl", unit="股", integer=True),
                "share_type": share_type,
                "holding_percent": _number(raw.get("ltbl"), f"{row_context}.ltbl", unit="%"),
                "previous_shares": _number(raw.get("sqcgsl"), f"{row_context}.sqcgsl", unit="股", integer=True),
            })
    return sorted(results, key=lambda row: row["period_end"], reverse=True)
