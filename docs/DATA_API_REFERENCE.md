# FinchX Data API Reference

English | [简体中文](DATA_API_REFERENCE.zh-CN.md)

This document covers 54 data interfaces and 1 computed capability, for 55 core capabilities.

## 1. What FinchX is / Architecture overview

FinchX is a small client for normalized Chinese market data. You call one public Client; FinchX validates the request, fetches a source-backed dataset, and returns one consistent result shape.

| Layer | What it does |
| --- | --- |
| Client | `FinchX()` is the user-facing entry point. |
| Dataset | Defines the stable request and business-data schema. |
| Provider | Implements one real external data source. |
| Collector | Routes the request to a Provider and builds `FetchResult`. |
| FetchResult | Shows business data first; audit fields remain on `provider`, `provenance`, `attempts`, `warnings`, and `cache_hit`. |

## 2. Quick start

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # Six-digit A-share code; endpoint resolves its market.
)

print(result.data)
rows = result.to_dicts()
print(rows[:1])
print(result.warnings)

```

`result.data` retains the native typed payload. `to_dicts()` is FinchX's standard export method: it always returns a list of business-data dictionaries, including for a single record, and preserves nested lists and objects. Inspect `result.warnings` for partial or recoverable issues. Each interface section below includes a complete example call.

## 3. Interface overview

### Market sentiment

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.breadth(...)` | Fetch the current market breadth snapshot. | `eastmoney.push2ex.breadth` |
| `fx.market.sentiment(...)` | Fetch the market sentiment snapshot. | `aigupiao.market_sentiment` |
| `fx.market.broken_limit_pool(...)` | Fetch the latest broken-limit pool snapshot. | `eastmoney.push2ex.broken_limit_pool` |
| `fx.market.consecutive_limit_up(...)` | Fetch the consecutive-limit-up snapshot. | `aigupiao.series_limit_up` |
| `fx.market.limit_down_pool(...)` | Fetch the latest limit-down pool snapshot. | `eastmoney.push2ex.limit_down_pool` |
| `fx.market.limit_up_pool(...)` | Fetch the latest limit-up pool snapshot. | `eastmoney.push2ex.limit_up_pool` |
| `fx.market.strong_pool(...)` | Fetch the latest strong-pool snapshot. | `eastmoney.push2ex.strong_pool` |
| `fx.market.yesterday_limit_up_pool(...)` | Fetch the latest yesterday-limit-up pool snapshot. | `eastmoney.push2ex.yesterday_limit_up_pool` |

### Index quotes

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.index_intraday(...)` | Fetch one index intraday session. | `tencent.finance.qq.intraday` |
| `fx.market.index_intraday_5d(...)` | Fetch five-day index intraday data. | `tencent.finance.qq.intraday` |

### Sector data and hotlists

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.hotlist.sectors(...)` | Fetch concept, industry, or index-sector heat rankings with available ETF enrichment. | `tonghuashun.hotlist` |
| `fx.hotlist.stocks(...)` | Fetch A-share stock heat rankings by category and 1-hour or 24-hour period. | `tonghuashun.hotlist` |
| `fx.market.concept_list(...)` | Fetch the complete available Tonghuashun concept directory. | `tonghuashun.concept` |
| `fx.market.concept_quote_snapshot(...)` | Fetch the current index-point quote and available breadth/flow for one concept. | `tonghuashun.concept` |
| `fx.market.concept_ohlcv(...)` | Fetch inclusive daily index-point OHLCV bars for one concept. | `tonghuashun.concept` |
| `fx.market.industry_comparison(...)` | Fetch the market industry comparison. | `tencent.finance.qq.industry` |
| `fx.market.instrument_sector_snapshot(...)` | Fetch sector tags and snapshots for an instrument. | `tencent.finance.qq.sector` |

### Individual stock quotes

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.equity_intraday(...)` | Fetch one equity intraday session. | `tencent.finance.qq.intraday` |
| `fx.market.equity_intraday_5d(...)` | Fetch five-day equity intraday data. | `tencent.finance.qq.intraday` |
| `fx.market.fund_flow_daily(...)` | Fetch daily fund-flow data. | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_intraday(...)` | Fetch intraday fund-flow data. | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_snapshot(...)` | Fetch the fund-flow snapshot. | `tencent.finance.qq.fund_flow` |
| `fx.market.ohlcv(...)` | Fetch OHLCV history for one instrument. | `tencent.finance.qq.klines`, `sohu.finance.klines` |
| `fx.market.orderbook(...)` | Fetch the order book. | `tencent.finance.qq.quote` |
| `fx.market.quote(...)` | Fetch a full-market A-share quote snapshot. | `tencent.finance.qq.market` |
| `fx.market.ranking(...)` | Rank A-share stocks by traded amount, price change, or volume. | `tencent.finance.qq.market` |
| `fx.market.quote_snapshot(...)` | Fetch one quote snapshot. | `tencent.finance.qq.quote` |

### Individual stock information and fundamentals

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.fundamental.company_profile(...)` | Fetch a company's profile. | `tencent.finance.qq.f10` |
| `fx.fundamental.financial_summary(...)` | Fetch a company's financial summary. | `tencent.finance.qq.f10` |
| `fx.fundamental.industry_comparison(...)` | Fetch the fundamental industry comparison. | `tencent.finance.qq.f10` |
| `fx.fundamental.revenue_breakdown(...)` | Fetch a company's revenue breakdown. | `tencent.finance.qq.f10` |
| `fx.financial.statements(...)` | Fetch financial statements. | `tonghuashun.financial` |
| `fx.market.stock_keyword(...)` | Fetch EastMoney source-ranked hot keywords for an instrument. | `eastmoney.stockrank` |
| `fx.ownership.capital_snapshot(...)` | Fetch a capital snapshot. | `tencent.finance.qq.f10` |
| `fx.ownership.float_holder(...)` | Fetch floating-holder data. | `tencent.finance.qq.float_holder` |
| `fx.ownership.holder_summary_snapshot(...)` | Fetch a holder-summary snapshot. | `tencent.finance.qq.f10` |
| `fx.company.executive_share_change(...)` | Fetch executive share changes. | `tencent.finance.qq.f10` |
| `fx.company.executive_snapshot(...)` | Fetch an executive snapshot. | `tencent.finance.qq.f10` |
| `fx.corporate_action.dividend(...)` | Fetch dividend actions. | `tencent.finance.qq.f10` |
| `fx.corporate_action.repurchase(...)` | Fetch repurchase actions. | `tencent.finance.qq.f10` |

### News and disclosures

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.news.search(...)` | Search news metadata and return document references. | `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news` |
| `fx.articles.get(...)` | Fetch one ordinary news or community article from its public Tonghuashun URL. | `tonghuashun.articles` |
| `fx.articles.from_topic(...)` | List supported news and long-article refs from a T-code topic's mixed feed; each returned URL is accepted by `articles.get`. | `tonghuashun.topic` |
| `fx.disclosure.search(...)` | Search disclosures and return document references. | `eastmoney.disclosure` |
| `fx.news.get_document(ref)` / `fx.news.get_documents(refs)` | Fetch individual-stock news details from search references. | `eastmoney.news` |
| `fx.disclosure.get_document(ref)` / `fx.disclosure.get_documents(refs)` | Fetch individual-stock disclosure details from search references. | `eastmoney.disclosure` |
| `fx.market_news.search(...)` / `fx.market_news.get_document(s)(...)` | Search all-market news and fetch its complete document details. | `aigupiao.market_news`, `baidu.finscope.market_news` |
| `fx.forum.replies(...)` | Read qualified replies from the authenticated Taoguba activity feed. | `taoguba.forum` |

### After-close review

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.daily_replay(...)` | Fetch one daily replay request with an explicit authenticated session. | `jiuyangongshe.daily_replay` |
| `fx.market.dragon_tiger_detail(...)` | Fetch Dragon-Tiger detail data. | `aigupiao.dragon_tiger` |
| `fx.market.dragon_tiger_list(...)` | Fetch Dragon-Tiger list data. | `aigupiao.dragon_tiger` |

### Regulatory deviation

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.deviation(...)` | Calculate close-based relative returns for one supported A-share stock against its board benchmark over 10- or 30-session windows. | — |

### Other

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.reference.trading_calendar(...)` | Return one trading-day flag per natural date in an inclusive A-share range. | `szse.official.calendar`, `pandas_market_calendars` |
| `fx.hotlist.convertible_bonds(...)` | Fetch convertible-bond heat rankings while preserving missing price changes. | `tonghuashun.hotlist` |
| `fx.hotlist.etfs(...)` | Fetch ETF heat rankings sorted by Tonghuashun attention metrics, with available tags. | `tonghuashun.hotlist` |
| `fx.hotlist.content(...)` | Fetch topic, comment, or article rankings with a distinct data shape for each type. | `tonghuashun.hotlist` |
| `fx.iwencai.select(...)` | Run the final table rendered by ``iwencai.com/screener``. | `iwencai` |
| `fx.iwencai.search(...)` | Search reports, announcements, or news with SkillHub OpenAPI. | `iwencai` |
| `fx.iwencai.report_detail(...)` | Fetch report text and metadata linked from ``iwencai.search``. | `iwencai` |

## 4. Interface details

## 4.1 Market sentiment

### `fx.market.breadth(...)`

**What it provides**
Fetch the current market breadth snapshot.

**Data source**
`eastmoney.push2ex.breadth`

**Example**

<!-- api-example: market.breadth -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.breadth()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketBreadthData` has business fields such as `tradeDate`, `advancing`, `declining`, `unchanged`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketBreadthData`

| Field | Type | Meaning |
| --- | --- | --- |
| tradeDate | date | Trade date reported by EastMoney. |
| advancing | int | — |
| declining | int | — |
| unchanged | int | — |
| total | int | — |
| limitUpCount | int | — |
| limitDownCount | int | — |
| upOver10PercentCount | int | — |
| downOver10PercentCount | int | — |
| distribution | list[MarketBreadthDistributionEntry] | — |

Nested business model: `MarketBreadthDistributionEntry`

| Field | Type | Meaning |
| --- | --- | --- |
| bucket | MarketBreadthBucket | — |
| count | int | Number of listed stocks in this return bucket. |

### `fx.market.sentiment(...)`

**What it provides**
Fetch the market sentiment snapshot.

**Data source**
`aigupiao.market_sentiment`

**Example**

<!-- api-example: market.sentiment -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.sentiment()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketSentimentData` has business fields such as `marketTemperature`, `totalTurnover`, `forecastedTurnover`, `turnoverChangeAmount`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketSentimentData`

| Field | Type | Meaning |
| --- | --- | --- |
| marketTemperature | Decimal | Aigupiao source-defined sentiment temperature; not a physical temperature or ratio. |
| totalTurnover | Decimal \| None | — |
| forecastedTurnover | Decimal \| None | Source forecast, not observed turnover. |
| turnoverChangeAmount | Decimal \| None | Source-reported change in turnover amount versus the prior day. |
| blastBreakRatio | Decimal \| None | Source-defined ratio; FinchX does not reproduce the denominator. |
| previousLimitUpBreakChangeRatio | Decimal \| None | Source-defined previous broken-limit performance ratio. |
| stopTradingCount | int | — |
| oneLimitUpCount | int | — |
| twoLimitUpCount | int | — |
| threeLimitUpCount | int | — |
| highLimitUpCount | int | — |
| twoLimitUpPromotionRatio | Decimal \| None | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| threeLimitUpPromotionRatio | Decimal \| None | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| highLimitUpPromotionRatio | Decimal \| None | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| previousLimitUpThemeChangeRatio | Decimal \| None | Source-defined previous limit-up group performance ratio. |
| previousConsecutiveLimitUpThemeChangeRatio | Decimal \| None | Source-defined previous consecutive-limit-up group performance ratio. |

### `fx.market.broken_limit_pool(...)`

**What it provides**
Fetch the latest broken-limit pool snapshot.

**Data source**
`eastmoney.push2ex.broken_limit_pool`

**Example**

<!-- api-example: market.broken_limit_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.broken_limit_pool()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketBrokenLimitPoolData` has business fields such as `instrumentId`, `tradeDate`, `name`, `price`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketBrokenLimitPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Trade date. |
| name | str | Name. |
| price | Decimal | Latest price in CNY per share. |
| limitUpPrice | Decimal | Current-session limit-up price in CNY per share. |
| changeRate | Decimal | Ratio fraction. |
| amount | Decimal | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Monetary amount in CNY. |
| marketCapitalization | Decimal | Monetary amount in CNY. |
| turnoverRate | Decimal | Ratio fraction. |
| amplitude | Decimal | Current-session amplitude as a ratio fraction. |
| firstLimitUpTime | str \| None | — |
| limitUpBreakCount | int | — |
| industry | str | — |
| limitUpStats | MarketBrokenLimitPoolStats | — |

Nested business model: `MarketBrokenLimitPoolStats`

| Field | Type | Meaning |
| --- | --- | --- |
| lookbackDays | int | — |
| limitUpCount | int | — |

### `fx.market.consecutive_limit_up(...)`

**What it provides**
Fetch the consecutive-limit-up snapshot.

**Data source**
`aigupiao.series_limit_up`

**Example**

<!-- api-example: market.consecutive_limit_up -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.consecutive_limit_up()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketConsecutiveLimitUpData` has business fields such as `instrumentId`, `name`, `tradeDate`, `lastPrice`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketConsecutiveLimitUpData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| tradeDate | date | Trade date. |
| lastPrice | Decimal | Price per share; currency is CNY. |
| change | Decimal | Signed price change in CNY per share. |
| changeRatio | Decimal | Ratio fraction; 10% is 0.10. |
| turnoverRatio | Decimal | Ratio fraction; 12% is 0.12. |
| amount | Decimal | Monetary amount in CNY. |
| limitUpTime | str | — |
| state | str | — |
| isConsecutiveLimitUp | bool | — |
| consecutiveLimitUpCount | int \| None | — |
| previousConsecutiveLimitUpCount | int \| None | — |
| themeId | int \| None | — |
| themeName | str \| None | — |
| floatShares | int | A non-negative whole number of shares. |
| totalShares | int | A non-negative whole number of shares. |
| marketCap | Decimal | Total market capitalization in CNY. |

### `fx.market.limit_down_pool(...)`

**What it provides**
Fetch the latest limit-down pool snapshot.

**Data source**
`eastmoney.push2ex.limit_down_pool`

**Example**

<!-- api-example: market.limit_down_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_down_pool()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketLimitDownPoolData` has business fields such as `instrumentId`, `tradeDate`, `name`, `price`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketLimitDownPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Trade date. |
| name | str | Name. |
| price | Decimal | Latest price in CNY per share. |
| changeRate | Decimal | Ratio fraction; -10% is -0.10. |
| amount | Decimal | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Monetary amount in CNY. |
| marketCapitalization | Decimal | Monetary amount in CNY. |
| priceEarningsRatio | Decimal \| None | EastMoney-reported dynamic P/E; source calculation details are unspecified. |
| turnoverRate | Decimal | Ratio fraction. |
| limitDownQueueAmount | Decimal \| None | EastMoney-reported limit-down queued amount in CNY. |
| lastLimitDownTime | str \| None | — |
| boardTradedAmount | Decimal \| None | Amount traded at the limit-down price in CNY. |
| consecutiveLimitDownDays | int | — |
| limitDownOpenCount | int | — |
| industry | str | — |

### `fx.market.limit_up_pool(...)`

**What it provides**
Fetch the latest limit-up pool snapshot.

**Data source**
`eastmoney.push2ex.limit_up_pool`

**Example**

<!-- api-example: market.limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_up_pool()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketLimitUpPoolData` has business fields such as `instrumentId`, `tradeDate`, `name`, `price`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketLimitUpPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Trade date. |
| name | str | Name. |
| price | Decimal | Latest price in CNY per share. |
| changeRate | Decimal | Ratio fraction; 10% is 0.10. |
| amount | Decimal | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Monetary amount in CNY. |
| marketCapitalization | Decimal | Monetary amount in CNY. |
| turnoverRate | Decimal | Ratio fraction; 5% is 0.05. |
| consecutiveLimitUpDays | int | — |
| firstLimitUpTime | str \| None | — |
| lastLimitUpTime | str \| None | — |
| limitUpQueueAmount | Decimal \| None | — |
| limitUpBreakCount | int | — |
| industry | str | — |
| limitUpStats | MarketLimitUpStats | — |

Nested business model: `MarketLimitUpStats`

| Field | Type | Meaning |
| --- | --- | --- |
| lookbackDays | int | — |
| limitUpCount | int | — |

### `fx.market.strong_pool(...)`

**What it provides**
Fetch the latest strong-pool snapshot.

**Data source**
`eastmoney.push2ex.strong_pool`

**Example**

<!-- api-example: market.strong_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.strong_pool()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketStrongPoolData` has business fields such as `instrumentId`, `tradeDate`, `name`, `price`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketStrongPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Trade date. |
| name | str | Name. |
| price | Decimal | Latest price in CNY per share. |
| limitUpPrice | Decimal | Current limit-up price in CNY per share. |
| changeRate | Decimal | Ratio fraction; 20% is 0.20. |
| amount | Decimal | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Monetary amount in CNY. |
| marketCapitalization | Decimal | Monetary amount in CNY. |
| turnoverRate | Decimal | Ratio fraction. |
| isSixtyDayHigh | bool | — |
| selectionReason | StrongPoolSelectionReason | — |
| volumeRatio | Decimal | Source volume ratio as a dimensionless multiple. |
| industry | str | — |
| limitUpStats | MarketStrongPoolStats | — |

Nested business model: `MarketStrongPoolStats`

| Field | Type | Meaning |
| --- | --- | --- |
| lookbackDays | int | — |
| limitUpCount | int | — |

### `fx.market.yesterday_limit_up_pool(...)`

**What it provides**
Fetch the latest yesterday-limit-up pool snapshot.

**Data source**
`eastmoney.push2ex.yesterday_limit_up_pool`

**Example**

<!-- api-example: market.yesterday_limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.yesterday_limit_up_pool()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketYesterdayLimitUpPoolData` has business fields such as `instrumentId`, `tradeDate`, `name`, `currentPrice`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `MarketYesterdayLimitUpPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Current observed source date, not the prior limit-up event date. |
| name | str | Name. |
| currentPrice | Decimal | Current-session price in CNY per share. |
| currentLimitUpPrice | Decimal | Current-session limit-up price in CNY per share. |
| currentChangeRate | Decimal | Current-session ratio fraction. |
| currentAmount | Decimal | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Monetary amount in CNY. |
| marketCapitalization | Decimal | Monetary amount in CNY. |
| currentTurnoverRate | Decimal | Current-session turnover ratio fraction. |
| currentAmplitude | Decimal | Current-session amplitude as a ratio fraction. |
| yesterdayFirstLimitUpTime | str \| None | Previous-session first limit-up time, market-local HH:MM:SS. |
| yesterdayConsecutiveLimitUpDays | int | — |
| industry | str | — |

## 4.2 Index quotes

### `fx.market.index_intraday(...)`

**What it provides**
Fetch one index intraday session.

**Data source**
`tencent.finance.qq.intraday`

**Example**

<!-- api-example: market.index_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.index_intraday(
    instrument="000001",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `IndexIntradayData` has business fields such as `instrumentId`, `tradeDate`, `time`, `price`. Use the time and price series to chart the index session. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `IndexIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Source trading-date label; not FinchX capturedAt. |
| time | str | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Volume traded during this minute, in whole shares. |
| amount | Decimal | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Tencent source cumulative traded amount in CNY, unchanged from source. |

### `fx.market.index_intraday_5d(...)`

**What it provides**
Fetch five-day index intraday data.

**Data source**
`tencent.finance.qq.intraday`

**Example**

<!-- api-example: market.index_intraday_5d -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.index_intraday_5d(
    instrument="000001",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `IndexIntradayData` has business fields such as `instrumentId`, `tradeDate`, `time`, `price`. Use the time and price series to chart the index session. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `IndexIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Source trading-date label; not FinchX capturedAt. |
| time | str | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Volume traded during this minute, in whole shares. |
| amount | Decimal | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Tencent source cumulative traded amount in CNY, unchanged from source. |

## 4.3 Sector data and hotlists

### `fx.hotlist.sectors(...)`

**What it provides**
Fetch concept, industry, or index-sector heat rankings with available ETF enrichment.

**Data source**
`tonghuashun.hotlist`

**Example**

<!-- api-example: hotlist.sectors -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.sectors(
    sector_type="industry",  # Industry-sector ranking.
    limit=20,  # Return at most 20 rows.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `HotSectorData` has business fields such as `rank`, `sectorCode`, `name`, `sectorType`. Use the rank and entity fields to inspect or compare the returned leaders. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| sector_type | str | Optional | 'concept' | One of `concept` (concept sectors), `industry` (industry sectors), or `index` (indexes). |
| limit | int | Optional | 20 | Optional positive integer; the minimum is 1 and the default is 20. |

**Output fields**

Data model: `HotSectorData`

| Field | Type | Meaning |
| --- | --- | --- |
| rank | int | Position within this hotlist. |
| sectorCode | str | Public sector identity code. |
| name | str | Name. |
| sectorType | Literal['concept', 'industry', 'index'] | Sector classification used by the ranking. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |
| heat | Decimal \| None | Source heat metric; meaningful within its own ranking. |
| rankChange | int \| None | Change in ranking position when reported by the source. |
| tag | str \| None | Sector note supplied by the source. |
| hotTag | str \| None | Hotlist streak or status label supplied by the source. |
| relatedEtfSymbol | str \| None | Related ETF code when available. |
| relatedEtfName | str \| None | Related ETF name when available. |
| relatedEtfChangePct | Decimal \| None | Related ETF price change as a ratio fraction. |

### `fx.hotlist.stocks(...)`

**What it provides**
Fetch A-share stock heat rankings by category and 1-hour or 24-hour period.

**Data source**
`tonghuashun.hotlist`

**Example**

<!-- api-example: hotlist.stocks -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.stocks(
    category="popular",  # Popularity ranking category.
    period="24h",  # 24-hour ranking window.
    limit=20,  # Return at most 20 rows.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `HotStockData` has business fields such as `rank`, `symbol`, `instrumentId`, `name`. Use the rank and entity fields to inspect or compare the returned leaders. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| category | str | Optional | 'popular' | One of `popular` (popularity), `rising` (rising heat), `new` (new listings), `technical` (technical analysis), `value` (value investing), or `trend` (trend analysis). |
| period | str \| None | Optional | None | Optional ranking window: `1h` or `24h`. `popular` and `rising` support both; other categories support only `24h`. |
| limit | int | Optional | 20 | Optional positive integer; the minimum is 1 and the default is 20. |

**Output fields**

Data model: `HotStockData`

| Field | Type | Meaning |
| --- | --- | --- |
| rank | int | Position within this hotlist. |
| symbol | str | Six-digit security code. |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| category | Literal['popular', 'rising', 'new', 'technical', 'value', 'trend'] | Selected hotlist category. |
| period | Literal['1h', '24h'] | Stock heat ranking period. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |
| heat | Decimal \| None | Source heat metric; meaningful within its own ranking. |
| rankChange | int \| None | Change in ranking position when reported by the source. |
| conceptTags | list[str] | Concept tags supplied by the source. |
| popularityTag | str \| None | Popularity label supplied by the source. |
| analysisTitle | str \| None | Analysis headline supplied by the source. |
| analysis | str \| None | Analysis text supplied by the source. |
| searchCount | int \| None | Search count when reported by the source. |
| updatedAt | datetime \| None | Source update time; naive source times use Asia/Shanghai. |
| pe | Decimal \| None | Issue price-to-earnings multiple for new listings. |

### `fx.market.concept_list(...)`

**What it provides**
Fetch the complete available Tonghuashun concept directory.

**Data source**
`tonghuashun.concept`

**Example**

<!-- api-example: market.concept_list -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.concept_list()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `ConceptRef` has business fields such as `sectorType`, `sectorName`, `providerNamespace`, `providerSectorId`. Use the concept identity and quote or bar fields to compare sector movement. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

None.

**Output fields**

Data model: `ConceptRef`

| Field | Type | Meaning |
| --- | --- | --- |
| sectorType | Literal['concept'] | Sector classification; this reference always represents a concept. |
| sectorName | str | Concept name from the Tonghuashun concept directory. |
| providerNamespace | Literal['tonghuashun_concept'] | Namespace that identifies the provider's concept-ID scheme. |
| providerSectorId | str | Tonghuashun concept page ID, distinct from its quote ID. |

### `fx.market.concept_quote_snapshot(...)`

**What it provides**
Fetch the current index-point quote and available breadth/flow for one concept.

**Data source**
`tonghuashun.concept`

**Example**

<!-- api-example: market.concept_quote_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.concept_quote_snapshot(
    concept="人工智能",  # Exact concept name; use a ConceptRef when available.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `ConceptQuoteSnapshotData` has business fields such as `concept`, `indexLevel`, `previousClose`, `open`. Use the concept identity and quote or bar fields to compare sector movement. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| concept | ConceptRef \| str | Required | — | A ConceptRef returned by concept_list(), or an exact concept name that resolves uniquely. |

**Output fields**

Data model: `ConceptQuoteSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| concept | ConceptRef | — |
| indexLevel | Decimal \| None | — |
| previousClose | Decimal \| None | — |
| open | Decimal \| None | — |
| high | Decimal \| None | — |
| low | Decimal \| None | — |
| levelChange | Decimal \| None | — |
| changeRate | Decimal \| None | Change as a ratio fraction; -0.85% is -0.0085. |
| volume | int \| None | Aggregate constituent trading volume in shares. |
| amount | Decimal \| None | Aggregate constituent traded amount in CNY. |
| netMoneyFlow | Decimal \| None | Net money flow in CNY. |
| riseCount | int \| None | — |
| fallCount | int \| None | — |
| sourceTimestamp | datetime \| None | — |

Nested business model: `ConceptRef`

| Field | Type | Meaning |
| --- | --- | --- |
| sectorType | Literal['concept'] | Sector classification; this reference always represents a concept. |
| sectorName | str | Concept name from the Tonghuashun concept directory. |
| providerNamespace | Literal['tonghuashun_concept'] | Namespace that identifies the provider's concept-ID scheme. |
| providerSectorId | str | Tonghuashun concept page ID, distinct from its quote ID. |

### `fx.market.concept_ohlcv(...)`

**What it provides**
Fetch inclusive daily index-point OHLCV bars for one concept.

**Data source**
`tonghuashun.concept`

**Example**

<!-- api-example: market.concept_ohlcv -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.concept_ohlcv(
    concept="人工智能",  # Exact concept name; use a ConceptRef when available.
    start_date="2026-09-01",  # Inclusive start date.
    end_date="2026-09-23",  # Inclusive end date.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `ConceptOhlcvData` has business fields such as `concept`, `barDate`, `open`, `high`. Use the concept identity and quote or bar fields to compare sector movement. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| concept | ConceptRef \| str | Required | — | A ConceptRef returned by concept_list(), or an exact concept name that resolves uniquely. |
| start_date | date \| str | Required | — | Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| end_date | date \| str | Required | — | Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |

**Output fields**

Data model: `ConceptOhlcvData`

| Field | Type | Meaning |
| --- | --- | --- |
| concept | ConceptRef | — |
| barDate | date | — |
| open | Decimal | An index level or change expressed in index points, not CNY per share. |
| high | Decimal | An index level or change expressed in index points, not CNY per share. |
| low | Decimal | An index level or change expressed in index points, not CNY per share. |
| close | Decimal | An index level or change expressed in index points, not CNY per share. |
| volume | int | A non-negative whole number of shares. |
| amount | Decimal \| None | — |

Nested business model: `ConceptRef`

| Field | Type | Meaning |
| --- | --- | --- |
| sectorType | Literal['concept'] | Sector classification; this reference always represents a concept. |
| sectorName | str | Concept name from the Tonghuashun concept directory. |
| providerNamespace | Literal['tonghuashun_concept'] | Namespace that identifies the provider's concept-ID scheme. |
| providerSectorId | str | Tonghuashun concept page ID, distinct from its quote ID. |

### `fx.market.industry_comparison(...)`

**What it provides**
Fetch the market industry comparison.

**Data source**
`tencent.finance.qq.industry`

**Example**

<!-- api-example: market.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.industry_comparison(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketIndustryComparisonData` has business fields such as `instrumentId`, `industry`, `instrumentValues`, `industryRanks`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketIndustryComparisonData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| industry | IndustryIdentity | — |
| instrumentValues | IndustryComparisonValues | — |
| industryRanks | IndustryComparisonRanks | — |
| industryAggregate | IndustryAggregate | — |
| marketAggregate | MarketAggregate | — |

Nested business model: `IndustryIdentity`

| Field | Type | Meaning |
| --- | --- | --- |
| providerNamespace | Literal['tencent_hypm'] | — |
| providerIndustryId | str | — |
| name | str | Name. |

Nested business model: `IndustryComparisonValues`

| Field | Type | Meaning |
| --- | --- | --- |
| priceEarnings | Decimal \| None | — |
| earningsPerShare | Decimal \| None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | Tencent zsz converted from 100 million CNY to CNY. |

Nested business model: `IndustryComparisonRanks`

| Field | Type | Meaning |
| --- | --- | --- |
| priceEarningsRank | int \| None | — |
| earningsPerShareRank | int \| None | — |
| marketCapitalizationRank | int \| None | — |

Nested business model: `IndustryAggregate`

| Field | Type | Meaning |
| --- | --- | --- |
| priceEarnings | Decimal \| None | — |
| earningsPerShare | Decimal \| None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | Tencent zsz converted from 100 million CNY to CNY. |
| count | int \| None | — |

Nested business model: `MarketAggregate`

| Field | Type | Meaning |
| --- | --- | --- |
| priceEarnings | Decimal \| None | — |
| earningsPerShare | Decimal \| None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | Tencent zsz converted from 100 million CNY to CNY. |

### `fx.market.instrument_sector_snapshot(...)`

**What it provides**
Fetch sector tags and snapshots for an instrument.

**Data source**
`tencent.finance.qq.sector`

**Example**

<!-- api-example: market.instrument_sector_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.instrument_sector_snapshot(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketInstrumentSectorSnapshotData` has business fields such as `instrumentId`, `sectors`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketInstrumentSectorSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| sectors | list[InstrumentSectorEntry] | — |

Nested business model: `InstrumentSectorEntry`

| Field | Type | Meaning |
| --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | Sector classification used by the ranking. |
| sectorName | str | — |
| providerNamespace | Literal['tencent_plate'] | — |
| providerSectorId | str | — |
| level | int \| None | — |
| tag | str \| None | Sector note supplied by the source. |
| changePct | Decimal \| None | Tencent zdf converted from percentage points to a ratio fraction. |

## 4.4 Individual stock quotes

### `fx.market.equity_intraday(...)`

**What it provides**
Fetch one equity intraday session.

**Data source**
`tencent.finance.qq.intraday`

**Example**

<!-- api-example: market.equity_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `EquityIntradayData` has business fields such as `instrumentId`, `tradeDate`, `time`, `price`. Use the time and price series to chart the stock session. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `EquityIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Source trading-date label; not FinchX capturedAt. |
| time | str | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Volume traded during this minute, in whole shares. |
| amount | Decimal | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Tencent source cumulative traded amount in CNY, unchanged from source. |

### `fx.market.equity_intraday_5d(...)`

**What it provides**
Fetch five-day equity intraday data.

**Data source**
`tencent.finance.qq.intraday`

**Example**

<!-- api-example: market.equity_intraday_5d -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday_5d(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `EquityIntradayData` has business fields such as `instrumentId`, `tradeDate`, `time`, `price`. Use the time and price series to chart the stock session. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `EquityIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Source trading-date label; not FinchX capturedAt. |
| time | str | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Volume traded during this minute, in whole shares. |
| amount | Decimal | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Tencent source cumulative traded amount in CNY, unchanged from source. |

### `fx.market.fund_flow_daily(...)`

**What it provides**
Fetch daily fund-flow data.

**Data source**
`tencent.finance.qq.fund_flow`

**Example**

<!-- api-example: market.fund_flow_daily -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_daily(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketFundFlowDailyData` has business fields such as `instrumentId`, `tradeDate`, `mainNetInflow`, `close`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketFundFlowDailyData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Trading date reported by Tencent, not FinchX capture time. |
| mainNetInflow | Decimal | Monetary amount in CNY. |
| close | Decimal | Daily close in CNY per share. |

### `fx.market.fund_flow_intraday(...)`

**What it provides**
Fetch intraday fund-flow data.

**Data source**
`tencent.finance.qq.fund_flow`

**Example**

<!-- api-example: market.fund_flow_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_intraday(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketFundFlowIntradayData` has business fields such as `instrumentId`, `tradeDate`, `time`, `price`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketFundFlowIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Trading date reported by Tencent, not FinchX capture time. |
| time | str | Source market-local time, HH:MM; values are cumulative from open. |
| price | Decimal | Source price in CNY per share. |
| cumulativeMainNetInflow | Decimal | Monetary amount in CNY. |
| cumulativeRetailNetInflow | Decimal | Monetary amount in CNY. |
| cumulativeSuperLargeNetInflow | Decimal | Monetary amount in CNY. |
| cumulativeLargeNetInflow | Decimal | Monetary amount in CNY. |
| cumulativeMediumNetInflow | Decimal | Monetary amount in CNY. |
| cumulativeSmallNetInflow | Decimal | Monetary amount in CNY. |
| cumulativeMainInflow | Decimal | Monetary amount in CNY. |
| cumulativeMainOutflow | Decimal | Monetary amount in CNY. |

### `fx.market.fund_flow_snapshot(...)`

**What it provides**
Fetch the fund-flow snapshot.

**Data source**
`tencent.finance.qq.fund_flow`

**Example**

<!-- api-example: market.fund_flow_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_snapshot(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketFundFlowSnapshotData` has business fields such as `instrumentId`, `tradeDate`, `mainNetInflow`, `mainInflow`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketFundFlowSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| tradeDate | date | Trading date reported by Tencent, not FinchX capture time. |
| mainNetInflow | Decimal | Monetary amount in CNY. |
| mainInflow | Decimal | Monetary amount in CNY. |
| mainOutflow | Decimal | Monetary amount in CNY. |
| mainInflowRate | Decimal | Ratio fraction; 15% is 0.15. |
| mainOutflowRate | Decimal | Ratio fraction; 19% is 0.19. |
| retailInflow | Decimal | Monetary amount in CNY. |
| retailOutflow | Decimal | Monetary amount in CNY. |
| retailInflowRate | Decimal | Ratio fraction; 35% is 0.35. |
| retailOutflowRate | Decimal | Ratio fraction; 31% is 0.31. |
| superLargeNetInflow | Decimal | Monetary amount in CNY. |
| largeNetInflow | Decimal | Monetary amount in CNY. |
| mediumNetInflow | Decimal | Monetary amount in CNY. |
| smallNetInflow | Decimal | Monetary amount in CNY. |

### `fx.market.ohlcv(...)`

**What it provides**
Fetch OHLCV history for one instrument.

**Data source**
`tencent.finance.qq.klines`, `sohu.finance.klines`

**Example**

<!-- api-example: market.ohlcv -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.ohlcv(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    start_date="2026-09-01",  # Inclusive start date.
    end_date="2026-09-23",  # Inclusive end date.
    adjustment="qfq",  # Forward-adjusted stock prices.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketKlineData` has business fields such as `instrumentId`, `barDate`, `open`, `high`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |
| start_date | date \| str | Required | — | Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| end_date | date \| str | Required | — | Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| adjustment | str \| None | Optional | None | Optional public adjustment: `qfq` means forward-adjusted, `hfq` means backward-adjusted, and Python `None` means unadjusted equities; indexes must use `None`. |

**Output fields**

Data model: `MarketKlineData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| barDate | date | — |
| open | Decimal | Price per share; currency is CNY. |
| high | Decimal | Price per share; currency is CNY. |
| low | Decimal | Price per share; currency is CNY. |
| close | Decimal | Price per share; currency is CNY. |
| volume | int | A non-negative whole number of shares. |
| amount | Decimal \| None | — |
| adjustment | KlineAdjustment | Output adjustment label: `none`, `qfq`, `hfq`, or `not_applicable`. |

### `fx.market.orderbook(...)`

**What it provides**
Fetch the order book.

**Data source**
`tencent.finance.qq.quote`

**Example**

<!-- api-example: market.orderbook -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.orderbook(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketOrderbookData` has business fields such as `instrumentId`, `bids`, `asks`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketOrderbookData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| bids | list[OrderbookLevel] | — |
| asks | list[OrderbookLevel] | — |

Nested business model: `OrderbookLevel`

| Field | Type | Meaning |
| --- | --- | --- |
| level | int | — |
| price | Decimal | Price per share; currency is CNY. |
| size | int | A non-negative whole number of shares. |

### `fx.market.quote(...)`

**What it provides**
Fetch a full-market A-share quote snapshot.

**Data source**
`tencent.finance.qq.market`

**Example**

<!-- api-example: market.quote -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketQuoteData` has business fields such as `instrumentId`, `name`, `price`, `priceChange`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | Optional | InstrumentUniverse.CN_A_SHARE | A-share quote universe; omit it for the full-market snapshot. |

**Output fields**

Data model: `MarketQuoteData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| name | str \| None | Name. |
| price | Decimal | Price per share; currency is CNY. |
| priceChange | Decimal \| None | Signed absolute price change in CNY per share. |
| changeRate | Decimal \| None | — |
| changeRate5d | Decimal \| None | Source-designated 5d price change, stored as a ratio fraction. |
| changeRate10d | Decimal \| None | Source-designated 10d price change, stored as a ratio fraction. |
| changeRate20d | Decimal \| None | Source-designated 20d price change, stored as a ratio fraction. |
| changeRate60d | Decimal \| None | Source-designated 60d price change, stored as a ratio fraction. |
| changeRate52w | Decimal \| None | Price change over the source-designated 52-week period, as a ratio fraction. |
| changeRateYtd | Decimal \| None | Year-to-date price change, stored as a ratio fraction. |
| amplitude | Decimal \| None | Intraday price amplitude, stored as a ratio fraction. |
| volumeRatio | Decimal \| None | Non-negative volume ratio in times; 2.35 represents 2.35x. |
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

**What it provides**
Rank A-share stocks by traded amount, price change, or volume.

**Data source**
`tencent.finance.qq.market`

**Example**

<!-- api-example: market.ranking -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.ranking(
    criterion="amount",  # Rank by traded amount.
    direction="desc",  # Sort from largest to smallest.
    limit=20,  # Return at most 20 rows.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketRankingData` has business fields such as `instrumentId`, `name`, `price`, `priceChange`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| criterion | str | Required | — | Choose `amount` for traded amount (CNY), `zdf` for price change (ratio fraction; e.g. 3% is 0.03), or `volume` for traded volume (shares). |
| direction | str | Required | — | Sort direction: `asc` from lowest to highest or `desc` from highest to lowest. |
| limit | int \| None | Required | — | Required positive integer or None; None means no limit. |

**Output fields**

Data model: `MarketRankingData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| name | str \| None | Name. |
| price | Decimal | Price per share; currency is CNY. |
| priceChange | Decimal \| None | Signed absolute price change in CNY per share. |
| changeRate | Decimal \| None | — |
| changeRate5d | Decimal \| None | Source-designated 5d price change, stored as a ratio fraction. |
| changeRate10d | Decimal \| None | Source-designated 10d price change, stored as a ratio fraction. |
| changeRate20d | Decimal \| None | Source-designated 20d price change, stored as a ratio fraction. |
| changeRate60d | Decimal \| None | Source-designated 60d price change, stored as a ratio fraction. |
| changeRate52w | Decimal \| None | Price change over the source-designated 52-week period, as a ratio fraction. |
| changeRateYtd | Decimal \| None | Year-to-date price change, stored as a ratio fraction. |
| amplitude | Decimal \| None | Intraday price amplitude, stored as a ratio fraction. |
| volumeRatio | Decimal \| None | Non-negative volume ratio in times; 2.35 represents 2.35x. |
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

Nested business model: `ChangePercentRankingMetric`

| Field | Type | Meaning |
| --- | --- | --- |
| criterion | Literal['change_percent'] | — |
| value | Decimal | A ratio fraction, not percentage points: 4.24% is 0.0424. |

Nested business model: `TurnoverRankingMetric`

| Field | Type | Meaning |
| --- | --- | --- |
| criterion | Literal['turnover'] | — |
| value | Decimal | Monetary amount in CNY. |

Nested business model: `VolumeRankingMetric`

| Field | Type | Meaning |
| --- | --- | --- |
| criterion | Literal['volume'] | — |
| value | int | A non-negative whole number of shares. |

### `fx.market.quote_snapshot(...)`

**What it provides**
Fetch one quote snapshot.

**Data source**
`tencent.finance.qq.quote`

**Example**

<!-- api-example: market.quote_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketQuoteSnapshotData` has business fields such as `instrumentId`, `price`, `previousClose`, `open`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketQuoteSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| price | Decimal | Latest price in CNY per share. |
| previousClose | Decimal \| None | — |
| open | Decimal \| None | Session open in CNY per share. |
| high | Decimal \| None | Session high in CNY per share. |
| low | Decimal \| None | Session low in CNY per share. |
| priceChange | Decimal \| None | — |
| changeRate | Decimal \| None | Change from previous close as a ratio fraction; 3% is 0.03. |
| volume | int \| None | Cumulative session volume in shares. |
| amount | Decimal \| None | Cumulative session amount in CNY. |
| sourceTimestamp | datetime | Source-reported quote time, separate from FinchX capturedAt. |

## 4.5 Individual stock information and fundamentals

### `fx.fundamental.company_profile(...)`

**What it provides**
Fetch a company's profile.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: fundamental.company_profile -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.company_profile(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `CompanyProfileData` has business fields such as `symbol`, `companyName`, `businessDescription`, `issuePrice`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `CompanyProfileData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| companyName | str \| None | — |
| businessDescription | str \| None | — |
| issuePrice | Decimal \| None | CNY per share. Tencent gsjj.jg is retained as the source candidate. |
| listingDate | date \| None | — |

### `fx.fundamental.financial_summary(...)`

**What it provides**
Fetch a company's financial summary.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: fundamental.financial_summary -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.financial_summary(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `FinancialSummaryData` has business fields such as `symbol`, `periods`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `FinancialSummaryData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| periods | list[FinancialSummaryPeriod] | — |

Nested business model: `FinancialSummaryPeriod`

| Field | Type | Meaning |
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

**What it provides**
Fetch the fundamental industry comparison.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: fundamental.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.industry_comparison(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `IndustryComparisonData` has business fields such as `symbol`, `industryName`, `metrics`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `IndustryComparisonData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| industryName | str \| None | — |
| metrics | list[IndustryComparisonMetric] | — |

Nested business model: `IndustryComparisonMetric`

| Field | Type | Meaning |
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

**What it provides**
Fetch a company's revenue breakdown.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: fundamental.revenue_breakdown -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.revenue_breakdown(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `RevenueBreakdownData` has business fields such as `symbol`, `breakdowns`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `RevenueBreakdownData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| breakdowns | list[RevenueBreakdownRow] | — |

Nested business model: `RevenueBreakdownRow`

| Field | Type | Meaning |
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

**What it provides**
Fetch financial statements.

**Data source**
`tonghuashun.financial`

**Example**

<!-- api-example: financial.statements -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.financial.statements(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    statement_type="income_statement",  # Income statement.
    period_end="2026-06-30",  # Report period ending on this date.
    max_periods=4,  # Return up to four periods.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `FinancialStatementData` has business fields such as `instrumentId`, `symbol`, `statementType`, `periods`. For calculations use normalized `lineItems[].value`; keep `sourceValue` only to verify the original source text or unit. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |
| statement_type | StatementType | Required | — | balance_sheet, income_statement, or cash_flow_statement. |
| period_end | date \| str \| None | Optional | None | Optional report-period date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| max_periods | int \| None | Optional | None | Optional maximum number of report periods. |

**Output fields**

Data model: `FinancialStatementData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| symbol | str | Six-digit security code. |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | — |
| periods | list[FinancialStatementPeriod] | — |

Nested business model: `FinancialStatementPeriod`

| Field | Type | Meaning |
| --- | --- | --- |
| periodEnd | date | — |
| lineItems | list[FinancialStatementLineItem] | — |

Nested business model: `FinancialStatementLineItem`

| Field | Type | Meaning |
| --- | --- | --- |
| lineItemId | str | — |
| sourceName | str | — |
| sourceUnit | str | — |
| sourceValue | str \| bool \| int \| float \| None | Original source value, retained for auditing and unit/content checks. |
| value | Decimal \| None | Normalized numeric value for calculations; use this instead of parsing the source text. |
| currency | Currency \| None | — |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | — |

### `fx.market.stock_keyword(...)`

**What it provides**
Fetch EastMoney source-ranked hot keywords for an instrument.

**Data source**
`eastmoney.stockrank`

**Example**

<!-- api-example: market.stock_keyword -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.stock_keyword(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketStockKeywordData` has business fields such as `instrumentId`, `keywords`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `MarketStockKeywordData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| keywords | list[StockKeywordEntry] | — |

Nested business model: `StockKeywordEntry`

| Field | Type | Meaning |
| --- | --- | --- |
| keywordName | str | — |
| providerNamespace | Literal['eastmoney_stockrank'] | — |
| providerKeywordId | str | — |
| hitCount | int | — |
| calculatedAt | datetime | — |

### `fx.ownership.capital_snapshot(...)`

**What it provides**
Fetch a capital snapshot.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: ownership.capital_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.capital_snapshot(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `CapitalSnapshotData` has business fields such as `symbol`, `totalShares`, `floatShares`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `CapitalSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| totalShares | int \| None | — |
| floatShares | int \| None | — |

### `fx.ownership.float_holder(...)`

**What it provides**
Fetch floating-holder data.

**Data source**
`tencent.finance.qq.float_holder`

**Example**

<!-- api-example: ownership.float_holder -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.float_holder(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `FloatHolderData` has business fields such as `symbol`, `periods`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `FloatHolderData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| periods | list[FloatHolderPeriod] | — |

Nested business model: `FloatHolderPeriod`

| Field | Type | Meaning |
| --- | --- | --- |
| periodEnd | date | — |
| publishedAt | datetime | — |
| rows | list[FloatHolderRow] | — |

Nested business model: `FloatHolderRow`

| Field | Type | Meaning |
| --- | --- | --- |
| rank | int | Derived from Tencent rows array order. |
| holderId | str \| None | — |
| holderName | str | — |
| shares | int | A non-negative whole number of shares. |
| holderType | str | — |
| floatShareRatio | Decimal \| None | — |
| previousShares | int \| None | — |
| shareChange | int \| None | — |
| isNewTopFloatHolderEntry | bool \| None | Derived from bdms=1 after multi-stock adjacent-period validation. |

### `fx.ownership.holder_summary_snapshot(...)`

**What it provides**
Fetch a holder-summary snapshot.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: ownership.holder_summary_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.holder_summary_snapshot(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `HolderSummarySnapshotData` has business fields such as `symbol`, `shareholderCount`, `averageSharesPerHolder`, `shareholderCountChange`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `HolderSummarySnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| shareholderCount | int \| None | — |
| averageSharesPerHolder | Decimal \| None | Exact share count per holder; Tencent rjcg display units are normalized to shares. |
| shareholderCountChange | Decimal \| None | Tencent gdrshb, normalized from percentage points to a ratio; not an absolute count delta. |
| top10FloatHolderRatio | Decimal \| None | — |
| top10HolderRatio | Decimal \| None | — |

### `fx.company.executive_share_change(...)`

**What it provides**
Fetch executive share changes.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: company.executive_share_change -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_share_change(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `ExecutiveShareChangeData` has business fields such as `symbol`, `changes`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `ExecutiveShareChangeData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| changes | list[ExecutiveShareChange] | — |

Nested business model: `ExecutiveShareChange`

| Field | Type | Meaning |
| --- | --- | --- |
| eventDate | date \| None | — |
| personName | str \| None | — |
| shareChange | int \| None | — |
| averagePrice | Decimal \| None | — |

### `fx.company.executive_snapshot(...)`

**What it provides**
Fetch an executive snapshot.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: company.executive_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_snapshot(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `ExecutiveSnapshotData` has business fields such as `symbol`, `executives`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `ExecutiveSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| executives | list[ExecutiveEntry] | — |

Nested business model: `ExecutiveEntry`

| Field | Type | Meaning |
| --- | --- | --- |
| name | str | Name. |
| roles | list[str] | — |
| shares | int \| None | — |
| compensation | Decimal \| None | — |

### `fx.corporate_action.dividend(...)`

**What it provides**
Fetch dividend actions.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: corporate_action.dividend -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.dividend(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `DividendData` has business fields such as `symbol`, `dividends`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `DividendData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| dividends | list[Dividend] | — |

Nested business model: `Dividend`

| Field | Type | Meaning |
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

**What it provides**
Fetch repurchase actions.

**Data source**
`tencent.finance.qq.f10`

**Example**

<!-- api-example: corporate_action.repurchase -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.repurchase(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `RepurchaseData` has business fields such as `symbol`, `repurchases`. Use the typed fields or exported rows to compare periods, holders, officers, or corporate actions. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |

**Output fields**

Data model: `RepurchaseData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| repurchases | list[Repurchase] | — |

Nested business model: `Repurchase`

| Field | Type | Meaning |
| --- | --- | --- |
| repurchaseDate | date \| None | — |
| quantity | int \| None | — |
| averagePrice | Decimal \| None | — |
| currency | Currency \| None | — |
| fundAmount | Decimal \| None | — |
| market | str \| None | — |

## 4.6 News and disclosures

### `fx.news.search(...)`

**What it provides**
Search news metadata and return document references.

**Data source**
`eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`

**Example**

<!-- api-example: news.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.news.search(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    sort="published_desc",  # Newest items first.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of typed document references. The Dataset row schema `NewsDocumentData` has business fields such as `documentId`, `sourceDocumentId`, `title`, `important`. Use the reference fields to select documents, then pass a reference to the matching detail method. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |
| page | int | Optional | 1 | One-based page number. |
| page_size | int | Optional | 20 | Page size. |
| max_results | int \| None | Optional | None | Optional result cap. |
| since | date \| datetime \| str \| None | Optional | None | Optional inclusive lower time bound. |
| until | date \| datetime \| str \| None | Optional | None | Optional inclusive upper time bound. |
| sort | str | Optional | 'published_desc' | published_desc or published_asc. |

**Output fields**

Data model: `NewsDocumentData`

| Field | Type | Meaning |
| --- | --- | --- |
| documentId | str | — |
| sourceDocumentId | str | — |
| title | str | Content title. |
| important | bool \| None | Normalized source importance marker: True when the source marks the item important; False when it does not; None when unavailable. |
| contentText | str \| None | — |
| summary | str \| None | Topic summary when supplied by the source. |
| publishedAt | datetime \| None | — |
| sourceOccurrences | list[NewsSourceOccurrence] | — |
| url | AnyUrl | Content URL when supplied by the source. |
| originalUrl | AnyUrl \| None | — |
| contentAvailable | bool | — |
| source | str \| None | — |
| relatedInstruments | list[str] | — |

Nested business model: `NewsSourceOccurrence`

| Field | Type | Meaning |
| --- | --- | --- |
| providerId | str | — |
| sourceDocumentId | str | — |
| sourceUrl | AnyUrl \| None | — |
| documentUrl | AnyUrl \| None | — |
| publishedAt | datetime \| None | — |
| capturedAt | datetime | — |

### `fx.articles.get(...)`

**What it provides**
Fetch one ordinary news or community article from its public Tonghuashun URL.

**Data source**
`tonghuashun.articles`

**Example**

<!-- api-example: articles.get -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.articles.get(
    url="https://stock.10jqka.com.cn/20260923/c680236250.shtml",  # Public article or report detail URL.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is one normalized record. The Dataset row schema `ArticleDetailData` has business fields such as `contentId`, `contentType`, `title`, `contentHtml`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| url | str | Required | — | Public Tonghuashun news or community article URL; route and ID are parsed from its allowlisted host and path. |

**Output fields**

Data model: `ArticleDetailData`

| Field | Type | Meaning |
| --- | --- | --- |
| contentId | str | Tonghuashun article identifier from the source URL. |
| contentType | Literal['news', 'zhibo'] | Article category: ordinary news or community zhibo. |
| title | str \| None | Article title. |
| contentHtml | str \| None | Sanitized article-body HTML, excluding comments and disclaimers. |
| contentText | str \| None | Plain-text extraction of the sanitized article body; may be empty when the body contains a sourced image. |
| publishedAt | datetime \| None | Timezone-aware publication time when supplied by the source. |
| sourceName | str \| None | Publisher or media name supplied by the source. |
| author | str \| None | Article author or byline. |
| sourceUrl | AnyUrl \| None | Upstream API or page URL used to retrieve the article. |
| pageUrl | AnyUrl \| None | Canonical public article page URL derived from the input URL. |
| aiSummary | str \| None | Source-provided AI summary, when available. |
| disclaimer | str \| None | Disclaimer text extracted separately from the article body. |
| comments | list[str] | Community comments extracted separately from the article body. |
| relatedStocks | list[ArticleRelatedStock] | Stock associations reported by the article detail source. |
| fetchMethod | Literal['detail_api', 'embedded_state', 'dom', 'zhibo_html'] \| None | Extraction path used for the article body. |
| rawHash | str \| None | SHA-256 of the raw API article body or fetched HTML page. |
| contentAvailable | bool | Whether a usable article title and body were retrieved. |
| errorCode | str \| None | Categorized fetch failure code when content is unavailable. |
| errorMessage | str \| None | Short source or parsing failure reason when content is unavailable. |

Nested business model: `ArticleRelatedStock`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Original source security code, retained verbatim. |
| instrumentId | str \| None | FinchX identity when the security and market can be classified; otherwise null. |
| name | str | Source-provided security name. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |
| sourceMarket | str \| None | Original Tonghuashun stockMarket marker; not a FinchX market enum. |
| sources | list[Literal['hotlist', 'detail']] | Input sources that contributed this association. |

### `fx.articles.from_topic(...)`

**What it provides**
List supported news and long-article refs from a T-code topic's mixed feed; each returned URL is accepted by `articles.get`.

**Data source**
`tonghuashun.topic`

**Example**

<!-- api-example: articles.from_topic -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.articles.from_topic(
    topic_url="https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=T4dryo6",  # Supported Tonghuashun topic URL.
    sort="recommend",  # Use the source recommendation order.
    limit=20,  # Return at most 20 rows.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `TopicArticleData` has business fields such as `topicCode`, `rank`, `contentId`, `contentType`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| topic_url | str | Required | — | Public HTTPS Tonghuashun T-code topic URL. Deep-topic report URLs are recognized and rejected because no report-scoped news feed is available. |
| sort | Literal['recommend'] | Optional | 'recommend' | Only `recommend` is supported: source-ordered recommendations followed by the paginated ordinary feed. |
| limit | int | Optional | 20 | Maximum number of supported news and long-article records after filtering the mixed feed; must be between 1 and 100. |

**Output fields**

Data model: `TopicArticleData`

| Field | Type | Meaning |
| --- | --- | --- |
| topicCode | str | — |
| rank | int | Position in the source-ordered, filtered article list. |
| contentId | str | Numeric Tonghuashun article sequence ID from the topic item. |
| contentType | Literal['news', 'zhibo'] | Verified type=8 news and type=2 long articles use the existing news or zhibo detail route. |
| title | str | Article title supplied by the topic feed. |
| url | str | Public news or zhibo article URL accepted by fx.articles.get(url). |
| publishedAt | datetime | Source article timestamp normalized from epoch milliseconds to Asia/Shanghai. |
| sourceName | str \| None | Publisher or media label supplied by the topic feed item. |

### `fx.disclosure.search(...)`

**What it provides**
Search disclosures and return document references.

**Data source**
`eastmoney.disclosure`

**Example**

<!-- api-example: disclosure.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.disclosure.search(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    categories=None,  # No disclosure category filter.
    sort="published_desc",  # Newest items first.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of typed document references. The Dataset row schema `DisclosureDocumentData` has business fields such as `documentId`, `sourceDocumentId`, `title`, `contentText`. Use the reference fields to select documents, then pass a reference to the matching detail method. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |
| page | int | Optional | 1 | One-based page number. |
| page_size | int | Optional | 20 | Page size. |
| max_results | int \| None | Optional | None | Optional result cap. |
| since | date \| datetime \| str \| None | Optional | None | Optional inclusive lower time bound. |
| until | date \| datetime \| str \| None | Optional | None | Optional inclusive upper time bound. |
| categories | Sequence[str] \| None | Optional | None | Optional disclosure category list. |
| sort | str | Optional | 'published_desc' | published_desc or published_asc. |

**Output fields**

Data model: `DisclosureDocumentData`

| Field | Type | Meaning |
| --- | --- | --- |
| documentId | str | — |
| sourceDocumentId | str | — |
| title | str | Content title. |
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

Nested business model: `DisclosureCategory`

| Field | Type | Meaning |
| --- | --- | --- |
| code | str | — |
| name | str | Name. |
| source | str | — |

Nested business model: `DisclosureAttachment`

| Field | Type | Meaning |
| --- | --- | --- |
| sequence | int \| None | — |
| size | int \| None | — |
| attachmentType | str \| None | — |
| url | AnyUrl | Content URL when supplied by the source. |
| webUrl | AnyUrl \| None | — |

### `fx.news.get_document(ref)`

**What it provides**
Fetch one complete individual-stock news document after a reference is returned by `fx.news.search(...)`.

**Data source**
`eastmoney.news`

**Example**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.news.search(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    sort="published_desc",  # Newest items first.
)

if search_result.data:
    ref = search_result.data[0]
    print(ref.document_url)
    result = fx.news.get_document(
        ref=search_result.data[0],  # Reference returned by the paired search.
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('No documents matched the example search.')
```

**Returned value and recommended use**
Returns one `StandardRecord` in `.data`. Read the document row payload from `result.data.data`, including fields such as `title`, `contentText`, and the document URLs; use `.to_dicts()` for a JSON-compatible row and inspect `.warnings` for fetch issues. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| ref | NewsDocumentRef | Required | — | A reference returned by fx.news.search(...). |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[document record] | Public return type. |
| data | document record | The complete normalized document record. |
| provider_id | str \| None | Provider identity carried by FetchResult. |
| dataset_id | str | Stable dataset identity carried by FetchResult. |
| to_dicts() | list[dict[str, object]] | Standard business-data export; one record is still returned as a one-item list. |

### `fx.news.get_documents(refs)`

**What it provides**
Fetch complete individual-stock news documents for a collection of references.

**Data source**
`eastmoney.news`

**Example**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.news.search(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    sort="published_desc",  # Newest items first.
)

if search_result.data:
    for ref in search_result.data:
        print(ref.document_url)
    result = fx.news.get_documents(
        refs=search_result.data,  # References returned by the paired search.
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('No documents matched the example search.')
```

**Returned value and recommended use**
Returns a tuple of `StandardRecord` values in `.data`, in reference order. Read each record's document fields or export all rows with `.to_dicts()`; inspect `.warnings` for fetch issues. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| refs | Iterable[NewsDocumentRef] | Required | — | References returned by fx.news.search(...). |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[tuple[document record, ...]] | Public return type. |
| data | tuple[document record, ...] | The complete normalized document records in input order. |
| provider_id | str \| None | Provider identity when all records come from one provider. |
| dataset_id | str | Stable dataset identity carried by FetchResult. |
| to_dicts() | list[dict[str, object]] | Standard business-data export for every record. |

### `fx.disclosure.get_document(ref)`

**What it provides**
Fetch one complete individual-stock disclosure after a reference is returned by `fx.disclosure.search(...)`.

**Data source**
`eastmoney.disclosure`

**Example**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.disclosure.search(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    categories=None,  # No disclosure category filter.
    sort="published_desc",  # Newest items first.
)

if search_result.data:
    ref = search_result.data[0]
    print(ref.original_document_url)
    result = fx.disclosure.get_document(
        ref=search_result.data[0],  # Reference returned by the paired search.
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('No documents matched the example search.')
```

**Returned value and recommended use**
Returns one `StandardRecord` in `.data`. Read the document row payload from `result.data.data`, including fields such as `title`, `contentText`, and the document URLs; use `.to_dicts()` for a JSON-compatible row and inspect `.warnings` for fetch issues. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| ref | DisclosureDocumentRef | Required | — | A reference returned by fx.disclosure.search(...). |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[document record] | Public return type. |
| data | document record | The complete normalized document record. |
| provider_id | str \| None | Provider identity carried by FetchResult. |
| dataset_id | str | Stable dataset identity carried by FetchResult. |
| to_dicts() | list[dict[str, object]] | Standard business-data export; one record is still returned as a one-item list. |

### `fx.disclosure.get_documents(refs)`

**What it provides**
Fetch complete individual-stock disclosures for a collection of references.

**Data source**
`eastmoney.disclosure`

**Example**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.disclosure.search(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    categories=None,  # No disclosure category filter.
    sort="published_desc",  # Newest items first.
)

if search_result.data:
    for ref in search_result.data:
        print(ref.original_document_url)
    result = fx.disclosure.get_documents(
        refs=search_result.data,  # References returned by the paired search.
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('No documents matched the example search.')
```

**Returned value and recommended use**
Returns a tuple of `StandardRecord` values in `.data`, in reference order. Read each record's document fields or export all rows with `.to_dicts()`; inspect `.warnings` for fetch issues. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| refs | Iterable[DisclosureDocumentRef] | Required | — | References returned by fx.disclosure.search(...). |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[tuple[document record, ...]] | Public return type. |
| data | tuple[document record, ...] | The complete normalized document records in input order. |
| provider_id | str \| None | Provider identity when all records come from one provider. |
| dataset_id | str | Stable dataset identity carried by FetchResult. |
| to_dicts() | list[dict[str, object]] | Standard business-data export for every record. |

### `fx.market_news.search(...)`

**What it provides**
Search deduplicated all-market news references across the configured market-news providers.

**Data source**
`aigupiao.market_news`, `baidu.finscope.market_news`

**Example**

```python
from finchx import FinchX

fx = FinchX()

result = fx.market_news.search(
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    sort="published_desc",  # Newest items first.
)

print(result.data)
print(result.to_dicts()[:1])
print(result.warnings)
```

**Returned value and recommended use**
Returns typed document references in `.data`. Filter or rank by fields such as `title` and `publishedAt`; use `documentUrl` for a news article body and `originalDocumentUrl` for a disclosure notice or attachment. Pass a chosen reference to the matching detail method. Export with `.to_dicts()` and inspect `.warnings` for a capped scan. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| page | int | Optional | 1 | One-based page number. |
| page_size | int | Optional | 20 | Number of source rows requested per page. |
| max_results | int \| None | Optional | None | Maximum number of deduplicated references. |
| since / until | date \| datetime \| str \| None | Optional | None | Published-time bounds. |
| sort | str | Optional | `published_desc` | Published-time ordering. |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[tuple[NewsDocumentRef, ...]] | Public return type. |
| data | tuple[NewsDocumentRef, ...] | Deduplicated references in the FetchResult. |
| provider | str \| None | Provider identity when all returned references come from one provider; otherwise None. |
| captured_at | datetime | Latest captured_at among returned references, or the current timezone-aware time for an empty result. |
| source_occurrences | tuple | All retained source occurrences for a deduplicated event. |
| provenance | object | Source references and capture metadata for the reference. |

### `fx.market_news.get_document(ref)`

**What it provides**
Fetch one complete all-market news document after a reference is returned by `fx.market_news.search(...)`.

**Data source**
`aigupiao.market_news`, `baidu.finscope.market_news`

**Example**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.market_news.search(
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    sort="published_desc",  # Newest items first.
)

if search_result.data:
    ref = search_result.data[0]
    print(ref.document_url)
    result = fx.market_news.get_document(
        ref=search_result.data[0],  # Reference returned by the paired search.
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('No documents matched the example search.')
```

**Returned value and recommended use**
Returns one `StandardRecord` in `.data`. Read the document row payload from `result.data.data`, including fields such as `title`, `contentText`, and the document URLs; use `.to_dicts()` for a JSON-compatible row and inspect `.warnings` for fetch issues. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| ref | NewsDocumentRef | Required | — | A reference returned by fx.market_news.search(...). |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[document record] | Public return type. |
| data | document record | The complete normalized document record. |
| provider_id | str \| None | Provider identity carried by FetchResult. |
| dataset_id | str | Stable dataset identity carried by FetchResult. |
| to_dicts() | list[dict[str, object]] | Standard business-data export; one record is still returned as a one-item list. |

### `fx.market_news.get_documents(refs)`

**What it provides**
Fetch complete all-market news documents for a collection of references.

**Data source**
`aigupiao.market_news`, `baidu.finscope.market_news`

**Example**

```python
from finchx import FinchX

fx = FinchX()

search_result = fx.market_news.search(
    page=1,  # Start from the first page for a complete date scan.
    page_size=20,  # Rows requested per source page.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
    sort="published_desc",  # Newest items first.
)

if search_result.data:
    for ref in search_result.data:
        print(ref.document_url)
    result = fx.market_news.get_documents(
        refs=search_result.data,  # References returned by the paired search.
    )
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
else:
    print('No documents matched the example search.')
```

**Returned value and recommended use**
Returns a tuple of `StandardRecord` values in `.data`, in reference order. Read each record's document fields or export all rows with `.to_dicts()`; inspect `.warnings` for fetch issues. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| refs | Iterable[NewsDocumentRef] | Required | — | References returned by fx.market_news.search(...). |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[tuple[document record, ...]] | Public return type. |
| data | tuple[document record, ...] | The complete normalized document records in input order. |
| provider_id | str \| None | Provider identity when all records come from one provider. |
| dataset_id | str | Stable dataset identity carried by FetchResult. |
| to_dicts() | list[dict[str, object]] | Standard business-data export for every record. |

### `fx.forum.replies(cookies=..., user_names=[...])`

**What it provides**
Fetch only activity-feed replies with a source locator, separate reply text, and complete nested quoted context. Activities without that context are excluded.

**Data source**
`taoguba.forum`

**Example**

```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"

result = fx.forum.replies(
    cookies=cookies,  # Caller-owned login Cookie; keep it secret.
    user_names=["洛飞超短笔记", "zarili"],  # Exact usernames to retain from the activity feed.
    max_results=50,  # Stop after at most 50 matches.
    since="2026-09-01",  # Inclusive lower publication/reply date.
    until="2026-09-23",  # Inclusive upper publication/reply date.
)

print(result.data)
print(result.to_dicts()[:1])
print(result.warnings)
```

**Returned value and recommended use**
Returns `FetchResult[tuple[ForumReply, ...]]`. Use `replyContent`, `parentContent`, `username`, and `replyTime` to review matched replies; use `replyUrl` to open the source reply. `.to_dicts()` exports the rows, and `.warnings` reports partial scans or other recoverable issues. Retrieval metadata remains on the result, including `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| cookies | str \| Mapping[str, str] | Required | — | Caller-provided Cookie header used only for the fixed activity-feed GET. |
| user_names | Sequence[str] \| None | Optional | None | Exact usernames to retain from the current activity page; it does not search other users. |
| max_results | int \| None | Optional | None | Maximum number of structurally qualified replies. |
| since / until | date \| datetime \| str \| None | Optional | None | Reply-time bounds. |

**Output fields**

| Field | Type | Meaning |
| --- | --- | --- |
| return type | FetchResult[tuple[ForumReply, ...]] | Public return type. |
| data | tuple[ForumReply, ...] | Qualified replies in a FinchX FetchResult. |
| provider | str | Taoguba forum provider identity. |
| dataset_id | str | forum.replies dataset identity at schema 1.0. |
| captured_at | datetime | Latest aware capture time, or the provider clock for an empty result. |
| provenance | tuple[Source, ...] | Direct source records; cookies are never included. |
| to_dicts() | list[dict[str, object]] | CamelCase business fields including replyContent and parentContent. |

## 4.7 After-close review

### `fx.market.daily_replay(...)`

**What it provides**
Fetch one daily replay request with an explicit authenticated session.

**Data source**
`jiuyangongshe.daily_replay`

**Example**

<!-- api-example: market.daily_replay -->
```python
from finchx import FinchX

fx = FinchX()
jygs_session = "<SESSION cookie from your logged-in browser>"

result = fx.market.daily_replay(
    requested_date="2026-09-23",  # Requested replay date.
    session=jygs_session,  # Caller-owned Jiuyangongshe SESSION cookie.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketDailyReplayData` has business fields such as `requestedDate`, `tradeDate`, `themes`. Use `tradeDate` to identify the returned session, then inspect `themes` for the close review. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| requested_date | date \| str | Required | — | Replay date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| session | str | Required | — | Required authenticated SESSION cookie for the Jiuyangongshe Provider; handle it like a password and never log or persist it. |

**Output fields**

Data model: `MarketDailyReplayData`

| Field | Type | Meaning |
| --- | --- | --- |
| requestedDate | date | — |
| tradeDate | date | Trade date. |
| themes | list[ReplayTheme] | — |

Nested business model: `ReplayTheme`

| Field | Type | Meaning |
| --- | --- | --- |
| themeName | str | — |
| reason | str \| None | — |
| stockCount | int | — |
| sourceThemeId | str \| None | — |
| stocks | list[ReplayStock] | — |

Nested business model: `ReplayStock`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| limitUpTime | time \| None | — |
| streakText | str \| None | — |
| price | Decimal \| None | — |
| changeRatio | Decimal \| None | — |
| day | int \| None | — |
| edition | int \| None | — |
| expound | str \| None | — |

### `fx.market.dragon_tiger_detail(...)`

**What it provides**
Fetch Dragon-Tiger detail data.

**Data source**
`aigupiao.dragon_tiger`

**Example**

<!-- api-example: market.dragon_tiger_detail -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.dragon_tiger_detail(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    trade_date="2026-09-23",  # Trading date.
    trade_id="600519-20260923-01",  # Example source trade identifier.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketDragonTigerDetailData` has business fields such as `instrumentId`, `name`, `tradeDate`, `tradeId`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |
| trade_date | date \| str | Required | — | Trading date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| trade_id | str | Required | — | Dragon-Tiger trade identifier. |

**Output fields**

Data model: `MarketDragonTigerDetailData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| tradeDate | date | Trade date. |
| tradeId | str | — |
| closePrice | Decimal | Price per share; currency is CNY. |
| changeRatio | Decimal | A ratio fraction, not percentage points: 4.24% is 0.0424. |
| amount | Decimal | Monetary amount in CNY. |
| totalBuy | Decimal | Monetary amount in CNY. |
| totalSell | Decimal | Monetary amount in CNY. |
| totalNet | Decimal | Monetary amount in CNY. |
| explanation | str | — |
| commentKind | str \| None | — |
| commentObjectId | str \| None | — |
| buySeats | list[DragonTigerSeat] | — |
| sellSeats | list[DragonTigerSeat] | — |

Nested business model: `DragonTigerSeat`

| Field | Type | Meaning |
| --- | --- | --- |
| rank | int | Derived from the source array order. |
| seatName | str | — |
| sourceSeatCode | str \| None | — |
| hasDetails | bool \| None | — |
| buyAmount | Decimal | Monetary amount in CNY. |
| sellAmount | Decimal | Monetary amount in CNY. |
| netAmount | Decimal | Monetary amount in CNY. |

### `fx.market.dragon_tiger_list(...)`

**What it provides**
Fetch Dragon-Tiger list data.

**Data source**
`aigupiao.dragon_tiger`

**Example**

<!-- api-example: market.dragon_tiger_list -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.dragon_tiger_list(
    trade_date="2026-09-23",  # Trading date.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `MarketDragonTigerListData` has business fields such as `instrumentId`, `name`, `tradeDate`, `tradeId`. Use the named business fields for follow-up filtering, comparisons, or charts. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| trade_date | date \| str | Required | — | Trading date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |

**Output fields**

Data model: `MarketDragonTigerListData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| tradeDate | date | Trade date. |
| tradeId | str | — |
| closePrice | Decimal | Price per share; currency is CNY. |
| changeRatio | Decimal | Ratio fraction; 10% is 0.10. |
| amount | Decimal | Monetary amount in CNY. |
| totalBuy | Decimal | Monetary amount in CNY. |
| totalNet | Decimal | Monetary amount in CNY. |
| explanation | str | — |
| threeDayFlag | str \| None | — |
| themeId | int \| None | — |
| themeName | str \| None | — |

## 4.8 Regulatory deviation

### `fx.market.deviation(...)`

**What it provides**
Calculate close-based relative returns for one supported A-share stock against its board benchmark over 10- or 30-session windows.

**Data source**
Computed locally from `market.ohlcv` and `reference.trading_calendar`; no direct Provider.

**Scope and calculation**
This is a deterministic close-based computation, not an exchange announcement, an intraday estimate, a market-wide scan, or an application-specific trigger state.
Supported equities are SSE `60xxxx` and `68xxxx`, and SZSE `00xxxx` and `30xxxx`; BSE equities are not supported. Each board uses its corresponding benchmark:

| Equity code | Board | Benchmark index |
| --- | --- | --- |
| SSE `60xxxx` | SSE main board | SSE A Share Index (`000002`) |
| SSE `68xxxx` | STAR | SSE STAR 50 Index (`000688`) |
| SZSE `00xxxx` | SZSE main board | SZSE A Share Index (`399107`) |
| SZSE `30xxxx` | ChiNext | ChiNext Composite Index (`399102`) |

Stock returns use QFQ equity closes; benchmark returns use unadjusted index points. Trading sessions come from the A-share calendar. For each window, FinchX calculates:

```text
stock_return = current_stock_close / baseline_stock_close - 1
benchmark_return = current_index_close / baseline_index_close - 1
deviation = stock_return - benchmark_return
```

The baseline is the close immediately before the selected window starts. Values are ratio fractions (`0.03` means 3%). `max_deviation_scan` selects the eligible start with the largest stock-minus-benchmark return; `strict_exchange_window` uses the exchange-shaped start. Unsupported codes or insufficient aligned history raise an error instead of returning zero.
The result reports `calculationMode = "official_close"`, `priceBasis = "qfq_stock__raw_index"`, and the frozen rule-set identifier in `ruleVersion`.

| Window | Upper threshold | Lower threshold |
| --- | --- | --- |
| 10 sessions | `+1.00` | `-0.50` |
| 30 sessions | `+2.00` | `-0.70` |

**Example**

<!-- api-example: market.deviation -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.deviation(
    instrument="600519",  # Six-digit A-share code; the endpoint resolves its market.
    windows=(10, 30),  # Compare 10- and 30-session windows.
    as_of="2026-09-23",  # Last completed session to include.
    window_convention="max_deviation_scan",  # Scan the documented deviation convention.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is one `DeviationData` model. The Dataset row schema `DeviationData` has business fields such as `instrumentId`, `board`, `effectiveAsOf`, `calculationMode`. Iterate `windows` to compare each requested trading window, and retain `effectiveAsOf` with the result. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | str | Required | — | Six-digit instrument code; FinchX resolves its market context. |
| windows | Sequence[int] | Optional | (10, 30) | Deviation windows, in trading sessions. |
| as_of | date \| str \| None | Optional | None | Optional completed-session date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| window_convention | DeviationWindowConvention | Optional | DeviationWindowConvention.MAX_DEVIATION_SCAN | Deviation window interpretation. |

**Output fields**

Data model: `DeviationData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| board | str | — |
| effectiveAsOf | date | — |
| calculationMode | Literal['official_close'] | — |
| priceBasis | Literal['qfq_stock__raw_index'] | — |
| ruleVersion | str | — |
| windows | tuple[DeviationWindowData, Ellipsis] | — |

Nested business model: `DeviationWindowData`

| Field | Type | Meaning |
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

## 4.9 Other

### `fx.reference.trading_calendar(...)`

**What it provides**
Return one trading-day flag per natural date in an inclusive A-share range.

**Data source**
`szse.official.calendar`, `pandas_market_calendars`

**Calendar semantics and sources**
Rows are complete, unique, and sorted by date. Dates are calendar labels, not instants; this method only answers whether each date is a trading day. It does not return session hours, breaks, open/close timestamps, or previous/next-session helpers.
The primary source reads each intersecting month from the official SZSE calendar and must explicitly provide every natural date. If transport, parsing, or completeness validation fails, the configured fallback handles the entire requested range; results never mix sources. The optional `calendar` extra enables the offline `pandas_market_calendars` fallback, whose holiday schedule depends on its package version.
Each StandardRecord uses `CN_A:YYYY-MM-DD` for its record and entity identity. Calendar dates have null `eventAt` and `asOf`; `capturedAt` and source metadata describe retrieval.

**Example**

<!-- api-example: reference.trading_calendar -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.reference.trading_calendar(
    start_date="2026-09-01",  # Inclusive start date.
    end_date="2026-09-23",  # Inclusive end date.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `TradingCalendarData` has business fields such as `date`, `isTradingDay`. Each natural date in the inclusive range appears once, and the interface always uses the unified A-share calendar. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| start_date | date \| str | Required | — | Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |
| end_date | date \| str | Required | — | Inclusive date; accepts YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD strings. |

**Output fields**

Data model: `TradingCalendarData`

| Field | Type | Meaning |
| --- | --- | --- |
| date | date | Date. |
| isTradingDay | bool | — |

### `fx.hotlist.convertible_bonds(...)`

**What it provides**
Fetch convertible-bond heat rankings while preserving missing price changes.

**Data source**
`tonghuashun.hotlist`

**Example**

<!-- api-example: hotlist.convertible_bonds -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.convertible_bonds(
    limit=20,  # Return at most 20 rows.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `HotConvertibleBondData` has business fields such as `rank`, `symbol`, `name`, `changePct`. Use the rank and entity fields to inspect or compare the returned leaders. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| limit | int | Optional | 20 | Required positive integer or None; None means no limit. |

**Output fields**

Data model: `HotConvertibleBondData`

| Field | Type | Meaning |
| --- | --- | --- |
| rank | int | Position within this hotlist. |
| symbol | str | Six-digit security code. |
| name | str | Name. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |
| heat | Decimal \| None | Source heat metric; meaningful within its own ranking. |

### `fx.hotlist.etfs(...)`

**What it provides**
Fetch ETF heat rankings sorted by Tonghuashun attention metrics, with available tags.

**Data source**
`tonghuashun.hotlist`

**Example**

<!-- api-example: hotlist.etfs -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.etfs(
    category="cross_border",  # Popularity ranking category.
    limit=20,  # Return at most 20 rows.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `HotEtfData` has business fields such as `rank`, `symbol`, `instrumentId`, `name`. Use the rank and entity fields to inspect or compare the returned leaders. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| category | str | Optional | 'popular' | One of `popular` (popular ETFs), `t0` (T+0 ETFs), `price_limit_20` (20% price-limit ETFs), `cross_border` (cross-border ETFs), or `commodity` (commodity ETFs). |
| limit | int | Optional | 20 | Optional positive integer; the minimum is 1 and the default is 20. |

**Output fields**

Data model: `HotEtfData`

| Field | Type | Meaning |
| --- | --- | --- |
| rank | int | Position within this hotlist. |
| symbol | str | Six-digit security code. |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |
| heat | Decimal | Source heat metric; meaningful within its own ranking. |
| tags | list[str] | Deduplicated ETF tags; empty if tag enrichment is unavailable. |

### `fx.hotlist.content(...)`

**What it provides**
Fetch topic, comment, or article rankings with a distinct data shape for each type.

**Data source**
`tonghuashun.hotlist`

**Example**

<!-- api-example: hotlist.content -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.hotlist.content(
    content_type="topic",  # Topic-content ranking.
    limit=20,  # Return at most 20 rows.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `HotContentData` has business fields such as `root`. Use the rank and entity fields to inspect or compare the returned leaders. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| content_type | str | Optional | 'topic' | One of `topic` (topics), `comment` (popular comments), or `article` (popular articles). |
| limit | int | Optional | 20 | Optional positive integer; the minimum is 1 and the default is 20. |

**Output fields**

Data model: `HotContentData`

| Field | Type | Meaning |
| --- | --- | --- |
| root | HotTopicData \| HotCommentData \| HotArticleData | — |

Nested business model: `HotArticleData`

| Field | Type | Meaning |
| --- | --- | --- |
| contentType | Literal['article'] | Content ranking shape: topic, comment, or article. |
| rank | int | Position within this hotlist. |
| title | str | Content title. |
| heat | Decimal \| None | Source heat metric; meaningful within its own ranking. |
| likeRatio | Decimal \| None | None until the source ratio unit is verified; article records carry a PARTIAL quality issue meanwhile. |
| commentRatio | Decimal \| None | None until the source ratio unit is verified; article records carry a PARTIAL quality issue meanwhile. |
| contentId | str \| None | Source content identifier when available. |
| url | str \| None | Content URL when supplied by the source. |
| relatedStocks | list[HotArticleRelatedStock] | Article associations preserve source codes, names, and stockMarket markers; instrumentId is null if market or security type cannot be represented. |

Nested business model: `HotCommentData`

| Field | Type | Meaning |
| --- | --- | --- |
| contentType | Literal['comment'] | Content ranking shape: topic, comment, or article. |
| rank | int | Position within this hotlist. |
| symbol | str | Six-digit security code. |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |
| heat | Decimal \| None | Source heat metric; meaningful within its own ranking. |
| text | str \| None | Comment text when available. |
| likes | int \| None | Comment likes when reported by the source. |
| contentId | str \| None | Source content identifier when available. |

Nested business model: `HotTopicData`

| Field | Type | Meaning |
| --- | --- | --- |
| contentType | Literal['topic'] | Content ranking shape: topic, comment, or article. |
| rank | int | Position within this hotlist. |
| title | str | Content title. |
| summary | str \| None | Topic summary when supplied by the source. |
| heat | Decimal \| None | Source heat metric; meaningful within its own ranking. |
| url | str \| None | Content URL when supplied by the source. |
| relatedStocks | list[HotRelatedStock] | Related stocks when provided by the source. |

Nested business model: `HotArticleRelatedStock`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Original source instrument code, retained verbatim. |
| instrumentId | str \| None | A classified CN_A equity or ETF identity when the source market and code range are verified; otherwise null. |
| name | str | Name. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |
| sourceMarket | str \| None | Original Tonghuashun stockMarket identifier; not a FinchX market enum. |

Nested business model: `HotRelatedStock`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | Six-digit security code. |
| instrumentId | str | Instrument code. |
| name | str | Name. |
| changePct | Decimal \| None | Price change as a ratio fraction; source percentage points are divided by 100. |

### `fx.iwencai.select(...)`

**What it provides**
Run the final table rendered by ``iwencai.com/screener``.

**Data source**
`iwencai`

**Example**

<!-- api-example: iwencai.select -->
```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"

result = fx.iwencai.select(
    query="成交额排名前500，最新价高于5日均线，非ST",  # Natural-language iWenCai query.
    cookies=cookies,  # Caller-owned login Cookie; keep it secret.
    user_agent="Mozilla/5.0 (compatible; FinchX documentation example)",  # Browser-compatible request header.
    page_size=20,  # Rows requested per source page.
    max_pages=5,  # Bound the number of iWenCai pages.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `IwencaiSelectionData` has business fields such as `instrumentId`, `name`, `price`, `changeRate`. Use the normalized fields and `extraFields` for screening or research follow-up. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| query | str | Required | — | Parameter. |
| cookies | str \| Mapping[str, str] | Required | — | Caller-provided logged-in iWenCai/THS Cookie header. |
| user_agent | str \| None | Optional | None | Optional browser User-Agent for the request. |
| page_size | int | Optional | 100 | Page size. |
| max_pages | int | Optional | 100 | Parameter. |

**Output fields**

Data model: `IwencaiSelectionData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | str | Instrument code. |
| name | str \| None | Name. |
| price | Decimal \| None | — |
| changeRate | Decimal \| None | — |
| amplitude | Decimal \| None | — |
| volume | int \| None | — |
| amount | Decimal \| None | — |
| turnoverRate | Decimal \| None | — |
| extraFields | dict[str, Any] | — |

### `fx.iwencai.search(...)`

**What it provides**
Search reports, announcements, or news with SkillHub OpenAPI.

**Data source**
`iwencai`

**Example**

<!-- api-example: iwencai.search -->
```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"
api_key = "<IWENCAI_API_KEY>"

result = fx.iwencai.search(
    query="人形机器人 行星滚柱丝杠",  # Natural-language iWenCai query.
    channel="report",  # Search reports.
    size=20,  # Number of semantic-search hits.
    cookies=cookies,  # Caller-owned login Cookie; keep it secret.
    api_key=api_key,  # SkillHub API key; load it from a secret store.
    deduplicate=True,  # Remove duplicate search hits.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `IwencaiSearchData` has business fields such as `uid`, `title`, `publishedAt`, `url`. Use the normalized fields and `extraFields` for screening or research follow-up. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| query | str | Required | — | Parameter. |
| channel | str | Optional | 'report' | Parameter. |
| size | int | Optional | 50 | Parameter. |
| cookies | str \| Mapping[str, str] \| None | Optional | None | Caller-provided logged-in iWenCai/THS Cookie header. |
| api_key | str \| None | Optional | None | Parameter. |
| deduplicate | bool | Optional | True | Parameter. |

**Output fields**

Data model: `IwencaiSearchData`

| Field | Type | Meaning |
| --- | --- | --- |
| uid | str \| None | — |
| title | str | Content title. |
| publishedAt | str \| None | — |
| url | str \| None | Report detail page URL, when supplied by the search result. |
| score | float | — |
| extraFields | dict[str, Any] | — |

### `fx.iwencai.report_detail(...)`

**What it provides**
Fetch report text and metadata linked from ``iwencai.search``.

**Data source**
`iwencai`

**Example**

<!-- api-example: iwencai.report_detail -->
```python
from finchx import FinchX

fx = FinchX()
cookies = "<Cookie header from your logged-in browser>"

result = fx.iwencai.report_detail(
    url="https://stock.10jqka.com.cn/20260923/c680236250.shtml",  # Public article or report detail URL.
    cookies=cookies,  # Caller-owned login Cookie; keep it secret.
    uid="example-report-uid",  # Fallback report identifier.
    title="示例研报标题",  # Fallback report title.
    published_at="2026-09-23",  # Fallback publication date.
    user_agent="Mozilla/5.0 (compatible; FinchX documentation example)",  # Browser-compatible request header.
)

print(result.data)  # Native typed data or records.
rows = result.to_dicts()  # JSON-compatible business rows.
print(rows[:1])
print(result.warnings)  # Check for partial or recoverable issues.
```

**Returned value and recommended use**
Returns a `FetchResult`. `.data` is a tuple of normalized records; each record's `.data` contains the Dataset row payload. The Dataset row schema `IwencaiReportDetailData` has business fields such as `documentId`, `sourceDocumentId`, `title`, `contentText`. Use the normalized fields and `extraFields` for screening or research follow-up. Export JSON-compatible rows with `.to_dicts()` and inspect `.warnings` for partial results. `.dataset_id`, `.provider_id`, `.captured_at`, `.provenance`, `.attempts`, `.fallback_used`, and `.cache_hit` carry retrieval and audit details.

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| url | str | Required | — | Report detail page URL from an iWenCai report search hit; it must contain a supported duid. |
| cookies | str \| Mapping[str, str] | Required | — | Caller-provided logged-in iWenCai/THS Cookie header. |
| uid | str \| None | Optional | None | Optional report UID from the search hit, used as a fallback. |
| title | str \| None | Optional | None | Optional report title from the search hit, used as a fallback. |
| published_at | str \| None | Optional | None | Optional publication date from the search hit, used as a fallback. |
| user_agent | str \| None | Optional | None | Optional browser User-Agent for the request. |

**Output fields**

Data model: `IwencaiReportDetailData`

| Field | Type | Meaning |
| --- | --- | --- |
| documentId | str | FinchX-owned report document identifier. |
| sourceDocumentId | str | Source report UID. |
| title | str | Report title. |
| contentText | str | Readable report text returned by the report detail endpoint. |
| publishedAt | datetime \| None | Publication date returned by the report detail endpoint. |
| contentAvailable | bool | Whether readable report text is available. |
| relatedInstruments | list[str] | Related securities when provided by the source. |
| url | AnyUrl | Report detail page URL. |
| originalUrl | AnyUrl \| None | Publisher or source URL when returned by the report detail endpoint. |
| organization | str \| None | Research organization. |
| analyst | str \| None | Report analyst or researcher. |
| fileExtension | str \| None | Source report file extension, when available. |
| sourceCreatedAt | str \| None | Source creation timestamp as returned by the report endpoint. |
| extraFields | dict[str, Any] | Additional report metadata returned by the source. |

## 5. Shared notes

### Security input rules

- Plain codes are resolved using the endpoint context: stock endpoints treat `000001` as a SZSE equity, while index endpoints treat `000001` as the SSE index.
- FinchX validates supported code prefixes and market rules internally; callers provide code strings.

### Date inputs

Public date parameters accept `datetime.date` values or unambiguous strings in `YYYY-MM-DD`, `YYYYMMDD`, and `YYYY/MM/DD` forms. Invalid calendar dates and ambiguous forms such as `09/01/2026` are rejected. Date-only fields do not accept `datetime` values; news, disclosure, all-market news, and forum time bounds also accept timezone-aware `datetime` values.

### Warnings

`result.warnings` contains recoverable quality or compatibility issues, such as a skipped News row with schema drift.

### Date-bounded searches

For `news.search`, `disclosure.search`, `market_news.search`, and `forum.replies`, `since` and `until` are inclusive time filters. Start at `page=1`; the Client scans source pages within a safety bound, stops after reaching an older page for descending results or exhausting the source, and honors `max_results`. If the safety bound is reached before the date boundary or source end, `result.warnings` reports that results may be incomplete. Set a practical `max_results` cap and inspect warnings when completeness matters.

### Document URLs

For news references, `sourceUrl` identifies the source search/list page, while `documentUrl` points to the article body. Use `ref.document_url` when you need the article URL; code that treated `ref.source_url` as the article URL should migrate to `ref.document_url`. For disclosure references, `sourceUrl` is the source query page and `originalDocumentUrl` remains the notice or attachment URL. Disclosure `sourceRecordedAt` is retained under `provenance.adjustments` as EastMoney's internal record time; it is not the notice publication time. Use `publishedAt` for the displayed notice time.

### FetchResult usage

Every method returns `FetchResult`. Record-backed endpoints place tuples of normalized `StandardRecord` values in `.data`; a single document-detail call returns one `StandardRecord`, document searches return typed reference tuples, and computed deviation returns `DeviationData`. `Dataset.data_type` describes the row payload schema, while `FetchResult.data` carries the runtime record or reference shape. Export business dictionaries with `result.to_dicts()` and inspect `result.warnings` for partial results. Retrieval details remain available through `dataset_id`, `provider_id`, `captured_at`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.
