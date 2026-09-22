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
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from finchx import __version__  # noqa: E402
from finchx.client import CLIENT_ENDPOINTS, FinchX  # noqa: E402
from finchx.computed import COMPUTED_DEVIATION_DATASET  # noqa: E402
from finchx.providers import PROVIDER_REGISTRY  # noqa: E402


class _NoopCollector:
    def fetch(self, *_args: Any, **_kwargs: Any) -> None:
        return None


_CLIENT = FinchX(collector=_NoopCollector())


MINIMUM_INPUT_ZH: dict[str, str] = {
    "instrument_id or request": "instrument_id 或 request",
    "start_date and end_date together, or request": "同时提供 start_date 和 end_date，或使用 request",
    "none": "无",
    "request": "request",
    "request (instrumentId, tradeDate, tradeId)": "request（包含 instrumentId、tradeDate 和 tradeId）",
    "request (equity instrumentId)": "request（包含股票 instrumentId）",
    "request (instrumentId)": "request（包含 instrumentId）",
    "request (index instrumentId)": "request（包含指数 instrumentId）",
    "instrument_id, start_date, end_date, and adjustment for equity": "股票需提供 instrument_id、start_date、end_date 和 adjustment",
    "none; the default universe is CN_A_SHARE": "无；默认范围为 CN_A_SHARE",
    "request (universe, criterion, direction, limit)": "request（包含 universe、criterion、direction 和 limit）",
    "instrument_id and statement_type, or request": "instrument_id 和 statement_type，或使用 request",
    "instrument (InstrumentId or six-digit equity code), or request": "instrument（InstrumentId 或六位股票代码），或使用 request",
    "request (instrumentId; optional asOf)": "request（包含 instrumentId；asOf 可选）",
    "instrument_id": "instrument_id",
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
        assert self.minimum_input_zh is not None


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
        _equity_call("fx.reference.instrument(instrument_id)"),
        "instrument_id or request",
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
        _request_call(
            "from finchx.datasets import MarketBrokenLimitPoolRequest",
            "MarketBrokenLimitPoolRequest(tradeDate=date(2026, 9, 18))",
            "fx.market.broken_limit_pool(request)",
            date_import=True,
        ),
        "request",
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
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import EquityIntradayRequest",
            "EquityIntradayRequest(instrumentId=instrument_id)",
            "fx.market.equity_intraday(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (equity instrumentId)",
    ),
    "market.equity_intraday_5d": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import EquityIntraday5dRequest",
            "EquityIntraday5dRequest(instrumentId=instrument_id)",
            "fx.market.equity_intraday_5d(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (equity instrumentId)",
    ),
    "market.fund_flow_daily": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketFundFlowRequest",
            "MarketFundFlowRequest(instrumentId=instrument_id)",
            "fx.market.fund_flow_daily(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "market.fund_flow_intraday": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketFundFlowRequest",
            "MarketFundFlowRequest(instrumentId=instrument_id)",
            "fx.market.fund_flow_intraday(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "market.fund_flow_snapshot": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketFundFlowRequest",
            "MarketFundFlowRequest(instrumentId=instrument_id)",
            "fx.market.fund_flow_snapshot(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
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
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketIndustryComparisonRequest",
            "MarketIndustryComparisonRequest(instrumentId=instrument_id)",
            "fx.market.industry_comparison(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "market.instrument_sector_snapshot": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketInstrumentSectorSnapshotRequest",
            "MarketInstrumentSectorSnapshotRequest(instrumentId=instrument_id)",
            "fx.market.instrument_sector_snapshot(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "market.stock_keyword": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketStockKeywordRequest",
            "MarketStockKeywordRequest(instrumentId=instrument_id)",
            "fx.market.stock_keyword(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "market.limit_down_pool": ExampleSpec(
        _request_call(
            "from finchx.datasets import MarketLimitDownPoolRequest",
            "MarketLimitDownPoolRequest(tradeDate=date(2026, 9, 18))",
            "fx.market.limit_down_pool(request)",
            date_import=True,
        ),
        "request",
    ),
    "market.limit_up_pool": ExampleSpec(
        _request_call(
            "from finchx.datasets import MarketLimitUpPoolRequest",
            "MarketLimitUpPoolRequest(tradeDate=date(2026, 9, 18))",
            "fx.market.limit_up_pool(request)",
            date_import=True,
        ),
        "request",
    ),
    "market.ohlcv": ExampleSpec(
        '''from datetime import date
from finchx import FinchX
from finchx.datasets import KlineAdjustment
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

fx = FinchX()
{equity_setup}
result = fx.market.ohlcv(
    instrument_id,
    date(2026, 9, 1),
    date(2026, 9, 18),
    adjustment=KlineAdjustment.QFQ,
)'''.format(equity_setup=_EQUITY_SETUP),
        "instrument_id, start_date, end_date, and adjustment for equity",
    ),
    "market.orderbook": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketOrderbookRequest",
            "MarketOrderbookRequest(instrumentId=instrument_id)",
            "fx.market.orderbook(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "market.quote": ExampleSpec(
        """from finchx import FinchX

fx = FinchX()
result = fx.market.quote()""",
        "none; the default universe is CN_A_SHARE",
    ),
    "market.quote_snapshot": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import MarketQuoteSnapshotRequest",
            "MarketQuoteSnapshotRequest(instrumentId=instrument_id)",
            "fx.market.quote_snapshot(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
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
        _request_call(
            "from finchx.datasets import MarketStrongPoolRequest",
            "MarketStrongPoolRequest(tradeDate=date(2026, 9, 18))",
            "fx.market.strong_pool(request)",
            date_import=True,
        ),
        "request",
    ),
    "market.yesterday_limit_up_pool": ExampleSpec(
        _request_call(
            "from finchx.datasets import MarketYesterdayLimitUpPoolRequest",
            "MarketYesterdayLimitUpPoolRequest(tradeDate=date(2026, 9, 18))",
            "fx.market.yesterday_limit_up_pool(request)",
            date_import=True,
        ),
        "request",
    ),
    "fundamental.company_profile": ExampleSpec(
        _equity_call("fx.fundamental.company_profile(instrument_id)"),
        "instrument_id or request",
    ),
    "fundamental.financial_summary": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import FinancialSummaryRequest",
            "FinancialSummaryRequest(instrumentId=instrument_id)",
            "fx.fundamental.financial_summary(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "fundamental.industry_comparison": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import IndustryComparisonRequest",
            "IndustryComparisonRequest(instrumentId=instrument_id)",
            "fx.fundamental.industry_comparison(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "fundamental.revenue_breakdown": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import RevenueBreakdownRequest",
            "RevenueBreakdownRequest(instrumentId=instrument_id)",
            "fx.fundamental.revenue_breakdown(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "financial.statements": ExampleSpec(
        _equity_call('fx.financial.statements(instrument_id, "income_statement")'),
        "instrument_id and statement_type, or request",
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
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import CapitalSnapshotRequest",
            "CapitalSnapshotRequest(instrumentId=instrument_id)",
            "fx.ownership.capital_snapshot(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "ownership.float_holder": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import FloatHolderRequest",
            "FloatHolderRequest(instrumentId=instrument_id)",
            "fx.ownership.float_holder(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId; optional asOf)",
    ),
    "ownership.holder_summary_snapshot": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import HolderSummarySnapshotRequest",
            "HolderSummarySnapshotRequest(instrumentId=instrument_id)",
            "fx.ownership.holder_summary_snapshot(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "company.executive_share_change": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import ExecutiveShareChangeRequest",
            "ExecutiveShareChangeRequest(instrumentId=instrument_id)",
            "fx.company.executive_share_change(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "company.executive_snapshot": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import ExecutiveSnapshotRequest",
            "ExecutiveSnapshotRequest(instrumentId=instrument_id)",
            "fx.company.executive_snapshot(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "corporate_action.dividend": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import DividendRequest",
            "DividendRequest(instrumentId=instrument_id)",
            "fx.corporate_action.dividend(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "corporate_action.repurchase": ExampleSpec(
        _request_call(
            f"{_EQUITY_IMPORT}\nfrom finchx.datasets import RepurchaseRequest",
            "RepurchaseRequest(instrumentId=instrument_id)",
            "fx.corporate_action.repurchase(request)",
            setup=_EQUITY_SETUP,
        ),
        "request (instrumentId)",
    ),
    "market.deviation": ExampleSpec(
        _equity_call("fx.market.deviation(instrument_id, windows=(10, 30))"),
        "instrument_id",
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

def field_description_text(field: Any, *, language: str, fallback: str) -> str:
    if not field.description:
        return fallback
    if language == "en":
        return field.description
    try:
        return DESCRIPTION_ZH[field.description]
    except KeyError as exc:
        raise RuntimeError(f"missing zh-CN field description: {field.description}") from exc


def model_field_rows(model: type[BaseModel], *, language: str) -> list[tuple[str, str, str, str, str]]:
    required = "Yes" if language == "en" else "是"
    optional = "No" if language == "en" else "否"
    fallback = (
        "Declared by the Pydantic model."
        if language == "en"
        else "由 Pydantic 模型定义。"
    )
    rows = []
    for name, field in model.model_fields.items():
        rows.append(
            (
                field.alias or name,
                annotation_text(field.annotation),
                required if field.is_required() else optional,
                "—" if field.is_required() else field_default_text(field),
                field_description_text(field, language=language, fallback=fallback),
            )
        )
    return rows


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
            if child in seen:
                continue
            seen.add(child)
            found.append(child)
            pending.extend(child.model_fields.values())
    return found


def model_section(model: type[BaseModel], heading: str, *, language: str) -> list[str]:
    if language == "en":
        headers = ("Field", "Type", "Required", "Default", "Description")
        empty = "No fields; instantiate this model without arguments."
    else:
        headers = ("字段", "类型", "必填", "默认值", "说明")
        empty = "无字段；直接无参实例化该模型。"
    rows = model_field_rows(model, language=language)
    return [
        f"#### {heading} `{model.__name__}`",
        "",
        table(headers, rows) if rows else empty,
    ]


_CONDITIONAL_REQUEST_ENDPOINTS = {
    "reference.instrument",
    "reference.trading_calendar",
    "market.ohlcv",
    "fundamental.company_profile",
    "financial.statements",
    "news.search",
    "disclosure.search",
}


def parameter_required(endpoint_key_value: str, name: str, parameter: inspect.Parameter, *, language: str) -> str:
    yes = "Yes" if language == "en" else "是"
    no = "No" if language == "en" else "否"
    if name in {"provider", "use_cache"}:
        return no
    if parameter.default is inspect.Signature.empty:
        return yes
    if name == "request" and parameter.default is None:
        if endpoint_key_value in _CONDITIONAL_REQUEST_ENDPOINTS:
            return "Conditional request alternative" if language == "en" else "条件性 request 替代"
        return no
    if name in {"instrument_id", "start_date", "end_date", "instrument", "statement_type"}:
        return "Required in convenience mode" if language == "en" else "便捷模式必填"
    if name == "adjustment":
        return "Required for equities; omit for indexes" if language == "en" else "股票必填；指数省略"
    return no


def parameter_description(name: str, *, language: str) -> str:
    english = {
        "provider": "Strict Provider id pin; a failure is not silently redirected.",
        "use_cache": "Cache control; None follows the configured CachePolicy.",
        "request": "Typed request model; valid combinations are governed by the Client and Pydantic validation.",
        "instrument_id": "Complete InstrumentId.",
        "instrument": "InstrumentId or a six-digit equity code.",
        "start_date": "Inclusive start date.",
        "end_date": "Inclusive end date.",
        "market": "Market enum; trading_calendar currently supports Market.CN_A only.",
        "adjustment": "Kline adjustment; required for equity calls and omitted for index calls.",
        "statement_type": "balance_sheet, income_statement, or cash_flow_statement.",
        "period_end": "Optional report-period end date.",
        "max_periods": "Optional maximum number of report periods.",
        "page": "One-based page number.",
        "page_size": "Page size.",
        "max_results": "Optional result cap; its combination with non-first pages is model-validated.",
        "since": "Optional inclusive lower time bound.",
        "until": "Optional inclusive upper time bound.",
        "sort": "published_desc or published_asc.",
        "categories": "Optional disclosure category list.",
        "universe": "Selection scope.",
        "windows": "Supported deviation windows: 10 and 30 trading sessions.",
        "as_of": "Optional completed-session date.",
        "window_convention": "Deviation window interpretation.",
    }
    chinese = {
        "provider": "严格指定 Provider id；失败时不会静默切换。",
        "use_cache": "缓存控制；None 遵循已配置的 CachePolicy。",
        "request": "类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。",
        "instrument_id": "完整的 InstrumentId。",
        "instrument": "InstrumentId 或六位股票代码。",
        "start_date": "包含在内的开始日期。",
        "end_date": "包含在内的结束日期。",
        "market": "Market 枚举；trading_calendar 当前仅支持 Market.CN_A。",
        "adjustment": "Kline 调整方式；股票调用必填，指数调用省略。",
        "statement_type": "balance_sheet、income_statement 或 cash_flow_statement。",
        "period_end": "可选的报告期结束日期。",
        "max_periods": "可选的最大报告期数量。",
        "page": "从 1 开始的页码。",
        "page_size": "单页数量。",
        "max_results": "可选的结果上限；与非第一页组合受模型校验。",
        "since": "可选的包含起点。",
        "until": "可选的包含终点。",
        "sort": "published_desc 或 published_asc。",
        "categories": "可选的公告分类列表。",
        "universe": "查询范围。",
        "windows": "支持的偏离窗口：10 和 30 个交易时段。",
        "as_of": "可选的已完成交易时段日期。",
        "window_convention": "偏离窗口解释方式。",
    }
    return (english if language == "en" else chinese).get(name, "Declared by the source signature." if language == "en" else "由源码签名定义。")


def request_alias_note(endpoint: Any, method: Any, *, language: str) -> str | None:
    """Call out the one known annotation alias without changing public API code."""

    signature_text = str(inspect.signature(method))
    if "FundamentalIndustryComparisonRequest" in signature_text and endpoint.dataset.name == "fundamental.industry_comparison":
        if language == "en":
            return "The Client annotation spells this local alias as `FundamentalIndustryComparisonRequest`; the real public class and Dataset request type are `finchx.datasets.IndustryComparisonRequest`."
        return "Client 标注使用局部别名 `FundamentalIndustryComparisonRequest`；真实公开类名和 Dataset request type 是 `finchx.datasets.IndustryComparisonRequest`。"
    return None


SUMMARY_ZH: dict[str, str] = {
    "reference.instrument": "获取标的规范身份和名称。",
    "reference.trading_calendar": "获取日期范围内的 A 股交易日标记。",
    "market.breadth": "获取当前市场涨跌家数分布。",
    "market.broken_limit_pool": "获取炸板池数据。",
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
    "market.limit_down_pool": "获取指定交易日的跌停池。",
    "market.limit_up_pool": "获取指定交易日的涨停池。",
    "market.ohlcv": "获取单个标的的日线 OHLCV 数据。",
    "market.orderbook": "获取单个标的的盘口数据。",
    "market.quote": "获取选定股票范围的行情快照。",
    "market.quote_snapshot": "获取单个标的的行情快照。",
    "market.ranking": "获取指定条件的市场排行。",
    "market.sentiment": "获取市场情绪快照。",
    "market.strong_pool": "获取强势股池。",
    "market.yesterday_limit_up_pool": "获取昨日涨停池。",
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


def summary_for(key: str, method: Any, *, language: str) -> str:
    if language == "zh":
        return SUMMARY_ZH.get(key, "公开 Client 接口。")
    doc = inspect.getdoc(method)
    return doc.split("\n")[0] if doc else "Public Client endpoint."

def providers_for(dataset: Any) -> tuple[str, ...]:
    return tuple(spec.provider_id for spec in PROVIDER_REGISTRY.providers_for(dataset))


def endpoint_block(endpoint: Any, *, language: str) -> list[str]:
    key = endpoint_key(endpoint)
    example = EXAMPLE_SPECS[key]
    method = getattr(getattr(_CLIENT, endpoint.namespace), endpoint.method)
    signature = str(inspect.signature(method))
    providers = providers_for(endpoint.dataset)
    if language == "en":
        lines = [
            f"### `fx.{key}(...)`",
            "",
            summary_for(key, method, language=language),
            "",
            f"**Dataset:** `{endpoint.dataset.name}`",
            f"**Schema version:** `{endpoint.dataset.schema_version}`",
            f"**Implemented Providers:** {', '.join(f'`{provider}`' for provider in providers) or '—'}",
            f"**Routing semantics:** `{PROVIDER_REGISTRY.routing_semantics_for(endpoint.dataset).value}`",
            "",
            "#### Method signature",
            "",
            "```python",
            f"fx.{key}{signature}",
            "```",
            "",
            "#### Parameters",
            "",
        ]
        rows = []
        for name, parameter in inspect.signature(method).parameters.items():
            rows.append((
                name,
                annotation_text(parameter.annotation),
                parameter_required(key, name, parameter, language=language),
                "—" if parameter.default is inspect.Signature.empty else default_text(parameter.default),
                parameter_description(name, language=language),
            ))
        lines.append(table(("Parameter", "Type", "Required", "Default", "Description"), rows))
        lines += ["", f"**Minimum business input:** {example.minimum_input_for('en')}.", ""]
        note = request_alias_note(endpoint, method, language=language)
        if note:
            lines += [f"**Naming note:** {note}", ""]
        lines += model_section(endpoint.request_type, "Request model", language=language)
        lines += ["", f"The public return annotation is `{annotation_text(get_type_hints(method)['return'])}`.", ""]
        lines += model_section(endpoint.dataset.data_type, "Returned data model", language=language)
        for nested in nested_models(endpoint.dataset.data_type):
            lines += [""] + model_section(nested, "Nested model", language=language)
        lines += ["", "#### Example", "", f"<!-- api-example: {key} -->", "```python", example.code, "```", ""]
    else:
        lines = [
            f"### `fx.{key}(...)`",
            "",
            summary_for(key, method, language=language),
            "",
            f"**Dataset：** `{endpoint.dataset.name}`",
            f"**Schema 版本：** `{endpoint.dataset.schema_version}`",
            f"**已实现 Provider：** {', '.join(f'`{provider}`' for provider in providers) or '—'}",
            f"**路由语义：** `{PROVIDER_REGISTRY.routing_semantics_for(endpoint.dataset).value}`",
            "",
            "#### 方法签名",
            "",
            "```python",
            f"fx.{key}{signature}",
            "```",
            "",
            "#### 参数",
            "",
        ]
        rows = []
        for name, parameter in inspect.signature(method).parameters.items():
            rows.append((
                name,
                annotation_text(parameter.annotation),
                parameter_required(key, name, parameter, language=language),
                "—" if parameter.default is inspect.Signature.empty else default_text(parameter.default),
                parameter_description(name, language=language),
            ))
        lines.append(table(("参数", "类型", "必填", "默认值", "说明"), rows))
        lines += ["", f"**最小业务输入：** {example.minimum_input_for('zh')}。", ""]
        note = request_alias_note(endpoint, method, language=language)
        if note:
            lines += [f"**命名说明：** {note}", ""]
        lines += model_section(endpoint.request_type, "请求模型", language=language)
        lines += ["", f"公开返回标注为 `{annotation_text(get_type_hints(method)['return'])}`。", ""]
        lines += model_section(endpoint.dataset.data_type, "返回数据模型", language=language)
        for nested in nested_models(endpoint.dataset.data_type):
            lines += [""] + model_section(nested, "嵌套模型", language=language)
        lines += ["", "#### 示例", "", f"<!-- api-example: {key} -->", "```python", example.code, "```", ""]
    return lines


def computed_block(*, language: str) -> list[str]:
    key = "market.deviation"
    example = EXAMPLE_SPECS[key]
    method = _CLIENT.market.deviation
    signature = str(inspect.signature(method))
    if language == "en":
        rows = []
        for name, parameter in inspect.signature(method).parameters.items():
            rows.append((
                name,
                annotation_text(parameter.annotation),
                "Yes" if parameter.default is inspect.Signature.empty else "No",
                "—" if parameter.default is inspect.Signature.empty else default_text(parameter.default),
                parameter_description(name, language=language),
            ))
        lines = [
            "### `fx.market.deviation(...)`",
            "",
            summary_for(key, method, language=language),
            "",
            "**Dataset:** `market.deviation` (computed; no Provider)",
            "**Schema version:** `1.0`",
            "",
            "#### Method signature",
            "",
            "```python",
            f"fx.market.deviation{signature}",
            "```",
            "",
            "#### Parameters",
            "",
            table(("Parameter", "Type", "Required", "Default", "Description"), rows),
            "",
            "**Minimum business input:** instrument_id.",
            "",
        ]
        lines += model_section(COMPUTED_DEVIATION_DATASET.request_type, "Request model", language=language)
        lines += ["", "The public return annotation is `FetchResult[DeviationData]`.", ""]
        lines += model_section(COMPUTED_DEVIATION_DATASET.data_type, "Returned data model", language=language)
        for nested in nested_models(COMPUTED_DEVIATION_DATASET.data_type):
            lines += [""] + model_section(nested, "Nested model", language=language)
        lines += ["", "#### Example", "", f"<!-- api-example: {key} -->", "```python", example.code, "```", ""]
    else:
        rows = []
        for name, parameter in inspect.signature(method).parameters.items():
            rows.append((
                name,
                annotation_text(parameter.annotation),
                "是" if parameter.default is inspect.Signature.empty else "否",
                "—" if parameter.default is inspect.Signature.empty else default_text(parameter.default),
                parameter_description(name, language=language),
            ))
        lines = [
            "### `fx.market.deviation(...)`",
            "",
            summary_for(key, method, language=language),
            "",
            "**Dataset：** `market.deviation`（计算能力；无 Provider）",
            "**Schema 版本：** `1.0`",
            "",
            "#### 方法签名",
            "",
            "```python",
            f"fx.market.deviation{signature}",
            "```",
            "",
            "#### 参数",
            "",
            table(("参数", "类型", "必填", "默认值", "说明"), rows),
            "",
            "**最小业务输入：** instrument_id。",
            "",
        ]
        lines += model_section(COMPUTED_DEVIATION_DATASET.request_type, "请求模型", language=language)
        lines += ["", "公开返回标注为 `FetchResult[DeviationData]`。", ""]
        lines += model_section(COMPUTED_DEVIATION_DATASET.data_type, "返回数据模型", language=language)
        for nested in nested_models(COMPUTED_DEVIATION_DATASET.data_type):
            lines += [""] + model_section(nested, "嵌套模型", language=language)
        lines += ["", "#### 示例", "", f"<!-- api-example: {key} -->", "```python", example.code, "```", ""]
    return lines


def endpoint_index(*, language: str) -> list[str]:
    rows = [
        (
            endpoint.namespace,
            endpoint.method,
            endpoint.dataset.name,
            ", ".join(providers_for(endpoint.dataset)) or "—",
            EXAMPLE_SPECS[endpoint_key(endpoint)].minimum_input_for(language),
        )
        for endpoint in CLIENT_ENDPOINTS
    ]
    rows.append(("market", "deviation", "market.deviation (computed)", "—", EXAMPLE_SPECS["market.deviation"].minimum_input_for(language)))
    if language == "en":
        return [
            "## Endpoint index",
            "",
            "This index is generated from `CLIENT_ENDPOINTS`, plus the computed `market.deviation` capability.",
            "",
            table(("Namespace", "Method", "Dataset", "Implemented Providers", "Minimum business input"), rows),
            "",
        ]
    return [
        "## 接口索引",
        "",
        "该索引由 `CLIENT_ENDPOINTS` 以及计算型 `market.deviation` 能力生成。",
        "",
        table(("Namespace", "方法", "Dataset", "已实现 Provider", "最小业务输入"), rows),
        "",
    ]


def render(language: str) -> str:
    validate_example_inventory()
    provider_count = len(CLIENT_ENDPOINTS)
    computed_count = len(all_endpoint_keys()) - provider_count
    capability_count = len(all_endpoint_keys())
    if language == "en":
        lines = [
            "# FinchX Data & API Reference",
            "",
            "English | [简体中文](DATA_API_REFERENCE.zh-CN.md)",
            "",
            f"This reference is generated from the {__version__} public Client, Dataset definitions, Pydantic request/data models and Provider Registry. It covers {provider_count} Provider-backed / Dataset-backed public endpoints plus {computed_count} computed capability ({capability_count} total capabilities).",
            "",
            "## Common rules",
            "",
            "Signatures below are taken from the live public Client. Request-field Required / Optional values come from Pydantic `model_fields`; convenience-mode and cross-field rules are documented separately when a signature alone is insufficient. Both language versions use the same structured Example definitions.",
            "",
            table(("Rule", "Meaning"), [
                ("`provider`", "Strict Provider id pin; a failure is not silently redirected."),
                ("`use_cache`", "None follows the configured CachePolicy; FinchX construction does not create storage."),
                ("Request model", "Some methods expose a convenience call and a typed request alternative; valid combinations follow the Client and Pydantic validators."),
                ("InstrumentId", "Use a complete identity with code, market, kind and exchange when the endpoint requires it."),
            ]),
            "",
        ]
    else:
        lines = [
            "# FinchX 数据与 API 参考",
            "",
            "[English](DATA_API_REFERENCE.md) | 简体中文",
            "",
            f"本文档根据 {__version__} 公开 Client、Dataset 定义、Pydantic 请求/数据模型和 Provider Registry 生成，覆盖 {provider_count} 个 Provider / Dataset 公开接口以及 {computed_count} 个计算型能力（共 {capability_count} 个能力）。",
            "",
            "## 通用规则",
            "",
            "下方签名直接来自公开 Client。请求字段的“必填/可选”来自 Pydantic 的 `model_fields`；当签名不足以表达便捷模式或跨字段约束时，文档会单独说明。两个语言版本使用同一份结构化示例定义。",
            "",
            table(("规则", "含义"), [
                ("`provider`", "严格指定 Provider id；失败时不会静默切换。"),
                ("`use_cache`", "None 遵循已配置的 CachePolicy；构造 FinchX 不会创建存储。"),
                ("请求模型", "部分方法同时提供便捷调用和类型化请求替代；合法组合以 Client 和 Pydantic 校验为准。"),
                ("InstrumentId", "接口需要时使用包含 code、market、kind 和 exchange 的完整身份。"),
            ]),
            "",
        ]
    lines += endpoint_index(language=language)
    lines += ["## Endpoint reference" if language == "en" else "## 接口参考", ""]
    current_namespace = None
    for endpoint in CLIENT_ENDPOINTS:
        if endpoint.namespace != current_namespace:
            current_namespace = endpoint.namespace
            lines += [f"## `{current_namespace}`", ""]
        lines += endpoint_block(endpoint, language=language)
    lines += ["## `market.deviation`", ""] + computed_block(language=language)
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
