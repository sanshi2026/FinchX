# FinchX 数据 API 参考

[English](DATA_API_REFERENCE.md) | 简体中文

本文档覆盖 42 个数据接口 + 1 个计算能力 = 43 个公开能力。

## 1. FinchX 是什么 / 架构概览

FinchX 是一个面向中国市场数据的统一客户端。用户调用一个公开 Client；FinchX 校验请求、访问数据源，并返回统一格式的结果。

| 层次 | 作用 |
| --- | --- |
| Client | 用户调用入口：`FinchX()`。 |
| Dataset | 定义稳定的请求模型和业务数据结构。 |
| Provider | 实现一个真实的外部数据源。 |
| Collector | 把请求路由到 Provider，并生成 `FetchResult`。 |
| FetchResult | 默认先展示业务数据；`provider`、`provenance`、`attempts`、`warnings`、`cache_hit` 保留为审计属性。 |

单证券便捷调用优先使用 `600519` 这样的六位代码。标的复杂或有歧义时，请使用 `InstrumentId`。

## 2. 快速开始

```python
from datetime import date
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot("600519")
calendar = fx.reference.trading_calendar(date(2026, 9, 1), date(2026, 9, 30))
pool = fx.market.broken_limit_pool()
news = fx.news.search("600519")

print(result)
rows = result.to_dicts()
df = result.to_pandas()

```

`print(result)` 显示简短的业务摘要；`result.to_dicts()` 返回行字典；`result.to_pandas()` 返回 DataFrame。pandas 是可选依赖；未安装时调用 `to_pandas()` 会给出安装提示。

## 3. 接口总览

下面按用户要解决的问题分组，覆盖全部公开能力。

### 基础参考与交易日历

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.reference.instrument(...)` | 获取标的规范身份和名称。 | `tencent.finance.qq.market` |
| `fx.reference.trading_calendar(...)` | 获取日期范围内的 A 股交易日标记。 | `szse.official.calendar`, `pandas_market_calendars` |

### 市场概览、排名与股票池

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.breadth(...)` | 获取当前市场涨跌家数分布。 | `eastmoney.push2ex.breadth` |
| `fx.market.broken_limit_pool(...)` | 获取最新炸板池快照。 | `eastmoney.push2ex.broken_limit_pool` |
| `fx.market.consecutive_limit_up(...)` | 获取连板股快照。 | `aigupiao.series_limit_up` |
| `fx.market.daily_replay(...)` | 获取指定日期的每日复盘数据。 | `jiuyangongshe.daily_replay` |
| `fx.market.dragon_tiger_detail(...)` | 获取指定标的的龙虎榜明细。 | `aigupiao.dragon_tiger` |
| `fx.market.dragon_tiger_list(...)` | 获取指定交易日的龙虎榜列表。 | `aigupiao.dragon_tiger` |
| `fx.market.limit_down_pool(...)` | 获取最新跌停池快照。 | `eastmoney.push2ex.limit_down_pool` |
| `fx.market.limit_up_pool(...)` | 获取最新涨停池快照。 | `eastmoney.push2ex.limit_up_pool` |
| `fx.market.quote(...)` | 获取选定股票范围的行情快照。 | `tencent.finance.qq.market` |
| `fx.market.ranking(...)` | 获取指定条件的市场排行。 | `tencent.finance.qq.market` |
| `fx.market.sentiment(...)` | 获取市场情绪快照。 | `aigupiao.market_sentiment` |
| `fx.market.strong_pool(...)` | 获取最新强势股池快照。 | `eastmoney.push2ex.strong_pool` |
| `fx.market.yesterday_limit_up_pool(...)` | 获取最新昨日涨停池快照。 | `eastmoney.push2ex.yesterday_limit_up_pool` |

### 单证券行情、盘口、K 线、资金流与板块

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.equity_intraday(...)` | 获取单个股票交易日内分钟数据。 | `tencent.finance.qq.intraday` |
| `fx.market.equity_intraday_5d(...)` | 获取股票五日分钟数据。 | `tencent.finance.qq.intraday` |
| `fx.market.fund_flow_daily(...)` | 获取单个标的的每日资金流数据。 | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_intraday(...)` | 获取单个标的的盘中资金流数据。 | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_snapshot(...)` | 获取资金流快照。 | `tencent.finance.qq.fund_flow` |
| `fx.market.index_intraday(...)` | 获取单个指数交易日内分钟数据。 | `tencent.finance.qq.intraday` |
| `fx.market.index_intraday_5d(...)` | 获取指数五日分钟数据。 | `tencent.finance.qq.intraday` |
| `fx.market.industry_comparison(...)` | 获取市场行业比较数据。 | `tencent.finance.qq.industry` |
| `fx.market.instrument_sector_snapshot(...)` | 获取标的所属板块及板块快照。 | `tencent.finance.qq.sector` |
| `fx.market.stock_keyword(...)` | 获取数据源提供的股票关键词。 | `eastmoney.stockrank` |
| `fx.market.ohlcv(...)` | 获取单个标的的日线 OHLCV 数据。 | `tencent.finance.qq.klines`, `sohu.finance.klines` |
| `fx.market.orderbook(...)` | 获取单个标的的盘口数据。 | `tencent.finance.qq.quote` |
| `fx.market.quote_snapshot(...)` | 获取单个标的的行情快照。 | `tencent.finance.qq.quote` |

### 公司基本面与财务

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.fundamental.company_profile(...)` | 获取公司概况。 | `tencent.finance.qq.f10` |
| `fx.fundamental.financial_summary(...)` | 获取公司财务摘要。 | `tencent.finance.qq.f10` |
| `fx.fundamental.industry_comparison(...)` | 获取公司与行业的基本面比较。 | `tencent.finance.qq.f10` |
| `fx.fundamental.revenue_breakdown(...)` | 获取公司收入构成。 | `tencent.finance.qq.f10` |
| `fx.financial.statements(...)` | 获取财务报表数据。 | `tonghuashun.financial` |

### 新闻与公告

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.news.search(...)` | 搜索个股新闻并返回文档引用。 | `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news` |
| `fx.disclosure.search(...)` | 搜索个股公告并返回公告引用。 | `eastmoney.disclosure` |

### 股东、管理层与公司行动

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.ownership.capital_snapshot(...)` | 获取股本快照。 | `tencent.finance.qq.f10` |
| `fx.ownership.float_holder(...)` | 获取流通股东数据。 | `tencent.finance.qq.float_holder` |
| `fx.ownership.holder_summary_snapshot(...)` | 获取股东汇总快照。 | `tencent.finance.qq.f10` |
| `fx.company.executive_share_change(...)` | 获取高管持股变动。 | `tencent.finance.qq.f10` |
| `fx.company.executive_snapshot(...)` | 获取高管快照。 | `tencent.finance.qq.f10` |
| `fx.corporate_action.dividend(...)` | 获取分红除权记录。 | `tencent.finance.qq.f10` |
| `fx.corporate_action.repurchase(...)` | 获取回购记录。 | `tencent.finance.qq.f10` |

### 计算型分析

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.deviation(...)` | 计算经过审计的基于收盘价的偏离值。 | — |

## 4. 接口详情

## 4.1 基础参考与交易日历

### `fx.reference.instrument(...)`

**提供什么数据**
获取标的规范身份和名称。

**数据源**
`tencent.finance.qq.market`

**调用方式**

```python
fx.reference.instrument(instrument_id: 'InstrumentInput | None' = None, *, request: 'InstrumentRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[InstrumentData]'
```

**示例**

<!-- api-example: reference.instrument -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.reference.instrument("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | 无 request 时必填 | None | InstrumentId 或六位 A 股代码。 |
| request | InstrumentRequest \| None | 便捷参数的替代 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`InstrumentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| name | str | 名称。 |

### `fx.reference.trading_calendar(...)`

**提供什么数据**
获取日期范围内的 A 股交易日标记。

**数据源**
`szse.official.calendar`, `pandas_market_calendars`

**调用方式**

```python
fx.reference.trading_calendar(start_date: 'date | None' = None, end_date: 'date | None' = None, *, market: 'Market' = <Market.CN_A: 'cn_a'>, request: 'TradingCalendarRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[TradingCalendarData]'
```

**示例**

<!-- api-example: reference.trading_calendar -->
```python
from datetime import date
from finchx import FinchX

fx = FinchX()
result = fx.reference.trading_calendar(
    date(2026, 9, 1),
    date(2026, 9, 30),
)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| start_date | date \| None | 无 request 时必填 | None | 包含在内的开始日期。 |
| end_date | date \| None | 无 request 时必填 | None | 包含在内的结束日期。 |
| market | Market | 可选 | Market.CN_A | 市场范围；默认是 Market.CN_A。 |
| request | TradingCalendarRequest \| None | 便捷参数的替代 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`TradingCalendarData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| date | date | 日期。 |
| isTradingDay | bool | — |

## 4.2 市场概览、排名与股票池

### `fx.market.breadth(...)`

**提供什么数据**
获取当前市场涨跌家数分布。

**数据源**
`eastmoney.push2ex.breadth`

**调用方式**

```python
fx.market.breadth(request: 'MarketBreadthRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBreadthData]'
```

**示例**

<!-- api-example: market.breadth -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.breadth()
```

**参数**

无。

**输出字段**

数据模型：`MarketBreadthData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| tradeDate | date | EastMoney 报告的交易日期。 |
| advancing | int | — |
| declining | int | — |
| unchanged | int | — |
| total | int | — |
| limitUpCount | int | — |
| limitDownCount | int | — |
| upOver10PercentCount | int | — |
| downOver10PercentCount | int | — |
| distribution | list[MarketBreadthDistributionEntry] | — |

嵌套业务模型： `MarketBreadthDistributionEntry`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| bucket | MarketBreadthBucket | — |
| count | int | 该返回区间内的上市股票数量。 |

### `fx.market.broken_limit_pool(...)`

**提供什么数据**
获取最新炸板池快照。

**数据源**
`eastmoney.push2ex.broken_limit_pool`

**调用方式**

```python
fx.market.broken_limit_pool(request: 'MarketBrokenLimitPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBrokenLimitPoolData]'
```

**示例**

<!-- api-example: market.broken_limit_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.broken_limit_pool()
```

**参数**

无。

**输出字段**

数据模型：`MarketBrokenLimitPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 交易日期。 |
| name | str | 名称。 |
| price | Decimal | 最新价格，单位为每股 CNY。 |
| limitUpPrice | Decimal | 当前交易日涨停价，单位为每股 CNY。 |
| changeRate | Decimal | 比例小数。 |
| amount | Decimal | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 金额，单位为 CNY。 |
| turnoverRate | Decimal | 比例小数。 |
| amplitude | Decimal | 当前交易日振幅比例小数。 |
| firstLimitUpTime | str \| None | — |
| limitUpBreakCount | int | — |
| industry | str | — |
| limitUpStats | MarketBrokenLimitPoolStats | — |

嵌套业务模型： `MarketBrokenLimitPoolStats`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| lookbackDays | int | — |
| limitUpCount | int | — |

### `fx.market.consecutive_limit_up(...)`

**提供什么数据**
获取连板股快照。

**数据源**
`aigupiao.series_limit_up`

**调用方式**

```python
fx.market.consecutive_limit_up(request: 'MarketConsecutiveLimitUpRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketConsecutiveLimitUpData]'
```

**示例**

<!-- api-example: market.consecutive_limit_up -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.consecutive_limit_up()
```

**参数**

无。

**输出字段**

数据模型：`MarketConsecutiveLimitUpData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| name | str | 名称。 |
| tradeDate | date | 交易日期。 |
| lastPrice | Decimal | 每股价格；币种为 CNY。 |
| change | Decimal | 带符号的价格变动，单位为每股 CNY。 |
| changeRatio | Decimal | 比例小数；10% 表示为 0.10。 |
| turnoverRatio | Decimal | 比例小数；12% 表示为 0.12。 |
| amount | Decimal | 金额，单位为 CNY。 |
| limitUpTime | str | — |
| state | str | — |
| isConsecutiveLimitUp | bool | — |
| consecutiveLimitUpCount | int \| None | — |
| previousConsecutiveLimitUpCount | int \| None | — |
| themeId | int \| None | — |
| themeName | str \| None | — |
| floatShares | int | 非负整数股数。 |
| totalShares | int | 非负整数股数。 |
| marketCap | Decimal | 总市值，单位为 CNY。 |

### `fx.market.daily_replay(...)`

**提供什么数据**
获取指定日期的每日复盘数据。

**数据源**
`jiuyangongshe.daily_replay`

**调用方式**

```python
fx.market.daily_replay(request: 'MarketDailyReplayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDailyReplayData]'
```

**示例**

<!-- api-example: market.daily_replay -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketDailyReplayRequest

fx = FinchX()
request = MarketDailyReplayRequest(requestedDate=date(2026, 9, 18))
result = fx.market.daily_replay(request)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketDailyReplayRequest | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketDailyReplayRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| requestedDate (`requested_date`) | date | 必填 | — | 请求日期。 |

**输出字段**

数据模型：`MarketDailyReplayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| requestedDate | date | — |
| tradeDate | date | 交易日期。 |
| themes | list[ReplayTheme] | — |

嵌套业务模型： `ReplayTheme`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| themeName | str | — |
| reason | str \| None | — |
| stockCount | int | — |
| sourceThemeId | str \| None | — |
| stocks | list[ReplayStock] | — |

嵌套业务模型： `ReplayStock`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| name | str | 名称。 |
| limitUpTime | time \| None | — |
| streakText | str \| None | — |
| price | Decimal \| None | — |
| changeRatio | Decimal \| None | — |
| day | int \| None | — |
| edition | int \| None | — |
| expound | str \| None | — |

### `fx.market.dragon_tiger_detail(...)`

**提供什么数据**
获取指定标的的龙虎榜明细。

**数据源**
`aigupiao.dragon_tiger`

**调用方式**

```python
fx.market.dragon_tiger_detail(request: 'MarketDragonTigerDetailRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerDetailData]'
```

**示例**

<!-- api-example: market.dragon_tiger_detail -->
```python
from datetime import date
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketDragonTigerDetailRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketDragonTigerDetailRequest(
    instrumentId=instrument_id,
    tradeDate=date(2026, 9, 18),
    tradeId="example-trade-id",
)
result = fx.market.dragon_tiger_detail(request)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerDetailRequest | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketDragonTigerDetailRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |
| tradeDate (`trade_date`) | date | 必填 | — | 交易日期。 |
| tradeId (`trade_id`) | str | 必填 | — | 龙虎榜交易标识。 |

**输出字段**

数据模型：`MarketDragonTigerDetailData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| name | str | 名称。 |
| tradeDate | date | 交易日期。 |
| tradeId | str | — |
| closePrice | Decimal | 每股价格；币种为 CNY。 |
| changeRatio | Decimal | 比例小数，而不是百分点：4.24% 表示为 0.0424。 |
| amount | Decimal | 金额，单位为 CNY。 |
| totalBuy | Decimal | 金额，单位为 CNY。 |
| totalSell | Decimal | 金额，单位为 CNY。 |
| totalNet | Decimal | 金额，单位为 CNY。 |
| explanation | str | — |
| commentKind | str \| None | — |
| commentObjectId | str \| None | — |
| buySeats | list[DragonTigerSeat] | — |
| sellSeats | list[DragonTigerSeat] | — |

嵌套业务模型： `DragonTigerSeat`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| rank | int | 根据来源数组顺序推导。 |
| seatName | str | — |
| sourceSeatCode | str \| None | — |
| hasDetails | bool \| None | — |
| buyAmount | Decimal | 金额，单位为 CNY。 |
| sellAmount | Decimal | 金额，单位为 CNY。 |
| netAmount | Decimal | 金额，单位为 CNY。 |

### `fx.market.dragon_tiger_list(...)`

**提供什么数据**
获取指定交易日的龙虎榜列表。

**数据源**
`aigupiao.dragon_tiger`

**调用方式**

```python
fx.market.dragon_tiger_list(request: 'MarketDragonTigerListRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerListData]'
```

**示例**

<!-- api-example: market.dragon_tiger_list -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketDragonTigerListRequest

fx = FinchX()
request = MarketDragonTigerListRequest(tradeDate=date(2026, 9, 18))
result = fx.market.dragon_tiger_list(request)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerListRequest | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketDragonTigerListRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| tradeDate (`trade_date`) | date | 必填 | — | 交易日期。 |

**输出字段**

数据模型：`MarketDragonTigerListData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| name | str | 名称。 |
| tradeDate | date | 交易日期。 |
| tradeId | str | — |
| closePrice | Decimal | 每股价格；币种为 CNY。 |
| changeRatio | Decimal | 比例小数；10% 表示为 0.10。 |
| amount | Decimal | 金额，单位为 CNY。 |
| totalBuy | Decimal | 金额，单位为 CNY。 |
| totalNet | Decimal | 金额，单位为 CNY。 |
| explanation | str | — |
| threeDayFlag | str \| None | — |
| themeId | int \| None | — |
| themeName | str \| None | — |

### `fx.market.limit_down_pool(...)`

**提供什么数据**
获取最新跌停池快照。

**数据源**
`eastmoney.push2ex.limit_down_pool`

**调用方式**

```python
fx.market.limit_down_pool(request: 'MarketLimitDownPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitDownPoolData]'
```

**示例**

<!-- api-example: market.limit_down_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_down_pool()
```

**参数**

无。

**输出字段**

数据模型：`MarketLimitDownPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 交易日期。 |
| name | str | 名称。 |
| price | Decimal | 最新价格，单位为每股 CNY。 |
| changeRate | Decimal | 比例小数；-10% 表示为 -0.10。 |
| amount | Decimal | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 金额，单位为 CNY。 |
| priceEarningsRatio | Decimal \| None | EastMoney 报告的动态 P/E；来源计算细节未提供。 |
| turnoverRate | Decimal | 比例小数。 |
| limitDownQueueAmount | Decimal \| None | EastMoney 报告的跌停排队金额，单位为 CNY。 |
| lastLimitDownTime | str \| None | — |
| boardTradedAmount | Decimal \| None | 以跌停价成交的金额，单位为 CNY。 |
| consecutiveLimitDownDays | int | — |
| limitDownOpenCount | int | — |
| industry | str | — |

### `fx.market.limit_up_pool(...)`

**提供什么数据**
获取最新涨停池快照。

**数据源**
`eastmoney.push2ex.limit_up_pool`

**调用方式**

```python
fx.market.limit_up_pool(request: 'MarketLimitUpPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitUpPoolData]'
```

**示例**

<!-- api-example: market.limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_up_pool()
```

**参数**

无。

**输出字段**

数据模型：`MarketLimitUpPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 交易日期。 |
| name | str | 名称。 |
| price | Decimal | 最新价格，单位为每股 CNY。 |
| changeRate | Decimal | 比例小数；10% 表示为 0.10。 |
| amount | Decimal | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 金额，单位为 CNY。 |
| turnoverRate | Decimal | 比例小数；5% 表示为 0.05。 |
| consecutiveLimitUpDays | int | — |
| firstLimitUpTime | str \| None | — |
| lastLimitUpTime | str \| None | — |
| limitUpQueueAmount | Decimal \| None | — |
| limitUpBreakCount | int | — |
| industry | str | — |
| limitUpStats | MarketLimitUpStats | — |

嵌套业务模型： `MarketLimitUpStats`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| lookbackDays | int | — |
| limitUpCount | int | — |

### `fx.market.quote(...)`

**提供什么数据**
获取选定股票范围的行情快照。

**数据源**
`tencent.finance.qq.market`

**调用方式**

```python
fx.market.quote(*, universe: 'InstrumentUniverse' = <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'>, request: 'MarketQuoteUniverseRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteData]'
```

**示例**

<!-- api-example: market.quote -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | 可选 | InstrumentUniverse.CN_A_SHARE | 查询范围。 |
| request | MarketQuoteUniverseRequest \| None | 可选 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`MarketQuoteData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| name | str \| None | 名称。 |
| price | Decimal | 每股价格；币种为 CNY。 |
| priceChange | Decimal \| None | 带符号的绝对价格变动，单位为每股 CNY。 |
| changeRate | Decimal \| None | — |
| changeRate5d | Decimal \| None | 来源指定的 5 日价格变动，以比例小数存储。 |
| changeRate10d | Decimal \| None | 来源指定的 10 日价格变动，以比例小数存储。 |
| changeRate20d | Decimal \| None | 来源指定的 20 日价格变动，以比例小数存储。 |
| changeRate60d | Decimal \| None | 来源指定的 60 日价格变动，以比例小数存储。 |
| changeRate52w | Decimal \| None | 来源指定 52 周期间的价格变动，以比例小数表示。 |
| changeRateYtd | Decimal \| None | 年初至今价格变动，以比例小数存储。 |
| amplitude | Decimal \| None | 盘中价格振幅，以比例小数存储。 |
| volumeRatio | Decimal \| None | 非负成交量倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | — |
| amount | Decimal \| None | — |
| turnoverRate | Decimal \| None | — |
| marketCap | Decimal \| None | — |
| floatMarketCap | Decimal \| None | — |
| peTtm | Decimal \| None | — |
| mainNetInflow | Decimal \| None | — |
| mainInflow | Decimal \| None | — |
| mainOutflow | Decimal \| None | — |
| mainInflow5d | Decimal \| None | — |
| mainOutflow5d | Decimal \| None | — |

### `fx.market.ranking(...)`

**提供什么数据**
获取指定条件的市场排行。

**数据源**
`tencent.finance.qq.market`

**调用方式**

```python
fx.market.ranking(request: 'MarketRankingRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketRankingData]'
```

**示例**

<!-- api-example: market.ranking -->
```python
from finchx import FinchX
from finchx.datasets import InstrumentUniverse, MarketRankingRequest, RankingCriterion, RankingDirection

fx = FinchX()
request = MarketRankingRequest(
    universe=InstrumentUniverse.CN_A_SHARE,
    criterion=RankingCriterion.TURNOVER,
    direction=RankingDirection.DESCENDING,
    limit=20,
)
result = fx.market.ranking(request)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketRankingRequest | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketRankingRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | 必填 | — | 查询范围。 |
| criterion | RankingCriterion | 必填 | — | 排行指标。 |
| direction | RankingDirection | 必填 | — | 排行方向。 |
| limit | int \| None | 必填 | — | 返回数量上限。 |

**输出字段**

数据模型：`MarketRankingData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| name | str \| None | 名称。 |
| price | Decimal | 每股价格；币种为 CNY。 |
| priceChange | Decimal \| None | 带符号的绝对价格变动，单位为每股 CNY。 |
| changeRate | Decimal \| None | — |
| changeRate5d | Decimal \| None | 来源指定的 5 日价格变动，以比例小数存储。 |
| changeRate10d | Decimal \| None | 来源指定的 10 日价格变动，以比例小数存储。 |
| changeRate20d | Decimal \| None | 来源指定的 20 日价格变动，以比例小数存储。 |
| changeRate60d | Decimal \| None | 来源指定的 60 日价格变动，以比例小数存储。 |
| changeRate52w | Decimal \| None | 来源指定 52 周期间的价格变动，以比例小数表示。 |
| changeRateYtd | Decimal \| None | 年初至今价格变动，以比例小数存储。 |
| amplitude | Decimal \| None | 盘中价格振幅，以比例小数存储。 |
| volumeRatio | Decimal \| None | 非负成交量倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | — |
| amount | Decimal \| None | — |
| turnoverRate | Decimal \| None | — |
| marketCap | Decimal \| None | — |
| floatMarketCap | Decimal \| None | — |
| peTtm | Decimal \| None | — |
| mainNetInflow | Decimal \| None | — |
| mainInflow | Decimal \| None | — |
| mainOutflow | Decimal \| None | — |
| mainInflow5d | Decimal \| None | — |
| mainOutflow5d | Decimal \| None | — |
| universe | InstrumentUniverse | — |
| direction | RankingDirection | — |
| position | int | — |
| metric | TurnoverRankingMetric \| ChangePercentRankingMetric \| VolumeRankingMetric | — |

嵌套业务模型： `ChangePercentRankingMetric`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| criterion | Literal['change_percent'] | — |
| value | Decimal | 比例小数，而不是百分点：4.24% 表示为 0.0424。 |

嵌套业务模型： `TurnoverRankingMetric`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| criterion | Literal['turnover'] | — |
| value | Decimal | 金额，单位为 CNY。 |

嵌套业务模型： `VolumeRankingMetric`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| criterion | Literal['volume'] | — |
| value | int | 非负整数股数。 |

### `fx.market.sentiment(...)`

**提供什么数据**
获取市场情绪快照。

**数据源**
`aigupiao.market_sentiment`

**调用方式**

```python
fx.market.sentiment(request: 'MarketSentimentRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketSentimentData]'
```

**示例**

<!-- api-example: market.sentiment -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.sentiment()
```

**参数**

无。

**输出字段**

数据模型：`MarketSentimentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| marketTemperature | Decimal | Aigupiao 定义的情绪温度；不是物理温度或比例。 |
| totalTurnover | Decimal \| None | — |
| forecastedTurnover | Decimal \| None | 来源预测值，不是观测到的换手率。 |
| turnoverChangeAmount | Decimal \| None | 来源报告的成交金额相对前一日的变动。 |
| blastBreakRatio | Decimal \| None | 来源定义的比例；FinchX 不复现其分母。 |
| previousLimitUpBreakChangeRatio | Decimal \| None | 来源定义的前期炸板表现比例。 |
| stopTradingCount | int | — |
| oneLimitUpCount | int | — |
| twoLimitUpCount | int | — |
| threeLimitUpCount | int | — |
| highLimitUpCount | int | — |
| twoLimitUpPromotionRatio | Decimal \| None | 来源定义的晋级比例；FinchX 不复现其分母。 |
| threeLimitUpPromotionRatio | Decimal \| None | 来源定义的晋级比例；FinchX 不复现其分母。 |
| highLimitUpPromotionRatio | Decimal \| None | 来源定义的晋级比例；FinchX 不复现其分母。 |
| previousLimitUpThemeChangeRatio | Decimal \| None | 来源定义的前期涨停组表现比例。 |
| previousConsecutiveLimitUpThemeChangeRatio | Decimal \| None | 来源定义的前期连板组表现比例。 |

### `fx.market.strong_pool(...)`

**提供什么数据**
获取最新强势股池快照。

**数据源**
`eastmoney.push2ex.strong_pool`

**调用方式**

```python
fx.market.strong_pool(request: 'MarketStrongPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStrongPoolData]'
```

**示例**

<!-- api-example: market.strong_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.strong_pool()
```

**参数**

无。

**输出字段**

数据模型：`MarketStrongPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 交易日期。 |
| name | str | 名称。 |
| price | Decimal | 最新价格，单位为每股 CNY。 |
| limitUpPrice | Decimal | 当前涨停价，单位为每股 CNY。 |
| changeRate | Decimal | 比例小数；20% 表示为 0.20。 |
| amount | Decimal | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 金额，单位为 CNY。 |
| turnoverRate | Decimal | 比例小数。 |
| isSixtyDayHigh | bool | — |
| selectionReason | StrongPoolSelectionReason | — |
| volumeRatio | Decimal | 来源成交量倍数，为无量纲倍数。 |
| industry | str | — |
| limitUpStats | MarketStrongPoolStats | — |

嵌套业务模型： `MarketStrongPoolStats`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| lookbackDays | int | — |
| limitUpCount | int | — |

### `fx.market.yesterday_limit_up_pool(...)`

**提供什么数据**
获取最新昨日涨停池快照。

**数据源**
`eastmoney.push2ex.yesterday_limit_up_pool`

**调用方式**

```python
fx.market.yesterday_limit_up_pool(request: 'MarketYesterdayLimitUpPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketYesterdayLimitUpPoolData]'
```

**示例**

<!-- api-example: market.yesterday_limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.yesterday_limit_up_pool()
```

**参数**

无。

**输出字段**

数据模型：`MarketYesterdayLimitUpPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 当前观测到的来源日期，不是前一涨停事件日期。 |
| name | str | 名称。 |
| currentPrice | Decimal | 当前交易日价格，单位为每股 CNY。 |
| currentLimitUpPrice | Decimal | 当前交易日涨停价，单位为每股 CNY。 |
| currentChangeRate | Decimal | 当前交易日比例小数。 |
| currentAmount | Decimal | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 金额，单位为 CNY。 |
| currentTurnoverRate | Decimal | 当前交易日换手率比例小数。 |
| currentAmplitude | Decimal | 当前交易日振幅比例小数。 |
| yesterdayFirstLimitUpTime | str \| None | 前一交易日首次涨停时间，使用市场本地 HH:MM:SS。 |
| yesterdayConsecutiveLimitUpDays | int | — |
| industry | str | — |

## 4.3 单证券行情、盘口、K 线、资金流与板块

### `fx.market.equity_intraday(...)`

**提供什么数据**
获取单个股票交易日内分钟数据。

**数据源**
`tencent.finance.qq.intraday`

**调用方式**

```python
fx.market.equity_intraday(request: 'EquityIntradayRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

**示例**

<!-- api-example: market.equity_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | EquityIntradayRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `EquityIntradayRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`EquityIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

### `fx.market.equity_intraday_5d(...)`

**提供什么数据**
获取股票五日分钟数据。

**数据源**
`tencent.finance.qq.intraday`

**调用方式**

```python
fx.market.equity_intraday_5d(request: 'EquityIntraday5dRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

**示例**

<!-- api-example: market.equity_intraday_5d -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday_5d("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | EquityIntraday5dRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `EquityIntraday5dRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`EquityIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

### `fx.market.fund_flow_daily(...)`

**提供什么数据**
获取单个标的的每日资金流数据。

**数据源**
`tencent.finance.qq.fund_flow`

**调用方式**

```python
fx.market.fund_flow_daily(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowDailyData]'
```

**示例**

<!-- api-example: market.fund_flow_daily -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_daily("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketFundFlowRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketFundFlowDailyData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | Tencent 报告的交易日期，不是 FinchX 抓取时间。 |
| mainNetInflow | Decimal | 金额，单位为 CNY。 |
| close | Decimal | 每日收盘价，单位为每股 CNY。 |

### `fx.market.fund_flow_intraday(...)`

**提供什么数据**
获取单个标的的盘中资金流数据。

**数据源**
`tencent.finance.qq.fund_flow`

**调用方式**

```python
fx.market.fund_flow_intraday(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowIntradayData]'
```

**示例**

<!-- api-example: market.fund_flow_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_intraday("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketFundFlowRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketFundFlowIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | Tencent 报告的交易日期，不是 FinchX 抓取时间。 |
| time | str | 来源市场本地时间，格式为 HH:MM；数值从开盘起累计。 |
| price | Decimal | 来源价格，单位为每股 CNY。 |
| cumulativeMainNetInflow | Decimal | 金额，单位为 CNY。 |
| cumulativeRetailNetInflow | Decimal | 金额，单位为 CNY。 |
| cumulativeSuperLargeNetInflow | Decimal | 金额，单位为 CNY。 |
| cumulativeLargeNetInflow | Decimal | 金额，单位为 CNY。 |
| cumulativeMediumNetInflow | Decimal | 金额，单位为 CNY。 |
| cumulativeSmallNetInflow | Decimal | 金额，单位为 CNY。 |
| cumulativeMainInflow | Decimal | 金额，单位为 CNY。 |
| cumulativeMainOutflow | Decimal | 金额，单位为 CNY。 |

### `fx.market.fund_flow_snapshot(...)`

**提供什么数据**
获取资金流快照。

**数据源**
`tencent.finance.qq.fund_flow`

**调用方式**

```python
fx.market.fund_flow_snapshot(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowSnapshotData]'
```

**示例**

<!-- api-example: market.fund_flow_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_snapshot("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketFundFlowRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketFundFlowSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | Tencent 报告的交易日期，不是 FinchX 抓取时间。 |
| mainNetInflow | Decimal | 金额，单位为 CNY。 |
| mainInflow | Decimal | 金额，单位为 CNY。 |
| mainOutflow | Decimal | 金额，单位为 CNY。 |
| mainInflowRate | Decimal | 比例小数；15% 表示为 0.15。 |
| mainOutflowRate | Decimal | 比例小数；19% 表示为 0.19。 |
| retailInflow | Decimal | 金额，单位为 CNY。 |
| retailOutflow | Decimal | 金额，单位为 CNY。 |
| retailInflowRate | Decimal | 比例小数；35% 表示为 0.35。 |
| retailOutflowRate | Decimal | 比例小数；31% 表示为 0.31。 |
| superLargeNetInflow | Decimal | 金额，单位为 CNY。 |
| largeNetInflow | Decimal | 金额，单位为 CNY。 |
| mediumNetInflow | Decimal | 金额，单位为 CNY。 |
| smallNetInflow | Decimal | 金额，单位为 CNY。 |

### `fx.market.index_intraday(...)`

**提供什么数据**
获取单个指数交易日内分钟数据。

**数据源**
`tencent.finance.qq.intraday`

**调用方式**

```python
fx.market.index_intraday(request: 'IndexIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

**示例**

<!-- api-example: market.index_intraday -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import IndexIntradayRequest

fx = FinchX()
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
request = IndexIntradayRequest(instrumentId=index_id)
result = fx.market.index_intraday(request)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | IndexIntradayRequest | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `IndexIntradayRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`IndexIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

### `fx.market.index_intraday_5d(...)`

**提供什么数据**
获取指数五日分钟数据。

**数据源**
`tencent.finance.qq.intraday`

**调用方式**

```python
fx.market.index_intraday_5d(request: 'IndexIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

**示例**

<!-- api-example: market.index_intraday_5d -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import IndexIntraday5dRequest

fx = FinchX()
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
request = IndexIntraday5dRequest(instrumentId=index_id)
result = fx.market.index_intraday_5d(request)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | IndexIntraday5dRequest | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `IndexIntraday5dRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`IndexIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

### `fx.market.industry_comparison(...)`

**提供什么数据**
获取市场行业比较数据。

**数据源**
`tencent.finance.qq.industry`

**调用方式**

```python
fx.market.industry_comparison(request: 'MarketIndustryComparisonRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketIndustryComparisonData]'
```

**示例**

<!-- api-example: market.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.industry_comparison("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketIndustryComparisonRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketIndustryComparisonRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketIndustryComparisonData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| industry | IndustryIdentity | — |
| instrumentValues | IndustryComparisonValues | — |
| industryRanks | IndustryComparisonRanks | — |
| industryAggregate | IndustryAggregate | — |
| marketAggregate | MarketAggregate | — |

嵌套业务模型： `IndustryIdentity`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| providerNamespace | Literal['tencent_hypm'] | — |
| providerIndustryId | str | — |
| name | str | 名称。 |

嵌套业务模型： `IndustryComparisonValues`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| priceEarnings | Decimal \| None | — |
| earningsPerShare | Decimal \| None | Tencent mgsy，单位为每股 CNY；此处未提供报告期语义。 |
| marketCapitalization | Decimal \| None | Tencent zsz 已从亿元转换为 CNY。 |

嵌套业务模型： `IndustryComparisonRanks`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| priceEarningsRank | int \| None | — |
| earningsPerShareRank | int \| None | — |
| marketCapitalizationRank | int \| None | — |

嵌套业务模型： `IndustryAggregate`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| priceEarnings | Decimal \| None | — |
| earningsPerShare | Decimal \| None | Tencent mgsy，单位为每股 CNY；此处未提供报告期语义。 |
| marketCapitalization | Decimal \| None | Tencent zsz 已从亿元转换为 CNY。 |
| count | int \| None | — |

嵌套业务模型： `MarketAggregate`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| priceEarnings | Decimal \| None | — |
| earningsPerShare | Decimal \| None | Tencent mgsy，单位为每股 CNY；此处未提供报告期语义。 |
| marketCapitalization | Decimal \| None | Tencent zsz 已从亿元转换为 CNY。 |

### `fx.market.instrument_sector_snapshot(...)`

**提供什么数据**
获取标的所属板块及板块快照。

**数据源**
`tencent.finance.qq.sector`

**调用方式**

```python
fx.market.instrument_sector_snapshot(request: 'MarketInstrumentSectorSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketInstrumentSectorSnapshotData]'
```

**示例**

<!-- api-example: market.instrument_sector_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.instrument_sector_snapshot("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketInstrumentSectorSnapshotRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketInstrumentSectorSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketInstrumentSectorSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| sectors | list[InstrumentSectorEntry] | — |

嵌套业务模型： `InstrumentSectorEntry`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | — |
| sectorName | str | — |
| providerNamespace | Literal['tencent_plate'] | — |
| providerSectorId | str | — |
| level | int \| None | — |
| tag | str \| None | — |
| changePct | Decimal \| None | Tencent zdf 已从百分点转换为比例小数。 |

### `fx.market.stock_keyword(...)`

**提供什么数据**
获取数据源提供的股票关键词。

**数据源**
`eastmoney.stockrank`

**调用方式**

```python
fx.market.stock_keyword(request: 'MarketStockKeywordRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStockKeywordData]'
```

**示例**

<!-- api-example: market.stock_keyword -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.stock_keyword("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketStockKeywordRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketStockKeywordRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketStockKeywordData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| keywords | list[StockKeywordEntry] | — |

嵌套业务模型： `StockKeywordEntry`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| keywordName | str | — |
| providerNamespace | Literal['eastmoney_stockrank'] | — |
| providerKeywordId | str | — |
| hitCount | int | — |
| calculatedAt | datetime | — |

### `fx.market.ohlcv(...)`

**提供什么数据**
获取单个标的的日线 OHLCV 数据。

**数据源**
`tencent.finance.qq.klines`, `sohu.finance.klines`

**调用方式**

```python
fx.market.ohlcv(instrument_id: 'InstrumentInput | None' = None, start_date: 'date | None' = None, end_date: 'date | None' = None, adjustment: 'KlineAdjustment | None' = None, *, request: 'KlinesRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketKlineData]'
```

**示例**

<!-- api-example: market.ohlcv -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import KlineAdjustment

fx = FinchX()
result = fx.market.ohlcv(
    "600519",
    date(2026, 9, 1),
    date(2026, 9, 18),
    adjustment=KlineAdjustment.QFQ,
)
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | 无 request 时必填 | None | InstrumentId 或六位 A 股代码。 |
| start_date | date \| None | 无 request 时必填 | None | 包含在内的开始日期。 |
| end_date | date \| None | 无 request 时必填 | None | 包含在内的结束日期。 |
| adjustment | KlineAdjustment \| None | 股票必填；指数省略 | None | K 线复权方式。 |
| request | KlinesRequest \| None | 便捷参数的替代 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`MarketKlineData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| barDate | date | — |
| open | Decimal | 每股价格；币种为 CNY。 |
| high | Decimal | 每股价格；币种为 CNY。 |
| low | Decimal | 每股价格；币种为 CNY。 |
| close | Decimal | 每股价格；币种为 CNY。 |
| volume | int | 非负整数股数。 |
| amount | Decimal \| None | — |
| adjustment | KlineAdjustment | — |

### `fx.market.orderbook(...)`

**提供什么数据**
获取单个标的的盘口数据。

**数据源**
`tencent.finance.qq.quote`

**调用方式**

```python
fx.market.orderbook(request: 'MarketOrderbookRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketOrderbookData]'
```

**示例**

<!-- api-example: market.orderbook -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.orderbook("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketOrderbookRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketOrderbookRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketOrderbookData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| bids | list[OrderbookLevel] | — |
| asks | list[OrderbookLevel] | — |

嵌套业务模型： `OrderbookLevel`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| level | int | — |
| price | Decimal | 每股价格；币种为 CNY。 |
| size | int | 非负整数股数。 |

### `fx.market.quote_snapshot(...)`

**提供什么数据**
获取单个标的的行情快照。

**数据源**
`tencent.finance.qq.quote`

**调用方式**

```python
fx.market.quote_snapshot(request: 'MarketQuoteSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteSnapshotData]'
```

**示例**

<!-- api-example: market.quote_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | MarketQuoteSnapshotRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `MarketQuoteSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`MarketQuoteSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| price | Decimal | 最新价格，单位为每股 CNY。 |
| previousClose | Decimal \| None | — |
| open | Decimal \| None | 交易时段开盘价，单位为每股 CNY。 |
| high | Decimal \| None | 交易时段最高价，单位为每股 CNY。 |
| low | Decimal \| None | 交易时段最低价，单位为每股 CNY。 |
| priceChange | Decimal \| None | — |
| changeRate | Decimal \| None | 相对前收盘价的变动比例小数；3% 表示为 0.03。 |
| volume | int \| None | 本交易时段累计成交股数。 |
| amount | Decimal \| None | 本交易时段累计成交金额，单位为 CNY。 |
| sourceTimestamp | datetime | 来源报告的行情时间，与 FinchX capturedAt 分开。 |

## 4.4 公司基本面与财务

### `fx.fundamental.company_profile(...)`

**提供什么数据**
获取公司概况。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.fundamental.company_profile(instrument_id: 'InstrumentInput | None' = None, *, request: 'CompanyProfileRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CompanyProfileData]'
```

**示例**

<!-- api-example: fundamental.company_profile -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.company_profile("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | 无 request 时必填 | None | InstrumentId 或六位 A 股代码。 |
| request | CompanyProfileRequest \| None | 便捷参数的替代 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`CompanyProfileData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| companyName | str \| None | — |
| businessDescription | str \| None | — |
| issuePrice | Decimal \| None | 单位为每股 CNY；保留 Tencent gsjj.jg 作为来源候选值。 |
| listingDate | date \| None | — |

### `fx.fundamental.financial_summary(...)`

**提供什么数据**
获取公司财务摘要。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.fundamental.financial_summary(request: 'FinancialSummaryRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialSummaryData]'
```

**示例**

<!-- api-example: fundamental.financial_summary -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.financial_summary("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | FinancialSummaryRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `FinancialSummaryRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`FinancialSummaryData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| periods | list[FinancialSummaryPeriod] | — |

嵌套业务模型： `FinancialSummaryPeriod`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| periodEnd | date \| None | — |
| reportedPeriodLabel | str | — |
| periodType | Literal['annual', 'interim', 'unknown'] | — |
| eps | Decimal \| None | — |
| revenue | Decimal \| None | — |
| revenueGrowth | Decimal \| None | — |
| netProfit | Decimal \| None | — |
| netProfitGrowth | Decimal \| None | — |
| bookValuePerShare | Decimal \| None | — |
| netAssets | Decimal \| None | — |
| goodwill | Decimal \| None | — |
| goodwillToNetAssets | Decimal \| None | — |
| roe | Decimal \| None | — |
| debtRatio | Decimal \| None | — |
| grossMargin | Decimal \| None | — |

### `fx.fundamental.industry_comparison(...)`

**提供什么数据**
获取公司与行业的基本面比较。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.fundamental.industry_comparison(request: 'FundamentalIndustryComparisonRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndustryComparisonData]'
```

**示例**

<!-- api-example: fundamental.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.industry_comparison("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | FundamentalIndustryComparisonRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `IndustryComparisonRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**命名说明**
签名中的局部别名是 `FundamentalIndustryComparisonRequest`；request 模型是 `finchx.datasets.IndustryComparisonRequest`。

**输出字段**

数据模型：`IndustryComparisonData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| industryName | str \| None | — |
| metrics | list[IndustryComparisonMetric] | — |

嵌套业务模型： `IndustryComparisonMetric`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| metric | Literal['eps', 'revenue', 'net_profit', 'book_value_per_share', 'roe', 'debt_ratio', 'gross_margin', 'revenue_growth', 'net_profit_growth', 'market_cap', 'pe', 'pb', 'dividend_yield'] | — |
| metricBasis | Literal['financial_period', 'market_snapshot'] | — |
| companyValue | Decimal \| Decimal \| Decimal \| None | — |
| industryAvg | Decimal \| Decimal \| Decimal \| None | — |
| industryMax | Decimal \| Decimal \| Decimal \| None | — |
| industryMin | Decimal \| Decimal \| Decimal \| None | — |
| periodEnd | date \| None | — |
| reportedPeriodLabel | str | — |
| observationAt | datetime \| None | — |

### `fx.fundamental.revenue_breakdown(...)`

**提供什么数据**
获取公司收入构成。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.fundamental.revenue_breakdown(request: 'RevenueBreakdownRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RevenueBreakdownData]'
```

**示例**

<!-- api-example: fundamental.revenue_breakdown -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.revenue_breakdown("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | RevenueBreakdownRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `RevenueBreakdownRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`RevenueBreakdownData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| breakdowns | list[RevenueBreakdownRow] | — |

嵌套业务模型： `RevenueBreakdownRow`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| reportedPeriodLabel | str | — |
| periodEnd | date \| None | — |
| dimension | Literal['product', 'region', 'industry'] | — |
| itemName | str | — |
| revenue | Decimal \| None | — |
| revenueShare | Decimal \| None | — |
| currency | Literal['CNY'] | — |
| sourceGroup | Literal['detail', 'others'] | — |
| isRollup | bool | — |

### `fx.financial.statements(...)`

**提供什么数据**
获取财务报表数据。

**数据源**
`tonghuashun.financial`

**调用方式**

```python
fx.financial.statements(instrument_id: 'InstrumentInput | None' = None, statement_type: 'StatementType | None' = None, *, period_end: 'date | None' = None, max_periods: 'int | None' = None, request: 'FinancialStatementRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialStatementData]'
```

**示例**

<!-- api-example: financial.statements -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.financial.statements("600519", "income_statement")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | 无 request 时必填 | None | InstrumentId 或六位 A 股代码。 |
| statement_type | StatementType \| None | 无 request 时必填 | None | balance_sheet、income_statement 或 cash_flow_statement。 |
| period_end | date \| None | 可选 | None | 可选的报告期结束日期。 |
| max_periods | int \| None | 可选 | None | 可选的最大报告期数量。 |
| request | FinancialStatementRequest \| None | 便捷参数的替代 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`FinancialStatementData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| symbol | str | — |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | — |
| periods | list[FinancialStatementPeriod] | — |

嵌套业务模型： `FinancialStatementPeriod`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| periodEnd | date | — |
| lineItems | list[FinancialStatementLineItem] | — |

嵌套业务模型： `FinancialStatementLineItem`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| lineItemId | str | — |
| sourceName | str | — |
| sourceUnit | str | — |
| sourceValue | str \| bool \| int \| float \| None | — |
| value | Decimal \| None | — |
| currency | Currency \| None | — |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | — |

## 4.5 新闻与公告

### `fx.news.search(...)`

**提供什么数据**
搜索个股新闻并返回文档引用。

**数据源**
`eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`

**调用方式**

```python
fx.news.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, sort: 'str' = 'published_desc', request: 'NewsSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[NewsDocumentRef, ...]]'
```

**示例**

<!-- api-example: news.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.news.search("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | 无 request 时必填 | None | InstrumentId 或六位 A 股代码。 |
| page | int | 可选 | 1 | 从 1 开始的页码。 |
| page_size | int | 可选 | 20 | 单页数量。 |
| max_results | int \| None | 可选 | None | 可选的结果上限。 |
| since | date \| datetime \| None | 可选 | None | 可选的时间范围起点。 |
| until | date \| datetime \| None | 可选 | None | 可选的时间范围终点。 |
| sort | str | 可选 | 'published_desc' | published_desc 或 published_asc。 |
| request | NewsSearchRequest \| None | 便捷参数的替代 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`NewsDocumentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| documentId | str | — |
| sourceDocumentId | str | — |
| title | str | — |
| contentText | str \| None | — |
| summary | str \| None | — |
| publishedAt | datetime \| None | — |
| sourceOccurrences | list[NewsSourceOccurrence] | — |
| url | AnyUrl | — |
| originalUrl | AnyUrl \| None | — |
| contentAvailable | bool | — |
| source | str \| None | — |
| relatedInstruments | list[InstrumentId] | — |

嵌套业务模型： `NewsSourceOccurrence`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| providerId | str | — |
| sourceDocumentId | str | — |
| sourceUrl | AnyUrl \| None | — |
| documentUrl | AnyUrl \| None | — |
| publishedAt | datetime \| None | — |
| capturedAt | datetime | — |

### `fx.disclosure.search(...)`

**提供什么数据**
搜索个股公告并返回公告引用。

**数据源**
`eastmoney.disclosure`

**调用方式**

```python
fx.disclosure.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, categories: 'Sequence[str] | None' = None, sort: 'str' = 'published_desc', request: 'DisclosureSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[DisclosureDocumentRef, ...]]'
```

**示例**

<!-- api-example: disclosure.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.disclosure.search("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | 无 request 时必填 | None | InstrumentId 或六位 A 股代码。 |
| page | int | 可选 | 1 | 从 1 开始的页码。 |
| page_size | int | 可选 | 20 | 单页数量。 |
| max_results | int \| None | 可选 | None | 可选的结果上限。 |
| since | date \| datetime \| None | 可选 | None | 可选的时间范围起点。 |
| until | date \| datetime \| None | 可选 | None | 可选的时间范围终点。 |
| categories | Sequence[str] \| None | 可选 | None | 可选的公告分类列表。 |
| sort | str | 可选 | 'published_desc' | published_desc 或 published_asc。 |
| request | DisclosureSearchRequest \| None | 便捷参数的替代 | None | 完整的类型化 request 模型。 |

**输出字段**

数据模型：`DisclosureDocumentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| documentId | str | — |
| sourceDocumentId | str | — |
| title | str | — |
| contentText | str \| None | — |
| noticeDate | date | — |
| publishedAt | datetime \| None | — |
| sourceRecordedAt | datetime \| None | — |
| categories | list[DisclosureCategory] | — |
| relatedInstruments | list[InstrumentId] | — |
| contentAvailable | bool | — |
| pdfAvailable | bool | — |
| originalDocumentUrl | AnyUrl | — |
| attachments | list[DisclosureAttachment] | — |
| sourceType | str \| None | — |

嵌套业务模型： `DisclosureCategory`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| code | str | — |
| name | str | 名称。 |
| source | str | — |

嵌套业务模型： `DisclosureAttachment`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| sequence | int \| None | — |
| size | int \| None | — |
| attachmentType | str \| None | — |
| url | AnyUrl | — |
| webUrl | AnyUrl \| None | — |

## 4.6 股东、管理层与公司行动

### `fx.ownership.capital_snapshot(...)`

**提供什么数据**
获取股本快照。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.ownership.capital_snapshot(request: 'CapitalSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CapitalSnapshotData]'
```

**示例**

<!-- api-example: ownership.capital_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.capital_snapshot("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | CapitalSnapshotRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `CapitalSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`CapitalSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| totalShares | int \| None | — |
| floatShares | int \| None | — |

### `fx.ownership.float_holder(...)`

**提供什么数据**
获取流通股东数据。

**数据源**
`tencent.finance.qq.float_holder`

**调用方式**

```python
fx.ownership.float_holder(request: 'FloatHolderRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FloatHolderData]'
```

**示例**

<!-- api-example: ownership.float_holder -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.float_holder("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | FloatHolderRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `FloatHolderRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |
| asOf (`as_of`) | datetime \| None | 可选 | None | — |

**输出字段**

数据模型：`FloatHolderData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| periods | list[FloatHolderPeriod] | — |

嵌套业务模型： `FloatHolderPeriod`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| periodEnd | date | — |
| publishedAt | datetime | — |
| rows | list[FloatHolderRow] | — |

嵌套业务模型： `FloatHolderRow`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| rank | int | 根据 Tencent rows 数组顺序推导。 |
| holderId | str \| None | — |
| holderName | str | — |
| shares | int | 非负整数股数。 |
| holderType | str | — |
| floatShareRatio | Decimal \| None | — |
| previousShares | int \| None | — |
| shareChange | int \| None | — |
| isNewTopFloatHolderEntry | bool \| None | 根据多股票相邻期间校验后的 bdms=1 推导。 |

### `fx.ownership.holder_summary_snapshot(...)`

**提供什么数据**
获取股东汇总快照。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.ownership.holder_summary_snapshot(request: 'HolderSummarySnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[HolderSummarySnapshotData]'
```

**示例**

<!-- api-example: ownership.holder_summary_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.holder_summary_snapshot("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | HolderSummarySnapshotRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `HolderSummarySnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`HolderSummarySnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| shareholderCount | int \| None | — |
| averageSharesPerHolder | Decimal \| None | 每位持有人的精确股数；Tencent rjcg 展示单位已换算为股。 |
| shareholderCountChange | Decimal \| None | Tencent gdrshb 已从百分点规范化为比例；不是绝对数量差。 |
| top10FloatHolderRatio | Decimal \| None | — |
| top10HolderRatio | Decimal \| None | — |

### `fx.company.executive_share_change(...)`

**提供什么数据**
获取高管持股变动。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.company.executive_share_change(request: 'ExecutiveShareChangeRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveShareChangeData]'
```

**示例**

<!-- api-example: company.executive_share_change -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_share_change("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | ExecutiveShareChangeRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `ExecutiveShareChangeRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`ExecutiveShareChangeData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| changes | list[ExecutiveShareChange] | — |

嵌套业务模型： `ExecutiveShareChange`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| eventDate | date \| None | — |
| personName | str \| None | — |
| shareChange | int \| None | — |
| averagePrice | Decimal \| None | — |

### `fx.company.executive_snapshot(...)`

**提供什么数据**
获取高管快照。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.company.executive_snapshot(request: 'ExecutiveSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveSnapshotData]'
```

**示例**

<!-- api-example: company.executive_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_snapshot("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | ExecutiveSnapshotRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `ExecutiveSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`ExecutiveSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| executives | list[ExecutiveEntry] | — |

嵌套业务模型： `ExecutiveEntry`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| name | str | 名称。 |
| roles | list[str] | — |
| shares | int \| None | — |
| compensation | Decimal \| None | — |

### `fx.corporate_action.dividend(...)`

**提供什么数据**
获取分红除权记录。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.corporate_action.dividend(request: 'DividendRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DividendData]'
```

**示例**

<!-- api-example: corporate_action.dividend -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.dividend("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | DividendRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `DividendRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`DividendData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| dividends | list[Dividend] | — |

嵌套业务模型： `Dividend`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| fiscalYear | int \| None | — |
| announcementDate | date \| None | — |
| stockDividendPer10 | Decimal \| None | — |
| capitalizationPer10 | Decimal \| None | — |
| cashDividendPer10 | Decimal \| None | — |
| rightsIssuePer10 | Decimal \| None | — |
| recordDate | date \| None | — |
| exDate | date \| None | — |
| description | str \| None | — |

### `fx.corporate_action.repurchase(...)`

**提供什么数据**
获取回购记录。

**数据源**
`tencent.finance.qq.f10`

**调用方式**

```python
fx.corporate_action.repurchase(request: 'RepurchaseRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RepurchaseData]'
```

**示例**

<!-- api-example: corporate_action.repurchase -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.repurchase("600519")
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| request | RepurchaseRequest \| InstrumentInput | 必填 | — | 完整的类型化 request 模型。 |

**Request 字段** — `RepurchaseRequest`

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | 必填 | — | 证券标识。 |

**输出字段**

数据模型：`RepurchaseData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | — |
| repurchases | list[Repurchase] | — |

嵌套业务模型： `Repurchase`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| repurchaseDate | date \| None | — |
| quantity | int \| None | — |
| averagePrice | Decimal \| None | — |
| currency | Currency \| None | — |
| fundAmount | Decimal \| None | — |
| market | str \| None | — |

## 4.7 计算型分析

### `fx.market.deviation(...)`

**提供什么数据**
计算经过审计的基于收盘价的偏离值。

**数据源**
由 `market.ohlcv` 和 `reference.trading_calendar` 在本地计算；无直接 Provider。

**调用方式**

```python
fx.market.deviation(instrument_id: 'InstrumentInput', *, windows: 'Sequence[int]' = (10, 30), as_of: 'date | None' = None, window_convention: 'DeviationWindowConvention' = <DeviationWindowConvention.MAX_DEVIATION_SCAN: 'max_deviation_scan'>, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DeviationData]'
```

**示例**

<!-- api-example: market.deviation -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.deviation("600519", windows=(10, 30))
```

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput | 必填 | — | InstrumentId 或六位 A 股代码。 |
| windows | Sequence[int] | 可选 | (10, 30) | 以交易时段计的偏离窗口。 |
| as_of | date \| None | 可选 | None | 可选的已完成交易时段日期。 |
| window_convention | DeviationWindowConvention | 可选 | DeviationWindowConvention.MAX_DEVIATION_SCAN | 偏离窗口解释方式。 |

**输出字段**

数据模型：`DeviationData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | InstrumentId | 证券标识。 |
| board | str | — |
| effectiveAsOf | date | — |
| calculationMode | Literal['official_close'] | — |
| priceBasis | Literal['qfq_stock__raw_index'] | — |
| ruleVersion | str | — |
| windows | tuple[DeviationWindowData, Ellipsis] | — |

嵌套业务模型： `DeviationWindowData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| windowDays | Literal[10, 30] | — |
| windowConvention | DeviationWindowConvention | — |
| tradingSessions | int | — |
| startDate | date | — |
| baselineDate | date | — |
| endDate | date | — |
| startPrice | Decimal | — |
| windowStartPrice | Decimal | — |
| currentPrice | Decimal | — |
| benchmarkInstrument | InstrumentId | — |
| benchmarkName | str | — |
| benchmarkStart | Decimal | — |
| benchmarkCurrent | Decimal | — |
| stockReturn | Decimal | — |
| benchmarkReturn | Decimal | — |
| deviation | Decimal | — |
| upperThreshold | Decimal | — |
| lowerThreshold | Decimal | — |
| remainingToUpper | Decimal | — |
| remainingToLower | Decimal | — |
| upperTriggerPrice | Decimal | — |
| lowerTriggerPrice | Decimal | — |
| remainingPricePctToUpper | Decimal | — |
| remainingPricePctToLower | Decimal | — |

## 5. 通用说明

### 证券输入规则

- `6xxxxx` 自动识别为 SSE 股票。
- `0xxxxx` 和 `3xxxxx` 自动识别为 SZSE 股票。
- 以 `4`、`8` 或 `9` 开头的裸代码不会自动猜测；请显式传入 `InstrumentId`。
- 指数和其他有歧义的标的必须显式传入 `InstrumentId`。

### 公共参数

| 参数 | 说明 |
| --- | --- |
| `provider` | 可选。显式指定 Provider；失败不会静默切换。 |
| `use_cache` | 可选。控制是否使用配置的缓存策略；`None` 使用默认配置。 |

### Provider 与 warnings

可用 `provider=` 显式指定 Provider。`result.warnings` 用于记录可恢复的数据质量或兼容性问题，例如跳过存在 schema drift 的单条 News 记录。

### 最新快照股票池

`limit_up_pool`、`limit_down_pool`、`broken_limit_pool`、`strong_pool` 和 `yesterday_limit_up_pool` 只返回最新快照，不支持历史日期查询。

**弃用兼容：** 旧请求模型可能仍保留可选 `tradeDate` 字段；当前 Client 会拒绝历史日期选择。新代码不要使用它。

文档由实时的 `CLIENT_ENDPOINTS`、Dataset 模型、Provider Registry 和计算能力 metadata 生成。
