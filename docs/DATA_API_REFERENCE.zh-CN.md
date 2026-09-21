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

`provider=` 是严格指定。提供 Provider 后只使用该 Provider id，失败时不会静默改用其他 Provider。未指定时，运行时策略控制重试和 Provider 选择。本文档只列出已实现的 Provider，不分配 primary 或 fallback 角色。

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

**Dataset:** `instrument`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.reference.instrument(instrument_id: 'InstrumentId | None' = None, *, request: 'InstrumentRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[InstrumentData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | 目标标的的完整 InstrumentId。 |
| request | InstrumentRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `InstrumentRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[InstrumentData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `InstrumentData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | No | 经 Provider 标准化的显示名称。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `trading_calendar`
**Schema version:** `1.0`
**已实现的 Provider：** `szse.official.calendar`, `pandas_market_calendars`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.reference.trading_calendar(start_date: 'date | None' = None, end_date: 'date | None' = None, *, market: 'Market' = <Market.CN_A: 'cn_a'>, request: 'TradingCalendarRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[TradingCalendarData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| start_date | date \| None | No | None | 包含起始日期。 |
| end_date | date \| None | No | None | 包含结束日期。 |
| market | Market | No | <Market.CN_A: 'cn_a'> | Market 枚举；公开交易日历契约默认使用 Market.CN_A。 |
| request | TradingCalendarRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `TradingCalendarRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| market | Literal['cn_a'] | Yes | — | FinchX 市场标识。 |
| startDate | date | Yes | — | 请求范围或选定窗口的包含起始日期。 |
| endDate | date | Yes | — | 请求范围或选定窗口的包含结束日期。 |

#### 返回值

公开方法的类型标注为 `FetchResult[TradingCalendarData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `TradingCalendarData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| date | date | No | 该行表示的自然日。 |
| isTradingDay | bool | No | 标准化的交易日标志字段。 |



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

**可选依赖：** 安装 pandas_market_calendars 对应的 source extra。从源码 checkout 安装时使用 `python -m pip install ".[calendar]"`；发布到 PyPI 后使用对应的 `finchx[calendar]` extra。

## `market`

行情、排名、池类、资金流、盘中数据、K 线、板块和市场情报。

### `fx.market.breadth(...)`

返回东方财富市场广度快照，包括上涨、下跌以及涨停/跌停数量。

**Dataset:** `market.breadth`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.breadth`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.breadth(request: 'MarketBreadthRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBreadthData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketBreadthRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketBreadthRequest`. 其字段如下：

该请求模型没有字段；可以不传 request 对象，直接调用接口使用默认请求行为。

#### 返回值

公开方法的类型标注为 `FetchResult[MarketBreadthData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketBreadthData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| advancing | int | No | 广度快照中的上涨标的数量或数值。 |
| declining | int | No | 广度快照中的下跌标的数量或数值。 |
| unchanged | int | No | 广度快照中的平盘标的数量或数值。 |
| total | int | No | 快照表示的标的总数。 |
| limitUpCount | int | No | 涨停标的数量。 |
| limitDownCount | int | No | 数量 limit-down instruments. |
| upOver10PercentCount | int | No | Count 的 instruments up more than 10%. |
| downOver10PercentCount | int | No | Count 的 instruments down more than 10%. |
| distribution | list[MarketBreadthDistributionEntry] | No | Breadth distribution buckets supplied by EastMoney. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`MarketBreadthDistributionEntry`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| bucket | MarketBreadthBucket | Yes | — | 标准化的 bucket 字段. |
| count | int | Yes | — | 数量 listed stocks in this 收益率 bucket. |


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

**Dataset:** `market.broken_limit_pool`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.broken_limit_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.broken_limit_pool(request: 'MarketBrokenLimitPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBrokenLimitPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketBrokenLimitPoolRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketBrokenLimitPoolRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketBrokenLimitPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketBrokenLimitPoolData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| limitUpPrice | Decimal | No | 当前交易时段的涨停价，单位为每股人民币。 |
| changeRate | Decimal | No | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | No | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | No | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | No | 总市值，单位为人民币。 |
| turnoverRate | Decimal | No | 换手率；百分比以小数表示。 |
| amplitude | Decimal | No | 盘中价格振幅，以比率小数表示。 |
| firstLimitUpTime | str \| None | Yes | 数据源当地时间格式的首次涨停时间。 |
| limitUpBreakCount | int | No | 数据源观测到的开板次数。 |
| industry | str | No | 数据源提供的行业标签。 |
| limitUpStats | MarketBrokenLimitPoolStats | No | 数据源定义的涨停历史统计。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`MarketBrokenLimitPoolStats`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | 标准化的回看天数字段。 |
| limitUpCount | int | Yes | — | 涨停标的数量。 |


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

**Dataset:** `market.consecutive_limit_up_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `aigupiao.series_limit_up`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.consecutive_limit_up(request: 'MarketConsecutiveLimitUpRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketConsecutiveLimitUpData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketConsecutiveLimitUpRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketConsecutiveLimitUpRequest`. 其字段如下：

该请求模型没有字段；可以不传 request 对象，直接调用接口使用默认请求行为。

#### 返回值

公开方法的类型标注为 `FetchResult[MarketConsecutiveLimitUpData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketConsecutiveLimitUpData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| lastPrice | Decimal | No | 最新的 价格 单位为人民币 每股. |
| change | Decimal | No | Signed 价格 变动 单位为人民币 每股. |
| changeRatio | Decimal | No | 变动比率；10% 表示为 0.10。 |
| turnoverRatio | Decimal | No | 比率小数；12% 表示为 0.12。 |
| amount | Decimal | No | 成交金额，单位为人民币。 |
| limitUpTime | str | No | 标准化的涨停时间字段。 |
| state | str | No | 数据源定义的 state label. |
| isConsecutiveLimitUp | bool | No | 数据源是否将该行标记为连续涨停。 |
| consecutiveLimitUpCount | int \| None | Yes | 标准化的 consecutive limit up 数量 字段. |
| previousConsecutiveLimitUpCount | int \| None | Yes | 数据源报告的此前连续涨停次数。 |
| themeId | int \| None | Yes | 数据源主题标识。 |
| themeName | str \| None | Yes | 数据源主题名称。 |
| floatShares | int | No | 流通股本。 |
| totalShares | int | No | 总股本。 |
| marketCap | Decimal | No | 总市值，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.daily_replay`
**Schema version:** `1.0`
**已实现的 Provider：** `jiuyangongshe.daily_replay`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.daily_replay(request: 'MarketDailyReplayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDailyReplayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDailyReplayRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketDailyReplayRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| requestedDate | date | Yes | — | 从 daily-replay 数据源请求的日期。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketDailyReplayData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketDailyReplayData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| requestedDate | date | No | 从 daily-replay 数据源请求的日期。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| themes | list[ReplayTheme] | No | 日复盘主题及其股票观测值。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`ReplayStock`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | Yes | — | 经 Provider 标准化的显示名称。 |
| limitUpTime | str \| None | No | None | 标准化的涨停时间字段。 |
| streakText | str \| None | No | None | 标准化的 streak text 字段. |
| price | Decimal \| None | No | None | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| changeRatio | Decimal \| None | No | None | 变动比率；10% 表示为 0.10。 |
| day | int \| None | No | None | 标准化的 day 字段. |
| edition | int \| None | No | None | 标准化的 edition 字段. |
| expound | str \| None | No | None | 标准化的 expound 字段. |

**`ReplayTheme`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| themeName | str | Yes | — | 数据源主题名称。 |
| reason | str \| None | No | None | 标准化的 reason 字段. |
| stockCount | int | Yes | — | 标准化的 stock 数量 字段. |
| sourceThemeId | str \| None | No | None | 标准化的 数据源 theme id 字段. |
| stocks | list[ReplayStock] | No | — | 与主题或复盘行关联的股票。 |


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

**可选依赖：** 安装 playwright 对应的 source extra。从源码 checkout 安装时使用 `python -m pip install ".[jygs]"`；发布到 PyPI 后使用对应的 `finchx[jygs]` extra。

**身份验证：** 选定的 Provider 需要已认证的 session。对于 Jiyangongshe Provider，请设置 `JYGS_SESSION` 并安装 `jygs` extra。

### `fx.market.dragon_tiger_detail(...)`

返回一条龙虎榜记录的买卖席位详情。

**Dataset:** `market.dragon_tiger_detail`
**Schema version:** `1.0`
**已实现的 Provider：** `aigupiao.dragon_tiger`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.dragon_tiger_detail(request: 'MarketDragonTigerDetailRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerDetailData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerDetailRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketDragonTigerDetailRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | Yes | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| tradeId | str | Yes | — | 标准化的交易 id 字段。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketDragonTigerDetailData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketDragonTigerDetailData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| tradeId | str | No | 标准化的交易 id 字段。 |
| closePrice | Decimal | No | 每股价格；货币为人民币。 |
| changeRatio | Decimal | No | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | No | 成交金额，单位为人民币。 |
| totalBuy | Decimal | No | 金额，单位为人民币。 |
| totalSell | Decimal | No | 金额，单位为人民币。 |
| totalNet | Decimal | No | 金额，单位为人民币。 |
| explanation | str | No | 标准化的说明字段。 |
| commentKind | str \| None | Yes | 标准化的 comment kind 字段. |
| commentObjectId | str \| None | Yes | 标准化的 comment object id 字段. |
| buySeats | list[DragonTigerSeat] | No | 标准化的 buy seats 字段. |
| sellSeats | list[DragonTigerSeat] | No | 标准化的 sell seats 字段. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`DragonTigerSeat`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| rank | int | Yes | — | 根据数据源数组顺序推导。 |
| seatName | str | Yes | — | 标准化的 seat name 字段. |
| sourceSeatCode | str \| None | No | None | 标准化的 数据源 seat code 字段. |
| hasDetails | bool \| None | No | None | 标准化的 has details 字段. |
| buyAmount | Decimal | Yes | — | 金额，单位为人民币。 |
| sellAmount | Decimal | Yes | — | 金额，单位为人民币。 |
| netAmount | Decimal | Yes | — | 金额，单位为人民币。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.dragon_tiger_list`
**Schema version:** `1.0`
**已实现的 Provider：** `aigupiao.dragon_tiger`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.dragon_tiger_list(request: 'MarketDragonTigerListRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerListData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerListRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketDragonTigerListRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketDragonTigerListData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketDragonTigerListData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| tradeId | str | No | 标准化的交易 id 字段。 |
| closePrice | Decimal | No | 每股价格；货币为人民币。 |
| changeRatio | Decimal | No | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | No | 成交金额，单位为人民币。 |
| totalBuy | Decimal | No | 金额，单位为人民币。 |
| totalNet | Decimal | No | 金额，单位为人民币。 |
| explanation | str | No | 标准化的说明字段。 |
| threeDayFlag | str \| None | Yes | 标准化的 three day flag 字段. |
| themeId | int \| None | Yes | 数据源主题标识。 |
| themeName | str \| None | Yes | 数据源主题名称。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.equity_intraday`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.equity_intraday(request: 'EquityIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | EquityIntradayRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `EquityIntradayRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[EquityIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `EquityIntradayData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | No | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | No | 成交量，以整股数表示。 |
| amount | str | No | 成交金额，单位为人民币。 |
| cumulativeVolume | int | No | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | No | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.equity_intraday_5d`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.equity_intraday_5d(request: 'EquityIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | EquityIntraday5dRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `EquityIntraday5dRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[EquityIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `EquityIntradayData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | No | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | No | 成交量，以整股数表示。 |
| amount | str | No | 成交金额，单位为人民币。 |
| cumulativeVolume | int | No | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | No | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.fund_flow_daily`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.fund_flow_daily(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowDailyData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketFundFlowRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketFundFlowDailyData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketFundFlowDailyData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| mainNetInflow | Decimal | No | 主力资金净流入，单位为人民币。 |
| close | Decimal | No | 收盘价格；按标的类型计为每股人民币或指数点。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.fund_flow_intraday`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.fund_flow_intraday(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketFundFlowRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketFundFlowIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketFundFlowIntradayData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | No | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| cumulativeMainNetInflow | Decimal | No | Cumulative main-fund net inflow 单位为人民币. |
| cumulativeRetailNetInflow | Decimal | No | Cumulative retail-fund net inflow 单位为人民币. |
| cumulativeSuperLargeNetInflow | Decimal | No | Cumulative super-large-order net inflow 单位为人民币. |
| cumulativeLargeNetInflow | Decimal | No | Cumulative large-order net inflow 单位为人民币. |
| cumulativeMediumNetInflow | Decimal | No | Cumulative medium-order net inflow 单位为人民币. |
| cumulativeSmallNetInflow | Decimal | No | Cumulative small-order net inflow 单位为人民币. |
| cumulativeMainInflow | Decimal | No | Cumulative main-fund inflow 单位为人民币. |
| cumulativeMainOutflow | Decimal | No | Cumulative main-fund outflow 单位为人民币. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.fund_flow_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.fund_flow`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.fund_flow_snapshot(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketFundFlowRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketFundFlowSnapshotData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketFundFlowSnapshotData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| mainNetInflow | Decimal | No | 主力资金净流入，单位为人民币。 |
| mainInflow | Decimal | No | 主力资金流入，单位为人民币。 |
| mainOutflow | Decimal | No | 主力资金流出，单位为人民币。 |
| mainInflowRate | Decimal | No | Main-fund inflow 比率. |
| mainOutflowRate | Decimal | No | Main-fund outflow 比率. |
| retailInflow | Decimal | No | Retail-fund inflow 单位为人民币. |
| retailOutflow | Decimal | No | Retail-fund outflow 单位为人民币. |
| retailInflowRate | Decimal | No | Retail-fund inflow 比率. |
| retailOutflowRate | Decimal | No | Retail-fund outflow 比率. |
| superLargeNetInflow | Decimal | No | Super-large-order net inflow 单位为人民币. |
| largeNetInflow | Decimal | No | Large-order net inflow 单位为人民币. |
| mediumNetInflow | Decimal | No | Medium-order net inflow 单位为人民币. |
| smallNetInflow | Decimal | No | Small-order net inflow 单位为人民币. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.index_intraday`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.index_intraday(request: 'IndexIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | IndexIntradayRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `IndexIntradayRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[IndexIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `IndexIntradayData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | No | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | No | 成交量，以整股数表示。 |
| amount | str | No | 成交金额，单位为人民币。 |
| cumulativeVolume | int | No | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | No | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.index_intraday_5d`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.intraday`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.index_intraday_5d(request: 'IndexIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | IndexIntraday5dRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `IndexIntraday5dRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[IndexIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `IndexIntradayData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| time | str | No | 观测值对应的数据源当地时间，通常为 HH：MM。 |
| price | str | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| volume | int | No | 成交量，以整股数表示。 |
| amount | str | No | 成交金额，单位为人民币。 |
| cumulativeVolume | int | No | 本交易时段累计成交量，以整股数表示。 |
| cumulativeAmount | str | No | 累计成交金额，单位为人民币。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.industry_comparison`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.industry`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.industry_comparison(request: 'MarketIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketIndustryComparisonData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketIndustryComparisonRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketIndustryComparisonRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketIndustryComparisonData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketIndustryComparisonData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| industry | IndustryIdentity | No | 数据源提供的行业标签。 |
| instrumentValues | IndustryComparisonValues | No | Instrument 值 使用的 in 该 comparison. |
| industryRanks | IndustryComparisonRanks | No | Industry-relative ranks supplied by 该 数据源. |
| industryAggregate | IndustryAggregate | No | Industry aggregate 值 supplied by 该 数据源. |
| marketAggregate | MarketAggregate | No | Broad-market aggregate 值 supplied by 该 数据源. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`IndustryAggregate`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | 标准化的市盈率字段。 |
| earningsPerShare | Decimal \| None | No | None | 腾讯 mgsy，单位为每股人民币；此处不提供报告期语义。 |
| marketCapitalization | Decimal \| None | No | None | 总市值，单位为人民币。 |
| count | int \| None | No | None | 标准化的 数量 字段. |

**`IndustryComparisonRanks`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| priceEarningsRank | int \| None | No | None | 标准化的 价格 earnings rank 字段. |
| earningsPerShareRank | int \| None | No | None | 标准化的 earnings 每股 rank 字段. |
| marketCapitalizationRank | int \| None | No | None | 标准化的 market capitalization rank 字段. |

**`IndustryComparisonValues`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | 标准化的市盈率字段。 |
| earningsPerShare | Decimal \| None | No | None | 腾讯 mgsy，单位为每股人民币；此处不提供报告期语义。 |
| marketCapitalization | Decimal \| None | No | None | 总市值，单位为人民币。 |

**`IndustryIdentity`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| providerNamespace | 'tencent_hypm' | Yes | — | 保留为公开身份的数据源特定 namespace。 |
| providerIndustryId | str | Yes | — | 标准化的 Provider industry id 字段. |
| name | str | Yes | — | 经 Provider 标准化的显示名称。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`MarketAggregate`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | 标准化的市盈率字段。 |
| earningsPerShare | Decimal \| None | No | None | 腾讯 mgsy，单位为每股人民币；此处不提供报告期语义。 |
| marketCapitalization | Decimal \| None | No | None | 总市值，单位为人民币。 |


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

**Dataset:** `market.instrument_sector_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.sector`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.instrument_sector_snapshot(request: 'MarketInstrumentSectorSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketInstrumentSectorSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketInstrumentSectorSnapshotRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketInstrumentSectorSnapshotRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketInstrumentSectorSnapshotData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketInstrumentSectorSnapshotData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| sectors | list[InstrumentSectorEntry] | No | Sector-tag entries attached to 该 instrument. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`InstrumentSectorEntry`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | Yes | — | Sector tag type： area, industry 或 concept. |
| sectorName | str | Yes | — | Provider sector name. |
| providerNamespace | 'tencent_plate' | Yes | — | 保留为公开身份的数据源特定 namespace。 |
| providerSectorId | str | Yes | — | 数据源特定的 sector 标识. |
| level | int \| None | No | None | 盘口档位编号或板块层级，取决于具体模型。 |
| tag | str \| None | No | None | 可选的 数据源 tag. |
| changePct | Decimal \| None | No | None | Tencent zdf converted 来自 percentage points to a 比率 fraction. |


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

**Dataset:** `market.stock_keyword`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.stockrank`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.stock_keyword(request: 'MarketStockKeywordRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStockKeywordData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketStockKeywordRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketStockKeywordRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketStockKeywordData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketStockKeywordData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| keywords | list[StockKeywordEntry] | No | 数据源排名的热门关键词/概念条目。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`StockKeywordEntry`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| keywordName | str | Yes | — | 数据源提供的关键词或概念名称。 |
| providerNamespace | 'eastmoney_stockrank' | Yes | — | 保留为公开身份的数据源特定 namespace。 |
| providerKeywordId | str | Yes | — | 数据源范围内的关键词/概念标识。 |
| hitCount | int | Yes | — | 东方财富数据源命中数量；它不是推断出的 NLP 热度分数。 |
| calculatedAt | datetime | Yes | — | 数据源报告的关键词观测计算时间。 |


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

**Dataset:** `market.limit_down_pool`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.limit_down_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.limit_down_pool(request: 'MarketLimitDownPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitDownPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketLimitDownPoolRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketLimitDownPoolRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketLimitDownPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketLimitDownPoolData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| changeRate | Decimal | No | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | No | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | No | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | No | 总市值，单位为人民币。 |
| priceEarningsRatio | Decimal \| None | Yes | 数据源报告的 dynamic 价格/earnings multiple. |
| turnoverRate | Decimal | No | 换手率；百分比以小数表示。 |
| limitDownQueueAmount | Decimal \| None | Yes | Amount queued at 该 limit-down 价格 单位为人民币. |
| lastLimitDownTime | str \| None | Yes | Last limit-down 时间 in 该 数据源 market-local 时间 format. |
| boardTradedAmount | Decimal \| None | Yes | Amount traded at 该 limit-down 价格 单位为人民币. |
| consecutiveLimitDownDays | int | No | Consecutive limit-down 数量 reported by 该 数据源. |
| limitDownOpenCount | int | No | 数量 limit-down openings recorded by 该 数据源. |
| industry | str | No | 数据源提供的行业标签。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.limit_up_pool`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.limit_up_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.limit_up_pool(request: 'MarketLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitUpPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketLimitUpPoolRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketLimitUpPoolRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketLimitUpPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketLimitUpPoolData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| changeRate | Decimal | No | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | No | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | No | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | No | 总市值，单位为人民币。 |
| turnoverRate | Decimal | No | 换手率；百分比以小数表示。 |
| consecutiveLimitUpDays | int | No | Consecutive limit-up 数量 reported by 该 数据源. |
| firstLimitUpTime | str \| None | Yes | 数据源当地时间格式的首次涨停时间。 |
| lastLimitUpTime | str \| None | Yes | Last limit-up 时间 in 该 数据源 market-local 时间 format. |
| limitUpQueueAmount | Decimal \| None | Yes | Amount queued at 该 limit-up 价格 单位为人民币. |
| limitUpBreakCount | int | No | 数据源观测到的开板次数。 |
| industry | str | No | 数据源提供的行业标签。 |
| limitUpStats | MarketLimitUpStats | No | 数据源定义的涨停历史统计。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`MarketLimitUpStats`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | 标准化的回看天数字段。 |
| limitUpCount | int | Yes | — | 涨停标的数量。 |


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

**Dataset:** `market.klines`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.klines`, `sohu.finance.klines`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.ohlcv(instrument_id: 'InstrumentId | None' = None, start_date: 'date | None' = None, end_date: 'date | None' = None, adjustment: 'KlineAdjustment | None' = None, *, request: 'KlinesRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketKlineData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | 目标标的的完整 InstrumentId。 |
| start_date | date \| None | No | None | 包含起始日期。 |
| end_date | date \| None | No | None | 包含结束日期。 |
| adjustment | KlineAdjustment \| None | No | None | 可选的 KlineAdjustment；除非计算型偏离值能力在内部选择 QFQ，否则默认值为 None。 |
| request | KlinesRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `KlinesRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| startDate | date | Yes | — | 请求范围或选定窗口的包含起始日期。 |
| endDate | date | Yes | — | 请求范围或选定窗口的包含结束日期。 |
| adjustment | Literal['none', 'qfq', 'hfq', 'not_applicable'] \| None | No | None | K 线序列使用的复权模式。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketKlineData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketKlineData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| barDate | date | No | OHLCV K 线表示的交易日期。 |
| open | Decimal | No | 交易时段开盘价，单位为每股人民币。 |
| high | Decimal | No | 交易时段最高价，单位为每股人民币。 |
| low | Decimal | No | 交易时段最低价，单位为每股人民币。 |
| close | Decimal | No | 收盘价格；按标的类型计为每股人民币或指数点。 |
| volume | int | No | 成交量，以整股数表示。 |
| amount | Decimal \| None | Yes | 成交金额，单位为人民币。 |
| adjustment | Literal['none', 'qfq', 'hfq', 'not_applicable'] | No | K 线序列使用的复权模式。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.orderbook`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.quote`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.orderbook(request: 'MarketOrderbookRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketOrderbookData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketOrderbookRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketOrderbookRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketOrderbookData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketOrderbookData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| bids | list[OrderbookLevel] | No | Bid-side order-book levels. |
| asks | list[OrderbookLevel] | No | Ask-side order-book levels. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`OrderbookLevel`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| level | int | Yes | — | 盘口档位编号或板块层级，取决于具体模型。 |
| price | Decimal | Yes | — | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| size | int | Yes | — | 非负整股数量。 |


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

**Dataset:** `market.quote`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.quote(*, universe: 'InstrumentUniverse' = <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'>, request: 'MarketQuoteUniverseRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | No | <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'> | InstrumentUniverse selection； 该 public quote convenience method defaults to CN_A_SHARE. |
| request | MarketQuoteUniverseRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketQuoteUniverseRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | Literal['cn_a_share'] | Yes | — | 要查询的标的范围。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketQuoteData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketQuoteData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str \| None | Yes | 经 Provider 标准化的显示名称。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| priceChange | Decimal \| None | Yes | 带符号的绝对价格变动，单位为每股人民币。 |
| changeRate | Decimal \| None | Yes | 变动比率；10% 表示为 0.10。 |
| changeRate5d | Decimal \| None | Yes | 数据源指定的五日价格变动比率。 |
| changeRate10d | Decimal \| None | Yes | 数据源指定的十日价格变动比率。 |
| changeRate20d | Decimal \| None | Yes | 数据源指定的二十日价格变动比率。 |
| changeRate60d | Decimal \| None | Yes | 数据源指定的六十日价格变动比率。 |
| changeRate52w | Decimal \| None | Yes | 数据源指定的 52 周价格变动比率。 |
| changeRateYtd | Decimal \| None | Yes | 年初至今价格变动比率。 |
| amplitude | Decimal \| None | Yes | 盘中价格振幅，以比率小数表示。 |
| volumeRatio | Decimal \| None | Yes | 数据源成交量比率，为无量纲倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | Yes | 成交量，以整股数表示。 |
| amount | Decimal \| None | Yes | 成交金额，单位为人民币。 |
| turnoverRate | Decimal \| None | Yes | 换手率；百分比以小数表示。 |
| marketCap | Decimal \| None | Yes | 总市值，单位为人民币。 |
| floatMarketCap | Decimal \| None | Yes | 流通市值，单位为人民币。 |
| peTtm | Decimal \| None | Yes | 数据源提供时的滚动市盈率倍数。 |
| mainNetInflow | Decimal \| None | Yes | 主力资金净流入，单位为人民币。 |
| mainInflow | Decimal \| None | Yes | 主力资金流入，单位为人民币。 |
| mainOutflow | Decimal \| None | Yes | 主力资金流出，单位为人民币。 |
| mainInflow5d | Decimal \| None | Yes | 标准化的五日主力流入字段。 |
| mainOutflow5d | Decimal \| None | Yes | 标准化的五日主力流出字段。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.quote_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.quote`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.quote_snapshot(request: 'MarketQuoteSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketQuoteSnapshotRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketQuoteSnapshotRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketQuoteSnapshotData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketQuoteSnapshotData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| previousClose | Decimal \| None | Yes | Previous-时段 close 单位为人民币 每股. |
| open | Decimal \| None | Yes | 交易时段开盘价，单位为每股人民币。 |
| high | Decimal \| None | Yes | 交易时段最高价，单位为每股人民币。 |
| low | Decimal \| None | Yes | 交易时段最低价，单位为每股人民币。 |
| priceChange | Decimal \| None | Yes | 带符号的绝对价格变动，单位为每股人民币。 |
| changeRate | Decimal \| None | Yes | 变动比率；10% 表示为 0.10。 |
| volume | int \| None | Yes | 成交量，以整股数表示。 |
| amount | Decimal \| None | Yes | 成交金额，单位为人民币。 |
| sourceTimestamp | datetime | No | 数据源报告的行情时间戳；它不同于 FinchX 的 capturedAt。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `market.ranking`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.market`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.market.ranking(request: 'MarketRankingRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketRankingData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketRankingRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketRankingRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| universe | Literal['cn_a_share'] | Yes | — | 要查询的标的范围。 |
| criterion | Literal['turnover', 'change_percent', 'volume'] | Yes | — | 用于选择指标的排名条件。 |
| direction | Literal['ascending', 'descending'] | Yes | — | 排名方向。 |
| limit | int \| None | Yes | — | Maximum 数量 ranking 行 请求的. |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketRankingData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketRankingData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| name | str \| None | Yes | 经 Provider 标准化的显示名称。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| priceChange | Decimal \| None | Yes | 带符号的绝对价格变动，单位为每股人民币。 |
| changeRate | Decimal \| None | Yes | 变动比率；10% 表示为 0.10。 |
| changeRate5d | Decimal \| None | Yes | 数据源指定的五日价格变动比率。 |
| changeRate10d | Decimal \| None | Yes | 数据源指定的十日价格变动比率。 |
| changeRate20d | Decimal \| None | Yes | 数据源指定的二十日价格变动比率。 |
| changeRate60d | Decimal \| None | Yes | 数据源指定的六十日价格变动比率。 |
| changeRate52w | Decimal \| None | Yes | 数据源指定的 52 周价格变动比率。 |
| changeRateYtd | Decimal \| None | Yes | 年初至今价格变动比率。 |
| amplitude | Decimal \| None | Yes | 盘中价格振幅，以比率小数表示。 |
| volumeRatio | Decimal \| None | Yes | 数据源成交量比率，为无量纲倍数；2.35 表示 2.35 倍。 |
| volume | int \| None | Yes | 成交量，以整股数表示。 |
| amount | Decimal \| None | Yes | 成交金额，单位为人民币。 |
| turnoverRate | Decimal \| None | Yes | 换手率；百分比以小数表示。 |
| marketCap | Decimal \| None | Yes | 总市值，单位为人民币。 |
| floatMarketCap | Decimal \| None | Yes | 流通市值，单位为人民币。 |
| peTtm | Decimal \| None | Yes | 数据源提供时的滚动市盈率倍数。 |
| mainNetInflow | Decimal \| None | Yes | 主力资金净流入，单位为人民币。 |
| mainInflow | Decimal \| None | Yes | 主力资金流入，单位为人民币。 |
| mainOutflow | Decimal \| None | Yes | 主力资金流出，单位为人民币。 |
| mainInflow5d | Decimal \| None | Yes | 标准化的五日主力流入字段。 |
| mainOutflow5d | Decimal \| None | Yes | 标准化的五日主力流出字段。 |
| universe | Literal['cn_a_share'] | No | 要查询的标的范围。 |
| direction | Literal['ascending', 'descending'] | No | 排名方向。 |
| position | int | No | 返回排名中从 1 开始计数的位置。 |
| metric | Any | No | 该行使用的排名指标。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`ChangePercentRankingMetric`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| criterion | 'change_percent' | Yes | — | 用于选择指标的排名条件。 |
| value | Decimal | Yes | — | 比率小数而不是百分点：4.24% 表示为 0.0424。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`TurnoverRankingMetric`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| criterion | 'turnover' | Yes | — | 用于选择指标的排名条件。 |
| value | Decimal | Yes | — | 金额，单位为人民币。 |

**`VolumeRankingMetric`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| criterion | 'volume' | Yes | — | 用于选择指标的排名条件。 |
| value | int | Yes | — | 非负整股数量。 |


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

**Dataset:** `market.sentiment_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `aigupiao.market_sentiment`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.sentiment(request: 'MarketSentimentRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketSentimentData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketSentimentRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketSentimentRequest`. 其字段如下：

该请求模型没有字段；可以不传 request 对象，直接调用接口使用默认请求行为。

#### 返回值

公开方法的类型标注为 `FetchResult[MarketSentimentData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketSentimentData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| marketTemperature | str | No | Aigupiao 数据源定义的市场温度；不是物理温度或通用比率。 |
| totalTurnover | Decimal \| None | Yes | 标准化的 总 turnover 字段. |
| forecastedTurnover | Decimal \| None | Yes | 数据源 forecast 的 turnover, 不是 observed turnover. |
| turnoverChangeAmount | Decimal \| None | Yes | 数据源报告的相对前一日换手金额变动。 |
| blastBreakRatio | Decimal \| None | Yes | 数据源定义的 broken-limit 比率； FinchX does 不是 reconstruct its denominator. |
| previousLimitUpBreakChangeRatio | Decimal \| None | Yes | 数据源定义的 此前 broken-limit performance 比率. |
| stopTradingCount | int | No | Count 的 stopped-交易 observations. |
| oneLimitUpCount | int | No | Count 的 one-limit-up observations. |
| twoLimitUpCount | int | No | Count 的 two-limit-up observations. |
| threeLimitUpCount | int | No | Count 的 three-limit-up observations. |
| highLimitUpCount | int | No | Count 的 high limit-up observations. |
| twoLimitUpPromotionRatio | Decimal \| None | Yes | 数据源定义的推广比率；FinchX 不复现其分母。 |
| threeLimitUpPromotionRatio | Decimal \| None | Yes | 数据源定义的推广比率；FinchX 不复现其分母。 |
| highLimitUpPromotionRatio | Decimal \| None | Yes | 数据源定义的推广比率；FinchX 不复现其分母。 |
| previousLimitUpThemeChangeRatio | Decimal \| None | Yes | 数据源定义的 此前 limit-up group performance 比率. |
| previousConsecutiveLimitUpThemeChangeRatio | Decimal \| None | Yes | 数据源定义的 此前 consecutive-limit-up group performance 比率. |



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

**Dataset:** `market.strong_pool`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.strong_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.strong_pool(request: 'MarketStrongPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStrongPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketStrongPoolRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketStrongPoolRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketStrongPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketStrongPoolData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| price | Decimal | No | 最新或观测到的价格，单位为每股人民币；指数序列除外。 |
| limitUpPrice | Decimal | No | 当前交易时段的涨停价，单位为每股人民币。 |
| changeRate | Decimal | No | 变动比率；10% 表示为 0.10。 |
| amount | Decimal | No | 成交金额，单位为人民币。 |
| floatMarketCapitalization | Decimal | No | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | No | 总市值，单位为人民币。 |
| turnoverRate | Decimal | No | 换手率；百分比以小数表示。 |
| isSixtyDayHigh | bool | No | 数据源是否将该标的标记为 60 日新高。 |
| selectionReason | Literal['sixty_day_high', 'recent_multiple_limit_ups', 'sixty_day_high_and_recent_multiple_limit_ups'] | No | 强势股池选择的数据源定义原因。 |
| volumeRatio | Decimal | No | 数据源成交量比率，为无量纲倍数；2.35 表示 2.35 倍。 |
| industry | str | No | 数据源提供的行业标签。 |
| limitUpStats | MarketStrongPoolStats | No | 数据源定义的涨停历史统计。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`MarketStrongPoolStats`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | 标准化的回看天数字段。 |
| limitUpCount | int | Yes | — | 涨停标的数量。 |


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

**Dataset:** `market.yesterday_limit_up_pool`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.push2ex.yesterday_limit_up_pool`
**路由语义：** `single_source`。Registry 将此 Dataset 标记为 `single_source`；列出的 Provider 是已实现的特定数据源契约。

#### 方法签名

```python
fx.market.yesterday_limit_up_pool(request: 'MarketYesterdayLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketYesterdayLimitUpPoolData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | MarketYesterdayLimitUpPoolRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `MarketYesterdayLimitUpPoolRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | 数据源交易日期标签；它不是 FinchX 的获取时间。 |

#### 返回值

公开方法的类型标注为 `FetchResult[MarketYesterdayLimitUpPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `MarketYesterdayLimitUpPoolData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| tradeDate | date | No | 数据源交易日期标签；它不是 FinchX 的获取时间。 |
| name | str | No | 经 Provider 标准化的显示名称。 |
| currentPrice | Decimal | No | 当前交易时段价格，单位为每股人民币。 |
| currentLimitUpPrice | Decimal | No | 当前交易时段的涨停价，单位为每股人民币。 |
| currentChangeRate | Decimal | No | 当前交易时段的变动比率；10% 表示为 0.10。 |
| currentAmount | Decimal | No | 当前交易时段的 traded 金额 单位为人民币. |
| floatMarketCapitalization | Decimal | No | 流通市值，单位为人民币。 |
| marketCapitalization | Decimal | No | 总市值，单位为人民币。 |
| currentTurnoverRate | Decimal | No | 当前交易时段的 turnover 比率. |
| currentAmplitude | Decimal | No | 当前交易时段的 价格 amplitude as a 比率 fraction. |
| yesterdayFirstLimitUpTime | str \| None | Yes | Previous-时段 first limit-up 时间, market-local HH：MM：SS. |
| yesterdayConsecutiveLimitUpDays | int | No | Prior-时段 consecutive limit-up 数量. |
| industry | str | No | 数据源提供的行业标签。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `fundamental.company_profile`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.company_profile(instrument_id: 'InstrumentId | None' = None, *, request: 'CompanyProfileRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CompanyProfileData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | 目标标的的完整 InstrumentId。 |
| request | CompanyProfileRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `CompanyProfileRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[CompanyProfileData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `CompanyProfileData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| companyName | str \| None | Yes | 标准化的 company name 字段. |
| businessDescription | str \| None | Yes | 标准化的 business description 字段. |
| issuePrice | Decimal \| None | Yes | 每股人民币。Tencent gsjj.jg 保留为数据源候选字段。 |
| listingDate | date \| None | Yes | 标准化的 listing 日期 字段. |



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

**Dataset:** `fundamental.financial_summary`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.financial_summary(request: 'FinancialSummaryRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialSummaryData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FinancialSummaryRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `FinancialSummaryRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[FinancialSummaryData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `FinancialSummaryData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| periods | list[FinancialSummaryPeriod] | No | 报告期或持有人期间记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`FinancialSummaryPeriod`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date \| None | No | None | 可选的财务报告期末日期。 |
| reportedPeriodLabel | str | Yes | — | 数据源报告期标签。 |
| periodType | Literal['annual', 'interim', 'unknown'] | Yes | — | Reporting-period classification. |
| eps | Decimal \| None | No | None | 可用时的每股收益。 |
| revenue | Decimal \| None | No | None | 可用时的收入金额。 |
| revenueGrowth | Decimal \| None | No | None | Revenue growth 比率. |
| netProfit | Decimal \| None | No | None | 可用时的净利润金额。 |
| netProfitGrowth | Decimal \| None | No | None | Net-profit growth 比率. |
| bookValuePerShare | Decimal \| None | No | None | Book 值 每股. |
| netAssets | Decimal \| None | No | None | Net assets 金额. |
| goodwill | Decimal \| None | No | None | Goodwill 金额. |
| goodwillToNetAssets | Decimal \| None | No | None | Goodwill-to-net-assets 比率. |
| roe | Decimal \| None | No | None | Return on equity 比率. |
| debtRatio | Decimal \| None | No | None | Debt 比率. |
| grossMargin | Decimal \| None | No | None | Gross-margin 比率. |


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

**Dataset:** `fundamental.industry_comparison`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.industry_comparison(request: 'FundamentalIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndustryComparisonData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FundamentalIndustryComparisonRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `IndustryComparisonRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[IndustryComparisonData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `IndustryComparisonData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| industryName | str \| None | Yes | 标准化的 industry name 字段. |
| metrics | list[IndustryComparisonMetric] | No | Industry comparison metric 行. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`IndustryComparisonMetric`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| metric | Literal['eps', 'revenue', 'net_profit', 'book_value_per_share', 'roe', 'debt_ratio', 'gross_margin', 'revenue_growth', 'net_profit_growth', 'market_cap', 'pe', 'pb', 'dividend_yield'] | Yes | — | 该行使用的排名指标。 |
| metricBasis | Literal['financial_period', 'market_snapshot'] | Yes | — | Allowed 值： financial_period, market_snapshot. |
| companyValue | Decimal \| None | No | None | 标准化的 company 值 字段. |
| industryAvg | Decimal \| None | No | None | 标准化的 industry avg 字段. |
| industryMax | Decimal \| None | No | None | 标准化的 industry max 字段. |
| industryMin | Decimal \| None | No | None | 标准化的 industry min 字段. |
| periodEnd | date \| None | No | None | 可选的财务报告期末日期。 |
| reportedPeriodLabel | str | Yes | — | 数据源报告期标签。 |
| observationAt | datetime \| None | No | None | 标准化的 observation at 字段. |


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

**Dataset:** `fundamental.revenue_breakdown`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.fundamental.revenue_breakdown(request: 'RevenueBreakdownRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RevenueBreakdownData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | RevenueBreakdownRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `RevenueBreakdownRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[RevenueBreakdownData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `RevenueBreakdownData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| breakdowns | list[RevenueBreakdownRow] | No | Revenue-breakdown 行. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`RevenueBreakdownRow`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| reportedPeriodLabel | str | Yes | — | 数据源报告期标签。 |
| periodEnd | date \| None | No | None | 可选的财务报告期末日期。 |
| dimension | Literal['product', 'region', 'industry'] | Yes | — | Allowed 值： product, region, industry. |
| itemName | str | Yes | — | 标准化的 item name 字段. |
| revenue | Decimal \| None | Yes | — | 可用时的收入金额。 |
| revenueShare | Decimal \| None | No | None | 标准化的 revenue 股份 字段. |
| currency | 'CNY' | Yes | — | 货币代码。 |
| sourceGroup | Literal['detail', 'others'] | Yes | — | Allowed 值： detail, others. |
| isRollup | bool | Yes | — | 标准化的汇总标志字段。 |


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

Structured financial statements.

### `fx.financial.statements(...)`

返回请求报表类型和期间的标准化财务报表行项目。

**Dataset:** `financial.statement`
**Schema version:** `1.0`
**已实现的 Provider：** `tonghuashun.financial`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.financial.statements(instrument_id: 'InstrumentId | None' = None, statement_type: 'StatementType | None' = None, *, period_end: 'date | None' = None, max_periods: 'int | None' = None, request: 'FinancialStatementRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialStatementData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | 目标标的的完整 InstrumentId。 |
| statement_type | StatementType \| None | No | None | StatementType selection. |
| period_end | date \| None | No | None | 可选的 reporting period end 日期. |
| max_periods | int \| None | No | None | 可选的 maximum 数量 financial periods. |
| request | FinancialStatementRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `FinancialStatementRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | Yes | — | 财务报表类型。 |
| periodEnd | date \| None | No | None | 可选的财务报告期末日期。 |
| maxPeriods | int \| None | No | None | 标准化的 max periods 字段. |

#### 返回值

公开方法的类型标注为 `FetchResult[FinancialStatementData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `FinancialStatementData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | No | 财务报表类型。 |
| periods | list[FinancialStatementPeriod] | No | 报告期或持有人期间记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`FinancialStatementLineItem`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| lineItemId | str | Yes | — | 标准化的 line item id 字段. |
| sourceName | str | Yes | — | 标准化的 数据源 name 字段. |
| sourceUnit | str | Yes | — | 标准化的 数据源 unit 字段. |
| sourceValue | str \| bool \| int \| Decimal \| None | Yes | — | 标准化的 数据源 值 字段. |
| value | Decimal \| None | No | None | 标准化的 值 字段. |
| currency | Currency \| None | No | None | 货币代码。 |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | No | None | 标准化的 missing reason 字段. |

**`FinancialStatementPeriod`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date | Yes | — | 可选的财务报告期末日期。 |
| lineItems | list[FinancialStatementLineItem] | Yes | — | Financial statement line items. |

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

Individual-stock news search references.

### `fx.news.search(...)`

搜索个股新闻元数据并返回可序列化的文档引用。

**Dataset:** `news.document`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.news.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, sort: 'str' = 'published_desc', request: 'NewsSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[NewsDocumentRef, ...]]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | No | None | 用于文档搜索的 InstrumentId 或受支持的六位代码文本。 |
| page | int | No | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| page_size | int | No | 20 | 页面大小；默认值为 20，并受请求模型上限约束。 |
| max_results | int \| None | No | None | 可选的结果数量上限。 |
| since | date \| datetime \| None | No | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | No | None | 可选的、包含边界的最晚发布时间。 |
| sort | str | No | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |
| request | NewsSearchRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `NewsSearchRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| page | int | No | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| pageSize | int | No | 20 | 标准化的页面大小字段。 |
| maxResults | int \| None | No | None | 标准化的最大结果数​​字段。 |
| since | date \| datetime \| None | No | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | No | None | 可选的、包含边界的最晚发布时间。 |
| sort | Literal['published_desc', 'published_asc'] | No | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |

#### 返回值

公开方法的类型标注为 `FetchResult[NewsDocumentData]`. FetchResult.data: tuple[NewsDocumentRef, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `NewsDocumentData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| documentId | str | No | FinchX 文档身份。 |
| sourceDocumentId | str | No | 数据源侧文档身份。 |
| title | str | No | 文档标题。 |
| contentText | str \| None | Yes | 内容可用时获取到的文档正文。 |
| summary | str \| None | Yes | 可用时的数据源简短摘要。 |
| publishedAt | datetime \| None | Yes | 数据源提供的发布时间戳。 |
| sourceOccurrences | list[NewsSourceOccurrence] | No | 数据源-side occurrences retained during document normalization. |
| url | AnyUrl | No | 标准化的 URL 字段。 |
| originalUrl | AnyUrl \| None | Yes | 提供时的原始文档 URL。 |
| contentAvailable | bool | No | 该结果中是否包含文档内容。 |
| source | str \| None | Yes | 标准化的数据源字段。 |
| relatedInstruments | list[InstrumentId] | No | 与文档相关的标的。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |

**`NewsSourceOccurrence`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| providerId | str | Yes | — | 标准化的 Provider id 字段. |
| sourceDocumentId | str | Yes | — | 数据源侧文档身份。 |
| sourceUrl | AnyUrl \| None | No | None | 直接数据源 URL 或数据源接口引用。 |
| documentUrl | AnyUrl \| None | No | None | 标准化的 document url 字段. |
| publishedAt | datetime \| None | No | None | 数据源提供的发布时间戳。 |
| capturedAt | datetime | Yes | — | FinchX 获取数据源观测值时的带时区时间。 |


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

Individual-stock disclosure search references.

### `fx.disclosure.search(...)`

搜索个股公告并返回可序列化的通知引用。

**Dataset:** `disclosure.document`
**Schema version:** `1.0`
**已实现的 Provider：** `eastmoney.disclosure`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.disclosure.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, categories: 'Sequence[str] | None' = None, sort: 'str' = 'published_desc', request: 'DisclosureSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[DisclosureDocumentRef, ...]]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | No | None | 用于文档搜索的 InstrumentId 或受支持的六位代码文本。 |
| page | int | No | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| page_size | int | No | 20 | 页面大小；默认值为 20，并受请求模型上限约束。 |
| max_results | int \| None | No | None | 可选的结果数量上限。 |
| since | date \| datetime \| None | No | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | No | None | 可选的、包含边界的最晚发布时间。 |
| categories | Sequence[str] \| None | No | None | 可选的公告类别代码或名称。 |
| sort | str | No | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |
| request | DisclosureSearchRequest \| None | No | None | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `DisclosureSearchRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| page | int | No | 1 | 从 1 开始计数的结果页；默认值为 1。 |
| pageSize | int | No | 20 | 标准化的页面大小字段。 |
| maxResults | int \| None | No | None | 标准化的最大结果数​​字段。 |
| since | date \| datetime \| None | No | None | 可选的、包含边界的最早发布时间。 |
| until | date \| datetime \| None | No | None | 可选的、包含边界的最晚发布时间。 |
| sort | Literal['published_desc', 'published_asc'] | No | 'published_desc' | 文档排序方式；公开默认值为 published_desc。 |
| categories | list[str] \| None | No | None | 公告类别。 |

#### 返回值

公开方法的类型标注为 `FetchResult[DisclosureDocumentData]`. FetchResult.data: tuple[DisclosureDocumentRef, ...]. 每个 StandardRecord 内的 `data` 数据载荷是 `DisclosureDocumentData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| documentId | str | No | FinchX 文档身份。 |
| sourceDocumentId | str | No | 数据源侧文档身份。 |
| title | str | No | 文档标题。 |
| contentText | str \| None | Yes | 内容可用时获取到的文档正文。 |
| noticeDate | date | No | Disclosure notice 日期. |
| publishedAt | datetime \| None | Yes | 数据源提供的发布时间戳。 |
| sourceRecordedAt | datetime \| None | Yes | 数据源侧记录的时间戳，不同于发布时间和获取时间。 |
| categories | list[DisclosureCategory] | No | 公告类别。 |
| relatedInstruments | list[InstrumentId] | No | 与文档相关的标的。 |
| contentAvailable | bool | No | 该结果中是否包含文档内容。 |
| pdfAvailable | bool | No | 是否有可用的 PDF 附件。 |
| originalDocumentUrl | AnyUrl | No | Original disclosure document URL. |
| attachments | list[DisclosureAttachment] | No | Disclosure attachments. |
| sourceType | str \| None | Yes | 数据源 document type label. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`DisclosureAttachment`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| sequence | int \| None | No | None | 标准化的 sequence 字段. |
| size | int \| None | No | None | 标准化的 size 字段. |
| attachmentType | str \| None | No | None | 标准化的 attachment type 字段. |
| url | AnyUrl | Yes | — | 标准化的 URL 字段。 |
| webUrl | AnyUrl \| None | No | None | 标准化的 web url 字段. |

**`DisclosureCategory`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| name | str | Yes | — | 经 Provider 标准化的显示名称。 |
| source | str | No | 'eastmoney' | 标准化的数据源字段。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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

**Dataset:** `ownership.capital_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.ownership.capital_snapshot(request: 'CapitalSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CapitalSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | CapitalSnapshotRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `CapitalSnapshotRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[CapitalSnapshotData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `CapitalSnapshotData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| totalShares | int \| None | Yes | 总股本。 |
| floatShares | int \| None | Yes | 流通股本。 |



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

**Dataset:** `ownership.float_holder`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.float_holder`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.ownership.float_holder(request: 'FloatHolderRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FloatHolderData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | FloatHolderRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `FloatHolderRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| asOf | datetime \| None | No | None | 查询或计算的可选截止日期。 |

#### 返回值

公开方法的类型标注为 `FetchResult[FloatHolderData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `FloatHolderData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| periods | list[FloatHolderPeriod] | No | 报告期或持有人期间记录。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`FloatHolderPeriod`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| periodEnd | date | Yes | — | 可选的财务报告期末日期。 |
| publishedAt | datetime | Yes | — | 数据源提供的发布时间戳。 |
| rows | list[FloatHolderRow] | Yes | — | 标准化的 行 字段. |

**`FloatHolderRow`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| rank | int | Yes | — | 根据腾讯 rows 数组顺序推导。 |
| holderId | str \| None | No | None | 标准化的 holder id 字段. |
| holderName | str | Yes | — | 标准化的 holder name 字段. |
| shares | int | Yes | — | 股份数量。 |
| holderType | str | Yes | — | 标准化的 holder type 字段. |
| floatShareRatio | Decimal \| None | No | None | 标准化的 float 股份 比率 字段. |
| previousShares | int \| None | No | None | 标准化的 此前 股份 字段. |
| shareChange | int \| None | No | None | 带符号的股份数量变动。 |
| isNewTopFloatHolderEntry | bool \| None | No | None | 多股票相邻期间校验后根据 bdms=1 推导。 |


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

**Dataset:** `ownership.holder_summary_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.ownership.holder_summary_snapshot(request: 'HolderSummarySnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[HolderSummarySnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | HolderSummarySnapshotRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `HolderSummarySnapshotRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[HolderSummarySnapshotData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `HolderSummarySnapshotData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| shareholderCount | int \| None | Yes | Shareholder 数量. |
| averageSharesPerHolder | Decimal \| None | Yes | Average 股份 per holder. |
| shareholderCountChange | Decimal \| None | Yes | Shareholder-数量 变动 比率, 不是 an absolute 数量 delta. |
| top10FloatHolderRatio | Decimal \| None | Yes | Top-ten 流通-holder 比率. |
| top10HolderRatio | Decimal \| None | Yes | Top-ten holder 比率. |



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

**Dataset:** `company.executive_share_change`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.company.executive_share_change(request: 'ExecutiveShareChangeRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveShareChangeData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | ExecutiveShareChangeRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `ExecutiveShareChangeRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[ExecutiveShareChangeData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `ExecutiveShareChangeData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| changes | list[ExecutiveShareChange] | No | 标准化的 changes 字段. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`ExecutiveShareChange`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| eventDate | date \| None | No | None | Executive 股份-变动 event 日期. |
| personName | str \| None | No | None | 管理层或相关人员姓名。 |
| shareChange | int \| None | No | None | 带符号的股份数量变动。 |
| averagePrice | Decimal \| None | No | None | 事件平均价格，单位为每股人民币。 |


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

**Dataset:** `company.executive_snapshot`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.company.executive_snapshot(request: 'ExecutiveSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveSnapshotData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | ExecutiveSnapshotRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `ExecutiveSnapshotRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[ExecutiveSnapshotData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `ExecutiveSnapshotData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| executives | list[ExecutiveEntry] | No | Executive entries. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`ExecutiveEntry`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| name | str | Yes | — | 经 Provider 标准化的显示名称。 |
| roles | list[str] | Yes | — | Executive roles. |
| shares | int \| None | No | None | 股份数量。 |
| compensation | Decimal \| None | No | None | 提供时的薪酬金额。 |


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

**Dataset:** `corporate_action.dividend`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.corporate_action.dividend(request: 'DividendRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DividendData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | DividendRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `DividendRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[DividendData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `DividendData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| dividends | list[Dividend] | No | Dividend event 行. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`Dividend`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| fiscalYear | int \| None | No | None | 标准化的 fiscal year 字段. |
| announcementDate | date \| None | No | None | 标准化的 announcement 日期 字段. |
| stockDividendPer10 | Decimal \| None | No | None | 标准化的 stock dividend per10 字段. |
| capitalizationPer10 | Decimal \| None | No | None | 标准化的 capitalization per10 字段. |
| cashDividendPer10 | Decimal \| None | No | None | 标准化的 cash dividend per10 字段. |
| rightsIssuePer10 | Decimal \| None | No | None | 标准化的 rights issue per10 字段. |
| recordDate | date \| None | No | None | Corporate-action 记录 日期. |
| exDate | date \| None | No | None | 除息或除权日期。 |
| description | str \| None | No | None | 标准化的 description 字段. |


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

**Dataset:** `corporate_action.repurchase`
**Schema version:** `1.0`
**已实现的 Provider：** `tencent.finance.qq.f10`
**路由语义：** `multi_provider`。Registry 将此 Dataset 标记为 `multi_provider`；列出的 Provider 集合就是本版本实际实现的集合。

#### 方法签名

```python
fx.corporate_action.repurchase(request: 'RepurchaseRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RepurchaseData]'
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| request | RepurchaseRequest | Yes | — | 类型化请求模型。不能与便捷业务参数同时使用。 |
| provider | str \| None | No | None | 严格指定 Provider id。只使用指定的 Provider。（仅限 keyword） |
| use_cache | bool \| None | No | None | 是否可以使用已配置的缓存；None 表示遵循已配置的 CachePolicy。（仅限 keyword） |

类型化请求模型为 `RepurchaseRequest`. 其字段如下：

| 请求字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | 完整的标的身份：code、market、kind 和可选的 exchange。 |

#### 返回值

公开方法的类型标注为 `FetchResult[RepurchaseData]`. FetchResult.data: StandardRecord. 每个 StandardRecord 内的 `data` 数据载荷是 `RepurchaseData` schema 如下.

#### 返回数据字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| symbol | str | No | 经 Provider 标准化的标的 symbol 字符串。 |
| repurchases | list[Repurchase] | No | Repurchase event 行. |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`Repurchase`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| repurchaseDate | date \| None | No | None | Repurchase 日期. |
| quantity | int \| None | No | None | Repurchased 股份 quantity. |
| averagePrice | Decimal \| None | No | None | 事件平均价格，单位为每股人民币。 |
| currency | Currency \| None | No | None | 货币代码。 |
| fundAmount | Decimal \| None | No | None | 该事件已使用或公告的资金金额，单位为人民币。 |
| market | str \| None | No | None | FinchX 市场标识。 |


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
| instrument_id | InstrumentId | Yes | — | 完整的 SSE/SZSE A 股股票身份。 |
| windows | Sequence[int] | No | (10, 30) | 仅接受 10 和 30；重复项会被拒绝。 |
| as_of | date \| None | No | None | 截止日期；使用不晚于该截止日期的最近已完成交易时段。 |
| window_convention | DeviationWindowConvention | No | max_deviation_scan | `strict_exchange_window` 或 `max_deviation_scan`. |
| provider | str \| None | No | None | 严格指定 Kline Provider。交易日历查询仍使用运行时选择的日历 Provider。 |
| use_cache | bool \| None | No | None | 传递给底层交易日历和 Kline 获取调用。 |

#### 计算规则

对每个请求的窗口，`deviation = stock_return - benchmark_return`，其中每个收益率均根据选定基准的收盘价/指数点和已完成的结束日期计算。默认的 `max_deviation_scan` 选择使该差值最大的合资格起点；`strict_exchange_window` 使用按交易所形状确定的起点。10 日阈值为 `+1.00` 和 `-0.50`；30 日阈值为 `+2.00` 和 `-0.70`。这些是比率，因此 `0.03` 表示 3%。正偏离值表示股票在选定窗口内跑赢基准；负偏离值表示跑输。

股票输入使用腾讯 QFQ 日 K 线收盘价；基准是未复权指数序列。结果报告 `priceBasis="qfq_stock__raw_index"`、`calculationMode="official_close"` 和规则版本 `cn-a-exchange-2026-07-06+finchx-v1`。它不会作为独立的偏离值 Provider 发起网络请求，但会调用底层交易日历和 K 线能力。

支持的基准映射：SSE `60xxxx` → SSE A Share Index `000002`；SSE `68xxxx` → SSE STAR 50 Index `000688`；SZSE `00xxxx` → SZSE A Share Index `399107`；SZSE `30xxxx` → ChiNext Composite Index `399102`。BSE 和不支持的代码前缀会触发现有的无效请求边界。

#### 计算结果字段

| 字段 | 类型 | 可为空 | 说明 |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | 完整的标的身份：code、market、kind 和可选的 exchange。 |
| board | str | No | 偏离值基准映射所使用的已解析板块分类。 |
| effectiveAsOf | date | No | 计算实际使用的最近已完成交易时段。 |
| calculationMode | 'official_close' | No | 冻结的计算模式；v1 为 official_close。 |
| priceBasis | 'qfq_stock__raw_index' | No | 冻结的价格口径；v1 为 qfq_stock__raw_index。 |
| ruleVersion | str | No | 偏离值计算规则集的版本。 |
| windows | list[DeviationWindowData] | No | 每个请求窗口的计算观测值。 |

#### 嵌套记录类型

上述字段使用以下对象类型。Enum 值会直接显示在类型列中。

**`DeviationWindowData`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| windowDays | Literal[10, 30] | Yes | — | 选定的偏离值窗口：10 或 30 个交易日。 |
| windowConvention | DeviationWindowConvention | Yes | — | 窗口解释：strict_exchange_window 或 max_deviation_scan。 |
| tradingSessions | int | Yes | — | 计算使用的对齐交易时段数量。 |
| startDate | date | Yes | — | 请求范围或选定窗口的包含起始日期。 |
| baselineDate | date | Yes | — | 紧邻选定窗口起点之前的交易时段。 |
| endDate | date | Yes | — | 请求范围或选定窗口的包含结束日期。 |
| startPrice | Decimal | Yes | — | 选定基准日期的股票价格。 |
| windowStartPrice | Decimal | Yes | — | 选定窗口起始日期的股票价格。 |
| currentPrice | Decimal | Yes | — | 当前交易时段价格，单位为每股人民币。 |
| benchmarkInstrument | InstrumentId | Yes | — | 作为基准使用的经审计指数标的。 |
| benchmarkName | str | Yes | — | 便于人类阅读的基准名称。 |
| benchmarkStart | Decimal | Yes | — | 选定基准日期的基准点位。 |
| benchmarkCurrent | Decimal | Yes | — | 计算结束日期的基准点位。 |
| stockReturn | Decimal | Yes | — | 从选定基准日期到结束日期的累计股票收益率。 |
| benchmarkReturn | Decimal | Yes | — | 从选定基准日期到结束日期的累计基准收益率。 |
| deviation | Decimal | Yes | — | 股票收益率减去基准收益率，以比率表示。 |
| upperThreshold | Decimal | Yes | — | 选定窗口的上偏离值阈值。 |
| lowerThreshold | Decimal | Yes | — | 选定窗口的下偏离值阈值。 |
| remainingToUpper | Decimal | Yes | — | 上阈值减去计算得到的偏离值。 |
| remainingToLower | Decimal | Yes | — | 计算得到的偏离值减去下阈值。 |
| upperTriggerPrice | Decimal | Yes | — | 在基准收益率保持不变时确定性的上触发价格估计。 |
| lowerTriggerPrice | Decimal | Yes | — | 在基准收益率保持不变时确定性的下触发价格估计。 |
| remainingPricePctToUpper | Decimal | Yes | — | 价格空间中到上触发估计值的距离。 |
| remainingPricePctToLower | Decimal | Yes | — | 价格空间中到下触发估计值的距离。 |

**`InstrumentId`**
| 字段 | 类型 | 必填 | Default | 说明 |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | 交易所特定的标的代码。 |
| market | Market | Yes | — | FinchX 市场标识。 |
| kind | InstrumentKind | Yes | — | 标的类型。 |
| exchange | Exchange \| None | No | None | Dataset 需要时使用的交易所身份。 |


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
| `calendar` | `pandas_market_calendars` | Optional trading-calendar Provider `pandas_market_calendars`. |
| `jygs` | `playwright` | Authenticated `jiuyangongshe.daily_replay`; also requires `JYGS_SESSION`. |

从源码 checkout 安装时，使用 `python -m pip install ".[calendar]"` 或 `python -m pip install ".[jygs]"`。发布到 PyPI 后，使用 `pip install "finchx[calendar]"` 或 `pip install "finchx[jygs]"`。

## 第三方数据说明

FinchX 提供访问和标准化第三方数据源的软件。FinchX 不重新分发第三方市场数据集。用户应自行遵守相应数据提供方的条款和政策。

## 许可证

FinchX 使用 Apache-2.0 许可证。第三方数据不包含在 FinchX 许可证中。
