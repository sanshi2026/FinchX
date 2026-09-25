# FinchX 数据 API 参考

[English](DATA_API_REFERENCE.md) | 简体中文

本文档覆盖 54 个数据接口 + 1 个计算能力 = 55 个核心能力。

## 1. FinchX 是什么 / 架构概览

FinchX 是一个面向中国A股市场数据的统一客户端。用户调用一个公开 Client；FinchX 校验请求、访问数据源，并返回统一格式的结果。

| 层次 | 作用 |
| --- | --- |
| Client | 用户调用入口：`FinchX()`。 |
| Dataset | 定义稳定的请求模型和业务数据结构。 |
| Provider | 实现一个真实的外部数据源。 |
| Collector | 把请求路由到 Provider，并生成 `FetchResult`。 |
| FetchResult | 默认先展示业务数据；`provider`、`provenance`、`attempts`、`warnings`、`cache_hit` 保留为审计属性。 |

## 2. 快速开始

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)

print(result.data)
rows = result.to_dicts()
print(rows[:1])
print(result.warnings)

```

`result.data` 保留原生类型载荷。`to_dicts()` 是 FinchX 的标准导出方式：始终返回业务数据字典列表，单条结果也保持这一形式，并完整保留嵌套列表和嵌套对象。检查 `result.warnings` 可了解部分数据或可恢复问题。下方每个接口章节都提供完整示例调用。

## 3. 接口总览

### 市场情绪

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.breadth(...)` | 获取当前市场涨跌家数分布。 | `eastmoney.push2ex.breadth` |
| `fx.market.sentiment(...)` | 获取市场情绪快照。 | `aigupiao.market_sentiment` |
| `fx.market.broken_limit_pool(...)` | 获取最新炸板池快照。 | `eastmoney.push2ex.broken_limit_pool` |
| `fx.market.consecutive_limit_up(...)` | 获取连板股快照。 | `aigupiao.series_limit_up` |
| `fx.market.limit_down_pool(...)` | 获取最新跌停池快照。 | `eastmoney.push2ex.limit_down_pool` |
| `fx.market.limit_up_pool(...)` | 获取最新涨停池快照。 | `eastmoney.push2ex.limit_up_pool` |
| `fx.market.strong_pool(...)` | 获取最新强势股池快照。 | `eastmoney.push2ex.strong_pool` |
| `fx.market.yesterday_limit_up_pool(...)` | 获取最新昨日涨停池快照。 | `eastmoney.push2ex.yesterday_limit_up_pool` |

### 指数行情

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.index_intraday(...)` | 获取单个指数当日分时数据。 | `tencent.finance.qq.intraday` |
| `fx.market.index_intraday_5d(...)` | 获取指数五日分时数据。 | `tencent.finance.qq.intraday` |

### 板块信息与热榜

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.hotlist.sectors(...)` | 获取概念、行业或指数板块热榜，并补充可用的关联 ETF 信息。 | `tonghuashun.hotlist` |
| `fx.hotlist.stocks(...)` | 获取按市场关注热度排序的 A 股热股榜，支持类别和 1 小时或 24 小时周期。 | `tonghuashun.hotlist` |
| `fx.market.concept_list(...)` | 获取同花顺概念目录；每条记录包含概念引用字段。 | `tonghuashun.concept` |
| `fx.market.concept_quote_snapshot(...)` | 获取一个概念指数的实时行情快照。 | `tonghuashun.concept` |
| `fx.market.concept_ohlcv(...)` | 获取一个概念指数的日线 OHLCV 数据。 | `tonghuashun.concept` |
| `fx.market.industry_comparison(...)` | 获取市场行业比较数据。 | `tencent.finance.qq.industry` |
| `fx.market.instrument_sector_snapshot(...)` | 获取标的所属板块及板块快照。 | `tencent.finance.qq.sector` |

### 个股行情

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.equity_intraday(...)` | 获取个股分时图。 | `tencent.finance.qq.intraday` |
| `fx.market.equity_intraday_5d(...)` | 获取个股5日分时图。 | `tencent.finance.qq.intraday` |
| `fx.market.fund_flow_daily(...)` | 获取个股每日资金流数据。 | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_intraday(...)` | 获取个股盘中资金流数据。 | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_snapshot(...)` | 获取资金流快照。 | `tencent.finance.qq.fund_flow` |
| `fx.market.ohlcv(...)` | 获取个股日线 OHLCV 数据。 | `tencent.finance.qq.klines`, `sohu.finance.klines` |
| `fx.market.orderbook(...)` | 获取个股盘口数据。 | `tencent.finance.qq.quote` |
| `fx.market.quote(...)` | 获取全市场行情快照。 | `tencent.finance.qq.market` |
| `fx.market.ranking(...)` | 按指定指标获取 A 股个股排行。 | `tencent.finance.qq.market` |
| `fx.market.quote_snapshot(...)` | 获取单个标的的行情快照。 | `tencent.finance.qq.quote` |

### 个股信息与基本面

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.fundamental.company_profile(...)` | 获取公司概况。 | `tencent.finance.qq.f10` |
| `fx.fundamental.financial_summary(...)` | 获取公司财务摘要。 | `tencent.finance.qq.f10` |
| `fx.fundamental.industry_comparison(...)` | 获取公司与行业的基本面比较。 | `tencent.finance.qq.f10` |
| `fx.fundamental.revenue_breakdown(...)` | 获取公司收入构成。 | `tencent.finance.qq.f10` |
| `fx.financial.statements(...)` | 获取财务报表数据。 | `tonghuashun.financial` |
| `fx.market.stock_keyword(...)` | 获取数据源提供的股票关键词。 | `eastmoney.stockrank` |
| `fx.ownership.capital_snapshot(...)` | 获取股本快照。 | `tencent.finance.qq.f10` |
| `fx.ownership.float_holder(...)` | 获取流通股东数据。 | `tencent.finance.qq.float_holder` |
| `fx.ownership.holder_summary_snapshot(...)` | 获取股东汇总快照。 | `tencent.finance.qq.f10` |
| `fx.company.executive_share_change(...)` | 获取高管持股变动。 | `tencent.finance.qq.f10` |
| `fx.company.executive_snapshot(...)` | 获取高管快照。 | `tencent.finance.qq.f10` |
| `fx.corporate_action.dividend(...)` | 获取分红除权记录。 | `tencent.finance.qq.f10` |
| `fx.corporate_action.repurchase(...)` | 获取回购记录。 | `tencent.finance.qq.f10` |

### 消息面

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.news.search(...)` | 搜索个股新闻并返回文档引用。 | `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news` |
| `fx.articles.get(...)` | 通过同花顺文章 URL 获取普通新闻或股吧直播正文。 | `tonghuashun.articles` |
| `fx.articles.from_topic(...)` | 从同花顺 T-code 主题混合 Feed 中筛出可由 articles.get 获取正文的普通新闻和长文。 | `tonghuashun.topic` |
| `fx.disclosure.search(...)` | 搜索个股公告并返回公告引用。 | `eastmoney.disclosure` |
| `fx.news.get_document(ref)` / `fx.news.get_documents(refs)` | 根据搜索引用读取个股新闻详情。 | `eastmoney.news` |
| `fx.disclosure.get_document(ref)` / `fx.disclosure.get_documents(refs)` | 根据搜索引用读取个股公告详情。 | `eastmoney.disclosure` |
| `fx.market_news.search(...)` / `fx.market_news.get_document(s)(...)` | 搜索全市场新闻并读取完整详情。 | `aigupiao.market_news`、`baidu.finscope.market_news` |
| `fx.forum.replies(...)` | 读取登录态淘股吧动态中符合条件的回复。 | `taoguba.forum` |

### 盘后复盘

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.daily_replay(...)` | 获取指定日期的每日复盘数据。 | `jiuyangongshe.daily_replay` |
| `fx.market.dragon_tiger_detail(...)` | 获取指定标的的龙虎榜明细。 | `aigupiao.dragon_tiger` |
| `fx.market.dragon_tiger_list(...)` | 获取指定交易日的龙虎榜列表。 | `aigupiao.dragon_tiger` |

### 监管类：偏离值

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.market.deviation(...)` | 计算经过审计的基于收盘价的偏离值。 | — |

### 其他

| 接口 | 用途 | Provider |
| --- | --- | --- |
| `fx.reference.trading_calendar(...)` | 获取日期范围内每个自然日的 A 股交易日标记。 | `szse.official.calendar`, `pandas_market_calendars` |
| `fx.hotlist.convertible_bonds(...)` | 获取可转债热度榜；尚未产生涨跌幅的转债会保留空值。 | `tonghuashun.hotlist` |
| `fx.hotlist.etfs(...)` | 获取 ETF 热榜，按同花顺关注热度指标排序并补充标签。 | `tonghuashun.hotlist` |
| `fx.hotlist.content(...)` | 获取主题、热评或热文内容榜；三种内容返回各自的数据结构。 | `tonghuashun.hotlist` |
| `fx.iwencai.select(...)` | 使用登录 Cookie 执行问财自然语言选股，并返回标准化股票记录。 | `iwencai` |
| `fx.iwencai.search(...)` | 使用 SkillHub OpenAPI 语义搜索研报、公告或新闻，并返回标准化命中记录。 | `iwencai` |
| `fx.iwencai.report_detail(...)` | 通过搜索结果中的研报链接获取正文和结构化研报元数据。 | `iwencai` |

## 4. 接口详情

## 4.1 市场情绪

### `fx.market.breadth(...)`

**提供什么数据**
获取当前市场涨跌家数分布。

**数据源**
`eastmoney.push2ex.breadth`

**示例**

<!-- api-example: market.breadth -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.breadth()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketBreadthData` 的业务字段包括 `tradeDate`, `advancing`, `declining`, `unchanged` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

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

### `fx.market.sentiment(...)`

**提供什么数据**
获取市场情绪快照。

**数据源**
`aigupiao.market_sentiment`

**示例**

<!-- api-example: market.sentiment -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.sentiment()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketSentimentData` 的业务字段包括 `marketTemperature`, `totalTurnover`, `forecastedTurnover`, `turnoverChangeAmount` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

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

### `fx.market.broken_limit_pool(...)`

**提供什么数据**
获取最新炸板池快照。

**数据源**
`eastmoney.push2ex.broken_limit_pool`

**示例**

<!-- api-example: market.broken_limit_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.broken_limit_pool()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketBrokenLimitPoolData` 的业务字段包括 `instrumentId`, `tradeDate`, `name`, `price` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

无。

**输出字段**

数据模型：`MarketBrokenLimitPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

**示例**

<!-- api-example: market.consecutive_limit_up -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.consecutive_limit_up()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketConsecutiveLimitUpData` 的业务字段包括 `instrumentId`, `name`, `tradeDate`, `lastPrice` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

无。

**输出字段**

数据模型：`MarketConsecutiveLimitUpData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

### `fx.market.limit_down_pool(...)`

**提供什么数据**
获取最新跌停池快照。

**数据源**
`eastmoney.push2ex.limit_down_pool`

**示例**

<!-- api-example: market.limit_down_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_down_pool()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketLimitDownPoolData` 的业务字段包括 `instrumentId`, `tradeDate`, `name`, `price` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

无。

**输出字段**

数据模型：`MarketLimitDownPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

**示例**

<!-- api-example: market.limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_up_pool()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketLimitUpPoolData` 的业务字段包括 `instrumentId`, `tradeDate`, `name`, `price` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

无。

**输出字段**

数据模型：`MarketLimitUpPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

### `fx.market.strong_pool(...)`

**提供什么数据**
获取最新强势股池快照。

**数据源**
`eastmoney.push2ex.strong_pool`

**示例**

<!-- api-example: market.strong_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.strong_pool()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketStrongPoolData` 的业务字段包括 `instrumentId`, `tradeDate`, `name`, `price` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

无。

**输出字段**

数据模型：`MarketStrongPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

**示例**

<!-- api-example: market.yesterday_limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.yesterday_limit_up_pool()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketYesterdayLimitUpPoolData` 的业务字段包括 `instrumentId`, `tradeDate`, `name`, `currentPrice` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

无。

**输出字段**

数据模型：`MarketYesterdayLimitUpPoolData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

## 4.2 指数行情

### `fx.market.index_intraday(...)`

**提供什么数据**
获取单个指数当日分时数据。

**数据源**
`tencent.finance.qq.intraday`

**示例**

<!-- api-example: market.index_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.index_intraday(
    instrument="000001",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `IndexIntradayData` 的业务字段包括 `instrumentId`, `tradeDate`, `time`, `price` 等。用时间序列和价格字段绘制指数交易日走势。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`IndexIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

### `fx.market.index_intraday_5d(...)`

**提供什么数据**
获取指数五日分时数据。

**数据源**
`tencent.finance.qq.intraday`

**示例**

<!-- api-example: market.index_intraday_5d -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.index_intraday_5d(
    instrument="000001",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `IndexIntradayData` 的业务字段包括 `instrumentId`, `tradeDate`, `time`, `price` 等。用时间序列和价格字段绘制指数交易日走势。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`IndexIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

## 4.3 板块信息与热榜

### `fx.hotlist.sectors(...)`

**提供什么数据**
获取概念、行业或指数板块热榜，并补充可用的关联 ETF 信息。

**数据源**
`tonghuashun.hotlist`

**示例**

<!-- api-example: hotlist.sectors -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.sectors(
    sector_type="industry",  # 行业板块榜。
    limit=20,  # 最多返回 20 行。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `HotSectorData` 的业务字段包括 `rank`, `sectorCode`, `name`, `sectorType` 等。用排名和实体字段查看或比较榜单靠前的对象。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| sector_type | str | 可选 | 'concept' | 可选 `concept`（概念板块）、`industry`（行业板块）或 `index`（指数）。 |
| limit | int | 可选 | 20 | 可选正整数，最小值为 1，默认值为 20。 |

**输出字段**

数据模型：`HotSectorData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| rank | int | 该榜单中的名次。 |
| sectorCode | str | 公开板块标识代码。 |
| name | str | 名称。 |
| sectorType | Literal['concept', 'industry', 'index'] | 热度榜使用的板块类型。 |
| changePct | Decimal \| None | 涨跌幅比例小数；来源百分点数值除以 100。 |
| heat | Decimal \| None | 来源热度指标；仅在对应榜单内比较。 |
| rankChange | int \| None | 来源提供时的排名变化。 |
| tag | str \| None | 来源提供的板块说明。 |
| hotTag | str \| None | 来源提供的连续上榜或状态标签。 |
| relatedEtfSymbol | str \| None | 有关联 ETF 时的代码。 |
| relatedEtfName | str \| None | 有关联 ETF 时的名称。 |
| relatedEtfChangePct | Decimal \| None | 关联 ETF 涨跌幅比例小数。 |

### `fx.hotlist.stocks(...)`

**提供什么数据**
获取按市场关注热度排序的 A 股热股榜，支持类别和 1 小时或 24 小时周期。

**数据源**
`tonghuashun.hotlist`

**示例**

<!-- api-example: hotlist.stocks -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.stocks(
    category="popular",  # 人气榜类别。
    period="24h",  # 24 小时榜单周期。
    limit=20,  # 最多返回 20 行。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `HotStockData` 的业务字段包括 `rank`, `symbol`, `instrumentId`, `name` 等。用排名和实体字段查看或比较榜单靠前的对象。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| category | str | 可选 | 'popular' | 可选 `popular`（人气）、`rising`（飙升）、`new`（新股）、`technical`（技术分析）、`value`（价值投资）或 `trend`（趋势）。 |
| period | str \| None | 可选 | None | 可选统计周期：`1h` 或 `24h`。`popular` 和 `rising` 支持两种周期；其他类别仅支持 `24h`。 |
| limit | int | 可选 | 20 | 可选正整数，最小值为 1，默认值为 20。 |

**输出字段**

数据模型：`HotStockData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| rank | int | 该榜单中的名次。 |
| symbol | str | 六位证券代码。 |
| instrumentId | str | 证券代码。 |
| name | str | 名称。 |
| category | Literal['popular', 'rising', 'new', 'technical', 'value', 'trend'] | 选择的热榜类别。 |
| period | Literal['1h', '24h'] | 股票热度榜统计周期。 |
| changePct | Decimal \| None | 涨跌幅比例小数；来源百分点数值除以 100。 |
| heat | Decimal \| None | 来源热度指标；仅在对应榜单内比较。 |
| rankChange | int \| None | 来源提供时的排名变化。 |
| conceptTags | list[str] | 来源提供的概念标签。 |
| popularityTag | str \| None | 来源提供的热度标签。 |
| analysisTitle | str \| None | 来源提供的分析标题。 |
| analysis | str \| None | 来源提供的分析内容。 |
| searchCount | int \| None | 来源提供时的搜索次数。 |
| updatedAt | datetime \| None | 来源更新时间；未标时区时按 Asia/Shanghai 处理。 |
| pe | Decimal \| None | 新股发行市盈率。 |

### `fx.market.concept_list(...)`

**提供什么数据**
获取同花顺概念目录；每条记录包含概念引用字段。

**数据源**
`tonghuashun.concept`

**示例**

<!-- api-example: market.concept_list -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.concept_list()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `ConceptRef` 的业务字段包括 `sectorType`, `sectorName`, `providerNamespace`, `providerSectorId` 等。用概念标识及行情或 K 线字段比较板块走势。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

无。

**输出字段**

数据模型：`ConceptRef`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| sectorType | Literal['concept'] | — |
| sectorName | str | — |
| providerNamespace | Literal['tonghuashun_concept'] | — |
| providerSectorId | str | — |

### `fx.market.concept_quote_snapshot(...)`

**提供什么数据**
获取一个概念指数的实时行情快照。

**数据源**
`tonghuashun.concept`

**示例**

<!-- api-example: market.concept_quote_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.concept_quote_snapshot(
    concept="人工智能",  # 准确概念名称；有 ConceptRef 时优先使用。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `ConceptQuoteSnapshotData` 的业务字段包括 `concept`, `indexLevel`, `previousClose`, `open` 等。用概念标识及行情或 K 线字段比较板块走势。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| concept | ConceptRef \| str | 必填 | — | concept_list() 返回的 ConceptRef，或可唯一匹配的准确概念名称。 |

**输出字段**

数据模型：`ConceptQuoteSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| concept | ConceptRef | — |
| indexLevel | Decimal \| None | — |
| previousClose | Decimal \| None | — |
| open | Decimal \| None | — |
| high | Decimal \| None | — |
| low | Decimal \| None | — |
| levelChange | Decimal \| None | — |
| changeRate | Decimal \| None | — |
| volume | int \| None | — |
| amount | Decimal \| None | — |
| netMoneyFlow | Decimal \| None | — |
| riseCount | int \| None | — |
| fallCount | int \| None | — |
| sourceTimestamp | datetime \| None | — |

嵌套业务模型： `ConceptRef`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| sectorType | Literal['concept'] | — |
| sectorName | str | — |
| providerNamespace | Literal['tonghuashun_concept'] | — |
| providerSectorId | str | — |

### `fx.market.concept_ohlcv(...)`

**提供什么数据**
获取一个概念指数的日线 OHLCV 数据。

**数据源**
`tonghuashun.concept`

**示例**

<!-- api-example: market.concept_ohlcv -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.concept_ohlcv(
    concept="人工智能",  # 准确概念名称；有 ConceptRef 时优先使用。
    start_date="2026-09-01",  # 包含在内的开始日期。
    end_date="2026-09-23",  # 包含在内的结束日期。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `ConceptOhlcvData` 的业务字段包括 `concept`, `barDate`, `open`, `high` 等。用概念标识及行情或 K 线字段比较板块走势。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| concept | ConceptRef \| str | 必填 | — | concept_list() 返回的 ConceptRef，或可唯一匹配的准确概念名称。 |
| start_date | date \| str | 必填 | — | 包含在内的开始日期。 |
| end_date | date \| str | 必填 | — | 包含在内的结束日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |

**输出字段**

数据模型：`ConceptOhlcvData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| concept | ConceptRef | — |
| barDate | date | — |
| open | Decimal | — |
| high | Decimal | — |
| low | Decimal | — |
| close | Decimal | — |
| volume | int | 非负整数股数。 |
| amount | Decimal \| None | — |

嵌套业务模型： `ConceptRef`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| sectorType | Literal['concept'] | — |
| sectorName | str | — |
| providerNamespace | Literal['tonghuashun_concept'] | — |
| providerSectorId | str | — |

### `fx.market.industry_comparison(...)`

**提供什么数据**
获取市场行业比较数据。

**数据源**
`tencent.finance.qq.industry`

**示例**

<!-- api-example: market.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.industry_comparison(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketIndustryComparisonData` 的业务字段包括 `instrumentId`, `industry`, `instrumentValues`, `industryRanks` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketIndustryComparisonData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

**示例**

<!-- api-example: market.instrument_sector_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.instrument_sector_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketInstrumentSectorSnapshotData` 的业务字段包括 `instrumentId`, `sectors` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketInstrumentSectorSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| sectors | list[InstrumentSectorEntry] | — |

嵌套业务模型： `InstrumentSectorEntry`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | 热度榜使用的板块类型。 |
| sectorName | str | — |
| providerNamespace | Literal['tencent_plate'] | — |
| providerSectorId | str | — |
| level | int \| None | — |
| tag | str \| None | 来源提供的板块说明。 |
| changePct | Decimal \| None | Tencent zdf 已从百分点转换为比例小数。 |

## 4.4 个股行情

### `fx.market.equity_intraday(...)`

**提供什么数据**
获取个股分时图。

**数据源**
`tencent.finance.qq.intraday`

**示例**

<!-- api-example: market.equity_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `EquityIntradayData` 的业务字段包括 `instrumentId`, `tradeDate`, `time`, `price` 等。用时间序列和价格字段绘制个股交易日走势。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`EquityIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

### `fx.market.equity_intraday_5d(...)`

**提供什么数据**
获取个股5日分时图。

**数据源**
`tencent.finance.qq.intraday`

**示例**

<!-- api-example: market.equity_intraday_5d -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday_5d(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `EquityIntradayData` 的业务字段包括 `instrumentId`, `tradeDate`, `time`, `price` 等。用时间序列和价格字段绘制个股交易日走势。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`EquityIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| tradeDate | date | 来源交易日期标签；不是 FinchX capturedAt。 |
| time | str | 来源交易时间由 HHMM 规范化为 HH:MM；不是 capturedAt。 |
| price | Decimal | 来源价格单位中的精确小数（股票为每股 CNY，指数为指数点数）。 |
| volume | int | 该分钟成交量，单位为整股。 |
| amount | Decimal | 该分钟成交金额，单位为 CNY。 |
| cumulativeVolume | int | Tencent 来源累计成交量已从手规范化为整股（来源手数乘以 100）。 |
| cumulativeAmount | Decimal | Tencent 来源累计成交金额，单位为 CNY，与来源保持一致。 |

### `fx.market.fund_flow_daily(...)`

**提供什么数据**
获取个股每日资金流数据。

**数据源**
`tencent.finance.qq.fund_flow`

**示例**

<!-- api-example: market.fund_flow_daily -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_daily(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketFundFlowDailyData` 的业务字段包括 `instrumentId`, `tradeDate`, `mainNetInflow`, `close` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketFundFlowDailyData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| tradeDate | date | Tencent 报告的交易日期，不是 FinchX 抓取时间。 |
| mainNetInflow | Decimal | 金额，单位为 CNY。 |
| close | Decimal | 每日收盘价，单位为每股 CNY。 |

### `fx.market.fund_flow_intraday(...)`

**提供什么数据**
获取个股盘中资金流数据。

**数据源**
`tencent.finance.qq.fund_flow`

**示例**

<!-- api-example: market.fund_flow_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_intraday(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketFundFlowIntradayData` 的业务字段包括 `instrumentId`, `tradeDate`, `time`, `price` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketFundFlowIntradayData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

**示例**

<!-- api-example: market.fund_flow_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketFundFlowSnapshotData` 的业务字段包括 `instrumentId`, `tradeDate`, `mainNetInflow`, `mainInflow` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketFundFlowSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

### `fx.market.ohlcv(...)`

**提供什么数据**
获取个股日线 OHLCV 数据。

**数据源**
`tencent.finance.qq.klines`, `sohu.finance.klines`

**示例**

<!-- api-example: market.ohlcv -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.ohlcv(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    start_date="2026-09-01",  # 包含在内的开始日期。
    end_date="2026-09-23",  # 包含在内的结束日期。
    adjustment="qfq",  # 股票前复权价格。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketKlineData` 的业务字段包括 `instrumentId`, `barDate`, `open`, `high` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |
| start_date | date \| str | 必填 | — | 包含在内的开始日期。 |
| end_date | date \| str | 必填 | — | 包含在内的结束日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |
| adjustment | str \| None | 可选 | None | 可选的公开复权参数：`qfq` 表示前复权，`hfq` 表示后复权，Python `None` 表示股票不复权；指数必须使用 `None`。 |

**输出字段**

数据模型：`MarketKlineData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| barDate | date | — |
| open | Decimal | 每股价格；币种为 CNY。 |
| high | Decimal | 每股价格；币种为 CNY。 |
| low | Decimal | 每股价格；币种为 CNY。 |
| close | Decimal | 每股价格；币种为 CNY。 |
| volume | int | 非负整数股数。 |
| amount | Decimal \| None | — |
| adjustment | KlineAdjustment | 输出复权标记：`none`、`qfq`、`hfq` 或 `not_applicable`。 |

### `fx.market.orderbook(...)`

**提供什么数据**
获取个股盘口数据。

**数据源**
`tencent.finance.qq.quote`

**示例**

<!-- api-example: market.orderbook -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.orderbook(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketOrderbookData` 的业务字段包括 `instrumentId`, `bids`, `asks` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketOrderbookData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| bids | list[OrderbookLevel] | — |
| asks | list[OrderbookLevel] | — |

嵌套业务模型： `OrderbookLevel`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| level | int | — |
| price | Decimal | 每股价格；币种为 CNY。 |
| size | int | 非负整数股数。 |

### `fx.market.quote(...)`

**提供什么数据**
获取全市场行情快照。

**数据源**
`tencent.finance.qq.market`

**示例**

<!-- api-example: market.quote -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketQuoteData` 的业务字段包括 `instrumentId`, `name`, `price`, `priceChange` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | 可选 | InstrumentUniverse.CN_A_SHARE | A 股行情范围；省略时获取全市场快照。 |

**输出字段**

数据模型：`MarketQuoteData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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
按指定指标获取 A 股个股排行。

**数据源**
`tencent.finance.qq.market`

**示例**

<!-- api-example: market.ranking -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.ranking(
    criterion="amount",  # 按成交额排名。
    direction="desc",  # 从大到小排序。
    limit=20,  # 最多返回 20 行。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketRankingData` 的业务字段包括 `instrumentId`, `name`, `price`, `priceChange` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| criterion | str | 必填 | — | 可选 `amount`（成交额，单位 CNY）、`zdf`（涨跌幅，比例小数，例如 3% 为 0.03）或 `volume`（成交量，单位为股）。 |
| direction | str | 必填 | — | 排序方向：`asc` 表示从低到高，`desc` 表示从高到低。 |
| limit | int \| None | 必填 | — | 必填；正整数或 None；None 表示不限制返回数量。 |

**输出字段**

数据模型：`MarketRankingData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

### `fx.market.quote_snapshot(...)`

**提供什么数据**
获取单个标的的行情快照。

**数据源**
`tencent.finance.qq.quote`

**示例**

<!-- api-example: market.quote_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketQuoteSnapshotData` 的业务字段包括 `instrumentId`, `price`, `previousClose`, `open` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketQuoteSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

## 4.5 个股信息与基本面

### `fx.fundamental.company_profile(...)`

**提供什么数据**
获取公司概况。

**数据源**
`tencent.finance.qq.f10`

**示例**

<!-- api-example: fundamental.company_profile -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.company_profile(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `CompanyProfileData` 的业务字段包括 `symbol`, `companyName`, `businessDescription`, `issuePrice` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`CompanyProfileData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
| companyName | str \| None | — |
| businessDescription | str \| None | — |
| issuePrice | Decimal \| None | 单位为每股 CNY；保留 Tencent gsjj.jg 作为来源候选值。 |
| listingDate | date \| None | — |

### `fx.fundamental.financial_summary(...)`

**提供什么数据**
获取公司财务摘要。

**数据源**
`tencent.finance.qq.f10`

**示例**

<!-- api-example: fundamental.financial_summary -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.financial_summary(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `FinancialSummaryData` 的业务字段包括 `symbol`, `periods` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`FinancialSummaryData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: fundamental.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.industry_comparison(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `IndustryComparisonData` 的业务字段包括 `symbol`, `industryName`, `metrics` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`IndustryComparisonData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: fundamental.revenue_breakdown -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.revenue_breakdown(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `RevenueBreakdownData` 的业务字段包括 `symbol`, `breakdowns` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`RevenueBreakdownData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: financial.statements -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.financial.statements(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    statement_type="income_statement",  # 利润表。
    period_end="2026-06-30",  # 报告期结束日期。
    max_periods=4,  # 最多返回四个报告期。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `FinancialStatementData` 的业务字段包括 `instrumentId`, `symbol`, `statementType`, `periods` 等。业务计算建议使用规范化的 `lineItems[].value`；`sourceValue` 仅用于核对来源原始文本或单位。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |
| statement_type | StatementType | 必填 | — | balance_sheet、income_statement 或 cash_flow_statement。 |
| period_end | date \| str \| None | 可选 | None | 可选的报告期结束日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |
| max_periods | int \| None | 可选 | None | 可选的最大报告期数量。 |

**输出字段**

数据模型：`FinancialStatementData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| symbol | str | 六位证券代码。 |
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
| sourceValue | str \| bool \| int \| float \| None | 保留的来源原始值，仅用于审计及核对单位或内容。 |
| value | Decimal \| None | 规范化数值，业务计算建议使用此字段，不要自行解析来源文本。 |
| currency | Currency \| None | — |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | — |

### `fx.market.stock_keyword(...)`

**提供什么数据**
获取数据源提供的股票关键词。

**数据源**
`eastmoney.stockrank`

**示例**

<!-- api-example: market.stock_keyword -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.stock_keyword(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketStockKeywordData` 的业务字段包括 `instrumentId`, `keywords` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`MarketStockKeywordData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| keywords | list[StockKeywordEntry] | — |

嵌套业务模型： `StockKeywordEntry`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| keywordName | str | — |
| providerNamespace | Literal['eastmoney_stockrank'] | — |
| providerKeywordId | str | — |
| hitCount | int | — |
| calculatedAt | datetime | — |

### `fx.ownership.capital_snapshot(...)`

**提供什么数据**
获取股本快照。

**数据源**
`tencent.finance.qq.f10`

**示例**

<!-- api-example: ownership.capital_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.capital_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `CapitalSnapshotData` 的业务字段包括 `symbol`, `totalShares`, `floatShares` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`CapitalSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
| totalShares | int \| None | — |
| floatShares | int \| None | — |

### `fx.ownership.float_holder(...)`

**提供什么数据**
获取流通股东数据。

**数据源**
`tencent.finance.qq.float_holder`

**示例**

<!-- api-example: ownership.float_holder -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.float_holder(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `FloatHolderData` 的业务字段包括 `symbol`, `periods` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`FloatHolderData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: ownership.holder_summary_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.holder_summary_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `HolderSummarySnapshotData` 的业务字段包括 `symbol`, `shareholderCount`, `averageSharesPerHolder`, `shareholderCountChange` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`HolderSummarySnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: company.executive_share_change -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_share_change(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `ExecutiveShareChangeData` 的业务字段包括 `symbol`, `changes` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`ExecutiveShareChangeData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: company.executive_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_snapshot(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `ExecutiveSnapshotData` 的业务字段包括 `symbol`, `executives` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`ExecutiveSnapshotData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: corporate_action.dividend -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.dividend(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `DividendData` 的业务字段包括 `symbol`, `dividends` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`DividendData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

**示例**

<!-- api-example: corporate_action.repurchase -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.repurchase(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `RepurchaseData` 的业务字段包括 `symbol`, `repurchases` 等。用类型化字段或导出行比较报告期、股东、高管或公司行动。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |

**输出字段**

数据模型：`RepurchaseData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
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

## 4.6 消息面

### `fx.news.search(...)`

**提供什么数据**
搜索个股新闻并返回文档引用。

**数据源**
`eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`

**示例**

<!-- api-example: news.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.news.search(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    sort="published_desc",  # 按发布时间从新到旧。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是带类型的文档引用元组。 Dataset 行模式 `NewsDocumentData` 的业务字段包括 `documentId`, `sourceDocumentId`, `title`, `important` 等。用引用字段筛选目标文档，再将引用传给对应详情方法。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |
| page | int | 可选 | 1 | 从 1 开始的页码。 |
| page_size | int | 可选 | 20 | 单页数量。 |
| max_results | int \| None | 可选 | None | 可选的结果上限。 |
| since | date \| datetime \| str \| None | 可选 | None | 可选的时间范围起点。 |
| until | date \| datetime \| str \| None | 可选 | None | 可选的时间范围终点。 |
| sort | str | 可选 | 'published_desc' | published_desc 或 published_asc。 |

**输出字段**

数据模型：`NewsDocumentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| documentId | str | — |
| sourceDocumentId | str | — |
| title | str | 内容标题。 |
| important | bool \| None | 统一后的数据源重要度标记：数据源标记为重要时为 True，未标记为重要时为 False，无法取得时为 None。 |
| contentText | str \| None | — |
| summary | str \| None | 来源提供时的主题摘要。 |
| publishedAt | datetime \| None | — |
| sourceOccurrences | list[NewsSourceOccurrence] | — |
| url | AnyUrl | 来源提供时的内容链接。 |
| originalUrl | AnyUrl \| None | — |
| contentAvailable | bool | — |
| source | str \| None | — |
| relatedInstruments | list[str] | — |

嵌套业务模型： `NewsSourceOccurrence`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| providerId | str | — |
| sourceDocumentId | str | — |
| sourceUrl | AnyUrl \| None | — |
| documentUrl | AnyUrl \| None | — |
| publishedAt | datetime \| None | — |
| capturedAt | datetime | — |

### `fx.articles.get(...)`

**提供什么数据**
通过同花顺文章 URL 获取普通新闻或股吧直播正文。

**数据源**
`tonghuashun.articles`

**示例**

<!-- api-example: articles.get -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.articles.get(
    url="https://stock.10jqka.com.cn/20260923/c680236250.shtml",  # 公开文章或研报详情 URL。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是一条标准化记录。 Dataset 行模式 `ArticleDetailData` 的业务字段包括 `contentId`, `contentType`, `title`, `contentHtml` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| url | str | 必填 | — | 同花顺普通新闻或股吧直播文章 URL；news/zhibo 类型和文章 ID 根据允许的主机与路径解析。 |

**输出字段**

数据模型：`ArticleDetailData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| contentId | str | 同花顺文章标识，与来源 URL 中的 ID 对应。 |
| contentType | Literal['news', 'zhibo'] | 文章类型：普通新闻或股吧直播。 |
| title | str \| None | 文章标题。 |
| contentHtml | str \| None | 清理后的文章正文 HTML，不包含评论和免责声明。 |
| contentText | str \| None | 从清理后的文章正文提取的纯文本；正文只含有效图片时可以为空。 |
| publishedAt | datetime \| None | 来源提供时的带时区发布时间。 |
| sourceName | str \| None | 来源提供的发布方或媒体名称。 |
| author | str \| None | 文章作者或署名。 |
| sourceUrl | AnyUrl \| None | 用于获取文章的上游 API 或页面 URL。 |
| pageUrl | AnyUrl \| None | 根据输入 URL 规范化后的公开文章页面 URL。 |
| aiSummary | str \| None | 来源提供时的 AI 摘要。 |
| disclaimer | str \| None | 从正文中分离提取的免责声明。 |
| comments | list[str] | 从正文中分离提取的社区评论。 |
| relatedStocks | list[ArticleRelatedStock] | 文章详情来源报告的关联证券。 |
| fetchMethod | Literal['detail_api', 'embedded_state', 'dom', 'zhibo_html'] \| None | 文章正文使用的提取路径。 |
| rawHash | str \| None | 原始 API 文章正文或抓取页面 HTML 的 SHA-256。 |
| contentAvailable | bool | 是否成功获取可用的文章标题和正文。 |
| errorCode | str \| None | 正文不可用时的分类错误代码。 |
| errorMessage | str \| None | 正文不可用时的简短来源或解析错误说明。 |

嵌套业务模型： `ArticleRelatedStock`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 原样保留的来源证券代码。 |
| instrumentId | str \| None | 仅在可识别证券类型和市场时提供 FinchX 标识，否则为 null。 |
| name | str | 来源提供的证券名称。 |
| changePct | Decimal \| None | — |
| sourceMarket | str \| None | 同花顺原始 stockMarket 标记，不是 FinchX 市场枚举。 |
| sources | list[Literal['hotlist', 'detail']] | 对该关联项有贡献的输入来源。 |

### `fx.articles.from_topic(...)`

**提供什么数据**
从同花顺 T-code 主题混合 Feed 中筛出可由 articles.get 获取正文的普通新闻和长文。

**数据源**
`tonghuashun.topic`

**示例**

<!-- api-example: articles.from_topic -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.articles.from_topic(
    topic_url="https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=T4dryo6",  # 受支持的同花顺话题 URL。
    sort="recommend",  # 按来源推荐顺序展示。
    limit=20,  # 最多返回 20 行。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `TopicArticleData` 的业务字段包括 `topicCode`, `rank`, `contentId`, `contentType` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| topic_url | str | 必填 | — | 同花顺 T-code 主题 HTTPS URL。可识别 deep-topic 报告链接并明确拒绝，因为当前没有该报告专属的新闻 Feed。 |
| sort | Literal['recommend'] | 可选 | 'recommend' | 目前仅支持 `recommend`：按源顺序读取推荐内容，并在推荐耗尽后继续分页读取普通 Feed。 |
| limit | int | 可选 | 20 | 混合 Feed 过滤后最多返回的已支持新闻和长文数；范围为 1 到 100。 |

**输出字段**

数据模型：`TopicArticleData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| topicCode | str | — |
| rank | int | 过滤后文章列表中的位置，保持来源顺序。 |
| contentId | str | 主题条目中的同花顺数字文章序列 ID。 |
| contentType | Literal['news', 'zhibo'] | 已验证的 type=8 新闻和 type=2 长文分别使用现有 news 或 zhibo 详情路由。 |
| title | str | 主题 Feed 提供的文章标题。 |
| url | str | 可直接传给 fx.articles.get(url) 的公开新闻或 zhibo 文章 URL。 |
| publishedAt | datetime | 来源文章时间戳由毫秒纪元值规范化为 Asia/Shanghai 时间。 |
| sourceName | str \| None | 主题 Feed 条目提供的发布方或媒体名称。 |

### `fx.disclosure.search(...)`

**提供什么数据**
搜索个股公告并返回公告引用。

**数据源**
`eastmoney.disclosure`

**示例**

<!-- api-example: disclosure.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.disclosure.search(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    categories=None,  # 不筛选公告分类。
    sort="published_desc",  # 按发布时间从新到旧。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是带类型的文档引用元组。 Dataset 行模式 `DisclosureDocumentData` 的业务字段包括 `documentId`, `sourceDocumentId`, `title`, `contentText` 等。用引用字段筛选目标文档，再将引用传给对应详情方法。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |
| page | int | 可选 | 1 | 从 1 开始的页码。 |
| page_size | int | 可选 | 20 | 单页数量。 |
| max_results | int \| None | 可选 | None | 可选的结果上限。 |
| since | date \| datetime \| str \| None | 可选 | None | 可选的时间范围起点。 |
| until | date \| datetime \| str \| None | 可选 | None | 可选的时间范围终点。 |
| categories | Sequence[str] \| None | 可选 | None | 可选的公告分类列表。 |
| sort | str | 可选 | 'published_desc' | published_desc 或 published_asc。 |

**输出字段**

数据模型：`DisclosureDocumentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| documentId | str | — |
| sourceDocumentId | str | — |
| title | str | 内容标题。 |
| contentText | str \| None | — |
| noticeDate | date | — |
| publishedAt | datetime \| None | — |
| categories | list[DisclosureCategory] | — |
| relatedInstruments | list[str] | — |
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
| url | AnyUrl | 来源提供时的内容链接。 |
| webUrl | AnyUrl \| None | — |

### `fx.news.get_document(ref)`

**提供什么数据**
根据 `fx.news.search(...)` 返回的引用，读取一条完整的个股新闻详情。

**数据源**
`eastmoney.news`

**示例**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.news.search(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    sort="published_desc",  # 按发布时间从新到旧。
)

if search_result.data:
    ref = search_result.data[0]
    print(ref.document_url)
    result = fx.news.get_document(
        ref=search_result.data[0],  # 对应搜索返回的引用。
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('没有找到符合示例搜索条件的文档。')
```

**返回值与推荐用法**
`.data` 返回一条 `StandardRecord`。可从 `result.data.data` 读取文档行载荷中的 `title`、`contentText` 和文档 URL 等字段；用 `.to_dicts()` 导出 JSON 兼容行，并检查 `.warnings` 了解读取问题。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| ref | NewsDocumentRef | 必填 | — | fx.news.search(...) 返回的新闻引用。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[document record] | 公开返回类型。 |
| data | 标准文档记录 | 完整的标准化文档记录。 |
| provider_id | str \| None | FetchResult 携带的数据源标识。 |
| dataset_id | str | FetchResult 携带的稳定数据集标识。 |
| to_dicts() | list[dict[str, object]] | 标准业务数据导出；单条记录仍返回单元素列表。 |

### `fx.news.get_documents(refs)`

**提供什么数据**
根据一组新闻引用，批量读取个股新闻详情。

**数据源**
`eastmoney.news`

**示例**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.news.search(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    sort="published_desc",  # 按发布时间从新到旧。
)

if search_result.data:
    for ref in search_result.data:
        print(ref.document_url)
    result = fx.news.get_documents(
        refs=search_result.data,  # 对应搜索返回的引用列表。
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('没有找到符合示例搜索条件的文档。')
```

**返回值与推荐用法**
`.data` 返回按引用顺序排列的 `StandardRecord` 元组。可读取每条记录的文档字段，或用 `.to_dicts()` 导出全部数据行；检查 `.warnings` 了解读取问题。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| refs | Iterable[NewsDocumentRef] | 必填 | — | fx.news.search(...) 返回的新闻引用。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[tuple[document record, ...]] | 公开返回类型。 |
| data | tuple[标准文档记录, ...] | 按输入顺序返回完整的标准化文档记录。 |
| provider_id | str \| None | 所有记录来自同一数据源时返回其标识。 |
| dataset_id | str | FetchResult 携带的稳定数据集标识。 |
| to_dicts() | list[dict[str, object]] | 所有记录的标准业务数据导出。 |

### `fx.disclosure.get_document(ref)`

**提供什么数据**
根据 `fx.disclosure.search(...)` 返回的引用，读取一条完整的个股公告详情。

**数据源**
`eastmoney.disclosure`

**示例**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.disclosure.search(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    categories=None,  # 不筛选公告分类。
    sort="published_desc",  # 按发布时间从新到旧。
)

if search_result.data:
    ref = search_result.data[0]
    print(ref.original_document_url)
    result = fx.disclosure.get_document(
        ref=search_result.data[0],  # 对应搜索返回的引用。
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('没有找到符合示例搜索条件的文档。')
```

**返回值与推荐用法**
`.data` 返回一条 `StandardRecord`。可从 `result.data.data` 读取文档行载荷中的 `title`、`contentText` 和文档 URL 等字段；用 `.to_dicts()` 导出 JSON 兼容行，并检查 `.warnings` 了解读取问题。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| ref | DisclosureDocumentRef | 必填 | — | fx.disclosure.search(...) 返回的公告引用。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[document record] | 公开返回类型。 |
| data | 标准文档记录 | 完整的标准化文档记录。 |
| provider_id | str \| None | FetchResult 携带的数据源标识。 |
| dataset_id | str | FetchResult 携带的稳定数据集标识。 |
| to_dicts() | list[dict[str, object]] | 标准业务数据导出；单条记录仍返回单元素列表。 |

### `fx.disclosure.get_documents(refs)`

**提供什么数据**
根据一组公告引用，批量读取个股公告详情。

**数据源**
`eastmoney.disclosure`

**示例**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.disclosure.search(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    categories=None,  # 不筛选公告分类。
    sort="published_desc",  # 按发布时间从新到旧。
)

if search_result.data:
    for ref in search_result.data:
        print(ref.original_document_url)
    result = fx.disclosure.get_documents(
        refs=search_result.data,  # 对应搜索返回的引用列表。
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('没有找到符合示例搜索条件的文档。')
```

**返回值与推荐用法**
`.data` 返回按引用顺序排列的 `StandardRecord` 元组。可读取每条记录的文档字段，或用 `.to_dicts()` 导出全部数据行；检查 `.warnings` 了解读取问题。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| refs | Iterable[DisclosureDocumentRef] | 必填 | — | fx.disclosure.search(...) 返回的公告引用。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[tuple[document record, ...]] | 公开返回类型。 |
| data | tuple[标准文档记录, ...] | 按输入顺序返回完整的标准化文档记录。 |
| provider_id | str \| None | 所有记录来自同一数据源时返回其标识。 |
| dataset_id | str | FetchResult 携带的稳定数据集标识。 |
| to_dicts() | list[dict[str, object]] | 所有记录的标准业务数据导出。 |

### `fx.market_news.search(...)`

**提供什么数据**
聚合并去重全市场新闻，返回可继续读取详情的新闻引用。

**数据源**
`aigupiao.market_news`、`baidu.finscope.market_news`

**示例**

```python
from finchx import FinchX

fx = FinchX()

result = fx.market_news.search(
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    sort="published_desc",  # 按发布时间从新到旧。
)

print(result.data)
print(result.to_dicts()[:1])
print(result.warnings)
```

**返回值与推荐用法**
`.data` 返回带类型的文档引用。可按 `title`、`publishedAt` 筛选或排序；新闻文章正文链接使用 `documentUrl`，公告原文或附件使用 `originalDocumentUrl`。将目标引用传给对应详情方法；用 `.to_dicts()` 导出数据，并检查 `.warnings` 了解扫描是否触及上限。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| page | int | 可选 | 1 | 从 1 开始的页码。 |
| page_size | int | 可选 | 20 | 每页向数据源请求的行数。 |
| max_results | int \| None | 可选 | None | 最多返回的去重引用数量。 |
| since / until | date \| datetime \| str \| None | 可选 | None | 发布时间范围。 |
| sort | str | 可选 | `published_desc` | 发布时间排序方式。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[tuple[NewsDocumentRef, ...]] | 公开返回类型。 |
| data | tuple[NewsDocumentRef, ...] | FetchResult 中的去重新闻引用。 |
| provider | str \| None | 所有返回引用来自同一 Provider 时返回其标识，否则为 None。 |
| captured_at | datetime | 返回引用中最大的 captured_at；空结果使用带时区的当前时间。 |
| source_occurrences | tuple | 去重事件保留的全部数据源出现记录。 |
| provenance | object | 引用对应的数据源引用和采集元数据。 |

### `fx.market_news.get_document(ref)`

**提供什么数据**
根据 `fx.market_news.search(...)` 返回的引用，读取一条完整的全市场新闻详情。

**数据源**
`aigupiao.market_news`、`baidu.finscope.market_news`

**示例**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.market_news.search(
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    sort="published_desc",  # 按发布时间从新到旧。
)

if search_result.data:
    ref = search_result.data[0]
    print(ref.document_url)
    result = fx.market_news.get_document(
        ref=search_result.data[0],  # 对应搜索返回的引用。
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('没有找到符合示例搜索条件的文档。')
```

**返回值与推荐用法**
`.data` 返回一条 `StandardRecord`。可从 `result.data.data` 读取文档行载荷中的 `title`、`contentText` 和文档 URL 等字段；用 `.to_dicts()` 导出 JSON 兼容行，并检查 `.warnings` 了解读取问题。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| ref | NewsDocumentRef | 必填 | — | fx.market_news.search(...) 返回的新闻引用。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[document record] | 公开返回类型。 |
| data | 标准文档记录 | 完整的标准化文档记录。 |
| provider_id | str \| None | FetchResult 携带的数据源标识。 |
| dataset_id | str | FetchResult 携带的稳定数据集标识。 |
| to_dicts() | list[dict[str, object]] | 标准业务数据导出；单条记录仍返回单元素列表。 |

### `fx.market_news.get_documents(refs)`

**提供什么数据**
根据一组新闻引用，批量读取全市场新闻详情。

**数据源**
`aigupiao.market_news`、`baidu.finscope.market_news`

**示例**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.market_news.search(
    page=1,  # 从第一页开始完整扫描日期范围。
    page_size=20,  # 每页请求的数据行数。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
    sort="published_desc",  # 按发布时间从新到旧。
)

if search_result.data:
    for ref in search_result.data:
        print(ref.document_url)
    result = fx.market_news.get_documents(
        refs=search_result.data,  # 对应搜索返回的引用列表。
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('没有找到符合示例搜索条件的文档。')
```

**返回值与推荐用法**
`.data` 返回按引用顺序排列的 `StandardRecord` 元组。可读取每条记录的文档字段，或用 `.to_dicts()` 导出全部数据行；检查 `.warnings` 了解读取问题。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| refs | Iterable[NewsDocumentRef] | 必填 | — | fx.market_news.search(...) 返回的新闻引用。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[tuple[document record, ...]] | 公开返回类型。 |
| data | tuple[标准文档记录, ...] | 按输入顺序返回完整的标准化文档记录。 |
| provider_id | str \| None | 所有记录来自同一数据源时返回其标识。 |
| dataset_id | str | FetchResult 携带的稳定数据集标识。 |
| to_dicts() | list[dict[str, object]] | 所有记录的标准业务数据导出。 |

### `fx.forum.replies(cookies=..., user_names=[...])`

**提供什么数据**
只返回当前账号动态中同时拥有原始定位链接、独立回复正文和完整嵌套引用上下文的记录；其他动态会被排除。

**数据源**
`taoguba.forum`

**示例**

```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"

result = fx.forum.replies(
    cookies=cookies,  # 调用者自己的登录 Cookie；按秘密凭证保管。
    user_names=["洛飞超短笔记", "zarili"],  # 从动态中精确保留这些用户名。
    max_results=50,  # 最多返回 50 条匹配结果。
    since="2026-09-01",  # 包含在内的发布时间/回复时间下界。
    until="2026-09-23",  # 包含在内的发布时间/回复时间上界。
)

print(result.data)
print(result.to_dicts()[:1])
print(result.warnings)
```

**返回值与推荐用法**
返回 `FetchResult[tuple[ForumReply, ...]]`。用 `replyContent`、`parentContent`、`username` 和 `replyTime` 查看匹配回复；用 `replyUrl` 打开来源回复。`.to_dicts()` 可导出数据行，`.warnings` 可检查分页不完整等可恢复问题。 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 保留在结果对象上，供采集审计使用。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| cookies | str \| Mapping[str, str] | 必填 | — | 调用者提供的 Cookie header，仅用于固定动态页 GET。 |
| user_names | Sequence[str] \| None | 可选 | None | 只精确过滤当前动态页中可见的用户名，不搜索其他用户。 |
| max_results | int \| None | 可选 | None | 最多返回的完整上下文回复数量。 |
| since / until | date \| datetime \| str \| None | 可选 | None | 回复时间范围。 |

**输出字段**

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| 返回类型 | FetchResult[tuple[ForumReply, ...]] | 公开返回类型。 |
| data | tuple[ForumReply, ...] | 统一 FinchX FetchResult 中的完整上下文回复。 |
| provider | str | 淘股吧论坛 Provider 标识。 |
| dataset_id | str | forum.replies@1.0 数据集标识。 |
| captured_at | datetime | 最大 aware 采集时间；空结果使用 Provider clock。 |
| provenance | tuple[Source, ...] | 直接来源；不会包含 Cookie。 |
| to_dicts() | list[dict[str, object]] | 导出 replyContent、parentContent 等 camelCase 字段。 |

## 4.7 盘后复盘

### `fx.market.daily_replay(...)`

**提供什么数据**
获取指定日期的每日复盘数据。

**数据源**
`jiuyangongshe.daily_replay`

**示例**

<!-- api-example: market.daily_replay -->
```python
from finchx import FinchX

fx = FinchX()
jygs_session = "<SESSION cookie from your logged-in browser>"

result = fx.market.daily_replay(
    requested_date="2026-09-23",  # 复盘日期。
    session=jygs_session,  # 调用者自己的韭研公社 SESSION Cookie。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketDailyReplayData` 的业务字段包括 `requestedDate`, `tradeDate`, `themes` 等。用 `tradeDate` 确认返回的交易日，再检查 `themes` 完成盘后复盘。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| requested_date | date \| str | 必填 | — | 复盘日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |
| session | str | 必填 | — | 韭研公社 Provider 必填的已认证 SESSION Cookie；按密码处理，切勿记录或持久化。 |

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
| instrumentId | str | 证券代码。 |
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

**示例**

<!-- api-example: market.dragon_tiger_detail -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.dragon_tiger_detail(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    trade_date="2026-09-23",  # 交易日期。
    trade_id="600519-20260923-01",  # 示例数据源交易标识。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketDragonTigerDetailData` 的业务字段包括 `instrumentId`, `name`, `tradeDate`, `tradeId` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |
| trade_date | date \| str | 必填 | — | 交易日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |
| trade_id | str | 必填 | — | 龙虎榜交易标识。 |

**输出字段**

数据模型：`MarketDragonTigerDetailData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

**示例**

<!-- api-example: market.dragon_tiger_list -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.dragon_tiger_list(
    trade_date="2026-09-23",  # 交易日期。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `MarketDragonTigerListData` 的业务字段包括 `instrumentId`, `name`, `tradeDate`, `tradeId` 等。使用这些业务字段进行后续筛选、比较或绘图。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| trade_date | date \| str | 必填 | — | 交易日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |

**输出字段**

数据模型：`MarketDragonTigerListData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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

## 4.8 监管类：偏离值

### `fx.market.deviation(...)`

**提供什么数据**
计算经过审计的基于收盘价的偏离值。

**数据源**
由 `market.ohlcv` 和 `reference.trading_calendar` 在本地计算；无直接 Provider。

**计算口径与适用范围**
这是基于收盘价的确定性计算，不是交易所公告、盘中估算、全市场扫描或特定应用的触发状态。
适用个股为 SSE `60xxxx`、`68xxxx` 和 SZSE `00xxxx`、`30xxxx`；暂不支持 BSE 个股。不同板块使用对应的基准指数：

| 代码范围 | 板块 | 基准指数 |
| --- | --- | --- |
| SSE `60xxxx` | SSE 主板 | SSE A Share Index (`000002`) |
| SSE `68xxxx` | 科创板 | SSE STAR 50 Index (`000688`) |
| SZSE `00xxxx` | SZSE 主板 | SZSE A Share Index (`399107`) |
| SZSE `30xxxx` | 创业板 | ChiNext Composite Index (`399102`) |

股票收益使用前复权日 K 收盘价，基准收益使用未复权指数点位；交易时段取自 A 股交易日历。每个窗口按以下方式计算：

```text
stock_return = 当前股票收盘价 / 窗口基准股票收盘价 - 1
benchmark_return = 当前指数点位 / 窗口基准指数点位 - 1
deviation = stock_return - benchmark_return
```

基准值为所选窗口起点前一交易日的收盘价或指数点位。比例以小数表示（`0.03` 即 3%）。默认的 `max_deviation_scan` 会选择股票与基准收益差最大的合资格起点；`strict_exchange_window` 使用按交易所窗口形状确定的起点。不支持的代码或不足的对齐历史数据会报错，不会返回零值。
结果中的 `calculationMode` 为 `official_close`，`priceBasis` 为 `qfq_stock__raw_index`，`ruleVersion` 标识采用的冻结规则集。

| 窗口 | 上阈值 | 下阈值 |
| --- | --- | --- |
| 10 个交易日 | `+1.00` | `-0.50` |
| 30 个交易日 | `+2.00` | `-0.70` |

**示例**

<!-- api-example: market.deviation -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.deviation(
    instrument="600519",  # 六位 A 股代码；接口会解析其市场。
    windows=(10, 30),  # 比较 10 和 30 个交易时段。
    as_of="2026-09-23",  # 纳入计算的最后一个已完成交易日。
    window_convention="max_deviation_scan",  # 使用文档说明的偏离窗口算法。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是一个 `DeviationData` 模型。 Dataset 行模式 `DeviationData` 的业务字段包括 `instrumentId`, `board`, `effectiveAsOf`, `calculationMode` 等。遍历 `windows` 比较各个交易窗口，并将 `effectiveAsOf` 与结果一起保留。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| instrument | str | 必填 | — | 六位证券代码；FinchX 根据接口语义解析市场。 |
| windows | Sequence[int] | 可选 | (10, 30) | 以交易时段计的偏离窗口。 |
| as_of | date \| str \| None | 可选 | None | 可选的已完成交易时段日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |
| window_convention | DeviationWindowConvention | 可选 | DeviationWindowConvention.MAX_DEVIATION_SCAN | 偏离窗口解释方式。 |

**输出字段**

数据模型：`DeviationData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
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
| benchmarkInstrument | str | — |
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

## 4.9 其他

### `fx.reference.trading_calendar(...)`

**提供什么数据**
获取日期范围内每个自然日的 A 股交易日标记。

**数据源**
`szse.official.calendar`, `pandas_market_calendars`

**日历语义与数据来源**
结果按日期升序排列，日期完整且不重复。日期是日历标签而不是时刻；此接口只回答某日是否为交易日，不提供交易时段、午休、开盘/收盘时间戳或前后交易日辅助方法。
主要来源按范围读取深交所官方月度日历，并要求明确返回每个自然日。若传输、解析或完整性校验失败，配置的备用来源会处理完整范围；结果不会混用多个来源。安装可选 `calendar` extra 后可启用离线 `pandas_market_calendars` 备用来源，其节假日日程取决于软件包版本。
每条 StandardRecord 使用 `CN_A:YYYY-MM-DD` 作为记录和实体标识。日历日期的 `eventAt` 和 `asOf` 为 null；`capturedAt` 与来源元数据描述数据获取信息。

**示例**

<!-- api-example: reference.trading_calendar -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.reference.trading_calendar(
    start_date="2026-09-01",  # 包含在内的开始日期。
    end_date="2026-09-23",  # 包含在内的结束日期。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `TradingCalendarData` 的业务字段包括 `date`, `isTradingDay` 等。闭区间内每个自然日各返回一行，接口固定使用统一的 A 股交易日历。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| start_date | date \| str | 必填 | — | 包含在内的开始日期。 |
| end_date | date \| str | 必填 | — | 包含在内的结束日期；支持 YYYY-MM-DD、YYYYMMDD 或 YYYY/MM/DD 字符串。 |

**输出字段**

数据模型：`TradingCalendarData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| date | date | 日期。 |
| isTradingDay | bool | — |

### `fx.hotlist.convertible_bonds(...)`

**提供什么数据**
获取可转债热度榜；尚未产生涨跌幅的转债会保留空值。

**数据源**
`tonghuashun.hotlist`

**示例**

<!-- api-example: hotlist.convertible_bonds -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.convertible_bonds(
    limit=20,  # 最多返回 20 行。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `HotConvertibleBondData` 的业务字段包括 `rank`, `symbol`, `name`, `changePct` 等。用排名和实体字段查看或比较榜单靠前的对象。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| limit | int | 可选 | 20 | 必填；正整数或 None；None 表示不限制返回数量。 |

**输出字段**

数据模型：`HotConvertibleBondData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| rank | int | 该榜单中的名次。 |
| symbol | str | 六位证券代码。 |
| name | str | 名称。 |
| changePct | Decimal \| None | 涨跌幅比例小数；来源百分点数值除以 100。 |
| heat | Decimal \| None | 来源热度指标；仅在对应榜单内比较。 |

### `fx.hotlist.etfs(...)`

**提供什么数据**
获取 ETF 热榜，按同花顺关注热度指标排序并补充标签。

**数据源**
`tonghuashun.hotlist`

**示例**

<!-- api-example: hotlist.etfs -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.etfs(
    category="cross_border",  # 人气榜类别。
    limit=20,  # 最多返回 20 行。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `HotEtfData` 的业务字段包括 `rank`, `symbol`, `instrumentId`, `name` 等。用排名和实体字段查看或比较榜单靠前的对象。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| category | str | 可选 | 'popular' | 可选 `popular`（热门 ETF）、`t0`（T+0 ETF）、`price_limit_20`（20% 涨跌幅限制 ETF）、`cross_border`（跨境 ETF）或 `commodity`（商品 ETF）。 |
| limit | int | 可选 | 20 | 可选正整数，最小值为 1，默认值为 20。 |

**输出字段**

数据模型：`HotEtfData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| rank | int | 该榜单中的名次。 |
| symbol | str | 六位证券代码。 |
| instrumentId | str | 证券代码。 |
| name | str | 名称。 |
| changePct | Decimal \| None | 涨跌幅比例小数；来源百分点数值除以 100。 |
| heat | Decimal | 来源热度指标；仅在对应榜单内比较。 |
| tags | list[str] | 去重后的 ETF 标签；标签补充失败时为空列表。 |

### `fx.hotlist.content(...)`

**提供什么数据**
获取主题、热评或热文内容榜；三种内容返回各自的数据结构。

**数据源**
`tonghuashun.hotlist`

**示例**

<!-- api-example: hotlist.content -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.content(
    content_type="topic",  # 话题内容榜。
    limit=20,  # 最多返回 20 行。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `HotContentData` 的业务字段包括 `root` 等。用排名和实体字段查看或比较榜单靠前的对象。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| content_type | str | 可选 | 'topic' | 可选 `topic`（话题）、`comment`（热评）或 `article`（热文）。 |
| limit | int | 可选 | 20 | 可选正整数，最小值为 1，默认值为 20。 |

**输出字段**

数据模型：`HotContentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| root | HotTopicData \| HotCommentData \| HotArticleData | — |

嵌套业务模型： `HotArticleData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| contentType | Literal['article'] | 内容榜结构：主题、热评或热文。 |
| rank | int | 该榜单中的名次。 |
| title | str | 内容标题。 |
| heat | Decimal \| None | 来源热度指标；仅在对应榜单内比较。 |
| likeRatio | Decimal \| None | 单位核实前为 None；此时文章记录的 Quality 会标记为部分数据（PARTIAL）。 |
| commentRatio | Decimal \| None | 单位核实前为 None；此时文章记录的 Quality 会标记为部分数据（PARTIAL）。 |
| contentId | str \| None | 来源内容标识（如有）。 |
| url | str \| None | 来源提供时的内容链接。 |
| relatedStocks | list[HotArticleRelatedStock] | 文章关联项保留来源代码、名称和 stockMarket 编号；无法表示其市场或证券类型时 instrumentId 为 null。 |

嵌套业务模型： `HotCommentData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| contentType | Literal['comment'] | 内容榜结构：主题、热评或热文。 |
| rank | int | 该榜单中的名次。 |
| symbol | str | 六位证券代码。 |
| instrumentId | str | 证券代码。 |
| name | str | 名称。 |
| changePct | Decimal \| None | 涨跌幅比例小数；来源百分点数值除以 100。 |
| heat | Decimal \| None | 来源热度指标；仅在对应榜单内比较。 |
| text | str \| None | 有评论详情时的正文。 |
| likes | int \| None | 来源提供时的点赞数。 |
| contentId | str \| None | 来源内容标识（如有）。 |

嵌套业务模型： `HotTopicData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| contentType | Literal['topic'] | 内容榜结构：主题、热评或热文。 |
| rank | int | 该榜单中的名次。 |
| title | str | 内容标题。 |
| summary | str \| None | 来源提供时的主题摘要。 |
| heat | Decimal \| None | 来源热度指标；仅在对应榜单内比较。 |
| url | str \| None | 来源提供时的内容链接。 |
| relatedStocks | list[HotRelatedStock] | 来源提供时关联的股票。 |

嵌套业务模型： `HotArticleRelatedStock`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 原样保留的来源证券代码。 |
| instrumentId | str \| None | 仅在来源市场与代码号段均可确认时构造 CN_A 股票或 ETF 标识；否则为 null。 |
| name | str | 名称。 |
| changePct | Decimal \| None | 涨跌幅比例小数；来源百分点数值除以 100。 |
| sourceMarket | str \| None | 同花顺原始 stockMarket 编号，不是 FinchX 市场枚举。 |

嵌套业务模型： `HotRelatedStock`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| symbol | str | 六位证券代码。 |
| instrumentId | str | 证券代码。 |
| name | str | 名称。 |
| changePct | Decimal \| None | 涨跌幅比例小数；来源百分点数值除以 100。 |

### `fx.iwencai.select(...)`

**提供什么数据**
使用登录 Cookie 执行问财自然语言选股，并返回标准化股票记录。

**数据源**
`iwencai`

**示例**

<!-- api-example: iwencai.select -->
```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"

result = fx.iwencai.select(
    query="成交额排名前500，最新价高于5日均线，非ST",  # 问财自然语言条件。
    cookies=cookies,  # 调用者自己的登录 Cookie；按秘密凭证保管。
    user_agent="Mozilla/5.0 (compatible; FinchX documentation example)",  # 兼容浏览器的请求头。
    page_size=20,  # 每页请求的数据行数。
    max_pages=5,  # 限制问财最多读取的页数。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `IwencaiSelectionData` 的业务字段包括 `instrumentId`, `name`, `price`, `changeRate` 等。使用规范化字段和 `extraFields` 进行筛选或继续研究。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| query | str | 必填 | — | 参数。 |
| cookies | str \| Mapping[str, str] | 必填 | — | 调用者提供的问财/同花顺登录态 Cookie header。 |
| user_agent | str \| None | 可选 | None | 可选的浏览器 User-Agent。 |
| page_size | int | 可选 | 100 | 单页数量。 |
| max_pages | int | 可选 | 100 | 参数。 |

**输出字段**

数据模型：`IwencaiSelectionData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| instrumentId | str | 证券代码。 |
| name | str \| None | 名称。 |
| price | Decimal \| None | — |
| changeRate | Decimal \| None | — |
| amplitude | Decimal \| None | — |
| volume | int \| None | — |
| amount | Decimal \| None | — |
| turnoverRate | Decimal \| None | — |
| extraFields | dict[str, Any] | — |

### `fx.iwencai.search(...)`

**提供什么数据**
使用 SkillHub OpenAPI 语义搜索研报、公告或新闻，并返回标准化命中记录。

**数据源**
`iwencai`

**示例**

<!-- api-example: iwencai.search -->
```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"
api_key = "<IWENCAI_API_KEY>"

result = fx.iwencai.search(
    query="人形机器人 行星滚柱丝杠",  # 问财自然语言条件。
    channel="report",  # 搜索研报。
    size=20,  # 语义搜索命中数量。
    cookies=cookies,  # 调用者自己的登录 Cookie；按秘密凭证保管。
    api_key=api_key,  # SkillHub API Key；从密钥存储读取。
    deduplicate=True,  # 去除重复命中。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `IwencaiSearchData` 的业务字段包括 `uid`, `title`, `publishedAt`, `url` 等。使用规范化字段和 `extraFields` 进行筛选或继续研究。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| query | str | 必填 | — | 参数。 |
| channel | str | 可选 | 'report' | 参数。 |
| size | int | 可选 | 50 | 参数。 |
| cookies | str \| Mapping[str, str] \| None | 可选 | None | 调用者提供的问财/同花顺登录态 Cookie header。 |
| api_key | str \| None | 可选 | None | 参数。 |
| deduplicate | bool | 可选 | True | 参数。 |

**输出字段**

数据模型：`IwencaiSearchData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| uid | str \| None | — |
| title | str | 内容标题。 |
| publishedAt | str \| None | — |
| url | str \| None | — |
| score | float | — |
| extraFields | dict[str, Any] | — |

### `fx.iwencai.report_detail(...)`

**提供什么数据**
通过搜索结果中的研报链接获取正文和结构化研报元数据。

**数据源**
`iwencai`

**示例**

<!-- api-example: iwencai.report_detail -->
```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"

result = fx.iwencai.report_detail(
    url="https://stock.10jqka.com.cn/20260923/c680236250.shtml",  # 公开文章或研报详情 URL。
    cookies=cookies,  # 调用者自己的登录 Cookie；按秘密凭证保管。
    uid="example-report-uid",  # 备用研报标识。
    title="示例研报标题",  # 备用研报标题。
    published_at="2026-09-23",  # 备用发布日期。
    user_agent="Mozilla/5.0 (compatible; FinchX documentation example)",  # 兼容浏览器的请求头。
)
print(result.data)  # 原生类型数据或记录。
rows = result.to_dicts()  # JSON 兼容的业务数据行。
print(rows[:1])
print(result.warnings)  # 检查部分数据和可恢复问题。
```

**返回值与推荐用法**
返回 `FetchResult`。`.data` 是标准化记录元组；每条记录的 `.data` 保存 Dataset 行载荷。 Dataset 行模式 `IwencaiReportDetailData` 的业务字段包括 `documentId`, `sourceDocumentId`, `title`, `contentText` 等。使用规范化字段和 `extraFields` 进行筛选或继续研究。 用 `.to_dicts()` 导出 JSON 兼容数据，并检查 `.warnings` 了解部分结果情况。 `.dataset_id`、`.provider_id`、`.captured_at`、`.provenance`、`.attempts`、`.fallback_used` 和 `.cache_hit` 提供采集与审计信息。

**参数**

| 参数 | 类型 | 必填 / 模式 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| url | str | 必填 | — | 问财研报搜索结果中的详情页 URL，必须包含受支持的 duid。 |
| cookies | str \| Mapping[str, str] | 必填 | — | 调用者提供的问财/同花顺登录态 Cookie header。 |
| uid | str \| None | 可选 | None | 可选的搜索结果研报 UID，用作备用值。 |
| title | str \| None | 可选 | None | 可选的搜索结果研报标题，用作备用值。 |
| published_at | str \| None | 可选 | None | 可选的搜索结果发布日期，用作备用值。 |
| user_agent | str \| None | 可选 | None | 可选的浏览器 User-Agent。 |

**输出字段**

数据模型：`IwencaiReportDetailData`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| documentId | str | FinchX 生成的研报标识。 |
| sourceDocumentId | str | 来源研报 UID。 |
| title | str | 研报标题。 |
| contentText | str | 详情接口返回的可读研报文本。 |
| publishedAt | datetime \| None | 详情接口返回的发布日期。 |
| contentAvailable | bool | 是否有可读取的正文文本。 |
| relatedInstruments | list[str] | 数据源提供时关联的证券列表。 |
| url | AnyUrl | 研报详情页链接。 |
| originalUrl | AnyUrl \| None | 详情接口返回的发布方或来源链接。 |
| organization | str \| None | 研究机构。 |
| analyst | str \| None | 报告分析师或研究员。 |
| fileExtension | str \| None | 来源研报文件扩展名（如有）。 |
| sourceCreatedAt | str \| None | 详情接口原样返回的来源创建时间。 |
| extraFields | dict[str, Any] | 数据源返回的其他研报元数据。 |

## 5. 通用说明

### 证券输入规则

- 裸代码会按接口语义解析：股票接口把 `000001` 解释为深市股票，指数接口把 `000001` 解释为上证指数。
- 支持的代码前缀和市场规则由 FinchX 在内部校验，调用方只需传入代码字符串。

### 日期输入

公开日期参数接受 `datetime.date`，或 `YYYY-MM-DD`、`YYYYMMDD`、`YYYY/MM/DD` 三种无歧义字符串。非法日期和 `09/01/2026` 这类歧义格式会被拒绝。仅日期字段不接受 `datetime`；新闻、公告、全市场新闻和论坛的时间范围也接受带时区 `datetime`。

### Warnings

`result.warnings` 用于记录可恢复的数据质量或兼容性问题，例如跳过存在 schema drift 的单条 News 记录。

### 按日期范围搜索

`news.search`、`disclosure.search`、`market_news.search` 和 `forum.replies` 的 `since` 与 `until` 是包含边界的时间筛选。请从 `page=1` 开始；Client 会在安全上限内跨页扫描，在降序结果到达早于起始日期的整页或数据源耗尽时停止，并遵守 `max_results`。如果触及安全上限时仍未到达日期边界或源末尾，`result.warnings` 会说明结果可能不完整。需要控制返回量时设置合适的 `max_results`，并在要求完整性时检查 warnings。

### 文档 URL

新闻引用中的 `sourceUrl` 指向数据源的搜索/列表页，`documentUrl` 指向文章正文。需要文章链接时使用 `ref.document_url`；如果旧代码把 `ref.source_url` 当正文链接，应迁移到 `ref.document_url`。公告引用的 `sourceUrl` 指向来源查询页，`originalDocumentUrl` 仍指向公告或附件原文。公告 `sourceRecordedAt` 保存在 `provenance.adjustments` 中，是东方财富内部记录时间，不是公告发布时间；展示公告时间请使用 `publishedAt`。

### FetchResult 用法

所有方法都返回 `FetchResult`。记录型接口的 `.data` 为标准化 `StandardRecord` 元组；单条文档详情返回一个 `StandardRecord`，文档搜索返回带类型的引用元组，计算型偏离值返回 `DeviationData`。`Dataset.data_type` 描述每行的业务载荷 schema，`FetchResult.data` 则承载实际运行时记录或引用结构。用 `result.to_dicts()` 导出业务字典，并检查 `result.warnings` 了解部分数据情况。采集信息可从 `dataset_id`、`provider_id`、`captured_at`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit` 读取。
