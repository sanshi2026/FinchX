"""Generate the bilingual FinchX v1 API reference from public runtime metadata.

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

from pydantic import AnyUrl, BaseModel

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
    "market.ohlcv": "获取个股日线 OHLCV 数据。",
    "market.orderbook": "获取个股盘口数据。",
    "market.quote": "获取全市场行情快照。",
    "market.quote_snapshot": "获取单个标的的行情快照。",
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
    "market.deviation": "计算经过审计的基于收盘价的偏离值。",
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
    CategorySpec("Regulatory deviation", "监管类：偏离值", _COMPUTED_CAPABILITY_KEYS),
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
        "Output adjustment label: `none`, `qfq`, `hfq`, or `not_applicable`.",
        "输出复权标记：`none`、`qfq`、`hfq` 或 `not_applicable`。",
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
        "as_of": "Optional completed-session date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings.", "window_convention": "Deviation window interpretation.",
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
        "as_of": "可选的已完成交易时段日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。", "window_convention": "偏离窗口解释方式。",
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
        "topic_url": "同花顺 T-code 主题分享 URL；仅允许两个已确认的社区主题路径。",
    }
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
        "market.deviation": "Calculate close-based relative returns for one supported A-share stock against its board benchmark over 10- or 30-session windows.",
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


def _result_usage_note(key: str, model: type[BaseModel], *, language: str) -> str:
    aliases = [field.alias or name for name, field in model.model_fields.items()]
    if key == "market.daily_replay":
        important = [name for name in ("requestedDate", "tradeDate", "themes") if name in aliases]
    else:
        important = aliases[:4]
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
    else:
        shape_en = "`.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload."
        shape_zh = "`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。"
    if language == "en":
        if key == "reference.trading_calendar":
            action = "Each natural date in the inclusive range appears once, and the interface always uses the unified A-share calendar."
        elif key == "market.daily_replay":
            action = "Use `tradeDate` to identify the returned session, then inspect `themes` for the close review."
        elif key == "market.deviation":
            action = "Iterate `windows` to compare each requested trading window, and retain `effectiveAsOf` with the result."
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
        return f"{shape_en} The Dataset row schema `{model.__name__}` has business fields such as {fields}. {action} Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results."
    if key == "reference.trading_calendar":
        action = "闭区间内每个自然日各返回一行，接口固定使用统一的 A 股交易日历。"
    elif key == "market.daily_replay":
        action = "用 `tradeDate` 确认返回的交易日，再检查 `themes` 完成盘后复盘。"
    elif key == "market.deviation":
        action = "遍历 `windows` 比较各个交易窗口，并将 `effectiveAsOf` 与结果一起保留。"
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
    return f"{shape_zh} Dataset 行模式 `{model.__name__}` 的业务字段包括 {fields} 等。{action} 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。"


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
    "window_convention": '"max_deviation_scan"',
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
        "windows": "Compare 10- and 30-session windows.", "as_of": "Last completed session to include.",
        "window_convention": "Scan the documented deviation convention.",
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
        "as_of": "纳入计算的最后一个已完成交易日。", "window_convention": "使用文档说明的偏离窗口算法。",
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
    example_parameters = {
        name: parameter
        for name, parameter in parameters.items()
        if name not in {"provider", "use_cache"}
        and not (key == "market.quote" and name == "universe")
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
            else:
                comment = comments.get(name, parameter_description(name, language=language, key=key))
            value = values[name]
            lines.append(f"    {name}={value},  # {comment}")
        lines.append(")")
    lines += ["", "print(result.data)  # Native typed data or records.", "rows = result.to_dicts()  # JSON-compatible business rows.", "print(rows[:1])", "print(result.warnings)  # Check for partial or recoverable issues."]
    if language == "zh":
        lines[-5:] = ["print(result.data)  # 原生类型数据或记录。", "rows = result.to_dicts()  # JSON 兼容的业务数据行。", "print(rows[:1])", "print(result.warnings)  # 检查部分数据和可恢复问题。"]
    return "\n".join(lines)


def _deviation_method_notes(*, language: str) -> list[str]:
    if language == "en":
        return [
            "**Scope and calculation**",
            "This is a deterministic close-based computation, not an exchange announcement, an intraday estimate, a market-wide scan, or an application-specific trigger state.",
            "Supported equities are SSE `60xxxx` and `68xxxx`, and SZSE `00xxxx` and `30xxxx`; BSE equities are not supported. Each board uses its corresponding benchmark:",
            "",
            table(("Equity code", "Board", "Benchmark index"), [
                ("SSE `60xxxx`", "SSE main board", "SSE A Share Index (`000002`)"),
                ("SSE `68xxxx`", "STAR", "SSE STAR 50 Index (`000688`)"),
                ("SZSE `00xxxx`", "SZSE main board", "SZSE A Share Index (`399107`)"),
                ("SZSE `30xxxx`", "ChiNext", "ChiNext Composite Index (`399102`)"),
            ]),
            "",
            "Stock returns use QFQ equity closes; benchmark returns use unadjusted index points. Trading sessions come from the A-share calendar. For each window, FinchX calculates:",
            "",
            "```text",
            "stock_return = current_stock_close / baseline_stock_close - 1",
            "benchmark_return = current_index_close / baseline_index_close - 1",
            "deviation = stock_return - benchmark_return",
            "```",
            "",
            "The baseline is the close immediately before the selected window starts. Values are ratio fractions (`0.03` means 3%). `max_deviation_scan` selects the eligible start with the largest stock-minus-benchmark return; `strict_exchange_window` uses the exchange-shaped start. Unsupported codes or insufficient aligned history raise an error instead of returning zero.",
            "The result reports `calculationMode = \"official_close\"`, `priceBasis = \"qfq_stock__raw_index\"`, and the frozen rule-set identifier in `ruleVersion`.",
            "",
            table(("Window", "Upper threshold", "Lower threshold"), [
                ("10 sessions", "`+1.00`", "`-0.50`"),
                ("30 sessions", "`+2.00`", "`-0.70`"),
            ]),
        ]
    return [
        "**计算口径与适用范围**",
        "这是基于收盘价的确定性计算，不是交易所公告、盘中估算、全市场扫描或特定应用的触发状态。",
        "适用个股为 SSE `60xxxx`、`68xxxx` 和 SZSE `00xxxx`、`30xxxx`；暂不支持 BSE 个股。不同板块使用对应的基准指数：",
        "",
        table(("代码范围", "板块", "基准指数"), [
            ("SSE `60xxxx`", "SSE 主板", "SSE A Share Index (`000002`)"),
            ("SSE `68xxxx`", "科创板", "SSE STAR 50 Index (`000688`)"),
            ("SZSE `00xxxx`", "SZSE 主板", "SZSE A Share Index (`399107`)"),
            ("SZSE `30xxxx`", "创业板", "ChiNext Composite Index (`399102`)"),
        ]),
        "",
        "股票收益使用前复权日 K 收盘价，基准收益使用未复权指数点位；交易时段取自 A 股交易日历。每个窗口按以下方式计算：",
        "",
        "```text",
        "stock_return = 当前股票收盘价 / 窗口基准股票收盘价 - 1",
        "benchmark_return = 当前指数点位 / 窗口基准指数点位 - 1",
        "deviation = stock_return - benchmark_return",
        "```",
        "",
        "基准值为所选窗口起点前一交易日的收盘价或指数点位。比例以小数表示（`0.03` 即 3%）。默认的 `max_deviation_scan` 会选择股票与基准收益差最大的合资格起点；`strict_exchange_window` 使用按交易所窗口形状确定的起点。不支持的代码或不足的对齐历史数据会报错，不会返回零值。",
        "结果中的 `calculationMode` 为 `official_close`，`priceBasis` 为 `qfq_stock__raw_index`，`ruleVersion` 标识采用的冻结规则集。",
        "",
        table(("窗口", "上阈值", "下阈值"), [
            ("10 个交易日", "`+1.00`", "`-0.50`"),
            ("30 个交易日", "`+2.00`", "`-0.70`"),
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


def _interface_block(key: str, method: Any, data_model: type[BaseModel], providers: tuple[str, ...], *, language: str, computed: bool = False) -> list[str]:
    example_code = _example_code(key, method, language=language)
    parameter_rows = _parameter_rows(key, method, language=language)
    if key == "market.deviation":
        method_notes = _deviation_method_notes(language=language)
    elif key == "reference.trading_calendar":
        method_notes = _trading_calendar_method_notes(language=language)
    else:
        method_notes = []
    if language == "en":
        parameter_table = table(("Parameter", "Type", "Required / mode", "Default", "Meaning"), parameter_rows) if parameter_rows else "None."
        data_source = "Computed locally from `market.ohlcv` and `reference.trading_calendar`; no direct Provider." if computed else ", ".join(f"`{provider}`" for provider in providers) or "—"
        result_note = f"Returns a `FetchResult`. {_result_usage_note(key, data_model, language=language)} `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details."
        lines = [f"### `fx.{key}(...)`", "", "**What it provides**", summary_for(key, method, language=language), "", "**Data source**", data_source, *( ["", *method_notes] if method_notes else []), "", "**Example**", "", f"<!-- api-example: {key} -->", "```python", example_code, "```", "", "**Returned value and recommended use**", result_note, "", "**Parameters**", "", parameter_table]
    else:
        parameter_table = table(("参数", "类型", "必填 / 模式", "默认值", "含义"), parameter_rows) if parameter_rows else "无。"
        data_source = "由 `market.ohlcv` 和 `reference.trading_calendar` 在本地计算；无直接 Provider。" if computed else ", ".join(f"`{provider}`" for provider in providers) or "—"
        result_note = f"返回 `FetchResult`。{_result_usage_note(key, data_model, language=language)} `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。"
        lines = [f"### `fx.{key}(...)`", "", "**提供什么数据**", summary_for(key, method, language=language), "", "**数据源**", data_source, *( ["", *method_notes] if method_notes else []), "", "**示例**", "", f"<!-- api-example: {key} -->", "```python", example_code, "```", "", "**返回值与推荐用法**", result_note, "", "**参数**", "", parameter_table]
    lines += ["", *_output_sections(data_model, language=language, key=key), ""]
    return lines


def endpoint_block(endpoint: Any, *, language: str) -> list[str]:
    key = endpoint_key(endpoint)
    return _interface_block(key, _method_for(key), endpoint.dataset.data_type, providers_for(endpoint.dataset), language=language)


def computed_block(*, language: str) -> list[str]:
    return _interface_block("market.deviation", _CLIENT.market.deviation, COMPUTED_DEVIATION_DATASET.data_type, (), language=language, computed=True)



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
            "### Date-bounded searches", "", "For `news.search`, `disclosure.search`, `market_news.search`, and `forum.replies`, `since` and `until` are inclusive time filters. Start at `page=1`; the Client scans source pages within a safety bound, stops after reaching an older page for descending results or exhausting the source, and honors `max_results`. If the safety bound is reached before the date boundary or source end, `result.warnings` reports that results may be incomplete. Set a practical `max_results` cap and inspect warnings when completeness matters.", "",
            "### Document URLs", "", "For news references, `sourceUrl` identifies the source search/list page, while `documentUrl` points to the article body. Use `ref.document_url` when you need the article URL; code that treated `ref.source_url` as the article URL should migrate to `ref.document_url`. For disclosure references, `sourceUrl` is the source query page and `originalDocumentUrl` remains the notice or attachment URL. Disclosure `sourceRecordedAt` is retained under `provenance.adjustments` as EastMoney's internal record time; it is not the notice publication time. Use `publishedAt` for the displayed notice time.", "",
            "### FetchResult usage", "", "Every method returns `FetchResult`. Record-backed endpoints place tuples of normalized `StandardRecord` values in `.data`; a single document-detail call returns one `StandardRecord`, document searches return typed reference tuples, and computed deviation returns `DeviationData`. `Dataset.data_type` describes the row payload schema, while `FetchResult.data` carries the runtime record or reference shape. Export business dictionaries with `result.to_dicts()` and inspect `result.warnings` for partial results. Retrieval details remain available through `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.",
        ]
    return [
        "## 5. 通用说明", "", "### 证券输入规则", "",
        "- 裸代码会按接口语义解析：股票接口把 `000001` 解释为深市股票，指数接口把 `000001` 解释为上证指数。", "- 支持的代码前缀和市场规则由 FinchX 在内部校验，调用方只需传入代码字符串。", "",
        "### 日期输入", "", "公开日期参数接受 `datetime.date`，或 `YYYY-MM-DD`、`YYYYMMDD`、`YYYY/MM/DD` 三种无歧义字符串。非法日期和 `09/01/2026` 这类歧义格式会被拒绝。仅日期字段不接受 `datetime`；新闻、公告、全市场新闻和论坛的时间范围也接受带时区 `datetime`。", "",
        "### Warnings", "", "`result.warnings` 用于记录可恢复的数据质量或兼容性问题，例如跳过存在 schema drift 的单条 News 记录。", "",
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
