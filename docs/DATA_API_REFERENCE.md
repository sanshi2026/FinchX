# FinchX Data API Reference

English | [简体中文](DATA_API_REFERENCE.zh-CN.md)

This document covers 42 data interfaces + 1 computed capability = 43 public capabilities.

## 1. What FinchX is / Architecture overview

FinchX is a small client for normalized Chinese market data. You call one public Client; FinchX validates the request, fetches a source-backed dataset, and returns one consistent result shape.

| Layer | What it does |
| --- | --- |
| Client | `FinchX()` is the user-facing entry point. |
| Dataset | Defines the stable request and business-data schema. |
| Provider | Implements one real external data source. |
| Collector | Routes the request to a Provider and builds `FetchResult`. |
| FetchResult | Shows business data first; audit fields remain on `provider`, `provenance`, `attempts`, `warnings`, and `cache_hit`. |

Single-equity convenience inputs accept a six-digit code such as `600519`. Use `InstrumentId` when the identity is complex or ambiguous.

## 2. Quick start

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

`print(result)` shows a short business summary. Use `result.to_dicts()` for rows and `result.to_pandas()` for a DataFrame. pandas is optional; without it, `to_pandas()` gives an installation message.

## 3. Interface overview

The index groups all public capabilities by the question they answer.

### Reference & Calendar

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.reference.instrument(...)` | Fetch instrument identity data. | `tencent.finance.qq.market` |
| `fx.reference.trading_calendar(...)` | Return canonical natural-date trading-day flags. | `szse.official.calendar`, `pandas_market_calendars` |

### Market Overview & Pools

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.breadth(...)` | Fetch the current market breadth snapshot. | `eastmoney.push2ex.breadth` |
| `fx.market.broken_limit_pool(...)` | Fetch the latest broken-limit pool snapshot. | `eastmoney.push2ex.broken_limit_pool` |
| `fx.market.consecutive_limit_up(...)` | Fetch the consecutive-limit-up snapshot. | `aigupiao.series_limit_up` |
| `fx.market.daily_replay(...)` | Fetch one daily replay request. | `jiuyangongshe.daily_replay` |
| `fx.market.dragon_tiger_detail(...)` | Fetch Dragon-Tiger detail data. | `aigupiao.dragon_tiger` |
| `fx.market.dragon_tiger_list(...)` | Fetch Dragon-Tiger list data. | `aigupiao.dragon_tiger` |
| `fx.market.limit_down_pool(...)` | Fetch the latest limit-down pool snapshot. | `eastmoney.push2ex.limit_down_pool` |
| `fx.market.limit_up_pool(...)` | Fetch the latest limit-up pool snapshot. | `eastmoney.push2ex.limit_up_pool` |
| `fx.market.quote(...)` | Fetch the selected quote universe. | `tencent.finance.qq.market` |
| `fx.market.ranking(...)` | Fetch the requested market ranking. | `tencent.finance.qq.market` |
| `fx.market.sentiment(...)` | Fetch the market sentiment snapshot. | `aigupiao.market_sentiment` |
| `fx.market.strong_pool(...)` | Fetch the latest strong-pool snapshot. | `eastmoney.push2ex.strong_pool` |
| `fx.market.yesterday_limit_up_pool(...)` | Fetch the latest yesterday-limit-up pool snapshot. | `eastmoney.push2ex.yesterday_limit_up_pool` |

### Single-Security Market Data

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.equity_intraday(...)` | Fetch one equity intraday session. | `tencent.finance.qq.intraday` |
| `fx.market.equity_intraday_5d(...)` | Fetch five-day equity intraday data. | `tencent.finance.qq.intraday` |
| `fx.market.fund_flow_daily(...)` | Fetch daily fund-flow data. | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_intraday(...)` | Fetch intraday fund-flow data. | `tencent.finance.qq.fund_flow` |
| `fx.market.fund_flow_snapshot(...)` | Fetch the fund-flow snapshot. | `tencent.finance.qq.fund_flow` |
| `fx.market.index_intraday(...)` | Fetch one index intraday session. | `tencent.finance.qq.intraday` |
| `fx.market.index_intraday_5d(...)` | Fetch five-day index intraday data. | `tencent.finance.qq.intraday` |
| `fx.market.industry_comparison(...)` | Fetch the market industry comparison. | `tencent.finance.qq.industry` |
| `fx.market.instrument_sector_snapshot(...)` | Fetch sector tags and snapshots for an instrument. | `tencent.finance.qq.sector` |
| `fx.market.stock_keyword(...)` | Fetch EastMoney source-ranked hot keywords for an instrument. | `eastmoney.stockrank` |
| `fx.market.ohlcv(...)` | Fetch OHLCV history for one instrument. | `tencent.finance.qq.klines`, `sohu.finance.klines` |
| `fx.market.orderbook(...)` | Fetch the order book. | `tencent.finance.qq.quote` |
| `fx.market.quote_snapshot(...)` | Fetch one quote snapshot. | `tencent.finance.qq.quote` |

### Fundamentals & Financials

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.fundamental.company_profile(...)` | Fetch a company's profile. | `tencent.finance.qq.f10` |
| `fx.fundamental.financial_summary(...)` | Fetch a company's financial summary. | `tencent.finance.qq.f10` |
| `fx.fundamental.industry_comparison(...)` | Fetch the fundamental industry comparison. | `tencent.finance.qq.f10` |
| `fx.fundamental.revenue_breakdown(...)` | Fetch a company's revenue breakdown. | `tencent.finance.qq.f10` |
| `fx.financial.statements(...)` | Fetch financial statements. | `tonghuashun.financial` |

### News & Disclosures

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.news.search(...)` | Search news metadata and return document references. | `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news` |
| `fx.disclosure.search(...)` | Search disclosures and return document references. | `eastmoney.disclosure` |

### Ownership, Executives & Corporate Actions

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.ownership.capital_snapshot(...)` | Fetch a capital snapshot. | `tencent.finance.qq.f10` |
| `fx.ownership.float_holder(...)` | Fetch floating-holder data. | `tencent.finance.qq.float_holder` |
| `fx.ownership.holder_summary_snapshot(...)` | Fetch a holder-summary snapshot. | `tencent.finance.qq.f10` |
| `fx.company.executive_share_change(...)` | Fetch executive share changes. | `tencent.finance.qq.f10` |
| `fx.company.executive_snapshot(...)` | Fetch an executive snapshot. | `tencent.finance.qq.f10` |
| `fx.corporate_action.dividend(...)` | Fetch dividend actions. | `tencent.finance.qq.f10` |
| `fx.corporate_action.repurchase(...)` | Fetch repurchase actions. | `tencent.finance.qq.f10` |

### Computed Analytics

| Interface | Purpose | Provider |
| --- | --- | --- |
| `fx.market.deviation(...)` | Compute close-based 10-day/30-day deviation from existing data. | — |

## 4. Interface details

## 4.1 Reference & Calendar

### `fx.reference.instrument(...)`

**What it provides**
Fetch instrument identity data.

**Data source**
`tencent.finance.qq.market`

**Call**

```python
fx.reference.instrument(instrument_id: 'InstrumentInput | None' = None, *, request: 'InstrumentRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[InstrumentData]'
```

**Example**

<!-- api-example: reference.instrument -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.reference.instrument("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required without request | None | InstrumentId or a six-digit A-share code. |
| request | InstrumentRequest \| None | Alternative to convenience inputs | None | Typed request model for the full request shape. |

**Output fields**

Data model: `InstrumentData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| name | str | Name. |

### `fx.reference.trading_calendar(...)`

**What it provides**
Return canonical natural-date trading-day flags.

**Data source**
`szse.official.calendar`, `pandas_market_calendars`

**Call**

```python
fx.reference.trading_calendar(start_date: 'date | None' = None, end_date: 'date | None' = None, *, market: 'Market' = <Market.CN_A: 'cn_a'>, request: 'TradingCalendarRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[TradingCalendarData]'
```

**Example**

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

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| start_date | date \| None | Required without request | None | Inclusive start date. |
| end_date | date \| None | Required without request | None | Inclusive end date. |
| market | Market | Optional | Market.CN_A | Market scope; the default is Market.CN_A. |
| request | TradingCalendarRequest \| None | Alternative to convenience inputs | None | Typed request model for the full request shape. |

**Output fields**

Data model: `TradingCalendarData`

| Field | Type | Meaning |
| --- | --- | --- |
| date | date | Date. |
| isTradingDay | bool | — |

## 4.2 Market Overview & Pools

### `fx.market.breadth(...)`

**What it provides**
Fetch the current market breadth snapshot.

**Data source**
`eastmoney.push2ex.breadth`

**Call**

```python
fx.market.breadth(request: 'MarketBreadthRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBreadthData]'
```

**Example**

<!-- api-example: market.breadth -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.breadth()
```

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

### `fx.market.broken_limit_pool(...)`

**What it provides**
Fetch the latest broken-limit pool snapshot.

**Data source**
`eastmoney.push2ex.broken_limit_pool`

**Call**

```python
fx.market.broken_limit_pool(request: 'MarketBrokenLimitPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBrokenLimitPoolData]'
```

**Example**

<!-- api-example: market.broken_limit_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.broken_limit_pool()
```

**Parameters**

None.

**Output fields**

Data model: `MarketBrokenLimitPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.consecutive_limit_up(request: 'MarketConsecutiveLimitUpRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketConsecutiveLimitUpData]'
```

**Example**

<!-- api-example: market.consecutive_limit_up -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.consecutive_limit_up()
```

**Parameters**

None.

**Output fields**

Data model: `MarketConsecutiveLimitUpData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

### `fx.market.daily_replay(...)`

**What it provides**
Fetch one daily replay request.

**Data source**
`jiuyangongshe.daily_replay`

**Call**

```python
fx.market.daily_replay(request: 'MarketDailyReplayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDailyReplayData]'
```

**Example**

<!-- api-example: market.daily_replay -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketDailyReplayRequest

fx = FinchX()
request = MarketDailyReplayRequest(requestedDate=date(2026, 9, 18))
result = fx.market.daily_replay(request)
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketDailyReplayRequest | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketDailyReplayRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| requestedDate (`requested_date`) | date | Required | — | 请求日期。 |

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
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.dragon_tiger_detail(request: 'MarketDragonTigerDetailRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerDetailData]'
```

**Example**

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

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerDetailRequest | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketDragonTigerDetailRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |
| tradeDate (`trade_date`) | date | Required | — | Trade date. |
| tradeId (`trade_id`) | str | Required | — | 龙虎榜交易标识。 |

**Output fields**

Data model: `MarketDragonTigerDetailData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.dragon_tiger_list(request: 'MarketDragonTigerListRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerListData]'
```

**Example**

<!-- api-example: market.dragon_tiger_list -->
```python
from datetime import date
from finchx import FinchX
from finchx.datasets import MarketDragonTigerListRequest

fx = FinchX()
request = MarketDragonTigerListRequest(tradeDate=date(2026, 9, 18))
result = fx.market.dragon_tiger_list(request)
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerListRequest | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketDragonTigerListRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| tradeDate (`trade_date`) | date | Required | — | Trade date. |

**Output fields**

Data model: `MarketDragonTigerListData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

### `fx.market.limit_down_pool(...)`

**What it provides**
Fetch the latest limit-down pool snapshot.

**Data source**
`eastmoney.push2ex.limit_down_pool`

**Call**

```python
fx.market.limit_down_pool(request: 'MarketLimitDownPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitDownPoolData]'
```

**Example**

<!-- api-example: market.limit_down_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_down_pool()
```

**Parameters**

None.

**Output fields**

Data model: `MarketLimitDownPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.limit_up_pool(request: 'MarketLimitUpPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitUpPoolData]'
```

**Example**

<!-- api-example: market.limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.limit_up_pool()
```

**Parameters**

None.

**Output fields**

Data model: `MarketLimitUpPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

### `fx.market.quote(...)`

**What it provides**
Fetch the selected quote universe.

**Data source**
`tencent.finance.qq.market`

**Call**

```python
fx.market.quote(*, universe: 'InstrumentUniverse' = <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'>, request: 'MarketQuoteUniverseRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteData]'
```

**Example**

<!-- api-example: market.quote -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | Optional | InstrumentUniverse.CN_A_SHARE | Selection scope. |
| request | MarketQuoteUniverseRequest \| None | Optional | None | Typed request model for the full request shape. |

**Output fields**

Data model: `MarketQuoteData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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
Fetch the requested market ranking.

**Data source**
`tencent.finance.qq.market`

**Call**

```python
fx.market.ranking(request: 'MarketRankingRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketRankingData]'
```

**Example**

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

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketRankingRequest | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketRankingRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | Required | — | 查询范围。 |
| criterion | RankingCriterion | Required | — | 排行指标。 |
| direction | RankingDirection | Required | — | 排行方向。 |
| limit | int \| None | Required | — | 返回数量上限。 |

**Output fields**

Data model: `MarketRankingData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

### `fx.market.sentiment(...)`

**What it provides**
Fetch the market sentiment snapshot.

**Data source**
`aigupiao.market_sentiment`

**Call**

```python
fx.market.sentiment(request: 'MarketSentimentRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketSentimentData]'
```

**Example**

<!-- api-example: market.sentiment -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.sentiment()
```

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

### `fx.market.strong_pool(...)`

**What it provides**
Fetch the latest strong-pool snapshot.

**Data source**
`eastmoney.push2ex.strong_pool`

**Call**

```python
fx.market.strong_pool(request: 'MarketStrongPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStrongPoolData]'
```

**Example**

<!-- api-example: market.strong_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.strong_pool()
```

**Parameters**

None.

**Output fields**

Data model: `MarketStrongPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.yesterday_limit_up_pool(request: 'MarketYesterdayLimitUpPoolRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketYesterdayLimitUpPoolData]'
```

**Example**

<!-- api-example: market.yesterday_limit_up_pool -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.yesterday_limit_up_pool()
```

**Parameters**

None.

**Output fields**

Data model: `MarketYesterdayLimitUpPoolData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

## 4.3 Single-Security Market Data

### `fx.market.equity_intraday(...)`

**What it provides**
Fetch one equity intraday session.

**Data source**
`tencent.finance.qq.intraday`

**Call**

```python
fx.market.equity_intraday(request: 'EquityIntradayRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

**Example**

<!-- api-example: market.equity_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | EquityIntradayRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `EquityIntradayRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `EquityIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.equity_intraday_5d(request: 'EquityIntraday5dRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

**Example**

<!-- api-example: market.equity_intraday_5d -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday_5d("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | EquityIntraday5dRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `EquityIntraday5dRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `EquityIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.fund_flow_daily(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowDailyData]'
```

**Example**

<!-- api-example: market.fund_flow_daily -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_daily("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketFundFlowRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketFundFlowDailyData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| tradeDate | date | Trading date reported by Tencent, not FinchX capture time. |
| mainNetInflow | Decimal | Monetary amount in CNY. |
| close | Decimal | Daily close in CNY per share. |

### `fx.market.fund_flow_intraday(...)`

**What it provides**
Fetch intraday fund-flow data.

**Data source**
`tencent.finance.qq.fund_flow`

**Call**

```python
fx.market.fund_flow_intraday(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowIntradayData]'
```

**Example**

<!-- api-example: market.fund_flow_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_intraday("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketFundFlowRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketFundFlowIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.fund_flow_snapshot(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowSnapshotData]'
```

**Example**

<!-- api-example: market.fund_flow_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_snapshot("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketFundFlowRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketFundFlowSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

### `fx.market.index_intraday(...)`

**What it provides**
Fetch one index intraday session.

**Data source**
`tencent.finance.qq.intraday`

**Call**

```python
fx.market.index_intraday(request: 'IndexIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

**Example**

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

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | IndexIntradayRequest | Required | — | Typed request model for the full request shape. |

**Request fields** — `IndexIntradayRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `IndexIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.index_intraday_5d(request: 'IndexIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

**Example**

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

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | IndexIntraday5dRequest | Required | — | Typed request model for the full request shape. |

**Request fields** — `IndexIntraday5dRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `IndexIntradayData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| tradeDate | date | Source trading-date label; not FinchX capturedAt. |
| time | str | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Volume traded during this minute, in whole shares. |
| amount | Decimal | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Tencent source cumulative traded amount in CNY, unchanged from source. |

### `fx.market.industry_comparison(...)`

**What it provides**
Fetch the market industry comparison.

**Data source**
`tencent.finance.qq.industry`

**Call**

```python
fx.market.industry_comparison(request: 'MarketIndustryComparisonRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketIndustryComparisonData]'
```

**Example**

<!-- api-example: market.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.industry_comparison("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketIndustryComparisonRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketIndustryComparisonRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketIndustryComparisonData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

**Call**

```python
fx.market.instrument_sector_snapshot(request: 'MarketInstrumentSectorSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketInstrumentSectorSnapshotData]'
```

**Example**

<!-- api-example: market.instrument_sector_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.instrument_sector_snapshot("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketInstrumentSectorSnapshotRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketInstrumentSectorSnapshotRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketInstrumentSectorSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| sectors | list[InstrumentSectorEntry] | — |

Nested business model: `InstrumentSectorEntry`

| Field | Type | Meaning |
| --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | — |
| sectorName | str | — |
| providerNamespace | Literal['tencent_plate'] | — |
| providerSectorId | str | — |
| level | int \| None | — |
| tag | str \| None | — |
| changePct | Decimal \| None | Tencent zdf converted from percentage points to a ratio fraction. |

### `fx.market.stock_keyword(...)`

**What it provides**
Fetch EastMoney source-ranked hot keywords for an instrument.

**Data source**
`eastmoney.stockrank`

**Call**

```python
fx.market.stock_keyword(request: 'MarketStockKeywordRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStockKeywordData]'
```

**Example**

<!-- api-example: market.stock_keyword -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.stock_keyword("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketStockKeywordRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketStockKeywordRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketStockKeywordData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| keywords | list[StockKeywordEntry] | — |

Nested business model: `StockKeywordEntry`

| Field | Type | Meaning |
| --- | --- | --- |
| keywordName | str | — |
| providerNamespace | Literal['eastmoney_stockrank'] | — |
| providerKeywordId | str | — |
| hitCount | int | — |
| calculatedAt | datetime | — |

### `fx.market.ohlcv(...)`

**What it provides**
Fetch OHLCV history for one instrument.

**Data source**
`tencent.finance.qq.klines`, `sohu.finance.klines`

**Call**

```python
fx.market.ohlcv(instrument_id: 'InstrumentInput | None' = None, start_date: 'date | None' = None, end_date: 'date | None' = None, adjustment: 'KlineAdjustment | None' = None, *, request: 'KlinesRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketKlineData]'
```

**Example**

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

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required without request | None | InstrumentId or a six-digit A-share code. |
| start_date | date \| None | Required without request | None | Inclusive start date. |
| end_date | date \| None | Required without request | None | Inclusive end date. |
| adjustment | KlineAdjustment \| None | Required for equities; omit for indexes | None | Kline adjustment mode. |
| request | KlinesRequest \| None | Alternative to convenience inputs | None | Typed request model for the full request shape. |

**Output fields**

Data model: `MarketKlineData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| barDate | date | — |
| open | Decimal | Price per share; currency is CNY. |
| high | Decimal | Price per share; currency is CNY. |
| low | Decimal | Price per share; currency is CNY. |
| close | Decimal | Price per share; currency is CNY. |
| volume | int | A non-negative whole number of shares. |
| amount | Decimal \| None | — |
| adjustment | KlineAdjustment | — |

### `fx.market.orderbook(...)`

**What it provides**
Fetch the order book.

**Data source**
`tencent.finance.qq.quote`

**Call**

```python
fx.market.orderbook(request: 'MarketOrderbookRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketOrderbookData]'
```

**Example**

<!-- api-example: market.orderbook -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.orderbook("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketOrderbookRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketOrderbookRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketOrderbookData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| bids | list[OrderbookLevel] | — |
| asks | list[OrderbookLevel] | — |

Nested business model: `OrderbookLevel`

| Field | Type | Meaning |
| --- | --- | --- |
| level | int | — |
| price | Decimal | Price per share; currency is CNY. |
| size | int | A non-negative whole number of shares. |

### `fx.market.quote_snapshot(...)`

**What it provides**
Fetch one quote snapshot.

**Data source**
`tencent.finance.qq.quote`

**Call**

```python
fx.market.quote_snapshot(request: 'MarketQuoteSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteSnapshotData]'
```

**Example**

<!-- api-example: market.quote_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | MarketQuoteSnapshotRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `MarketQuoteSnapshotRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `MarketQuoteSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

## 4.4 Fundamentals & Financials

### `fx.fundamental.company_profile(...)`

**What it provides**
Fetch a company's profile.

**Data source**
`tencent.finance.qq.f10`

**Call**

```python
fx.fundamental.company_profile(instrument_id: 'InstrumentInput | None' = None, *, request: 'CompanyProfileRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CompanyProfileData]'
```

**Example**

<!-- api-example: fundamental.company_profile -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.company_profile("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required without request | None | InstrumentId or a six-digit A-share code. |
| request | CompanyProfileRequest \| None | Alternative to convenience inputs | None | Typed request model for the full request shape. |

**Output fields**

Data model: `CompanyProfileData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
| companyName | str \| None | — |
| businessDescription | str \| None | — |
| issuePrice | Decimal \| None | CNY per share. Tencent gsjj.jg is retained as the source candidate. |
| listingDate | date \| None | — |

### `fx.fundamental.financial_summary(...)`

**What it provides**
Fetch a company's financial summary.

**Data source**
`tencent.finance.qq.f10`

**Call**

```python
fx.fundamental.financial_summary(request: 'FinancialSummaryRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialSummaryData]'
```

**Example**

<!-- api-example: fundamental.financial_summary -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.financial_summary("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | FinancialSummaryRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `FinancialSummaryRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `FinancialSummaryData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.fundamental.industry_comparison(request: 'FundamentalIndustryComparisonRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndustryComparisonData]'
```

**Example**

<!-- api-example: fundamental.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.industry_comparison("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | FundamentalIndustryComparisonRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `IndustryComparisonRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Naming note**
The signature uses the local alias `FundamentalIndustryComparisonRequest`; the request model is `finchx.datasets.IndustryComparisonRequest`.

**Output fields**

Data model: `IndustryComparisonData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.fundamental.revenue_breakdown(request: 'RevenueBreakdownRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RevenueBreakdownData]'
```

**Example**

<!-- api-example: fundamental.revenue_breakdown -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.revenue_breakdown("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | RevenueBreakdownRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `RevenueBreakdownRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `RevenueBreakdownData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.financial.statements(instrument_id: 'InstrumentInput | None' = None, statement_type: 'StatementType | None' = None, *, period_end: 'date | None' = None, max_periods: 'int | None' = None, request: 'FinancialStatementRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialStatementData]'
```

**Example**

<!-- api-example: financial.statements -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.financial.statements("600519", "income_statement")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required without request | None | InstrumentId or a six-digit A-share code. |
| statement_type | StatementType \| None | Required without request | None | balance_sheet, income_statement, or cash_flow_statement. |
| period_end | date \| None | Optional | None | Optional report-period end date. |
| max_periods | int \| None | Optional | None | Optional maximum number of report periods. |
| request | FinancialStatementRequest \| None | Alternative to convenience inputs | None | Typed request model for the full request shape. |

**Output fields**

Data model: `FinancialStatementData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
| symbol | str | — |
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
| sourceValue | str \| bool \| int \| float \| None | — |
| value | Decimal \| None | — |
| currency | Currency \| None | — |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | — |

## 4.5 News & Disclosures

### `fx.news.search(...)`

**What it provides**
Search news metadata and return document references.

**Data source**
`eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`

**Call**

```python
fx.news.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, sort: 'str' = 'published_desc', request: 'NewsSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[NewsDocumentRef, ...]]'
```

**Example**

<!-- api-example: news.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.news.search("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | Required without request | None | InstrumentId or a six-digit A-share code. |
| page | int | Optional | 1 | One-based page number. |
| page_size | int | Optional | 20 | Page size. |
| max_results | int \| None | Optional | None | Optional result cap. |
| since | date \| datetime \| None | Optional | None | Optional inclusive lower time bound. |
| until | date \| datetime \| None | Optional | None | Optional inclusive upper time bound. |
| sort | str | Optional | 'published_desc' | published_desc or published_asc. |
| request | NewsSearchRequest \| None | Alternative to convenience inputs | None | Typed request model for the full request shape. |

**Output fields**

Data model: `NewsDocumentData`

| Field | Type | Meaning |
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

Nested business model: `NewsSourceOccurrence`

| Field | Type | Meaning |
| --- | --- | --- |
| providerId | str | — |
| sourceDocumentId | str | — |
| sourceUrl | AnyUrl \| None | — |
| documentUrl | AnyUrl \| None | — |
| publishedAt | datetime \| None | — |
| capturedAt | datetime | — |

### `fx.disclosure.search(...)`

**What it provides**
Search disclosures and return document references.

**Data source**
`eastmoney.disclosure`

**Call**

```python
fx.disclosure.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, categories: 'Sequence[str] | None' = None, sort: 'str' = 'published_desc', request: 'DisclosureSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[DisclosureDocumentRef, ...]]'
```

**Example**

<!-- api-example: disclosure.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.disclosure.search("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | Required without request | None | InstrumentId or a six-digit A-share code. |
| page | int | Optional | 1 | One-based page number. |
| page_size | int | Optional | 20 | Page size. |
| max_results | int \| None | Optional | None | Optional result cap. |
| since | date \| datetime \| None | Optional | None | Optional inclusive lower time bound. |
| until | date \| datetime \| None | Optional | None | Optional inclusive upper time bound. |
| categories | Sequence[str] \| None | Optional | None | Optional disclosure category list. |
| sort | str | Optional | 'published_desc' | published_desc or published_asc. |
| request | DisclosureSearchRequest \| None | Alternative to convenience inputs | None | Typed request model for the full request shape. |

**Output fields**

Data model: `DisclosureDocumentData`

| Field | Type | Meaning |
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
| url | AnyUrl | — |
| webUrl | AnyUrl \| None | — |

## 4.6 Ownership, Executives & Corporate Actions

### `fx.ownership.capital_snapshot(...)`

**What it provides**
Fetch a capital snapshot.

**Data source**
`tencent.finance.qq.f10`

**Call**

```python
fx.ownership.capital_snapshot(request: 'CapitalSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CapitalSnapshotData]'
```

**Example**

<!-- api-example: ownership.capital_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.capital_snapshot("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | CapitalSnapshotRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `CapitalSnapshotRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `CapitalSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
| totalShares | int \| None | — |
| floatShares | int \| None | — |

### `fx.ownership.float_holder(...)`

**What it provides**
Fetch floating-holder data.

**Data source**
`tencent.finance.qq.float_holder`

**Call**

```python
fx.ownership.float_holder(request: 'FloatHolderRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FloatHolderData]'
```

**Example**

<!-- api-example: ownership.float_holder -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.float_holder("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | FloatHolderRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `FloatHolderRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |
| asOf (`as_of`) | datetime \| None | Optional | None | — |

**Output fields**

Data model: `FloatHolderData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.ownership.holder_summary_snapshot(request: 'HolderSummarySnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[HolderSummarySnapshotData]'
```

**Example**

<!-- api-example: ownership.holder_summary_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.holder_summary_snapshot("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | HolderSummarySnapshotRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `HolderSummarySnapshotRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `HolderSummarySnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.company.executive_share_change(request: 'ExecutiveShareChangeRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveShareChangeData]'
```

**Example**

<!-- api-example: company.executive_share_change -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_share_change("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | ExecutiveShareChangeRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `ExecutiveShareChangeRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `ExecutiveShareChangeData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.company.executive_snapshot(request: 'ExecutiveSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveSnapshotData]'
```

**Example**

<!-- api-example: company.executive_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_snapshot("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | ExecutiveSnapshotRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `ExecutiveSnapshotRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `ExecutiveSnapshotData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.corporate_action.dividend(request: 'DividendRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DividendData]'
```

**Example**

<!-- api-example: corporate_action.dividend -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.dividend("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | DividendRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `DividendRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `DividendData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

**Call**

```python
fx.corporate_action.repurchase(request: 'RepurchaseRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RepurchaseData]'
```

**Example**

<!-- api-example: corporate_action.repurchase -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.repurchase("600519")
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| request | RepurchaseRequest \| InstrumentInput | Required | — | Typed request model for the full request shape. |

**Request fields** — `RepurchaseRequest`

| Field | Type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrumentId (`instrument_id`) | InstrumentId | Required | — | Instrument identifier. |

**Output fields**

Data model: `RepurchaseData`

| Field | Type | Meaning |
| --- | --- | --- |
| symbol | str | — |
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

## 4.7 Computed Analytics

### `fx.market.deviation(...)`

**What it provides**
Compute close-based 10-day/30-day deviation from existing data.

**Data source**
Computed locally from `market.ohlcv` and `reference.trading_calendar`; no direct Provider.

**Call**

```python
fx.market.deviation(instrument_id: 'InstrumentInput', *, windows: 'Sequence[int]' = (10, 30), as_of: 'date | None' = None, window_convention: 'DeviationWindowConvention' = <DeviationWindowConvention.MAX_DEVIATION_SCAN: 'max_deviation_scan'>, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DeviationData]'
```

**Example**

<!-- api-example: market.deviation -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.deviation("600519", windows=(10, 30))
```

**Parameters**

| Parameter | Type | Required / mode | Default | Meaning |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput | Required | — | InstrumentId or a six-digit A-share code. |
| windows | Sequence[int] | Optional | (10, 30) | Deviation windows, in trading sessions. |
| as_of | date \| None | Optional | None | Optional completed-session date. |
| window_convention | DeviationWindowConvention | Optional | DeviationWindowConvention.MAX_DEVIATION_SCAN | Deviation window interpretation. |

**Output fields**

Data model: `DeviationData`

| Field | Type | Meaning |
| --- | --- | --- |
| instrumentId | InstrumentId | Instrument identifier. |
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

## 5. Shared notes

### Security input rules

- `6xxxxx` is interpreted as an SSE equity.
- `0xxxxx` and `3xxxxx` are interpreted as SZSE equities.
- Bare codes beginning with `4`, `8`, or `9` are not guessed; use an explicit `InstrumentId`.
- Indexes and other ambiguous identities require an explicit `InstrumentId`.

### Common parameters

| Parameter | Meaning |
| --- | --- |
| `provider` | Optional. Pin a Provider explicitly; failures are not silently redirected. |
| `use_cache` | Optional. Controls the configured cache policy; `None` uses the default configuration. |

### Provider and warnings

Pass `provider=` to pin a Provider explicitly. `result.warnings` contains recoverable quality or compatibility issues, such as a skipped News row with schema drift.

### Latest snapshot pools

`limit_up_pool`, `limit_down_pool`, `broken_limit_pool`, `strong_pool`, and `yesterday_limit_up_pool` return the latest snapshot only. They do not support historical date queries.

**Deprecated compatibility:** legacy request models may retain an optional `tradeDate` field; the current Client rejects historical selection. Do not use it in new code.

The documents are generated from the live `CLIENT_ENDPOINTS`, Dataset models, Provider Registry, and computed capability metadata.
