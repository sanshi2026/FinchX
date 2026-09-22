"""Generate the bilingual FinchX v1 API reference from public runtime metadata.

Client signatures, Dataset definitions, Pydantic fields and the Provider
Registry are read from the package.  Examples are the one intentionally
explicit part of the metadata: business-level requirements such as whether an
endpoint needs an equity or index identity cannot be inferred safely from a
Python signature alone.
"""

from __future__ import annotations

import argparse
import inspect
import sys
import types
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from finchx.client import CLIENT_ENDPOINTS, FinchX  # noqa: E402
from finchx.computed import COMPUTED_DEVIATION_DATASET  # noqa: E402
from finchx.providers import PROVIDER_REGISTRY  # noqa: E402


class _NoopCollector:
    def fetch(self, *_args: Any, **_kwargs: Any) -> None:
        return None


_CLIENT = FinchX(collector=_NoopCollector())


MINIMUM_INPUT_ZH: dict[str, str] = {
    "instrument_id (InstrumentId or six-digit equity code) or request": "instrument_id（InstrumentId 或六位股票代码），或使用 request",
    "start_date and end_date together, or request": "同时提供 start_date 和 end_date，或使用 request",
    "none": "无",
    "request": "request",
    "request (instrumentId, tradeDate, tradeId)": "request（包含 instrumentId、tradeDate 和 tradeId）",
    "request (index instrumentId)": "request（包含指数 instrumentId）",
    "none; the default universe is CN_A_SHARE": "无；默认范围为 CN_A_SHARE",
    "request (universe, criterion, direction, limit)": "request（包含 universe、criterion、direction 和 limit）",
    "instrument_id (InstrumentId or six-digit equity code) and statement_type, or request": "instrument_id（InstrumentId 或六位股票代码）和 statement_type，或使用 request",
    "instrument (InstrumentId or six-digit equity code), or request": "instrument（InstrumentId 或六位股票代码），或使用 request",
    "instrument_id (InstrumentId or six-digit equity code), start_date, end_date, and adjustment for equity": "股票需提供 instrument_id（InstrumentId 或六位股票代码）、start_date、end_date 和 adjustment",
    "instrument_id (InstrumentId or six-digit equity code)": "instrument_id（InstrumentId 或六位股票代码）",
}

@dataclass(frozen=True)
class ExampleSpec:
    """Smallest documented valid call for one public capability."""

    code: str
    minimum_input_en: str
    minimum_input_zh: str | None = None

    def __post_init__(self) -> None:
        if self.minimum_input_zh is None:
            try:
                localized = MINIMUM_INPUT_ZH[self.minimum_input_en]
            except KeyError as exc:
                raise ValueError(f"missing zh-CN minimum input: {self.minimum_input_en}") from exc
            object.__setattr__(self, "minimum_input_zh", localized)

    def minimum_input_for(self, language: str) -> str:
        if language == "en":
            return self.minimum_input_en
        return self.minimum_input_zh


_EQUITY_IMPORT = "from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market"
_EQUITY_SETUP = '''instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)'''
_INDEX_SETUP = '''index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)'''


def _equity_call(call: str) -> str:
    return f'''from finchx import FinchX
{_EQUITY_IMPORT}

fx = FinchX()
{_EQUITY_SETUP}
result = {call}'''


def _equity_code_call(call: str) -> str:
    return f'''from finchx import FinchX

fx = FinchX()
result = {call}'''


def _index_call(call: str) -> str:
    return f'''from finchx import FinchX
{_EQUITY_IMPORT}

fx = FinchX()
{_INDEX_SETUP}
result = {call}'''


def _request_call(
    imports: str,
    request_expression: str,
    call: str,
    *,
    setup: str | None = None,
    date_import: bool = False,
) -> str:
    prefix = "from datetime import date\n" if date_import else ""
    setup_block = f"\n{setup}" if setup else ""
    return f'''{prefix}from finchx import FinchX
{imports}

fx = FinchX(){setup_block}
request = {request_expression}
result = {call}'''


EXAMPLE_SPECS: dict[str, ExampleSpec] = {
    "reference.instrument": ExampleSpec(
        _equity_code_call('fx.reference.instrument("600519")'),
        "instrument_id (InstrumentId or six-digit equity code) or request",
    ),
    "reference.trading_calendar": ExampleSpec(
        '''from datetime import date
from finchx import FinchX

fx = FinchX()
result = fx.reference.trading_calendar(
    date(2026, 9, 1),
    date(2026, 9, 30),
)''',
        "start_date and end_date together, or request",
    ),
    "market.breadth": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.breadth()""",
        "none",
    ),
    "market.broken_limit_pool": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.broken_limit_pool()""",
        "none",
    ),
    "market.consecutive_limit_up": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.consecutive_limit_up()""",
        "none",
    ),
    "market.daily_replay": ExampleSpec(
        _request_call(
            "from finchx.datasets import MarketDailyReplayRequest",
            "MarketDailyReplayRequest(requestedDate=date(2026, 9, 18))",
            "fx.market.daily_replay(request)",
            date_import=True,
        ),
        "request",
    ),
    "market.dragon_tiger_detail": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketDragonTigerDetailRequest",
            '''MarketDragonTigerDetailRequest(
    instrumentId=instrument_id,
    tradeDate=date(2026, 9, 18),
    tradeId="example-trade-id",
)''',
            "fx.market.dragon_tiger_detail(request)",
            setup=_EQUITY_SETUP,
            date_import=True,
        ),
        "request (instrumentId, tradeDate, tradeId)",
    ),
    "market.dragon_tiger_list": ExampleSpec(
        _request_call(
            "from finchx.datasets import MarketDragonTigerListRequest",
            "MarketDragonTigerListRequest(tradeDate=date(2026, 9, 18))",
            "fx.market.dragon_tiger_list(request)",
            date_import=True,
        ),
        "request",
    ),
    "market.equity_intraday": ExampleSpec(
        _equity_code_call('fx.market.equity_intraday("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.equity_intraday_5d": ExampleSpec(
        _equity_code_call('fx.market.equity_intraday_5d("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.fund_flow_daily": ExampleSpec(
        _equity_code_call('fx.market.fund_flow_daily("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.fund_flow_intraday": ExampleSpec(
        _equity_code_call('fx.market.fund_flow_intraday("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.fund_flow_snapshot": ExampleSpec(
        _equity_code_call('fx.market.fund_flow_snapshot("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.index_intraday": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import IndexIntradayRequest",
            "IndexIntradayRequest(instrumentId=index_id)",
            "fx.market.index_intraday(request)",
            setup=_INDEX_SETUP,
        ),
        "request (index instrumentId)",
    ),
    "market.index_intraday_5d": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import IndexIntraday5dRequest",
            "IndexIntraday5dRequest(instrumentId=index_id)",
            "fx.market.index_intraday_5d(request)",
            setup=_INDEX_SETUP,
        ),
        "request (index instrumentId)",
    ),
    "market.industry_comparison": ExampleSpec(
        _equity_code_call('fx.market.industry_comparison("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.instrument_sector_snapshot": ExampleSpec(
        _equity_code_call('fx.market.instrument_sector_snapshot("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.stock_keyword": ExampleSpec(
        _equity_code_call('fx.market.stock_keyword("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.limit_down_pool": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.limit_down_pool()""",
        "none",
    ),
    "market.limit_up_pool": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.limit_up_pool()""",
        "none",
    ),
    "market.ohlcv": ExampleSpec(
        '''from datetime import date
from finchx import FinchX
from finchx.datasets import KlineAdjustment

fx = FinchX()
result = fx.market.ohlcv(
    "600519",
    date(2026, 9, 1),
    date(2026, 9, 18),
    adjustment=KlineAdjustment.QFQ,
)''',
        "instrument_id (InstrumentId or six-digit equity code), start_date, end_date, and adjustment for equity",
    ),
    "market.orderbook": ExampleSpec(
        _equity_code_call('fx.market.orderbook("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.quote": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.quote()""",
        "none; the default universe is CN_A_SHARE",
    ),
    "market.quote_snapshot": ExampleSpec(
        _equity_code_call('fx.market.quote_snapshot("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.ranking": ExampleSpec(
        _request_call(
            "from finchx.datasets import InstrumentUniverse, MarketRankingRequest, RankingCriterion, RankingDirection",
            '''MarketRankingRequest(
    universe=InstrumentUniverse.CN_A_SHARE,
    criterion=RankingCriterion.TURNOVER,
    direction=RankingDirection.DESCENDING,
    limit=20,
)''',
            "fx.market.ranking(request)",
        ),
        "request (universe, criterion, direction, limit)",
    ),
    "market.sentiment": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.sentiment()""",
        "none",
    ),
    "market.strong_pool": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.strong_pool()""",
        "none",
    ),
    "market.yesterday_limit_up_pool": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.yesterday_limit_up_pool()""",
        "none",
    ),
    "fundamental.company_profile": ExampleSpec(
        _equity_code_call('fx.fundamental.company_profile("600519")'),
        "instrument_id (InstrumentId or six-digit equity code) or request",
    ),
    "fundamental.financial_summary": ExampleSpec(
        _equity_code_call('fx.fundamental.financial_summary("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "fundamental.industry_comparison": ExampleSpec(
        _equity_code_call('fx.fundamental.industry_comparison("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "fundamental.revenue_breakdown": ExampleSpec(
        _equity_code_call('fx.fundamental.revenue_breakdown("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "financial.statements": ExampleSpec(
        _equity_code_call('fx.financial.statements("600519", "income_statement")'),
        "instrument_id (InstrumentId or six-digit equity code) and statement_type, or request",
    ),
    "news.search": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.news.search("600519")""",
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "disclosure.search": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.disclosure.search("600519")""",
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "ownership.capital_snapshot": ExampleSpec(
        _equity_code_call('fx.ownership.capital_snapshot("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "ownership.float_holder": ExampleSpec(
        _equity_code_call('fx.ownership.float_holder("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "ownership.holder_summary_snapshot": ExampleSpec(
        _equity_code_call('fx.ownership.holder_summary_snapshot("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "company.executive_share_change": ExampleSpec(
        _equity_code_call('fx.company.executive_share_change("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "company.executive_snapshot": ExampleSpec(
        _equity_code_call('fx.company.executive_snapshot("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "corporate_action.dividend": ExampleSpec(
        _equity_code_call('fx.corporate_action.dividend("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "corporate_action.repurchase": ExampleSpec(
        _equity_code_call('fx.corporate_action.repurchase("600519")'),
        "instrument (InstrumentId or six-digit equity code), or request",
    ),
    "market.deviation": ExampleSpec(
        _equity_code_call('fx.market.deviation("600519", windows=(10, 30))'),
        "instrument_id (InstrumentId or six-digit equity code)",
    ),
}


def endpoint_key(endpoint: Any) -> str:
    return f"{endpoint.namespace}.{endpoint.method}"


def all_endpoint_keys() -> tuple[str, ...]:
    return tuple(endpoint_key(endpoint) for endpoint in CLIENT_ENDPOINTS) + ("market.deviation",)


def validate_example_inventory() -> None:
    expected = set(all_endpoint_keys())
    actual = set(EXAMPLE_SPECS)
    if actual != expected:
        raise RuntimeError(
            f"example metadata mismatch: missing={sorted(expected - actual)!r}, "
            f"extra={sorted(actual - expected)!r}"
        )


def annotation_text(annotation: Any) -> str:
    """Render annotations without leaking Pydantic FieldInfo repr addresses."""

    if annotation is inspect.Signature.empty:
        return "—"
    if isinstance(annotation, str):
        return annotation.strip("'")
    if annotation is type(None):
        return "None"
    origin = get_origin(annotation)
    if origin is Annotated:
        return annotation_text(get_args(annotation)[0])
    if origin is Literal:
        return "Literal[" + ", ".join(repr(value) for value in get_args(annotation)) + "]"
    if origin is Union or isinstance(annotation, types.UnionType):
        return " | ".join(annotation_text(item) for item in get_args(annotation))
    if origin is not None:
        name = getattr(origin, "__name__", str(origin).replace("typing.", ""))
        return f"{name}[{', '.join(annotation_text(item) for item in get_args(annotation))}]"
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def default_text(value: Any) -> str:
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    return repr(value)


def field_default_text(field: Any) -> str:
    """Render a Pydantic default without exposing its internal sentinel."""

    if field.default_factory is not None:
        factory_name = getattr(field.default_factory, "__name__", type(field.default_factory).__name__)
        return f"default_factory={factory_name}"
    return default_text(field.default)


def table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    def cell(value: str) -> str:
        return value.replace("|", r"\|")

    lines = [
        "| " + " | ".join(cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


DESCRIPTION_ZH: dict[str, str] = {
    "A non-negative whole number of shares.": "非负整数股数。",
    "A ratio fraction, not percentage points: 4.24% is 0.0424.": "比例小数，而不是百分点：4.24% 表示为 0.0424。",
    "Aigupiao source-defined sentiment temperature; not a physical temperature or ratio.": "Aigupiao 定义的情绪温度；不是物理温度或比例。",
    "Amount traded at the limit-down price in CNY.": "以跌停价成交的金额，单位为 CNY。",
    "Amount traded during this minute, in CNY.": "该分钟成交金额，单位为 CNY。",
    "CNY per share. Tencent gsjj.jg is retained as the source candidate.": "单位为每股 CNY；保留 Tencent gsjj.jg 作为来源候选值。",
    "Deprecated compatibility input; this Provider returns the latest snapshot and does not support historical selection.": "已弃用的兼容输入；该 Provider 只返回最新快照，不支持历史日期选择。",
    "Change from previous close as a ratio fraction; 3% is 0.03.": "相对前收盘价的变动比例小数；3% 表示为 0.03。",
    "Cumulative session amount in CNY.": "本交易时段累计成交金额，单位为 CNY。",
    "Cumulative session volume in shares.": "本交易时段累计成交股数。",
    "Current limit-up price in CNY per share.": "当前涨停价，单位为每股 CNY。",
    "Current observed source date, not the prior limit-up event date.": "当前观测到的来源日期，不是前一涨停事件日期。",
    "Current-session amplitude as a ratio fraction.": "当前交易日振幅比例小数。",
    "Current-session limit-up price in CNY per share.": "当前交易日涨停价，单位为每股 CNY。",
    "Current-session price in CNY per share.": "当前交易日价格，单位为每股 CNY。",
    "Current-session ratio fraction.": "当前交易日比例小数。",
    "Current-session traded amount in CNY.": "当前交易日成交金额，单位为 CNY。",
    "Current-session turnover ratio fraction.": "当前交易日换手率比例小数。",
    "Daily close in CNY per share.": "每日收盘价，单位为每股 CNY。",
    "Derived from Tencent rows array order.": "根据 Tencent rows 数组顺序推导。",
    "Derived from bdms=1 after multi-stock adjacent-period validation.": "根据多股票相邻期间校验后的 bdms=1 推导。",
    "Derived from the source array order.": "根据来源数组顺序推导。",
    "EastMoney-reported dynamic P/E; source calculation details are unspecified.": "EastMoney 报告的动态 P/E；来源计算细节未提供。",
    "EastMoney-reported limit-down queued amount in CNY.": "EastMoney 报告的跌停排队金额，单位为 CNY。",
    "Exact decimal in the source price unit (CNY per share for equities; index points for indices).": "来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。",
    "Exact share count per holder; Tencent rjcg display units are normalized to shares.": "每位持有人的精确股数；Tencent rjcg 展示单位已换算为股。",
    "Intraday price amplitude, stored as a ratio fraction.": "盘中价格振幅，以比例小数存储。",
    "Latest price in CNY per share.": "最新价格，单位为每股 CNY。",
    "Monetary amount in CNY.": "金额，单位为 CNY。",
    "Non-negative volume ratio in times; 2.35 represents 2.35x.": "非负成交量倍数；2.35 表示 2.35 倍。",
    "Number of listed stocks in this return bucket.": "该返回区间内的上市股票数量。",
    "Previous-session first limit-up time, market-local HH:MM:SS.": "前一交易日首次涨停时间，使用市场本地 HH:MM:SS。",
    "Price change over the source-designated 52-week period, as a ratio fraction.": "来源指定 52 周期间的价格变动，以比例小数表示。",
    "Price per share; currency is CNY.": "每股价格；币种为 CNY。",
    "Ratio fraction.": "比例小数。",
    "Ratio fraction; -10% is -0.10.": "比例小数；-10% 表示为 -0.10。",
    "Ratio fraction; 10% is 0.10.": "比例小数；10% 表示为 0.10。",
    "Ratio fraction; 12% is 0.12.": "比例小数；12% 表示为 0.12。",
    "Ratio fraction; 15% is 0.15.": "比例小数；15% 表示为 0.15。",
    "Ratio fraction; 19% is 0.19.": "比例小数；19% 表示为 0.19。",
    "Ratio fraction; 20% is 0.20.": "比例小数；20% 表示为 0.20。",
    "Ratio fraction; 31% is 0.31.": "比例小数；31% 表示为 0.31。",
    "Ratio fraction; 35% is 0.35.": "比例小数；35% 表示为 0.35。",
    "Ratio fraction; 5% is 0.05.": "比例小数；5% 表示为 0.05。",
    "Session high in CNY per share.": "交易时段最高价，单位为每股 CNY。",
    "Session low in CNY per share.": "交易时段最低价，单位为每股 CNY。",
    "Session open in CNY per share.": "交易时段开盘价，单位为每股 CNY。",
    "Signed absolute price change in CNY per share.": "带符号的绝对价格变动，单位为每股 CNY。",
    "Signed price change in CNY per share.": "带符号的价格变动，单位为每股 CNY。",
    "Source forecast, not observed turnover.": "来源预测值，不是观测到的换手率。",
    "Source market-local time, HH:MM; values are cumulative from open.": "来源市场本地时间，格式为 HH:MM；数值从开盘起累计。",
    "Source price in CNY per share.": "来源价格，单位为每股 CNY。",
    "Source trading time in HHMM normalized to HH:MM; not capturedAt.": "来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。",
    "Source trading-date label; not FinchX capturedAt.": "来源交易日期标签；不是 FinchX capturedAt。",
    "Source volume ratio as a dimensionless multiple.": "来源成交量倍数，为无量纲倍数。",
    "Source-defined previous broken-limit performance ratio.": "来源定义的前期炸板表现比例。",
    "Source-defined previous consecutive-limit-up group performance ratio.": "来源定义的前期连板组表现比例。",
    "Source-defined previous limit-up group performance ratio.": "来源定义的前期涨停组表现比例。",
    "Source-defined promotion ratio; FinchX does not reproduce the denominator.": "来源定义的晋级比例；FinchX 不复现其分母。",
    "Source-defined ratio; FinchX does not reproduce the denominator.": "来源定义的比例；FinchX 不复现其分母。",
    "Source-designated 10d price change, stored as a ratio fraction.": "来源指定的 10 日价格变动，以比例小数存储。",
    "Source-designated 20d price change, stored as a ratio fraction.": "来源指定的 20 日价格变动，以比例小数存储。",
    "Source-designated 5d price change, stored as a ratio fraction.": "来源指定的 5 日价格变动，以比例小数存储。",
    "Source-designated 60d price change, stored as a ratio fraction.": "来源指定的 60 日价格变动，以比例小数存储。",
    "Source-reported change in turnover amount versus the prior day.": "来源报告的成交金额相对前一日的变动。",
    "Source-reported quote time, separate from FinchX capturedAt.": "来源报告的行情时间，与 FinchX capturedAt 分开。",
    "Tencent gdrshb, normalized from percentage points to a ratio; not an absolute count delta.": "Tencent gdrshb 已从百分点规范化为比例；不是绝对数量差。",
    "Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here.": "Tencent mgsy，单位为每股 CNY；此处未提供报告期语义。",
    "Tencent source cumulative traded amount in CNY, unchanged from source.": "Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。",
    "Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100).": "Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。",
    "Tencent zdf converted from percentage points to a ratio fraction.": "Tencent zdf 已从百分点转换为比例小数。",
    "Tencent zsz converted from 100 million CNY to CNY.": "Tencent zsz 已从亿元转换为 CNY。",
    "Total market capitalization in CNY.": "总市值，单位为 CNY。",
    "Trade date reported by EastMoney.": "EastMoney 报告的交易日期。",
    "Trading date reported by Tencent, not FinchX capture time.": "Tencent 报告的交易日期，不是 FinchX 抓取时间。",
    "Volume traded during this minute, in whole shares.": "该分钟成交量，单位为整股。",
    "Year-to-date price change, stored as a ratio fraction.": "年初至今价格变动，以比例小数存储。",
}





SUMMARY_ZH: dict[str, str] = {
    "reference.instrument": "获取标的规范身份和名称。",
    "reference.trading_calendar": "获取日期范围内的 A 股交易日标记。",
    "market.breadth": "获取当前市场涨跌家数分布。",
    "market.broken_limit_pool": "获取最新炸板池快照。",
    "market.consecutive_limit_up": "获取连板股快照。",
    "market.daily_replay": "获取指定日期的每日复盘数据。",
    "market.dragon_tiger_detail": "获取指定标的的龙虎榜明细。",
    "market.dragon_tiger_list": "获取指定交易日的龙虎榜列表。",
    "market.equity_intraday": "获取单个股票交易日内分钟数据。",
    "market.equity_intraday_5d": "获取股票五日分钟数据。",
    "market.fund_flow_daily": "获取单个标的的每日资金流数据。",
    "market.fund_flow_intraday": "获取单个标的的盘中资金流数据。",
    "market.fund_flow_snapshot": "获取资金流快照。",
    "market.index_intraday": "获取单个指数交易日内分钟数据。",
    "market.index_intraday_5d": "获取指数五日分钟数据。",
    "market.industry_comparison": "获取市场行业比较数据。",
    "market.instrument_sector_snapshot": "获取标的所属板块及板块快照。",
    "market.stock_keyword": "获取数据源提供的股票关键词。",
    "market.limit_down_pool": "获取最新跌停池快照。",
    "market.limit_up_pool": "获取最新涨停池快照。",
    "market.ohlcv": "获取单个标的的日线 OHLCV 数据。",
    "market.orderbook": "获取单个标的的盘口数据。",
    "market.quote": "获取选定股票范围的行情快照。",
    "market.quote_snapshot": "获取单个标的的行情快照。",
    "market.ranking": "获取指定条件的市场排行。",
    "market.sentiment": "获取市场情绪快照。",
    "market.strong_pool": "获取最新强势股池快照。",
    "market.yesterday_limit_up_pool": "获取最新昨日涨停池快照。",
    "fundamental.company_profile": "获取公司概况。",
    "fundamental.financial_summary": "获取公司财务摘要。",
    "fundamental.industry_comparison": "获取公司与行业的基本面比较。",
    "fundamental.revenue_breakdown": "获取公司收入构成。",
    "financial.statements": "获取财务报表数据。",
    "news.search": "搜索个股新闻并返回文档引用。",
    "disclosure.search": "搜索个股公告并返回公告引用。",
    "ownership.capital_snapshot": "获取股本快照。",
    "ownership.float_holder": "获取流通股东数据。",
    "ownership.holder_summary_snapshot": "获取股东汇总快照。",
    "company.executive_share_change": "获取高管持股变动。",
    "company.executive_snapshot": "获取高管快照。",
    "corporate_action.dividend": "获取分红除权记录。",
    "corporate_action.repurchase": "获取回购记录。",
    "market.deviation": "计算经过审计的基于收盘价的偏离值。",
}

# The renderer below is intentionally organized around the reader-facing
# document, not the historical namespace layout above.  The metadata helpers
# and ExampleSpec inventory remain shared with the regression tests.
_COMPUTED_CAPABILITY_KEYS: tuple[str, ...] = ("market.deviation",)

_CONDITIONAL_REQUEST_ENDPOINTS = frozenset({
    "reference.instrument",
    "reference.trading_calendar",
    "market.ohlcv",
    "fundamental.company_profile",
    "financial.statements",
    "news.search",
    "disclosure.search",
})

_LATEST_POOL_ENDPOINTS = frozenset({
    "market.limit_up_pool",
    "market.limit_down_pool",
    "market.broken_limit_pool",
    "market.strong_pool",
    "market.yesterday_limit_up_pool",
})

_GENERIC_NESTED_MODELS = frozenset({
    "InstrumentId",
    "Provenance",
    "Quality",
    "Source",
    "SourceReference",
    "StandardRecord",
})


@dataclass(frozen=True)
class CategorySpec:
    title_en: str
    title_zh: str
    endpoint_keys: tuple[str, ...]


CATEGORY_SPECS: tuple[CategorySpec, ...] = (
    CategorySpec("Reference & Calendar", "基础参考与交易日历", (
        "reference.instrument", "reference.trading_calendar",
    )),
    CategorySpec("Market Overview & Pools", "市场概览、排名与股票池", (
        "market.breadth", "market.broken_limit_pool", "market.consecutive_limit_up",
        "market.daily_replay", "market.dragon_tiger_detail", "market.dragon_tiger_list",
        "market.limit_down_pool", "market.limit_up_pool", "market.quote", "market.ranking",
        "market.sentiment", "market.strong_pool", "market.yesterday_limit_up_pool",
    )),
    CategorySpec("Single-Security Market Data", "单证券行情、盘口、K 线、资金流与板块", (
        "market.equity_intraday", "market.equity_intraday_5d", "market.fund_flow_daily",
        "market.fund_flow_intraday", "market.fund_flow_snapshot", "market.index_intraday",
        "market.index_intraday_5d", "market.industry_comparison",
        "market.instrument_sector_snapshot", "market.stock_keyword", "market.ohlcv",
        "market.orderbook", "market.quote_snapshot",
    )),
    CategorySpec("Fundamentals & Financials", "公司基本面与财务", (
        "fundamental.company_profile", "fundamental.financial_summary",
        "fundamental.industry_comparison", "fundamental.revenue_breakdown",
        "financial.statements",
    )),
    CategorySpec("News & Disclosures", "新闻与公告", (
        "news.search", "disclosure.search",
    )),
    CategorySpec("Ownership, Executives & Corporate Actions", "股东、管理层与公司行动", (
        "ownership.capital_snapshot", "ownership.float_holder",
        "ownership.holder_summary_snapshot", "company.executive_share_change",
        "company.executive_snapshot", "corporate_action.dividend",
        "corporate_action.repurchase",
    )),
    CategorySpec("Computed Analytics", "计算型分析", _COMPUTED_CAPABILITY_KEYS),
)


def provider_endpoint_keys() -> tuple[str, ...]:
    return tuple(endpoint_key(endpoint) for endpoint in CLIENT_ENDPOINTS)


def computed_endpoint_keys() -> tuple[str, ...]:
    return _COMPUTED_CAPABILITY_KEYS


def all_endpoint_keys() -> tuple[str, ...]:
    return provider_endpoint_keys() + computed_endpoint_keys()


def validate_example_inventory() -> None:
    expected = set(all_endpoint_keys())
    actual = set(EXAMPLE_SPECS)
    if actual != expected:
        raise RuntimeError(
            f"example metadata mismatch: missing={sorted(expected - actual)!r}, "
            f"extra={sorted(actual - expected)!r}"
        )


def validate_category_inventory() -> None:
    expected = set(all_endpoint_keys())
    actual = [key for spec in CATEGORY_SPECS for key in spec.endpoint_keys]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise RuntimeError(
            f"category metadata mismatch: missing={sorted(expected - set(actual))!r}, "
            f"extra={sorted(set(actual) - expected)!r}"
        )


def field_description_text(field: Any, *, language: str, fallback: str) -> str:
    if not field.description:
        return fallback
    if language == "en":
        return field.description
    return DESCRIPTION_ZH.get(field.description, fallback)


_COMMON_FIELD_DESCRIPTIONS = {
    "instrumentId": ("Instrument identifier.", "证券标识。"),
    "instrument_id": ("Instrument identifier.", "证券标识。"),
    "name": ("Name.", "名称。"),
    "tradeDate": ("Trade date.", "交易日期。"),
    "trade_date": ("Trade date.", "交易日期。"),
    "date": ("Date.", "日期。"),
}


def common_field_description(name: str, *, language: str) -> str | None:
    descriptions = _COMMON_FIELD_DESCRIPTIONS.get(name)
    if descriptions is None:
        return None
    return descriptions[0] if language == "en" else descriptions[1]


def nested_model_types(annotation: Any) -> set[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {annotation}
    nested: set[type[BaseModel]] = set()
    for arg in get_args(annotation):
        nested.update(nested_model_types(arg))
    return nested


def nested_models(model: type[BaseModel]) -> list[type[BaseModel]]:
    found: list[type[BaseModel]] = []
    seen = {model}
    pending = list(model.model_fields.values())
    while pending:
        field = pending.pop(0)
        for child in sorted(nested_model_types(field.annotation), key=lambda item: item.__name__):
            if child in seen or child.__name__ in _GENERIC_NESTED_MODELS:
                continue
            seen.add(child)
            found.append(child)
            pending.extend(child.model_fields.values())
    return found


def output_field_rows(
    model: type[BaseModel],
    *,
    language: str,
    exclude_fields: set[str] | frozenset[str] = frozenset(),
) -> list[tuple[str, str, str]]:
    fallback = "—"
    rows = []
    for name, field in model.model_fields.items():
        if name in exclude_fields or field.alias in exclude_fields:
            continue
        description = field_description_text(field, language=language, fallback=fallback)
        if not field.description:
            description = common_field_description(field.alias or name, language=language) or fallback
        rows.append((field.alias or name, annotation_text(field.annotation), description))
    return rows


_REQUEST_FIELD_ZH = {
    "instrument_id": "证券标识。", "start_date": "包含在内的开始日期。",
    "end_date": "包含在内的结束日期。", "market": "市场范围。",
    "trade_date": "交易日期。", "requested_date": "请求日期。",
    "trade_id": "龙虎榜交易标识。", "statement_type": "报表类型。",
    "period_end": "报告期结束日期。", "max_periods": "最多返回的报告期数量。",
    "page": "从 1 开始的页码。", "page_size": "单页数量。",
    "max_results": "最多返回的结果数。", "since": "时间范围起点。",
    "until": "时间范围终点。", "sort": "排序方式。", "categories": "公告分类。",
    "universe": "查询范围。", "criterion": "排行指标。", "direction": "排行方向。",
    "limit": "返回数量上限。", "adjustment": "K 线复权方式。",
}


def request_field_rows(
    model: type[BaseModel] | None,
    *,
    language: str,
    exclude_fields: set[str] | frozenset[str] = frozenset(),
) -> list[tuple[str, str, str, str, str]]:
    if model is None:
        return []
    required = "Required" if language == "en" else "必填"
    optional = "Optional" if language == "en" else "可选"
    rows = []
    for name, field in model.model_fields.items():
        if name in exclude_fields or field.alias in exclude_fields:
            continue
        label = field.alias or name
        if field.alias and field.alias != name:
            label = f"{field.alias} (`{name}`)"
        if field.description:
            description = field_description_text(field, language=language, fallback="—")
        else:
            description = common_field_description(field.alias or name, language=language)
            if description is None:
                description = _REQUEST_FIELD_ZH.get(name, "—" if language == "en" else "—")
        rows.append((
            label,
            annotation_text(field.annotation),
            required if field.is_required() else optional,
            "—" if field.is_required() else field_default_text(field),
            description,
        ))
    return rows


def parameter_required(endpoint_key_value: str, name: str, parameter: inspect.Parameter, *, language: str) -> str:
    if parameter.default is inspect.Signature.empty:
        return "Required" if language == "en" else "必填"
    if name == "request":
        if endpoint_key_value in _CONDITIONAL_REQUEST_ENDPOINTS:
            return "Alternative to convenience inputs" if language == "en" else "便捷参数的替代"
        return "Optional" if language == "en" else "可选"
    if name in {"instrument_id", "start_date", "end_date", "instrument", "statement_type"}:
        return "Required without request" if language == "en" else "无 request 时必填"
    if name == "adjustment":
        return "Required for equities; omit for indexes" if language == "en" else "股票必填；指数省略"
    return "Optional" if language == "en" else "可选"


def parameter_description(name: str, *, language: str) -> str:
    english = {
        "request": "Typed request model for the full request shape.",
        "instrument_id": "InstrumentId or a six-digit A-share code.",
        "instrument": "InstrumentId or a six-digit A-share code.",
        "start_date": "Inclusive start date.", "end_date": "Inclusive end date.",
        "market": "Market scope; the default is Market.CN_A.",
        "adjustment": "Kline adjustment mode.",
        "statement_type": "balance_sheet, income_statement, or cash_flow_statement.",
        "period_end": "Optional report-period end date.", "max_periods": "Optional maximum number of report periods.",
        "page": "One-based page number.", "page_size": "Page size.", "max_results": "Optional result cap.",
        "since": "Optional inclusive lower time bound.", "until": "Optional inclusive upper time bound.",
        "sort": "published_desc or published_asc.", "categories": "Optional disclosure category list.",
        "universe": "Selection scope.", "windows": "Deviation windows, in trading sessions.",
        "as_of": "Optional completed-session date.", "window_convention": "Deviation window interpretation.",
    }
    chinese = {
        "request": "完整的类型化 request 模型。", "instrument_id": "InstrumentId 或六位 A 股代码。",
        "instrument": "InstrumentId 或六位 A 股代码。", "start_date": "包含在内的开始日期。",
        "end_date": "包含在内的结束日期。", "market": "市场范围；默认是 Market.CN_A。",
        "adjustment": "K 线复权方式。", "statement_type": "balance_sheet、income_statement 或 cash_flow_statement。",
        "period_end": "可选的报告期结束日期。", "max_periods": "可选的最大报告期数量。",
        "page": "从 1 开始的页码。", "page_size": "单页数量。", "max_results": "可选的结果上限。",
        "since": "可选的时间范围起点。", "until": "可选的时间范围终点。",
        "sort": "published_desc 或 published_asc。", "categories": "可选的公告分类列表。",
        "universe": "查询范围。", "windows": "以交易时段计的偏离窗口。",
        "as_of": "可选的已完成交易时段日期。", "window_convention": "偏离窗口解释方式。",
    }
    return (english if language == "en" else chinese).get(name, "Parameter." if language == "en" else "参数。")


def summary_for(key: str, method: Any, *, language: str) -> str:
    if language == "zh":
        return SUMMARY_ZH.get(key, "公开数据接口。")
    doc = inspect.getdoc(method)
    summary = doc.split("\n")[0] if doc else "Provides the dataset returned by this interface."
    for phrase in (" and return it in a FetchResult", " in a FetchResult"):
        if summary.endswith(phrase + "."):
            summary = summary[: -len(phrase) - 1] + "."
    return summary


def request_alias_note(key: str, *, language: str) -> str | None:
    if key != "fundamental.industry_comparison":
        return None
    if language == "en":
        return "The signature uses the local alias `FundamentalIndustryComparisonRequest`; the request model is `finchx.datasets.IndustryComparisonRequest`."
    return "签名中的局部别名是 `FundamentalIndustryComparisonRequest`；request 模型是 `finchx.datasets.IndustryComparisonRequest`。"


def providers_for(dataset: Any) -> tuple[str, ...]:
    return tuple(spec.provider_id for spec in PROVIDER_REGISTRY.providers_for(dataset))


def _method_for(key: str) -> Any:
    namespace, method_name = key.split(".", 1)
    return getattr(getattr(_CLIENT, namespace), method_name)


def _request_exclusions(key: str) -> frozenset[str]:
    return frozenset({"trade_date", "tradeDate"}) if key in _LATEST_POOL_ENDPOINTS else frozenset()


def _parameter_rows(key: str, method: Any, request_model: type[BaseModel] | None, *, language: str) -> list[tuple[str, str, str, str, str]]:
    request_rows = request_field_rows(request_model, language=language, exclude_fields=_request_exclusions(key))
    rows = []
    for name, parameter in inspect.signature(method).parameters.items():
        if name in {"provider", "use_cache"}:
            continue
        if name == "request" and not request_rows and parameter.default is not inspect.Signature.empty:
            continue
        rows.append((
            name,
            annotation_text(parameter.annotation),
            parameter_required(key, name, parameter, language=language),
            "—" if parameter.default is inspect.Signature.empty else default_text(parameter.default),
            parameter_description(name, language=language),
        ))
    return rows


def _output_sections(model: type[BaseModel], *, language: str, key: str) -> list[str]:
    if language == "en":
        lines = ["**Output fields**", "", f"Data model: `{model.__name__}`", ""]
        rows = output_field_rows(model, language=language)
        lines.append(table(("Field", "Type", "Meaning"), rows) if rows else "No business fields.")
        nested_heading = "Nested business model"
        nested_separator = ":"
    else:
        lines = ["**输出字段**", "", f"数据模型：`{model.__name__}`", ""]
        rows = output_field_rows(model, language=language)
        lines.append(table(("字段", "类型", "含义"), rows) if rows else "无业务字段。")
        nested_heading = "嵌套业务模型"
        nested_separator = "："
    for nested in nested_models(model):
        nested_rows = output_field_rows(nested, language=language)
        lines += ["", f"{nested_heading}{nested_separator} `{nested.__name__}`", ""]
        lines.append(table(("Field", "Type", "Meaning"), nested_rows) if language == "en" else table(("字段", "类型", "含义"), nested_rows))
    return lines


def _interface_block(key: str, method: Any, request_model: type[BaseModel] | None, data_model: type[BaseModel], providers: tuple[str, ...], *, language: str, computed: bool = False) -> list[str]:
    example = EXAMPLE_SPECS[key]
    signature = str(inspect.signature(method))
    request_rows = request_field_rows(request_model, language=language, exclude_fields=_request_exclusions(key))
    request_parameter = inspect.signature(method).parameters.get("request")
    show_request_fields = bool(request_rows) and request_parameter is not None and request_parameter.default is inspect.Signature.empty
    if not show_request_fields:
        request_rows = []
    alias_note = request_alias_note(key, language=language)
    parameter_rows = _parameter_rows(key, method, request_model, language=language)
    if language == "en":
        parameter_table = table(("Parameter", "Type", "Required / mode", "Default", "Meaning"), parameter_rows) if parameter_rows else "None."
        request_section = (["", f"**Request fields** — `{request_model.__name__}`", "", table(("Field", "Type", "Required", "Default", "Meaning"), request_rows)] if request_rows else [])
        data_source = "Computed locally from `market.ohlcv` and `reference.trading_calendar`; no direct Provider." if computed else ", ".join(f"`{provider}`" for provider in providers) or "—"
        lines = [f"### `fx.{key}(...)`", "", "**What it provides**", summary_for(key, method, language=language), "", "**Data source**", data_source, "", "**Call**", "", "```python", f"fx.{key}{signature}", "```", "", "**Example**", "", f"<!-- api-example: {key} -->", "```python", example.code, "```", "", "**Parameters**", "", parameter_table]
    else:
        parameter_table = table(("参数", "类型", "必填 / 模式", "默认值", "含义"), parameter_rows) if parameter_rows else "无。"
        request_section = (["", f"**Request 字段** — `{request_model.__name__}`", "", table(("字段", "类型", "必填", "默认值", "含义"), request_rows)] if request_rows else [])
        data_source = "由 `market.ohlcv` 和 `reference.trading_calendar` 在本地计算；无直接 Provider。" if computed else ", ".join(f"`{provider}`" for provider in providers) or "—"
        lines = [f"### `fx.{key}(...)`", "", "**提供什么数据**", summary_for(key, method, language=language), "", "**数据源**", data_source, "", "**调用方式**", "", "```python", f"fx.{key}{signature}", "```", "", "**示例**", "", f"<!-- api-example: {key} -->", "```python", example.code, "```", "", "**参数**", "", parameter_table]
    if alias_note:
        request_section += ["", "**Naming note**" if language == "en" else "**命名说明**", alias_note]
    lines += request_section + ["", *_output_sections(data_model, language=language, key=key), ""]
    return lines


def endpoint_block(endpoint: Any, *, language: str) -> list[str]:
    key = endpoint_key(endpoint)
    return _interface_block(key, _method_for(key), endpoint.request_type, endpoint.dataset.data_type, providers_for(endpoint.dataset), language=language)


def computed_block(*, language: str) -> list[str]:
    return _interface_block("market.deviation", _CLIENT.market.deviation, COMPUTED_DEVIATION_DATASET.request_type, COMPUTED_DEVIATION_DATASET.data_type, (), language=language, computed=True)


def category_index(*, language: str) -> list[str]:
    endpoint_by_key = {endpoint_key(endpoint): endpoint for endpoint in CLIENT_ENDPOINTS}
    if language == "en":
        lines = ["## 3. Interface overview", "", "The index groups all public capabilities by the question they answer.", ""]
        headers = ("Interface", "Purpose", "Provider")
    else:
        lines = ["## 3. 接口总览", "", "下面按用户要解决的问题分组，覆盖全部公开能力。", ""]
        headers = ("接口", "用途", "Provider")
    for spec in CATEGORY_SPECS:
        rows = []
        for key in spec.endpoint_keys:
            if key in endpoint_by_key:
                endpoint = endpoint_by_key[key]
                providers = providers_for(endpoint.dataset)
                method = _method_for(key)
            else:
                providers = ()
                method = _CLIENT.market.deviation
            rows.append((f"`fx.{key}(...)`", summary_for(key, method, language=language), ", ".join(f"`{provider}`" for provider in providers) or "—"))
        title = spec.title_en if language == "en" else spec.title_zh
        lines += [f"### {title}", "", table(headers, rows), ""]
    return lines


_QUICK_START_CODE = """from datetime import date
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot("600519")
calendar = fx.reference.trading_calendar(date(2026, 9, 1), date(2026, 9, 30))
pool = fx.market.broken_limit_pool()
news = fx.news.search("600519")

print(result)
rows = result.to_dicts()
df = result.to_pandas()
"""


def _intro(*, language: str, provider_count: int, computed_count: int, capability_count: int) -> list[str]:
    if language == "en":
        return [
            "# FinchX Data API Reference", "", "English | [简体中文](DATA_API_REFERENCE.zh-CN.md)", "",
            f"This document covers {provider_count} data interfaces + {computed_count} computed capability = {capability_count} public capabilities.", "",
            "## 1. What FinchX is / Architecture overview", "",
            "FinchX is a small client for normalized Chinese market data. You call one public Client; FinchX validates the request, fetches a source-backed dataset, and returns one consistent result shape.", "",
            table(("Layer", "What it does"), [("Client", "`FinchX()` is the user-facing entry point."), ("Dataset", "Defines the stable request and business-data schema."), ("Provider", "Implements one real external data source."), ("Collector", "Routes the request to a Provider and builds `FetchResult`."), ("FetchResult", "Shows business data first; audit fields remain on `provider`, `provenance`, `attempts`, `warnings`, and `cache_hit`.")]), "",
            "Single-equity convenience inputs accept a six-digit code such as `600519`. Use `InstrumentId` when the identity is complex or ambiguous.", "",
            "## 2. Quick start", "", "```python", _QUICK_START_CODE, "```", "",
            "`print(result)` shows a short business summary. Use `result.to_dicts()` for rows and `result.to_pandas()` for a DataFrame. pandas is optional; without it, `to_pandas()` gives an installation message.", "",
        ]
    return [
        "# FinchX 数据 API 参考", "", "[English](DATA_API_REFERENCE.md) | 简体中文", "",
        f"本文档覆盖 {provider_count} 个数据接口 + {computed_count} 个计算能力 = {capability_count} 个公开能力。", "",
        "## 1. FinchX 是什么 / 架构概览", "",
        "FinchX 是一个面向中国市场数据的统一客户端。用户调用一个公开 Client；FinchX 校验请求、访问数据源，并返回统一格式的结果。", "",
        table(("层次", "作用"), [("Client", "用户调用入口：`FinchX()`。"), ("Dataset", "定义稳定的请求模型和业务数据结构。"), ("Provider", "实现一个真实的外部数据源。"), ("Collector", "把请求路由到 Provider，并生成 `FetchResult`。"), ("FetchResult", "默认先展示业务数据；`provider`、`provenance`、`attempts`、`warnings`、`cache_hit` 保留为审计属性。")]), "",
        "单证券便捷调用优先使用 `600519` 这样的六位代码。标的复杂或有歧义时，请使用 `InstrumentId`。", "",
        "## 2. 快速开始", "", "```python", _QUICK_START_CODE, "```", "",
        "`print(result)` 显示简短的业务摘要；`result.to_dicts()` 返回行字典；`result.to_pandas()` 返回 DataFrame。pandas 是可选依赖；未安装时调用 `to_pandas()` 会给出安装提示。", "",
    ]


def _shared_notes(*, language: str) -> list[str]:
    if language == "en":
        return [
            "## 5. Shared notes", "", "### Security input rules", "",
            "- `6xxxxx` is interpreted as an SSE equity.", "- `0xxxxx` and `3xxxxx` are interpreted as SZSE equities.", "- Bare codes beginning with `4`, `8`, or `9` are not guessed; use an explicit `InstrumentId`.", "- Indexes and other ambiguous identities require an explicit `InstrumentId`.", "",
            "### Common parameters", "",
            table(("Parameter", "Meaning"), [
                ("`provider`", "Optional. Pin a Provider explicitly; failures are not silently redirected."),
                ("`use_cache`", "Optional. Controls the configured cache policy; `None` uses the default configuration."),
            ]), "",
            "### Provider and warnings", "", "Pass `provider=` to pin a Provider explicitly. `result.warnings` contains recoverable quality or compatibility issues, such as a skipped News row with schema drift.", "",
            "### Latest snapshot pools", "", "`limit_up_pool`, `limit_down_pool`, `broken_limit_pool`, `strong_pool`, and `yesterday_limit_up_pool` return the latest snapshot only. They do not support historical date queries.", "",
            "**Deprecated compatibility:** legacy request models may retain an optional `tradeDate` field; the current Client rejects historical selection. Do not use it in new code.", "",
            "The documents are generated from the live `CLIENT_ENDPOINTS`, Dataset models, Provider Registry, and computed capability metadata.",
        ]
    return [
        "## 5. 通用说明", "", "### 证券输入规则", "",
        "- `6xxxxx` 自动识别为 SSE 股票。", "- `0xxxxx` 和 `3xxxxx` 自动识别为 SZSE 股票。", "- 以 `4`、`8` 或 `9` 开头的裸代码不会自动猜测；请显式传入 `InstrumentId`。", "- 指数和其他有歧义的标的必须显式传入 `InstrumentId`。", "",
        "### 公共参数", "",
        table(("参数", "说明"), [
            ("`provider`", "可选。显式指定 Provider；失败不会静默切换。"),
            ("`use_cache`", "可选。控制是否使用配置的缓存策略；`None` 使用默认配置。"),
        ]), "",
        "### Provider 与 warnings", "", "可用 `provider=` 显式指定 Provider。`result.warnings` 用于记录可恢复的数据质量或兼容性问题，例如跳过存在 schema drift 的单条 News 记录。", "",
        "### 最新快照股票池", "", "`limit_up_pool`、`limit_down_pool`、`broken_limit_pool`、`strong_pool` 和 `yesterday_limit_up_pool` 只返回最新快照，不支持历史日期查询。", "",
        "**弃用兼容：** 旧请求模型可能仍保留可选 `tradeDate` 字段；当前 Client 会拒绝历史日期选择。新代码不要使用它。", "",
        "文档由实时的 `CLIENT_ENDPOINTS`、Dataset 模型、Provider Registry 和计算能力 metadata 生成。",
    ]


def render(language: str) -> str:
    validate_example_inventory()
    validate_category_inventory()
    provider_count = len(provider_endpoint_keys())
    computed_count = len(computed_endpoint_keys())
    capability_count = len(all_endpoint_keys())
    lines = _intro(language=language, provider_count=provider_count, computed_count=computed_count, capability_count=capability_count)
    lines += category_index(language=language)
    lines += ["## 4. Interface details" if language == "en" else "## 4. 接口详情", ""]
    endpoint_by_key = {endpoint_key(endpoint): endpoint for endpoint in CLIENT_ENDPOINTS}
    for index, spec in enumerate(CATEGORY_SPECS, 1):
        title = spec.title_en if language == "en" else spec.title_zh
        lines += [f"## 4.{index} {title}", ""]
        for key in spec.endpoint_keys:
            lines += endpoint_block(endpoint_by_key[key], language=language) if key in endpoint_by_key else computed_block(language=language)
    lines += _shared_notes(language=language)
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when generated documents are stale")
    args = parser.parse_args()
    outputs = {
        ROOT / "docs" / "DATA_API_REFERENCE.md": render("en"),
        ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md": render("zh"),
    }
    for path, content in outputs.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if args.check:
            if current != content:
                print(f"stale generated document: {path}")
                return 1
        else:
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
