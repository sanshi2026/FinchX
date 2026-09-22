# FinchX Data & API Reference

English | [简体中文](DATA_API_REFERENCE.zh-CN.md)

This reference is generated from the 1.0.0 public Client, Dataset definitions, Pydantic request/data models and Provider Registry. It covers 42 Provider-backed / Dataset-backed public endpoints plus 1 computed capability (43 total capabilities).

## Common rules

Signatures below are taken from the live public Client. Request-field Required / Optional values come from Pydantic `model_fields`; convenience-mode and cross-field rules are documented separately when a signature alone is insufficient. Both language versions use the same structured Example definitions.

| Rule | Meaning |
| --- | --- |
| `provider` | Strict Provider id pin; a failure is not silently redirected. |
| `use_cache` | None follows the configured CachePolicy; FinchX construction does not create storage. |
| Request model | Some methods expose a convenience call and a typed request alternative; valid combinations follow the Client and Pydantic validators. |
| Instrument input | Single-equity endpoints accept an InstrumentId or a verified six-digit A-share code; index and other ambiguous identities still require an explicit InstrumentId. |

## Endpoint index

This index is generated from `CLIENT_ENDPOINTS`, plus the computed `market.deviation` capability.

| Namespace | Method | Dataset | Implemented Providers | Minimum business input |
| --- | --- | --- | --- | --- |
| reference | instrument | instrument | tencent.finance.qq.market | instrument_id (InstrumentId or six-digit equity code) or request |
| reference | trading_calendar | trading_calendar | szse.official.calendar, pandas_market_calendars | start_date and end_date together, or request |
| market | breadth | market.breadth | eastmoney.push2ex.breadth | none |
| market | broken_limit_pool | market.broken_limit_pool | eastmoney.push2ex.broken_limit_pool | request |
| market | consecutive_limit_up | market.consecutive_limit_up_snapshot | aigupiao.series_limit_up | none |
| market | daily_replay | market.daily_replay | jiuyangongshe.daily_replay | request |
| market | dragon_tiger_detail | market.dragon_tiger_detail | aigupiao.dragon_tiger | request (instrumentId, tradeDate, tradeId) |
| market | dragon_tiger_list | market.dragon_tiger_list | aigupiao.dragon_tiger | request |
| market | equity_intraday | market.equity_intraday | tencent.finance.qq.intraday | instrument (InstrumentId or six-digit equity code), or request |
| market | equity_intraday_5d | market.equity_intraday_5d | tencent.finance.qq.intraday | instrument (InstrumentId or six-digit equity code), or request |
| market | fund_flow_daily | market.fund_flow_daily | tencent.finance.qq.fund_flow | instrument (InstrumentId or six-digit equity code), or request |
| market | fund_flow_intraday | market.fund_flow_intraday | tencent.finance.qq.fund_flow | instrument (InstrumentId or six-digit equity code), or request |
| market | fund_flow_snapshot | market.fund_flow_snapshot | tencent.finance.qq.fund_flow | instrument (InstrumentId or six-digit equity code), or request |
| market | index_intraday | market.index_intraday | tencent.finance.qq.intraday | request (index instrumentId) |
| market | index_intraday_5d | market.index_intraday_5d | tencent.finance.qq.intraday | request (index instrumentId) |
| market | industry_comparison | market.industry_comparison | tencent.finance.qq.industry | instrument (InstrumentId or six-digit equity code), or request |
| market | instrument_sector_snapshot | market.instrument_sector_snapshot | tencent.finance.qq.sector | instrument (InstrumentId or six-digit equity code), or request |
| market | stock_keyword | market.stock_keyword | eastmoney.stockrank | instrument (InstrumentId or six-digit equity code), or request |
| market | limit_down_pool | market.limit_down_pool | eastmoney.push2ex.limit_down_pool | request |
| market | limit_up_pool | market.limit_up_pool | eastmoney.push2ex.limit_up_pool | request |
| market | ohlcv | market.klines | tencent.finance.qq.klines, sohu.finance.klines | instrument_id (InstrumentId or six-digit equity code), start_date, end_date, and adjustment for equity |
| market | orderbook | market.orderbook | tencent.finance.qq.quote | instrument (InstrumentId or six-digit equity code), or request |
| market | quote | market.quote | tencent.finance.qq.market | none; the default universe is CN_A_SHARE |
| market | quote_snapshot | market.quote_snapshot | tencent.finance.qq.quote | instrument (InstrumentId or six-digit equity code), or request |
| market | ranking | market.ranking | tencent.finance.qq.market | request (universe, criterion, direction, limit) |
| market | sentiment | market.sentiment_snapshot | aigupiao.market_sentiment | none |
| market | strong_pool | market.strong_pool | eastmoney.push2ex.strong_pool | request |
| market | yesterday_limit_up_pool | market.yesterday_limit_up_pool | eastmoney.push2ex.yesterday_limit_up_pool | request |
| fundamental | company_profile | fundamental.company_profile | tencent.finance.qq.f10 | instrument_id (InstrumentId or six-digit equity code) or request |
| fundamental | financial_summary | fundamental.financial_summary | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| fundamental | industry_comparison | fundamental.industry_comparison | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| fundamental | revenue_breakdown | fundamental.revenue_breakdown | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| financial | statements | financial.statement | tonghuashun.financial | instrument_id (InstrumentId or six-digit equity code) and statement_type, or request |
| news | search | news.document | eastmoney.news, eastmoney.market_news, aigupiao.market_news, baidu.finscope.market_news | instrument (InstrumentId or six-digit equity code), or request |
| disclosure | search | disclosure.document | eastmoney.disclosure | instrument (InstrumentId or six-digit equity code), or request |
| ownership | capital_snapshot | ownership.capital_snapshot | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| ownership | float_holder | ownership.float_holder | tencent.finance.qq.float_holder | instrument (InstrumentId or six-digit equity code), or request |
| ownership | holder_summary_snapshot | ownership.holder_summary_snapshot | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| company | executive_share_change | company.executive_share_change | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| company | executive_snapshot | company.executive_snapshot | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| corporate_action | dividend | corporate_action.dividend | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| corporate_action | repurchase | corporate_action.repurchase | tencent.finance.qq.f10 | instrument (InstrumentId or six-digit equity code), or request |
| market | deviation | market.deviation (computed) | — | instrument_id (InstrumentId or six-digit equity code) |

## Endpoint reference

## `reference`

### `fx.reference.instrument(...)`

Fetch instrument identity data and return it in a FetchResult.

**Dataset:** `instrument`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.market`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.reference.instrument(instrument_id: 'InstrumentInput | None' = None, *, request: 'InstrumentRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[InstrumentData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required in convenience mode | None | Complete InstrumentId. |
| request | InstrumentRequest \| None | Conditional request alternative | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument_id (InstrumentId or six-digit equity code) or request.

#### Request model `InstrumentRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[InstrumentData]`.

#### Returned data model `InstrumentData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: reference.instrument -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.reference.instrument("600519")
```

### `fx.reference.trading_calendar(...)`

Return canonical natural-date trading-day flags.

**Dataset:** `trading_calendar`
**Schema version:** `1.0`
**Implemented Providers:** `szse.official.calendar`, `pandas_market_calendars`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.reference.trading_calendar(start_date: 'date | None' = None, end_date: 'date | None' = None, *, market: 'Market' = <Market.CN_A: 'cn_a'>, request: 'TradingCalendarRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[TradingCalendarData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| start_date | date \| None | Required in convenience mode | None | Inclusive start date. |
| end_date | date \| None | Required in convenience mode | None | Inclusive end date. |
| market | Market | No | Market.CN_A | Market enum; trading_calendar currently supports Market.CN_A only. |
| request | TradingCalendarRequest \| None | Conditional request alternative | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** start_date and end_date together, or request.

#### Request model `TradingCalendarRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| market | Market | Yes | — | Declared by the Pydantic model. |
| startDate | date | Yes | — | Declared by the Pydantic model. |
| endDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[TradingCalendarData]`.

#### Returned data model `TradingCalendarData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| date | date | Yes | — | Declared by the Pydantic model. |
| isTradingDay | bool | Yes | — | Declared by the Pydantic model. |

#### Example

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

Fetch the current market breadth snapshot in a FetchResult.

**Dataset:** `market.breadth`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.breadth`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.breadth(request: 'MarketBreadthRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBreadthData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketBreadthRequest \| None | No | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** none.

#### Request model `MarketBreadthRequest`

No fields; instantiate this model without arguments.

The public return annotation is `FetchResult[MarketBreadthData]`.

#### Returned data model `MarketBreadthData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Trade date reported by EastMoney. |
| advancing | int | Yes | — | Declared by the Pydantic model. |
| declining | int | Yes | — | Declared by the Pydantic model. |
| unchanged | int | Yes | — | Declared by the Pydantic model. |
| total | int | Yes | — | Declared by the Pydantic model. |
| limitUpCount | int | Yes | — | Declared by the Pydantic model. |
| limitDownCount | int | Yes | — | Declared by the Pydantic model. |
| upOver10PercentCount | int | Yes | — | Declared by the Pydantic model. |
| downOver10PercentCount | int | Yes | — | Declared by the Pydantic model. |
| distribution | list[MarketBreadthDistributionEntry] | Yes | — | Declared by the Pydantic model. |

#### Nested model `MarketBreadthDistributionEntry`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| bucket | MarketBreadthBucket | Yes | — | Declared by the Pydantic model. |
| count | int | Yes | — | Number of listed stocks in this return bucket. |

#### Example

<!-- api-example: market.breadth -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.breadth()
```

### `fx.market.broken_limit_pool(...)`

Fetch the broken-limit pool in a FetchResult.

**Dataset:** `market.broken_limit_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.broken_limit_pool`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.broken_limit_pool(request: 'MarketBrokenLimitPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBrokenLimitPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketBrokenLimitPoolRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request.

#### Request model `MarketBrokenLimitPoolRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketBrokenLimitPoolData]`.

#### Returned data model `MarketBrokenLimitPoolData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Latest price in CNY per share. |
| limitUpPrice | Decimal | Yes | — | Current-session limit-up price in CNY per share. |
| changeRate | Decimal | Yes | — | Ratio fraction. |
| amount | Decimal | Yes | — | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| marketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| turnoverRate | Decimal | Yes | — | Ratio fraction. |
| amplitude | Decimal | Yes | — | Current-session amplitude as a ratio fraction. |
| firstLimitUpTime | str \| None | No | None | Declared by the Pydantic model. |
| limitUpBreakCount | int | Yes | — | Declared by the Pydantic model. |
| industry | str | Yes | — | Declared by the Pydantic model. |
| limitUpStats | MarketBrokenLimitPoolStats | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `MarketBrokenLimitPoolStats`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | Declared by the Pydantic model. |
| limitUpCount | int | Yes | — | Declared by the Pydantic model. |

#### Example

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

Fetch the consecutive-limit-up snapshot in a FetchResult.

**Dataset:** `market.consecutive_limit_up_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.series_limit_up`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.consecutive_limit_up(request: 'MarketConsecutiveLimitUpRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketConsecutiveLimitUpData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketConsecutiveLimitUpRequest \| None | No | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** none.

#### Request model `MarketConsecutiveLimitUpRequest`

No fields; instantiate this model without arguments.

The public return annotation is `FetchResult[MarketConsecutiveLimitUpData]`.

#### Returned data model `MarketConsecutiveLimitUpData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| lastPrice | Decimal | Yes | — | Price per share; currency is CNY. |
| change | Decimal | Yes | — | Signed price change in CNY per share. |
| changeRatio | Decimal | Yes | — | Ratio fraction; 10% is 0.10. |
| turnoverRatio | Decimal | Yes | — | Ratio fraction; 12% is 0.12. |
| amount | Decimal | Yes | — | Monetary amount in CNY. |
| limitUpTime | str | Yes | — | Declared by the Pydantic model. |
| state | str | Yes | — | Declared by the Pydantic model. |
| isConsecutiveLimitUp | bool | Yes | — | Declared by the Pydantic model. |
| consecutiveLimitUpCount | int \| None | No | None | Declared by the Pydantic model. |
| previousConsecutiveLimitUpCount | int \| None | No | None | Declared by the Pydantic model. |
| themeId | int \| None | No | None | Declared by the Pydantic model. |
| themeName | str \| None | No | None | Declared by the Pydantic model. |
| floatShares | int | Yes | — | A non-negative whole number of shares. |
| totalShares | int | Yes | — | A non-negative whole number of shares. |
| marketCap | Decimal | Yes | — | Total market capitalization in CNY. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.consecutive_limit_up -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.consecutive_limit_up()
```

### `fx.market.daily_replay(...)`

Fetch one daily replay request in a FetchResult.

**Dataset:** `market.daily_replay`
**Schema version:** `1.0`
**Implemented Providers:** `jiuyangongshe.daily_replay`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.daily_replay(request: 'MarketDailyReplayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDailyReplayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketDailyReplayRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request.

#### Request model `MarketDailyReplayRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| requestedDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketDailyReplayData]`.

#### Returned data model `MarketDailyReplayData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| requestedDate | date | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| themes | list[ReplayTheme] | Yes | — | Declared by the Pydantic model. |

#### Nested model `ReplayTheme`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| themeName | str | Yes | — | Declared by the Pydantic model. |
| reason | str \| None | No | None | Declared by the Pydantic model. |
| stockCount | int | Yes | — | Declared by the Pydantic model. |
| sourceThemeId | str \| None | No | None | Declared by the Pydantic model. |
| stocks | list[ReplayStock] | No | default_factory=list | Declared by the Pydantic model. |

#### Nested model `ReplayStock`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| limitUpTime | time \| None | No | None | Declared by the Pydantic model. |
| streakText | str \| None | No | None | Declared by the Pydantic model. |
| price | Decimal \| None | No | None | Declared by the Pydantic model. |
| changeRatio | Decimal \| None | No | None | Declared by the Pydantic model. |
| day | int \| None | No | None | Declared by the Pydantic model. |
| edition | int \| None | No | None | Declared by the Pydantic model. |
| expound | str \| None | No | None | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

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

Fetch Dragon-Tiger detail data in a FetchResult.

**Dataset:** `market.dragon_tiger_detail`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.dragon_tiger`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.dragon_tiger_detail(request: 'MarketDragonTigerDetailRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerDetailData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerDetailRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request (instrumentId, tradeDate, tradeId).

#### Request model `MarketDragonTigerDetailRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| tradeId | str | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketDragonTigerDetailData]`.

#### Returned data model `MarketDragonTigerDetailData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| tradeId | str | Yes | — | Declared by the Pydantic model. |
| closePrice | Decimal | Yes | — | Price per share; currency is CNY. |
| changeRatio | Decimal | Yes | — | A ratio fraction, not percentage points: 4.24% is 0.0424. |
| amount | Decimal | Yes | — | Monetary amount in CNY. |
| totalBuy | Decimal | Yes | — | Monetary amount in CNY. |
| totalSell | Decimal | Yes | — | Monetary amount in CNY. |
| totalNet | Decimal | Yes | — | Monetary amount in CNY. |
| explanation | str | Yes | — | Declared by the Pydantic model. |
| commentKind | str \| None | No | None | Declared by the Pydantic model. |
| commentObjectId | str \| None | No | None | Declared by the Pydantic model. |
| buySeats | list[DragonTigerSeat] | Yes | — | Declared by the Pydantic model. |
| sellSeats | list[DragonTigerSeat] | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `DragonTigerSeat`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| rank | int | Yes | — | Derived from the source array order. |
| seatName | str | Yes | — | Declared by the Pydantic model. |
| sourceSeatCode | str \| None | No | None | Declared by the Pydantic model. |
| hasDetails | bool \| None | No | None | Declared by the Pydantic model. |
| buyAmount | Decimal | Yes | — | Monetary amount in CNY. |
| sellAmount | Decimal | Yes | — | Monetary amount in CNY. |
| netAmount | Decimal | Yes | — | Monetary amount in CNY. |

#### Example

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

Fetch Dragon-Tiger list data in a FetchResult.

**Dataset:** `market.dragon_tiger_list`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.dragon_tiger`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.dragon_tiger_list(request: 'MarketDragonTigerListRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerListData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerListRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request.

#### Request model `MarketDragonTigerListRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketDragonTigerListData]`.

#### Returned data model `MarketDragonTigerListData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| tradeId | str | Yes | — | Declared by the Pydantic model. |
| closePrice | Decimal | Yes | — | Price per share; currency is CNY. |
| changeRatio | Decimal | Yes | — | Ratio fraction; 10% is 0.10. |
| amount | Decimal | Yes | — | Monetary amount in CNY. |
| totalBuy | Decimal | Yes | — | Monetary amount in CNY. |
| totalNet | Decimal | Yes | — | Monetary amount in CNY. |
| explanation | str | Yes | — | Declared by the Pydantic model. |
| threeDayFlag | str \| None | No | None | Declared by the Pydantic model. |
| themeId | int \| None | No | None | Declared by the Pydantic model. |
| themeName | str \| None | No | None | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

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

Fetch one equity intraday session in a FetchResult.

**Dataset:** `market.equity_intraday`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.equity_intraday(request: 'EquityIntradayRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | EquityIntradayRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `EquityIntradayRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[EquityIntradayData]`.

#### Returned data model `EquityIntradayData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Source trading-date label; not FinchX capturedAt. |
| time | str | Yes | — | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Yes | — | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Yes | — | Volume traded during this minute, in whole shares. |
| amount | Decimal | Yes | — | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Yes | — | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Yes | — | Tencent source cumulative traded amount in CNY, unchanged from source. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.equity_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday("600519")
```

### `fx.market.equity_intraday_5d(...)`

Fetch five-day equity intraday data in a FetchResult.

**Dataset:** `market.equity_intraday_5d`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.equity_intraday_5d(request: 'EquityIntraday5dRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | EquityIntraday5dRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `EquityIntraday5dRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[EquityIntradayData]`.

#### Returned data model `EquityIntradayData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Source trading-date label; not FinchX capturedAt. |
| time | str | Yes | — | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Yes | — | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Yes | — | Volume traded during this minute, in whole shares. |
| amount | Decimal | Yes | — | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Yes | — | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Yes | — | Tencent source cumulative traded amount in CNY, unchanged from source. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.equity_intraday_5d -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.equity_intraday_5d("600519")
```

### `fx.market.fund_flow_daily(...)`

Fetch daily fund-flow data in a FetchResult.

**Dataset:** `market.fund_flow_daily`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.fund_flow`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.fund_flow_daily(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowDailyData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketFundFlowRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketFundFlowDailyData]`.

#### Returned data model `MarketFundFlowDailyData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Trading date reported by Tencent, not FinchX capture time. |
| mainNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| close | Decimal | Yes | — | Daily close in CNY per share. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.fund_flow_daily -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_daily("600519")
```

### `fx.market.fund_flow_intraday(...)`

Fetch intraday fund-flow data in a FetchResult.

**Dataset:** `market.fund_flow_intraday`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.fund_flow`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.fund_flow_intraday(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketFundFlowRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketFundFlowIntradayData]`.

#### Returned data model `MarketFundFlowIntradayData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Trading date reported by Tencent, not FinchX capture time. |
| time | str | Yes | — | Source market-local time, HH:MM; values are cumulative from open. |
| price | Decimal | Yes | — | Source price in CNY per share. |
| cumulativeMainNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| cumulativeRetailNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| cumulativeSuperLargeNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| cumulativeLargeNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| cumulativeMediumNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| cumulativeSmallNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| cumulativeMainInflow | Decimal | Yes | — | Monetary amount in CNY. |
| cumulativeMainOutflow | Decimal | Yes | — | Monetary amount in CNY. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.fund_flow_intraday -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_intraday("600519")
```

### `fx.market.fund_flow_snapshot(...)`

Fetch the fund-flow snapshot in a FetchResult.

**Dataset:** `market.fund_flow_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.fund_flow`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.fund_flow_snapshot(request: 'MarketFundFlowRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketFundFlowRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketFundFlowSnapshotData]`.

#### Returned data model `MarketFundFlowSnapshotData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Trading date reported by Tencent, not FinchX capture time. |
| mainNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| mainInflow | Decimal | Yes | — | Monetary amount in CNY. |
| mainOutflow | Decimal | Yes | — | Monetary amount in CNY. |
| mainInflowRate | Decimal | Yes | — | Ratio fraction; 15% is 0.15. |
| mainOutflowRate | Decimal | Yes | — | Ratio fraction; 19% is 0.19. |
| retailInflow | Decimal | Yes | — | Monetary amount in CNY. |
| retailOutflow | Decimal | Yes | — | Monetary amount in CNY. |
| retailInflowRate | Decimal | Yes | — | Ratio fraction; 35% is 0.35. |
| retailOutflowRate | Decimal | Yes | — | Ratio fraction; 31% is 0.31. |
| superLargeNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| largeNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| mediumNetInflow | Decimal | Yes | — | Monetary amount in CNY. |
| smallNetInflow | Decimal | Yes | — | Monetary amount in CNY. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.fund_flow_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.fund_flow_snapshot("600519")
```

### `fx.market.index_intraday(...)`

Fetch one index intraday session in a FetchResult.

**Dataset:** `market.index_intraday`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.index_intraday(request: 'IndexIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | IndexIntradayRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request (index instrumentId).

#### Request model `IndexIntradayRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[IndexIntradayData]`.

#### Returned data model `IndexIntradayData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Source trading-date label; not FinchX capturedAt. |
| time | str | Yes | — | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Yes | — | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Yes | — | Volume traded during this minute, in whole shares. |
| amount | Decimal | Yes | — | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Yes | — | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Yes | — | Tencent source cumulative traded amount in CNY, unchanged from source. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

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

Fetch five-day index intraday data in a FetchResult.

**Dataset:** `market.index_intraday_5d`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.index_intraday_5d(request: 'IndexIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | IndexIntraday5dRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request (index instrumentId).

#### Request model `IndexIntraday5dRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[IndexIntradayData]`.

#### Returned data model `IndexIntradayData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Source trading-date label; not FinchX capturedAt. |
| time | str | Yes | — | Source trading time in HHMM normalized to HH:MM; not capturedAt. |
| price | Decimal | Yes | — | Exact decimal in the source price unit (CNY per share for equities; index points for indices). |
| volume | int | Yes | — | Volume traded during this minute, in whole shares. |
| amount | Decimal | Yes | — | Amount traded during this minute, in CNY. |
| cumulativeVolume | int | Yes | — | Tencent source cumulative traded volume, normalized to whole shares from lots (source lots multiplied by 100). |
| cumulativeAmount | Decimal | Yes | — | Tencent source cumulative traded amount in CNY, unchanged from source. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

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

Fetch the market industry comparison in a FetchResult.

**Dataset:** `market.industry_comparison`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.industry`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.industry_comparison(request: 'MarketIndustryComparisonRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketIndustryComparisonData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketIndustryComparisonRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketIndustryComparisonRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketIndustryComparisonData]`.

#### Returned data model `MarketIndustryComparisonData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| industry | IndustryIdentity | Yes | — | Declared by the Pydantic model. |
| instrumentValues | IndustryComparisonValues | Yes | — | Declared by the Pydantic model. |
| industryRanks | IndustryComparisonRanks | Yes | — | Declared by the Pydantic model. |
| industryAggregate | IndustryAggregate | Yes | — | Declared by the Pydantic model. |
| marketAggregate | MarketAggregate | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `IndustryIdentity`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| providerNamespace | Literal['tencent_hypm'] | Yes | — | Declared by the Pydantic model. |
| providerIndustryId | str | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |

#### Nested model `IndustryComparisonValues`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | Declared by the Pydantic model. |
| earningsPerShare | Decimal \| None | No | None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | No | None | Tencent zsz converted from 100 million CNY to CNY. |

#### Nested model `IndustryComparisonRanks`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarningsRank | int \| None | No | None | Declared by the Pydantic model. |
| earningsPerShareRank | int \| None | No | None | Declared by the Pydantic model. |
| marketCapitalizationRank | int \| None | No | None | Declared by the Pydantic model. |

#### Nested model `IndustryAggregate`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | Declared by the Pydantic model. |
| earningsPerShare | Decimal \| None | No | None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | No | None | Tencent zsz converted from 100 million CNY to CNY. |
| count | int \| None | No | None | Declared by the Pydantic model. |

#### Nested model `MarketAggregate`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | Declared by the Pydantic model. |
| earningsPerShare | Decimal \| None | No | None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | No | None | Tencent zsz converted from 100 million CNY to CNY. |

#### Example

<!-- api-example: market.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.industry_comparison("600519")
```

### `fx.market.instrument_sector_snapshot(...)`

Fetch sector tags and snapshots for an instrument in a FetchResult.

**Dataset:** `market.instrument_sector_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.sector`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.instrument_sector_snapshot(request: 'MarketInstrumentSectorSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketInstrumentSectorSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketInstrumentSectorSnapshotRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketInstrumentSectorSnapshotRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketInstrumentSectorSnapshotData]`.

#### Returned data model `MarketInstrumentSectorSnapshotData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| sectors | list[InstrumentSectorEntry] | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `InstrumentSectorEntry`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | Yes | — | Declared by the Pydantic model. |
| sectorName | str | Yes | — | Declared by the Pydantic model. |
| providerNamespace | Literal['tencent_plate'] | Yes | — | Declared by the Pydantic model. |
| providerSectorId | str | Yes | — | Declared by the Pydantic model. |
| level | int \| None | No | None | Declared by the Pydantic model. |
| tag | str \| None | No | None | Declared by the Pydantic model. |
| changePct | Decimal \| None | No | None | Tencent zdf converted from percentage points to a ratio fraction. |

#### Example

<!-- api-example: market.instrument_sector_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.instrument_sector_snapshot("600519")
```

### `fx.market.stock_keyword(...)`

Fetch EastMoney source-ranked hot keywords for an instrument.

**Dataset:** `market.stock_keyword`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.stockrank`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.stock_keyword(request: 'MarketStockKeywordRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStockKeywordData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketStockKeywordRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketStockKeywordRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketStockKeywordData]`.

#### Returned data model `MarketStockKeywordData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| keywords | list[StockKeywordEntry] | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `StockKeywordEntry`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| keywordName | str | Yes | — | Declared by the Pydantic model. |
| providerNamespace | Literal['eastmoney_stockrank'] | Yes | — | Declared by the Pydantic model. |
| providerKeywordId | str | Yes | — | Declared by the Pydantic model. |
| hitCount | int | Yes | — | Declared by the Pydantic model. |
| calculatedAt | datetime | Yes | — | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.stock_keyword -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.stock_keyword("600519")
```

### `fx.market.limit_down_pool(...)`

Fetch the limit-down pool in a FetchResult.

**Dataset:** `market.limit_down_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.limit_down_pool`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.limit_down_pool(request: 'MarketLimitDownPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitDownPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketLimitDownPoolRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request.

#### Request model `MarketLimitDownPoolRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketLimitDownPoolData]`.

#### Returned data model `MarketLimitDownPoolData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Latest price in CNY per share. |
| changeRate | Decimal | Yes | — | Ratio fraction; -10% is -0.10. |
| amount | Decimal | Yes | — | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| marketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| priceEarningsRatio | Decimal \| None | No | None | EastMoney-reported dynamic P/E; source calculation details are unspecified. |
| turnoverRate | Decimal | Yes | — | Ratio fraction. |
| limitDownQueueAmount | Decimal \| None | No | None | EastMoney-reported limit-down queued amount in CNY. |
| lastLimitDownTime | str \| None | No | None | Declared by the Pydantic model. |
| boardTradedAmount | Decimal \| None | No | None | Amount traded at the limit-down price in CNY. |
| consecutiveLimitDownDays | int | Yes | — | Declared by the Pydantic model. |
| limitDownOpenCount | int | Yes | — | Declared by the Pydantic model. |
| industry | str | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

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

Fetch the limit-up pool in a FetchResult.

**Dataset:** `market.limit_up_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.limit_up_pool`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.limit_up_pool(request: 'MarketLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitUpPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketLimitUpPoolRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request.

#### Request model `MarketLimitUpPoolRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketLimitUpPoolData]`.

#### Returned data model `MarketLimitUpPoolData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Latest price in CNY per share. |
| changeRate | Decimal | Yes | — | Ratio fraction; 10% is 0.10. |
| amount | Decimal | Yes | — | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| marketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| turnoverRate | Decimal | Yes | — | Ratio fraction; 5% is 0.05. |
| consecutiveLimitUpDays | int | Yes | — | Declared by the Pydantic model. |
| firstLimitUpTime | str \| None | No | None | Declared by the Pydantic model. |
| lastLimitUpTime | str \| None | No | None | Declared by the Pydantic model. |
| limitUpQueueAmount | Decimal \| None | No | None | Declared by the Pydantic model. |
| limitUpBreakCount | int | Yes | — | Declared by the Pydantic model. |
| industry | str | Yes | — | Declared by the Pydantic model. |
| limitUpStats | MarketLimitUpStats | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `MarketLimitUpStats`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | Declared by the Pydantic model. |
| limitUpCount | int | Yes | — | Declared by the Pydantic model. |

#### Example

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

Fetch OHLCV history for one instrument in a FetchResult.

**Dataset:** `market.klines`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.klines`, `sohu.finance.klines`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.ohlcv(instrument_id: 'InstrumentInput | None' = None, start_date: 'date | None' = None, end_date: 'date | None' = None, adjustment: 'KlineAdjustment | None' = None, *, request: 'KlinesRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketKlineData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required in convenience mode | None | Complete InstrumentId. |
| start_date | date \| None | Required in convenience mode | None | Inclusive start date. |
| end_date | date \| None | Required in convenience mode | None | Inclusive end date. |
| adjustment | KlineAdjustment \| None | Required for equities; omit for indexes | None | Kline adjustment; required for equity calls and omitted for index calls. |
| request | KlinesRequest \| None | Conditional request alternative | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument_id (InstrumentId or six-digit equity code), start_date, end_date, and adjustment for equity.

#### Request model `KlinesRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| startDate | date | Yes | — | Declared by the Pydantic model. |
| endDate | date | Yes | — | Declared by the Pydantic model. |
| adjustment | KlineAdjustment \| None | No | None | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketKlineData]`.

#### Returned data model `MarketKlineData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| barDate | date | Yes | — | Declared by the Pydantic model. |
| open | Decimal | Yes | — | Price per share; currency is CNY. |
| high | Decimal | Yes | — | Price per share; currency is CNY. |
| low | Decimal | Yes | — | Price per share; currency is CNY. |
| close | Decimal | Yes | — | Price per share; currency is CNY. |
| volume | int | Yes | — | A non-negative whole number of shares. |
| amount | Decimal \| None | No | None | Declared by the Pydantic model. |
| adjustment | KlineAdjustment | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

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

### `fx.market.orderbook(...)`

Fetch the order book in a FetchResult.

**Dataset:** `market.orderbook`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.quote`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.orderbook(request: 'MarketOrderbookRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketOrderbookData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketOrderbookRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketOrderbookRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketOrderbookData]`.

#### Returned data model `MarketOrderbookData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| bids | list[OrderbookLevel] | Yes | — | Declared by the Pydantic model. |
| asks | list[OrderbookLevel] | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `OrderbookLevel`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| level | int | Yes | — | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Price per share; currency is CNY. |
| size | int | Yes | — | A non-negative whole number of shares. |

#### Example

<!-- api-example: market.orderbook -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.orderbook("600519")
```

### `fx.market.quote(...)`

Fetch the selected quote universe in a FetchResult.

**Dataset:** `market.quote`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.market`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.quote(*, universe: 'InstrumentUniverse' = <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'>, request: 'MarketQuoteUniverseRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | No | InstrumentUniverse.CN_A_SHARE | Selection scope. |
| request | MarketQuoteUniverseRequest \| None | No | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** none; the default universe is CN_A_SHARE.

#### Request model `MarketQuoteUniverseRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketQuoteData]`.

#### Returned data model `MarketQuoteData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| name | str \| None | No | None | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Price per share; currency is CNY. |
| priceChange | Decimal \| None | No | None | Signed absolute price change in CNY per share. |
| changeRate | Decimal \| None | No | None | Declared by the Pydantic model. |
| changeRate5d | Decimal \| None | No | None | Source-designated 5d price change, stored as a ratio fraction. |
| changeRate10d | Decimal \| None | No | None | Source-designated 10d price change, stored as a ratio fraction. |
| changeRate20d | Decimal \| None | No | None | Source-designated 20d price change, stored as a ratio fraction. |
| changeRate60d | Decimal \| None | No | None | Source-designated 60d price change, stored as a ratio fraction. |
| changeRate52w | Decimal \| None | No | None | Price change over the source-designated 52-week period, as a ratio fraction. |
| changeRateYtd | Decimal \| None | No | None | Year-to-date price change, stored as a ratio fraction. |
| amplitude | Decimal \| None | No | None | Intraday price amplitude, stored as a ratio fraction. |
| volumeRatio | Decimal \| None | No | None | Non-negative volume ratio in times; 2.35 represents 2.35x. |
| volume | int \| None | No | None | Declared by the Pydantic model. |
| amount | Decimal \| None | No | None | Declared by the Pydantic model. |
| turnoverRate | Decimal \| None | No | None | Declared by the Pydantic model. |
| marketCap | Decimal \| None | No | None | Declared by the Pydantic model. |
| floatMarketCap | Decimal \| None | No | None | Declared by the Pydantic model. |
| peTtm | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainNetInflow | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainInflow | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainOutflow | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainInflow5d | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainOutflow5d | Decimal \| None | No | None | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.quote -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()
```

### `fx.market.quote_snapshot(...)`

Fetch one quote snapshot in a FetchResult.

**Dataset:** `market.quote_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.quote`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.quote_snapshot(request: 'MarketQuoteSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketQuoteSnapshotRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `MarketQuoteSnapshotRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketQuoteSnapshotData]`.

#### Returned data model `MarketQuoteSnapshotData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Latest price in CNY per share. |
| previousClose | Decimal \| None | No | None | Declared by the Pydantic model. |
| open | Decimal \| None | No | None | Session open in CNY per share. |
| high | Decimal \| None | No | None | Session high in CNY per share. |
| low | Decimal \| None | No | None | Session low in CNY per share. |
| priceChange | Decimal \| None | No | None | Declared by the Pydantic model. |
| changeRate | Decimal \| None | No | None | Change from previous close as a ratio fraction; 3% is 0.03. |
| volume | int \| None | No | None | Cumulative session volume in shares. |
| amount | Decimal \| None | No | None | Cumulative session amount in CNY. |
| sourceTimestamp | datetime | Yes | — | Source-reported quote time, separate from FinchX capturedAt. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.quote_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot("600519")
```

### `fx.market.ranking(...)`

Fetch the requested market ranking in a FetchResult.

**Dataset:** `market.ranking`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.market`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.market.ranking(request: 'MarketRankingRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketRankingData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketRankingRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request (universe, criterion, direction, limit).

#### Request model `MarketRankingRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | Yes | — | Declared by the Pydantic model. |
| criterion | RankingCriterion | Yes | — | Declared by the Pydantic model. |
| direction | RankingDirection | Yes | — | Declared by the Pydantic model. |
| limit | int \| None | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketRankingData]`.

#### Returned data model `MarketRankingData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| name | str \| None | No | None | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Price per share; currency is CNY. |
| priceChange | Decimal \| None | No | None | Signed absolute price change in CNY per share. |
| changeRate | Decimal \| None | No | None | Declared by the Pydantic model. |
| changeRate5d | Decimal \| None | No | None | Source-designated 5d price change, stored as a ratio fraction. |
| changeRate10d | Decimal \| None | No | None | Source-designated 10d price change, stored as a ratio fraction. |
| changeRate20d | Decimal \| None | No | None | Source-designated 20d price change, stored as a ratio fraction. |
| changeRate60d | Decimal \| None | No | None | Source-designated 60d price change, stored as a ratio fraction. |
| changeRate52w | Decimal \| None | No | None | Price change over the source-designated 52-week period, as a ratio fraction. |
| changeRateYtd | Decimal \| None | No | None | Year-to-date price change, stored as a ratio fraction. |
| amplitude | Decimal \| None | No | None | Intraday price amplitude, stored as a ratio fraction. |
| volumeRatio | Decimal \| None | No | None | Non-negative volume ratio in times; 2.35 represents 2.35x. |
| volume | int \| None | No | None | Declared by the Pydantic model. |
| amount | Decimal \| None | No | None | Declared by the Pydantic model. |
| turnoverRate | Decimal \| None | No | None | Declared by the Pydantic model. |
| marketCap | Decimal \| None | No | None | Declared by the Pydantic model. |
| floatMarketCap | Decimal \| None | No | None | Declared by the Pydantic model. |
| peTtm | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainNetInflow | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainInflow | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainOutflow | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainInflow5d | Decimal \| None | No | None | Declared by the Pydantic model. |
| mainOutflow5d | Decimal \| None | No | None | Declared by the Pydantic model. |
| universe | InstrumentUniverse | Yes | — | Declared by the Pydantic model. |
| direction | RankingDirection | Yes | — | Declared by the Pydantic model. |
| position | int | Yes | — | Declared by the Pydantic model. |
| metric | TurnoverRankingMetric \| ChangePercentRankingMetric \| VolumeRankingMetric | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `ChangePercentRankingMetric`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| criterion | Literal['change_percent'] | Yes | — | Declared by the Pydantic model. |
| value | Decimal | Yes | — | A ratio fraction, not percentage points: 4.24% is 0.0424. |

#### Nested model `TurnoverRankingMetric`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| criterion | Literal['turnover'] | Yes | — | Declared by the Pydantic model. |
| value | Decimal | Yes | — | Monetary amount in CNY. |

#### Nested model `VolumeRankingMetric`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| criterion | Literal['volume'] | Yes | — | Declared by the Pydantic model. |
| value | int | Yes | — | A non-negative whole number of shares. |

#### Example

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

Fetch the market sentiment snapshot in a FetchResult.

**Dataset:** `market.sentiment_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.market_sentiment`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.sentiment(request: 'MarketSentimentRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketSentimentData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketSentimentRequest \| None | No | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** none.

#### Request model `MarketSentimentRequest`

No fields; instantiate this model without arguments.

The public return annotation is `FetchResult[MarketSentimentData]`.

#### Returned data model `MarketSentimentData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| marketTemperature | Decimal | Yes | — | Aigupiao source-defined sentiment temperature; not a physical temperature or ratio. |
| totalTurnover | Decimal \| None | No | None | Declared by the Pydantic model. |
| forecastedTurnover | Decimal \| None | No | None | Source forecast, not observed turnover. |
| turnoverChangeAmount | Decimal \| None | No | None | Source-reported change in turnover amount versus the prior day. |
| blastBreakRatio | Decimal \| None | No | None | Source-defined ratio; FinchX does not reproduce the denominator. |
| previousLimitUpBreakChangeRatio | Decimal \| None | No | None | Source-defined previous broken-limit performance ratio. |
| stopTradingCount | int | Yes | — | Declared by the Pydantic model. |
| oneLimitUpCount | int | Yes | — | Declared by the Pydantic model. |
| twoLimitUpCount | int | Yes | — | Declared by the Pydantic model. |
| threeLimitUpCount | int | Yes | — | Declared by the Pydantic model. |
| highLimitUpCount | int | Yes | — | Declared by the Pydantic model. |
| twoLimitUpPromotionRatio | Decimal \| None | No | None | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| threeLimitUpPromotionRatio | Decimal \| None | No | None | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| highLimitUpPromotionRatio | Decimal \| None | No | None | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| previousLimitUpThemeChangeRatio | Decimal \| None | No | None | Source-defined previous limit-up group performance ratio. |
| previousConsecutiveLimitUpThemeChangeRatio | Decimal \| None | No | None | Source-defined previous consecutive-limit-up group performance ratio. |

#### Example

<!-- api-example: market.sentiment -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.sentiment()
```

### `fx.market.strong_pool(...)`

Fetch the strong pool in a FetchResult.

**Dataset:** `market.strong_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.strong_pool`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.strong_pool(request: 'MarketStrongPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStrongPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketStrongPoolRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request.

#### Request model `MarketStrongPoolRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketStrongPoolData]`.

#### Returned data model `MarketStrongPoolData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| price | Decimal | Yes | — | Latest price in CNY per share. |
| limitUpPrice | Decimal | Yes | — | Current limit-up price in CNY per share. |
| changeRate | Decimal | Yes | — | Ratio fraction; 20% is 0.20. |
| amount | Decimal | Yes | — | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| marketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| turnoverRate | Decimal | Yes | — | Ratio fraction. |
| isSixtyDayHigh | bool | Yes | — | Declared by the Pydantic model. |
| selectionReason | StrongPoolSelectionReason | Yes | — | Declared by the Pydantic model. |
| volumeRatio | Decimal | Yes | — | Source volume ratio as a dimensionless multiple. |
| industry | str | Yes | — | Declared by the Pydantic model. |
| limitUpStats | MarketStrongPoolStats | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `MarketStrongPoolStats`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | Declared by the Pydantic model. |
| limitUpCount | int | Yes | — | Declared by the Pydantic model. |

#### Example

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

Fetch the yesterday-limit-up pool in a FetchResult.

**Dataset:** `market.yesterday_limit_up_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.yesterday_limit_up_pool`
**Routing semantics:** `single_source`

#### Method signature

```python
fx.market.yesterday_limit_up_pool(request: 'MarketYesterdayLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketYesterdayLimitUpPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketYesterdayLimitUpPoolRequest | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** request.

#### Request model `MarketYesterdayLimitUpPoolRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[MarketYesterdayLimitUpPoolData]`.

#### Returned data model `MarketYesterdayLimitUpPoolData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| tradeDate | date | Yes | — | Current observed source date, not the prior limit-up event date. |
| name | str | Yes | — | Declared by the Pydantic model. |
| currentPrice | Decimal | Yes | — | Current-session price in CNY per share. |
| currentLimitUpPrice | Decimal | Yes | — | Current-session limit-up price in CNY per share. |
| currentChangeRate | Decimal | Yes | — | Current-session ratio fraction. |
| currentAmount | Decimal | Yes | — | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| marketCapitalization | Decimal | Yes | — | Monetary amount in CNY. |
| currentTurnoverRate | Decimal | Yes | — | Current-session turnover ratio fraction. |
| currentAmplitude | Decimal | Yes | — | Current-session amplitude as a ratio fraction. |
| yesterdayFirstLimitUpTime | str \| None | No | None | Previous-session first limit-up time, market-local HH:MM:SS. |
| yesterdayConsecutiveLimitUpDays | int | Yes | — | Declared by the Pydantic model. |
| industry | str | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

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

Fetch a company's profile in a FetchResult.

**Dataset:** `fundamental.company_profile`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.fundamental.company_profile(instrument_id: 'InstrumentInput | None' = None, *, request: 'CompanyProfileRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CompanyProfileData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required in convenience mode | None | Complete InstrumentId. |
| request | CompanyProfileRequest \| None | Conditional request alternative | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument_id (InstrumentId or six-digit equity code) or request.

#### Request model `CompanyProfileRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[CompanyProfileData]`.

#### Returned data model `CompanyProfileData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| companyName | str \| None | No | None | Declared by the Pydantic model. |
| businessDescription | str \| None | No | None | Declared by the Pydantic model. |
| issuePrice | Decimal \| None | No | None | CNY per share. Tencent gsjj.jg is retained as the source candidate. |
| listingDate | date \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: fundamental.company_profile -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.company_profile("600519")
```

### `fx.fundamental.financial_summary(...)`

Fetch a company's financial summary in a FetchResult.

**Dataset:** `fundamental.financial_summary`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.fundamental.financial_summary(request: 'FinancialSummaryRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialSummaryData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | FinancialSummaryRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `FinancialSummaryRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[FinancialSummaryData]`.

#### Returned data model `FinancialSummaryData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| periods | list[FinancialSummaryPeriod] | Yes | — | Declared by the Pydantic model. |

#### Nested model `FinancialSummaryPeriod`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| periodEnd | date \| None | No | None | Declared by the Pydantic model. |
| reportedPeriodLabel | str | Yes | — | Declared by the Pydantic model. |
| periodType | Literal['annual', 'interim', 'unknown'] | Yes | — | Declared by the Pydantic model. |
| eps | Decimal \| None | No | None | Declared by the Pydantic model. |
| revenue | Decimal \| None | No | None | Declared by the Pydantic model. |
| revenueGrowth | Decimal \| None | No | None | Declared by the Pydantic model. |
| netProfit | Decimal \| None | No | None | Declared by the Pydantic model. |
| netProfitGrowth | Decimal \| None | No | None | Declared by the Pydantic model. |
| bookValuePerShare | Decimal \| None | No | None | Declared by the Pydantic model. |
| netAssets | Decimal \| None | No | None | Declared by the Pydantic model. |
| goodwill | Decimal \| None | No | None | Declared by the Pydantic model. |
| goodwillToNetAssets | Decimal \| None | No | None | Declared by the Pydantic model. |
| roe | Decimal \| None | No | None | Declared by the Pydantic model. |
| debtRatio | Decimal \| None | No | None | Declared by the Pydantic model. |
| grossMargin | Decimal \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: fundamental.financial_summary -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.financial_summary("600519")
```

### `fx.fundamental.industry_comparison(...)`

Fetch the fundamental industry comparison in a FetchResult.

**Dataset:** `fundamental.industry_comparison`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.fundamental.industry_comparison(request: 'FundamentalIndustryComparisonRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndustryComparisonData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | FundamentalIndustryComparisonRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

**Naming note:** The Client annotation spells this local alias as `FundamentalIndustryComparisonRequest`; the real public class and Dataset request type are `finchx.datasets.IndustryComparisonRequest`.

#### Request model `IndustryComparisonRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[IndustryComparisonData]`.

#### Returned data model `IndustryComparisonData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| industryName | str \| None | No | None | Declared by the Pydantic model. |
| metrics | list[IndustryComparisonMetric] | Yes | — | Declared by the Pydantic model. |

#### Nested model `IndustryComparisonMetric`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| metric | Literal['eps', 'revenue', 'net_profit', 'book_value_per_share', 'roe', 'debt_ratio', 'gross_margin', 'revenue_growth', 'net_profit_growth', 'market_cap', 'pe', 'pb', 'dividend_yield'] | Yes | — | Declared by the Pydantic model. |
| metricBasis | Literal['financial_period', 'market_snapshot'] | Yes | — | Declared by the Pydantic model. |
| companyValue | Decimal \| Decimal \| Decimal \| None | No | None | Declared by the Pydantic model. |
| industryAvg | Decimal \| Decimal \| Decimal \| None | No | None | Declared by the Pydantic model. |
| industryMax | Decimal \| Decimal \| Decimal \| None | No | None | Declared by the Pydantic model. |
| industryMin | Decimal \| Decimal \| Decimal \| None | No | None | Declared by the Pydantic model. |
| periodEnd | date \| None | No | None | Declared by the Pydantic model. |
| reportedPeriodLabel | str | Yes | — | Declared by the Pydantic model. |
| observationAt | datetime \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: fundamental.industry_comparison -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.industry_comparison("600519")
```

### `fx.fundamental.revenue_breakdown(...)`

Fetch a company's revenue breakdown in a FetchResult.

**Dataset:** `fundamental.revenue_breakdown`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.fundamental.revenue_breakdown(request: 'RevenueBreakdownRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RevenueBreakdownData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | RevenueBreakdownRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `RevenueBreakdownRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[RevenueBreakdownData]`.

#### Returned data model `RevenueBreakdownData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| breakdowns | list[RevenueBreakdownRow] | Yes | — | Declared by the Pydantic model. |

#### Nested model `RevenueBreakdownRow`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| reportedPeriodLabel | str | Yes | — | Declared by the Pydantic model. |
| periodEnd | date \| None | No | None | Declared by the Pydantic model. |
| dimension | Literal['product', 'region', 'industry'] | Yes | — | Declared by the Pydantic model. |
| itemName | str | Yes | — | Declared by the Pydantic model. |
| revenue | Decimal \| None | Yes | — | Declared by the Pydantic model. |
| revenueShare | Decimal \| None | No | None | Declared by the Pydantic model. |
| currency | Literal['CNY'] | Yes | — | Declared by the Pydantic model. |
| sourceGroup | Literal['detail', 'others'] | Yes | — | Declared by the Pydantic model. |
| isRollup | bool | Yes | — | Declared by the Pydantic model. |

#### Example

<!-- api-example: fundamental.revenue_breakdown -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.fundamental.revenue_breakdown("600519")
```

## `financial`

### `fx.financial.statements(...)`

Fetch financial statements in a FetchResult.

**Dataset:** `financial.statement`
**Schema version:** `1.0`
**Implemented Providers:** `tonghuashun.financial`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.financial.statements(instrument_id: 'InstrumentInput | None' = None, statement_type: 'StatementType | None' = None, *, period_end: 'date | None' = None, max_periods: 'int | None' = None, request: 'FinancialStatementRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialStatementData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput \| None | Required in convenience mode | None | Complete InstrumentId. |
| statement_type | StatementType \| None | Required in convenience mode | None | balance_sheet, income_statement, or cash_flow_statement. |
| period_end | date \| None | No | None | Optional report-period end date. |
| max_periods | int \| None | No | None | Optional maximum number of report periods. |
| request | FinancialStatementRequest \| None | Conditional request alternative | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument_id (InstrumentId or six-digit equity code) and statement_type, or request.

#### Request model `FinancialStatementRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | Yes | — | Declared by the Pydantic model. |
| periodEnd | date \| None | No | None | Declared by the Pydantic model. |
| maxPeriods | int \| None | No | None | Declared by the Pydantic model. |

The public return annotation is `FetchResult[FinancialStatementData]`.

#### Returned data model `FinancialStatementData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | Yes | — | Declared by the Pydantic model. |
| periods | list[FinancialStatementPeriod] | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `FinancialStatementPeriod`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| periodEnd | date | Yes | — | Declared by the Pydantic model. |
| lineItems | list[FinancialStatementLineItem] | Yes | — | Declared by the Pydantic model. |

#### Nested model `FinancialStatementLineItem`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lineItemId | str | Yes | — | Declared by the Pydantic model. |
| sourceName | str | Yes | — | Declared by the Pydantic model. |
| sourceUnit | str | Yes | — | Declared by the Pydantic model. |
| sourceValue | str \| bool \| int \| float \| None | Yes | — | Declared by the Pydantic model. |
| value | Decimal \| None | No | None | Declared by the Pydantic model. |
| currency | Currency \| None | No | None | Declared by the Pydantic model. |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: financial.statements -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.financial.statements("600519", "income_statement")
```

## `news`

### `fx.news.search(...)`

Search news metadata and return document references in a FetchResult.

**Dataset:** `news.document`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.news.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, sort: 'str' = 'published_desc', request: 'NewsSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[NewsDocumentRef, ...]]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | Required in convenience mode | None | InstrumentId or a six-digit equity code. |
| page | int | No | 1 | One-based page number. |
| page_size | int | No | 20 | Page size. |
| max_results | int \| None | No | None | Optional result cap; its combination with non-first pages is model-validated. |
| since | date \| datetime \| None | No | None | Optional inclusive lower time bound. |
| until | date \| datetime \| None | No | None | Optional inclusive upper time bound. |
| sort | str | No | 'published_desc' | published_desc or published_asc. |
| request | NewsSearchRequest \| None | Conditional request alternative | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `NewsSearchRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| page | int | No | 1 | Declared by the Pydantic model. |
| pageSize | int | No | 20 | Declared by the Pydantic model. |
| maxResults | int \| None | No | None | Declared by the Pydantic model. |
| since | date \| datetime \| None | No | None | Declared by the Pydantic model. |
| until | date \| datetime \| None | No | None | Declared by the Pydantic model. |
| sort | Literal['published_desc', 'published_asc'] | No | 'published_desc' | Declared by the Pydantic model. |

The public return annotation is `FetchResult[tuple[NewsDocumentRef, Ellipsis]]`.

#### Returned data model `NewsDocumentData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| documentId | str | Yes | — | Declared by the Pydantic model. |
| sourceDocumentId | str | Yes | — | Declared by the Pydantic model. |
| title | str | Yes | — | Declared by the Pydantic model. |
| contentText | str \| None | No | None | Declared by the Pydantic model. |
| summary | str \| None | No | None | Declared by the Pydantic model. |
| publishedAt | datetime \| None | No | None | Declared by the Pydantic model. |
| sourceOccurrences | list[NewsSourceOccurrence] | No | default_factory=list | Declared by the Pydantic model. |
| url | AnyUrl | Yes | — | Declared by the Pydantic model. |
| originalUrl | AnyUrl \| None | No | None | Declared by the Pydantic model. |
| contentAvailable | bool | Yes | — | Declared by the Pydantic model. |
| source | str \| None | No | None | Declared by the Pydantic model. |
| relatedInstruments | list[InstrumentId] | Yes | — | Declared by the Pydantic model. |

#### Nested model `NewsSourceOccurrence`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| providerId | str | Yes | — | Declared by the Pydantic model. |
| sourceDocumentId | str | Yes | — | Declared by the Pydantic model. |
| sourceUrl | AnyUrl \| None | No | None | Declared by the Pydantic model. |
| documentUrl | AnyUrl \| None | No | None | Declared by the Pydantic model. |
| publishedAt | datetime \| None | No | None | Declared by the Pydantic model. |
| capturedAt | datetime | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: news.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.news.search("600519")
```

## `disclosure`

### `fx.disclosure.search(...)`

Search disclosures and return document references in a FetchResult.

**Dataset:** `disclosure.document`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.disclosure`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.disclosure.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, categories: 'Sequence[str] | None' = None, sort: 'str' = 'published_desc', request: 'DisclosureSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[DisclosureDocumentRef, ...]]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | Required in convenience mode | None | InstrumentId or a six-digit equity code. |
| page | int | No | 1 | One-based page number. |
| page_size | int | No | 20 | Page size. |
| max_results | int \| None | No | None | Optional result cap; its combination with non-first pages is model-validated. |
| since | date \| datetime \| None | No | None | Optional inclusive lower time bound. |
| until | date \| datetime \| None | No | None | Optional inclusive upper time bound. |
| categories | Sequence[str] \| None | No | None | Optional disclosure category list. |
| sort | str | No | 'published_desc' | published_desc or published_asc. |
| request | DisclosureSearchRequest \| None | Conditional request alternative | None | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `DisclosureSearchRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| page | int | No | 1 | Declared by the Pydantic model. |
| pageSize | int | No | 20 | Declared by the Pydantic model. |
| maxResults | int \| None | No | None | Declared by the Pydantic model. |
| since | date \| datetime \| None | No | None | Declared by the Pydantic model. |
| until | date \| datetime \| None | No | None | Declared by the Pydantic model. |
| sort | Literal['published_desc', 'published_asc'] | No | 'published_desc' | Declared by the Pydantic model. |
| categories | list[str] \| None | No | None | Declared by the Pydantic model. |

The public return annotation is `FetchResult[tuple[DisclosureDocumentRef, Ellipsis]]`.

#### Returned data model `DisclosureDocumentData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| documentId | str | Yes | — | Declared by the Pydantic model. |
| sourceDocumentId | str | Yes | — | Declared by the Pydantic model. |
| title | str | Yes | — | Declared by the Pydantic model. |
| contentText | str \| None | No | None | Declared by the Pydantic model. |
| noticeDate | date | Yes | — | Declared by the Pydantic model. |
| publishedAt | datetime \| None | No | None | Declared by the Pydantic model. |
| sourceRecordedAt | datetime \| None | No | None | Declared by the Pydantic model. |
| categories | list[DisclosureCategory] | Yes | — | Declared by the Pydantic model. |
| relatedInstruments | list[InstrumentId] | Yes | — | Declared by the Pydantic model. |
| contentAvailable | bool | Yes | — | Declared by the Pydantic model. |
| pdfAvailable | bool | Yes | — | Declared by the Pydantic model. |
| originalDocumentUrl | AnyUrl | Yes | — | Declared by the Pydantic model. |
| attachments | list[DisclosureAttachment] | Yes | — | Declared by the Pydantic model. |
| sourceType | str \| None | No | None | Declared by the Pydantic model. |

#### Nested model `DisclosureCategory`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| name | str | Yes | — | Declared by the Pydantic model. |
| source | str | No | 'eastmoney' | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `DisclosureAttachment`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| sequence | int \| None | No | None | Declared by the Pydantic model. |
| size | int \| None | No | None | Declared by the Pydantic model. |
| attachmentType | str \| None | No | None | Declared by the Pydantic model. |
| url | AnyUrl | Yes | — | Declared by the Pydantic model. |
| webUrl | AnyUrl \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: disclosure.search -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.disclosure.search("600519")
```

## `ownership`

### `fx.ownership.capital_snapshot(...)`

Fetch a capital snapshot in a FetchResult.

**Dataset:** `ownership.capital_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.ownership.capital_snapshot(request: 'CapitalSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CapitalSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | CapitalSnapshotRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `CapitalSnapshotRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[CapitalSnapshotData]`.

#### Returned data model `CapitalSnapshotData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| totalShares | int \| None | No | None | Declared by the Pydantic model. |
| floatShares | int \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: ownership.capital_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.capital_snapshot("600519")
```

### `fx.ownership.float_holder(...)`

Fetch floating-holder data in a FetchResult.

**Dataset:** `ownership.float_holder`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.float_holder`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.ownership.float_holder(request: 'FloatHolderRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FloatHolderData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | FloatHolderRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `FloatHolderRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| asOf | datetime \| None | No | None | Declared by the Pydantic model. |

The public return annotation is `FetchResult[FloatHolderData]`.

#### Returned data model `FloatHolderData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| periods | list[FloatHolderPeriod] | Yes | — | Declared by the Pydantic model. |

#### Nested model `FloatHolderPeriod`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| periodEnd | date | Yes | — | Declared by the Pydantic model. |
| publishedAt | datetime | Yes | — | Declared by the Pydantic model. |
| rows | list[FloatHolderRow] | Yes | — | Declared by the Pydantic model. |

#### Nested model `FloatHolderRow`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| rank | int | Yes | — | Derived from Tencent rows array order. |
| holderId | str \| None | No | None | Declared by the Pydantic model. |
| holderName | str | Yes | — | Declared by the Pydantic model. |
| shares | int | Yes | — | A non-negative whole number of shares. |
| holderType | str | Yes | — | Declared by the Pydantic model. |
| floatShareRatio | Decimal \| None | No | None | Declared by the Pydantic model. |
| previousShares | int \| None | No | None | Declared by the Pydantic model. |
| shareChange | int \| None | No | None | Declared by the Pydantic model. |
| isNewTopFloatHolderEntry | bool \| None | No | None | Derived from bdms=1 after multi-stock adjacent-period validation. |

#### Example

<!-- api-example: ownership.float_holder -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.float_holder("600519")
```

### `fx.ownership.holder_summary_snapshot(...)`

Fetch a holder-summary snapshot in a FetchResult.

**Dataset:** `ownership.holder_summary_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.ownership.holder_summary_snapshot(request: 'HolderSummarySnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[HolderSummarySnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | HolderSummarySnapshotRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `HolderSummarySnapshotRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[HolderSummarySnapshotData]`.

#### Returned data model `HolderSummarySnapshotData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| shareholderCount | int \| None | No | None | Declared by the Pydantic model. |
| averageSharesPerHolder | Decimal \| None | No | None | Exact share count per holder; Tencent rjcg display units are normalized to shares. |
| shareholderCountChange | Decimal \| None | No | None | Tencent gdrshb, normalized from percentage points to a ratio; not an absolute count delta. |
| top10FloatHolderRatio | Decimal \| None | No | None | Declared by the Pydantic model. |
| top10HolderRatio | Decimal \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: ownership.holder_summary_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.ownership.holder_summary_snapshot("600519")
```

## `company`

### `fx.company.executive_share_change(...)`

Fetch executive share changes in a FetchResult.

**Dataset:** `company.executive_share_change`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.company.executive_share_change(request: 'ExecutiveShareChangeRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveShareChangeData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | ExecutiveShareChangeRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `ExecutiveShareChangeRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[ExecutiveShareChangeData]`.

#### Returned data model `ExecutiveShareChangeData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| changes | list[ExecutiveShareChange] | Yes | — | Declared by the Pydantic model. |

#### Nested model `ExecutiveShareChange`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| eventDate | date \| None | No | None | Declared by the Pydantic model. |
| personName | str \| None | No | None | Declared by the Pydantic model. |
| shareChange | int \| None | No | None | Declared by the Pydantic model. |
| averagePrice | Decimal \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: company.executive_share_change -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_share_change("600519")
```

### `fx.company.executive_snapshot(...)`

Fetch an executive snapshot in a FetchResult.

**Dataset:** `company.executive_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.company.executive_snapshot(request: 'ExecutiveSnapshotRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | ExecutiveSnapshotRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `ExecutiveSnapshotRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[ExecutiveSnapshotData]`.

#### Returned data model `ExecutiveSnapshotData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| executives | list[ExecutiveEntry] | Yes | — | Declared by the Pydantic model. |

#### Nested model `ExecutiveEntry`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| name | str | Yes | — | Declared by the Pydantic model. |
| roles | list[str] | Yes | — | Declared by the Pydantic model. |
| shares | int \| None | No | None | Declared by the Pydantic model. |
| compensation | Decimal \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: company.executive_snapshot -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.company.executive_snapshot("600519")
```

## `corporate_action`

### `fx.corporate_action.dividend(...)`

Fetch dividend actions in a FetchResult.

**Dataset:** `corporate_action.dividend`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.corporate_action.dividend(request: 'DividendRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DividendData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | DividendRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `DividendRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[DividendData]`.

#### Returned data model `DividendData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| dividends | list[Dividend] | Yes | — | Declared by the Pydantic model. |

#### Nested model `Dividend`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| fiscalYear | int \| None | No | None | Declared by the Pydantic model. |
| announcementDate | date \| None | No | None | Declared by the Pydantic model. |
| stockDividendPer10 | Decimal \| None | No | None | Declared by the Pydantic model. |
| capitalizationPer10 | Decimal \| None | No | None | Declared by the Pydantic model. |
| cashDividendPer10 | Decimal \| None | No | None | Declared by the Pydantic model. |
| rightsIssuePer10 | Decimal \| None | No | None | Declared by the Pydantic model. |
| recordDate | date \| None | No | None | Declared by the Pydantic model. |
| exDate | date \| None | No | None | Declared by the Pydantic model. |
| description | str \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: corporate_action.dividend -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.dividend("600519")
```

### `fx.corporate_action.repurchase(...)`

Fetch repurchase actions in a FetchResult.

**Dataset:** `corporate_action.repurchase`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`

#### Method signature

```python
fx.corporate_action.repurchase(request: 'RepurchaseRequest | InstrumentInput', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RepurchaseData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | RepurchaseRequest \| InstrumentInput | Yes | — | Typed request model; valid combinations are governed by the Client and Pydantic validation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument (InstrumentId or six-digit equity code), or request.

#### Request model `RepurchaseRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |

The public return annotation is `FetchResult[RepurchaseData]`.

#### Returned data model `RepurchaseData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| symbol | str | Yes | — | Declared by the Pydantic model. |
| repurchases | list[Repurchase] | Yes | — | Declared by the Pydantic model. |

#### Nested model `Repurchase`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| repurchaseDate | date \| None | No | None | Declared by the Pydantic model. |
| quantity | int \| None | No | None | Declared by the Pydantic model. |
| averagePrice | Decimal \| None | No | None | Declared by the Pydantic model. |
| currency | Currency \| None | No | None | Declared by the Pydantic model. |
| fundAmount | Decimal \| None | No | None | Declared by the Pydantic model. |
| market | str \| None | No | None | Declared by the Pydantic model. |

#### Example

<!-- api-example: corporate_action.repurchase -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.corporate_action.repurchase("600519")
```

## `market.deviation`

### `fx.market.deviation(...)`

Compute close-based 10-day/30-day deviation from existing data.

**Dataset:** `market.deviation` (computed; no Provider)
**Schema version:** `1.0`

#### Method signature

```python
fx.market.deviation(instrument_id: 'InstrumentInput', *, windows: 'Sequence[int]' = (10, 30), as_of: 'date | None' = None, window_convention: 'DeviationWindowConvention' = <DeviationWindowConvention.MAX_DEVIATION_SCAN: 'max_deviation_scan'>, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DeviationData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentInput | Yes | — | Complete InstrumentId. |
| windows | Sequence[int] | No | (10, 30) | Supported deviation windows: 10 and 30 trading sessions. |
| as_of | date \| None | No | None | Optional completed-session date. |
| window_convention | DeviationWindowConvention | No | DeviationWindowConvention.MAX_DEVIATION_SCAN | Deviation window interpretation. |
| provider | str \| None | No | None | Strict Provider id pin; a failure is not silently redirected. |
| use_cache | bool \| None | No | None | Cache control; None follows the configured CachePolicy. |

**Minimum business input:** instrument_id (InstrumentId or six-digit equity code).

#### Request model `DeviationRequest`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| asOf | date \| None | No | None | Declared by the Pydantic model. |
| windows | tuple[Literal[10, 30], Ellipsis] | No | (10, 30) | Declared by the Pydantic model. |
| windowConvention | DeviationWindowConvention | No | DeviationWindowConvention.MAX_DEVIATION_SCAN | Declared by the Pydantic model. |

The public return annotation is `FetchResult[DeviationData]`.

#### Returned data model `DeviationData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Declared by the Pydantic model. |
| board | str | Yes | — | Declared by the Pydantic model. |
| effectiveAsOf | date | Yes | — | Declared by the Pydantic model. |
| calculationMode | Literal['official_close'] | Yes | — | Declared by the Pydantic model. |
| priceBasis | Literal['qfq_stock__raw_index'] | Yes | — | Declared by the Pydantic model. |
| ruleVersion | str | Yes | — | Declared by the Pydantic model. |
| windows | tuple[DeviationWindowData, Ellipsis] | Yes | — | Declared by the Pydantic model. |

#### Nested model `InstrumentId`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Declared by the Pydantic model. |
| market | Market | Yes | — | Declared by the Pydantic model. |
| kind | InstrumentKind | Yes | — | Declared by the Pydantic model. |
| exchange | Exchange \| None | No | None | Declared by the Pydantic model. |

#### Nested model `DeviationWindowData`

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| windowDays | Literal[10, 30] | Yes | — | Declared by the Pydantic model. |
| windowConvention | DeviationWindowConvention | Yes | — | Declared by the Pydantic model. |
| tradingSessions | int | Yes | — | Declared by the Pydantic model. |
| startDate | date | Yes | — | Declared by the Pydantic model. |
| baselineDate | date | Yes | — | Declared by the Pydantic model. |
| endDate | date | Yes | — | Declared by the Pydantic model. |
| startPrice | Decimal | Yes | — | Declared by the Pydantic model. |
| windowStartPrice | Decimal | Yes | — | Declared by the Pydantic model. |
| currentPrice | Decimal | Yes | — | Declared by the Pydantic model. |
| benchmarkInstrument | InstrumentId | Yes | — | Declared by the Pydantic model. |
| benchmarkName | str | Yes | — | Declared by the Pydantic model. |
| benchmarkStart | Decimal | Yes | — | Declared by the Pydantic model. |
| benchmarkCurrent | Decimal | Yes | — | Declared by the Pydantic model. |
| stockReturn | Decimal | Yes | — | Declared by the Pydantic model. |
| benchmarkReturn | Decimal | Yes | — | Declared by the Pydantic model. |
| deviation | Decimal | Yes | — | Declared by the Pydantic model. |
| upperThreshold | Decimal | Yes | — | Declared by the Pydantic model. |
| lowerThreshold | Decimal | Yes | — | Declared by the Pydantic model. |
| remainingToUpper | Decimal | Yes | — | Declared by the Pydantic model. |
| remainingToLower | Decimal | Yes | — | Declared by the Pydantic model. |
| upperTriggerPrice | Decimal | Yes | — | Declared by the Pydantic model. |
| lowerTriggerPrice | Decimal | Yes | — | Declared by the Pydantic model. |
| remainingPricePctToUpper | Decimal | Yes | — | Declared by the Pydantic model. |
| remainingPricePctToLower | Decimal | Yes | — | Declared by the Pydantic model. |

#### Example

<!-- api-example: market.deviation -->
```python
from finchx import FinchX

fx = FinchX()
result = fx.market.deviation("600519", windows=(10, 30))
```
