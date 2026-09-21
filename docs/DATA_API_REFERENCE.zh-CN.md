# FinchX 数据与 API 参考

[English](DATA_API_REFERENCE.md) | 简体中文


本参考根据当前 Client、Dataset 定义、Pydantic schema 和 Provider Registry，描述公开 API 表面：42 个 Provider-backed / Dataset-backed 公开接口，以及计算型 `market.deviation` 能力。计算能力单独成章，因为它有意不属于 Provider-backed 清单。

## 通用概念

### InstrumentId

大多数 market、fundamental、financial、ownership、company 和 corporate-action 请求都使用完整的 `InstrumentId`：

```python
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

instrument_id = InstrumentId(
    code="600519", market=Market.CN_A,
    kind=InstrumentKind.EQUITY, exchange=Exchange.SSE,
)
```
允许的 enum 值包括 `Market.CN_A` (`cn_a`)、`InstrumentKind.EQUITY`/`INDEX`/`ETF` (`equity`、`index`、`etf`) 和 `Exchange.SSE`/`SZSE`/`BSE` (`sse`、`szse`、`bse`)。基础身份模型中的 `exchange` 是可选的，但需要交易所特定映射的能力要求它必填。

### FetchResult

所有显式 Client 方法都返回 `FetchResult`。其字段包括：

| 字段 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `data` | generic | — | 返回标准化记录、文档引用或计算结果。 |
| `dataset` | DatasetDefinition | — | Dataset 名称、schema 版本、请求类型和数据载荷类型。 |
| `dataset_id` | str | — | 包含 `dataset.name` 的便捷属性。 |
| `provider` | str \| None | — | 成功获取所使用的 Provider id；计算型偏离值为 `None`。 |
| `provider_id` | str \| None | — | 映射 `provider` 的便捷属性。 |
| `captured_at` | datetime | — | 带时区的 FinchX 获取时间。 |
| `warnings` | tuple[str, ...] | () | 非致命的获取警告。 |
| `provenance` | tuple[Source, ...] | () | 结果中保留的直接数据源身份。 |
| `attempts` | tuple[FetchAttempt, ...] | () | Provider 尝试记录；在可用时包含重试/失败事实。 |
| `fallback_used` | bool | False | 运行时是否在较早的 Provider 失败后使用了后续允许的 Provider。 |
| `cache_hit` | bool | False | 结果是否来自已配置的缓存。 |

Provider-backed 记录使用 `StandardRecord` 外层结构。其公开字段包括 `dataset`、`schemaVersion`、`recordId`、`entityId`、`eventAt`、`publishedAt`、`updatedAt`、`capturedAt`、`asOf`、`source`、`status`、`quality`、`provenance` 和 `data`。下方 Dataset 字段表描述标准化的 `record.data` 数据载荷。列表和时间序列接口返回外层结构元组；新闻和公告搜索返回 `NewsDocumentRef` 或 `DisclosureDocumentRef` 元组，而不是完整的 `StandardRecord` 外层结构。

`Source` 包含 `providerId`、可选的 `sourceRecordId` 和可选的 `sourceUrl`。`FetchAttempt` 包含 `provider`、`attempt`、`started_at`、`captured_at`、`success`，以及可选的 `error_type`/`error_message`。

### Provider 选择

提供 `provider=` 时会严格指定 Provider。提供 Provider 后只使用该 Provider id，失败时不会静默改用其他 Provider。未指定时，运行时策略控制重试和 Provider 选择。本文档只列出已实现的 Provider，不分配 primary 或 fallback 角色。

Provider id 是稳定的 Registry 身份标识，例如 `tencent.finance.qq.klines` 或 `eastmoney.stockrank`。标记为 `single_source` 的 Dataset 使用特定数据源的公开契约；标记为 `multi_provider` 的 Dataset 可以接纳实现同一标准化契约的 Provider。

### Cache

`use_cache=None` 遵循已配置的 `CachePolicy`。`use_cache=False` 绕过缓存读取。显式指定 Provider 会绕过缓存结果。除非通过 Collector 配置提供，`FinchX()` 不启用缓存，也没有默认 SQLite 文件。

### 时间字段

`capturedAt` 是 FinchX 获取上游观测值的时间。它不同于数据源的 `publishedAt`、`sourceTimestamp`，市场的 `tradeDate`/`barDate`，公告的 `noticeDate` 和数据源的 `calculatedAt`。偏离值中的 `effectiveAsOf` 是计算实际使用的已完成交易时段。

### 错误

主要公开错误类别包括 `InvalidRequest`、`AuthenticationError`、`MissingOptionalDependency`、`SchemaDrift`、`NoData`、`ProviderDoesNotSupportDataset`、`UnknownProvider` 和 `AllProvidersFailed`。未严格指定 Provider 时，传输、限流和超时情况可能根据配置的运行时策略进行重试或路由。

## 数据来源

下表列出当前 Registry 身份及其对应的公开接口。这是实现清单，不是上游 SLA，也不承诺路由顺序。

| Provider id | 接口 | 说明 |
| --- | --- | --- |
| `szse.official.calendar` | `reference.trading_calendar` | — |
| `pandas_market_calendars` | `reference.trading_calendar` | 可选：pandas_market_calendars |
| `tencent.finance.qq.market` | `reference.instrument`, `market.quote`, `market.ranking` | — |
| `tencent.finance.qq.quote` | `market.quote_snapshot`, `market.orderbook` | — |
| `tencent.finance.qq.klines` | `market.ohlcv` | — |
| `sohu.finance.klines` | `market.ohlcv` | — |
| `tencent.finance.qq.intraday` | `market.equity_intraday`, `market.equity_intraday_5d`, `market.index_intraday`, `market.index_intraday_5d` | — |
| `tencent.finance.qq.fund_flow` | `market.fund_flow_snapshot`, `market.fund_flow_intraday`, `market.fund_flow_daily` | — |
| `eastmoney.push2ex.breadth` | `market.breadth` | — |
| `eastmoney.push2ex.limit_up_pool` | `market.limit_up_pool` | — |
| `eastmoney.push2ex.limit_down_pool` | `market.limit_down_pool` | — |
| `eastmoney.push2ex.yesterday_limit_up_pool` | `market.yesterday_limit_up_pool` | — |
| `eastmoney.push2ex.strong_pool` | `market.strong_pool` | — |
| `eastmoney.push2ex.broken_limit_pool` | `market.broken_limit_pool` | — |
| `tencent.finance.qq.sector` | `market.instrument_sector_snapshot` | — |
| `eastmoney.stockrank` | `market.stock_keyword` | — |
| `tencent.finance.qq.industry` | `market.industry_comparison` | — |
| `tonghuashun.financial` | `financial.statements` | — |
| `tencent.finance.qq.f10` | `fundamental.company_profile`, `fundamental.financial_summary`, `fundamental.revenue_breakdown`, `fundamental.industry_comparison`, `ownership.capital_snapshot`, `ownership.holder_summary_snapshot`, `company.executive_snapshot`, `company.executive_share_change`, `corporate_action.dividend`, `corporate_action.repurchase` | — |
| `tencent.finance.qq.float_holder` | `ownership.float_holder` | — |
| `eastmoney.news` | `news.search` | — |
| `eastmoney.disclosure` | `disclosure.search` | — |
| `eastmoney.market_news` | `news.search` | — |
| `aigupiao.market_news` | `news.search` | — |
| `baidu.finscope.market_news` | `news.search` | — |
| `aigupiao.market_sentiment` | `market.sentiment` | — |
| `aigupiao.series_limit_up` | `market.consecutive_limit_up` | — |
| `aigupiao.dragon_tiger` | `market.dragon_tiger_list`, `market.dragon_tiger_detail` | — |
| `jiuyangongshe.daily_replay` | `market.daily_replay` | 需要身份验证；可选：playwright |

## 接口索引

该索引涵盖全部 42 个已注册的 Dataset-backed 方法以及计算型偏离值能力。

| Namespace | 接口 | Dataset | 已实现的 Provider | 主要必填输入 |
| --- | --- | --- | --- | --- |
| `reference` | `instrument` | `instrument` | `tencent.finance.qq.market` | instrumentId |
| `reference` | `trading_calendar` | `trading_calendar` | `szse.official.calendar`, `pandas_market_calendars` | market, startDate, endDate |
| `market` | `breadth` | `market.breadth` | `eastmoney.push2ex.breadth` | — |
| `market` | `broken_limit_pool` | `market.broken_limit_pool` | `eastmoney.push2ex.broken_limit_pool` | tradeDate |
| `market` | `consecutive_limit_up` | `market.consecutive_limit_up_snapshot` | `aigupiao.series_limit_up` | — |
| `market` | `daily_replay` | `market.daily_replay` | `jiuyangongshe.daily_replay` | requestedDate |
| `market` | `dragon_tiger_detail` | `market.dragon_tiger_detail` | `aigupiao.dragon_tiger` | instrumentId, tradeDate, tradeId |
| `market` | `dragon_tiger_list` | `market.dragon_tiger_list` | `aigupiao.dragon_tiger` | tradeDate |
| `market` | `equity_intraday` | `market.equity_intraday` | `tencent.finance.qq.intraday` | instrumentId |
| `market` | `equity_intraday_5d` | `market.equity_intraday_5d` | `tencent.finance.qq.intraday` | instrumentId |
| `market` | `fund_flow_daily` | `market.fund_flow_daily` | `tencent.finance.qq.fund_flow` | instrumentId |
| `market` | `fund_flow_intraday` | `market.fund_flow_intraday` | `tencent.finance.qq.fund_flow` | instrumentId |
| `market` | `fund_flow_snapshot` | `market.fund_flow_snapshot` | `tencent.finance.qq.fund_flow` | instrumentId |
| `market` | `index_intraday` | `market.index_intraday` | `tencent.finance.qq.intraday` | instrumentId |
| `market` | `index_intraday_5d` | `market.index_intraday_5d` | `tencent.finance.qq.intraday` | instrumentId |
| `market` | `industry_comparison` | `market.industry_comparison` | `tencent.finance.qq.industry` | instrumentId |
| `market` | `instrument_sector_snapshot` | `market.instrument_sector_snapshot` | `tencent.finance.qq.sector` | instrumentId |
| `market` | `stock_keyword` | `market.stock_keyword` | `eastmoney.stockrank` | instrumentId |
| `market` | `limit_down_pool` | `market.limit_down_pool` | `eastmoney.push2ex.limit_down_pool` | tradeDate |
| `market` | `limit_up_pool` | `market.limit_up_pool` | `eastmoney.push2ex.limit_up_pool` | tradeDate |
| `market` | `ohlcv` | `market.klines` | `tencent.finance.qq.klines`, `sohu.finance.klines` | instrumentId, startDate, endDate |
| `market` | `orderbook` | `market.orderbook` | `tencent.finance.qq.quote` | instrumentId |
| `market` | `quote` | `market.quote` | `tencent.finance.qq.market` | universe |
| `market` | `quote_snapshot` | `market.quote_snapshot` | `tencent.finance.qq.quote` | instrumentId |
| `market` | `ranking` | `market.ranking` | `tencent.finance.qq.market` | universe, criterion, direction, limit |
| `market` | `sentiment` | `market.sentiment_snapshot` | `aigupiao.market_sentiment` | — |
| `market` | `strong_pool` | `market.strong_pool` | `eastmoney.push2ex.strong_pool` | tradeDate |
| `market` | `yesterday_limit_up_pool` | `market.yesterday_limit_up_pool` | `eastmoney.push2ex.yesterday_limit_up_pool` | tradeDate |
| `fundamental` | `company_profile` | `fundamental.company_profile` | `tencent.finance.qq.f10` | instrumentId |
| `fundamental` | `financial_summary` | `fundamental.financial_summary` | `tencent.finance.qq.f10` | instrumentId |
| `fundamental` | `industry_comparison` | `fundamental.industry_comparison` | `tencent.finance.qq.f10` | instrumentId |
| `fundamental` | `revenue_breakdown` | `fundamental.revenue_breakdown` | `tencent.finance.qq.f10` | instrumentId |
| `financial` | `statements` | `financial.statement` | `tonghuashun.financial` | instrumentId, statementType |
| `news` | `search` | `news.document` | `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news` | instrumentId |
| `disclosure` | `search` | `disclosure.document` | `eastmoney.disclosure` | instrumentId |
| `ownership` | `capital_snapshot` | `ownership.capital_snapshot` | `tencent.finance.qq.f10` | instrumentId |
| `ownership` | `float_holder` | `ownership.float_holder` | `tencent.finance.qq.float_holder` | instrumentId |
| `ownership` | `holder_summary_snapshot` | `ownership.holder_summary_snapshot` | `tencent.finance.qq.f10` | instrumentId |
| `company` | `executive_share_change` | `company.executive_share_change` | `tencent.finance.qq.f10` | instrumentId |
| `company` | `executive_snapshot` | `company.executive_snapshot` | `tencent.finance.qq.f10` | instrumentId |
| `corporate_action` | `dividend` | `corporate_action.dividend` | `tencent.finance.qq.f10` | instrumentId |
| `corporate_action` | `repurchase` | `corporate_action.repurchase` | `tencent.finance.qq.f10` | instrumentId |
| `market` | `deviation` | `market.deviation` (computed) | — | `instrument_id` |

## 接口参考

## `reference`

规范的标的身份和交易日历。

### `fx.reference.instrument(...)`

查询一个标的的规范身份和显示名称；如果省略标的，则返回选定的 A 股范围。

**Dataset：** `instrument`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.reference.instrument(instrument_id: 'InstrumentId | None' = None, *, request: 'InstrumentRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[InstrumentData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 否 | None | 目标标的的完整 InstrumentId。 |
| request | InstrumentRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `InstrumentRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[InstrumentData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `InstrumentData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
instrument = fx.reference.instrument(instrument_id)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.market`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.reference.trading_calendar(...)`

返回请求范围内每个自然日的一行记录，并提供规范的交易日标志。

**Dataset：** `trading_calendar`
**Schema 版本：** `1.0`
**已实现的 Provider：** `szse.official.calendar`, `pandas_market_calendars`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.reference.trading_calendar(start_date: 'date | None' = None, end_date: 'date | None' = None, *, market: 'Market' = <Market.CN_A: 'cn_a'>, request: 'TradingCalendarRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[TradingCalendarData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| start_date | date \| None | 否 | None | 包含起始日期。 |
| end_date | date \| None | 否 | None | 包含结束日期。 |
| market | Market | 否 | <Market.CN_A: 'cn_a'> | Market 枚举；公开交易日历契约默认使用 Market.CN_A。 |
| request | TradingCalendarRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `TradingCalendarRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| market | Literal['cn_a'] | 是 | — | FinchX 市场标识。 |
| startDate | date | 是 | — | 请求范围或选定窗口的包含起始日期。 |
| endDate | date | 是 | — | 请求范围或选定窗口的包含结束日期。 |

#### 返回值

公开方法的类型标注为 `FetchResult[TradingCalendarData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `TradingCalendarData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| date | date | 否 | 该行表示的自然日。 |
| isTradingDay | bool | 否 | 标准化的交易日标志字段。 |



#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
result = fx.reference.trading_calendar(date(2026, 9, 1), date(2026, 9, 30))
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`szse.official.calendar`, `pandas_market_calendars`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

**可选依赖：** 安装 pandas_market_calendars 对应的源码 extra。从源码目录安装时使用 `python -m pip install ".[calendar]"`；发布到 PyPI 后使用对应的 `finchx[calendar]` extra。

## `market`

行情、排名、池类、资金流、盘中数据、K 线、板块和市场情报。

### `fx.market.breadth(...)`

返回东方财富市场广度快照，包括上涨、下跌以及涨停/跌停数量。

**Dataset：** `market.breadth`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.breadth`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.breadth(request: 'MarketBreadthRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBreadthData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketBreadthRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketBreadthRequest`。其字段如下：

该请求模型没有字段；可以不传 request 对象，直接调用接口使用默认请求行为。

#### 返回值

公开方法的类型标注为 `FetchResult[MarketBreadthData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketBreadthData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| advancing | int | 否 | 广度快照中的上涨标的数量或数值。 |
| declining | int | 否 | 广度快照中的下跌标的数量或数值。 |
| unchanged | int | 否 | 广度快照中的平盘标的数量或数值。 |
| total | int | 否 | 快照表示的标的总数。 |
| limitUpCount | int | 否 | 涨停标的数量。 |
| limitDownCount | int | 否 | 跌停标的数量。 |
| upOver10PercentCount | int | 否 | 涨幅超过 10% 的标的数量。 |
| downOver10PercentCount | int | 否 | 跌幅超过 10% 的标的数量。 |
| distribution | list[MarketBreadthDistributionEntry] | 否 | 东方财富提供的广度分布分组。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`MarketBreadthDistributionEntry`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| bucket | MarketBreadthBucket | 是 | — | 标准化的分组字段。 |
| count | int | 是 | — | 该收益分组中的上市股票数量。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketBreadthRequest
request = MarketBreadthRequest()
result = fx.market.breadth(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.push2ex.breadth`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.broken_limit_pool(...)`

返回在请求交易日打开涨停的股票，以及数据源定义的开板统计。

**Dataset：** `market.broken_limit_pool`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.broken_limit_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.broken_limit_pool(request: 'MarketBrokenLimitPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBrokenLimitPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketBrokenLimitPoolRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketBrokenLimitPoolRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketBrokenLimitPoolData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketBrokenLimitPoolData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| limitUpPrice | Decimal | 否 | 当前交易时段的涨停价，单位为每股人民币。 |
| changeRate | Decimal | 否 | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | 否 | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | 否 | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | 否 | 总市值，单位为人民币。 |
| turnoverRate | Decimal | 否 | 换手率；百分比以小数表示。 |
| amplitude | Decimal | 否 | 盘中价格振幅，以比率小数表示。 |
| firstLimitUpTime | str \| None | 是 | 数据源当地时间格式的首次涨停时间。 |
| limitUpBreakCount | int | 否 | 数据源观测到的开板次数。 |
| industry | str | 否 | 数据源提供的行业标签。 |
| limitUpStats | MarketBrokenLimitPoolStats | 否 | 数据源定义的涨停历史统计。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`MarketBrokenLimitPoolStats`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | 是 | — | 标准化的回看天数字段。 |
| limitUpCount | int | 是 | — | 涨停标的数量。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketBrokenLimitPoolRequest
request = MarketBrokenLimitPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.broken_limit_pool(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.push2ex.broken_limit_pool`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.consecutive_limit_up(...)`

返回 Aigupiao 连续涨停股票快照及其相关主题字段。

**Dataset：** `market.consecutive_limit_up_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `aigupiao.series_limit_up`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.consecutive_limit_up(request: 'MarketConsecutiveLimitUpRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketConsecutiveLimitUpData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketConsecutiveLimitUpRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketConsecutiveLimitUpRequest`。其字段如下：

该请求模型没有字段；可以不传 request 对象，直接调用接口使用默认请求行为。

#### 返回值

公开方法的类型标注为 `FetchResult[MarketConsecutiveLimitUpData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketConsecutiveLimitUpData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| lastPrice | Decimal | 否 | 最新价格，单位为人民币/股。 |
| change | Decimal | 否 | 带符号的价格变动，单位为人民币/股。 |
| changeRatio | Decimal | 否 | 变动比率；10% 表示为 0.10。 |
| turnoverRatio | Decimal | 否 | 比率小数；12% 表示为 0.12。 |
| amount | Decimal | 否 | 成交金额，单位为人民币。 |
| limitUpTime | str | 否 | 标准化的涨停时间字段。 |
| state | str | 否 | 数据源定义的状态标签。 |
| isConsecutiveLimitUp | bool | 否 | 数据源是否将该行标记为连续涨停。 |
| consecutiveLimitUpCount | int \| None | 是 | 标准化的连续涨停次数。 |
| previousConsecutiveLimitUpCount | int \| None | 是 | 数据源报告的此前连续涨停次数。 |
| themeId | int \| None | 是 | 数据源主题标识。 |
| themeName | str \| None | 是 | 数据源主题名称。 |
| floatShares | int | 否 | 流通股本。 |
| totalShares | int | 否 | 总股本。 |
| marketCap | Decimal | 否 | 总市值，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketConsecutiveLimitUpRequest
request = MarketConsecutiveLimitUpRequest()
result = fx.market.consecutive_limit_up(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`aigupiao.series_limit_up`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.daily_replay(...)`

返回请求日期的 Jiyangongshe 主题和股票观测日复盘。

**Dataset：** `market.daily_replay`
**Schema 版本：** `1.0`
**已实现的 Provider：** `jiuyangongshe.daily_replay`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.daily_replay(request: 'MarketDailyReplayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDailyReplayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDailyReplayRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketDailyReplayRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| requestedDate | date | 是 | — | 从 daily-replay 数据源请求的日期。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketDailyReplayData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketDailyReplayData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| requestedDate | date | 否 | 从 daily-replay 数据源请求的日期。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| themes | list[ReplayTheme] | 否 | 日复盘主题及其股票观测值。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`ReplayStock`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | 是 | — | 经 Provider 标准化的显示名称。 |
| limitUpTime | str \| None | 否 | None | 标准化的涨停时间字段。 |
| streakText | str \| None | 否 | None | 标准化的连续涨停描述。 |
| price | Decimal \| None | 否 | None | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| changeRatio | Decimal \| None | 否 | None | 变动比率；10% 表示为 0.10。 |
| day | int \| None | 否 | None | 标准化的天数字段。 |
| edition | int \| None | 否 | None | 标准化的版本字段。 |
| expound | str \| None | 否 | None | 标准化的说明字段。 |

**`ReplayTheme`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| themeName | str | 是 | — | 数据源主题名称。 |
| reason | str \| None | 否 | None | 标准化的原因字段。 |
| stockCount | int | 是 | — | 标准化的股票数量字段。 |
| sourceThemeId | str \| None | 否 | None | 标准化的数据源主题 id 字段。 |
| stocks | list[ReplayStock] | 否 | — | 与主题或复盘行关联的股票。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketDailyReplayRequest
request = MarketDailyReplayRequest(requestedDate=date(2026, 9, 18))
result = fx.market.daily_replay(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`jiuyangongshe.daily_replay`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

**可选依赖：** 安装 playwright 对应的源码 extra。从源码目录安装时使用 `python -m pip install ".[jygs]"`；发布到 PyPI 后使用对应的 `finchx[jygs]` extra。

**身份验证：** 选定的 Provider 需要已认证的 session。对于 Jiyangongshe Provider，请设置 `JYGS_SESSION` 并安装 `jygs` extra。

### `fx.market.dragon_tiger_detail(...)`

返回一条龙虎榜记录的买卖席位详情。

**Dataset：** `market.dragon_tiger_detail`
**Schema 版本：** `1.0`
**已实现的 Provider：** `aigupiao.dragon_tiger`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.dragon_tiger_detail(request: 'MarketDragonTigerDetailRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerDetailData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerDetailRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketDragonTigerDetailRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 是 | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| tradeId | str | 是 | — | 标准化的交易 id 字段。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketDragonTigerDetailData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketDragonTigerDetailData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| tradeId | str | 否 | 标准化的交易 id 字段。 |
| closePrice | Decimal | 否 | 每股价格；货币为人民币。 |
| changeRatio | Decimal | 否 | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | 否 | 成交金额，单位为人民币。 |
| totalBuy | Decimal | 否 | 金额，单位为人民币。 |
| totalSell | Decimal | 否 | 金额，单位为人民币。 |
| totalNet | Decimal | 否 | 金额，单位为人民币。 |
| explanation | str | 否 | 标准化的说明字段。 |
| commentKind | str \| None | 是 | 标准化的评论类型字段。 |
| commentObjectId | str \| None | 是 | 标准化的评论对象 id 字段。 |
| buySeats | list[DragonTigerSeat] | 否 | 标准化的买方席位字段。 |
| sellSeats | list[DragonTigerSeat] | 否 | 标准化的卖方席位字段。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`DragonTigerSeat`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| rank | int | 是 | — | 根据数据源数组顺序推导。 |
| seatName | str | 是 | — | 标准化的席位名称字段。 |
| sourceSeatCode | str \| None | 否 | None | 标准化的数据源席位代码字段。 |
| hasDetails | bool \| None | 否 | None | 标准化的详情存在标志字段。 |
| buyAmount | Decimal | 是 | — | 金额，单位为人民币。 |
| sellAmount | Decimal | 是 | — | 金额，单位为人民币。 |
| netAmount | Decimal | 是 | — | 金额，单位为人民币。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketDragonTigerDetailRequest
request = MarketDragonTigerDetailRequest(
    instrumentId=instrument_id, tradeDate=date(2026, 9, 18), tradeId="demo-trade-id"
)
result = fx.market.dragon_tiger_detail(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`aigupiao.dragon_tiger`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.dragon_tiger_list(...)`

返回指定交易日的 Aigupiao 龙虎榜列表。

**Dataset：** `market.dragon_tiger_list`
**Schema 版本：** `1.0`
**已实现的 Provider：** `aigupiao.dragon_tiger`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.dragon_tiger_list(request: 'MarketDragonTigerListRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerListData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerListRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketDragonTigerListRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketDragonTigerListData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketDragonTigerListData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| tradeId | str | 否 | 标准化的交易 id 字段。 |
| closePrice | Decimal | 否 | 每股价格；货币为人民币。 |
| changeRatio | Decimal | 否 | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | 否 | 成交金额，单位为人民币。 |
| totalBuy | Decimal | 否 | 金额，单位为人民币。 |
| totalNet | Decimal | 否 | 金额，单位为人民币。 |
| explanation | str | 否 | 标准化的说明字段。 |
| threeDayFlag | str \| None | 是 | 标准化的三日标志字段。 |
| themeId | int \| None | 是 | 数据源主题标识。 |
| themeName | str \| None | 是 | 数据源主题名称。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketDragonTigerListRequest
request = MarketDragonTigerListRequest(tradeDate=date(2026, 9, 18))
result = fx.market.dragon_tiger_list(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`aigupiao.dragon_tiger`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.equity_intraday(...)`

返回一个标的和交易时段的股票盘中观测值。

**Dataset：** `market.equity_intraday`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.equity_intraday(request: 'EquityIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | EquityIntradayRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `EquityIntradayRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[EquityIntradayData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `EquityIntradayData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | 否 | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | 否 | 成交量，以整股数表示。 |
| amount | str | 否 | 成交金额，单位为人民币。 |
| cumulativeVolume | int | 否 | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | 否 | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import EquityIntradayRequest
request = EquityIntradayRequest(instrumentId=instrument_id)
result = fx.market.equity_intraday(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.intraday`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.equity_intraday_5d(...)`

返回一个标的的数据源五日股票盘中序列。

**Dataset：** `market.equity_intraday_5d`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.equity_intraday_5d(request: 'EquityIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | EquityIntraday5dRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `EquityIntraday5dRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[EquityIntradayData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `EquityIntradayData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | 否 | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | 否 | 成交量，以整股数表示。 |
| amount | str | 否 | 成交金额，单位为人民币。 |
| cumulativeVolume | int | 否 | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | 否 | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import EquityIntraday5dRequest
request = EquityIntraday5dRequest(instrumentId=instrument_id)
result = fx.market.equity_intraday_5d(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.intraday`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.fund_flow_daily(...)`

返回一个标的的每日主力资金净流入观测值。

**Dataset：** `market.fund_flow_daily`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.fund_flow_daily(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowDailyData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketFundFlowRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketFundFlowDailyData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketFundFlowDailyData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| mainNetInflow | Decimal | 否 | 主力资金净流入，单位为人民币。 |
| close | Decimal | 否 | 收盘价格；按标的类型计为每股人民币或指数点。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketFundFlowRequest
request = MarketFundFlowRequest(instrumentId=instrument_id)
result = fx.market.fund_flow_daily(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.fund_flow`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.fund_flow_intraday(...)`

返回一个标的的累计盘中资金流观测值。

**Dataset：** `market.fund_flow_intraday`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.fund_flow_intraday(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketFundFlowRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketFundFlowIntradayData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketFundFlowIntradayData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | 否 | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| cumulativeMainNetInflow | Decimal | 否 | 累计主力资金净流入，单位为人民币。 |
| cumulativeRetailNetInflow | Decimal | 否 | 累计散户资金净流入，单位为人民币。 |
| cumulativeSuperLargeNetInflow | Decimal | 否 | 累计超大单净流入，单位为人民币。 |
| cumulativeLargeNetInflow | Decimal | 否 | 累计大单净流入，单位为人民币。 |
| cumulativeMediumNetInflow | Decimal | 否 | 累计中单净流入，单位为人民币。 |
| cumulativeSmallNetInflow | Decimal | 否 | 累计小单净流入，单位为人民币。 |
| cumulativeMainInflow | Decimal | 否 | 累计主力资金流入，单位为人民币。 |
| cumulativeMainOutflow | Decimal | 否 | 累计主力资金流出，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketFundFlowRequest
request = MarketFundFlowRequest(instrumentId=instrument_id)
result = fx.market.fund_flow_intraday(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.fund_flow`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.fund_flow_snapshot(...)`

返回当前资金流快照及分类级别的流入/流出金额。

**Dataset：** `market.fund_flow_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.fund_flow_snapshot(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketFundFlowRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketFundFlowSnapshotData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketFundFlowSnapshotData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| mainNetInflow | Decimal | 否 | 主力资金净流入，单位为人民币。 |
| mainInflow | Decimal | 否 | 主力资金流入，单位为人民币。 |
| mainOutflow | Decimal | 否 | 主力资金流出，单位为人民币。 |
| mainInflowRate | Decimal | 否 | 主力资金流入比率。 |
| mainOutflowRate | Decimal | 否 | 主力资金流出比率。 |
| retailInflow | Decimal | 否 | 散户资金流入，单位为人民币。 |
| retailOutflow | Decimal | 否 | 散户资金流出，单位为人民币。 |
| retailInflowRate | Decimal | 否 | 散户资金流入比率。 |
| retailOutflowRate | Decimal | 否 | 散户资金流出比率。 |
| superLargeNetInflow | Decimal | 否 | 超大单净流入，单位为人民币。 |
| largeNetInflow | Decimal | 否 | 大单净流入，单位为人民币。 |
| mediumNetInflow | Decimal | 否 | 中单净流入，单位为人民币。 |
| smallNetInflow | Decimal | 否 | 小单净流入，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketFundFlowRequest
request = MarketFundFlowRequest(instrumentId=instrument_id)
result = fx.market.fund_flow_snapshot(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.fund_flow`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.index_intraday(...)`

返回一个指数标的和交易时段的盘中指数观测值。

**Dataset：** `market.index_intraday`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.index_intraday(request: 'IndexIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | IndexIntradayRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `IndexIntradayRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[IndexIntradayData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `IndexIntradayData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | 否 | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | 否 | 成交量，以整股数表示。 |
| amount | str | 否 | 成交金额，单位为人民币。 |
| cumulativeVolume | int | 否 | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | 否 | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import IndexIntradayRequest
request = IndexIntradayRequest(instrumentId=index_id)
result = fx.market.index_intraday(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.intraday`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.index_intraday_5d(...)`

返回一个指数标的的数据源五日盘中指数序列。

**Dataset：** `market.index_intraday_5d`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.index_intraday_5d(request: 'IndexIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | IndexIntraday5dRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `IndexIntraday5dRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[IndexIntradayData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `IndexIntradayData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | 否 | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | 否 | 成交量，以整股数表示。 |
| amount | str | 否 | 成交金额，单位为人民币。 |
| cumulativeVolume | int | 否 | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | 否 | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import IndexIntraday5dRequest
request = IndexIntraday5dRequest(instrumentId=index_id)
result = fx.market.index_intraday_5d(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.intraday`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.industry_comparison(...)`

使用腾讯行业契约，将一个标的与其行业汇总值及更广泛市场进行比较。

**Dataset：** `market.industry_comparison`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.industry`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.industry_comparison(request: 'MarketIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketIndustryComparisonData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketIndustryComparisonRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketIndustryComparisonRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketIndustryComparisonData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketIndustryComparisonData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| industry | IndustryIdentity | 否 | 数据源提供的行业标签。 |
| instrumentValues | IndustryComparisonValues | 否 | 该比较使用的标的数值。 |
| industryRanks | IndustryComparisonRanks | 否 | 数据源提供的行业相对排名。 |
| industryAggregate | IndustryAggregate | 否 | 数据源提供的行业汇总值。 |
| marketAggregate | MarketAggregate | 否 | 数据源提供的广泛市场汇总值。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`IndustryAggregate`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | 否 | None | 标准化的市盈率字段。 |
| earningsPerShare | Decimal \| None | 否 | None | 腾讯 mgsy，单位为每股人民币；此处不提供报告期语义。 |
| marketCapitalization | Decimal \| None | 否 | None | 总市值，单位为人民币。 |
| count | int \| None | 否 | None | 标准化的数量字段。 |

**`IndustryComparisonRanks`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarningsRank | int \| None | 否 | None | 标准化的市盈率排名字段。 |
| earningsPerShareRank | int \| None | 否 | None | 标准化的每股收益排名字段。 |
| marketCapitalizationRank | int \| None | 否 | None | 标准化的市值排名字段。 |

**`IndustryComparisonValues`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | 否 | None | 标准化的市盈率字段。 |
| earningsPerShare | Decimal \| None | 否 | None | 腾讯 mgsy，单位为每股人民币；此处不提供报告期语义。 |
| marketCapitalization | Decimal \| None | 否 | None | 总市值，单位为人民币。 |

**`IndustryIdentity`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| providerNamespace | 'tencent_hypm' | 是 | — | 保留为公开身份的数据源特定 namespace。 |
| providerIndustryId | str | 是 | — | 标准化的 Provider 行业 id 字段。 |
| name | str | 是 | — | 经 Provider 标准化的显示名称。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`MarketAggregate`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | 否 | None | 标准化的市盈率字段。 |
| earningsPerShare | Decimal \| None | 否 | None | 腾讯 mgsy，单位为每股人民币；此处不提供报告期语义。 |
| marketCapitalization | Decimal \| None | 否 | None | 总市值，单位为人民币。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketIndustryComparisonRequest
request = MarketIndustryComparisonRequest(instrumentId=instrument_id)
result = fx.market.industry_comparison(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.industry`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.instrument_sector_snapshot(...)`

返回附加到一个标的上的腾讯地域、行业和概念标签。

**Dataset：** `market.instrument_sector_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.sector`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.instrument_sector_snapshot(request: 'MarketInstrumentSectorSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketInstrumentSectorSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketInstrumentSectorSnapshotRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketInstrumentSectorSnapshotRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketInstrumentSectorSnapshotData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketInstrumentSectorSnapshotData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| sectors | list[InstrumentSectorEntry] | 否 | 附加到该标的的板块标签条目。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`InstrumentSectorEntry`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | 是 | — | 板块标签类型：area、industry 或 concept。 |
| sectorName | str | 是 | — | Provider 提供的板块名称。 |
| providerNamespace | 'tencent_plate' | 是 | — | 保留为公开身份的数据源特定 namespace。 |
| providerSectorId | str | 是 | — | 数据源特定的板块标识。 |
| level | int \| None | 否 | None | 盘口档位编号或板块层级，取决于具体模型。 |
| tag | str \| None | 否 | None | 可选的数据源标签。 |
| changePct | Decimal \| None | 否 | None | 腾讯 zdf 从百分点转换得到的比率小数。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketInstrumentSectorSnapshotRequest
request = MarketInstrumentSectorSnapshotRequest(instrumentId=instrument_id)
result = fx.market.instrument_sector_snapshot(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.sector`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.stock_keyword(...)`

返回一个股票的数据源热门关键词/概念快照；这是结构化的数据源排名数据，不是 NLP 抽取结果。

**Dataset：** `market.stock_keyword`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.stockrank`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.stock_keyword(request: 'MarketStockKeywordRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStockKeywordData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketStockKeywordRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketStockKeywordRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketStockKeywordData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketStockKeywordData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| keywords | list[StockKeywordEntry] | 否 | 数据源排名的热门关键词/概念条目。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`StockKeywordEntry`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| keywordName | str | 是 | — | 数据源提供的关键词或概念名称。 |
| providerNamespace | 'eastmoney_stockrank' | 是 | — | 保留为公开身份的数据源特定 namespace。 |
| providerKeywordId | str | 是 | — | 数据源范围内的关键词/概念标识。 |
| hitCount | int | 是 | — | 东方财富数据源命中数量；它不是推断出的 NLP 热度分数。 |
| calculatedAt | datetime | 是 | — | 数据源报告的关键词观测计算时间。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketStockKeywordRequest
result = fx.market.stock_keyword(MarketStockKeywordRequest(instrumentId=instrument_id))
print(result.data.data["keywords"])
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.stockrank`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

**关键词语义：** 传入完整的 `InstrumentId`（需要时包含 exchange）；此接口没有单独代码快捷方式。Provider 支持 SSE、SZSE 和 BSE 路由，合法的空 BSE 关键词列表仍表示请求成功。这是数据源排名的结构化关键词/概念数据：`keywordName`、`providerKeywordId`、`hitCount` 和 `calculatedAt` 保留东方财富语义。它不是 NLP 关键词抽取，`hitCount` 也不是推断出的热度分数。

### `fx.market.limit_down_pool(...)`

返回指定交易日的东方财富跌停池。

**Dataset：** `market.limit_down_pool`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.limit_down_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.limit_down_pool(request: 'MarketLimitDownPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitDownPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketLimitDownPoolRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketLimitDownPoolRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketLimitDownPoolData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketLimitDownPoolData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| changeRate | Decimal | 否 | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | 否 | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | 否 | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | 否 | 总市值，单位为人民币。 |
| priceEarningsRatio | Decimal \| None | 是 | 数据源报告的动态市盈率倍数。 |
| turnoverRate | Decimal | 否 | 换手率；百分比以小数表示。 |
| limitDownQueueAmount | Decimal \| None | 是 | 跌停价上的排队金额，单位为人民币。 |
| lastLimitDownTime | str \| None | 是 | 数据源当地时间格式的最后跌停时间。 |
| boardTradedAmount | Decimal \| None | 是 | 跌停价成交金额，单位为人民币。 |
| consecutiveLimitDownDays | int | 否 | 数据源报告的连续跌停次数。 |
| limitDownOpenCount | int | 否 | 数据源记录的跌停开板次数。 |
| industry | str | 否 | 数据源提供的行业标签。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketLimitDownPoolRequest
request = MarketLimitDownPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.limit_down_pool(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.push2ex.limit_down_pool`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.limit_up_pool(...)`

返回指定交易日的东方财富涨停池。

**Dataset：** `market.limit_up_pool`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.limit_up_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.limit_up_pool(request: 'MarketLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitUpPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketLimitUpPoolRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketLimitUpPoolRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketLimitUpPoolData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketLimitUpPoolData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| changeRate | Decimal | 否 | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | 否 | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | 否 | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | 否 | 总市值，单位为人民币。 |
| turnoverRate | Decimal | 否 | 换手率；百分比以小数表示。 |
| consecutiveLimitUpDays | int | 否 | 数据源报告的连续涨停次数。 |
| firstLimitUpTime | str \| None | 是 | 数据源当地时间格式的首次涨停时间。 |
| lastLimitUpTime | str \| None | 是 | 数据源当地时间格式的最后涨停时间。 |
| limitUpQueueAmount | Decimal \| None | 是 | 涨停价上的排队金额，单位为人民币。 |
| limitUpBreakCount | int | 否 | 数据源观测到的开板次数。 |
| industry | str | 否 | 数据源提供的行业标签。 |
| limitUpStats | MarketLimitUpStats | 否 | 数据源定义的涨停历史统计。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`MarketLimitUpStats`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | 是 | — | 标准化的回看天数字段。 |
| limitUpCount | int | 是 | — | 涨停标的数量。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketLimitUpPoolRequest
request = MarketLimitUpPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.limit_up_pool(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.push2ex.limit_up_pool`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.ohlcv(...)`

返回一个标的在指定日期范围内的日 OHLCV K 线。

**Dataset：** `market.klines`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.klines`, `sohu.finance.klines`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.ohlcv(instrument_id: 'InstrumentId | None' = None, start_date: 'date | None' = None, end_date: 'date | None' = None, adjustment: 'KlineAdjustment | None' = None, *, request: 'KlinesRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketKlineData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 否 | None | 目标标的的完整 InstrumentId。 |
| start_date | date \| None | 否 | None | 包含起始日期。 |
| end_date | date \| None | 否 | None | 包含结束日期。 |
| adjustment | KlineAdjustment \| None | 否 | None | 可选的 KlineAdjustment；除非计算型偏离值能力在内部选择 QFQ，否则默认值为 None。 |
| request | KlinesRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `KlinesRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| startDate | date | 是 | — | 请求范围或选定窗口的包含起始日期。 |
| endDate | date | 是 | — | 请求范围或选定窗口的包含结束日期。 |
| adjustment | Literal['none', 'qfq', 'hfq', 'not_applicable'] \| None | 否 | None | K 线序列使用的复权模式。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketKlineData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketKlineData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| barDate | date | 否 | OHLCV K 线表示的交易日期。 |
| open | Decimal | 否 | 交易时段开盘价，单位为每股人民币。 |
| high | Decimal | 否 | 交易时段最高价，单位为每股人民币。 |
| low | Decimal | 否 | 交易时段最低价，单位为每股人民币。 |
| close | Decimal | 否 | 收盘价格；按标的类型计为每股人民币或指数点。 |
| volume | int | 否 | 成交量，以整股数表示。 |
| amount | Decimal \| None | 是 | 成交金额，单位为人民币。 |
| adjustment | Literal['none', 'qfq', 'hfq', 'not_applicable'] | 否 | K 线序列使用的复权模式。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
result = fx.market.ohlcv(
    instrument_id, date(2026, 9, 1), date(2026, 9, 18), adjustment=KlineAdjustment.QFQ
)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.klines`, `sohu.finance.klines`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.orderbook(...)`

返回一个标的当前的买价和卖价档位。

**Dataset：** `market.orderbook`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.quote`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.orderbook(request: 'MarketOrderbookRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketOrderbookData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketOrderbookRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketOrderbookRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketOrderbookData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketOrderbookData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| bids | list[OrderbookLevel] | 否 | 买方盘口档位。 |
| asks | list[OrderbookLevel] | 否 | 卖方盘口档位。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`OrderbookLevel`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| level | int | 是 | — | 盘口档位编号或板块层级，取决于具体模型。 |
| price | Decimal | 是 | — | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| size | int | 是 | — | 非负整股数量。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketOrderbookRequest
request = MarketOrderbookRequest(instrumentId=instrument_id)
result = fx.market.orderbook(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.quote`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.quote(...)`

以每个标的一条标准化记录的形式返回选定的 A 股行情范围。

**Dataset：** `market.quote`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.quote(*, universe: 'InstrumentUniverse' = <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'>, request: 'MarketQuoteUniverseRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | 否 | <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'> | InstrumentUniverse 选择；公开行情便捷方法默认使用 CN_A_SHARE。 |
| request | MarketQuoteUniverseRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketQuoteUniverseRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | Literal['cn_a_share'] | 是 | — | 要查询的标的范围。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketQuoteData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketQuoteData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str \| None | 是 | 经 Provider 标准化的显示名称。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| priceChange | Decimal \| None | 是 | 带符号的绝对价格变动，单位为每股人民币。 |
| changeRate | Decimal \| None | 是 | 变动比率；10% 表示为 0.10。 |
| changeRate5d | Decimal \| None | 是 | 数据源指定的五日价格变动比率。 |
| changeRate10d | Decimal \| None | 是 | 数据源指定的十日价格变动比率。 |
| changeRate20d | Decimal \| None | 是 | 数据源指定的二十日价格变动比率。 |
| changeRate60d | Decimal \| None | 是 | 数据源指定的六十日价格变动比率。 |
| changeRate52w | Decimal \| None | 是 | 数据源指定的 52 周价格变动比率。 |
| changeRateYtd | Decimal \| None | 是 | 年初至今价格变动比率。 |
| amplitude | Decimal \| None | 是 | 盘中价格振幅，以比率小数表示。 |
| volumeRatio | Decimal \| None | 是 | 数据源成交量比率，为无量纲倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | 是 | 成交量，以整股数表示。 |
| amount | Decimal \| None | 是 | 成交金额，单位为人民币。 |
| turnoverRate | Decimal \| None | 是 | 换手率；百分比以小数表示。 |
| marketCap | Decimal \| None | 是 | 总市值，单位为人民币。 |
| floatMarketCap | Decimal \| None | 是 | 流通市值，单位为人民币。 |
| peTtm | Decimal \| None | 是 | 数据源提供时的滚动市盈率倍数。 |
| mainNetInflow | Decimal \| None | 是 | 主力资金净流入，单位为人民币。 |
| mainInflow | Decimal \| None | 是 | 主力资金流入，单位为人民币。 |
| mainOutflow | Decimal \| None | 是 | 主力资金流出，单位为人民币。 |
| mainInflow5d | Decimal \| None | 是 | 标准化的五日主力流入字段。 |
| mainOutflow5d | Decimal \| None | 是 | 标准化的五日主力流出字段。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
result = fx.market.quote()
for record in result.data:
    print(record.data["instrumentId"], record.data["price"])
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.market`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.quote_snapshot(...)`

返回一个标的的行情快照，包括数据源报告的时间戳。

**Dataset：** `market.quote_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.quote`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.quote_snapshot(request: 'MarketQuoteSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketQuoteSnapshotRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketQuoteSnapshotRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketQuoteSnapshotData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketQuoteSnapshotData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| previousClose | Decimal \| None | 是 | 前一交易时段收盘价，单位为人民币/股。 |
| open | Decimal \| None | 是 | 交易时段开盘价，单位为每股人民币。 |
| high | Decimal \| None | 是 | 交易时段最高价，单位为每股人民币。 |
| low | Decimal \| None | 是 | 交易时段最低价，单位为每股人民币。 |
| priceChange | Decimal \| None | 是 | 带符号的绝对价格变动，单位为每股人民币。 |
| changeRate | Decimal \| None | 是 | 变动比率；10% 表示为 0.10。 |
| volume | int \| None | 是 | 成交量，以整股数表示。 |
| amount | Decimal \| None | 是 | 成交金额，单位为人民币。 |
| sourceTimestamp | datetime | 否 | 数据源报告的行情时间戳；它不同于 FinchX 的 capturedAt。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketQuoteSnapshotRequest
request = MarketQuoteSnapshotRequest(instrumentId=instrument_id)
result = fx.market.quote_snapshot(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.quote`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.ranking(...)`

按一个受支持的市场指标和方向对选定的行情范围排名。

**Dataset：** `market.ranking`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.ranking(request: 'MarketRankingRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketRankingData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketRankingRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketRankingRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | Literal['cn_a_share'] | 是 | — | 要查询的标的范围。 |
| criterion | Literal['turnover', 'change_percent', 'volume'] | 是 | — | 用于选择指标的排名条件。 |
| direction | Literal['ascending', 'descending'] | 是 | — | 排名方向。 |
| limit | int \| None | 是 | — | 请求的排名行数上限。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketRankingData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketRankingData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str \| None | 是 | 经 Provider 标准化的显示名称。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| priceChange | Decimal \| None | 是 | 带符号的绝对价格变动，单位为每股人民币。 |
| changeRate | Decimal \| None | 是 | 变动比率；10% 表示为 0.10。 |
| changeRate5d | Decimal \| None | 是 | 数据源指定的五日价格变动比率。 |
| changeRate10d | Decimal \| None | 是 | 数据源指定的十日价格变动比率。 |
| changeRate20d | Decimal \| None | 是 | 数据源指定的二十日价格变动比率。 |
| changeRate60d | Decimal \| None | 是 | 数据源指定的六十日价格变动比率。 |
| changeRate52w | Decimal \| None | 是 | 数据源指定的 52 周价格变动比率。 |
| changeRateYtd | Decimal \| None | 是 | 年初至今价格变动比率。 |
| amplitude | Decimal \| None | 是 | 盘中价格振幅，以比率小数表示。 |
| volumeRatio | Decimal \| None | 是 | 数据源成交量比率，为无量纲倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | 是 | 成交量，以整股数表示。 |
| amount | Decimal \| None | 是 | 成交金额，单位为人民币。 |
| turnoverRate | Decimal \| None | 是 | 换手率；百分比以小数表示。 |
| marketCap | Decimal \| None | 是 | 总市值，单位为人民币。 |
| floatMarketCap | Decimal \| None | 是 | 流通市值，单位为人民币。 |
| peTtm | Decimal \| None | 是 | 数据源提供时的滚动市盈率倍数。 |
| mainNetInflow | Decimal \| None | 是 | 主力资金净流入，单位为人民币。 |
| mainInflow | Decimal \| None | 是 | 主力资金流入，单位为人民币。 |
| mainOutflow | Decimal \| None | 是 | 主力资金流出，单位为人民币。 |
| mainInflow5d | Decimal \| None | 是 | 标准化的五日主力流入字段。 |
| mainOutflow5d | Decimal \| None | 是 | 标准化的五日主力流出字段。 |
| universe | Literal['cn_a_share'] | 否 | 要查询的标的范围。 |
| direction | Literal['ascending', 'descending'] | 否 | 排名方向。 |
| position | int | 否 | 返回排名中从 1 开始计数的位置。 |
| metric | Any | 否 | 该行使用的排名指标。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`ChangePercentRankingMetric`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| criterion | 'change_percent' | 是 | — | 用于选择指标的排名条件。 |
| value | Decimal | 是 | — | 比率小数而不是百分点：4.24% 表示为 0.0424。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`TurnoverRankingMetric`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| criterion | 'turnover' | 是 | — | 用于选择指标的排名条件。 |
| value | Decimal | 是 | — | 金额，单位为人民币。 |

**`VolumeRankingMetric`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| criterion | 'volume' | 是 | — | 用于选择指标的排名条件。 |
| value | int | 是 | — | 非负整股数量。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketRankingRequest
from finchx.datasets import MarketRankingRequest
request = MarketRankingRequest(
    universe="cn_a_share", criterion="turnover", direction="descending", limit=10
)
result = fx.market.ranking(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.market`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.market.sentiment(...)`

返回 Aigupiao 市场情绪快照及数据源定义的比率/计数。

**Dataset：** `market.sentiment_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `aigupiao.market_sentiment`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.sentiment(request: 'MarketSentimentRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketSentimentData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketSentimentRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketSentimentRequest`。其字段如下：

该请求模型没有字段；可以不传 request 对象，直接调用接口使用默认请求行为。

#### 返回值

公开方法的类型标注为 `FetchResult[MarketSentimentData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `MarketSentimentData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| marketTemperature | str | 否 | Aigupiao 数据源定义的市场温度；不是物理温度，也不是通用比率。 |
| totalTurnover | Decimal \| None | 是 | 标准化的总换手字段。 |
| forecastedTurnover | Decimal \| None | 是 | 数据源预测的换手值，不是实际观测的换手值。 |
| turnoverChangeAmount | Decimal \| None | 是 | 数据源报告的相对前一日换手金额变动。 |
| blastBreakRatio | Decimal \| None | 是 | 数据源定义的开板比率；FinchX 不重建其分母。 |
| previousLimitUpBreakChangeRatio | Decimal \| None | 是 | 数据源定义的此前开板表现比率。 |
| stopTradingCount | int | 否 | 停牌观测值数量。 |
| oneLimitUpCount | int | 否 | 一次涨停观测值数量。 |
| twoLimitUpCount | int | 否 | 两次涨停观测值数量。 |
| threeLimitUpCount | int | 否 | 三次涨停观测值数量。 |
| highLimitUpCount | int | 否 | 高位涨停观测值数量。 |
| twoLimitUpPromotionRatio | Decimal \| None | 是 | 数据源定义的推广比率；FinchX 不复现其分母。 |
| threeLimitUpPromotionRatio | Decimal \| None | 是 | 数据源定义的推广比率；FinchX 不复现其分母。 |
| highLimitUpPromotionRatio | Decimal \| None | 是 | 数据源定义的推广比率；FinchX 不复现其分母。 |
| previousLimitUpThemeChangeRatio | Decimal \| None | 是 | 数据源定义的此前涨停组表现比率。 |
| previousConsecutiveLimitUpThemeChangeRatio | Decimal \| None | 是 | 数据源定义的此前连续涨停组表现比率。 |



#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketSentimentRequest
request = MarketSentimentRequest()
result = fx.market.sentiment(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`aigupiao.market_sentiment`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.strong_pool(...)`

返回指定交易日的东方财富强势股池。

**Dataset：** `market.strong_pool`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.strong_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.strong_pool(request: 'MarketStrongPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStrongPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketStrongPoolRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketStrongPoolRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketStrongPoolData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketStrongPoolData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| price | Decimal | 否 | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| limitUpPrice | Decimal | 否 | 当前交易时段的涨停价，单位为每股人民币。 |
| changeRate | Decimal | 否 | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | 否 | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | 否 | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | 否 | 总市值，单位为人民币。 |
| turnoverRate | Decimal | 否 | 换手率；百分比以小数表示。 |
| isSixtyDayHigh | bool | 否 | 数据源是否将该标的标记为 60 日新高。 |
| selectionReason | Literal['sixty_day_high', 'recent_multiple_limit_ups', 'sixty_day_high_and_recent_multiple_limit_ups'] | 否 | 强势股池选择的数据源定义原因。 |
| volumeRatio | Decimal | 否 | 数据源成交量比率，为无量纲倍数；2.35 表示 2.35 倍。 |
| industry | str | 否 | 数据源提供的行业标签。 |
| limitUpStats | MarketStrongPoolStats | 否 | 数据源定义的涨停历史统计。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`MarketStrongPoolStats`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | 是 | — | 标准化的回看天数字段。 |
| limitUpCount | int | 是 | — | 涨停标的数量。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketStrongPoolRequest
request = MarketStrongPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.strong_pool(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.push2ex.strong_pool`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

### `fx.market.yesterday_limit_up_pool(...)`

返回前一交易日涨停池中股票的当日观测值。

**Dataset：** `market.yesterday_limit_up_pool`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.yesterday_limit_up_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.yesterday_limit_up_pool(request: 'MarketYesterdayLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketYesterdayLimitUpPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketYesterdayLimitUpPoolRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `MarketYesterdayLimitUpPoolRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | 是 | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketYesterdayLimitUpPoolData]`。FetchResult.data：tuple[StandardRecord, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `MarketYesterdayLimitUpPoolData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | 否 | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | 否 | 经 Provider 标准化的显示名称。 |
| currentPrice | Decimal | 否 | 当前交易时段价格，单位为每股人民币。 |
| currentLimitUpPrice | Decimal | 否 | 当前交易时段的涨停价，单位为每股人民币。 |
| currentChangeRate | Decimal | 否 | 当前交易时段的变动比率；10% 表示为 0.10。 |
| currentAmount | Decimal | 否 | 当前交易时段成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | 否 | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | 否 | 总市值，单位为人民币。 |
| currentTurnoverRate | Decimal | 否 | 当前交易时段的换手比率。 |
| currentAmplitude | Decimal | 否 | 当前交易时段的价格振幅，以比率小数表示。 |
| yesterdayFirstLimitUpTime | str \| None | 是 | 前一交易时段的首次涨停时间，使用当地市场 HH:MM:SS 格式。 |
| yesterdayConsecutiveLimitUpDays | int | 否 | 此前交易时段的连续涨停次数。 |
| industry | str | 否 | 数据源提供的行业标签。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import MarketYesterdayLimitUpPoolRequest
request = MarketYesterdayLimitUpPoolRequest(tradeDate=date(2026, 9, 18))
result = fx.market.yesterday_limit_up_pool(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.push2ex.yesterday_limit_up_pool`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

## `fundamental`

公司概况、财务摘要、收入和行业比较。

### `fx.fundamental.company_profile(...)`

返回一个标的的标准化公司概况。

**Dataset：** `fundamental.company_profile`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.company_profile(instrument_id: 'InstrumentId | None' = None, *, request: 'CompanyProfileRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CompanyProfileData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 否 | None | 目标标的的完整 InstrumentId。 |
| request | CompanyProfileRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `CompanyProfileRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[CompanyProfileData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `CompanyProfileData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| companyName | str \| None | 是 | 标准化的公司名称字段。 |
| businessDescription | str \| None | 是 | 标准化的业务描述字段。 |
| issuePrice | Decimal \| None | 是 | 每股人民币。Tencent gsjj.jg 保留为数据源候选字段。 |
| listingDate | date \| None | 是 | 标准化的上市日期字段。 |



#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import CompanyProfileRequest
request = CompanyProfileRequest(instrumentId=instrument_id)
result = fx.fundamental.company_profile(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.fundamental.financial_summary(...)`

返回一个标的在可用报告期内的标准化摘要指标。

**Dataset：** `fundamental.financial_summary`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.financial_summary(request: 'FinancialSummaryRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialSummaryData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FinancialSummaryRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `FinancialSummaryRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[FinancialSummaryData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `FinancialSummaryData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| periods | list[FinancialSummaryPeriod] | 否 | 报告期或持有人期间记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`FinancialSummaryPeriod`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date \| None | 否 | None | 可选的财务报告期末日期。 |
| reportedPeriodLabel | str | 是 | — | 数据源报告期标签。 |
| periodType | Literal['annual', 'interim', 'unknown'] | 是 | — | 报告期分类。 |
| eps | Decimal \| None | 否 | None | 可用时的每股收益。 |
| revenue | Decimal \| None | 否 | None | 可用时的收入金额。 |
| revenueGrowth | Decimal \| None | 否 | None | 收入增长比率。 |
| netProfit | Decimal \| None | 否 | None | 可用时的净利润金额。 |
| netProfitGrowth | Decimal \| None | 否 | None | 净利润增长比率。 |
| bookValuePerShare | Decimal \| None | 否 | None | 每股账面价值。 |
| netAssets | Decimal \| None | 否 | None | 净资产金额。 |
| goodwill | Decimal \| None | 否 | None | 商誉金额。 |
| goodwillToNetAssets | Decimal \| None | 否 | None | 商誉与净资产比率。 |
| roe | Decimal \| None | 否 | None | 净资产收益率。 |
| debtRatio | Decimal \| None | 否 | None | 负债比率。 |
| grossMargin | Decimal \| None | 否 | None | 毛利率。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import FinancialSummaryRequest
request = FinancialSummaryRequest(instrumentId=instrument_id)
result = fx.fundamental.financial_summary(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.fundamental.industry_comparison(...)`

返回一个标的数据源提供的行业比较指标。

**Dataset：** `fundamental.industry_comparison`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.industry_comparison(request: 'FundamentalIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndustryComparisonData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FundamentalIndustryComparisonRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `IndustryComparisonRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[IndustryComparisonData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `IndustryComparisonData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| industryName | str \| None | 是 | 标准化的行业名称字段。 |
| metrics | list[IndustryComparisonMetric] | 否 | 行业比较指标记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`IndustryComparisonMetric`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| metric | Literal['eps', 'revenue', 'net_profit', 'book_value_per_share', 'roe', 'debt_ratio', 'gross_margin', 'revenue_growth', 'net_profit_growth', 'market_cap', 'pe', 'pb', 'dividend_yield'] | 是 | — | 该行使用的排名指标。 |
| metricBasis | Literal['financial_period', 'market_snapshot'] | 是 | — | 允许值：financial_period、market_snapshot。 |
| companyValue | Decimal \| None | 否 | None | 标准化的公司值字段。 |
| industryAvg | Decimal \| None | 否 | None | 标准化的行业平均值字段。 |
| industryMax | Decimal \| None | 否 | None | 标准化的行业最大值字段。 |
| industryMin | Decimal \| None | 否 | None | 标准化的行业最小值字段。 |
| periodEnd | date \| None | 否 | None | 可选的财务报告期末日期。 |
| reportedPeriodLabel | str | 是 | — | 数据源报告期标签。 |
| observationAt | datetime \| None | 否 | None | 标准化的观测时间字段。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import IndustryComparisonRequest
request = IndustryComparisonRequest(instrumentId=instrument_id)
result = fx.fundamental.industry_comparison(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.fundamental.revenue_breakdown(...)`

返回公司的标准化收入拆分记录。

**Dataset：** `fundamental.revenue_breakdown`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.revenue_breakdown(request: 'RevenueBreakdownRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RevenueBreakdownData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | RevenueBreakdownRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `RevenueBreakdownRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[RevenueBreakdownData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `RevenueBreakdownData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| breakdowns | list[RevenueBreakdownRow] | 否 | 收入拆分记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`RevenueBreakdownRow`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| reportedPeriodLabel | str | 是 | — | 数据源报告期标签。 |
| periodEnd | date \| None | 否 | None | 可选的财务报告期末日期。 |
| dimension | Literal['product', 'region', 'industry'] | 是 | — | 允许值：product、region、industry。 |
| itemName | str | 是 | — | 标准化的项目名称字段。 |
| revenue | Decimal \| None | 是 | — | 可用时的收入金额。 |
| revenueShare | Decimal \| None | 否 | None | 标准化的收入占比字段。 |
| currency | 'CNY' | 是 | — | 货币代码。 |
| sourceGroup | Literal['detail', 'others'] | 是 | — | 允许值：detail、others。 |
| isRollup | bool | 是 | — | 标准化的汇总标志字段。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import RevenueBreakdownRequest
request = RevenueBreakdownRequest(instrumentId=instrument_id)
result = fx.fundamental.revenue_breakdown(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

## `financial`

Structured financial statements。

### `fx.financial.statements(...)`

返回请求报表类型和期间的标准化财务报表行项目。

**Dataset：** `financial.statement`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tonghuashun.financial`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.financial.statements(instrument_id: 'InstrumentId | None' = None, statement_type: 'StatementType | None' = None, *, period_end: 'date | None' = None, max_periods: 'int | None' = None, request: 'FinancialStatementRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialStatementData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | 否 | None | 目标标的的完整 InstrumentId。 |
| statement_type | StatementType \| None | 否 | None | StatementType 选择。 |
| period_end | date \| None | 否 | None | 可选的报告期末日期。 |
| max_periods | int \| None | 否 | None | 可选的财务期间数量上限。 |
| request | FinancialStatementRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `FinancialStatementRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | 是 | — | 财务报表类型。 |
| periodEnd | date \| None | 否 | None | 可选的财务报告期末日期。 |
| maxPeriods | int \| None | 否 | None | 标准化的最大期间数字段。 |

#### 返回值

公开方法的类型标注为 `FetchResult[FinancialStatementData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `FinancialStatementData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | 否 | 财务报表类型。 |
| periods | list[FinancialStatementPeriod] | 否 | 报告期或持有人期间记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`FinancialStatementLineItem`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| lineItemId | str | 是 | — | 标准化的行项目 id 字段。 |
| sourceName | str | 是 | — | 标准化的数据源名称字段。 |
| sourceUnit | str | 是 | — | 标准化的数据源单位字段。 |
| sourceValue | str \| bool \| int \| Decimal \| None | 是 | — | 标准化的 数据源 值 字段。 |
| value | Decimal \| None | 否 | None | 标准化的 值 字段。 |
| currency | Currency \| None | 否 | None | 货币代码。 |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | 否 | None | 标准化的缺失原因字段。 |

**`FinancialStatementPeriod`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date | 是 | — | 可选的财务报告期末日期。 |
| lineItems | list[FinancialStatementLineItem] | 是 | — | 财务报表行项目。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import FinancialStatementRequest
request = FinancialStatementRequest(instrumentId=instrument_id, statementType="income_statement")
result = fx.financial.statements(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tonghuashun.financial`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

## `news`

Individual-stock news search references。

### `fx.news.search(...)`

搜索个股新闻元数据并返回可序列化的文档引用。

**Dataset：** `news.document`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.news.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, sort: 'str' = 'published_desc', request: 'NewsSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[NewsDocumentRef, ...]]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | 否 | None | 用于文档搜索的 InstrumentId 或受支持的六位代码文本。 |
| page | int | 否 | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| page_size | int | 否 | 20 | 页面大小；默认值为 20，并受请求模型上限约束。 |
| max_results | int \| None | 否 | None | 可选的结果数量上限。 |
| since | date \| datetime \| None | 否 | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | 否 | None | 可选的、包含边界的最晚发布时间。 |
| sort | str | 否 | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |
| request | NewsSearchRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `NewsSearchRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| page | int | 否 | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| pageSize | int | 否 | 20 | 标准化的页面大小字段。 |
| maxResults | int \| None | 否 | None | 标准化的最大结果数​​字段。 |
| since | date \| datetime \| None | 否 | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | 否 | None | 可选的、包含边界的最晚发布时间。 |
| sort | Literal['published_desc', 'published_asc'] | 否 | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |

#### 返回值

公开方法的类型标注为 `FetchResult[NewsDocumentData]`。FetchResult.data：tuple[NewsDocumentRef, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `NewsDocumentData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| documentId | str | 否 | FinchX 文档身份。 |
| sourceDocumentId | str | 否 | 数据源侧文档身份。 |
| title | str | 否 | 文档标题。 |
| contentText | str \| None | 是 | 内容可用时获取到的文档正文。 |
| summary | str \| None | 是 | 可用时的数据源简短摘要。 |
| publishedAt | datetime \| None | 是 | 数据源提供的发布时间戳。 |
| sourceOccurrences | list[NewsSourceOccurrence] | 否 | 文档标准化过程中保留的数据源侧出现记录。 |
| url | AnyUrl | 否 | 标准化的 URL 字段。 |
| originalUrl | AnyUrl \| None | 是 | 提供时的原始文档 URL。 |
| contentAvailable | bool | 否 | 该结果中是否包含文档内容。 |
| source | str \| None | 是 | 标准化的数据源字段。 |
| relatedInstruments | list[InstrumentId] | 否 | 与文档相关的标的。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |

**`NewsSourceOccurrence`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| providerId | str | 是 | — | 标准化的 Provider id。 |
| sourceDocumentId | str | 是 | — | 数据源侧文档身份。 |
| sourceUrl | AnyUrl \| None | 否 | None | 直接数据源 URL 或数据源接口引用。 |
| documentUrl | AnyUrl \| None | 否 | None | 标准化的文档 URL 字段。 |
| publishedAt | datetime \| None | 否 | None | 数据源提供的发布时间戳。 |
| capturedAt | datetime | 是 | — | FinchX 获取数据源观测值时的带时区时间。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
result = fx.news.search(instrument_id, page_size=10)
for ref in result.data:
    print(ref.title, ref.published_at)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

## `disclosure`

Individual-stock disclosure search references。

### `fx.disclosure.search(...)`

搜索个股公告并返回可序列化的通知引用。

**Dataset：** `disclosure.document`
**Schema 版本：** `1.0`
**已实现的 Provider：** `eastmoney.disclosure`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.disclosure.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, categories: 'Sequence[str] | None' = None, sort: 'str' = 'published_desc', request: 'DisclosureSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[DisclosureDocumentRef, ...]]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | 否 | None | 用于文档搜索的 InstrumentId 或受支持的六位代码文本。 |
| page | int | 否 | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| page_size | int | 否 | 20 | 页面大小；默认值为 20，并受请求模型上限约束。 |
| max_results | int \| None | 否 | None | 可选的结果数量上限。 |
| since | date \| datetime \| None | 否 | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | 否 | None | 可选的、包含边界的最晚发布时间。 |
| categories | Sequence[str] \| None | 否 | None | 可选的公告类别代码或名称。 |
| sort | str | 否 | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |
| request | DisclosureSearchRequest \| None | 否 | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `DisclosureSearchRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| page | int | 否 | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| pageSize | int | 否 | 20 | 标准化的页面大小字段。 |
| maxResults | int \| None | 否 | None | 标准化的最大结果数​​字段。 |
| since | date \| datetime \| None | 否 | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | 否 | None | 可选的、包含边界的最晚发布时间。 |
| sort | Literal['published_desc', 'published_asc'] | 否 | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |
| categories | list[str] \| None | 否 | None | 公告类别。 |

#### 返回值

公开方法的类型标注为 `FetchResult[DisclosureDocumentData]`。FetchResult.data：tuple[DisclosureDocumentRef, ...]。每个 StandardRecord 内的 `data` 数据载荷是 `DisclosureDocumentData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| documentId | str | 否 | FinchX 文档身份。 |
| sourceDocumentId | str | 否 | 数据源侧文档身份。 |
| title | str | 否 | 文档标题。 |
| contentText | str \| None | 是 | 内容可用时获取到的文档正文。 |
| noticeDate | date | 否 | 公告日期。 |
| publishedAt | datetime \| None | 是 | 数据源提供的发布时间戳。 |
| sourceRecordedAt | datetime \| None | 是 | 数据源侧记录的时间戳，不同于发布时间和获取时间。 |
| categories | list[DisclosureCategory] | 否 | 公告类别。 |
| relatedInstruments | list[InstrumentId] | 否 | 与文档相关的标的。 |
| contentAvailable | bool | 否 | 该结果中是否包含文档内容。 |
| pdfAvailable | bool | 否 | 是否有可用的 PDF 附件。 |
| originalDocumentUrl | AnyUrl | 否 | 原始公告文档 URL。 |
| attachments | list[DisclosureAttachment] | 否 | 公告附件。 |
| sourceType | str \| None | 是 | 数据源文档类型标签。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`DisclosureAttachment`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| sequence | int \| None | 否 | None | 标准化的序号字段。 |
| size | int \| None | 否 | None | 标准化的大小字段。 |
| attachmentType | str \| None | 否 | None | 标准化的附件类型字段。 |
| url | AnyUrl | 是 | — | 标准化的 URL 字段。 |
| webUrl | AnyUrl \| None | 否 | None | 标准化的网页 URL 字段。 |

**`DisclosureCategory`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| name | str | 是 | — | 经 Provider 标准化的显示名称。 |
| source | str | 否 | 'eastmoney' | 标准化的数据源字段。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
result = fx.disclosure.search(instrument_id, page_size=10)
for ref in result.data:
    print(ref.title, ref.notice_date)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`eastmoney.disclosure`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

## `ownership`

资本结构和股东快照。

### `fx.ownership.capital_snapshot(...)`

返回一个标的的总股本和流通股本数量。

**Dataset：** `ownership.capital_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.ownership.capital_snapshot(request: 'CapitalSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CapitalSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | CapitalSnapshotRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `CapitalSnapshotRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[CapitalSnapshotData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `CapitalSnapshotData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| totalShares | int \| None | 是 | 总股本。 |
| floatShares | int \| None | 是 | 流通股本。 |



#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import CapitalSnapshotRequest
request = CapitalSnapshotRequest(instrumentId=instrument_id)
result = fx.ownership.capital_snapshot(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.ownership.float_holder(...)`

返回一个标的的流通股东记录，也可以指定日期。

**Dataset：** `ownership.float_holder`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.float_holder`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.ownership.float_holder(request: 'FloatHolderRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FloatHolderData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FloatHolderRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `FloatHolderRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| asOf | datetime \| None | 否 | None | 查询或计算的可选截止日期。 |

#### 返回值

公开方法的类型标注为 `FetchResult[FloatHolderData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `FloatHolderData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| periods | list[FloatHolderPeriod] | 否 | 报告期或持有人期间记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`FloatHolderPeriod`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date | 是 | — | 可选的财务报告期末日期。 |
| publishedAt | datetime | 是 | — | 数据源提供的发布时间戳。 |
| rows | list[FloatHolderRow] | 是 | — | 标准化的 行 字段。 |

**`FloatHolderRow`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| rank | int | 是 | — | 根据腾讯 rows 数组顺序推导。 |
| holderId | str \| None | 否 | None | 标准化的持有人 id 字段。 |
| holderName | str | 是 | — | 标准化的持有人名称字段。 |
| shares | int | 是 | — | 股份数量。 |
| holderType | str | 是 | — | 标准化的持有人类型字段。 |
| floatShareRatio | Decimal \| None | 否 | None | 标准化的流通股份比率字段。 |
| previousShares | int \| None | 否 | None | 标准化的此前股份字段。 |
| shareChange | int \| None | 否 | None | 带符号的股份数量变动。 |
| isNewTopFloatHolderEntry | bool \| None | 否 | None | 多股票相邻期间校验后根据 bdms=1 推导。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import FloatHolderRequest
request = FloatHolderRequest(instrumentId=instrument_id)
result = fx.ownership.float_holder(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.float_holder`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.ownership.holder_summary_snapshot(...)`

返回股东数量、集中度和户均指标。

**Dataset：** `ownership.holder_summary_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.ownership.holder_summary_snapshot(request: 'HolderSummarySnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[HolderSummarySnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | HolderSummarySnapshotRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `HolderSummarySnapshotRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[HolderSummarySnapshotData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `HolderSummarySnapshotData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| shareholderCount | int \| None | 是 | 股东数量。 |
| averageSharesPerHolder | Decimal \| None | 是 | 每位持有人的平均股份数。 |
| shareholderCountChange | Decimal \| None | 是 | 股东数量变动比率，不是绝对数量差值。 |
| top10FloatHolderRatio | Decimal \| None | 是 | 前十大流通股东占比。 |
| top10HolderRatio | Decimal \| None | 是 | 前十大股东占比。 |



#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import HolderSummarySnapshotRequest
request = HolderSummarySnapshotRequest(instrumentId=instrument_id)
result = fx.ownership.holder_summary_snapshot(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

## `company`

管理层名册和管理层持股变动观测值。

### `fx.company.executive_share_change(...)`

返回标准化的管理层持股变动事件。

**Dataset：** `company.executive_share_change`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.company.executive_share_change(request: 'ExecutiveShareChangeRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveShareChangeData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | ExecutiveShareChangeRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `ExecutiveShareChangeRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[ExecutiveShareChangeData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `ExecutiveShareChangeData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| changes | list[ExecutiveShareChange] | 否 | 标准化的变动记录字段。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`ExecutiveShareChange`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| eventDate | date \| None | 否 | None | 管理层持股变动事件日期。 |
| personName | str \| None | 否 | None | 管理层或相关人员姓名。 |
| shareChange | int \| None | 否 | None | 带符号的股份数量变动。 |
| averagePrice | Decimal \| None | 否 | None | 事件平均价格，单位为每股人民币。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import ExecutiveShareChangeRequest
request = ExecutiveShareChangeRequest(instrumentId=instrument_id)
result = fx.company.executive_share_change(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.company.executive_snapshot(...)`

返回标准化的管理层名册和职务。

**Dataset：** `company.executive_snapshot`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.company.executive_snapshot(request: 'ExecutiveSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | ExecutiveSnapshotRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `ExecutiveSnapshotRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[ExecutiveSnapshotData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `ExecutiveSnapshotData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| executives | list[ExecutiveEntry] | 否 | 管理层条目。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`ExecutiveEntry`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| name | str | 是 | — | 经 Provider 标准化的显示名称。 |
| roles | list[str] | 是 | — | 管理层职务。 |
| shares | int \| None | 否 | None | 股份数量。 |
| compensation | Decimal \| None | 否 | None | 提供时的薪酬金额。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import ExecutiveSnapshotRequest
request = ExecutiveSnapshotRequest(instrumentId=instrument_id)
result = fx.company.executive_snapshot(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

## `corporate_action`

分红和股份回购观测值。

### `fx.corporate_action.dividend(...)`

返回标准化的分红事件及其数据源字段。

**Dataset：** `corporate_action.dividend`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.corporate_action.dividend(request: 'DividendRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DividendData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | DividendRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `DividendRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[DividendData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `DividendData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| dividends | list[Dividend] | 否 | 分红事件记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`Dividend`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| fiscalYear | int \| None | 否 | None | 标准化的财务年度字段。 |
| announcementDate | date \| None | 否 | None | 标准化的公告日期字段。 |
| stockDividendPer10 | Decimal \| None | 否 | None | 标准化的每十股股票股利字段。 |
| capitalizationPer10 | Decimal \| None | 否 | None | 标准化的每十股资本公积转增字段。 |
| cashDividendPer10 | Decimal \| None | 否 | None | 标准化的每十股现金股利字段。 |
| rightsIssuePer10 | Decimal \| None | 否 | None | 标准化的每十股配股字段。 |
| recordDate | date \| None | 否 | None | 公司行为记录日期。 |
| exDate | date \| None | 否 | None | 除息或除权日期。 |
| description | str \| None | 否 | None | 标准化的说明字段。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import DividendRequest
request = DividendRequest(instrumentId=instrument_id)
result = fx.corporate_action.dividend(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

### `fx.corporate_action.repurchase(...)`

返回标准化的股份回购事件及其数据源字段。

**Dataset：** `corporate_action.repurchase`
**Schema 版本：** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.corporate_action.repurchase(request: 'RepurchaseRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RepurchaseData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | RepurchaseRequest | 是 | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | 否 | None | 严格指定 Provider id。只使用指定的 Provider。（仅限关键字参数） |
| use_cache | bool \| None | 否 | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限关键字参数） |

类型化请求模型为 `RepurchaseRequest`。其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | 是 | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[RepurchaseData]`。FetchResult.data：StandardRecord。每个 StandardRecord 内的 `data` 数据载荷是 `RepurchaseData` schema 如下。

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | 否 | 经 Provider 标准化的标的 symbol 字符串。 |
| repurchases | list[Repurchase] | 否 | 回购事件记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`Repurchase`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| repurchaseDate | date \| None | 否 | None | 回购日期。 |
| quantity | int \| None | 否 | None | 回购股份数量。 |
| averagePrice | Decimal \| None | 否 | None | 事件平均价格，单位为每股人民币。 |
| currency | Currency \| None | 否 | None | 货币代码。 |
| fundAmount | Decimal \| None | 否 | None | 该事件已使用或公告的资金金额，单位为人民币。 |
| market | str \| None | 否 | None | FinchX 市场标识。 |


#### 示例

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
index_id = InstrumentId(
    code="000001",
    market=Market.CN_A,
    kind=InstrumentKind.INDEX,
    exchange=Exchange.SSE,
)
from finchx.datasets import RepurchaseRequest
request = RepurchaseRequest(instrumentId=instrument_id)
result = fx.corporate_action.repurchase(request)
```

#### Provider 行为与注意事项

当前 Registry 实现的 Provider 为：`tencent.finance.qq.f10`。除非提供 `provider=`，否则 Provider 选择由运行时策略控制。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

## 计算能力：`market.deviation`

`market.deviation` 是确定性的本地计算，不是外部 Provider。它复用交易日历和 Kline Dataset 调用，将 `provider=None` 设置在返回的 `FetchResult` 上，并保留底层 provenance。

### `fx.market.deviation(...)`

根据 FinchX 交易日历和 K 线输入，计算基于收盘价的 10 日和/或 30 日股票相对基准偏离值。

**Dataset 身份：** `market.deviation`（计算型，schema 版本 `1.0`）
**外部 Provider：** 无；该计算使用交易日历能力和 K 线。
**默认 Kline Provider：** `tencent.finance.qq.klines`。

#### 方法签名

```python
fx.market.deviation(instrument_id: 'InstrumentId', *, windows: 'Sequence[int]' = (10, 30), as_of: 'date | None' = None, window_convention: 'DeviationWindowConvention' = <DeviationWindowConvention.MAX_DEVIATION_SCAN: 'max_deviation_scan'>, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DeviationData]'
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId | 是 | — | 完整的 SSE/SZSE A 股股票身份。 |
| windows | Sequence[int] | 否 | (10, 30) | 仅接受 10 和 30；重复项会被拒绝。 |
| as_of | date \| None | 否 | None | 截止日期；使用不晚于该截止日期的最近已完成交易时段。 |
| window_convention | DeviationWindowConvention | 否 | max_deviation_scan | `strict_exchange_window` 或 `max_deviation_scan`。 |
| provider | str \| None | 否 | None | 严格指定 Kline Provider。交易日历查询仍使用运行时选择的日历 Provider。 |
| use_cache | bool \| None | 否 | None | 传递给底层交易日历和 Kline 获取调用。 |

#### 计算规则

对每个请求的窗口，`deviation = stock_return - benchmark_return`，其中每个收益率均根据选定基准的收盘价/指数点和已完成的结束日期计算。默认的 `max_deviation_scan` 选择使该差值最大的合资格起点；`strict_exchange_window` 使用按交易所形状确定的起点。10 日阈值为 `+1.00` 和 `-0.50`；30 日阈值为 `+2.00` 和 `-0.70`。这些是比率，因此 `0.03` 表示 3%。正偏离值表示股票在选定窗口内跑赢基准；负偏离值表示跑输。

股票输入使用腾讯 QFQ 日 K 线收盘价；基准是未复权指数序列。结果报告 `priceBasis="qfq_stock__raw_index"`、`calculationMode="official_close"` 和规则版本 `cn-a-exchange-2026-07-06+finchx-v1`。它不会作为独立的偏离值 Provider 发起网络请求，但会调用底层交易日历和 K 线能力。

支持的基准映射：SSE `60xxxx` → SSE A Share Index `000002`；SSE `68xxxx` → SSE STAR 50 Index `000688`；SZSE `00xxxx` → SZSE A Share Index `399107`；SZSE `30xxxx` → ChiNext Composite Index `399102`。BSE 和不支持的代码前缀会触发现有的无效请求边界。

#### 计算结果字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | 否 | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| board | str | 否 | 偏离值基准映射所使用的已解析板块分类。 |
| effectiveAsOf | date | 否 | 计算实际使用的最近已完成交易时段。 |
| calculationMode | 'official_close' | 否 | 冻结的计算模式；v1 为 official_close。 |
| priceBasis | 'qfq_stock__raw_index' | 否 | 冻结的价格口径；v1 为 qfq_stock__raw_index。 |
| ruleVersion | str | 否 | 偏离值计算规则集的版本。 |
| windows | list[DeviationWindowData] | 否 | 每个请求窗口的计算观测值。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`DeviationWindowData`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| windowDays | Literal[10, 30] | 是 | — | 选定的偏离值窗口：10 或 30 个交易日。 |
| windowConvention | DeviationWindowConvention | 是 | — | 窗口解释：strict_exchange_window 或 max_deviation_scan。 |
| tradingSessions | int | 是 | — | 计算使用的对齐交易时段数量。 |
| startDate | date | 是 | — | 请求范围或选定窗口的包含起始日期。 |
| baselineDate | date | 是 | — | 紧邻选定窗口起点之前的交易时段。 |
| endDate | date | 是 | — | 请求范围或选定窗口的包含结束日期。 |
| startPrice | Decimal | 是 | — | 选定基准日期的股票价格。 |
| windowStartPrice | Decimal | 是 | — | 选定窗口起始日期的股票价格。 |
| currentPrice | Decimal | 是 | — | 当前交易时段价格，单位为每股人民币。 |
| benchmarkInstrument | InstrumentId | 是 | — | 作为基准使用的经审计指数标的。 |
| benchmarkName | str | 是 | — | 便于人类阅读的基准名称。 |
| benchmarkStart | Decimal | 是 | — | 选定基准日期的基准点位。 |
| benchmarkCurrent | Decimal | 是 | — | 计算结束日期的基准点位。 |
| stockReturn | Decimal | 是 | — | 从选定基准日期到结束日期的累计股票收益率。 |
| benchmarkReturn | Decimal | 是 | — | 从选定基准日期到结束日期的累计基准收益率。 |
| deviation | Decimal | 是 | — | 股票收益率减去基准收益率，以比率表示。 |
| upperThreshold | Decimal | 是 | — | 选定窗口的上偏离值阈值。 |
| lowerThreshold | Decimal | 是 | — | 选定窗口的下偏离值阈值。 |
| remainingToUpper | Decimal | 是 | — | 上阈值减去计算得到的偏离值。 |
| remainingToLower | Decimal | 是 | — | 计算得到的偏离值减去下阈值。 |
| upperTriggerPrice | Decimal | 是 | — | 在基准收益率保持不变时确定性的上触发价格估计。 |
| lowerTriggerPrice | Decimal | 是 | — | 在基准收益率保持不变时确定性的下触发价格估计。 |
| remainingPricePctToUpper | Decimal | 是 | — | 价格空间中到上触发估计值的距离。 |
| remainingPricePctToLower | Decimal | 是 | — | 价格空间中到下触发估计值的距离。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| code | str | 是 | — | 交易所特定的标的代码。 |
| market | Market | 是 | — | FinchX 市场标识。 |
| kind | InstrumentKind | 是 | — | 标的类型。 |
| exchange | Exchange \| None | 否 | None | Dataset 需要时使用的交易所身份。 |


#### 示例

```python
from datetime import date
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
for window in result.data.windows:
    print(window.window_days, window.deviation, window.benchmark_name)
```

计算型偏离值不是交易所官方公告、盘中估算、产品排除状态或触发状态。历史数据不足、缺少对齐收盘价、价格非正或标的身份不受支持时会产生错误，而不是零值。

## 可选依赖参考

| Extra | 包 | 能力 |
| --- | --- | --- |
| `calendar` | `pandas_market_calendars` | 可选的交易日历 Provider `pandas_market_calendars`。 |
| `jygs` | `playwright` | 需要身份验证的 `jiuyangongshe.daily_replay`；还需要 `JYGS_SESSION`。 |

从源码目录安装时，使用 `python -m pip install ".[calendar]"` 或 `python -m pip install ".[jygs]"`。发布到 PyPI 后，使用 `pip install "finchx[calendar]"` 或 `pip install "finchx[jygs]"`。

## 第三方数据说明

FinchX 提供访问和标准化第三方数据源的软件。FinchX 不重新分发第三方市场数据集。用户应自行遵守相应数据提供方的条款和政策。

## 许可证

FinchX 使用 Apache-2.0 许可证。第三方数据不包含在 FinchX 许可证中。
