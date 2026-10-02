"""Generate the bilingual FinchX API reference from public runtime metadata.

Client signatures, Dataset definitions, Pydantic fields and the Provider
Registry are read from the package.  Examples are the one intentionally
explicit part of the metadata: business-level requirements such as whether an
endpoint needs an equity or index identity cannot be inferred safely from a
Python signature alone.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import inspect
import re
import sys
import types
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import AnyUrl, BaseModel, RootModel

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


@dataclass(frozen=True)
class ExampleSpec:
    """Marker that a public capability has a rendered example."""


EXAMPLE_SPECS: dict[str, ExampleSpec] = {}


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
    if annotation is AnyUrl:
        return "AnyUrl"
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


def public_annotation_text(annotation: Any) -> str:
    """Render user-facing types without exposing internal identity models."""

    text = annotation_text(annotation)
    return re.sub(r"\b(?:InstrumentInput|InstrumentId)\b", "str", text)


def _contains_annotation(annotation: Any, target: type[Any]) -> bool:
    if annotation is target:
        return True
    return any(_contains_annotation(item, target) for item in get_args(annotation))


def request_annotation_text(annotation: Any) -> str:
    """Render request date fields with the string forms accepted by validation."""

    if not _contains_annotation(annotation, date):
        return annotation_text(annotation)
    parts = ["date"]
    if _contains_annotation(annotation, datetime):
        parts.append("datetime")
    parts.append("str")
    if type(None) in get_args(annotation):
        parts.append("None")
    return " | ".join(parts)


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
    "Source-reported total constituent stock count from realhead field 37; never inferred from pagination.": "同花顺 realhead 字段 37 报告的成分股总数；不会根据分页信息推算。",
    "A ratio fraction, not percentage points: 4.24% is 0.0424.": "比例小数，而不是百分点：4.24% 表示为 0.0424。",
    "Aigupiao source-defined sentiment temperature; not a physical temperature or ratio.": "Aigupiao 定义的情绪温度；不是物理温度或比例。",
    "Amount traded at the limit-down price in CNY.": "以跌停价成交的金额，单位为 CNY。",
    "Amount traded during this minute, in CNY.": "该分钟成交金额，单位为 CNY。",
    "Additional report metadata returned by the source.": "数据源返回的其他研报元数据。",
    "FinchX-owned report document identifier.": "FinchX 生成的研报标识。",
    "Readable report text returned by the report detail endpoint.": "详情接口返回的可读研报文本。",
    "Publication date returned by the report detail endpoint.": "详情接口返回的发布日期。",
    "Whether readable report text is available.": "是否有可读取的正文文本。",
    "Related securities when provided by the source.": "数据源提供时关联的证券列表。",
    "Report detail page URL.": "研报详情页链接。",
    "Publisher or source URL when returned by the report detail endpoint.": "详情接口返回的发布方或来源链接。",
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
    "Latest equity price in CNY per share or index level in points.": "最新价格；股票为每股 CNY，指数为点数。",
    "Previous equity close in CNY per share or index close in points.": "前收盘价；股票为每股 CNY，指数为点数。",
    "Session open in CNY per share for equities or points for indices.": "时段开盘价；股票为每股 CNY，指数为点数。",
    "Session high in CNY per share for equities or points for indices.": "时段最高价；股票为每股 CNY，指数为点数。",
    "Session low in CNY per share for equities or points for indices.": "时段最低价；股票为每股 CNY，指数为点数。",
    "Change from previous close in CNY for equities or points for indices.": "最新价与前收盘价之差；股票单位为 CNY，指数单位为点。",
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
    "Source creation timestamp as returned by the report endpoint.": "详情接口原样返回的来源创建时间。",
    "Source report file extension, when available.": "来源研报文件扩展名（如有）。",
    "Source report UID.": "来源研报 UID。",
    "Source-reported change in turnover amount versus the prior day.": "来源报告的成交金额相对前一日的变动。",
    "Source-reported quote time, separate from FinchX capturedAt.": "来源报告的行情时间，与 FinchX capturedAt 分开。",
    "Original report detail page URL.": "原始研报详情页链接。",
    "Report analyst or researcher.": "报告分析师或研究员。",
    "Report title.": "研报标题。",
    "Research organization.": "研究机构。",
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
    "Normalized A-share instrument identity.": "规范化后的 A 股证券身份。",
    "Security name supplied by EastMoney quote data.": "东方财富行情数据提供的证券名称。",
    "Current ranking position reported by EastMoney.": "东方财富来源当前榜单排名。",
    "Current price in CNY per share; unavailable source placeholders are None.": "当前价格，单位 CNY/股；来源缺失占位值为 None。",
    "Signed price change in CNY per share, directly from EastMoney f4; unavailable values are None.": "直接取东方财富 f4 的带符号涨跌额，单位 CNY/股；缺失值为 None。",
    "Price change as a ratio fraction; EastMoney percentage points are divided by 100.": "涨跌幅使用比例小数；东方财富百分点数值除以 100。",
}





SUMMARY_ZH: dict[str, str] = {
    "hotlist.stocks": "获取按市场关注热度排序的 A 股热股榜，支持类别和 1 小时或 24 小时周期。",
    "hotlist.sectors": "获取概念、行业或指数板块热榜，并补充可用的关联 ETF 信息。",
    "hotlist.convertible_bonds": "获取可转债热度榜；尚未产生涨跌幅的转债会保留空值。",
    "hotlist.etfs": "获取 ETF 热榜，按同花顺关注热度指标排序并补充标签。",
    "hotlist.content": "获取主题、热评或热文内容榜；三种内容返回各自的数据结构。",
    "articles.get": "通过同花顺文章 URL 获取普通新闻或股吧直播正文。",
    "articles.from_topic": "从同花顺 T-code 主题混合 Feed 中筛出可由 articles.get 获取正文的普通新闻和长文。",
    "reference.trading_calendar": "获取日期范围内每个自然日的 A 股交易日标记。",
    "market.breadth": "获取当前市场涨跌家数分布。",
    "market.regulation_watchlist": "获取东方财富最新监管监控名单，保留所有来源行，包括无法核实证券类别的行。",
    "market.abnormal_records": "按 abnormal_events、severe_events 或 prediction_history 获取单个上游分页。",
    "market.severe_predictions": "获取有页数上限的严重异常预测池，保留未知预测状态和来源原值。",
    "market.abnormal_counts": "获取有页数上限的异常次数榜；保留来源 count 与 open 等未解释元数据。",
    "market.broken_limit_pool": "获取最新炸板池快照。",
    "market.consecutive_limit_up": "获取连板股快照。",
    "market.daily_replay": "获取指定日期的每日复盘数据。",
    "market.dragon_tiger_detail": "获取指定标的的龙虎榜明细。",
    "market.dragon_tiger_list": "获取指定交易日的龙虎榜列表。",
    "market.equity_intraday": "获取个股分时图。",
    "market.equity_intraday_5d": "获取个股5日分时图。",
    "market.fund_flow_daily": "获取个股每日资金流数据。",
    "market.fund_flow_intraday": "获取个股盘中资金流数据。",
    "market.fund_flow_snapshot": "获取资金流快照。",
    "market.index_intraday": "获取单个指数当日分时数据。",
    "market.index_intraday_5d": "获取指数五日分时数据。",
    "market.industry_comparison": "获取市场行业比较数据。",
    "market.instrument_sector_snapshot": "获取标的所属板块及板块快照。",
    "market.concept_list": "获取同花顺概念目录；每条记录包含概念引用字段。",
    "market.concept_quote_snapshot": "获取一个概念指数的实时行情快照。",
    "market.concept_ohlcv": "获取一个概念指数的日线 OHLCV 数据。",
    "market.stock_keyword": "获取数据源提供的股票关键词。",
    "market.limit_down_pool": "获取最新跌停池快照。",
    "market.limit_up_pool": "获取最新涨停池快照。",
    "market.ohlcv": "获取股票或受支持指数的日线 OHLCV 数据。",
    "market.orderbook": "获取腾讯来源的五档盘口槽位，保留零值与缺失值的区别。",
    "market.quote": "获取全市场行情快照。",
    "market.quote_snapshot": "获取 SSE/SZSE 股票或受支持指数的行情快照。",
    "market.ranking": "按指定指标获取 A 股个股排行。",
    "market.sentiment": "获取市场情绪快照。",
    "market.strong_pool": "获取最新强势股池快照。",
    "market.yesterday_limit_up_pool": "获取最新昨日涨停池快照。",
    "fundamental.company_profile": "获取公司概况。",
    "fundamental.financial_summary": "获取公司财务摘要。",
    "fundamental.industry_comparison": "获取公司与行业的基本面比较。",
    "fundamental.revenue_breakdown": "获取公司收入构成。",
    "financial.statements": "获取财务报表数据。",
    "iwencai.select": "使用登录 Cookie 执行问财自然语言选股，并返回标准化股票记录。",
    "iwencai.search": "使用 SkillHub OpenAPI 语义搜索研报、公告或新闻，并返回标准化命中记录。",
    "iwencai.report_detail": "通过搜索结果中的研报链接获取正文和结构化研报元数据。",
    "news.search": "搜索个股新闻并返回文档引用。",
    "disclosure.search": "搜索个股公告并返回公告引用。",
    "ownership.capital_snapshot": "获取股本快照。",
    "ownership.float_holder": "获取流通股东数据。",
    "ownership.holder_summary_snapshot": "获取股东汇总快照。",
    "company.executive_share_change": "获取高管持股变动。",
    "company.executive_snapshot": "获取高管快照。",
    "corporate_action.dividend": "获取分红除权记录。",
    "corporate_action.repurchase": "获取回购记录。",
    "market.deviation": "按盘前、当日和次日窗口边界计算板块基准偏离值。",
}

# The renderer below is intentionally organized around the reader-facing
# document, not the historical namespace layout above.  The metadata helpers
# and ExampleSpec inventory remain shared with the regression tests.
_COMPUTED_CAPABILITY_KEYS: tuple[str, ...] = ("market.deviation",)

_CONDITIONAL_REQUEST_ENDPOINTS = frozenset({
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
    CategorySpec("Market sentiment", "市场情绪", (
        "market.breadth", "market.sentiment", "market.broken_limit_pool",
        "market.consecutive_limit_up", "market.limit_down_pool", "market.limit_up_pool",
        "market.strong_pool", "market.yesterday_limit_up_pool",
    )),
    CategorySpec("Index quotes", "指数行情", (
        "market.index_intraday", "market.index_intraday_5d",
    )),
    CategorySpec("Sector data and hotlists", "板块信息与热榜", (
        "hotlist.sectors", "hotlist.stocks", "market.concept_list", "market.concept_quote_snapshot",
        "market.concept_ohlcv", "market.industry_comparison",
        "market.instrument_sector_snapshot",
    )),
    CategorySpec("Individual stock quotes", "个股行情", (
        "market.equity_intraday", "market.equity_intraday_5d", "market.fund_flow_daily",
        "market.fund_flow_intraday", "market.fund_flow_snapshot", "market.ohlcv",
        "market.orderbook", "market.quote", "market.ranking", "market.quote_snapshot",
    )),
    CategorySpec("Individual stock information and fundamentals", "个股信息与基本面", (
        "fundamental.company_profile", "fundamental.financial_summary",
        "fundamental.industry_comparison", "fundamental.revenue_breakdown",
        "financial.statements", "market.stock_keyword", "ownership.capital_snapshot",
        "ownership.float_holder", "ownership.holder_summary_snapshot",
        "company.executive_share_change", "company.executive_snapshot",
        "corporate_action.dividend", "corporate_action.repurchase",
    )),
    CategorySpec("News and disclosures", "消息面", (
        "news.search", "articles.get", "articles.from_topic", "disclosure.search",
    )),
    CategorySpec("After-close review", "盘后复盘", (
        "market.daily_replay", "market.dragon_tiger_detail", "market.dragon_tiger_list",
    )),
    CategorySpec("Regulatory monitoring and deviation", "监管监测与偏离值", (
        "market.regulation_watchlist", "market.abnormal_records",
        "market.severe_predictions", "market.abnormal_counts", "market.deviation",
    )),
    CategorySpec("Other", "其他", (
        "reference.trading_calendar", "hotlist.convertible_bonds",
        "hotlist.etfs", "hotlist.content", "iwencai.select", "iwencai.search",
        "iwencai.report_detail",
    )),
)


def provider_endpoint_keys() -> tuple[str, ...]:
    return tuple(endpoint_key(endpoint) for endpoint in CLIENT_ENDPOINTS)


def computed_endpoint_keys() -> tuple[str, ...]:
    return _COMPUTED_CAPABILITY_KEYS


def all_endpoint_keys() -> tuple[str, ...]:
    return provider_endpoint_keys() + computed_endpoint_keys()


EXAMPLE_SPECS = {key: ExampleSpec() for key in all_endpoint_keys()}


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
    "instrumentId": ("Instrument code.", "证券代码。"),
    "instrument_id": ("Instrument code.", "证券代码。"),
    "name": ("Name.", "名称。"),
    "tradeDate": ("Trade date.", "交易日期。"),
    "trade_date": ("Trade date.", "交易日期。"),
    "date": ("Date.", "日期。"),
    "adjustment": (
        "Actual bar adjustment supplied: `none`, `qfq`, `hfq`, or `not_applicable`. A `qfq` request may return `none` only with the documented Tencent `day` fallback metadata and warning.",
        "来源实际提供的复权口径：`none`、`qfq`、`hfq` 或 `not_applicable`。`qfq` 请求只有在使用文档所述腾讯 `day` 回退时才可能返回 `none`，并附带 metadata 和 warning。",
    ),
    "rank": ("Position within this hotlist.", "该榜单中的名次。"),
    "symbol": ("Six-digit security code.", "六位证券代码。"),
    "category": ("Selected hotlist category.", "选择的热榜类别。"),
    "period": ("Stock heat ranking period.", "股票热度榜统计周期。"),
    "sectorType": ("Sector classification used by the ranking.", "热度榜使用的板块类型。"),
    "contentType": ("Content ranking shape: topic, comment, or article.", "内容榜结构：主题、热评或热文。"),
    "changePct": ("Price change as a ratio fraction; source percentage points are divided by 100.", "涨跌幅比例小数；来源百分点数值除以 100。"),
    "heat": ("Source heat metric; meaningful within its own ranking.", "来源热度指标；仅在对应榜单内比较。"),
    "rankChange": ("Change in ranking position when reported by the source.", "来源提供时的排名变化。"),
    "conceptTags": ("Concept tags supplied by the source.", "来源提供的概念标签。"),
    "popularityTag": ("Popularity label supplied by the source.", "来源提供的热度标签。"),
    "analysisTitle": ("Analysis headline supplied by the source.", "来源提供的分析标题。"),
    "analysis": ("Analysis text supplied by the source.", "来源提供的分析内容。"),
    "searchCount": ("Search count when reported by the source.", "来源提供时的搜索次数。"),
    "updatedAt": ("Source update time; naive source times use Asia/Shanghai.", "来源更新时间；未标时区时按 Asia/Shanghai 处理。"),
    "pe": ("Issue price-to-earnings multiple for new listings.", "新股发行市盈率。"),
    "sectorCode": ("Public sector identity code.", "公开板块标识代码。"),
    "tag": ("Sector note supplied by the source.", "来源提供的板块说明。"),
    "hotTag": ("Hotlist streak or status label supplied by the source.", "来源提供的连续上榜或状态标签。"),
    "relatedEtfSymbol": ("Related ETF code when available.", "有关联 ETF 时的代码。"),
    "relatedEtfName": ("Related ETF name when available.", "有关联 ETF 时的名称。"),
    "relatedEtfChangePct": ("Related ETF price change as a ratio fraction.", "关联 ETF 涨跌幅比例小数。"),
    "tags": ("Deduplicated ETF tags; empty if tag enrichment is unavailable.", "去重后的 ETF 标签；标签补充失败时为空列表。"),
    "title": ("Content title.", "内容标题。"),
    "summary": ("Topic summary when supplied by the source.", "来源提供时的主题摘要。"),
    "url": ("Content URL when supplied by the source.", "来源提供时的内容链接。"),
    "relatedStocks": ("Related stocks when provided by the source.", "来源提供时关联的股票。"),
    "text": ("Comment text when available.", "有评论详情时的正文。"),
    "likes": ("Comment likes when reported by the source.", "来源提供时的点赞数。"),
    "contentId": ("Source content identifier when available.", "来源内容标识（如有）。"),
    "likeRatio": ("None until the source ratio unit is verified; article records carry a PARTIAL quality issue meanwhile.", "单位核实前为 None；此时文章记录的 Quality 会标记为部分数据（PARTIAL）。"),
    "commentRatio": ("None until the source ratio unit is verified; article records carry a PARTIAL quality issue meanwhile.", "单位核实前为 None；此时文章记录的 Quality 会标记为部分数据（PARTIAL）。"),
    "limit": ("Maximum number of rows to return; must be a positive integer.", "返回数量上限，必须为正整数。"),
}

DESCRIPTION_ZH["Normalized source importance marker: True when the source marks the item important; False when it does not; None when unavailable."] = "统一后的数据源重要度标记：数据源标记为重要时为 True，未标记为重要时为 False，无法取得时为 None。"
DESCRIPTION_ZH["Original source instrument code, retained verbatim."] = "原样保留的来源证券代码。"
DESCRIPTION_ZH["A classified CN_A equity or ETF identity when the source market and code range are verified; otherwise null."] = "仅在来源市场与代码号段均可确认时构造 CN_A 股票或 ETF 标识；否则为 null。"
DESCRIPTION_ZH["Original Tonghuashun stockMarket identifier; not a FinchX market enum."] = "同花顺原始 stockMarket 编号，不是 FinchX 市场枚举。"
DESCRIPTION_ZH["Article associations preserve source codes, names, and stockMarket markers; instrumentId is null if market or security type cannot be represented."] = "文章关联项保留来源代码、名称和 stockMarket 编号；无法表示其市场或证券类型时 instrumentId 为 null。"
DESCRIPTION_ZH.update({
    "Original source security code, retained verbatim.": "原样保留的来源证券代码。",
    "FinchX identity when the security and market can be classified; otherwise null.": "仅在可识别证券类型和市场时提供 FinchX 标识，否则为 null。",
    "Source-provided security name.": "来源提供的证券名称。",
    "Input sources that contributed this association.": "对该关联项有贡献的输入来源。",
    "Tonghuashun article identifier from the source URL.": "同花顺文章标识，与来源 URL 中的 ID 对应。",
    "Article category: ordinary news or community zhibo.": "文章类型：普通新闻或股吧直播。",
    "Article title.": "文章标题。",
    "Sanitized article-body HTML, excluding comments and disclaimers.": "清理后的文章正文 HTML，不包含评论和免责声明。",
    "Plain-text extraction of the sanitized article body.": "从清理后的文章正文提取的纯文本。",
    "Plain-text extraction of the sanitized article body; may be empty when the body contains a sourced image.": "从清理后的文章正文提取的纯文本；正文只含有效图片时可以为空。",
    "Timezone-aware publication time when supplied by the source.": "来源提供时的带时区发布时间。",
    "Publisher or media name supplied by the source.": "来源提供的发布方或媒体名称。",
    "Article author or byline.": "文章作者或署名。",
    "Upstream API or page URL used to retrieve the article.": "用于获取文章的上游 API 或页面 URL。",
    "Canonical public article page URL derived from the input URL.": "根据输入 URL 规范化后的公开文章页面 URL。",
    "Source-provided AI summary, when available.": "来源提供时的 AI 摘要。",
    "Disclaimer text extracted separately from the article body.": "从正文中分离提取的免责声明。",
    "Community comments extracted separately from the article body.": "从正文中分离提取的社区评论。",
    "Stock associations reported by the article detail source.": "文章详情来源报告的关联证券。",
    "Extraction path used for the article body.": "文章正文使用的提取路径。",
    "SHA-256 of the raw API article body or fetched HTML page.": "原始 API 文章正文或抓取页面 HTML 的 SHA-256。",
    "Whether a usable article title and body were retrieved.": "是否成功获取可用的文章标题和正文。",
    "Categorized fetch failure code when content is unavailable.": "正文不可用时的分类错误代码。",
    "Short source or parsing failure reason when content is unavailable.": "正文不可用时的简短来源或解析错误说明。",
    "Original Tonghuashun stockMarket marker; not a FinchX market enum.": "同花顺原始 stockMarket 标记，不是 FinchX 市场枚举。",
    "Validated T-code extracted from an allowlisted topic URL; it is the cache identity.": "从允许的主题 URL 中提取并验证的 T-code，同时作为缓存身份。",
    "Recommendation feed followed by its ordinary feed; other tab cursors are not exposed.": "先读取推荐 Feed，再读取普通 Feed；不公开其他分页游标。",
    "Maximum number of supported news and long-article records after filtering the mixed feed.": "混合 Feed 过滤后最多返回的已支持新闻和长文记录数。",
    "Position in the source-ordered, filtered article list.": "过滤后文章列表中的位置，保持来源顺序。",
    "Numeric Tonghuashun article sequence ID from the topic item.": "主题条目中的同花顺数字文章序列 ID。",
    "Verified type=8 news and type=2 long articles use the existing news or zhibo detail route.": "已验证的 type=8 新闻和 type=2 长文分别使用现有 news 或 zhibo 详情路由。",
    "Article title supplied by the topic feed.": "主题 Feed 提供的文章标题。",
    "Public news or zhibo article URL accepted by fx.articles.get(url).": "可直接传给 fx.articles.get(url) 的公开新闻或 zhibo 文章 URL。",
    "Source article timestamp normalized from epoch milliseconds to Asia/Shanghai.": "来源文章时间戳由毫秒纪元值规范化为 Asia/Shanghai 时间。",
    "Publisher or media label supplied by the topic feed item.": "主题 Feed 条目提供的发布方或媒体名称。",
})

DESCRIPTION_ZH.update({
    "Select abnormal_events, severe_events, or prediction_history on this shared Dataset.": "在此共享 Dataset 中选择 abnormal_events、severe_events 或 prediction_history。",
    "One-based upstream page number; each request fetches this page only.": "从 1 开始的上游页码；每次只获取这一页。",
    "Rows requested from the upstream page; maximum 200.": "从上游请求的单页行数；最大 200。",
    "severe_events only; None defaults to current provider rows.": "仅适用于 severe_events；None 默认读取来源当前记录。",
    "prediction_history local/server filter: all, yes, or no; unknown flags do not match yes/no.": "prediction_history 的本地/来源筛选：all、yes 或 no；未知标记既不匹配 yes 也不匹配 no。",
    "prediction_history only; true is pushed to the validated positive-flag filter.": "仅适用于 prediction_history；true 会下推到已验证的正向标记筛选。",
    "prediction_history only; false filters current-session rows locally, while unknown source flags remain unknown.": "仅适用于 prediction_history；false 会在本地排除当前交易日记录，来源未知标记仍为未知。",
    "Include only rising rows when true.": "为 true 时只保留上涨记录。",
    "Request BSE rows from the provider when true.": "为 true 时请求来源返回北交所记录。",
    "Provider sort key: count, price, or maximum deviation.": "来源排序字段：count、price 或最大偏离值。",
    "Provider sort direction.": "来源排序方向。",
    "Original source security code.": "来源原始证券代码。",
    "Security name supplied by the source.": "来源提供的证券名称。",
    "Null because stock_monitor.json has no verified security-kind field.": "由于 stock_monitor.json 没有可核实的证券类别字段，因此为 null。",
    "Exchange decoded from MARKET: 1 is SSE, 0 is SZSE, B is BSE; unknown codes remain null.": "由 MARKET 解码交易所：1 为 SSE、0 为 SZSE、B 为 BSE；未知代码保留 null。",
    "unknown because the source does not identify equity, ETF, or other security kinds.": "由于来源没有标明股票、ETF 或其他证券类别，因此为 unknown。",
    "Original MARKET code retained as source evidence.": "保留来源原始 MARKET 编码作为证据。",
    "Source monitoring start date.": "来源监控开始日期。",
    "Source monitoring end date when supplied.": "来源提供时的监控结束日期。",
    "Source-linked notice URL when supplied.": "来源提供时关联的公告 URL。",
    "Original EastMoney row values, including unrecognized markers.": "东方财富原始行字段，包括未识别标记。",
    "Six-digit instrument code reported by EastMoney.": "东方财富报告的六位证券代码。",
    "Security name supplied by EastMoney.": "东方财富提供的证券名称。",
    "Instrument identity decoded from SECUCODE.": "根据 SECUCODE 解码的证券标识。",
    "Exchange decoded from the SECUCODE suffix.": "根据 SECUCODE 后缀解码的交易所。",
    "Source event start date when supplied.": "来源提供时的事件开始日期。",
    "Source event end date when supplied.": "来源提供时的事件结束日期。",
    "Source INFO_CODE when supplied.": "来源提供时的 INFO_CODE。",
    "Announcement date supplied by EastMoney.": "东方财富提供的公告日期。",
    "EastMoney notice URL formed from INFO_CODE when present.": "存在 INFO_CODE 时据此构造东方财富公告 URL。",
    "Source abnormality reason text.": "来源提供的异动原因文本。",
    "Source abnormality reason-type text.": "来源提供的异动原因类型文本。",
    "Original disclosure-market text; not normalized to FinchX Exchange.": "来源原始披露市场文本；不转换为 FinchX Exchange。",
    "Original UNUSUAL_TYPE marker: 001 ordinary or 002 severe.": "来源原始 UNUSUAL_TYPE 标记：001 普通事件、002 严重事件。",
    "Original EastMoney values retained for audit.": "保留东方财富原始值供审计。",
    "Normalized event class for UNUSUAL_TYPE=001.": "UNUSUAL_TYPE=001 对应的规范化事件类别。",
    "Normalized event class for UNUSUAL_TYPE=002.": "UNUSUAL_TYPE=002 对应的规范化事件类别。",
    "Provider prediction monitoring start date.": "来源预测监控开始日期。",
    "Provider prediction monitoring end date.": "来源预测监控结束日期。",
    "IS_HIS=1 maps to current, 0 to history; other values remain unknown.": "IS_HIS=1 映射为 current、0 映射为 history；其他值保留为 unknown。",
    "Original IS_HIS marker.": "来源原始 IS_HIS 标记。",
    "Prediction-history trade date.": "预测历史交易日期。",
    "Source CHANGE_RATE percentage points divided by 100; 3% is 0.03.": "来源 CHANGE_RATE 百分点除以 100；3% 表示为 0.03。",
    "Source MAX_DAYS value; preserved as supplied without asserting a calculation convention.": "来源 MAX_DAYS 值原样保留，不推断其计算口径。",
    "Source DEVUATION_VALUE percentage points divided by 100.": "来源 DEVUATION_VALUE 百分点除以 100。",
    "Source CHANGE_RATE_TARGET percentage points divided by 100.": "来源 CHANGE_RATE_TARGET 百分点除以 100。",
    "IS_HAPPEN 1 maps to true, 0 to false; unknown values remain null.": "IS_HAPPEN=1 映射为 true、0 为 false；未知值保留 null。",
    "Original UNUSUAL_TYPE text; it is not coerced to an event-code enum.": "来源原始 UNUSUAL_TYPE 文本；不强行转换为事件码枚举。",
    "IS_SYSDATE 1 maps to true, 0 to false; unknown values remain null.": "IS_SYSDATE=1 映射为 true、0 为 false；未知值保留 null。",
    "IS_POSITIVE 1 maps to true, 0 to false; unknown values remain null.": "IS_POSITIVE=1 映射为 true、0 为 false；未知值保留 null。",
    "Original MARKET_CODE value; its semantics are provider-specific.": "来源原始 MARKET_CODE；其语义由来源定义。",
    "Original EastMoney values retained for audit, including RANK_TYPE.": "保留东方财富原始值供审计，包括 RANK_TYPE。",
    "Six-digit instrument code supplied by the prediction pool.": "预测池提供的六位证券代码。",
    "Security name supplied by the prediction pool.": "预测池提供的证券名称。",
    "Identity decoded from the provider board code when recognized; otherwise null.": "能识别来源板块码时解码证券标识，否则为 null。",
    "Exchange decoded from s: 4 is SZSE, 5 is SSE, 6 is BSE; unknown board codes remain null.": "由 s 解码交易所：4 为 SZSE、5 为 SSE、6 为 BSE；未知板块码保留 null。",
    "Original m value; it is not used alone to infer the exchange.": "来源原始 m 值；不会仅凭此值推断交易所。",
    "Original s board code.": "来源原始 s 板块码。",
    "Original e rule code; retained even when FinchX cannot interpret it.": "来源原始 e 规则码；即使 FinchX 无法解释也会保留。",
    "Stable FinchX interpretation derived from recognized board and rule codes; null for unknown rules.": "根据可识别的板块码和规则码生成稳定的 FinchX 语义标识；未知规则为 null。",
    "Readable label for the recognized rule; the provider values remain available separately.": "已识别规则的可读标签；来源原值另行保留。",
    "Source x percentage points divided by 100; 95.69 becomes 0.9569.": "来源 x 百分点除以 100；95.69 转换为 0.9569。",
    "Source d value retained as supplied.": "来源 d 值原样保留。",
    "Source t trigger percentage points divided by 100.": "来源 t 触发涨跌幅百分点除以 100。",
    "Source a percentage points divided by 100.": "来源 a 百分点除以 100。",
    "Derived from o: 0/1 are current-session states, 2 is next-session, other values are unknown.": "根据 o 推导：0/1 表示当前交易日状态，2 表示下一交易日，其他值为 unknown。",
    "o=0 maps to false, 1 to true, and 2 or unknown values to null.": "o=0 映射为 false、1 为 true；2 或未知值映射为 null。",
    "Original o signal-state value.": "来源原始 o 信号状态值。",
    "Original provider row, including source percentage values.": "来源原始行，包括来源百分比数值。",
    "Six-digit instrument code supplied by the count pool.": "次数榜提供的六位证券代码。",
    "Security name supplied by the count pool.": "次数榜提供的证券名称。",
    "Source price in CNY per share.": "来源价格，单位为每股 CNY。",
    "Source a percentage points divided by 100.": "来源 a 百分点除以 100。",
    "Number from /count.t; it is a row-level count, not a pool total.": "/count.t 的记录次数；这是单行次数，不是榜单总数。",
    "Source x percentage points divided by 100.": "来源 x 百分点除以 100。",
    "Original provider row retained, including d whose semantics are not asserted.": "保留来源原始行，包括语义未确认的 d 字段。",
})


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
    key: str | None = None,
    exclude_fields: set[str] | frozenset[str] = frozenset(),
) -> list[tuple[str, str, str]]:
    fallback = "—"
    deviation_descriptions = {
        "DeviationData": {
            "instrumentId": ("Full identity of the requested A-share equity.", "请求 A 股的完整证券标识。"),
            "board": ("Resolved equity board used to select the benchmark index.", "用于选择基准指数的个股板块。"),
            "asOf": ("Normalized observation trading date shared by all scenario rows.", "所有情景记录共用的归一化观察交易日。"),
            "effectiveAsOf": ("Compatibility alias equal to asOf; it is not the end date shared by every row.", "兼容字段，与 asOf 相同；它不是所有记录共用的结束日。"),
            "calculationMode": ("Compatibility summary label; scenario-specific price sources are described by each row.", "兼容性摘要标签；各记录的行情来源由其 scenario 决定。"),
            "priceBasis": ("Reports the actual stock bar scale and raw index points. A stock quote fallback bridges history by previousClose only for QFQ bars; unadjusted day history and quotes stay on their source scale.", "报告实际股票日线口径和未复权指数点位。股票快照仅在 QFQ 日线下按 previousClose 桥接历史；未复权 day 历史与快照保留来源价格尺度。"),
            "ruleVersion": ("Version identifier for the deviation calculation contract.", "偏离值计算契约的版本标识。"),
            "coverageStatus": ("Aggregate historical coverage summary across requested scenario rows.", "所请求情景记录的历史覆盖汇总状态。"),
            "inferredHaltDates": ("Union of stock-gap dates inferred by the requested rows; these are calculation assumptions, not source halt records.", "各记录推定的个股缺口日期并集；这是计算依据，不是来源停牌记录。"),
            "windows": ("Flat scenario records ordered by requested window length and then pre_open, current, next_session.", "扁平情景记录；先按请求窗口长度排序，再依次为 pre_open、current、next_session。"),
        },
        "DeviationWindowData": {
            "windowDays": ("Requested target length: 10 or 30 trading sessions; next_session keeps this length while rolling its candidate boundary.", "请求的目标窗口长度：10 或 30 个交易日；next_session 滚动候选边界但保留此长度。"),
            "scenario": ("Row convention: pre_open ends on the prior session; current ends on asOf; next_session uses asOf prices with the next-session candidate boundary.", "记录口径：pre_open 截至前一交易日；current 截至 asOf；next_session 使用 asOf 价格并采用下一交易日候选边界。"),
            "tradingSessions": ("Observed statistic sessions in the selected maximum-deviation interval, excluding its baseline price point.", "最大偏离选中区间内已观测的统计交易日数，不含基准价格点。"),
            "availableTradingSessions": ("Observed statistic sessions available in this scenario, excluding the baseline and any unobserved future target.", "该情景可用的已观测统计交易日数，不含基准点及未观测的未来目标日。"),
            "windowStatus": ("Whether available observations form a complete target window or a supported partial window.", "可用观测构成完整目标窗口还是受支持的部分窗口。"),
            "coverageStatus": ("Historical coverage and inferred stock-gap summary for this row.", "本记录的历史覆盖和个股缺口推定摘要。"),
            "startDate": ("First statistic session in the selected maximum-deviation interval; not the earliest candidate boundary or return baseline date.", "最大偏离选中区间的首个统计交易日；不是候选边界最早日，也不是收益基准日。"),
            "baselineDate": ("Existing compatibility date equal to stockBaselineDate.", "现有兼容日期字段，与 stockBaselineDate 相同。"),
            "stockBaselineDate": ("Date of the stock price used as the stock-return baseline.", "股票收益率基准价格所属日期。"),
            "benchmarkBaselineDate": ("Date of the index point used as the benchmark-return baseline; it may differ after an inferred halt.", "指数收益率基准点所属日期；停牌缺口推定后可能与股票基准日期不同。"),
            "endDate": ("Date of the terminal stock and benchmark prices actually used.", "实际采用的股票和指数终值所属日期。"),
            "targetDate": ("Trading date defining this row's candidate-window boundary; next_session has no price data for its future target.", "决定本记录候选窗口边界的交易日；next_session 不读取未来目标日行情。"),
            "inferredHaltDates": ("Missing stock-bar dates inferred between observed stock bars; index gaps are not treated as stock halts.", "前后个股 K 线之间推定缺失的日期；指数缺口不会被当作个股停牌。"),
            "stockBaselinePrice": ("Stock-return baseline price in CNY per share on the reported priceBasis.", "股票收益率基准价，单位 CNY/股，采用返回的 priceBasis。"),
            "windowStartPrice": ("Stock price at startDate in CNY per share; distinct from the preceding return-baseline price.", "startDate 当日股票价格，单位 CNY/股；与收益率基准价格不同。"),
            "currentPrice": ("Terminal stock price in CNY per share, using the source and date selected for this scenario.", "本情景采用的股票终值，单位 CNY/股。"),
            "benchmarkInstrument": ("Full identity of the board-specific benchmark index.", "板块对应基准指数的完整证券标识。"),
            "benchmarkName": ("Human-readable name of the board-specific benchmark index.", "板块对应基准指数的名称。"),
            "benchmarkStart": ("Benchmark baseline in index points, retaining its existing field name.", "指数收益率基准点位，保留现有字段名，单位为点。"),
            "benchmarkCurrent": ("Terminal benchmark value in raw index points on endDate.", "endDate 当日指数终值，采用未复权点位。"),
            "stockReturn": ("Stock return ratio from stockBaselinePrice to currentPrice; 0.03 means 3%.", "从 stockBaselinePrice 到 currentPrice 的股票收益率；0.03 表示 3%。"),
            "benchmarkReturn": ("Benchmark return ratio from benchmarkStart to benchmarkCurrent; 0.03 means 3%.", "从 benchmarkStart 到 benchmarkCurrent 的指数收益率；0.03 表示 3%。"),
            "deviation": ("Stock return minus benchmark return for the maximum-deviation candidate; negative values are preserved.", "最大偏离候选的股票收益率减指数收益率；保留负值。"),
            "upperThreshold": ("Fixed upper deviation threshold: 1.00 for 10 sessions or 2.00 for 30 sessions.", "固定上方偏离阈值：10 日为 1.00，30 日为 2.00。"),
            "remainingToUpper": ("Rounded upperTriggerPrice divided by currentPrice minus 1; negative values are preserved.", "进位后的 upperTriggerPrice / currentPrice - 1；保留负值。"),
            "upperTriggerPrice": ("Minimum theoretical stock price across eligible candidates, rounded up to CNY 0.01 after selection; CNY per share.", "按未进位候选值选取合格候选对应的最小理论股价，再向上进位到 0.01 CNY。"),
            "upperTriggerPrice_original": ("Unrounded theoretical price for the selected minimum-price candidate; CNY per share.", "选中的最小候选理论股价的未进位原始值，单位 CNY/股。"),
            "stockSourceTimestamp": ("Source timestamp for a stock quote terminal; null when the terminal comes from a daily bar.", "股票快照终值的来源时间戳；终值来自日线时为 null。"),
            "benchmarkSourceTimestamp": ("Source timestamp for a benchmark quote terminal; null when the terminal comes from a daily bar.", "基准指数快照终值的来源时间戳；终值来自日线时为 null。"),
        },
    }
    rows = []
    for name, field in model.model_fields.items():
        if name in exclude_fields or field.alias in exclude_fields:
            continue
        description = field_description_text(field, language=language, fallback=fallback)
        if not field.description:
            description = common_field_description(field.alias or name, language=language) or fallback
        if key == "market.deviation":
            descriptions = deviation_descriptions.get(model.__name__, {}).get(field.alias or name)
            if descriptions is not None:
                description = descriptions[0 if language == "en" else 1]
        if model.__name__ == "FinancialStatementLineItem":
            if (field.alias or name) == "value":
                description = (
                    "Normalized numeric value for calculations; use this instead of parsing the source text."
                    if language == "en"
                    else "规范化数值，业务计算建议使用此字段，不要自行解析来源文本。"
                )
            elif (field.alias or name) == "sourceValue":
                description = (
                    "Original source value, retained for auditing and unit/content checks."
                    if language == "en"
                    else "保留的来源原始值，仅用于审计及核对单位或内容。"
                )
        if key == "market.orderbook":
            orderbook_descriptions = {
                ("MarketOrderbookData", "instrumentId"): (
                    "Equity instrument for this source book.",
                    "该来源盘口对应的股票证券标识。",
                ),
                ("MarketOrderbookData", "bids"): (
                    "Five Tencent bid slots in source order; zero and null values are retained.",
                    "腾讯来源顺序的五个买盘槽位；保留零值和 null。",
                ),
                ("MarketOrderbookData", "asks"): (
                    "Five Tencent ask slots in source order; zero and null values are retained.",
                    "腾讯来源顺序的五个卖盘槽位；保留零值和 null。",
                ),
                ("MarketOrderbookData", "sourceTimestamp"): (
                    "Tencent quote timestamp with its Shanghai UTC+08:00 offset; distinct from capturedAt.",
                    "腾讯来源行情时间，保留上海时区 UTC+08:00；与 capturedAt 分开。",
                ),
                ("OrderbookLevel", "level"): (
                    "Tencent source slot number from 1 through 5; levels remain in source order.",
                    "腾讯来源槽位编号，范围 1 至 5；按来源顺序保留。",
                ),
                ("OrderbookLevel", "price"): (
                    "CNY per share as a decimal string or null; explicit zero is retained.",
                    "单位为 CNY/股的 Decimal 字符串或 null；显式零值会保留。",
                ),
                ("OrderbookLevel", "size"): (
                    "Whole shares or null; Tencent hands are multiplied by 100. Explicit zero is retained.",
                    "整数股数或 null；腾讯来源手数乘以 100。显式零值会保留。",
                ),
            }
            description = orderbook_descriptions.get(
                (model.__name__, field.alias or name), (None, None)
            )[0 if language == "en" else 1] or description
        if key == "market.ohlcv" and model.__name__ == "MarketKlineData":
            kline_descriptions = {
                "instrumentId": (
                    "Complete FinchX identity; index bars retain market, exchange, kind, and code.",
                    "完整 FinchX 标识；指数 K 线会保留 market、exchange、kind 和 code。",
                ),
                "open": (
                    "Open price: CNY per share for equities; index points for indices.",
                    "开盘价：股票单位为每股 CNY；指数单位为点数。",
                ),
                "high": (
                    "High price: CNY per share for equities; index points for indices.",
                    "最高价：股票单位为每股 CNY；指数单位为点数。",
                ),
                "low": (
                    "Low price: CNY per share for equities; index points for indices.",
                    "最低价：股票单位为每股 CNY；指数单位为点数。",
                ),
                "close": (
                    "Close price: CNY per share for equities; index points for indices.",
                    "收盘价：股票单位为每股 CNY；指数单位为点数。",
                ),
                "volume": (
                    "Provider volume normalized to whole shares (source lots multiplied by 100).",
                    "来源成交量规范化为整股（来源手数乘以 100）。",
                ),
                "amount": (
                    "Provider-reported traded amount in CNY when available.",
                    "来源提供时的成交金额，单位为 CNY。",
                ),
            }
            field_description = kline_descriptions.get(field.alias or name)
            if field_description is not None:
                description = field_description[0 if language == "en" else 1]
        rows.append((field.alias or name, public_annotation_text(field.annotation), description))
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
    "content_id": "同花顺文章 ID。",
    "content_type": "内容榜类别：topic、comment 或 article。",
    "date": "可选文章日期；仅在普通新闻 API 正文不可用时，用于构造 HTML 回退页面 URL。",
    "related_stocks": "热榜文章关联股票，用于与正文侧关联股票合并。",
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
            public_annotation_text(field.annotation),
            required if field.is_required() else optional,
            "—" if field.is_required() else field_default_text(field),
            description,
        ))
    return rows


def parameter_required(endpoint_key_value: str, name: str, parameter: inspect.Parameter, *, language: str) -> str:
    if parameter.default is inspect.Signature.empty:
        return "Required" if language == "en" else "必填"
    return "Optional" if language == "en" else "可选"


def parameter_description(name: str, *, language: str, key: str | None = None) -> str:
    english = {
        "request": "Typed request model for the full request shape.",
        "instrument_id": "Six-digit instrument code; FinchX resolves its market context.",
        "instrument": "Six-digit instrument code; FinchX resolves its market context.",
        "concept": "A ConceptRef returned by concept_list(), or an exact concept name that resolves uniquely.",
        "session": "Required authenticated SESSION cookie for the Jiuyangongshe Provider; handle it like a password and never log or persist it.",
        "start_date": "Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings.", "end_date": "Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings.",
        "requested_date": "Replay date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings.",
        "trade_date": "Trading date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings.",
        "trade_id": "Dragon-Tiger trade identifier.",
        "market": "Market scope; the default is Market.CN_A.",
        "adjustment": "Optional public adjustment: `qfq` means forward-adjusted, `hfq` means backward-adjusted, and Python `None` means unadjusted equities; indexes must use `None`.",
        "statement_type": "balance_sheet, income_statement, or cash_flow_statement.",
        "period_end": "Optional report-period date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings.", "max_periods": "Optional maximum number of report periods.",
        "page": "One-based page number.", "page_size": "Page size.", "max_results": "Optional result cap.",
        "since": "Optional inclusive lower time bound.", "until": "Optional inclusive upper time bound.",
        "sort": "published_desc or published_asc.", "categories": "Optional disclosure category list.",
        "universe": "A-share quote universe; omit it for the full-market snapshot.",
        "criterion": "Choose `amount` for traded amount (CNY), `zdf` for price change (ratio fraction; e.g. 3% is 0.03), or `volume` for traded volume (shares).",
        "direction": "Sort direction: `asc` from lowest to highest or `desc` from highest to lowest.",
        "limit": "Required positive integer or None; None means no limit.",
        "windows": "Deviation windows, in trading sessions.",
        "as_of": "Observation trading date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings.",
        "url": "Report detail page URL from an iWenCai report search hit; it must contain a supported duid.",
        "cookies": "Caller-provided logged-in iWenCai/THS Cookie header.",
        "uid": "Optional report UID from the search hit, used as a fallback.",
        "title": "Optional report title from the search hit, used as a fallback.",
        "published_at": "Optional publication date from the search hit, used as a fallback.",
        "user_agent": "Optional browser User-Agent for the request.",
        "content_id": "Tonghuashun article ID.",
        "content_type": "Content ranking category: topic, comment, or article.",
        "date": "Optional article date used only to build the HTML fallback URL when the ordinary-news API body is unavailable.",
        "related_stocks": "Hotlist-side stock associations to merge with the article-side associations.",
        "sector_type": "Sector category: concept, industry, or index.",
        "dataset": "Required selector: `abnormal_events`, `severe_events`, or `prediction_history`.",
        "status": "For severe events: `current`, `history`, or `all`; omitted/None selects current rows.",
        "triggered": "Prediction-history filter: `yes`, `no`, or `all`; unknown flags match neither yes nor no.",
        "rise_only": "Prediction-history positive-only filter; only the verified provider flag is sent upstream.",
        "include_current": "When false, remove current-session rows locally; unknown current flags remain unknown.",
        "include_bse": "Request BSE rows from the provider.",
        "sort_by": "Provider order key: `count`, `price`, or `max_deviation`.",
        "order": "Provider sort direction: `asc` or `desc`.",
    }
    chinese = {
        "request": "完整的类型化 request 模型。", "instrument_id": "六位证券代码；FinchX 根据接口语义解析市场。",
        "instrument": "六位证券代码；FinchX 根据接口语义解析市场。", "start_date": "包含在内的开始日期。",
        "concept": "concept_list() 返回的 ConceptRef，或可唯一匹配的准确概念名称。",
        "session": "韭研公社 Provider 必填的已认证 SESSION Cookie；按密码处理，切勿记录或持久化。",
        "end_date": "包含在内的结束日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。", "market": "市场范围；默认是 Market.CN_A。",
        "requested_date": "复盘日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。",
        "trade_date": "交易日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。",
        "trade_id": "龙虎榜交易标识。",
        "adjustment": "可选的公开复权参数：`qfq` 表示前复权，`hfq` 表示后复权，Python `None` 表示股票不复权；指数必须使用 `None`。", "statement_type": "balance_sheet、income_statement 或 cash_flow_statement。",
        "period_end": "可选的报告期结束日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。", "max_periods": "可选的最大报告期数量。",
        "page": "从 1 开始的页码。", "page_size": "单页数量。", "max_results": "可选的结果上限。",
        "since": "可选的时间范围起点。", "until": "可选的时间范围终点。",
        "sort": "published_desc 或 published_asc。", "categories": "可选的公告分类列表。",
        "universe": "A 股行情范围；省略时获取全市场快照。",
        "criterion": "可选 `amount`（成交额，单位 CNY）、`zdf`（涨跌幅，比例小数，例如 3% 为 0.03）或 `volume`（成交量，单位为股）。",
        "direction": "排序方向：`asc` 表示从低到高，`desc` 表示从高到低。",
        "limit": "必填；正整数或 None；None 表示不限制返回数量。", "windows": "以交易时段计的偏离窗口。",
        "as_of": "观察基准交易日；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。",
        "url": "问财研报搜索结果中的详情页 URL，必须包含受支持的 duid。",
        "cookies": "调用者提供的问财/同花顺登录态 Cookie header。",
        "uid": "可选的搜索结果研报 UID，用作备用值。",
        "title": "可选的搜索结果研报标题，用作备用值。",
        "published_at": "可选的搜索结果发布日期，用作备用值。",
        "user_agent": "可选的浏览器 User-Agent。",
        "content_id": "同花顺文章 ID。",
        "content_type": "内容榜类别：topic、comment 或 article。",
        "date": "可选文章日期；仅在普通新闻 API 正文不可用时，用于构造 HTML 回退页面 URL。",
        "related_stocks": "热榜文章关联股票，用于与正文侧关联股票合并。",
        "sector_type": "板块类别，可选 concept、industry 或 index。",
        "dataset": "必填选择项：`abnormal_events`、`severe_events` 或 `prediction_history`。",
        "status": "仅适用于严重事件：`current`、`history` 或 `all`；省略/None 时读取当前记录。",
        "triggered": "预测历史筛选：`yes`、`no` 或 `all`；未知标记既不匹配 yes 也不匹配 no。",
        "rise_only": "预测历史只看上涨记录；仅发送已验证的来源筛选标记。",
        "include_current": "设为 false 时在本地排除当前交易日记录；来源状态未知时仍保留为未知。",
        "include_bse": "请求来源返回北交所记录。",
        "sort_by": "来源排序字段：`count`、`price` 或 `max_deviation`。",
        "order": "来源排序方向：`asc` 或 `desc`。",
        "topic_url": "同花顺 T-code 主题分享 URL；仅允许两个已确认的社区主题路径。",
    }
    if key == "market.severe_predictions" and name == "rise_only":
        return (
            "When true, request only rows the provider marks as rising."
            if language == "en"
            else "为 true 时，只请求来源标记为上涨的记录。"
        )
    if name == "url" and key == "articles.get":
        return (
            "Public Tonghuashun news or community article URL; route and ID are parsed from its allowlisted host and path."
            if language == "en"
            else "同花顺普通新闻或股吧直播文章 URL；news/zhibo 类型和文章 ID 根据允许的主机与路径解析。"
        )
    hotlist_descriptions = {
        ("hotlist.stocks", "category"): (
            "One of `popular` (popularity), `rising` (rising heat), `new` (new listings), `technical` (technical analysis), `value` (value investing), or `trend` (trend analysis).",
            "可选 `popular`（人气）、`rising`（飙升）、`new`（新股）、`technical`（技术分析）、`value`（价值投资）或 `trend`（趋势）。",
        ),
        ("hotlist.stocks", "period"): (
            "Optional ranking window: `1h` or `24h`. `popular` and `rising` support both; other categories support only `24h`.",
            "可选统计周期：`1h` 或 `24h`。`popular` 和 `rising` 支持两种周期；其他类别仅支持 `24h`。",
        ),
        ("hotlist.etfs", "category"): (
            "One of `popular` (popular ETFs), `t0` (T+0 ETFs), `price_limit_20` (20% price-limit ETFs), `cross_border` (cross-border ETFs), or `commodity` (commodity ETFs).",
            "可选 `popular`（热门 ETF）、`t0`（T+0 ETF）、`price_limit_20`（20% 涨跌幅限制 ETF）、`cross_border`（跨境 ETF）或 `commodity`（商品 ETF）。",
        ),
        ("hotlist.content", "content_type"): (
            "One of `topic` (topics), `comment` (popular comments), or `article` (popular articles).",
            "可选 `topic`（话题）、`comment`（热评）或 `article`（热文）。",
        ),
        ("hotlist.sectors", "sector_type"): (
            "One of `concept` (concept sectors), `industry` (industry sectors), or `index` (indexes).",
            "可选 `concept`（概念板块）、`industry`（行业板块）或 `index`（指数）。",
        ),
    }
    if key == "market.abnormal_records" and name == "page":
        return (
            "One-based upstream page number. A request fetches this page only; local current-session exclusion does not scan other pages."
            if language == "en"
            else "从 1 开始的上游页码。每次只获取这一页；本地当前交易日筛选不会扫描其他页。"
        )
    if key == "market.abnormal_records" and name == "page_size":
        return (
            "Rows requested from the upstream page; maximum 200. Local current-session exclusion may reduce the returned row count."
            if language == "en"
            else "从上游请求的单页行数；最大 200。本地排除当前交易日记录后，返回行数可能减少。"
        )
    if key == "market.quote_snapshot" and name == "instrument":
        return (
            "Six-digit equity code, or a full index identity such as `cn_a:sse:index:000001` or `cn_a:szse:index:399001`. In this generic endpoint a bare `000001` means a SZSE equity. Supported indices are `cn_a:sse:index:000001`, `cn_a:sse:index:000002`, `cn_a:sse:index:000688`, `cn_a:szse:index:399001`, `cn_a:szse:index:399006`, `cn_a:szse:index:399102`, and `cn_a:szse:index:399107`."
            if language == "en"
            else "六位股票代码，或指数完整标识，例如 `cn_a:sse:index:000001`、`cn_a:szse:index:399001`。此通用接口中裸代码 `000001` 表示深交所股票。支持的指数为 `cn_a:sse:index:000001`、`cn_a:sse:index:000002`、`cn_a:sse:index:000688`、`cn_a:szse:index:399001`、`cn_a:szse:index:399006`、`cn_a:szse:index:399102` 和 `cn_a:szse:index:399107`。"
        )
    if key == "market.ohlcv" and name == "instrument":
        return (
            "Six-digit equity code, or a full identity for one of the seven supported indices: `cn_a:sse:index:000001`, `cn_a:sse:index:000002`, `cn_a:sse:index:000688`, `cn_a:szse:index:399001`, `cn_a:szse:index:399006`, `cn_a:szse:index:399102`, or `cn_a:szse:index:399107`. In this generic endpoint a bare `000001` means a SZSE equity."
            if language == "en"
            else "六位股票代码，或以下七个受支持指数之一的完整标识：`cn_a:sse:index:000001`、`cn_a:sse:index:000002`、`cn_a:sse:index:000688`、`cn_a:szse:index:399001`、`cn_a:szse:index:399006`、`cn_a:szse:index:399102` 或 `cn_a:szse:index:399107`。此通用接口中裸代码 `000001` 表示深交所股票。"
        )
    if key is not None and (key, name) in hotlist_descriptions:
        return hotlist_descriptions[(key, name)][0 if language == "en" else 1]
    if name == "limit" and key in {
        "hotlist.stocks",
        "hotlist.etfs",
        "hotlist.content",
        "hotlist.sectors",
    }:
        return (
            "Optional positive integer; the minimum is 1 and the default is 20."
            if language == "en"
            else "可选正整数，最小值为 1，默认值为 20。"
        )
    if key == "articles.from_topic":
        topic_descriptions = {
            "topic_url": (
                "Public HTTPS Tonghuashun T-code topic URL. Deep-topic report URLs are recognized and rejected because no report-scoped news feed is available."
                if language == "en"
                else "同花顺 T-code 主题 HTTPS URL。可识别 deep-topic 报告链接并明确拒绝，因为当前没有该报告专属的新闻 Feed。"
            ),
            "sort": (
                "Only `recommend` is supported: source-ordered recommendations followed by the paginated ordinary feed."
                if language == "en"
                else "目前仅支持 `recommend`：按源顺序读取推荐内容，并在推荐耗尽后继续分页读取普通 Feed。"
            ),
            "limit": (
                "Maximum number of supported news and long-article records after filtering the mixed feed; must be between 1 and 100."
                if language == "en"
                else "混合 Feed 过滤后最多返回的已支持新闻和长文数；范围为 1 到 100。"
            ),
        }
        if name in topic_descriptions:
            return topic_descriptions[name]
    return (english if language == "en" else chinese).get(name, "Parameter." if language == "en" else "参数。")


def summary_for(key: str, method: Any, *, language: str) -> str:
    if language == "zh":
        return SUMMARY_ZH.get(key, "公开数据接口。")
    summary_en = {
        "hotlist.stocks": "Fetch A-share stock heat rankings by category and 1-hour or 24-hour period.",
        "hotlist.sectors": "Fetch concept, industry, or index-sector heat rankings with available ETF enrichment.",
        "hotlist.convertible_bonds": "Fetch convertible-bond heat rankings while preserving missing price changes.",
        "hotlist.etfs": "Fetch ETF heat rankings sorted by Tonghuashun attention metrics, with available tags.",
        "hotlist.content": "Fetch topic, comment, or article rankings with a distinct data shape for each type.",
        "articles.get": "Fetch one ordinary news or community article from its public Tonghuashun URL.",
        "articles.from_topic": "List supported news and long-article refs from a T-code topic's mixed feed; each returned URL is accepted by `articles.get`.",
        "market.ranking": "Rank A-share stocks by traded amount, price change, or volume.",
        "market.regulation_watchlist": "Fetch EastMoney's latest regulation watchlist, including rows with unverified security kinds.",
        "market.abnormal_records": "Fetch one upstream page from ordinary events, severe events, or prediction history.",
        "market.severe_predictions": "Fetch the bounded severe-prediction pool and preserve unrecognized provider states.",
        "market.abnormal_counts": "Fetch the bounded abnormal-count pool while keeping ambiguous provider counters as raw evidence.",
        "market.ohlcv": "Fetch daily OHLCV history for an SSE/SZSE equity or supported index.",
        "market.quote_snapshot": "Fetch a current quote snapshot for an SSE/SZSE equity or supported index.",
        "market.orderbook": "Fetch Tencent's five-level equity book while preserving source slot order and null values.",
        "market.deviation": "Calculate pre-open, current-session, and next-session deviation rows against the board benchmark.",
    }
    if key in summary_en:
        return summary_en[key]
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


def _parameter_rows(key: str, method: Any, *, language: str) -> list[tuple[str, str, str, str, str]]:
    rows = []
    for name, parameter in inspect.signature(method).parameters.items():
        if name in {"provider", "use_cache"}:
            continue
        rows.append((
            name,
            public_annotation_text(parameter.annotation),
            parameter_required(key, name, parameter, language=language),
            "—" if parameter.default is inspect.Signature.empty else default_text(parameter.default),
            parameter_description(name, language=language, key=key),
        ))
    return rows


def _output_sections(model: type[BaseModel], *, language: str, key: str) -> list[str]:
    is_root = issubclass(model, RootModel)
    if language == "en":
        lines = ["**Output fields**", "", f"Data model: `{model.__name__}`", ""]
        rows = [] if is_root else output_field_rows(model, language=language, key=key)
        lines.append(table(("Field", "Type", "Meaning"), rows) if rows else "No business fields.")
        if is_root:
            lines[-1] = "A tagged union of the row models below; `dataset` identifies the row type."
        nested_heading = "Nested business model"
        nested_separator = ":"
    else:
        lines = ["**输出字段**", "", f"数据模型：`{model.__name__}`", ""]
        rows = [] if is_root else output_field_rows(model, language=language, key=key)
        lines.append(table(("字段", "类型", "含义"), rows) if rows else "无业务字段。")
        if is_root:
            lines[-1] = "以下行模式组成带标签的联合类型；`dataset` 标识具体行类型。"
        nested_heading = "嵌套业务模型"
        nested_separator = "："
    for nested in nested_models(model):
        nested_rows = output_field_rows(nested, language=language, key=key)
        lines += ["", f"{nested_heading}{nested_separator} `{nested.__name__}`", ""]
        lines.append(table(("Field", "Type", "Meaning"), nested_rows) if language == "en" else table(("字段", "类型", "含义"), nested_rows))
    return lines


def _result_usage_note(key: str, model: type[BaseModel], *, language: str) -> str:
    aliases = [field.alias or name for name, field in model.model_fields.items()]
    if key == "market.daily_replay":
        important = [name for name in ("requestedDate", "tradeDate", "themes") if name in aliases]
    else:
        important = aliases[:4]
    if key == "market.abnormal_records":
        important = ["dataset", "code", "name", "exchange"]
    fields = ", ".join(f"`{name}`" for name in important) if important else "business fields"
    if key in {"news.search", "disclosure.search", "market_news.search"}:
        shape_en = "`.data` is a tuple of typed document references."
        shape_zh = "`.data` 是带类型的文档引用元组。"
    elif key == "market.deviation":
        shape_en = "`.data` is one `DeviationData` model."
        shape_zh = "`.data` 是一个 `DeviationData` 模型。"
    elif key == "articles.get":
        shape_en = "`.data` is one normalized record."
        shape_zh = "`.data` 是一条标准化记录。"
    elif key == "market.orderbook":
        shape_en = "`.data` is one normalized `StandardRecord`."
        shape_zh = "`.data` 是一条标准化 `StandardRecord`。"
    else:
        shape_en = "`.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload."
        shape_zh = "`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。"
    if language == "en":
        if key == "market.orderbook":
            return (
                f"{shape_en} `{model.__name__}` exposes the Tencent book slots. Each of `bids` and `asks` has five source levels in source order; FinchX does not sort or remove zero-valued or null-valued slots. `price` is a decimal string or `null`; `size` is an integer share count or `null`, after converting Tencent hands to shares (`hands × 100`). Explicit zero remains zero. `sourceTimestamp` is Tencent's Shanghai-time quote timestamp and is separate from FinchX `capturedAt`. Tencent's empty sentinels become typed null values; null does not establish that a physical exchange level is absent. Status is `missing` only when every source price and size is null; any explicit zero counts as reported data. This next unreleased package intentionally changes the previous filtered and price-sorted output contract. No auction, limit-up, or order-amount interpretation is inferred. Export with `.to_dicts()`."
            )
        if key == "market.ranking":
            return (
                f"{shape_en} The Dataset row schema `{model.__name__}` has business fields such as {fields}. "
                "Use the named business fields for follow-up filtering, comparisons, or charts. "
                "Tencent rankings are fetched from live pages. If a stock repeats on a later page, FinchX keeps its first row and skips the repeat; the result then has partial coverage. "
                "The requested `limit` is a source-row budget; skipped repeats do not trigger extra pages to refill unique rows. "
                "Check `.warnings` and `.metadata` for `coverage_status`, `requested_count`, `source_row_count`, `unique_count`, `source_total`, and `duplicate_rows_skipped`. "
                "`position` preserves the source row number, so gaps can appear. The pages do not form a consistent point-in-time snapshot, even when no repeats appear. "
                "Export JSON-compatible rows with `.to_dicts()`."
            )
        if key == "reference.trading_calendar":
            action = "Each natural date in the inclusive range appears once, and the interface always uses the unified A-share calendar."
        elif key == "market.daily_replay":
            action = (
                "Use `tradeDate` to identify the returned session, then inspect `themes` for the close review. "
                "If you log in again, refresh `SESSION` because the previous cookie may no longer be accepted. "
                "Errors identify the failed transport stage without including cookie values, URL query parameters, or raw browser messages. "
                "An explicit HTTP 401/403 or source `errCode=1/110` response is reported as an authentication/access failure immediately, even if the other API response is missing."
            )
        elif key == "market.deviation":
            action = "Iterate the three scenario rows per requested window in `windows`; use `asOf` as the observation date. `effectiveAsOf` is a compatibility alias."
        elif key.startswith("market.index_intraday"):
            action = "Use the time and price series to chart the index session."
        elif key.startswith("market.equity_intraday"):
            action = "Use the time and price series to chart the stock session."
        elif key.startswith("market.concept_"):
            action = "Use the concept identity and quote or bar fields to compare sector movement."
        elif key.startswith(("news.", "disclosure.", "market_news.")):
            action = "Use the reference fields to select documents, then pass a reference to the matching detail method."
        elif key.startswith("hotlist."):
            action = "Use the rank and entity fields to inspect or compare the returned leaders."
        elif key == "financial.statements":
            action = "For calculations use normalized `lineItems[].value`; keep `sourceValue` only to verify the original source text or unit."
        elif key.startswith(("fundamental.", "financial.", "ownership.", "company.", "corporate_action.")):
            action = "Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions."
        elif key.startswith("iwencai."):
            action = "Use the normalized fields and `extraFields` for screening or research follow-up."
        else:
            action = "Use the named business fields for follow-up filtering, comparisons, or charts."
        completeness = " `result.metadata` reports `upstream_page`, `upstream_pages`, `has_more`, `page_complete`, and `collection_complete` where pagination applies." if key in {"market.abnormal_records", "market.severe_predictions", "market.abnormal_counts", "market.regulation_watchlist"} else ""
        return f"{shape_en} The Dataset row schema `{model.__name__}` has business fields such as {fields}. {action} Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results.{completeness}"
    if key == "market.orderbook":
        return (
            f"{shape_zh} `{model.__name__}` 展示腾讯盘口槽位。`bids` 和 `asks` 各含来源顺序的五档；FinchX 不排序，也不删除零值或 null 槽位。`price` 是 Decimal 字符串或 `null`；`size` 是整数股数或 `null`，Tencent 来源手数会乘以 100 转为股数。显式零值仍为 0。`sourceTimestamp` 是 Tencent 上海时区的来源行情时间，与 FinchX 的 `capturedAt` 分开。Tencent 空字符串、`-` 和 `--` 会转为带类型的 null；null 不证明交易所物理档位不存在。只有全部来源价格和数量都为 null 时状态才是 `missing`；任何显式零值都算来源已提供数据。下一未发布版本会有意改变旧版滤除空档并按价格排序的输出契约。不推断竞价封板、涨停入表或委托额语义。用 `.to_dicts()` 导出。"
        )
    if key == "market.ranking":
        return (
            f"{shape_zh} Dataset 行模式 `{model.__name__}` 的业务字段包括 {fields} 等。"
            "腾讯排名通过实时分页获取。如果某只股票在后续页再次出现，FinchX 保留首次记录并跳过重复行，此时结果会标记为部分覆盖。请求的 `limit` 按来源行数计；跳过重复行后不会再请求额外页面补足唯一记录。"
            "请检查 `.warnings` 和 `.metadata` 中的 `coverage_status`、`requested_count`、`source_row_count`、`unique_count`、`source_total` 与 `duplicate_rows_skipped`。"
            "`position` 保留来源行号，因此可能出现名次缺口。多页结果不代表同一时点快照，即使没有观察到重复也不能据此确认快照一致。"
            "用 `.to_dicts()` 导出 JSON 兼容数据。"
        )
    if key == "reference.trading_calendar":
        action = "闭区间内每个自然日各返回一行，接口固定使用统一的 A 股交易日历。"
    elif key == "market.daily_replay":
        action = (
            "用 `tradeDate` 确认返回的交易日，再检查 `themes` 完成盘后复盘。"
            "重新登录后旧 `SESSION` 可能失效，请传入当前会话的 Cookie。错误会标明失败阶段，且不包含 Cookie、URL 查询参数或浏览器原始异常。"
            "来源明确返回 HTTP 401/403 或 `errCode=1/110` 时会立即报告认证或访问失败，即使另一个 API 响应缺失。"
        )
    elif key == "market.deviation":
        action = "遍历 `windows` 中每个请求窗口对应的三种情景记录；使用 `asOf` 作为观察日。`effectiveAsOf` 是兼容别名。"
    elif key.startswith("market.index_intraday"):
        action = "用时间序列和价格字段绘制指数交易日走势。"
    elif key.startswith("market.equity_intraday"):
        action = "用时间序列和价格字段绘制个股交易日走势。"
    elif key.startswith("market.concept_"):
        action = "用概念标识及行情或 K 线字段比较板块走势。"
    elif key.startswith(("news.", "disclosure.", "market_news.")):
        action = "用引用字段筛选目标文档，再将引用传给对应详情方法。"
    elif key.startswith("hotlist."):
        action = "用排名和实体字段查看或比较榜单靠前的对象。"
    elif key == "financial.statements":
        action = "业务计算建议使用规范化的 `lineItems[].value`；`sourceValue` 仅用于核对来源原始文本或单位。"
    elif key.startswith(("fundamental.", "financial.", "ownership.", "company.", "corporate_action.")):
        action = "用类型化字段或导出行比较报告期、股东、高管或公司行动。"
    elif key.startswith("iwencai."):
        action = "使用规范化字段和 `extraFields` 进行筛选或继续研究。"
    else:
        action = "使用这些业务字段进行后续筛选、比较或绘图。"
    completeness_zh = " 分页相关的 `result.metadata` 会提供 `upstream_page`、`upstream_pages`、`has_more`、`page_complete` 和 `collection_complete`。" if key in {"market.abnormal_records", "market.severe_predictions", "market.abnormal_counts", "market.regulation_watchlist"} else ""
    return f"{shape_zh} Dataset 行模式 `{model.__name__}` 的业务字段包括 {fields} 等。{action} 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。{completeness_zh}"


_EXAMPLE_VALUES: dict[str, str] = {
    "instrument": '"600519"',
    "instrument_id": '"600519"',
    "concept": '"人工智能"',
    "start_date": '"2026-09-01"',
    "end_date": '"2026-09-23"',
    "requested_date": '"2026-09-23"',
    "trade_date": '"2026-09-23"',
    "trade_id": '"600519-20260923-01"',
    "market": '"cn_a"',
    "universe": '"cn_a_share"',
    "adjustment": '"qfq"',
    "criterion": '"amount"',
    "direction": '"desc"',
    "limit": "20",
    "category": '"popular"',
    "period": '"24h"',
    "sector_type": '"industry"',
    "content_type": '"topic"',
    "statement_type": '"income_statement"',
    "period_end": '"2026-06-30"',
    "max_periods": "4",
    "query": '"成交额排名前500，最新价高于5日均线，非ST"',
    "cookies": "cookies",
    "session": "jygs_session",
    "user_agent": '"Mozilla/5.0 (compatible; FinchX documentation example)"',
    "page": "1",
    "page_size": "20",
    "max_pages": "5",
    "max_results": "50",
    "since": '"2026-09-01"',
    "until": '"2026-09-23"',
    "sort": '"published_desc"',
    "categories": "None",
    "size": "20",
    "channel": '"report"',
    "api_key": "api_key",
    "deduplicate": "True",
    "url": '"https://stock.10jqka.com.cn/20260923/c680236250.shtml"',
    "uid": '"example-report-uid"',
    "title": '"示例研报标题"',
    "published_at": '"2026-09-23"',
    "windows": "(10, 30)",
    "as_of": '"2026-09-23"',
    "sort": '"published_desc"',
    "topic_url": '"https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=T4dryo6"',
    "related_stocks": "None",
    "date": '"2026-09-23"',
}

_EXAMPLE_COMMENTS = {
    "en": {
        "instrument": "Six-digit A-share code; the endpoint resolves its market.",
        "instrument_id": "Six-digit A-share code.",
        "concept": "Exact concept name; use a ConceptRef when available.",
        "start_date": "Inclusive start date.", "end_date": "Inclusive end date.",
        "requested_date": "Requested replay date.", "trade_date": "Trading date.",
        "trade_id": "Example source trade identifier.", "market": "A-share market scope.",
        "universe": "A-share quote universe; omit it for the full-market snapshot.", "adjustment": "Forward-adjusted stock prices.",
        "criterion": "Rank by traded amount.", "direction": "Sort from largest to smallest.",
        "limit": "Return at most 20 rows.", "category": "Popularity ranking category.",
        "period": "24-hour ranking window.", "sector_type": "Industry-sector ranking.",
        "content_type": "Topic-content ranking.", "statement_type": "Income statement.",
        "period_end": "Report period ending on this date.", "max_periods": "Return up to four periods.",
        "query": "Natural-language iWenCai query.", "cookies": "Caller-owned login Cookie; keep it secret.",
        "session": "Caller-owned Jiuyangongshe SESSION cookie.", "user_agent": "Browser-compatible request header.",
        "page": "Start from the first page for a complete date scan.", "page_size": "Rows requested per source page.",
        "max_pages": "Bound the number of iWenCai pages.", "max_results": "Stop after at most 50 matches.",
        "since": "Inclusive lower publication/reply date.", "until": "Inclusive upper publication/reply date.",
        "sort": "Newest items first.", "categories": "No disclosure category filter.",
        "size": "Number of semantic-search hits.", "channel": "Search reports.",
        "api_key": "SkillHub API key; load it from a secret store.", "deduplicate": "Remove duplicate search hits.",
        "url": "Public article or report detail URL.", "uid": "Fallback report identifier.",
        "title": "Fallback report title.", "published_at": "Fallback publication date.",
        "windows": "Return three scenario records for each requested 10- or 30-session window.", "as_of": "Observation trading date; historical queries use that session's close data.",
        "topic_url": "Supported Tonghuashun topic URL.", "related_stocks": "No additional stock associations.",
        "date": "Date used only by the article fallback URL.",
    },
    "zh": {
        "instrument": "六位 A 股代码；接口会解析其市场。", "instrument_id": "六位 A 股代码。",
        "concept": "准确概念名称；有 ConceptRef 时优先使用。", "start_date": "包含在内的开始日期。",
        "end_date": "包含在内的结束日期。", "requested_date": "复盘日期。", "trade_date": "交易日期。",
        "trade_id": "示例数据源交易标识。", "market": "A 股市场范围。", "universe": "A 股行情范围；省略时获取全市场快照。",
        "adjustment": "股票前复权价格。", "criterion": "按成交额排名。", "direction": "从大到小排序。",
        "limit": "最多返回 20 行。", "category": "人气榜类别。", "period": "24 小时榜单周期。",
        "sector_type": "行业板块榜。", "content_type": "话题内容榜。", "statement_type": "利润表。",
        "period_end": "报告期结束日期。", "max_periods": "最多返回四个报告期。",
        "query": "问财自然语言条件。", "cookies": "调用者自己的登录 Cookie；按秘密凭证保管。",
        "session": "调用者自己的韭研公社 SESSION Cookie。", "user_agent": "兼容浏览器的请求头。",
        "page": "从第一页开始完整扫描日期范围。", "page_size": "每页请求的数据行数。",
        "max_pages": "限制问财最多读取的页数。", "max_results": "最多返回 50 条匹配结果。",
        "since": "包含在内的发布时间/回复时间下界。", "until": "包含在内的发布时间/回复时间上界。",
        "sort": "按发布时间从新到旧。", "categories": "不筛选公告分类。", "size": "语义搜索命中数量。",
        "channel": "搜索研报。", "api_key": "SkillHub API Key；从密钥存储读取。", "deduplicate": "去除重复命中。",
        "url": "公开文章或研报详情 URL。", "uid": "备用研报标识。", "title": "备用研报标题。",
        "published_at": "备用发布日期。", "windows": "比较 10 和 30 个交易时段。",
        "as_of": "观察基准交易日；历史查询使用该交易日的收盘数据。",
        "topic_url": "受支持的同花顺话题 URL。", "related_stocks": "不额外合并股票关联。",
        "date": "仅在构造文章回退 URL 时使用的日期。",
    },
}


def _example_value(key: str, name: str, parameter: inspect.Parameter) -> str:
    if name in {"instrument", "instrument_id"} and key in {"market.index_intraday", "market.index_intraday_5d"}:
        return '"000001"'
    if name == "category" and key == "hotlist.etfs":
        return '"cross_border"'
    if name == "query" and key.startswith("iwencai.") and key != "iwencai.select":
        return '"人形机器人 行星滚柱丝杠"'
    if name == "sort" and key == "articles.from_topic":
        return '"recommend"'
    if name in _EXAMPLE_VALUES:
        return _EXAMPLE_VALUES[name]
    if parameter.default is not inspect.Signature.empty:
        return default_text(parameter.default)
    raise ValueError(f"no example value for required parameter {key}.{name}")


def _example_code(key: str, method: Any, *, language: str) -> str:
    comments = _EXAMPLE_COMMENTS[language]
    parameters = inspect.signature(method).parameters
    if key == "market.abnormal_records":
        if language == "en":
            return "\n".join([
                "from finchx import FinchX",
                "",
                "fx = FinchX()",
                "# Each call fetches one page from the selected dataset; request later pages explicitly.",
                'ordinary = fx.market.abnormal_records(dataset="abnormal_events", page=1, page_size=20)',
                'severe = fx.market.abnormal_records(dataset="severe_events", page=1, page_size=20, status="current")',
                'history = fx.market.abnormal_records(dataset="prediction_history", page=1, page_size=20, triggered="all", rise_only=False, include_current=None)',
                "for name, result in ((\"ordinary\", ordinary), (\"severe\", severe), (\"history\", history)):",
                "    print(name, result.to_dicts()[:1], result.metadata.get(\"has_more\"))",
                "    print(result.warnings)",
            ])
        return "\n".join([
            "from finchx import FinchX",
            "",
            "fx = FinchX()",
            "# 每次调用只取指定 dataset 的一页；需要后续数据时显式请求下一页。",
            'ordinary = fx.market.abnormal_records(dataset="abnormal_events", page=1, page_size=20)',
            'severe = fx.market.abnormal_records(dataset="severe_events", page=1, page_size=20, status="current")',
            'history = fx.market.abnormal_records(dataset="prediction_history", page=1, page_size=20, triggered="all", rise_only=False, include_current=None)',
            "for name, result in ((\"ordinary\", ordinary), (\"severe\", severe), (\"history\", history)):",
            "    print(name, result.to_dicts()[:1], result.metadata.get(\"has_more\"))",
            "    print(result.warnings)",
        ])
    example_parameters = {
        name: parameter
        for name, parameter in parameters.items()
        if name not in {"provider", "use_cache"}
        and not (key == "market.quote" and name == "universe")
        and not (key in {"market.severe_predictions", "market.abnormal_counts"} and name == "instrument")
    }
    values = {
        name: _example_value(key, name, parameter)
        for name, parameter in example_parameters.items()
    }
    lines = ["from finchx import FinchX", "", "fx = FinchX()"]
    if "session" in parameters:
        lines += ['jygs_session = "<SESSION cookie from your logged-in browser>"']
    if "cookies" in parameters:
        lines += ['cookies = "<Cookie header from your logged-in browser>"']
    if "api_key" in parameters:
        lines += ['api_key = "<IWENCAI_API_KEY>"']
    if len(lines) > 3:
        lines.append("")
    if not example_parameters:
        lines.append(f"result = fx.{key}()")
    else:
        lines.append(f"result = fx.{key}(")
        for name in example_parameters:
            if key == "articles.from_topic" and name == "sort":
                comment = "Use the source recommendation order." if language == "en" else "按来源推荐顺序展示。"
            elif key == "market.severe_predictions" and name == "rise_only":
                comment = "Request only rows the provider marks as rising." if language == "en" else "只请求来源标记为上涨的记录。"
            else:
                comment = comments.get(name, parameter_description(name, language=language, key=key))
            value = values[name]
            lines.append(f"    {name}={value},  # {comment}")
        lines.append(")")
    lines += ["", "print(result.data)  # Native typed data or records.", "rows = result.to_dicts()  # JSON-compatible business rows.", "print(rows[:1])", "print(result.warnings)  # Check for partial or recoverable issues."]
    if language == "zh":
        lines[-5:] = ["print(result.data)  # 原生类型数据或记录。", "rows = result.to_dicts()  # JSON 兼容的业务数据行。", "print(rows[:1])", "print(result.warnings)  # 检查部分数据和可恢复问题。"]
    if key == "market.quote_snapshot":
        lines += [
            "",
            "# Use complete identities; a bare 000001 means the SZSE equity on this generic endpoint." if language == "en" else "# 使用完整标识；此通用接口中的裸 000001 表示深交所股票。",
            'sse_index = fx.market.quote_snapshot(instrument="cn_a:sse:index:000001")',
            'szse_index = fx.market.quote_snapshot(instrument="cn_a:szse:index:399001")',
            "print(sse_index.to_dicts()[:1])",
            "print(szse_index.to_dicts()[:1])",
        ]
    elif key == "market.ohlcv":
        lines += [
            "",
            "# Index bars use explicit identity and no price adjustment." if language == "en" else "# 指数 K 线使用完整标识，且不复权。",
            'index_bars = fx.market.ohlcv("cn_a:sse:index:000001", "2026-09-01", "2026-09-23", adjustment=None)',
            "print(index_bars.to_dicts()[:1])",
        ]
    return "\n".join(lines)


def _deviation_method_notes(*, language: str) -> list[str]:
    if language == "en":
        return [
            "**Scope and calculation**",
            "FinchX reports market inputs and calculations only. It does not decide whether a formal abnormal-movement event occurred and does not return trigger, risk, trading, or alert judgments. The top-level `effectiveAsOf` and `calculationMode` are retained compatibility fields: `effectiveAsOf` aliases `asOf`, and `calculationMode` is `scenario_based`.",
            "Supported equities are SSE `60xxxx` and `68xxxx`, and SZSE `00xxxx` and `30xxxx`; BSE equities are not supported. Each board uses its corresponding benchmark:",
            "",
            table(("Equity code", "Board", "Benchmark index"), [
                ("SSE `60xxxx`", "SSE main board", "SSE A Share Index (`000002`)"),
                ("SSE `68xxxx`", "STAR", "SSE STAR 50 Index (`000688`)"),
                ("SZSE `00xxxx`", "SZSE main board", "SZSE A Share Index (`399107`)"),
                ("SZSE `30xxxx`", "ChiNext", "ChiNext Composite Index (`399102`)"),
            ]),
            "",
            "Each requested window length returns three flat rows in `pre_open`, `current`, `next_session` order. With the default `(10, 30)`, `windows` contains six rows. `as_of` identifies the observation trading session; a non-trading date follows the existing prior-session normalization. `endDate` identifies the terminal prices actually used, `targetDate` defines that row's candidate boundary, and `startDate` is the start of the selected maximum-deviation interval.",
            "",
            "For an observation session D10, `pre_open` always ends on prior session D9 and is unaffected by D10 prices. During D10, `current` and `next_session` use validated same-day stock and index quote snapshots. After the session, FinchX uses each available D10 daily bar for its own terminal value (stock QFQ bar, index raw bar); it requests a quote only for a side whose D10 bar is missing. A stock quote fallback bridges QFQ stock history through that quote's `previousClose`; an index quote remains in raw index points. A post-close quote may carry a same-day timestamp before 15:00, such as 14:59. Its source date, instrument, positive price, and non-future timestamp are checked, but it is not described as a confirmed daily close. Quote fallback warnings apply only to `current` and `next_session`. The two terminal sources are recorded as `result.metadata.stock_terminal_source` and `benchmark_terminal_source`; a bar has a null row source timestamp, while a quote retains its source timestamp. `next_session` ends on D10 too, targets D11, and shares the same stock/index terminal prices as `current`; only its candidate boundary rolls forward. It reads no D11 price and creates no D11 bar. Historical `as_of` queries use that session's daily bars and cannot reproduce an earlier intraday instant.",
            "",
            "The top-level `priceBasis` reports the actual stock Kline scale: `qfq_stock__raw_index` when Tencent returns QFQ bars, or `raw_stock__raw_index` when a QFQ request uses the documented unadjusted `day` fallback. For QFQ bars, a stock quote fallback bridges history by that quote's `previousClose`; for unadjusted bars, FinchX keeps history and quote values on their source scale without a QFQ bridge. The requested and actual adjustment, source series, and any fallback warning are available in `result.metadata` and `result.warnings`. Index bars and quotes remain raw index points. `price_inputs`, `stock_terminal_source`, and `benchmark_terminal_source` describe the D10 inputs for `current` and `next_session`; `terminal_source_scope` identifies those scenarios, while `pre_open` always uses D9 bars. Each terminal-source value is `same_day_daily_bar`, `same_day_quote`, or `historical_daily_bar`. `price_inputs` distinguishes historical bars, intraday quotes with daily history, after-close daily bars, one-sided quote fallback, and two-sided quote fallback. Quote source timestamps are retained per side; they are null when a daily bar supplies that side.",
            "",
            "For each eligible candidate baseline `b`, FinchX calculates with unrounded Decimal values:",
            "```text",
            "stockReturn_b = currentPrice / stockBaselinePrice_b - 1",
            "benchmarkReturn_b = benchmarkCurrent / benchmarkStart_b - 1",
            "deviation_b = stockReturn_b - benchmarkReturn_b",
            "deviation = max(deviation_b)",
            "```",
            "The selected `startDate`, stock/index baselines, returns, and `deviation` all come from the maximum-deviation candidate. Equal deviations use the earliest eligible candidate. `next_session` moves that candidate boundary forward by one trading session and rescans; for a complete 10-session request it has at most 9 observed statistic sessions, excluding the baseline. The 10/30 `windowDays` and upper thresholds remain unchanged. The final observed D10 candidate may use the actual D9 baseline and D10 price; no D11 zero-return candidate is added. Negative maxima and negative distances are preserved.",
            "",
            "The upper threshold is `1.00` for 10 sessions and `2.00` for 30. `upperTriggerPrice_b = stockBaselinePrice_b * (1 + upperThreshold + benchmarkReturn_b)` assumes `benchmarkCurrent` stays fixed. FinchX selects the minimum unrounded candidate price independently from the maximum-deviation candidate, then rounds the selected `upperTriggerPrice` up to CNY 0.01. The original unrounded value is returned as `upperTriggerPrice_original`, and the selected candidate basis is available in `result.metadata.windows[].upper_trigger_basis`. `remainingToUpper = upperTriggerPrice / currentPrice - 1`, using the rounded price. Negative values are preserved. The theoretical price is not a promise of execution or an event decision.",
            "",
            "A missing stock Kline date bracketed by stock bars remains an inferred gap for this calculation only; dates before the first available bar are short history, not inferred suspensions. After a gap, the stock and benchmark may use distinct baselines; missing index dates are never treated as stock halts. Partial windows and coverage are reported per row in `tradingSessions`, `availableTradingSessions`, `windowStatus`, `coverageStatus`, and `inferredHaltDates`; `availableTradingSessions` excludes the baseline and any unobserved future target. It counts observations, not the requested window length or the selected interval length. No raw OHLCV is changed.",
            "Ratio fields use fractions (`0.03` means 3%); prices are CNY per share and index values are points. `priceBasis` is `qfq_stock__raw_index` or `raw_stock__raw_index`, based on the actual stock Klines used. `ruleVersion` identifies the algorithm contract.",
            "",
            table(("Window", "Upper threshold"), [
                ("10 sessions", "`+1.00`"),
                ("30 sessions", "`+2.00`"),
            ]),
        ]
    return [
        "**计算口径与适用范围**",
        "FinchX 仅提供行情依据和计算结果，不判断是否构成正式异动，不返回触线、风险、交易或提醒结论。顶层 `effectiveAsOf` 与 `calculationMode` 是保留的兼容字段：`effectiveAsOf` 与 `asOf` 相同，`calculationMode` 为 `scenario_based`。",
        "适用个股为 SSE `60xxxx`、`68xxxx` 和 SZSE `00xxxx`、`30xxxx`；暂不支持 BSE 个股。不同板块使用对应的基准指数：",
        "",
        table(("代码范围", "板块", "基准指数"), [
            ("SSE `60xxxx`", "SSE 主板", "SSE A Share Index (`000002`)"),
            ("SSE `68xxxx`", "科创板", "SSE STAR 50 Index (`000688`)"),
            ("SZSE `00xxxx`", "SZSE 主板", "SZSE A Share Index (`399107`)"),
            ("SZSE `30xxxx`", "创业板", "ChiNext Composite Index (`399102`)"),
        ]),
        "",
        "每个请求窗口长度返回三条扁平记录，顺序为 `pre_open`、`current`、`next_session`。默认 `(10, 30)` 时 `windows` 有六条。`as_of` 表示观察基准交易日；非交易日沿用现有规则归一到此前交易日。`endDate` 是实际采用终值价格所属日，`targetDate` 决定该条记录的候选窗口边界，`startDate` 是最大偏离结果选中区间的统计开始日。",
        "",
        "观察日为 D10 时，`pre_open` 固定使用 D9 日线，不受 D10 价格影响。D10 盘中，`current` 和 `next_session` 使用通过校验的同日股票及指数快照。收盘后，每一侧优先采用可用的 D10 日线终值（股票前复权 K 线、指数未复权 K 线）；仅当某侧缺少 D10 日线时，才请求该侧同日快照作为终值。股票快照回退时，会用该快照的 `previousClose` 桥接 QFQ 股票历史；指数快照仍为未复权点位。盘后快照的来源时间可以早于 15:00，例如 14:59。程序校验证券标识、来源日期、正价格和时间戳不能晚于当前时间，但不会把快照称为已确认的日线收盘价。quote 回退警告只适用于 `current` 和 `next_session`。两侧终值来源分别记录在 `result.metadata.stock_terminal_source` 和 `benchmark_terminal_source`；来源为日线时行内来源时间戳为 null，来源为快照时保留来源时间戳。`next_session` 的终值同样截至 D10、目标日为 D11，与 `current` 共用同一份股票和指数终值，只把候选边界向后滚动一个交易日；不读取 D11 行情，也不构造 D11 K 线。历史 `as_of` 使用观察日的日线数据，日期参数无法复现过去某个盘中时刻。",
        "",
        "顶层 `priceBasis` 按实际股票 K 线口径返回：腾讯提供 QFQ 日线时为 `qfq_stock__raw_index`；QFQ 请求回退到文档所述未复权 `day` 数据时为 `raw_stock__raw_index`。使用 QFQ 日线时，股票快照回退会按其 `previousClose` 桥接历史；使用未复权日线时，历史和快照保留各自来源价格尺度，不做 QFQ 桥接。请求口径、实际口径、来源序列和回退 warning 可从 `result.metadata` 与 `result.warnings` 查询。指数日 K 线和快照均保持未复权点位。`price_inputs`、`stock_terminal_source` 和 `benchmark_terminal_source` 描述 `current` 与 `next_session` 的 D10 终值输入，`terminal_source_scope` 标明适用情景；`pre_open` 始终使用 D9 日线。终值来源值为 `same_day_daily_bar`、`same_day_quote` 或 `historical_daily_bar`。`price_inputs` 区分历史日线、盘中快照、盘后日线、单侧快照回退和双侧快照回退。快照来源时间按股票和指数分别保留；使用日线的一侧时间戳为 null。",
        "",
        "每个合格候选基准 `b` 使用未展示舍入的 Decimal 计算：",
        "```text",
        "stockReturn_b = currentPrice / stockBaselinePrice_b - 1",
        "benchmarkReturn_b = benchmarkCurrent / benchmarkStart_b - 1",
        "deviation_b = stockReturn_b - benchmarkReturn_b",
        "deviation = max(deviation_b)",
        "```",
        "最大偏离候选决定该行的 `startDate`、股票/指数基准、收益和 `deviation`；若偏离值相同，选最早的合格候选。`next_session` 将候选边界向后移一个交易日并重新扫描；完整 10 日请求最多包含 9 个已发生统计交易日，不含基准点。`windowDays` 与上阈值仍为 10/30。最后一个 D10 候选可以使用实际 D9 基准和 D10 价格；不会加入虚构的 D11 零收益候选。负偏离和负距离均保留。",
        "",
        "10 日上阈值为 `1.00`，30 日为 `2.00`。固定 `benchmarkCurrent` 时，`upperTriggerPrice_b = stockBaselinePrice_b * (1 + upperThreshold + benchmarkReturn_b)`。FinchX 先按未进位候选值独立于最大偏离候选选取最小理论价格，再将最终 `upperTriggerPrice` 向上进位到 0.01 CNY。原始未进位值通过 `upperTriggerPrice_original` 返回，选点依据可从 `result.metadata.windows[].upper_trigger_basis` 追溯。`remainingToUpper = upperTriggerPrice / currentPrice - 1` 使用进位后的价格。保留负值。理论价格不表示可成交价格，也不构成异动结论。",
        "",
        "被前后个股 K 线夹住的缺失日仍仅作为本计算的停牌推定；首条可用 K 线之前的缺失属于历史不足。缺口后股票与指数基线可以不同；指数缺失不会推定为个股停牌。每条记录用 `tradingSessions`、`availableTradingSessions`、`windowStatus`、`coverageStatus` 和 `inferredHaltDates` 报告覆盖情况。`availableTradingSessions` 统计场景候选窗口内已观测的统计交易日，不包括基准点或未发生的目标日；它不表示请求长度，也不等同于最终选中区间长度。原始 OHLCV 不会被修改。",
        "比例字段使用小数（`0.03` 即 3%）；股票价格单位为每股 CNY，指数单位为点。`priceBasis` 根据实际股票 K 线口径为 `qfq_stock__raw_index` 或 `raw_stock__raw_index`，`ruleVersion` 标识计算契约版本。",
        "",
        table(("窗口", "上阈值"), [
            ("10 个交易日", "`+1.00`"),
            ("30 个交易日", "`+2.00`"),
        ]),
    ]


def _trading_calendar_method_notes(*, language: str) -> list[str]:
    if language == "en":
        return [
            "**Calendar semantics and sources**",
            "Rows are complete, unique, and sorted by date. Dates are calendar labels, not instants; this method only answers whether each date is a trading day. It does not return session hours, breaks, open/close timestamps, or previous/next-session helpers.",
            "The primary source reads each intersecting month from the official SZSE calendar and must explicitly provide every natural date. If transport, parsing, or completeness validation fails, the configured fallback handles the entire requested range; results never mix sources. The optional `calendar` extra enables the offline `pandas_market_calendars` fallback, whose holiday schedule depends on its package version.",
            "Each StandardRecord uses `CN_A:YYYY-MM-DD` for its record and entity identity. Calendar dates have null `eventAt` and `asOf`; `capturedAt` and source metadata describe retrieval.",
        ]
    return [
        "**日历语义与数据来源**",
        "结果按日期升序排列，日期完整且不重复。日期是日历标签而不是时刻；此接口只回答某日是否为交易日，不提供交易时段、午休、开盘/收盘时间戳或前后交易日辅助方法。",
        "主要来源按范围读取深交所官方月度日历，并要求明确返回每个自然日。若传输、解析或完整性校验失败，配置的备用来源会处理完整范围；结果不会混用多个来源。安装可选 `calendar` extra 后可启用离线 `pandas_market_calendars` 备用来源，其节假日日程取决于软件包版本。",
        "每条 StandardRecord 使用 `CN_A:YYYY-MM-DD` 作为记录和实体标识。日历日期的 `eventAt` 和 `asOf` 为 null；`capturedAt` 与来源元数据描述数据获取信息。",
    ]


def _regulation_method_notes(key: str, *, language: str) -> list[str]:
    if key == "market.abnormal_records":
        if language == "en":
            return [
                "**Page and filter semantics**",
                "Each call requires one `dataset`: `abnormal_events`, `severe_events`, or `prediction_history`. It fetches exactly one 1-based upstream page (`page_size` maximum 200); it does not scan the full history automatically. Request later pages explicitly after checking `result.metadata.has_more`. `triggered` and `rise_only` are sent upstream through verified filters; `include_current` is applied locally and removes only rows explicitly marked as current. `page_complete` describes this fetched page; `collection_complete` is true only when the request covers the entire selected dataset result.",
                "Severe events default to current provider status. Unknown 0/1 flags stay null rather than becoming false.",
            ]
        return [
            "**分页与筛选口径**",
            "每次调用必须选择一个 `dataset`：`abnormal_events`、`severe_events` 或 `prediction_history`。每次只取从 1 开始的一个上游页（`page_size` 最大 200），不会自动扫描完整历史。请根据 `result.metadata.has_more` 显式请求后续页。经验证的 `triggered` 与 `rise_only` 会下推；`include_current` 在本地处理，仅排除明确标为当前交易日的记录。`page_complete` 表示本次上游页完整；仅覆盖所选数据集的全部结果时 `collection_complete` 才为 true。",
            "严重事件默认取来源当前状态。来源 0/1 标记无法识别时保留 null，不会当作 false。",
        ]
    if key in {"market.severe_predictions", "market.abnormal_counts"}:
        if language == "en":
            notes = [
                "**Pool and source-field semantics**",
                "The client requests pages of 200 and stops after at most 10 pages. `collection_complete` is false when source pages remain or pagination changes while fetching. `provider_count_raw` and `provider_open_raw` retain source fields without treating them as result totals or boolean state. Row percentages are normalized to ratio fractions (`95.69` becomes `0.9569`) while `providerValues` keeps source values.",
            ]
            if key == "market.severe_predictions":
                notes.append("Current- and next-session rows are returned together. Unknown provider states remain `horizon=\"unknown\"` with the source marker preserved in `providerValues`.")
                return notes
            notes.append("`/count.t` is the row's event count, not the pool total. The source meaning of `d` is not asserted; it remains in `providerValues`.")
            return notes
        notes = [
            "**榜单与来源字段口径**",
            "客户端每页请求 200 行，最多读取 10 页。来源报告还有后续页或分页期间数据变化时，`collection_complete` 为 false。`provider_count_raw` 与 `provider_open_raw` 保留来源字段，不会被解释为结果总数或布尔状态。百分数统一规范为比例小数（`95.69` 转为 `0.9569`），`providerValues` 保留来源原始值。",
        ]
        if key == "market.severe_predictions":
            notes.append("结果会同时返回当前交易日与下一交易日记录。来源状态未知时，`horizon` 保留为 `unknown`，原始标记保留在 `providerValues` 中。")
            return notes
        notes.append("`/count.t` 是单行异动次数，不是榜单总数。来源 `d` 的含义不作推断，并保留在 `providerValues` 中。")
        return notes
    if key == "market.regulation_watchlist":
        return [
            "**Security-kind coverage**" if language == "en" else "**证券类别覆盖**",
            ('The endpoint does not expose verified security kinds. FinchX returns every source row, leaves `instrumentId` null, and sets `result.metadata.classification_complete` to false. Original fields, including `MARKET`, remain in `providerValues`.' if language == "en" else '来源没有可核实的证券类别。FinchX 返回所有来源行，`instrumentId` 保持 null，且 `result.metadata.classification_complete` 为 false。包括 `MARKET` 在内的原始字段保留在 `providerValues` 中。'),
        ]
    return []


def _interface_block(key: str, method: Any, data_model: type[BaseModel], providers: tuple[str, ...], *, language: str, computed: bool = False) -> list[str]:
    example_code = _example_code(key, method, language=language)
    parameter_rows = _parameter_rows(key, method, language=language)
    if key == "market.deviation":
        method_notes = _deviation_method_notes(language=language)
    elif key in {"market.ohlcv", "market.quote_snapshot"}:
        method_notes = _index_quote_method_notes(key, language=language)
    elif key == "reference.trading_calendar":
        method_notes = _trading_calendar_method_notes(language=language)
    elif key.startswith("market.regulation_") or key in {"market.abnormal_records", "market.severe_predictions", "market.abnormal_counts"}:
        method_notes = _regulation_method_notes(key, language=language)
    else:
        method_notes = []
    if language == "en":
        parameter_table = table(("Parameter", "Type", "Required / mode", "Default", "Meaning"), parameter_rows) if parameter_rows else "None."
        data_source = "Computed locally from `market.ohlcv`, `market.quote_snapshot`, and `reference.trading_calendar`; no direct Provider." if computed else ", ".join(f"`{provider}`" for provider in providers) or "—"
        result_note = f"Returns a `FetchResult`. {_result_usage_note(key, data_model, language=language)} `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details."
        lines = [f"### `fx.{key}(...)`", "", "**What it provides**", summary_for(key, method, language=language), "", "**Data source**", data_source, *( ["", *method_notes] if method_notes else []), "", "**Example**", "", f"<!-- api-example: {key} -->", "```python", example_code, "```", "", "**Returned value and recommended use**", result_note, "", "**Parameters**", "", parameter_table]
    else:
        parameter_table = table(("参数", "类型", "必填 / 模式", "默认值", "含义"), parameter_rows) if parameter_rows else "无。"
        data_source = "由 `market.ohlcv`、`market.quote_snapshot` 和 `reference.trading_calendar` 在本地计算；无直接 Provider。" if computed else ", ".join(f"`{provider}`" for provider in providers) or "—"
        result_note = f"返回 `FetchResult`。{_result_usage_note(key, data_model, language=language)} `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。"
        lines = [f"### `fx.{key}(...)`", "", "**提供什么数据**", summary_for(key, method, language=language), "", "**数据源**", data_source, *( ["", *method_notes] if method_notes else []), "", "**示例**", "", f"<!-- api-example: {key} -->", "```python", example_code, "```", "", "**返回值与推荐用法**", result_note, "", "**参数**", "", parameter_table]
    lines += ["", *_output_sections(data_model, language=language, key=key), ""]
    return lines


def endpoint_block(endpoint: Any, *, language: str) -> list[str]:
    key = endpoint_key(endpoint)
    return _interface_block(key, _method_for(key), endpoint.dataset.data_type, providers_for(endpoint.dataset), language=language)


def computed_block(*, language: str) -> list[str]:
    return _interface_block("market.deviation", _CLIENT.market.deviation, COMPUTED_DEVIATION_DATASET.data_type, (), language=language, computed=True)


def _index_quote_method_notes(key: str, *, language: str) -> list[str]:
    if language == "en":
        notes = [
            "**Supported index identities**",
            "Use a full `market:exchange:index:code` identity, for example `cn_a:sse:index:000001` or `cn_a:szse:index:399001`. The current whitelist is SSE `000001`, `000002`, `000688` and SZSE `399001`, `399006`, `399102`, `399107`. On these generic methods, a bare `000001` resolves as the SZSE equity, not the SSE index.",
        ]
        if key == "market.ohlcv":
            notes += [
                "For an index, omit `adjustment` or pass `adjustment=None`; equities may use `qfq`, `hfq`, or no adjustment. OHLC fields are CNY per share for equities and index points for indices.",
                "Automatic `market.ohlcv` routing uses Tencent and does not automatically fall back to Sohu. Sohu remains available when explicitly selected for its supported indices; equity requests are rejected before network access. Tencent retries transient transport and HTTP 408/425/429/5xx failures up to four attempts within a 45-second request budget; HTTP 429 uses longer bounded exponential waits. Permanent HTTP, request, and response-schema failures are not retried.",
                "For an equity `qfq` request, Tencent's `qfqday` series is preferred. If that key is absent and the same response contains a valid `day` array, FinchX uses those unadjusted bars without another request. Each returned bar and its provenance keep `adjustment=\"none\"`; `FetchResult.metadata` records `requested_adjustment=\"qfq\"`, `actual_adjustment=\"none\"`, and `source_series=\"day\"`, and `FetchResult.warnings` explains that the values are not forward-adjusted. An empty or malformed `qfqday` does not trigger this fallback.",
            ]
        else:
            notes += [
                "Quote price fields use CNY per share for equities and index points for indices.",
            ]
        return notes
    notes = [
        "**受支持的指数标识**",
        "请使用 `market:exchange:index:code` 完整标识，例如 `cn_a:sse:index:000001` 或 `cn_a:szse:index:399001`。当前白名单为 SSE `000001`、`000002`、`000688` 及 SZSE `399001`、`399006`、`399102`、`399107`。在这两个通用接口中，裸代码 `000001` 会解析为深交所股票，而不是上证指数。",
    ]
    if key == "market.ohlcv":
        notes += [
            "指数请求请省略 `adjustment` 或传入 `adjustment=None`；股票可使用 `qfq`、`hfq` 或不复权。OHLC 字段对股票表示每股 CNY，对指数表示指数点数。",
            "`market.ohlcv` 自动路由使用腾讯，不会自动回退到搜狐。搜狐仍可通过显式指定 Provider 用于其受支持的指数；股票请求会在联网前拒绝。腾讯对可重试传输故障及 HTTP 408/425/429/5xx 错误最多尝试四次，并受单次请求 45 秒总预算限制；HTTP 429 使用更长的有界指数退避。永久 HTTP、请求及响应格式错误不会重试。",
            "股票请求 `qfq` 时优先使用腾讯的 `qfqday`。只有响应中没有该键、且同一响应的 `day` 是合法数组时，FinchX 才使用未复权日线，不会重复请求。返回行及 provenance 均保留 `adjustment=\"none\"`；`FetchResult.metadata` 记录 `requested_adjustment=\"qfq\"`、`actual_adjustment=\"none\"` 和 `source_series=\"day\"`，`FetchResult.warnings` 会说明这些价格不是前复权数据。若 `qfqday` 为空或格式错误，不会触发回退。",
        ]
    else:
        notes += [
            "行情价格字段对股票表示每股 CNY，对指数表示指数点数。",
        ]
    return notes



def _structured_operation_block(
    *,
    signature: str,
    what: str,
    source: str,
    example: str,
    parameter_rows: list[tuple[str, ...]],
    output_rows: list[tuple[str, ...]],
    language: str,
) -> list[str]:
    mark = chr(96)
    fence = mark * 3
    signature_text = f"{mark}{signature}{mark}"
    if "forum.replies" in signature:
        return_type = "FetchResult[tuple[ForumReply, ...]]"
    elif "get_documents" in signature:
        return_type = "FetchResult[tuple[document record, ...]]"
    elif "get_document" in signature:
        return_type = "FetchResult[document record]"
    elif "market_news.search" in signature:
        return_type = "FetchResult[tuple[NewsDocumentRef, ...]]"
    else:
        return_type = "tuple[NewsDocumentRef, ...]"
    if language == "en":
        if "forum.replies" in signature:
            result_note = "Returns `FetchResult[tuple[ForumReply, ...]]`. Use `replyContent`, `parentContent`, `username`, and `replyTime` to review matched replies; use `replyUrl` to open the source reply. `.to_dicts()` exports the rows, and `.warnings` reports partial scans or other recoverable issues."
        elif ".search(" in signature:
            result_note = "Returns typed document references in `.data`. Filter or rank by fields such as `title` and `publishedAt`; use `documentUrl` for a news article body and `originalDocumentUrl` for a disclosure notice or attachment. Pass a chosen reference to the matching detail method. Export with `.to_dicts()` and inspect `.warnings` for a capped scan."
        elif "get_document(ref)" in signature:
            result_note = "Returns one `StandardRecord` in `.data`. Read the document row payload from `result.data.data`, including fields such as `title`, `contentText`, and the document URLs; use `.to_dicts()` for a JSON-compatible row and inspect `.warnings` for fetch issues."
        else:
            result_note = "Returns a tuple of `StandardRecord` values in `.data`, in reference order. Read each record's document fields or export all rows with `.to_dicts()`; inspect `.warnings` for fetch issues."
    else:
        if "forum.replies" in signature:
            result_note = "返回 `FetchResult[tuple[ForumReply, ...]]`。用 `replyContent`、`parentContent`、`username` 和 `replyTime` 查看匹配回复；用 `replyUrl` 打开来源回复。`.to_dicts()` 可导出数据行，`.warnings` 可检查分页不完整等可恢复问题。"
        elif ".search(" in signature:
            result_note = "`.data` 返回带类型的文档引用。可按 `title`、`publishedAt` 筛选或排序；新闻文章正文链接使用 `documentUrl`，公告原文或附件使用 `originalDocumentUrl`。将目标引用传给对应详情方法；用 `.to_dicts()` 导出数据，并检查 `.warnings` 了解扫描是否触及上限。"
        elif "get_document(ref)" in signature:
            result_note = "`.data` 返回一条 `StandardRecord`。可从 `result.data.data` 读取文档行载荷中的 `title`、`contentText` 和文档 URL 等字段；用 `.to_dicts()` 导出 JSON 兼容行，并检查 `.warnings` 了解读取问题。"
        else:
            result_note = "`.data` 返回按引用顺序排列的 `StandardRecord` 元组。可读取每条记录的文档字段，或用 `.to_dicts()` 导出全部数据行；检查 `.warnings` 了解读取问题。"
    if language == "en":
        output_rows = [("return type", return_type, "Public return type.")] + output_rows
        return [
            f"### {signature_text}",
            "",
            "**What it provides**",
            what,
            "",
            "**Data source**",
            source,
            "",
            "**Example**",
            "",
            f"{fence}python",
            example,
            fence,
            "",
            "**Returned value and recommended use**",
            result_note + " Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.",
            "",
            "**Parameters**",
            "",
            table(("Parameter", "Type", "Required / mode", "Default", "Meaning"), parameter_rows) if parameter_rows else "None.",
            "",
            "**Output fields**",
            "",
            table(("Field", "Type", "Meaning"), output_rows),
            "",
        ]
    output_rows = [("返回类型", return_type, "公开返回类型。"), *output_rows]
    return [
        f"### {signature_text}",
        "",
        "**提供什么数据**",
        what,
        "",
        "**数据源**",
        source,
        "",
        "**示例**",
        "",
        f"{fence}python",
        example,
        fence,
        "",
        "**返回值与推荐用法**",
        result_note + " `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。",
        "",
        "**参数**",
        "",
        table(("参数", "类型", "必填 / 模式", "默认值", "含义"), parameter_rows) if parameter_rows else "无。",
        "",
        "**输出字段**",
        "",
        table(("字段", "类型", "含义"), output_rows),
        "",
    ]


def _document_operation_example(signature: str, *, language: str) -> str:
    if language == "en":
        special = {
            "ref": "Reference returned by the paired search.",
            "refs": "References returned by the paired search.",
            "user_names": "Exact usernames to retain from the activity feed.",
        }
    else:
        special = {
            "ref": "对应搜索返回的引用。",
            "refs": "对应搜索返回的引用列表。",
            "user_names": "从动态中精确保留这些用户名。",
        }
    comments = _EXAMPLE_COMMENTS[language] | special

    def method_for(full_name: str) -> Any:
        namespace, method_name = full_name.split(".", 1)
        return getattr(getattr(_CLIENT, namespace), method_name)

    def value_for(full_name: str, name: str, parameter: inspect.Parameter, *, source: str = "") -> str:
        if name == "ref":
            return "search_result.data[0]"
        if name == "refs":
            return "search_result.data"
        if name == "cookies":
            return "cookies"
        if name == "user_names":
            return '["洛飞超短笔记", "zarili"]'
        if name == "query" and full_name == "iwencai.select":
            return '"成交额排名前500，最新价高于5日均线，非ST"'
        return _example_value(full_name, name, parameter)

    def call_lines(
        variable: str,
        full_name: str,
        *,
        indent: str = "",
        reference_source: str = "",
    ) -> list[str]:
        method = method_for(full_name)
        lines = [f"{indent}{variable} = fx.{full_name}("]
        for name, parameter in inspect.signature(method).parameters.items():
            if name in {"provider", "use_cache"}:
                continue
            value = value_for(full_name, name, parameter, source=reference_source)
            comment = comments.get(name, parameter_description(name, language=language, key=full_name))
            lines.append(f"{indent}    {name}={value},  # {comment}")
        lines.append(f"{indent})")
        return lines

    if "forum.replies" in signature:
        lines = [
            "from finchx import FinchX", "", "fx = FinchX()",
            'cookies = "<Cookie header from your logged-in browser>"', "",
        ]
        lines += call_lines("result", "forum.replies")
        lines += ["", "print(result.data)", "print(result.to_dicts()[:1])", "print(result.warnings)"]
        return "\n".join(lines)

    full_name = signature.removeprefix("fx.").split("(", 1)[0]
    namespace, operation = full_name.split(".", 1)
    lines = ["from finchx import FinchX", "", "fx = FinchX()", ""]
    if operation == "search":
        lines += call_lines("result", full_name)
        lines += ["", "print(result.data)", "print(result.to_dicts()[:1])", "print(result.warnings)"]
        return "\n".join(lines)

    search_name = f"{namespace}.search"
    lines += call_lines("search_result", search_name)
    lines += ["", "if search_result.data:"]
    if operation == "get_document":
        lines += ["    ref = search_result.data[0]"]
        lines += ["    print(ref.original_document_url)" if namespace == "disclosure" else "    print(ref.document_url)"]
        lines += call_lines("result", full_name, indent="    ", reference_source="search_result")
    else:
        lines += ["    for ref in search_result.data:"]
        lines += ["        print(ref.original_document_url)" if namespace == "disclosure" else "        print(ref.document_url)"]
        lines += call_lines("result", full_name, indent="    ", reference_source="search_result")
    no_match = "No documents matched the example search." if language == "en" else "没有找到符合示例搜索条件的文档。"
    lines += ["    print(result.data)", "    print(result.to_dicts()[:1])", "    print(result.warnings)", "else:", f"    print({no_match!r})"]
    return "\n".join(lines)


def document_operations_block(*, language: str) -> list[str]:
    mark = chr(96)

    def inline(value: str) -> str:
        return f"{mark}{value}{mark}"

    document_record_en = "document record"
    common_single_output_en = [
        ("data", document_record_en, "The complete normalized document record."),
        ("provider_id", "str | None", "Provider identity carried by FetchResult."),
        ("dataset_id", "str", "Stable dataset identity carried by FetchResult."),
        ("to_dicts()", "list[dict[str, object]]", "Standard business-data export; one record is still returned as a one-item list."),
    ]
    common_batch_output_en = [
        ("data", "tuple[document record, ...]", "The complete normalized document records in input order."),
        ("provider_id", "str | None", "Provider identity when all records come from one provider."),
        ("dataset_id", "str", "Stable dataset identity carried by FetchResult."),
        ("to_dicts()", "list[dict[str, object]]", "Standard business-data export for every record."),
    ]
    document_record_zh = "标准文档记录"
    common_single_output_zh = [
        ("data", document_record_zh, "完整的标准化文档记录。"),
        ("provider_id", "str | None", "FetchResult 携带的数据源标识。"),
        ("dataset_id", "str", "FetchResult 携带的稳定数据集标识。"),
        ("to_dicts()", "list[dict[str, object]]", "标准业务数据导出；单条记录仍返回单元素列表。"),
    ]
    common_batch_output_zh = [
        ("data", "tuple[标准文档记录, ...]", "按输入顺序返回完整的标准化文档记录。"),
        ("provider_id", "str | None", "所有记录来自同一数据源时返回其标识。"),
        ("dataset_id", "str", "FetchResult 携带的稳定数据集标识。"),
        ("to_dicts()", "list[dict[str, object]]", "所有记录的标准业务数据导出。"),
    ]
    market_sources = (
        "aigupiao.market_news",
        "baidu.finscope.market_news",
    )

    if language == "en":
        specs = [
            {
                "signature": "fx.news.get_document(ref)",
                "what": f"Fetch one complete individual-stock news document after a reference is returned by {inline('fx.news.search(...)')}.",
                "source": inline("eastmoney.news"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.news.search("600519", page_size=2)\nif search_result.data:\n    detail_result = fx.news.get_document(search_result.data[0])\n    print(detail_result.to_dicts())\n    print(detail_result.data.data)',
                "parameter_rows": [
                    ("ref", "NewsDocumentRef", "Required", "—", "A reference returned by fx.news.search(...)."),
                ],
                "output_rows": common_single_output_en,
            },
            {
                "signature": "fx.news.get_documents(refs)",
                "what": "Fetch complete individual-stock news documents for a collection of references.",
                "source": inline("eastmoney.news"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.news.search("600519", page_size=2)\ndetails_result = fx.news.get_documents(search_result.data)\nprint(details_result.to_dicts())',
                "parameter_rows": [
                    ("refs", "Iterable[NewsDocumentRef]", "Required", "—", "References returned by fx.news.search(...)."),
                ],
                "output_rows": common_batch_output_en,
            },
            {
                "signature": "fx.disclosure.get_document(ref)",
                "what": f"Fetch one complete individual-stock disclosure after a reference is returned by {inline('fx.disclosure.search(...)')}.",
                "source": inline("eastmoney.disclosure"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.disclosure.search("600519", page_size=2)\nif search_result.data:\n    detail_result = fx.disclosure.get_document(search_result.data[0])\n    print(detail_result.to_dicts())\n    print(detail_result.data.data)',
                "parameter_rows": [
                    ("ref", "DisclosureDocumentRef", "Required", "—", "A reference returned by fx.disclosure.search(...)."),
                ],
                "output_rows": common_single_output_en,
            },
            {
                "signature": "fx.disclosure.get_documents(refs)",
                "what": "Fetch complete individual-stock disclosures for a collection of references.",
                "source": inline("eastmoney.disclosure"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.disclosure.search("600519", page_size=2)\ndetails_result = fx.disclosure.get_documents(search_result.data)\nprint(details_result.to_dicts())',
                "parameter_rows": [
                    ("refs", "Iterable[DisclosureDocumentRef]", "Required", "—", "References returned by fx.disclosure.search(...)."),
                ],
                "output_rows": common_batch_output_en,
            },
            {
                "signature": "fx.market_news.search(...)",
                "what": "Search deduplicated all-market news references across the configured market-news providers.",
                "source": ", ".join(inline(provider) for provider in market_sources),
                "example": "from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.market_news.search(page_size=20, max_results=50)\nfor ref in search_result.data:\n    print(ref.title, ref.source.provider_id)",
                "parameter_rows": [
                    ("page", "int", "Optional", "1", "One-based page number."),
                    ("page_size", "int", "Optional", "20", "Number of source rows requested per page."),
                    ("max_results", "int | None", "Optional", "None", "Maximum number of deduplicated references."),
                    ("since / until", "date | datetime | str | None", "Optional", "None", "Published-time bounds."),
                    ("sort", "str", "Optional", inline("published_desc"), "Published-time ordering."),
                ],
                "output_rows": [
                    ("data", "tuple[NewsDocumentRef, ...]", "Deduplicated references in the FetchResult."),
                    ("provider", "str | None", "Provider identity when all returned references come from one provider; otherwise None."),
                    ("captured_at", "datetime", "Latest captured_at among returned references, or the current timezone-aware time for an empty result."),
                    ("source_occurrences", "tuple", "All retained source occurrences for a deduplicated event."),
                    ("provenance", "object", "Source references and capture metadata for the reference."),
                ],
            },
            {
                "signature": "fx.market_news.get_document(ref)",
                "what": f"Fetch one complete all-market news document after a reference is returned by {inline('fx.market_news.search(...)')}.",
                "source": ", ".join(inline(provider) for provider in market_sources),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.market_news.search(max_results=10)\nif search_result.data:\n    detail_result = fx.market_news.get_document(search_result.data[0])\n    print(detail_result.to_dicts())\n    print(detail_result.data.data)',
                "parameter_rows": [
                    ("ref", "NewsDocumentRef", "Required", "—", "A reference returned by fx.market_news.search(...)."),
                ],
                "output_rows": common_single_output_en,
            },
            {
                "signature": "fx.market_news.get_documents(refs)",
                "what": "Fetch complete all-market news documents for a collection of references.",
                "source": ", ".join(inline(provider) for provider in market_sources),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.market_news.search(max_results=10)\ndetails_result = fx.market_news.get_documents(search_result.data)\nprint(details_result.to_dicts())',
                "parameter_rows": [
                    ("refs", "Iterable[NewsDocumentRef]", "Required", "—", "References returned by fx.market_news.search(...)."),
                ],
                "output_rows": common_batch_output_en,
            },
            {
                "signature": "fx.forum.replies(cookies=..., user_names=[...])",
                "what": "Fetch only activity-feed replies with a source locator, separate reply text, and complete nested quoted context. Activities without that context are excluded.",
                "source": inline("taoguba.forum"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nresult = fx.forum.replies(\n    cookies="<Cookie header from your logged-in browser>",\n    user_names=["洛飞超短笔记", "zarili"],\n    max_results=50,\n)\nfor reply in result.data:\n    print(reply.reply_content, reply.parent_content)\nprint(result.to_dicts())',
                "parameter_rows": [
                    ("cookies", "str | Mapping[str, str]", "Required", "—", "Caller-provided Cookie header used only for the fixed activity-feed GET."),
                    ("user_names", "Sequence[str] | None", "Optional", "None", "Exact usernames to retain from the current activity page; it does not search other users."),
                    ("max_results", "int | None", "Optional", "None", "Maximum number of structurally qualified replies."),
                    ("since / until", "date | datetime | str | None", "Optional", "None", "Reply-time bounds."),
                ],
                "output_rows": [
                    ("data", "tuple[ForumReply, ...]", "Qualified replies in a FinchX FetchResult."),
                    ("provider", "str", "Taoguba forum provider identity."),
                    ("dataset_id", "str", "forum.replies dataset identity at schema 1.0."),
                    ("captured_at", "datetime", "Latest aware capture time, or the provider clock for an empty result."),
                    ("provenance", "tuple[Source, ...]", "Direct source records; cookies are never included."),
                    ("to_dicts()", "list[dict[str, object]]", "CamelCase business fields including replyContent and parentContent."),
                ],
            },
        ]
    else:
        specs = [
            {
                "signature": "fx.news.get_document(ref)",
                "what": f"根据 {inline('fx.news.search(...)')} 返回的引用，读取一条完整的个股新闻详情。",
                "source": inline("eastmoney.news"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.news.search("600519", page_size=2)\nif search_result.data:\n    detail_result = fx.news.get_document(search_result.data[0])\n    print(detail_result.to_dicts())\n    print(detail_result.data.data)',
                "parameter_rows": [
                    ("ref", "NewsDocumentRef", "必填", "—", "fx.news.search(...) 返回的新闻引用。"),
                ],
                "output_rows": common_single_output_zh,
            },
            {
                "signature": "fx.news.get_documents(refs)",
                "what": "根据一组新闻引用，批量读取个股新闻详情。",
                "source": inline("eastmoney.news"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.news.search("600519", page_size=2)\ndetails_result = fx.news.get_documents(search_result.data)\nprint(details_result.to_dicts())',
                "parameter_rows": [
                    ("refs", "Iterable[NewsDocumentRef]", "必填", "—", "fx.news.search(...) 返回的新闻引用。"),
                ],
                "output_rows": common_batch_output_zh,
            },
            {
                "signature": "fx.disclosure.get_document(ref)",
                "what": f"根据 {inline('fx.disclosure.search(...)')} 返回的引用，读取一条完整的个股公告详情。",
                "source": inline("eastmoney.disclosure"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.disclosure.search("600519", page_size=2)\nif search_result.data:\n    detail_result = fx.disclosure.get_document(search_result.data[0])\n    print(detail_result.to_dicts())\n    print(detail_result.data.data)',
                "parameter_rows": [
                    ("ref", "DisclosureDocumentRef", "必填", "—", "fx.disclosure.search(...) 返回的公告引用。"),
                ],
                "output_rows": common_single_output_zh,
            },
            {
                "signature": "fx.disclosure.get_documents(refs)",
                "what": "根据一组公告引用，批量读取个股公告详情。",
                "source": inline("eastmoney.disclosure"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.disclosure.search("600519", page_size=2)\ndetails_result = fx.disclosure.get_documents(search_result.data)\nprint(details_result.to_dicts())',
                "parameter_rows": [
                    ("refs", "Iterable[DisclosureDocumentRef]", "必填", "—", "fx.disclosure.search(...) 返回的公告引用。"),
                ],
                "output_rows": common_batch_output_zh,
            },
            {
                "signature": "fx.market_news.search(...)",
                "what": "聚合并去重全市场新闻，返回可继续读取详情的新闻引用。",
                "source": "、".join(inline(provider) for provider in market_sources),
                "example": "from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.market_news.search(page_size=20, max_results=50)\nfor ref in search_result.data:\n    print(ref.title, ref.source.provider_id)",
                "parameter_rows": [
                    ("page", "int", "可选", "1", "从 1 开始的页码。"),
                    ("page_size", "int", "可选", "20", "每页向数据源请求的行数。"),
                    ("max_results", "int | None", "可选", "None", "最多返回的去重引用数量。"),
                    ("since / until", "date | datetime | str | None", "可选", "None", "发布时间范围。"),
                    ("sort", "str", "可选", inline("published_desc"), "发布时间排序方式。"),
                ],
                "output_rows": [
                    ("data", "tuple[NewsDocumentRef, ...]", "FetchResult 中的去重新闻引用。"),
                    ("provider", "str | None", "所有返回引用来自同一 Provider 时返回其标识，否则为 None。"),
                    ("captured_at", "datetime", "返回引用中最大的 captured_at；空结果使用带时区的当前时间。"),
                    ("source_occurrences", "tuple", "去重事件保留的全部数据源出现记录。"),
                    ("provenance", "object", "引用对应的数据源引用和采集元数据。"),
                ],
            },
            {
                "signature": "fx.market_news.get_document(ref)",
                "what": f"根据 {inline('fx.market_news.search(...)')} 返回的引用，读取一条完整的全市场新闻详情。",
                "source": "、".join(inline(provider) for provider in market_sources),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.market_news.search(max_results=10)\nif search_result.data:\n    detail_result = fx.market_news.get_document(search_result.data[0])\n    print(detail_result.to_dicts())\n    print(detail_result.data.data)',
                "parameter_rows": [
                    ("ref", "NewsDocumentRef", "必填", "—", "fx.market_news.search(...) 返回的新闻引用。"),
                ],
                "output_rows": common_single_output_zh,
            },
            {
                "signature": "fx.market_news.get_documents(refs)",
                "what": "根据一组新闻引用，批量读取全市场新闻详情。",
                "source": "、".join(inline(provider) for provider in market_sources),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nsearch_result = fx.market_news.search(max_results=10)\ndetails_result = fx.market_news.get_documents(search_result.data)\nprint(details_result.to_dicts())',
                "parameter_rows": [
                    ("refs", "Iterable[NewsDocumentRef]", "必填", "—", "fx.market_news.search(...) 返回的新闻引用。"),
                ],
                "output_rows": common_batch_output_zh,
            },
            {
                "signature": "fx.forum.replies(cookies=..., user_names=[...])",
                "what": "只返回当前账号动态中同时拥有原始定位链接、独立回复正文和完整嵌套引用上下文的记录；其他动态会被排除。",
                "source": inline("taoguba.forum"),
                "example": 'from finchx import FinchX\n\nfx = FinchX()\nresult = fx.forum.replies(\n    cookies="<登录浏览器中的 Cookie header>",\n    user_names=["洛飞超短笔记", "zarili"],\n    max_results=50,\n)\nfor reply in result.data:\n    print(reply.reply_content, reply.parent_content)\nprint(result.to_dicts())',
                "parameter_rows": [
                    ("cookies", "str | Mapping[str, str]", "必填", "—", "调用者提供的 Cookie header，仅用于固定动态页 GET。"),
                    ("user_names", "Sequence[str] | None", "可选", "None", "只精确过滤当前动态页中可见的用户名，不搜索其他用户。"),
                    ("max_results", "int | None", "可选", "None", "最多返回的完整上下文回复数量。"),
                    ("since / until", "date | datetime | str | None", "可选", "None", "回复时间范围。"),
                ],
                "output_rows": [
                    ("data", "tuple[ForumReply, ...]", "统一 FinchX FetchResult 中的完整上下文回复。"),
                    ("provider", "str", "淘股吧论坛 Provider 标识。"),
                    ("dataset_id", "str", "forum.replies@1.0 数据集标识。"),
                    ("captured_at", "datetime", "最大 aware 采集时间；空结果使用 Provider clock。"),
                    ("provenance", "tuple[Source, ...]", "直接来源；不会包含 Cookie。"),
                    ("to_dicts()", "list[dict[str, object]]", "导出 replyContent、parentContent 等 camelCase 字段。"),
                ],
            },
        ]

    lines: list[str] = []
    for spec in specs:
        spec = {**spec, "example": _document_operation_example(spec["signature"], language=language)}
        lines.extend(_structured_operation_block(language=language, **spec))
    return lines


def category_index(*, language: str) -> list[str]:
    endpoint_by_key = {endpoint_key(endpoint): endpoint for endpoint in CLIENT_ENDPOINTS}
    if language == "en":
        lines = ["## 3. Interface overview", ""]
        headers = ("Interface", "Purpose", "Provider")
    else:
        lines = ["## 3. 接口总览", ""]
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
        if spec.title_en == "News and disclosures":
            if language == "en":
                rows.extend([
                    ("`fx.news.get_document(ref)` / `fx.news.get_documents(refs)`", "Fetch individual-stock news details from search references.", "`eastmoney.news`"),
                    ("`fx.disclosure.get_document(ref)` / `fx.disclosure.get_documents(refs)`", "Fetch individual-stock disclosure details from search references.", "`eastmoney.disclosure`"),
                    ("`fx.market_news.search(...)` / `fx.market_news.get_document(s)(...)`", "Search all-market news and fetch its complete document details.", "`aigupiao.market_news`, `baidu.finscope.market_news`"),
                    ("`fx.forum.replies(...)`", "Read qualified replies from the authenticated Taoguba activity feed.", "`taoguba.forum`"),
                ])
            else:
                rows.extend([
                    ("`fx.news.get_document(ref)` / `fx.news.get_documents(refs)`", "根据搜索引用读取个股新闻详情。", "`eastmoney.news`"),
                    ("`fx.disclosure.get_document(ref)` / `fx.disclosure.get_documents(refs)`", "根据搜索引用读取个股公告详情。", "`eastmoney.disclosure`"),
                    ("`fx.market_news.search(...)` / `fx.market_news.get_document(s)(...)`", "搜索全市场新闻并读取完整详情。", "`aigupiao.market_news`、`baidu.finscope.market_news`"),
                    ("`fx.forum.replies(...)`", "读取登录态淘股吧动态中符合条件的回复。", "`taoguba.forum`"),
                ])
        title = spec.title_en if language == "en" else spec.title_zh
        lines += [f"### {title}", "", table(headers, rows), ""]
    return lines


_QUICK_START_CODE = """from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # Six-digit A-share code; endpoint resolves its market.
)

print(result.data)
rows = result.to_dicts()
print(rows[:1])
print(result.warnings)
"""

_QUICK_START_CODE_ZH = """from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)

print(result.data)
rows = result.to_dicts()
print(rows[:1])
print(result.warnings)
"""


def _intro(*, language: str, provider_count: int, computed_count: int, capability_count: int) -> list[str]:
    if language == "en":
        return [
            "# FinchX Data API Reference", "", "English | [简体中文](DATA_API_REFERENCE.zh-CN.md)", "",
            f"This document covers {provider_count} data interfaces and {computed_count} computed capability, for {capability_count} core capabilities.", "",
            "## 1. What FinchX is / Architecture overview", "",
            "FinchX is a small client for normalized Chinese market data. You call one public Client; FinchX validates the request, fetches a source-backed dataset, and returns one consistent result shape.", "",
            table(("Layer", "What it does"), [("Client", "`FinchX()` is the user-facing entry point."), ("Dataset", "Defines the stable request and business-data schema."), ("Provider", "Implements one real external data source."), ("Collector", "Routes the request to a Provider and builds `FetchResult`."), ("FetchResult", "Shows business data first; audit fields remain on `provider`, `provenance`, `attempts`, `warnings`, and `cache_hit`.")]), "",
            "## 2. Quick start", "", "```python", _QUICK_START_CODE, "```", "",
            "`result.data` retains the native typed payload. `to_dicts()` is FinchX's standard export method: it always returns a list of business-data dictionaries, including for a single record, and preserves nested lists and objects. Inspect `result.warnings` for partial or recoverable issues. Each interface section below includes a complete example call.", "",
        ]
    return [
        "# FinchX 数据 API 参考", "", "[English](DATA_API_REFERENCE.md) | 简体中文", "",
        f"本文档覆盖 {provider_count} 个数据接口 + {computed_count} 个计算能力 = {capability_count} 个核心能力。", "",
        "## 1. FinchX 是什么 / 架构概览", "",
        "FinchX 是一个面向中国A股市场数据的统一客户端。用户调用一个公开 Client；FinchX 校验请求、访问数据源，并返回统一格式的结果。", "",
        table(("层次", "作用"), [("Client", "用户调用入口：`FinchX()`。"), ("Dataset", "定义稳定的请求模型和业务数据结构。"), ("Provider", "实现一个真实的外部数据源。"), ("Collector", "把请求路由到 Provider，并生成 `FetchResult`。"), ("FetchResult", "默认先展示业务数据；`provider`、`provenance`、`attempts`、`warnings`、`cache_hit` 保留为审计属性。")]), "",
        "## 2. 快速开始", "", "```python", _QUICK_START_CODE_ZH, "```", "",
        "`result.data` 保留原生类型载荷。`to_dicts()` 是 FinchX 的标准导出方式：始终返回业务数据字典列表，单条结果也保持这一形式，并完整保留嵌套列表和嵌套对象。检查 `result.warnings` 可了解部分数据或可恢复问题。下方每个接口章节都提供完整示例调用。", "",
    ]


def _shared_notes(*, language: str) -> list[str]:
    if language == "en":
        return [
            "## 5. Shared notes", "", "### Security input rules", "",
            "- Plain codes are resolved using the endpoint context: stock endpoints treat `000001` as a SZSE equity, while index endpoints treat `000001` as the SSE index.", "- FinchX validates supported code prefixes and market rules internally; callers provide code strings.", "",
            "### Date inputs", "", "Public date parameters accept `datetime.date` values or unambiguous strings in `YYYY-MM-DD`, `YYYYMMDD`, and `YYYY/MM/DD` forms. Invalid calendar dates and ambiguous forms such as `09/01/2026` are rejected. Date-only fields do not accept `datetime` values; news, disclosure, all-market news, and forum time bounds also accept timezone-aware `datetime` values.", "",
            "### Warnings", "", "`result.warnings` contains recoverable quality or compatibility issues, such as a skipped News row with schema drift.", "",
            "### Live paginated stock lists", "", "Tencent's full-market `market.quote`, its instrument listing used by exact `instrument` Dataset lookups, `market.ranking`, and the five EastMoney pool methods read live pages. If a stock repeats on a later page, FinchX keeps the first row and skips the repeated row; `.warnings` and `.metadata` then report partial coverage. Pagination uses source-row counts, so ranking `limit` is a source-row budget and skipped repeats never cause extra pages to refill unique rows. Multiple live pages do not form a consistent point-in-time snapshot, even when no repeat is observed; ranking `position` retains the original source row number and may have gaps.", "",
            "### Date-bounded searches", "", "For `news.search`, `disclosure.search`, `market_news.search`, and `forum.replies`, `since` and `until` are inclusive time filters. Start at `page=1`; the Client scans source pages within a safety bound, stops after reaching an older page for descending results or exhausting the source, and honors `max_results`. If the safety bound is reached before the date boundary or source end, `result.warnings` reports that results may be incomplete. Set a practical `max_results` cap and inspect warnings when completeness matters.", "",
            "### Document URLs", "", "For news references, `sourceUrl` identifies the source search/list page, while `documentUrl` points to the article body. Use `ref.document_url` when you need the article URL; code that treated `ref.source_url` as the article URL should migrate to `ref.document_url`. For disclosure references, `sourceUrl` is the source query page and `originalDocumentUrl` remains the notice or attachment URL. Disclosure `sourceRecordedAt` is retained under `provenance.adjustments` as EastMoney's internal record time; it is not the notice publication time. Use `publishedAt` for the displayed notice time.", "",
            "### FetchResult usage", "", "Every method returns `FetchResult`. Record-backed endpoints place tuples of normalized `StandardRecord` values in `.data`; a single document-detail call returns one `StandardRecord`, document searches return typed reference tuples, and computed deviation returns `DeviationData`. `Dataset.data_type` describes the row payload schema, while `FetchResult.data` carries the runtime record or reference shape. Export business dictionaries with `result.to_dicts()` and inspect `result.warnings` for partial results. Retrieval details remain available through `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.",
        ]
    return [
        "## 5. 通用说明", "", "### 证券输入规则", "",
        "- 裸代码会按接口语义解析：股票接口把 `000001` 解释为深市股票，指数接口把 `000001` 解释为上证指数。", "- 支持的代码前缀和市场规则由 FinchX 在内部校验，调用方只需传入代码字符串。", "",
        "### 日期输入", "", "公开日期参数接受 `datetime.date`，或 `YYYY-MM-DD`、`YYYYMMDD`、`YYYY/MM/DD` 三种无歧义字符串。非法日期和 `09/01/2026` 这类歧义格式会被拒绝。仅日期字段不接受 `datetime`；新闻、公告、全市场新闻和论坛的时间范围也接受带时区 `datetime`。", "",
        "### Warnings", "", "`result.warnings` 用于记录可恢复的数据质量或兼容性问题，例如跳过存在 schema drift 的单条 News 记录。", "",
        "### 实时分页股票列表", "", "Tencent 全市场 `market.quote`、用于 `instrument` Dataset 精确查询的证券列表、`market.ranking` 以及 EastMoney 五个股票池接口都会读取实时分页数据。如果股票在后续页重复，FinchX 保留首次记录并跳过重复行；此时 `.warnings` 和 `.metadata` 会标明部分覆盖。分页按来源行数推进，因此 ranking 的 `limit` 是来源行预算，跳过重复行不会触发额外请求来补足唯一记录。多页实时数据不构成同一时点快照，即使没有观察到重复也不能据此确认快照一致；ranking 的 `position` 保留来源行号，可能出现名次缺口。", "",
        "### 按日期范围搜索", "", "`news.search`、`disclosure.search`、`market_news.search` 和 `forum.replies` 的 `since` 与 `until` 是包含边界的时间筛选。请从 `page=1` 开始；Client 会在安全上限内跨页扫描，在降序结果到达早于起始日期的整页或数据源耗尽时停止，并遵守 `max_results`。如果触及安全上限时仍未到达日期边界或源末尾，`result.warnings` 会说明结果可能不完整。需要控制返回量时设置合适的 `max_results`，并在要求完整性时检查 warnings。", "",
        "### 文档 URL", "", "新闻引用中的 `sourceUrl` 指向数据源的搜索/列表页，`documentUrl` 指向文章正文。需要文章链接时使用 `ref.document_url`；如果旧代码把 `ref.source_url` 当正文链接，应迁移到 `ref.document_url`。公告引用的 `sourceUrl` 指向来源查询页，`originalDocumentUrl` 仍指向公告或附件原文。公告 `sourceRecordedAt` 保存在 `provenance.adjustments` 中，是东方财富内部记录时间，不是公告发布时间；展示公告时间请使用 `publishedAt`。", "",
        "### FetchResult 用法", "", "所有方法都返回 `FetchResult`。记录型接口的 `.data` 为标准化 `StandardRecord` 元组；单条文档详情返回一个 `StandardRecord`，文档搜索返回带类型的引用元组，计算型偏离值返回 `DeviationData`。`Dataset.data_type` 描述每行的业务载荷 schema，`FetchResult.data` 则承载实际运行时记录或引用结构。用 `result.to_dicts()` 导出业务字典，并检查 `result.warnings` 了解部分数据情况。采集信息可从 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 读取。",
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
            if key == "disclosure.search":
                lines += document_operations_block(language=language)
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
