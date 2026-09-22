# FinchX 数据与 API 参考

[English](DATA_API_REFERENCE.md) | 简体中文

本文档根据 1.0.0 公开 Client、Dataset 定义、Pydantic 请求/数据模型和 Provider Registry 生成，覆盖 42 个 Provider / Dataset 公开接口以及 1 个计算型能力（共 43 个能力）。

## 通用规则

下方签名直接来自公开 Client。请求字段的“必填/可选”来自 Pydantic 的 `model_fields`；当签名不足以表达便捷模式或跨字段约束时，文档会单独说明。两个语言版本使用同一份结构化示例定义。

| 规则 | 含义 |
| --- | --- |
| `provider` | 严格指定 Provider id；失败时不会静默切换。 |
| `use_cache` | None 遵循已配置的 CachePolicy；构造 FinchX 不会创建存储。 |
| 请求模型 | 部分方法同时提供便捷调用和类型化请求替代；合法组合以 Client 和 Pydantic 校验为准。 |
| InstrumentId | 接口需要时使用包含 code、market、kind 和 exchange 的完整身份。 |

## 接口索引

该索引由 `CLIENT_ENDPOINTS` 以及计算型 `market.deviation` 能力生成。

| Namespace | 方法 | Dataset | 已实现 Provider | 最小业务输入 |
| --- | --- | --- | --- | --- |
| reference | instrument | instrument | tencent.finance.qq.market | instrument_id 或 request |
| reference | trading_calendar | trading_calendar | szse.official.calendar, pandas_market_calendars | 同时提供 start_date 和 end_date，或使用 request |
| market | breadth | market.breadth | eastmoney.push2ex.breadth | 无 |
| market | broken_limit_pool | market.broken_limit_pool | eastmoney.push2ex.broken_limit_pool | request |
| market | consecutive_limit_up | market.consecutive_limit_up_snapshot | aigupiao.series_limit_up | 无 |
| market | daily_replay | market.daily_replay | jiuyangongshe.daily_replay | request |
| market | dragon_tiger_detail | market.dragon_tiger_detail | aigupiao.dragon_tiger | request（包含 instrumentId、tradeDate 和 tradeId） |
| market | dragon_tiger_list | market.dragon_tiger_list | aigupiao.dragon_tiger | request |
| market | equity_intraday | market.equity_intraday | tencent.finance.qq.intraday | request（包含股票 instrumentId） |
| market | equity_intraday_5d | market.equity_intraday_5d | tencent.finance.qq.intraday | request（包含股票 instrumentId） |
| market | fund_flow_daily | market.fund_flow_daily | tencent.finance.qq.fund_flow | request（包含 instrumentId） |
| market | fund_flow_intraday | market.fund_flow_intraday | tencent.finance.qq.fund_flow | request（包含 instrumentId） |
| market | fund_flow_snapshot | market.fund_flow_snapshot | tencent.finance.qq.fund_flow | request（包含 instrumentId） |
| market | index_intraday | market.index_intraday | tencent.finance.qq.intraday | request（包含指数 instrumentId） |
| market | index_intraday_5d | market.index_intraday_5d | tencent.finance.qq.intraday | request（包含指数 instrumentId） |
| market | industry_comparison | market.industry_comparison | tencent.finance.qq.industry | request（包含 instrumentId） |
| market | instrument_sector_snapshot | market.instrument_sector_snapshot | tencent.finance.qq.sector | request（包含 instrumentId） |
| market | stock_keyword | market.stock_keyword | eastmoney.stockrank | request（包含 instrumentId） |
| market | limit_down_pool | market.limit_down_pool | eastmoney.push2ex.limit_down_pool | request |
| market | limit_up_pool | market.limit_up_pool | eastmoney.push2ex.limit_up_pool | request |
| market | ohlcv | market.klines | tencent.finance.qq.klines, sohu.finance.klines | 股票需提供 instrument_id、start_date、end_date 和 adjustment |
| market | orderbook | market.orderbook | tencent.finance.qq.quote | request（包含 instrumentId） |
| market | quote | market.quote | tencent.finance.qq.market | 无；默认范围为 CN_A_SHARE |
| market | quote_snapshot | market.quote_snapshot | tencent.finance.qq.quote | request（包含 instrumentId） |
| market | ranking | market.ranking | tencent.finance.qq.market | request（包含 universe、criterion、direction 和 limit） |
| market | sentiment | market.sentiment_snapshot | aigupiao.market_sentiment | 无 |
| market | strong_pool | market.strong_pool | eastmoney.push2ex.strong_pool | request |
| market | yesterday_limit_up_pool | market.yesterday_limit_up_pool | eastmoney.push2ex.yesterday_limit_up_pool | request |
| fundamental | company_profile | fundamental.company_profile | tencent.finance.qq.f10 | instrument_id 或 request |
| fundamental | financial_summary | fundamental.financial_summary | tencent.finance.qq.f10 | request（包含 instrumentId） |
| fundamental | industry_comparison | fundamental.industry_comparison | tencent.finance.qq.f10 | request（包含 instrumentId） |
| fundamental | revenue_breakdown | fundamental.revenue_breakdown | tencent.finance.qq.f10 | request（包含 instrumentId） |
| financial | statements | financial.statement | tonghuashun.financial | instrument_id 和 statement_type，或使用 request |
| news | search | news.document | eastmoney.news, eastmoney.market_news, aigupiao.market_news, baidu.finscope.market_news | instrument（InstrumentId 或六位股票代码），或使用 request |
| disclosure | search | disclosure.document | eastmoney.disclosure | instrument（InstrumentId 或六位股票代码），或使用 request |
| ownership | capital_snapshot | ownership.capital_snapshot | tencent.finance.qq.f10 | request（包含 instrumentId） |
| ownership | float_holder | ownership.float_holder | tencent.finance.qq.float_holder | request（包含 instrumentId；asOf 可选） |
| ownership | holder_summary_snapshot | ownership.holder_summary_snapshot | tencent.finance.qq.f10 | request（包含 instrumentId） |
| company | executive_share_change | company.executive_share_change | tencent.finance.qq.f10 | request（包含 instrumentId） |
| company | executive_snapshot | company.executive_snapshot | tencent.finance.qq.f10 | request（包含 instrumentId） |
| corporate_action | dividend | corporate_action.dividend | tencent.finance.qq.f10 | request（包含 instrumentId） |
| corporate_action | repurchase | corporate_action.repurchase | tencent.finance.qq.f10 | request（包含 instrumentId） |
| market | deviation | market.deviation (computed) | — | instrument_id |

## 接口参考

## `reference`

### `fx.reference.instrument(...)`

获取标的规范身份和名称。

**Dataset：** `instrument`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.reference.instrument(instrument_id: 'InstrumentId | None' = None, *, request: 'InstrumentRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[InstrumentData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 便捷模式必填 | None | 完整的 InstrumentId。 |
| request | InstrumentRequest \| None | 条件性 request 替代 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** instrument_id 或 request。

#### 请求模型 `InstrumentRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[InstrumentData]`。

#### 返回数据模型 `InstrumentData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: reference.instrument -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = fx.reference.instrument(instrument_id)
```

### `fx.reference.trading_calendar(...)`

获取日期范围内的 A 股交易日标记。

**Dataset：** `trading_calendar`
**Schema 版本：** `1.0`
**已实现 Provider：** `szse.official.calendar`, `pandas_market_calendars`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.reference.trading_calendar(start_date: 'date | None' = None, end_date: 'date | None' = None, *, market: 'Market' = <Market.CN_A: 'cn_a'>, request: 'TradingCalendarRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[TradingCalendarData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| start_date | date \| None | 便捷模式必填 | None | 包含在内的开始日期。 |
| end_date | date \| None | 便捷模式必填 | None | 包含在内的结束日期。 |
| market | Market | 否 | Market.CN_A | Market 枚举；trading_calendar 当前仅支持 Market.CN_A。 |
| request | TradingCalendarRequest \| None | 条件性 request 替代 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** 同时提供 start_date 和 end_date，或使用 request。

#### 请求模型 `TradingCalendarRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| startDate | date | 是 | — | 由 Pydantic 模型定义。 |
| endDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[TradingCalendarData]`。

#### 返回数据模型 `TradingCalendarData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| date | date | 是 | — | 由 Pydantic 模型定义。 |
| isTradingDay | bool | 是 | — | 由 Pydantic 模型定义。 |

#### 示例

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

## `market`

### `fx.market.breadth(...)`

获取当前市场涨跌家数分布。

**Dataset：** `market.breadth`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.push2ex.breadth`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.breadth(request: 'MarketBreadthRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBreadthData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketBreadthRequest \| None | 否 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** 无。

#### 请求模型 `MarketBreadthRequest`

无字段；直接无参实例化该模型。

公开返回标注为 `FetchResult[MarketBreadthData]`。

#### 返回数据模型 `MarketBreadthData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | EastMoney 报告的交易日期。 |
| advancing | int | 是 | — | 由 Pydantic 模型定义。 |
| declining | int | 是 | — | 由 Pydantic 模型定义。 |
| unchanged | int | 是 | — | 由 Pydantic 模型定义。 |
| total | int | 是 | — | 由 Pydantic 模型定义。 |
| limitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |
| limitDownCount | int | 是 | — | 由 Pydantic 模型定义。 |
| upOver10PercentCount | int | 是 | — | 由 Pydantic 模型定义。 |
| downOver10PercentCount | int | 是 | — | 由 Pydantic 模型定义。 |
| distribution | list[MarketBreadthDistributionEntry] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `MarketBreadthDistributionEntry`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| bucket | MarketBreadthBucket | 是 | — | 由 Pydantic 模型定义。 |
| count | int | 是 | — | 该返回区间内的上市股票数量。 |

#### 示例

<!-- api-example: market.breadth -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.breadth()
```

### `fx.market.broken_limit_pool(...)`

获取炸板池数据。

**Dataset：** `market.broken_limit_pool`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.push2ex.broken_limit_pool`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.broken_limit_pool(request: 'MarketBrokenLimitPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBrokenLimitPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketBrokenLimitPoolRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request。

#### 请求模型 `MarketBrokenLimitPoolRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketBrokenLimitPoolData]`。

#### 返回数据模型 `MarketBrokenLimitPoolData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 最新价格，单位为每股 CNY。 |
| limitUpPrice | Decimal | 是 | — | 当前交易日涨停价，单位为每股 CNY。 |
| changeRate | Decimal | 是 | — | 比例小数。 |
| amount | Decimal | 是 | — | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| turnoverRate | Decimal | 是 | — | 比例小数。 |
| amplitude | Decimal | 是 | — | 当前交易日振幅比例小数。 |
| firstLimitUpTime | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| limitUpBreakCount | int | 是 | — | 由 Pydantic 模型定义。 |
| industry | str | 是 | — | 由 Pydantic 模型定义。 |
| limitUpStats | MarketBrokenLimitPoolStats | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `MarketBrokenLimitPoolStats`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | 是 | — | 由 Pydantic 模型定义。 |
| limitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.broken_limit_pool -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketBrokenLimitPoolRequest

fx = FinchX()
request = MarketBrokenLimitPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.broken_limit_pool(request)
```

### `fx.market.consecutive_limit_up(...)`

获取连板股快照。

**Dataset：** `market.consecutive_limit_up_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `aigupiao.series_limit_up`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.consecutive_limit_up(request: 'MarketConsecutiveLimitUpRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketConsecutiveLimitUpData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketConsecutiveLimitUpRequest \| None | 否 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** 无。

#### 请求模型 `MarketConsecutiveLimitUpRequest`

无字段；直接无参实例化该模型。

公开返回标注为 `FetchResult[MarketConsecutiveLimitUpData]`。

#### 返回数据模型 `MarketConsecutiveLimitUpData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| lastPrice | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| change | Decimal | 是 | — | 带符号的价格变动，单位为每股 CNY。 |
| changeRatio | Decimal | 是 | — | 比例小数；10% 表示为 0.10。 |
| turnoverRatio | Decimal | 是 | — | 比例小数；12% 表示为 0.12。 |
| amount | Decimal | 是 | — | 金额，单位为 CNY。 |
| limitUpTime | str | 是 | — | 由 Pydantic 模型定义。 |
| state | str | 是 | — | 由 Pydantic 模型定义。 |
| isConsecutiveLimitUp | bool | 是 | — | 由 Pydantic 模型定义。 |
| consecutiveLimitUpCount | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| previousConsecutiveLimitUpCount | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| themeId | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| themeName | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| floatShares | int | 是 | — | 非负整数股数。 |
| totalShares | int | 是 | — | 非负整数股数。 |
| marketCap | Decimal | 是 | — | 总市值，单位为 CNY。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.consecutive_limit_up -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.consecutive_limit_up()
```

### `fx.market.daily_replay(...)`

获取指定日期的每日复盘数据。

**Dataset：** `market.daily_replay`
**Schema 版本：** `1.0`
**已实现 Provider：** `jiuyangongshe.daily_replay`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.daily_replay(request: 'MarketDailyReplayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDailyReplayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDailyReplayRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request。

#### 请求模型 `MarketDailyReplayRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| requestedDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketDailyReplayData]`。

#### 返回数据模型 `MarketDailyReplayData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| requestedDate | date | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| themes | list[ReplayTheme] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `ReplayTheme`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| themeName | str | 是 | — | 由 Pydantic 模型定义。 |
| reason | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| stockCount | int | 是 | — | 由 Pydantic 模型定义。 |
| sourceThemeId | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| stocks | list[ReplayStock] | 否 | default_factory=list | 由 Pydantic 模型定义。 |

#### 嵌套模型 `ReplayStock`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| limitUpTime | time \| None | 否 | None | 由 Pydantic 模型定义。 |
| streakText | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| price | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| changeRatio | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| day | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| edition | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| expound | str \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.daily_replay -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketDailyReplayRequest

fx = FinchX()
request = MarketDailyReplayRequest(requestedDate=date(2026, 9, 18))
result = fx.market.daily_replay(request)
```

### `fx.market.dragon_tiger_detail(...)`

获取指定标的的龙虎榜明细。

**Dataset：** `market.dragon_tiger_detail`
**Schema 版本：** `1.0`
**已实现 Provider：** `aigupiao.dragon_tiger`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.dragon_tiger_detail(request: 'MarketDragonTigerDetailRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerDetailData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerDetailRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId、tradeDate 和 tradeId）。

#### 请求模型 `MarketDragonTigerDetailRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| tradeId | str | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketDragonTigerDetailData]`。

#### 返回数据模型 `MarketDragonTigerDetailData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| tradeId | str | 是 | — | 由 Pydantic 模型定义。 |
| closePrice | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| changeRatio | Decimal | 是 | — | 比例小数，而不是百分点：4.24% 表示为 0.0424。 |
| amount | Decimal | 是 | — | 金额，单位为 CNY。 |
| totalBuy | Decimal | 是 | — | 金额，单位为 CNY。 |
| totalSell | Decimal | 是 | — | 金额，单位为 CNY。 |
| totalNet | Decimal | 是 | — | 金额，单位为 CNY。 |
| explanation | str | 是 | — | 由 Pydantic 模型定义。 |
| commentKind | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| commentObjectId | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| buySeats | list[DragonTigerSeat] | 是 | — | 由 Pydantic 模型定义。 |
| sellSeats | list[DragonTigerSeat] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `DragonTigerSeat`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| rank | int | 是 | — | 根据来源数组顺序推导。 |
| seatName | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceSeatCode | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| hasDetails | bool \| None | 否 | None | 由 Pydantic 模型定义。 |
| buyAmount | Decimal | 是 | — | 金额，单位为 CNY。 |
| sellAmount | Decimal | 是 | — | 金额，单位为 CNY。 |
| netAmount | Decimal | 是 | — | 金额，单位为 CNY。 |

#### 示例

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

### `fx.market.dragon_tiger_list(...)`

获取指定交易日的龙虎榜列表。

**Dataset：** `market.dragon_tiger_list`
**Schema 版本：** `1.0`
**已实现 Provider：** `aigupiao.dragon_tiger`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.dragon_tiger_list(request: 'MarketDragonTigerListRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerListData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerListRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request。

#### 请求模型 `MarketDragonTigerListRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketDragonTigerListData]`。

#### 返回数据模型 `MarketDragonTigerListData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| tradeId | str | 是 | — | 由 Pydantic 模型定义。 |
| closePrice | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| changeRatio | Decimal | 是 | — | 比例小数；10% 表示为 0.10。 |
| amount | Decimal | 是 | — | 金额，单位为 CNY。 |
| totalBuy | Decimal | 是 | — | 金额，单位为 CNY。 |
| totalNet | Decimal | 是 | — | 金额，单位为 CNY。 |
| explanation | str | 是 | — | 由 Pydantic 模型定义。 |
| threeDayFlag | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| themeId | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| themeName | str \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.dragon_tiger_list -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketDragonTigerListRequest

fx = FinchX()
request = MarketDragonTigerListRequest(tradeDate=date(2026, 9, 18))
result = fx.market.dragon_tiger_list(request)
```

### `fx.market.equity_intraday(...)`

获取单个股票交易日内分钟数据。

**Dataset：** `market.equity_intraday`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.equity_intraday(request: 'EquityIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | EquityIntradayRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含股票 instrumentId）。

#### 请求模型 `EquityIntradayRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[EquityIntradayData]`。

#### 返回数据模型 `EquityIntradayData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 是 | — | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 是 | — | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 是 | — | 该分钟成交量，单位为整股。 |
| amount | Decimal | 是 | — | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | 是 | — | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | 是 | — | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.equity_intraday -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import EquityIntradayRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = EquityIntradayRequest(instrumentId=instrument_id)
result = fx.market.equity_intraday(request)
```

### `fx.market.equity_intraday_5d(...)`

获取股票五日分钟数据。

**Dataset：** `market.equity_intraday_5d`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.equity_intraday_5d(request: 'EquityIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | EquityIntraday5dRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含股票 instrumentId）。

#### 请求模型 `EquityIntraday5dRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[EquityIntradayData]`。

#### 返回数据模型 `EquityIntradayData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 是 | — | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 是 | — | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 是 | — | 该分钟成交量，单位为整股。 |
| amount | Decimal | 是 | — | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | 是 | — | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | 是 | — | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.equity_intraday_5d -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import EquityIntraday5dRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = EquityIntraday5dRequest(instrumentId=instrument_id)
result = fx.market.equity_intraday_5d(request)
```

### `fx.market.fund_flow_daily(...)`

获取单个标的的每日资金流数据。

**Dataset：** `market.fund_flow_daily`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.fund_flow_daily(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowDailyData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketFundFlowRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketFundFlowDailyData]`。

#### 返回数据模型 `MarketFundFlowDailyData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | Tencent 报告的交易日期，不是 FinchX 抓取时间。 |
| mainNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| close | Decimal | 是 | — | 每日收盘价，单位为每股 CNY。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.fund_flow_daily -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketFundFlowRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketFundFlowRequest(instrumentId=instrument_id)
result = fx.market.fund_flow_daily(request)
```

### `fx.market.fund_flow_intraday(...)`

获取单个标的的盘中资金流数据。

**Dataset：** `market.fund_flow_intraday`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.fund_flow_intraday(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketFundFlowRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketFundFlowIntradayData]`。

#### 返回数据模型 `MarketFundFlowIntradayData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | Tencent 报告的交易日期，不是 FinchX 抓取时间。 |
| time | str | 是 | — | 来源市场本地时间，格式为 HH:MM；数值从开盘起累计。 |
| price | Decimal | 是 | — | 来源价格，单位为每股 CNY。 |
| cumulativeMainNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| cumulativeRetailNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| cumulativeSuperLargeNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| cumulativeLargeNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| cumulativeMediumNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| cumulativeSmallNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| cumulativeMainInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| cumulativeMainOutflow | Decimal | 是 | — | 金额，单位为 CNY。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.fund_flow_intraday -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketFundFlowRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketFundFlowRequest(instrumentId=instrument_id)
result = fx.market.fund_flow_intraday(request)
```

### `fx.market.fund_flow_snapshot(...)`

获取资金流快照。

**Dataset：** `market.fund_flow_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.fund_flow_snapshot(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketFundFlowRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketFundFlowSnapshotData]`。

#### 返回数据模型 `MarketFundFlowSnapshotData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | Tencent 报告的交易日期，不是 FinchX 抓取时间。 |
| mainNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| mainInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| mainOutflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| mainInflowRate | Decimal | 是 | — | 比例小数；15% 表示为 0.15。 |
| mainOutflowRate | Decimal | 是 | — | 比例小数；19% 表示为 0.19。 |
| retailInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| retailOutflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| retailInflowRate | Decimal | 是 | — | 比例小数；35% 表示为 0.35。 |
| retailOutflowRate | Decimal | 是 | — | 比例小数；31% 表示为 0.31。 |
| superLargeNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| largeNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| mediumNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |
| smallNetInflow | Decimal | 是 | — | 金额，单位为 CNY。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.fund_flow_snapshot -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketFundFlowRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketFundFlowRequest(instrumentId=instrument_id)
result = fx.market.fund_flow_snapshot(request)
```

### `fx.market.index_intraday(...)`

获取单个指数交易日内分钟数据。

**Dataset：** `market.index_intraday`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.index_intraday(request: 'IndexIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | IndexIntradayRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含指数 instrumentId）。

#### 请求模型 `IndexIntradayRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[IndexIntradayData]`。

#### 返回数据模型 `IndexIntradayData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 是 | — | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 是 | — | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 是 | — | 该分钟成交量，单位为整股。 |
| amount | Decimal | 是 | — | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | 是 | — | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | 是 | — | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

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

### `fx.market.index_intraday_5d(...)`

获取指数五日分钟数据。

**Dataset：** `market.index_intraday_5d`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.index_intraday_5d(request: 'IndexIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | IndexIntraday5dRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含指数 instrumentId）。

#### 请求模型 `IndexIntraday5dRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[IndexIntradayData]`。

#### 返回数据模型 `IndexIntradayData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 是 | — | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 是 | — | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 是 | — | 该分钟成交量，单位为整股。 |
| amount | Decimal | 是 | — | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | 是 | — | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | 是 | — | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

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

### `fx.market.industry_comparison(...)`

获取市场行业比较数据。

**Dataset：** `market.industry_comparison`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.industry`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.industry_comparison(request: 'MarketIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketIndustryComparisonData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketIndustryComparisonRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketIndustryComparisonRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketIndustryComparisonData]`。

#### 返回数据模型 `MarketIndustryComparisonData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| industry | IndustryIdentity | 是 | — | 由 Pydantic 模型定义。 |
| instrumentValues | IndustryComparisonValues | 是 | — | 由 Pydantic 模型定义。 |
| industryRanks | IndustryComparisonRanks | 是 | — | 由 Pydantic 模型定义。 |
| industryAggregate | IndustryAggregate | 是 | — | 由 Pydantic 模型定义。 |
| marketAggregate | MarketAggregate | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `IndustryIdentity`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| providerNamespace | Literal['tencent_hypm'] | 是 | — | 由 Pydantic 模型定义。 |
| providerIndustryId | str | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `IndustryComparisonValues`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| earningsPerShare | Decimal \| None | 否 | None | Tencent mgsy，单位为每股 CNY；此处未提供报告期语义。 |
| marketCapitalization | Decimal \| None | 否 | None | Tencent zsz 已从亿元转换为 CNY。 |

#### 嵌套模型 `IndustryComparisonRanks`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarningsRank | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| earningsPerShareRank | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| marketCapitalizationRank | int \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `IndustryAggregate`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| earningsPerShare | Decimal \| None | 否 | None | Tencent mgsy，单位为每股 CNY；此处未提供报告期语义。 |
| marketCapitalization | Decimal \| None | 否 | None | Tencent zsz 已从亿元转换为 CNY。 |
| count | int \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `MarketAggregate`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| earningsPerShare | Decimal \| None | 否 | None | Tencent mgsy，单位为每股 CNY；此处未提供报告期语义。 |
| marketCapitalization | Decimal \| None | 否 | None | Tencent zsz 已从亿元转换为 CNY。 |

#### 示例

<!-- api-example: market.industry_comparison -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketIndustryComparisonRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketIndustryComparisonRequest(instrumentId=instrument_id)
result = fx.market.industry_comparison(request)
```

### `fx.market.instrument_sector_snapshot(...)`

获取标的所属板块及板块快照。

**Dataset：** `market.instrument_sector_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.sector`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.instrument_sector_snapshot(request: 'MarketInstrumentSectorSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketInstrumentSectorSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketInstrumentSectorSnapshotRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketInstrumentSectorSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketInstrumentSectorSnapshotData]`。

#### 返回数据模型 `MarketInstrumentSectorSnapshotData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| sectors | list[InstrumentSectorEntry] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentSectorEntry`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | 是 | — | 由 Pydantic 模型定义。 |
| sectorName | str | 是 | — | 由 Pydantic 模型定义。 |
| providerNamespace | Literal['tencent_plate'] | 是 | — | 由 Pydantic 模型定义。 |
| providerSectorId | str | 是 | — | 由 Pydantic 模型定义。 |
| level | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| tag | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| changePct | Decimal \| None | 否 | None | Tencent zdf 已从百分点转换为比例小数。 |

#### 示例

<!-- api-example: market.instrument_sector_snapshot -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketInstrumentSectorSnapshotRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketInstrumentSectorSnapshotRequest(instrumentId=instrument_id)
result = fx.market.instrument_sector_snapshot(request)
```

### `fx.market.stock_keyword(...)`

获取数据源提供的股票关键词。

**Dataset：** `market.stock_keyword`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.stockrank`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.stock_keyword(request: 'MarketStockKeywordRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStockKeywordData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketStockKeywordRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketStockKeywordRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketStockKeywordData]`。

#### 返回数据模型 `MarketStockKeywordData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| keywords | list[StockKeywordEntry] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `StockKeywordEntry`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| keywordName | str | 是 | — | 由 Pydantic 模型定义。 |
| providerNamespace | Literal['eastmoney_stockrank'] | 是 | — | 由 Pydantic 模型定义。 |
| providerKeywordId | str | 是 | — | 由 Pydantic 模型定义。 |
| hitCount | int | 是 | — | 由 Pydantic 模型定义。 |
| calculatedAt | datetime | 是 | — | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.stock_keyword -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketStockKeywordRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketStockKeywordRequest(instrumentId=instrument_id)
result = fx.market.stock_keyword(request)
```

### `fx.market.limit_down_pool(...)`

获取指定交易日的跌停池。

**Dataset：** `market.limit_down_pool`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.push2ex.limit_down_pool`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.limit_down_pool(request: 'MarketLimitDownPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitDownPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketLimitDownPoolRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request。

#### 请求模型 `MarketLimitDownPoolRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketLimitDownPoolData]`。

#### 返回数据模型 `MarketLimitDownPoolData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 最新价格，单位为每股 CNY。 |
| changeRate | Decimal | 是 | — | 比例小数；-10% 表示为 -0.10。 |
| amount | Decimal | 是 | — | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| priceEarningsRatio | Decimal \| None | 否 | None | EastMoney 报告的动态 P/E；来源计算细节未提供。 |
| turnoverRate | Decimal | 是 | — | 比例小数。 |
| limitDownQueueAmount | Decimal \| None | 否 | None | EastMoney 报告的跌停排队金额，单位为 CNY。 |
| lastLimitDownTime | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| boardTradedAmount | Decimal \| None | 否 | None | 以跌停价成交的金额，单位为 CNY。 |
| consecutiveLimitDownDays | int | 是 | — | 由 Pydantic 模型定义。 |
| limitDownOpenCount | int | 是 | — | 由 Pydantic 模型定义。 |
| industry | str | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.limit_down_pool -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketLimitDownPoolRequest

fx = FinchX()
request = MarketLimitDownPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.limit_down_pool(request)
```

### `fx.market.limit_up_pool(...)`

获取指定交易日的涨停池。

**Dataset：** `market.limit_up_pool`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.push2ex.limit_up_pool`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.limit_up_pool(request: 'MarketLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitUpPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketLimitUpPoolRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request。

#### 请求模型 `MarketLimitUpPoolRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketLimitUpPoolData]`。

#### 返回数据模型 `MarketLimitUpPoolData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 最新价格，单位为每股 CNY。 |
| changeRate | Decimal | 是 | — | 比例小数；10% 表示为 0.10。 |
| amount | Decimal | 是 | — | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| turnoverRate | Decimal | 是 | — | 比例小数；5% 表示为 0.05。 |
| consecutiveLimitUpDays | int | 是 | — | 由 Pydantic 模型定义。 |
| firstLimitUpTime | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| lastLimitUpTime | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| limitUpQueueAmount | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| limitUpBreakCount | int | 是 | — | 由 Pydantic 模型定义。 |
| industry | str | 是 | — | 由 Pydantic 模型定义。 |
| limitUpStats | MarketLimitUpStats | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `MarketLimitUpStats`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | 是 | — | 由 Pydantic 模型定义。 |
| limitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.limit_up_pool -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketLimitUpPoolRequest

fx = FinchX()
request = MarketLimitUpPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.limit_up_pool(request)
```

### `fx.market.ohlcv(...)`

获取单个标的的日线 OHLCV 数据。

**Dataset：** `market.klines`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.klines`, `sohu.finance.klines`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.ohlcv(instrument_id: 'InstrumentId | None' = None, start_date: 'date | None' = None, end_date: 'date | None' = None, adjustment: 'KlineAdjustment | None' = None, *, request: 'KlinesRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketKlineData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 便捷模式必填 | None | 完整的 InstrumentId。 |
| start_date | date \| None | 便捷模式必填 | None | 包含在内的开始日期。 |
| end_date | date \| None | 便捷模式必填 | None | 包含在内的结束日期。 |
| adjustment | KlineAdjustment \| None | 股票必填；指数省略 | None | Kline 调整方式；股票调用必填，指数调用省略。 |
| request | KlinesRequest \| None | 条件性 request 替代 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** 股票需提供 instrument_id、start_date、end_date 和 adjustment。

#### 请求模型 `KlinesRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| startDate | date | 是 | — | 由 Pydantic 模型定义。 |
| endDate | date | 是 | — | 由 Pydantic 模型定义。 |
| adjustment | KlineAdjustment \| None | 否 | None | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketKlineData]`。

#### 返回数据模型 `MarketKlineData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| barDate | date | 是 | — | 由 Pydantic 模型定义。 |
| open | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| high | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| low | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| close | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| volume | int | 是 | — | 非负整数股数。 |
| amount | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| adjustment | KlineAdjustment | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.ohlcv -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import KlineAdjustment
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = fx.market.ohlcv(
    instrument_id,
    date(2026, 9, 1),
    date(2026, 9, 18),
    adjustment=KlineAdjustment.QFQ,
)
```

### `fx.market.orderbook(...)`

获取单个标的的盘口数据。

**Dataset：** `market.orderbook`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.quote`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.orderbook(request: 'MarketOrderbookRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketOrderbookData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketOrderbookRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketOrderbookRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketOrderbookData]`。

#### 返回数据模型 `MarketOrderbookData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| bids | list[OrderbookLevel] | 是 | — | 由 Pydantic 模型定义。 |
| asks | list[OrderbookLevel] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `OrderbookLevel`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| level | int | 是 | — | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| size | int | 是 | — | 非负整数股数。 |

#### 示例

<!-- api-example: market.orderbook -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketOrderbookRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketOrderbookRequest(instrumentId=instrument_id)
result = fx.market.orderbook(request)
```

### `fx.market.quote(...)`

获取选定股票范围的行情快照。

**Dataset：** `market.quote`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.quote(*, universe: 'InstrumentUniverse' = <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'>, request: 'MarketQuoteUniverseRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | 否 | InstrumentUniverse.CN_A_SHARE | 查询范围。 |
| request | MarketQuoteUniverseRequest \| None | 否 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** 无；默认范围为 CN_A_SHARE。

#### 请求模型 `MarketQuoteUniverseRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketQuoteData]`。

#### 返回数据模型 `MarketQuoteData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| name | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| priceChange | Decimal \| None | 否 | None | 带符号的绝对价格变动，单位为每股 CNY。 |
| changeRate | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| changeRate5d | Decimal \| None | 否 | None | 来源指定的 5 日价格变动，以比例小数存储。 |
| changeRate10d | Decimal \| None | 否 | None | 来源指定的 10 日价格变动，以比例小数存储。 |
| changeRate20d | Decimal \| None | 否 | None | 来源指定的 20 日价格变动，以比例小数存储。 |
| changeRate60d | Decimal \| None | 否 | None | 来源指定的 60 日价格变动，以比例小数存储。 |
| changeRate52w | Decimal \| None | 否 | None | 来源指定 52 周期间的价格变动，以比例小数表示。 |
| changeRateYtd | Decimal \| None | 否 | None | 年初至今价格变动，以比例小数存储。 |
| amplitude | Decimal \| None | 否 | None | 盘中价格振幅，以比例小数存储。 |
| volumeRatio | Decimal \| None | 否 | None | 非负成交量倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| amount | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| turnoverRate | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| marketCap | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| floatMarketCap | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| peTtm | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainNetInflow | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainInflow | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainOutflow | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainInflow5d | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainOutflow5d | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.quote -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()
```

### `fx.market.quote_snapshot(...)`

获取单个标的的行情快照。

**Dataset：** `market.quote_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.quote`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.quote_snapshot(request: 'MarketQuoteSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketQuoteSnapshotRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `MarketQuoteSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketQuoteSnapshotData]`。

#### 返回数据模型 `MarketQuoteSnapshotData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 最新价格，单位为每股 CNY。 |
| previousClose | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| open | Decimal \| None | 否 | None | 交易时段开盘价，单位为每股 CNY。 |
| high | Decimal \| None | 否 | None | 交易时段最高价，单位为每股 CNY。 |
| low | Decimal \| None | 否 | None | 交易时段最低价，单位为每股 CNY。 |
| priceChange | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| changeRate | Decimal \| None | 否 | None | 相对前收盘价的变动比例小数；3% 表示为 0.03。 |
| volume | int \| None | 否 | None | 本交易时段累计成交股数。 |
| amount | Decimal \| None | 否 | None | 本交易时段累计成交金额，单位为 CNY。 |
| sourceTimestamp | datetime | 是 | — | 来源报告的行情时间，与 FinchX capturedAt 分开。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.quote_snapshot -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import MarketQuoteSnapshotRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = MarketQuoteSnapshotRequest(instrumentId=instrument_id)
result = fx.market.quote_snapshot(request)
```

### `fx.market.ranking(...)`

获取指定条件的市场排行。

**Dataset：** `market.ranking`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.market.ranking(request: 'MarketRankingRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketRankingData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketRankingRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 universe、criterion、direction 和 limit）。

#### 请求模型 `MarketRankingRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | 是 | — | 由 Pydantic 模型定义。 |
| criterion | RankingCriterion | 是 | — | 由 Pydantic 模型定义。 |
| direction | RankingDirection | 是 | — | 由 Pydantic 模型定义。 |
| limit | int \| None | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketRankingData]`。

#### 返回数据模型 `MarketRankingData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| name | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 每股价格；币种为 CNY。 |
| priceChange | Decimal \| None | 否 | None | 带符号的绝对价格变动，单位为每股 CNY。 |
| changeRate | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| changeRate5d | Decimal \| None | 否 | None | 来源指定的 5 日价格变动，以比例小数存储。 |
| changeRate10d | Decimal \| None | 否 | None | 来源指定的 10 日价格变动，以比例小数存储。 |
| changeRate20d | Decimal \| None | 否 | None | 来源指定的 20 日价格变动，以比例小数存储。 |
| changeRate60d | Decimal \| None | 否 | None | 来源指定的 60 日价格变动，以比例小数存储。 |
| changeRate52w | Decimal \| None | 否 | None | 来源指定 52 周期间的价格变动，以比例小数表示。 |
| changeRateYtd | Decimal \| None | 否 | None | 年初至今价格变动，以比例小数存储。 |
| amplitude | Decimal \| None | 否 | None | 盘中价格振幅，以比例小数存储。 |
| volumeRatio | Decimal \| None | 否 | None | 非负成交量倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| amount | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| turnoverRate | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| marketCap | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| floatMarketCap | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| peTtm | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainNetInflow | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainInflow | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainOutflow | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainInflow5d | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| mainOutflow5d | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| universe | InstrumentUniverse | 是 | — | 由 Pydantic 模型定义。 |
| direction | RankingDirection | 是 | — | 由 Pydantic 模型定义。 |
| position | int | 是 | — | 由 Pydantic 模型定义。 |
| metric | TurnoverRankingMetric \| ChangePercentRankingMetric \| VolumeRankingMetric | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `ChangePercentRankingMetric`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| criterion | Literal['change_percent'] | 是 | — | 由 Pydantic 模型定义。 |
| value | Decimal | 是 | — | 比例小数，而不是百分点：4.24% 表示为 0.0424。 |

#### 嵌套模型 `TurnoverRankingMetric`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| criterion | Literal['turnover'] | 是 | — | 由 Pydantic 模型定义。 |
| value | Decimal | 是 | — | 金额，单位为 CNY。 |

#### 嵌套模型 `VolumeRankingMetric`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| criterion | Literal['volume'] | 是 | — | 由 Pydantic 模型定义。 |
| value | int | 是 | — | 非负整数股数。 |

#### 示例

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

### `fx.market.sentiment(...)`

获取市场情绪快照。

**Dataset：** `market.sentiment_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `aigupiao.market_sentiment`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.sentiment(request: 'MarketSentimentRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketSentimentData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketSentimentRequest \| None | 否 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** 无。

#### 请求模型 `MarketSentimentRequest`

无字段；直接无参实例化该模型。

公开返回标注为 `FetchResult[MarketSentimentData]`。

#### 返回数据模型 `MarketSentimentData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| marketTemperature | Decimal | 是 | — | Aigupiao 定义的情绪温度；不是物理温度或比例。 |
| totalTurnover | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| forecastedTurnover | Decimal \| None | 否 | None | 来源预测值，不是观测到的换手率。 |
| turnoverChangeAmount | Decimal \| None | 否 | None | 来源报告的成交金额相对前一日的变动。 |
| blastBreakRatio | Decimal \| None | 否 | None | 来源定义的比例；FinchX 不复现其分母。 |
| previousLimitUpBreakChangeRatio | Decimal \| None | 否 | None | 来源定义的前期炸板表现比例。 |
| stopTradingCount | int | 是 | — | 由 Pydantic 模型定义。 |
| oneLimitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |
| twoLimitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |
| threeLimitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |
| highLimitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |
| twoLimitUpPromotionRatio | Decimal \| None | 否 | None | 来源定义的晋级比例；FinchX 不复现其分母。 |
| threeLimitUpPromotionRatio | Decimal \| None | 否 | None | 来源定义的晋级比例；FinchX 不复现其分母。 |
| highLimitUpPromotionRatio | Decimal \| None | 否 | None | 来源定义的晋级比例；FinchX 不复现其分母。 |
| previousLimitUpThemeChangeRatio | Decimal \| None | 否 | None | 来源定义的前期涨停组表现比例。 |
| previousConsecutiveLimitUpThemeChangeRatio | Decimal \| None | 否 | None | 来源定义的前期连板组表现比例。 |

#### 示例

<!-- api-example: market.sentiment -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.sentiment()
```

### `fx.market.strong_pool(...)`

获取强势股池。

**Dataset：** `market.strong_pool`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.push2ex.strong_pool`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.strong_pool(request: 'MarketStrongPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStrongPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketStrongPoolRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request。

#### 请求模型 `MarketStrongPoolRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketStrongPoolData]`。

#### 返回数据模型 `MarketStrongPoolData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| price | Decimal | 是 | — | 最新价格，单位为每股 CNY。 |
| limitUpPrice | Decimal | 是 | — | 当前涨停价，单位为每股 CNY。 |
| changeRate | Decimal | 是 | — | 比例小数；20% 表示为 0.20。 |
| amount | Decimal | 是 | — | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| turnoverRate | Decimal | 是 | — | 比例小数。 |
| isSixtyDayHigh | bool | 是 | — | 由 Pydantic 模型定义。 |
| selectionReason | StrongPoolSelectionReason | 是 | — | 由 Pydantic 模型定义。 |
| volumeRatio | Decimal | 是 | — | 来源成交量倍数，为无量纲倍数。 |
| industry | str | 是 | — | 由 Pydantic 模型定义。 |
| limitUpStats | MarketStrongPoolStats | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `MarketStrongPoolStats`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | 是 | — | 由 Pydantic 模型定义。 |
| limitUpCount | int | 是 | — | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.strong_pool -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketStrongPoolRequest

fx = FinchX()
request = MarketStrongPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.strong_pool(request)
```

### `fx.market.yesterday_limit_up_pool(...)`

获取昨日涨停池。

**Dataset：** `market.yesterday_limit_up_pool`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.push2ex.yesterday_limit_up_pool`
**路由语义：** `single_source`

#### 方法签名

```python
fx.market.yesterday_limit_up_pool(request: 'MarketYesterdayLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketYesterdayLimitUpPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketYesterdayLimitUpPoolRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request。

#### 请求模型 `MarketYesterdayLimitUpPoolRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[MarketYesterdayLimitUpPoolData]`。

#### 返回数据模型 `MarketYesterdayLimitUpPoolData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| tradeDate | date | 是 | — | 当前观测到的来源日期，不是前一涨停事件日期。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| currentPrice | Decimal | 是 | — | 当前交易日价格，单位为每股 CNY。 |
| currentLimitUpPrice | Decimal | 是 | — | 当前交易日涨停价，单位为每股 CNY。 |
| currentChangeRate | Decimal | 是 | — | 当前交易日比例小数。 |
| currentAmount | Decimal | 是 | — | 当前交易日成交金额，单位为 CNY。 |
| floatMarketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| marketCapitalization | Decimal | 是 | — | 金额，单位为 CNY。 |
| currentTurnoverRate | Decimal | 是 | — | 当前交易日换手率比例小数。 |
| currentAmplitude | Decimal | 是 | — | 当前交易日振幅比例小数。 |
| yesterdayFirstLimitUpTime | str \| None | 否 | None | 前一交易日首次涨停时间，使用市场本地 HH:MM:SS。 |
| yesterdayConsecutiveLimitUpDays | int | 是 | — | 由 Pydantic 模型定义。 |
| industry | str | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.yesterday_limit_up_pool -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketYesterdayLimitUpPoolRequest

fx = FinchX()
request = MarketYesterdayLimitUpPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.yesterday_limit_up_pool(request)
```

## `fundamental`

### `fx.fundamental.company_profile(...)`

获取公司概况。

**Dataset：** `fundamental.company_profile`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.fundamental.company_profile(instrument_id: 'InstrumentId | None' = None, *, request: 'CompanyProfileRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CompanyProfileData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 便捷模式必填 | None | 完整的 InstrumentId。 |
| request | CompanyProfileRequest \| None | 条件性 request 替代 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** instrument_id 或 request。

#### 请求模型 `CompanyProfileRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[CompanyProfileData]`。

#### 返回数据模型 `CompanyProfileData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| companyName | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| businessDescription | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| issuePrice | Decimal \| None | 否 | None | 单位为每股 CNY；保留 Tencent gsjj.jg 作为来源候选值。 |
| listingDate | date \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: fundamental.company_profile -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = fx.fundamental.company_profile(instrument_id)
```

### `fx.fundamental.financial_summary(...)`

获取公司财务摘要。

**Dataset：** `fundamental.financial_summary`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.fundamental.financial_summary(request: 'FinancialSummaryRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialSummaryData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FinancialSummaryRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `FinancialSummaryRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[FinancialSummaryData]`。

#### 返回数据模型 `FinancialSummaryData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| periods | list[FinancialSummaryPeriod] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `FinancialSummaryPeriod`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| reportedPeriodLabel | str | 是 | — | 由 Pydantic 模型定义。 |
| periodType | Literal['annual', 'interim', 'unknown'] | 是 | — | 由 Pydantic 模型定义。 |
| eps | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| revenue | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| revenueGrowth | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| netProfit | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| netProfitGrowth | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| bookValuePerShare | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| netAssets | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| goodwill | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| goodwillToNetAssets | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| roe | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| debtRatio | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| grossMargin | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: fundamental.financial_summary -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import FinancialSummaryRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = FinancialSummaryRequest(instrumentId=instrument_id)
result = fx.fundamental.financial_summary(request)
```

### `fx.fundamental.industry_comparison(...)`

获取公司与行业的基本面比较。

**Dataset：** `fundamental.industry_comparison`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.fundamental.industry_comparison(request: 'FundamentalIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndustryComparisonData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FundamentalIndustryComparisonRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

**命名说明：** Client 标注使用局部别名 `FundamentalIndustryComparisonRequest`；真实公开类名和 Dataset request type 是 `finchx.datasets.IndustryComparisonRequest`。

#### 请求模型 `IndustryComparisonRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[IndustryComparisonData]`。

#### 返回数据模型 `IndustryComparisonData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| industryName | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| metrics | list[IndustryComparisonMetric] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `IndustryComparisonMetric`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| metric | Literal['eps', 'revenue', 'net_profit', 'book_value_per_share', 'roe', 'debt_ratio', 'gross_margin', 'revenue_growth', 'net_profit_growth', 'market_cap', 'pe', 'pb', 'dividend_yield'] | 是 | — | 由 Pydantic 模型定义。 |
| metricBasis | Literal['financial_period', 'market_snapshot'] | 是 | — | 由 Pydantic 模型定义。 |
| companyValue | Decimal \| Decimal \| Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| industryAvg | Decimal \| Decimal \| Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| industryMax | Decimal \| Decimal \| Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| industryMin | Decimal \| Decimal \| Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| periodEnd | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| reportedPeriodLabel | str | 是 | — | 由 Pydantic 模型定义。 |
| observationAt | datetime \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: fundamental.industry_comparison -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import IndustryComparisonRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = IndustryComparisonRequest(instrumentId=instrument_id)
result = fx.fundamental.industry_comparison(request)
```

### `fx.fundamental.revenue_breakdown(...)`

获取公司收入构成。

**Dataset：** `fundamental.revenue_breakdown`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.fundamental.revenue_breakdown(request: 'RevenueBreakdownRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RevenueBreakdownData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | RevenueBreakdownRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `RevenueBreakdownRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[RevenueBreakdownData]`。

#### 返回数据模型 `RevenueBreakdownData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| breakdowns | list[RevenueBreakdownRow] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `RevenueBreakdownRow`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| reportedPeriodLabel | str | 是 | — | 由 Pydantic 模型定义。 |
| periodEnd | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| dimension | Literal['product', 'region', 'industry'] | 是 | — | 由 Pydantic 模型定义。 |
| itemName | str | 是 | — | 由 Pydantic 模型定义。 |
| revenue | Decimal \| None | 是 | — | 由 Pydantic 模型定义。 |
| revenueShare | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| currency | Literal['CNY'] | 是 | — | 由 Pydantic 模型定义。 |
| sourceGroup | Literal['detail', 'others'] | 是 | — | 由 Pydantic 模型定义。 |
| isRollup | bool | 是 | — | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: fundamental.revenue_breakdown -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import RevenueBreakdownRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = RevenueBreakdownRequest(instrumentId=instrument_id)
result = fx.fundamental.revenue_breakdown(request)
```

## `financial`

### `fx.financial.statements(...)`

获取财务报表数据。

**Dataset：** `financial.statement`
**Schema 版本：** `1.0`
**已实现 Provider：** `tonghuashun.financial`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.financial.statements(instrument_id: 'InstrumentId | None' = None, statement_type: 'StatementType | None' = None, *, period_end: 'date | None' = None, max_periods: 'int | None' = None, request: 'FinancialStatementRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialStatementData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 便捷模式必填 | None | 完整的 InstrumentId。 |
| statement_type | StatementType \| None | 便捷模式必填 | None | balance_sheet、income_statement 或 cash_flow_statement。 |
| period_end | date \| None | 否 | None | 可选的报告期结束日期。 |
| max_periods | int \| None | 否 | None | 可选的最大报告期数量。 |
| request | FinancialStatementRequest \| None | 条件性 request 替代 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** instrument_id 和 statement_type，或使用 request。

#### 请求模型 `FinancialStatementRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | 是 | — | 由 Pydantic 模型定义。 |
| periodEnd | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| maxPeriods | int \| None | 否 | None | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[FinancialStatementData]`。

#### 返回数据模型 `FinancialStatementData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | 是 | — | 由 Pydantic 模型定义。 |
| periods | list[FinancialStatementPeriod] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `FinancialStatementPeriod`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date | 是 | — | 由 Pydantic 模型定义。 |
| lineItems | list[FinancialStatementLineItem] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `FinancialStatementLineItem`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lineItemId | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceName | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceUnit | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceValue | str \| bool \| int \| float \| None | 是 | — | 由 Pydantic 模型定义。 |
| value | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| currency | Currency \| None | 否 | None | 由 Pydantic 模型定义。 |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: financial.statements -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = fx.financial.statements(instrument_id, "income_statement")
```

## `news`

### `fx.news.search(...)`

搜索个股新闻并返回文档引用。

**Dataset：** `news.document`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.news.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, sort: 'str' = 'published_desc', request: 'NewsSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[NewsDocumentRef, ...]]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | 便捷模式必填 | None | InstrumentId 或六位股票代码。 |
| page | int | 否 | 1 | 从 1 开始的页码。 |
| page_size | int | 否 | 20 | 单页数量。 |
| max_results | int \| None | 否 | None | 可选的结果上限；与非第一页组合受模型校验。 |
| since | date \| datetime \| None | 否 | None | 可选的包含起点。 |
| until | date \| datetime \| None | 否 | None | 可选的包含终点。 |
| sort | str | 否 | 'published_desc' | published_desc 或 published_asc。 |
| request | NewsSearchRequest \| None | 条件性 request 替代 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** instrument（InstrumentId 或六位股票代码），或使用 request。

#### 请求模型 `NewsSearchRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| page | int | 否 | 1 | 由 Pydantic 模型定义。 |
| pageSize | int | 否 | 20 | 由 Pydantic 模型定义。 |
| maxResults | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| since | date \| datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| until | date \| datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| sort | Literal['published_desc', 'published_asc'] | 否 | 'published_desc' | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[tuple[NewsDocumentRef, Ellipsis]]`。

#### 返回数据模型 `NewsDocumentData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| documentId | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceDocumentId | str | 是 | — | 由 Pydantic 模型定义。 |
| title | str | 是 | — | 由 Pydantic 模型定义。 |
| contentText | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| summary | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| publishedAt | datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| sourceOccurrences | list[NewsSourceOccurrence] | 否 | default_factory=list | 由 Pydantic 模型定义。 |
| url | AnyUrl | 是 | — | 由 Pydantic 模型定义。 |
| originalUrl | AnyUrl \| None | 否 | None | 由 Pydantic 模型定义。 |
| contentAvailable | bool | 是 | — | 由 Pydantic 模型定义。 |
| source | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| relatedInstruments | list[InstrumentId] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `NewsSourceOccurrence`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| providerId | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceDocumentId | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceUrl | AnyUrl \| None | 否 | None | 由 Pydantic 模型定义。 |
| documentUrl | AnyUrl \| None | 否 | None | 由 Pydantic 模型定义。 |
| publishedAt | datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| capturedAt | datetime | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: news.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.news.search("600519")
```

## `disclosure`

### `fx.disclosure.search(...)`

搜索个股公告并返回公告引用。

**Dataset：** `disclosure.document`
**Schema 版本：** `1.0`
**已实现 Provider：** `eastmoney.disclosure`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.disclosure.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, categories: 'Sequence[str] | None' = None, sort: 'str' = 'published_desc', request: 'DisclosureSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[DisclosureDocumentRef, ...]]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | 便捷模式必填 | None | InstrumentId 或六位股票代码。 |
| page | int | 否 | 1 | 从 1 开始的页码。 |
| page_size | int | 否 | 20 | 单页数量。 |
| max_results | int \| None | 否 | None | 可选的结果上限；与非第一页组合受模型校验。 |
| since | date \| datetime \| None | 否 | None | 可选的包含起点。 |
| until | date \| datetime \| None | 否 | None | 可选的包含终点。 |
| categories | Sequence[str] \| None | 否 | None | 可选的公告分类列表。 |
| sort | str | 否 | 'published_desc' | published_desc 或 published_asc。 |
| request | DisclosureSearchRequest \| None | 条件性 request 替代 | None | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** instrument（InstrumentId 或六位股票代码），或使用 request。

#### 请求模型 `DisclosureSearchRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| page | int | 否 | 1 | 由 Pydantic 模型定义。 |
| pageSize | int | 否 | 20 | 由 Pydantic 模型定义。 |
| maxResults | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| since | date \| datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| until | date \| datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| sort | Literal['published_desc', 'published_asc'] | 否 | 'published_desc' | 由 Pydantic 模型定义。 |
| categories | list[str] \| None | 否 | None | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[tuple[DisclosureDocumentRef, Ellipsis]]`。

#### 返回数据模型 `DisclosureDocumentData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| documentId | str | 是 | — | 由 Pydantic 模型定义。 |
| sourceDocumentId | str | 是 | — | 由 Pydantic 模型定义。 |
| title | str | 是 | — | 由 Pydantic 模型定义。 |
| contentText | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| noticeDate | date | 是 | — | 由 Pydantic 模型定义。 |
| publishedAt | datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| sourceRecordedAt | datetime \| None | 否 | None | 由 Pydantic 模型定义。 |
| categories | list[DisclosureCategory] | 是 | — | 由 Pydantic 模型定义。 |
| relatedInstruments | list[InstrumentId] | 是 | — | 由 Pydantic 模型定义。 |
| contentAvailable | bool | 是 | — | 由 Pydantic 模型定义。 |
| pdfAvailable | bool | 是 | — | 由 Pydantic 模型定义。 |
| originalDocumentUrl | AnyUrl | 是 | — | 由 Pydantic 模型定义。 |
| attachments | list[DisclosureAttachment] | 是 | — | 由 Pydantic 模型定义。 |
| sourceType | str \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `DisclosureCategory`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| source | str | 否 | 'eastmoney' | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `DisclosureAttachment`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| sequence | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| size | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| attachmentType | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| url | AnyUrl | 是 | — | 由 Pydantic 模型定义。 |
| webUrl | AnyUrl \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: disclosure.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.disclosure.search("600519")
```

## `ownership`

### `fx.ownership.capital_snapshot(...)`

获取股本快照。

**Dataset：** `ownership.capital_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.ownership.capital_snapshot(request: 'CapitalSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CapitalSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | CapitalSnapshotRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `CapitalSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[CapitalSnapshotData]`。

#### 返回数据模型 `CapitalSnapshotData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| totalShares | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| floatShares | int \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: ownership.capital_snapshot -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import CapitalSnapshotRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = CapitalSnapshotRequest(instrumentId=instrument_id)
result = fx.ownership.capital_snapshot(request)
```

### `fx.ownership.float_holder(...)`

获取流通股东数据。

**Dataset：** `ownership.float_holder`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.float_holder`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.ownership.float_holder(request: 'FloatHolderRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FloatHolderData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FloatHolderRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId；asOf 可选）。

#### 请求模型 `FloatHolderRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| asOf | datetime \| None | 否 | None | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[FloatHolderData]`。

#### 返回数据模型 `FloatHolderData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| periods | list[FloatHolderPeriod] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `FloatHolderPeriod`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date | 是 | — | 由 Pydantic 模型定义。 |
| publishedAt | datetime | 是 | — | 由 Pydantic 模型定义。 |
| rows | list[FloatHolderRow] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `FloatHolderRow`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| rank | int | 是 | — | 根据 Tencent rows 数组顺序推导。 |
| holderId | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| holderName | str | 是 | — | 由 Pydantic 模型定义。 |
| shares | int | 是 | — | 非负整数股数。 |
| holderType | str | 是 | — | 由 Pydantic 模型定义。 |
| floatShareRatio | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| previousShares | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| shareChange | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| isNewTopFloatHolderEntry | bool \| None | 否 | None | 根据多股票相邻期间校验后的 bdms=1 推导。 |

#### 示例

<!-- api-example: ownership.float_holder -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import FloatHolderRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = FloatHolderRequest(instrumentId=instrument_id)
result = fx.ownership.float_holder(request)
```

### `fx.ownership.holder_summary_snapshot(...)`

获取股东汇总快照。

**Dataset：** `ownership.holder_summary_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.ownership.holder_summary_snapshot(request: 'HolderSummarySnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[HolderSummarySnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | HolderSummarySnapshotRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `HolderSummarySnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[HolderSummarySnapshotData]`。

#### 返回数据模型 `HolderSummarySnapshotData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| shareholderCount | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| averageSharesPerHolder | Decimal \| None | 否 | None | 每位持有人的精确股数；Tencent rjcg 展示单位已换算为股。 |
| shareholderCountChange | Decimal \| None | 否 | None | Tencent gdrshb 已从百分点规范化为比例；不是绝对数量差。 |
| top10FloatHolderRatio | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| top10HolderRatio | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: ownership.holder_summary_snapshot -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import HolderSummarySnapshotRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = HolderSummarySnapshotRequest(instrumentId=instrument_id)
result = fx.ownership.holder_summary_snapshot(request)
```

## `company`

### `fx.company.executive_share_change(...)`

获取高管持股变动。

**Dataset：** `company.executive_share_change`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.company.executive_share_change(request: 'ExecutiveShareChangeRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveShareChangeData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | ExecutiveShareChangeRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `ExecutiveShareChangeRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[ExecutiveShareChangeData]`。

#### 返回数据模型 `ExecutiveShareChangeData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| changes | list[ExecutiveShareChange] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `ExecutiveShareChange`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| eventDate | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| personName | str \| None | 否 | None | 由 Pydantic 模型定义。 |
| shareChange | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| averagePrice | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: company.executive_share_change -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import ExecutiveShareChangeRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = ExecutiveShareChangeRequest(instrumentId=instrument_id)
result = fx.company.executive_share_change(request)
```

### `fx.company.executive_snapshot(...)`

获取高管快照。

**Dataset：** `company.executive_snapshot`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.company.executive_snapshot(request: 'ExecutiveSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | ExecutiveSnapshotRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `ExecutiveSnapshotRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[ExecutiveSnapshotData]`。

#### 返回数据模型 `ExecutiveSnapshotData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| executives | list[ExecutiveEntry] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `ExecutiveEntry`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| name | str | 是 | — | 由 Pydantic 模型定义。 |
| roles | list[str] | 是 | — | 由 Pydantic 模型定义。 |
| shares | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| compensation | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: company.executive_snapshot -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import ExecutiveSnapshotRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = ExecutiveSnapshotRequest(instrumentId=instrument_id)
result = fx.company.executive_snapshot(request)
```

## `corporate_action`

### `fx.corporate_action.dividend(...)`

获取分红除权记录。

**Dataset：** `corporate_action.dividend`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.corporate_action.dividend(request: 'DividendRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DividendData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | DividendRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `DividendRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[DividendData]`。

#### 返回数据模型 `DividendData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| dividends | list[Dividend] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `Dividend`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| fiscalYear | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| announcementDate | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| stockDividendPer10 | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| capitalizationPer10 | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| cashDividendPer10 | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| rightsIssuePer10 | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| recordDate | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| exDate | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| description | str \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: corporate_action.dividend -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import DividendRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = DividendRequest(instrumentId=instrument_id)
result = fx.corporate_action.dividend(request)
```

### `fx.corporate_action.repurchase(...)`

获取回购记录。

**Dataset：** `corporate_action.repurchase`
**Schema 版本：** `1.0`
**已实现 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`

#### 方法签名

```python
fx.corporate_action.repurchase(request: 'RepurchaseRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RepurchaseData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | RepurchaseRequest | 是 | — | 类型化请求模型；合法组合由 Client 和 Pydantic 校验决定。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** request（包含 instrumentId）。

#### 请求模型 `RepurchaseRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[RepurchaseData]`。

#### 返回数据模型 `RepurchaseData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| symbol | str | 是 | — | 由 Pydantic 模型定义。 |
| repurchases | list[Repurchase] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `Repurchase`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| repurchaseDate | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| quantity | int \| None | 否 | None | 由 Pydantic 模型定义。 |
| averagePrice | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| currency | Currency \| None | 否 | None | 由 Pydantic 模型定义。 |
| fundAmount | Decimal \| None | 否 | None | 由 Pydantic 模型定义。 |
| market | str \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: corporate_action.repurchase -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.datasets import RepurchaseRequest

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
request = RepurchaseRequest(instrumentId=instrument_id)
result = fx.corporate_action.repurchase(request)
```

## `market.deviation`

### `fx.market.deviation(...)`

计算经过审计的基于收盘价的偏离值。

**Dataset：** `market.deviation`（计算能力；无 Provider）
**Schema 版本：** `1.0`

#### 方法签名

```python
fx.market.deviation(instrument_id: 'InstrumentId', *, windows: 'Sequence[int]' = (10, 30), as_of: 'date | None' = None, window_convention: 'DeviationWindowConvention' = <DeviationWindowConvention.MAX_DEVIATION_SCAN: 'max_deviation_scan'>, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DeviationData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId | 是 | — | 完整的 InstrumentId。 |
| windows | Sequence[int] | 否 | (10, 30) | 支持的偏离窗口：10 和 30 个交易时段。 |
| as_of | date \| None | 否 | None | 可选的已完成交易时段日期。 |
| window_convention | DeviationWindowConvention | 否 | DeviationWindowConvention.MAX_DEVIATION_SCAN | 偏离窗口解释方式。 |
| provider | str \| None | 否 | None | 严格指定 Provider id；失败时不会静默切换。 |
| use_cache | bool \| None | 否 | None | 缓存控制；None 遵循已配置的 CachePolicy。 |

**最小业务输入：** instrument_id。

#### 请求模型 `DeviationRequest`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| asOf | date \| None | 否 | None | 由 Pydantic 模型定义。 |
| windows | tuple[Literal[10, 30], Ellipsis] | 否 | (10, 30) | 由 Pydantic 模型定义。 |
| windowConvention | DeviationWindowConvention | 否 | DeviationWindowConvention.MAX_DEVIATION_SCAN | 由 Pydantic 模型定义。 |

公开返回标注为 `FetchResult[DeviationData]`。

#### 返回数据模型 `DeviationData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| board | str | 是 | — | 由 Pydantic 模型定义。 |
| effectiveAsOf | date | 是 | — | 由 Pydantic 模型定义。 |
| calculationMode | Literal['official_close'] | 是 | — | 由 Pydantic 模型定义。 |
| priceBasis | Literal['qfq_stock__raw_index'] | 是 | — | 由 Pydantic 模型定义。 |
| ruleVersion | str | 是 | — | 由 Pydantic 模型定义。 |
| windows | tuple[DeviationWindowData, Ellipsis] | 是 | — | 由 Pydantic 模型定义。 |

#### 嵌套模型 `InstrumentId`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 由 Pydantic 模型定义。 |
| market | Market | 是 | — | 由 Pydantic 模型定义。 |
| kind | InstrumentKind | 是 | — | 由 Pydantic 模型定义。 |
| exchange | Exchange \| None | 否 | None | 由 Pydantic 模型定义。 |

#### 嵌套模型 `DeviationWindowData`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| windowDays | Literal[10, 30] | 是 | — | 由 Pydantic 模型定义。 |
| windowConvention | DeviationWindowConvention | 是 | — | 由 Pydantic 模型定义。 |
| tradingSessions | int | 是 | — | 由 Pydantic 模型定义。 |
| startDate | date | 是 | — | 由 Pydantic 模型定义。 |
| baselineDate | date | 是 | — | 由 Pydantic 模型定义。 |
| endDate | date | 是 | — | 由 Pydantic 模型定义。 |
| startPrice | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| windowStartPrice | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| currentPrice | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| benchmarkInstrument | InstrumentId | 是 | — | 由 Pydantic 模型定义。 |
| benchmarkName | str | 是 | — | 由 Pydantic 模型定义。 |
| benchmarkStart | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| benchmarkCurrent | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| stockReturn | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| benchmarkReturn | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| deviation | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| upperThreshold | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| lowerThreshold | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| remainingToUpper | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| remainingToLower | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| upperTriggerPrice | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| lowerTriggerPrice | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| remainingPricePctToUpper | Decimal | 是 | — | 由 Pydantic 模型定义。 |
| remainingPricePctToLower | Decimal | 是 | — | 由 Pydantic 模型定义。 |

#### 示例

<!-- api-example: market.deviation -->
```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

fx = FinchX()
instrument_id = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = fx.market.deviation(instrument_id, windows=(10, 30))
```
