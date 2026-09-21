# FinchX Data & API Reference

English | [简体中文](DATA_API_REFERENCE.zh-CN.md)


This reference describes the current public surface from the Client, Dataset definitions, Pydantic schemas and Provider registry: 42 Provider-backed / Dataset-backed public endpoints plus the computed `market.deviation` capability. The computed capability is documented separately because it is intentionally outside the Provider-backed inventory.

## Common concepts

### InstrumentId

Most market, fundamental, financial, ownership, company and corporate-action requests use a complete `InstrumentId`:

```python
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

instrument_id = InstrumentId(
    code="600519", market=Market.CN_A,
    kind=InstrumentKind.EQUITY, exchange=Exchange.SSE,
)
```
Allowed enum values are `Market.CN_A` (`cn_a`), `InstrumentKind.EQUITY`/`INDEX`/`ETF` (`equity`, `index`, `etf`), and `Exchange.SSE`/`SZSE`/`BSE` (`sse`, `szse`, `bse`). `exchange` is optional in the base identity model but is required by capabilities that need an exchange-specific mapping.

### FetchResult

All explicit Client methods return a `FetchResult`. Its fields are:

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `data` | generic | — | Returned standardized records, document references, or computed data. |
| `dataset` | DatasetDefinition | — | Dataset name, schema version, request type and payload type. |
| `dataset_id` | str | — | Convenience property containing `dataset.name`. |
| `provider` | str \| None | — | Provider id used for the successful fetch; computed deviation is `None`. |
| `provider_id` | str \| None | — | Convenience property mirroring `provider`. |
| `captured_at` | datetime | — | Timezone-aware FinchX capture time. |
| `warnings` | tuple[str, ...] | () | Non-fatal fetch warnings. |
| `provenance` | tuple[Source, ...] | () | Direct source identities retained by the result. |
| `attempts` | tuple[FetchAttempt, ...] | () | Provider attempts, including retry/failure facts when available. |
| `fallback_used` | bool | False | Whether the runtime used a later allowed Provider after an earlier failure. |
| `cache_hit` | bool | False | Whether the result came from the configured cache. |

A provider-backed record is a `StandardRecord` envelope. Its public fields are `dataset`, `schemaVersion`, `recordId`, `entityId`, `eventAt`, `publishedAt`, `updatedAt`, `capturedAt`, `asOf`, `source`, `status`, `quality`, `provenance` and `data`. The Dataset field tables below describe the normalized `record.data` payload. Listing and time-series endpoints return a tuple of envelopes; news and disclosure search return tuples of `NewsDocumentRef` or `DisclosureDocumentRef` rather than full `StandardRecord` envelopes.

`Source` contains `providerId`, optional `sourceRecordId` and optional `sourceUrl`. `FetchAttempt` contains `provider`, `attempt`, `started_at`, `captured_at`, `success`, and optional `error_type`/`error_message`.

### Provider selection

`provider=` is a strict pin. When provided, only that Provider id is used and a failure is not silently redirected to another Provider. Without a pin, runtime policy controls retry and Provider selection. This document lists implemented Providers only; it does not assign primary or fallback roles.

Provider ids are stable registry identities such as `tencent.finance.qq.klines` or `eastmoney.stockrank`. A Dataset marked `single_source` has a source-specific public contract; a Dataset marked `multi_provider` can admit peer Providers implementing the same normalized contract.

### Cache

`use_cache=None` follows the configured `CachePolicy`. `use_cache=False` bypasses cache reads. An explicit Provider pin bypasses a cached result. `FinchX()` has no enabled cache or default SQLite file unless one is supplied through Collector configuration.

### Time fields

`capturedAt` is when FinchX captured an upstream observation. It is distinct from source `publishedAt`, source `sourceTimestamp`, market `tradeDate`/`barDate`, disclosure `noticeDate`, and source `calculatedAt`. `effectiveAsOf` in deviation is the completed session actually used by the calculation.

### Errors

The main public categories are `InvalidRequest`, `AuthenticationError`, `MissingOptionalDependency`, `SchemaDrift`, `NoData`, `ProviderDoesNotSupportDataset`, `UnknownProvider`, and `AllProvidersFailed`. Transport, rate-limit and timeout conditions may be retried or routed according to the configured runtime policy when no strict Provider pin is used.

## Data Sources

The table lists the current registry identities and the public endpoints that use them. It is an implementation inventory, not an upstream SLA or a promised routing order.

| Provider id | Endpoints | Notes |
| --- | --- | --- |
| `szse.official.calendar` | `reference.trading_calendar` | — |
| `pandas_market_calendars` | `reference.trading_calendar` | optional: pandas_market_calendars |
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
| `jiuyangongshe.daily_replay` | `market.daily_replay` | authentication required; optional: playwright |

## Endpoint Index

The index covers all 42 registered Dataset-backed methods plus the computed deviation capability.

| Namespace | Endpoint | Dataset | Implemented Provider(s) | Required primary input |
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

## Endpoint reference

## `reference`

Canonical instrument identity and trading-day calendars.

### `fx.reference.instrument(...)`

Look up canonical identity and display name for one instrument, or return the selected A-share universe when the instrument is omitted.

**Dataset:** `instrument`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.market`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.reference.instrument(instrument_id: 'InstrumentId | None' = None, *, request: 'InstrumentRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[InstrumentData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | Complete InstrumentId for the target instrument. |
| request | InstrumentRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `InstrumentRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[InstrumentData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `InstrumentData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| name | str | No | Provider-normalized display name. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.market`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.reference.trading_calendar(...)`

Return one row for every natural date in a requested range, with the canonical trading-day flag.

**Dataset:** `trading_calendar`
**Schema version:** `1.0`
**Implemented Providers:** `szse.official.calendar`, `pandas_market_calendars`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.reference.trading_calendar(start_date: 'date | None' = None, end_date: 'date | None' = None, *, market: 'Market' = <Market.CN_A: 'cn_a'>, request: 'TradingCalendarRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[TradingCalendarData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| start_date | date \| None | No | None | Inclusive start date. |
| end_date | date \| None | No | None | Inclusive end date. |
| market | Market | No | <Market.CN_A: 'cn_a'> | Market enum; the public calendar contract defaults to Market.CN_A. |
| request | TradingCalendarRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `TradingCalendarRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| market | Literal['cn_a'] | Yes | — | FinchX market identifier. |
| startDate | date | Yes | — | Inclusive start date of the requested range or selected window. |
| endDate | date | Yes | — | Inclusive end date of the requested range or selected window. |

#### Return value

The public method annotation is `FetchResult[TradingCalendarData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `TradingCalendarData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| date | date | No | Natural calendar date represented by the row. |
| isTradingDay | bool | No | Normalized is trading day field. |



#### Example

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

#### Provider behavior and notes

The registry currently implements: `szse.official.calendar`, `pandas_market_calendars`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

**Optional dependency:** install the source extra for pandas_market_calendars. From a source checkout use `python -m pip install ".[calendar]"`; after PyPI publication use the equivalent `finchx[calendar]` extra.

## `market`

Quotes, rankings, pools, flows, intraday data, klines, sectors and market intelligence.

### `fx.market.breadth(...)`

Return the EastMoney market breadth snapshot, including advancing, declining and limit-up/limit-down counts.

**Dataset:** `market.breadth`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.breadth`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.breadth(request: 'MarketBreadthRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBreadthData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketBreadthRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketBreadthRequest`. Its fields are:

This request model has no fields; call the endpoint without a request object or use the default request behavior.

#### Return value

The public method annotation is `FetchResult[MarketBreadthData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketBreadthData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| advancing | int | No | Number or value of advancing instruments in the breadth snapshot. |
| declining | int | No | Number or value of declining instruments in the breadth snapshot. |
| unchanged | int | No | Number or value of unchanged instruments in the breadth snapshot. |
| total | int | No | Total instrument count represented by the snapshot. |
| limitUpCount | int | No | Number of limit-up instruments. |
| limitDownCount | int | No | Number of limit-down instruments. |
| upOver10PercentCount | int | No | Count of instruments up more than 10%. |
| downOver10PercentCount | int | No | Count of instruments down more than 10%. |
| distribution | list[MarketBreadthDistributionEntry] | No | Breadth distribution buckets supplied by EastMoney. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`MarketBreadthDistributionEntry`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| bucket | MarketBreadthBucket | Yes | — | Normalized bucket field. |
| count | int | Yes | — | Number of listed stocks in this return bucket. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.push2ex.breadth`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.broken_limit_pool(...)`

Return stocks that broke a limit-up during the requested trading date, together with the source-defined break statistics.

**Dataset:** `market.broken_limit_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.broken_limit_pool`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.broken_limit_pool(request: 'MarketBrokenLimitPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketBrokenLimitPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketBrokenLimitPoolRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketBrokenLimitPoolRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Source trading-date label; it is not FinchX capture time. |

#### Return value

The public method annotation is `FetchResult[MarketBrokenLimitPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketBrokenLimitPoolData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| name | str | No | Provider-normalized display name. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| limitUpPrice | Decimal | No | Current-session limit-up price in CNY per share. |
| changeRate | Decimal | No | Change ratio; 10% is represented as 0.10. |
| amount | Decimal | No | Traded amount in CNY. |
| floatMarketCapitalization | Decimal | No | Floating market capitalization in CNY. |
| marketCapitalization | Decimal | No | Total market capitalization in CNY. |
| turnoverRate | Decimal | No | Turnover ratio; percentage values are represented as fractions. |
| amplitude | Decimal | No | Intraday price amplitude as a ratio fraction. |
| firstLimitUpTime | str \| None | Yes | First limit-up time in the source market-local time format. |
| limitUpBreakCount | int | No | Number of limit-up breaks observed by the source. |
| industry | str | No | Source-provided industry label. |
| limitUpStats | MarketBrokenLimitPoolStats | No | Source-defined limit-up history statistics. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`MarketBrokenLimitPoolStats`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | Normalized lookback days field. |
| limitUpCount | int | Yes | — | Number of limit-up instruments. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.push2ex.broken_limit_pool`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.consecutive_limit_up(...)`

Return the Aigupiao snapshot of stocks with consecutive limit-up behavior and their associated theme fields.

**Dataset:** `market.consecutive_limit_up_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.series_limit_up`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.consecutive_limit_up(request: 'MarketConsecutiveLimitUpRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketConsecutiveLimitUpData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketConsecutiveLimitUpRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketConsecutiveLimitUpRequest`. Its fields are:

This request model has no fields; call the endpoint without a request object or use the default request behavior.

#### Return value

The public method annotation is `FetchResult[MarketConsecutiveLimitUpData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketConsecutiveLimitUpData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| name | str | No | Provider-normalized display name. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| lastPrice | Decimal | No | Latest price in CNY per share. |
| change | Decimal | No | Signed price change in CNY per share. |
| changeRatio | Decimal | No | Change ratio; 10% is represented as 0.10. |
| turnoverRatio | Decimal | No | Ratio fraction; 12% is 0.12. |
| amount | Decimal | No | Traded amount in CNY. |
| limitUpTime | str | No | Normalized limit up time field. |
| state | str | No | Source-defined state label. |
| isConsecutiveLimitUp | bool | No | Whether the source marks the row as consecutive limit-up. |
| consecutiveLimitUpCount | int \| None | Yes | Normalized consecutive limit up count field. |
| previousConsecutiveLimitUpCount | int \| None | Yes | Prior consecutive limit-up count reported by the source. |
| themeId | int \| None | Yes | Source theme identifier. |
| themeName | str \| None | Yes | Source theme name. |
| floatShares | int | No | Floating shares outstanding. |
| totalShares | int | No | Total shares outstanding. |
| marketCap | Decimal | No | Total market capitalization in CNY. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `aigupiao.series_limit_up`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.daily_replay(...)`

Return a daily replay of Jiyangongshe themes and stock observations for a requested date.

**Dataset:** `market.daily_replay`
**Schema version:** `1.0`
**Implemented Providers:** `jiuyangongshe.daily_replay`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.daily_replay(request: 'MarketDailyReplayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDailyReplayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketDailyReplayRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketDailyReplayRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| requestedDate | date | Yes | — | Date requested from the daily-replay source. |

#### Return value

The public method annotation is `FetchResult[MarketDailyReplayData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketDailyReplayData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| requestedDate | date | No | Date requested from the daily-replay source. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| themes | list[ReplayTheme] | No | Daily replay themes and their stock observations. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`ReplayStock`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |
| name | str | Yes | — | Provider-normalized display name. |
| limitUpTime | str \| None | No | None | Normalized limit up time field. |
| streakText | str \| None | No | None | Normalized streak text field. |
| price | Decimal \| None | No | None | Latest or observed price in CNY per share unless the dataset is an index series. |
| changeRatio | Decimal \| None | No | None | Change ratio; 10% is represented as 0.10. |
| day | int \| None | No | None | Normalized day field. |
| edition | int \| None | No | None | Normalized edition field. |
| expound | str \| None | No | None | Normalized expound field. |

**`ReplayTheme`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| themeName | str | Yes | — | Source theme name. |
| reason | str \| None | No | None | Normalized reason field. |
| stockCount | int | Yes | — | Normalized stock count field. |
| sourceThemeId | str \| None | No | None | Normalized source theme id field. |
| stocks | list[ReplayStock] | No | — | Stocks associated with the theme or replay row. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `jiuyangongshe.daily_replay`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

**Optional dependency:** install the source extra for playwright. From a source checkout use `python -m pip install ".[jygs]"`; after PyPI publication use the equivalent `finchx[jygs]` extra.

**Authentication:** the selected Provider requires an authenticated session. For the Jiyangongshe Provider, set `JYGS_SESSION` and install the `jygs` extra.

### `fx.market.dragon_tiger_detail(...)`

Return the buy/sell seat detail for one Dragon-Tiger list trade record.

**Dataset:** `market.dragon_tiger_detail`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.dragon_tiger`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.dragon_tiger_detail(request: 'MarketDragonTigerDetailRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerDetailData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerDetailRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketDragonTigerDetailRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | Yes | — | Source trading-date label; it is not FinchX capture time. |
| tradeId | str | Yes | — | Normalized trade id field. |

#### Return value

The public method annotation is `FetchResult[MarketDragonTigerDetailData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketDragonTigerDetailData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| name | str | No | Provider-normalized display name. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| tradeId | str | No | Normalized trade id field. |
| closePrice | Decimal | No | Price per share; currency is CNY. |
| changeRatio | Decimal | No | Change ratio; 10% is represented as 0.10. |
| amount | Decimal | No | Traded amount in CNY. |
| totalBuy | Decimal | No | Monetary amount in CNY. |
| totalSell | Decimal | No | Monetary amount in CNY. |
| totalNet | Decimal | No | Monetary amount in CNY. |
| explanation | str | No | Normalized explanation field. |
| commentKind | str \| None | Yes | Normalized comment kind field. |
| commentObjectId | str \| None | Yes | Normalized comment object id field. |
| buySeats | list[DragonTigerSeat] | No | Normalized buy seats field. |
| sellSeats | list[DragonTigerSeat] | No | Normalized sell seats field. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`DragonTigerSeat`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| rank | int | Yes | — | Derived from the source array order. |
| seatName | str | Yes | — | Normalized seat name field. |
| sourceSeatCode | str \| None | No | None | Normalized source seat code field. |
| hasDetails | bool \| None | No | None | Normalized has details field. |
| buyAmount | Decimal | Yes | — | Monetary amount in CNY. |
| sellAmount | Decimal | Yes | — | Monetary amount in CNY. |
| netAmount | Decimal | Yes | — | Monetary amount in CNY. |

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `aigupiao.dragon_tiger`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.dragon_tiger_list(...)`

Return the Aigupiao Dragon-Tiger list for one trading date.

**Dataset:** `market.dragon_tiger_list`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.dragon_tiger`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.dragon_tiger_list(request: 'MarketDragonTigerListRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketDragonTigerListData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketDragonTigerListRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketDragonTigerListRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Source trading-date label; it is not FinchX capture time. |

#### Return value

The public method annotation is `FetchResult[MarketDragonTigerListData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketDragonTigerListData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| name | str | No | Provider-normalized display name. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| tradeId | str | No | Normalized trade id field. |
| closePrice | Decimal | No | Price per share; currency is CNY. |
| changeRatio | Decimal | No | Change ratio; 10% is represented as 0.10. |
| amount | Decimal | No | Traded amount in CNY. |
| totalBuy | Decimal | No | Monetary amount in CNY. |
| totalNet | Decimal | No | Monetary amount in CNY. |
| explanation | str | No | Normalized explanation field. |
| threeDayFlag | str \| None | Yes | Normalized three day flag field. |
| themeId | int \| None | Yes | Source theme identifier. |
| themeName | str \| None | Yes | Source theme name. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `aigupiao.dragon_tiger`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.equity_intraday(...)`

Return intraday equity observations for one instrument and session.

**Dataset:** `market.equity_intraday`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.equity_intraday(request: 'EquityIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | EquityIntradayRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `EquityIntradayRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[EquityIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `EquityIntradayData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| time | str | No | Source market-local time for the observation, normally HH:MM. |
| price | str | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| volume | int | No | Traded volume in whole shares. |
| amount | str | No | Traded amount in CNY. |
| cumulativeVolume | int | No | Cumulative session volume in whole shares. |
| cumulativeAmount | str | No | Cumulative traded amount in CNY. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.intraday`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.equity_intraday_5d(...)`

Return the provider's five-day intraday equity series for one instrument.

**Dataset:** `market.equity_intraday_5d`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.equity_intraday_5d(request: 'EquityIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[EquityIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | EquityIntraday5dRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `EquityIntraday5dRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[EquityIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `EquityIntradayData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| time | str | No | Source market-local time for the observation, normally HH:MM. |
| price | str | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| volume | int | No | Traded volume in whole shares. |
| amount | str | No | Traded amount in CNY. |
| cumulativeVolume | int | No | Cumulative session volume in whole shares. |
| cumulativeAmount | str | No | Cumulative traded amount in CNY. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.intraday`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.fund_flow_daily(...)`

Return daily main-fund net inflow observations for one instrument.

**Dataset:** `market.fund_flow_daily`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.fund_flow`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.fund_flow_daily(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowDailyData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketFundFlowRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketFundFlowDailyData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketFundFlowDailyData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| mainNetInflow | Decimal | No | Main-fund net inflow in CNY. |
| close | Decimal | No | Closing price in CNY per share or index points, according to the instrument. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.fund_flow`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.fund_flow_intraday(...)`

Return cumulative intraday fund-flow observations for one instrument.

**Dataset:** `market.fund_flow_intraday`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.fund_flow`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.fund_flow_intraday(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketFundFlowRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketFundFlowIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketFundFlowIntradayData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| time | str | No | Source market-local time for the observation, normally HH:MM. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| cumulativeMainNetInflow | Decimal | No | Cumulative main-fund net inflow in CNY. |
| cumulativeRetailNetInflow | Decimal | No | Cumulative retail-fund net inflow in CNY. |
| cumulativeSuperLargeNetInflow | Decimal | No | Cumulative super-large-order net inflow in CNY. |
| cumulativeLargeNetInflow | Decimal | No | Cumulative large-order net inflow in CNY. |
| cumulativeMediumNetInflow | Decimal | No | Cumulative medium-order net inflow in CNY. |
| cumulativeSmallNetInflow | Decimal | No | Cumulative small-order net inflow in CNY. |
| cumulativeMainInflow | Decimal | No | Cumulative main-fund inflow in CNY. |
| cumulativeMainOutflow | Decimal | No | Cumulative main-fund outflow in CNY. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.fund_flow`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.fund_flow_snapshot(...)`

Return the current fund-flow snapshot and category-level inflow/outflow amounts.

**Dataset:** `market.fund_flow_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.fund_flow`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.fund_flow_snapshot(request: 'MarketFundFlowRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketFundFlowSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketFundFlowRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketFundFlowRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketFundFlowSnapshotData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketFundFlowSnapshotData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| mainNetInflow | Decimal | No | Main-fund net inflow in CNY. |
| mainInflow | Decimal | No | Main-fund inflow in CNY. |
| mainOutflow | Decimal | No | Main-fund outflow in CNY. |
| mainInflowRate | Decimal | No | Main-fund inflow ratio. |
| mainOutflowRate | Decimal | No | Main-fund outflow ratio. |
| retailInflow | Decimal | No | Retail-fund inflow in CNY. |
| retailOutflow | Decimal | No | Retail-fund outflow in CNY. |
| retailInflowRate | Decimal | No | Retail-fund inflow ratio. |
| retailOutflowRate | Decimal | No | Retail-fund outflow ratio. |
| superLargeNetInflow | Decimal | No | Super-large-order net inflow in CNY. |
| largeNetInflow | Decimal | No | Large-order net inflow in CNY. |
| mediumNetInflow | Decimal | No | Medium-order net inflow in CNY. |
| smallNetInflow | Decimal | No | Small-order net inflow in CNY. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.fund_flow`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.index_intraday(...)`

Return intraday index observations for one index instrument and session.

**Dataset:** `market.index_intraday`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.index_intraday(request: 'IndexIntradayRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | IndexIntradayRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `IndexIntradayRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[IndexIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `IndexIntradayData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| time | str | No | Source market-local time for the observation, normally HH:MM. |
| price | str | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| volume | int | No | Traded volume in whole shares. |
| amount | str | No | Traded amount in CNY. |
| cumulativeVolume | int | No | Cumulative session volume in whole shares. |
| cumulativeAmount | str | No | Cumulative traded amount in CNY. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.intraday`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.index_intraday_5d(...)`

Return the provider's five-day intraday index series for one index instrument.

**Dataset:** `market.index_intraday_5d`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.intraday`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.index_intraday_5d(request: 'IndexIntraday5dRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndexIntradayData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | IndexIntraday5dRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `IndexIntraday5dRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[IndexIntradayData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `IndexIntradayData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| time | str | No | Source market-local time for the observation, normally HH:MM. |
| price | str | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| volume | int | No | Traded volume in whole shares. |
| amount | str | No | Traded amount in CNY. |
| cumulativeVolume | int | No | Cumulative session volume in whole shares. |
| cumulativeAmount | str | No | Cumulative traded amount in CNY. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.intraday`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.industry_comparison(...)`

Compare one instrument with its industry aggregate and the broader market using the Tencent industry contract.

**Dataset:** `market.industry_comparison`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.industry`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.industry_comparison(request: 'MarketIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketIndustryComparisonData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketIndustryComparisonRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketIndustryComparisonRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketIndustryComparisonData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketIndustryComparisonData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| industry | IndustryIdentity | No | Source-provided industry label. |
| instrumentValues | IndustryComparisonValues | No | Instrument values used in the comparison. |
| industryRanks | IndustryComparisonRanks | No | Industry-relative ranks supplied by the source. |
| industryAggregate | IndustryAggregate | No | Industry aggregate values supplied by the source. |
| marketAggregate | MarketAggregate | No | Broad-market aggregate values supplied by the source. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`IndustryAggregate`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | Normalized price earnings field. |
| earningsPerShare | Decimal \| None | No | None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | No | None | Total market capitalization in CNY. |
| count | int \| None | No | None | Normalized count field. |

**`IndustryComparisonRanks`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarningsRank | int \| None | No | None | Normalized price earnings rank field. |
| earningsPerShareRank | int \| None | No | None | Normalized earnings per share rank field. |
| marketCapitalizationRank | int \| None | No | None | Normalized market capitalization rank field. |

**`IndustryComparisonValues`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | Normalized price earnings field. |
| earningsPerShare | Decimal \| None | No | None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | No | None | Total market capitalization in CNY. |

**`IndustryIdentity`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| providerNamespace | 'tencent_hypm' | Yes | — | Source-specific namespace retained as public identity. |
| providerIndustryId | str | Yes | — | Normalized provider industry id field. |
| name | str | Yes | — | Provider-normalized display name. |

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`MarketAggregate`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| priceEarnings | Decimal \| None | No | None | Normalized price earnings field. |
| earningsPerShare | Decimal \| None | No | None | Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here. |
| marketCapitalization | Decimal \| None | No | None | Total market capitalization in CNY. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.industry`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.instrument_sector_snapshot(...)`

Return Tencent area, industry and concept tags attached to one instrument.

**Dataset:** `market.instrument_sector_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.sector`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.instrument_sector_snapshot(request: 'MarketInstrumentSectorSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketInstrumentSectorSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketInstrumentSectorSnapshotRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketInstrumentSectorSnapshotRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketInstrumentSectorSnapshotData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketInstrumentSectorSnapshotData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| sectors | list[InstrumentSectorEntry] | No | Sector-tag entries attached to the instrument. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`InstrumentSectorEntry`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| sectorType | Literal['area', 'industry', 'concept'] | Yes | — | Sector tag type: area, industry or concept. |
| sectorName | str | Yes | — | Provider sector name. |
| providerNamespace | 'tencent_plate' | Yes | — | Source-specific namespace retained as public identity. |
| providerSectorId | str | Yes | — | Source-specific sector identifier. |
| level | int \| None | No | None | Order-book level number or sector hierarchy level, depending on the model. |
| tag | str \| None | No | None | Optional source tag. |
| changePct | Decimal \| None | No | None | Tencent zdf converted from percentage points to a ratio fraction. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.sector`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.stock_keyword(...)`

Return the source-provided hot keyword/concept snapshot for one equity; this is structured source ranking data, not NLP extraction.

**Dataset:** `market.stock_keyword`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.stockrank`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.stock_keyword(request: 'MarketStockKeywordRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStockKeywordData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketStockKeywordRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketStockKeywordRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketStockKeywordData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketStockKeywordData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| keywords | list[StockKeywordEntry] | No | Source-ranked hot keyword/concept entries. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`StockKeywordEntry`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| keywordName | str | Yes | — | Source-provided keyword or concept name. |
| providerNamespace | 'eastmoney_stockrank' | Yes | — | Source-specific namespace retained as public identity. |
| providerKeywordId | str | Yes | — | Source-scoped keyword/concept identifier. |
| hitCount | int | Yes | — | EastMoney source hit count; it is not an inferred NLP heat score. |
| calculatedAt | datetime | Yes | — | Source-reported time at which the keyword observation was calculated. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.stockrank`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

**Keyword semantics:** pass a complete `InstrumentId` (with exchange where required); this endpoint has no bare-code shortcut. The Provider supports SSE, SZSE, and BSE routing, and a legal empty BSE keyword list is still a successful result. This is source-ranked structured keyword/concept data: `keywordName`, `providerKeywordId`, `hitCount` and `calculatedAt` retain EastMoney meaning. It is not NLP keyword extraction and `hitCount` is not an inferred heat score.

### `fx.market.limit_down_pool(...)`

Return the EastMoney limit-down pool for one trading date.

**Dataset:** `market.limit_down_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.limit_down_pool`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.limit_down_pool(request: 'MarketLimitDownPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitDownPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketLimitDownPoolRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketLimitDownPoolRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Source trading-date label; it is not FinchX capture time. |

#### Return value

The public method annotation is `FetchResult[MarketLimitDownPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketLimitDownPoolData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| name | str | No | Provider-normalized display name. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| changeRate | Decimal | No | Change ratio; 10% is represented as 0.10. |
| amount | Decimal | No | Traded amount in CNY. |
| floatMarketCapitalization | Decimal | No | Floating market capitalization in CNY. |
| marketCapitalization | Decimal | No | Total market capitalization in CNY. |
| priceEarningsRatio | Decimal \| None | Yes | Source-reported dynamic price/earnings multiple. |
| turnoverRate | Decimal | No | Turnover ratio; percentage values are represented as fractions. |
| limitDownQueueAmount | Decimal \| None | Yes | Amount queued at the limit-down price in CNY. |
| lastLimitDownTime | str \| None | Yes | Last limit-down time in the source market-local time format. |
| boardTradedAmount | Decimal \| None | Yes | Amount traded at the limit-down price in CNY. |
| consecutiveLimitDownDays | int | No | Consecutive limit-down count reported by the source. |
| limitDownOpenCount | int | No | Number of limit-down openings recorded by the source. |
| industry | str | No | Source-provided industry label. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.push2ex.limit_down_pool`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.limit_up_pool(...)`

Return the EastMoney limit-up pool for one trading date.

**Dataset:** `market.limit_up_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.limit_up_pool`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.limit_up_pool(request: 'MarketLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketLimitUpPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketLimitUpPoolRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketLimitUpPoolRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Source trading-date label; it is not FinchX capture time. |

#### Return value

The public method annotation is `FetchResult[MarketLimitUpPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketLimitUpPoolData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| name | str | No | Provider-normalized display name. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| changeRate | Decimal | No | Change ratio; 10% is represented as 0.10. |
| amount | Decimal | No | Traded amount in CNY. |
| floatMarketCapitalization | Decimal | No | Floating market capitalization in CNY. |
| marketCapitalization | Decimal | No | Total market capitalization in CNY. |
| turnoverRate | Decimal | No | Turnover ratio; percentage values are represented as fractions. |
| consecutiveLimitUpDays | int | No | Consecutive limit-up count reported by the source. |
| firstLimitUpTime | str \| None | Yes | First limit-up time in the source market-local time format. |
| lastLimitUpTime | str \| None | Yes | Last limit-up time in the source market-local time format. |
| limitUpQueueAmount | Decimal \| None | Yes | Amount queued at the limit-up price in CNY. |
| limitUpBreakCount | int | No | Number of limit-up breaks observed by the source. |
| industry | str | No | Source-provided industry label. |
| limitUpStats | MarketLimitUpStats | No | Source-defined limit-up history statistics. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`MarketLimitUpStats`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | Normalized lookback days field. |
| limitUpCount | int | Yes | — | Number of limit-up instruments. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.push2ex.limit_up_pool`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.ohlcv(...)`

Return daily OHLCV bars for one instrument and date range.

**Dataset:** `market.klines`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.klines`, `sohu.finance.klines`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.ohlcv(instrument_id: 'InstrumentId | None' = None, start_date: 'date | None' = None, end_date: 'date | None' = None, adjustment: 'KlineAdjustment | None' = None, *, request: 'KlinesRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketKlineData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | Complete InstrumentId for the target instrument. |
| start_date | date \| None | No | None | Inclusive start date. |
| end_date | date \| None | No | None | Inclusive end date. |
| adjustment | KlineAdjustment \| None | No | None | Optional KlineAdjustment; the default is None unless the computed deviation capability selects QFQ internally. |
| request | KlinesRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `KlinesRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |
| startDate | date | Yes | — | Inclusive start date of the requested range or selected window. |
| endDate | date | Yes | — | Inclusive end date of the requested range or selected window. |
| adjustment | Literal['none', 'qfq', 'hfq', 'not_applicable'] \| None | No | None | Kline adjustment mode used for the bar series. |

#### Return value

The public method annotation is `FetchResult[MarketKlineData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketKlineData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| barDate | date | No | Trading date represented by the OHLCV bar. |
| open | Decimal | No | Session open price in CNY per share. |
| high | Decimal | No | Session high price in CNY per share. |
| low | Decimal | No | Session low price in CNY per share. |
| close | Decimal | No | Closing price in CNY per share or index points, according to the instrument. |
| volume | int | No | Traded volume in whole shares. |
| amount | Decimal \| None | Yes | Traded amount in CNY. |
| adjustment | Literal['none', 'qfq', 'hfq', 'not_applicable'] | No | Kline adjustment mode used for the bar series. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.klines`, `sohu.finance.klines`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.orderbook(...)`

Return the current bid and ask levels for one instrument.

**Dataset:** `market.orderbook`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.quote`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.orderbook(request: 'MarketOrderbookRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketOrderbookData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketOrderbookRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketOrderbookRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketOrderbookData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketOrderbookData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| bids | list[OrderbookLevel] | No | Bid-side order-book levels. |
| asks | list[OrderbookLevel] | No | Ask-side order-book levels. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`OrderbookLevel`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| level | int | Yes | — | Order-book level number or sector hierarchy level, depending on the model. |
| price | Decimal | Yes | — | Latest or observed price in CNY per share unless the dataset is an index series. |
| size | int | Yes | — | A non-negative whole number of shares. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.quote`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.quote(...)`

Return the selected A-share quote universe as one standardized record per instrument.

**Dataset:** `market.quote`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.market`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.quote(*, universe: 'InstrumentUniverse' = <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'>, request: 'MarketQuoteUniverseRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| universe | InstrumentUniverse | No | <InstrumentUniverse.CN_A_SHARE: 'cn_a_share'> | InstrumentUniverse selection; the public quote convenience method defaults to CN_A_SHARE. |
| request | MarketQuoteUniverseRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketQuoteUniverseRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| universe | Literal['cn_a_share'] | Yes | — | Instrument universe to query. |

#### Return value

The public method annotation is `FetchResult[MarketQuoteData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketQuoteData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| name | str \| None | Yes | Provider-normalized display name. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| priceChange | Decimal \| None | Yes | Signed absolute price change in CNY per share. |
| changeRate | Decimal \| None | Yes | Change ratio; 10% is represented as 0.10. |
| changeRate5d | Decimal \| None | Yes | Source-designated five-day price change ratio. |
| changeRate10d | Decimal \| None | Yes | Source-designated ten-day price change ratio. |
| changeRate20d | Decimal \| None | Yes | Source-designated twenty-day price change ratio. |
| changeRate60d | Decimal \| None | Yes | Source-designated sixty-day price change ratio. |
| changeRate52w | Decimal \| None | Yes | Source-designated 52-week price change ratio. |
| changeRateYtd | Decimal \| None | Yes | Year-to-date price change ratio. |
| amplitude | Decimal \| None | Yes | Intraday price amplitude as a ratio fraction. |
| volumeRatio | Decimal \| None | Yes | Source volume ratio as a dimensionless multiple; 2.35 means 2.35x. |
| volume | int \| None | Yes | Traded volume in whole shares. |
| amount | Decimal \| None | Yes | Traded amount in CNY. |
| turnoverRate | Decimal \| None | Yes | Turnover ratio; percentage values are represented as fractions. |
| marketCap | Decimal \| None | Yes | Total market capitalization in CNY. |
| floatMarketCap | Decimal \| None | Yes | Floating market capitalization in CNY. |
| peTtm | Decimal \| None | Yes | Trailing price/earnings multiple when supplied by the source. |
| mainNetInflow | Decimal \| None | Yes | Main-fund net inflow in CNY. |
| mainInflow | Decimal \| None | Yes | Main-fund inflow in CNY. |
| mainOutflow | Decimal \| None | Yes | Main-fund outflow in CNY. |
| mainInflow5d | Decimal \| None | Yes | Normalized main inflow5d field. |
| mainOutflow5d | Decimal \| None | Yes | Normalized main outflow5d field. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.market`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.quote_snapshot(...)`

Return one quote snapshot for one instrument, including source-reported timestamp.

**Dataset:** `market.quote_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.quote`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.quote_snapshot(request: 'MarketQuoteSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketQuoteSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketQuoteSnapshotRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketQuoteSnapshotRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[MarketQuoteSnapshotData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketQuoteSnapshotData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| previousClose | Decimal \| None | Yes | Previous-session close in CNY per share. |
| open | Decimal \| None | Yes | Session open price in CNY per share. |
| high | Decimal \| None | Yes | Session high price in CNY per share. |
| low | Decimal \| None | Yes | Session low price in CNY per share. |
| priceChange | Decimal \| None | Yes | Signed absolute price change in CNY per share. |
| changeRate | Decimal \| None | Yes | Change ratio; 10% is represented as 0.10. |
| volume | int \| None | Yes | Traded volume in whole shares. |
| amount | Decimal \| None | Yes | Traded amount in CNY. |
| sourceTimestamp | datetime | No | Source-reported quote timestamp; it is distinct from FinchX capturedAt. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.quote`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.ranking(...)`

Rank the selected quote universe by one supported market metric and direction.

**Dataset:** `market.ranking`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.market`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.market.ranking(request: 'MarketRankingRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketRankingData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketRankingRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketRankingRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| universe | Literal['cn_a_share'] | Yes | — | Instrument universe to query. |
| criterion | Literal['turnover', 'change_percent', 'volume'] | Yes | — | Ranking criterion used to select the metric. |
| direction | Literal['ascending', 'descending'] | Yes | — | Ranking direction. |
| limit | int \| None | Yes | — | Maximum number of ranking rows requested. |

#### Return value

The public method annotation is `FetchResult[MarketRankingData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketRankingData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| name | str \| None | Yes | Provider-normalized display name. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| priceChange | Decimal \| None | Yes | Signed absolute price change in CNY per share. |
| changeRate | Decimal \| None | Yes | Change ratio; 10% is represented as 0.10. |
| changeRate5d | Decimal \| None | Yes | Source-designated five-day price change ratio. |
| changeRate10d | Decimal \| None | Yes | Source-designated ten-day price change ratio. |
| changeRate20d | Decimal \| None | Yes | Source-designated twenty-day price change ratio. |
| changeRate60d | Decimal \| None | Yes | Source-designated sixty-day price change ratio. |
| changeRate52w | Decimal \| None | Yes | Source-designated 52-week price change ratio. |
| changeRateYtd | Decimal \| None | Yes | Year-to-date price change ratio. |
| amplitude | Decimal \| None | Yes | Intraday price amplitude as a ratio fraction. |
| volumeRatio | Decimal \| None | Yes | Source volume ratio as a dimensionless multiple; 2.35 means 2.35x. |
| volume | int \| None | Yes | Traded volume in whole shares. |
| amount | Decimal \| None | Yes | Traded amount in CNY. |
| turnoverRate | Decimal \| None | Yes | Turnover ratio; percentage values are represented as fractions. |
| marketCap | Decimal \| None | Yes | Total market capitalization in CNY. |
| floatMarketCap | Decimal \| None | Yes | Floating market capitalization in CNY. |
| peTtm | Decimal \| None | Yes | Trailing price/earnings multiple when supplied by the source. |
| mainNetInflow | Decimal \| None | Yes | Main-fund net inflow in CNY. |
| mainInflow | Decimal \| None | Yes | Main-fund inflow in CNY. |
| mainOutflow | Decimal \| None | Yes | Main-fund outflow in CNY. |
| mainInflow5d | Decimal \| None | Yes | Normalized main inflow5d field. |
| mainOutflow5d | Decimal \| None | Yes | Normalized main outflow5d field. |
| universe | Literal['cn_a_share'] | No | Instrument universe to query. |
| direction | Literal['ascending', 'descending'] | No | Ranking direction. |
| position | int | No | One-based position in the returned ranking. |
| metric | Any | No | Ranking metric used for the row. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`ChangePercentRankingMetric`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| criterion | 'change_percent' | Yes | — | Ranking criterion used to select the metric. |
| value | Decimal | Yes | — | A ratio fraction, not percentage points: 4.24% is 0.0424. |

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`TurnoverRankingMetric`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| criterion | 'turnover' | Yes | — | Ranking criterion used to select the metric. |
| value | Decimal | Yes | — | Monetary amount in CNY. |

**`VolumeRankingMetric`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| criterion | 'volume' | Yes | — | Ranking criterion used to select the metric. |
| value | int | Yes | — | A non-negative whole number of shares. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.market`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.market.sentiment(...)`

Return the Aigupiao market-sentiment snapshot and its source-defined ratios/counts.

**Dataset:** `market.sentiment_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `aigupiao.market_sentiment`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.sentiment(request: 'MarketSentimentRequest | None' = None, *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketSentimentData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketSentimentRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketSentimentRequest`. Its fields are:

This request model has no fields; call the endpoint without a request object or use the default request behavior.

#### Return value

The public method annotation is `FetchResult[MarketSentimentData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `MarketSentimentData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| marketTemperature | str | No | Aigupiao source-defined market temperature; not a physical temperature or universal ratio. |
| totalTurnover | Decimal \| None | Yes | Normalized total turnover field. |
| forecastedTurnover | Decimal \| None | Yes | Source forecast of turnover, not observed turnover. |
| turnoverChangeAmount | Decimal \| None | Yes | Source-reported turnover amount change versus the prior day. |
| blastBreakRatio | Decimal \| None | Yes | Source-defined broken-limit ratio; FinchX does not reconstruct its denominator. |
| previousLimitUpBreakChangeRatio | Decimal \| None | Yes | Source-defined previous broken-limit performance ratio. |
| stopTradingCount | int | No | Count of stopped-trading observations. |
| oneLimitUpCount | int | No | Count of one-limit-up observations. |
| twoLimitUpCount | int | No | Count of two-limit-up observations. |
| threeLimitUpCount | int | No | Count of three-limit-up observations. |
| highLimitUpCount | int | No | Count of high limit-up observations. |
| twoLimitUpPromotionRatio | Decimal \| None | Yes | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| threeLimitUpPromotionRatio | Decimal \| None | Yes | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| highLimitUpPromotionRatio | Decimal \| None | Yes | Source-defined promotion ratio; FinchX does not reproduce the denominator. |
| previousLimitUpThemeChangeRatio | Decimal \| None | Yes | Source-defined previous limit-up group performance ratio. |
| previousConsecutiveLimitUpThemeChangeRatio | Decimal \| None | Yes | Source-defined previous consecutive-limit-up group performance ratio. |



#### Example

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

#### Provider behavior and notes

The registry currently implements: `aigupiao.market_sentiment`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.strong_pool(...)`

Return the EastMoney strong-stock pool for one trading date.

**Dataset:** `market.strong_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.strong_pool`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.strong_pool(request: 'MarketStrongPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketStrongPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketStrongPoolRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketStrongPoolRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Source trading-date label; it is not FinchX capture time. |

#### Return value

The public method annotation is `FetchResult[MarketStrongPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketStrongPoolData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| name | str | No | Provider-normalized display name. |
| price | Decimal | No | Latest or observed price in CNY per share unless the dataset is an index series. |
| limitUpPrice | Decimal | No | Current-session limit-up price in CNY per share. |
| changeRate | Decimal | No | Change ratio; 10% is represented as 0.10. |
| amount | Decimal | No | Traded amount in CNY. |
| floatMarketCapitalization | Decimal | No | Floating market capitalization in CNY. |
| marketCapitalization | Decimal | No | Total market capitalization in CNY. |
| turnoverRate | Decimal | No | Turnover ratio; percentage values are represented as fractions. |
| isSixtyDayHigh | bool | No | Whether the source marks the instrument as a 60-day high. |
| selectionReason | Literal['sixty_day_high', 'recent_multiple_limit_ups', 'sixty_day_high_and_recent_multiple_limit_ups'] | No | Source-defined reason for strong-pool selection. |
| volumeRatio | Decimal | No | Source volume ratio as a dimensionless multiple; 2.35 means 2.35x. |
| industry | str | No | Source-provided industry label. |
| limitUpStats | MarketStrongPoolStats | No | Source-defined limit-up history statistics. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`MarketStrongPoolStats`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lookbackDays | int | Yes | — | Normalized lookback days field. |
| limitUpCount | int | Yes | — | Number of limit-up instruments. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.push2ex.strong_pool`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

### `fx.market.yesterday_limit_up_pool(...)`

Return today's observations for stocks that were in the prior-session limit-up pool.

**Dataset:** `market.yesterday_limit_up_pool`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.push2ex.yesterday_limit_up_pool`
**Routing semantics:** `single_source`. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

#### Method signature

```python
fx.market.yesterday_limit_up_pool(request: 'MarketYesterdayLimitUpPoolRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[MarketYesterdayLimitUpPoolData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | MarketYesterdayLimitUpPoolRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `MarketYesterdayLimitUpPoolRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| tradeDate | date | Yes | — | Source trading-date label; it is not FinchX capture time. |

#### Return value

The public method annotation is `FetchResult[MarketYesterdayLimitUpPoolData]`. FetchResult.data: tuple[StandardRecord, ...]. The `data` payload inside each StandardRecord is the `MarketYesterdayLimitUpPoolData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| tradeDate | date | No | Source trading-date label; it is not FinchX capture time. |
| name | str | No | Provider-normalized display name. |
| currentPrice | Decimal | No | Current-session price in CNY per share. |
| currentLimitUpPrice | Decimal | No | Current-session limit-up price in CNY per share. |
| currentChangeRate | Decimal | No | Current-session change ratio; 10% is represented as 0.10. |
| currentAmount | Decimal | No | Current-session traded amount in CNY. |
| floatMarketCapitalization | Decimal | No | Floating market capitalization in CNY. |
| marketCapitalization | Decimal | No | Total market capitalization in CNY. |
| currentTurnoverRate | Decimal | No | Current-session turnover ratio. |
| currentAmplitude | Decimal | No | Current-session price amplitude as a ratio fraction. |
| yesterdayFirstLimitUpTime | str \| None | Yes | Previous-session first limit-up time, market-local HH:MM:SS. |
| yesterdayConsecutiveLimitUpDays | int | No | Prior-session consecutive limit-up count. |
| industry | str | No | Source-provided industry label. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.push2ex.yesterday_limit_up_pool`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `single_source`; the listed Provider is the implemented source-specific contract.

## `fundamental`

Company profiles, financial summaries, revenue and industry comparisons.

### `fx.fundamental.company_profile(...)`

Return the normalized company profile for one instrument.

**Dataset:** `fundamental.company_profile`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.fundamental.company_profile(instrument_id: 'InstrumentId | None' = None, *, request: 'CompanyProfileRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CompanyProfileData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | Complete InstrumentId for the target instrument. |
| request | CompanyProfileRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `CompanyProfileRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[CompanyProfileData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `CompanyProfileData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| companyName | str \| None | Yes | Normalized company name field. |
| businessDescription | str \| None | Yes | Normalized business description field. |
| issuePrice | Decimal \| None | Yes | CNY per share. Tencent gsjj.jg is retained as the source candidate. |
| listingDate | date \| None | Yes | Normalized listing date field. |



#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.fundamental.financial_summary(...)`

Return normalized summary metrics across available reporting periods for one instrument.

**Dataset:** `fundamental.financial_summary`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.fundamental.financial_summary(request: 'FinancialSummaryRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialSummaryData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | FinancialSummaryRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `FinancialSummaryRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[FinancialSummaryData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `FinancialSummaryData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| periods | list[FinancialSummaryPeriod] | No | Reporting-period or holder-period rows. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`FinancialSummaryPeriod`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| periodEnd | date \| None | No | None | Optional financial-reporting period end date. |
| reportedPeriodLabel | str | Yes | — | Source reporting-period label. |
| periodType | Literal['annual', 'interim', 'unknown'] | Yes | — | Reporting-period classification. |
| eps | Decimal \| None | No | None | Earnings per share when available. |
| revenue | Decimal \| None | No | None | Revenue amount when available. |
| revenueGrowth | Decimal \| None | No | None | Revenue growth ratio. |
| netProfit | Decimal \| None | No | None | Net-profit amount when available. |
| netProfitGrowth | Decimal \| None | No | None | Net-profit growth ratio. |
| bookValuePerShare | Decimal \| None | No | None | Book value per share. |
| netAssets | Decimal \| None | No | None | Net assets amount. |
| goodwill | Decimal \| None | No | None | Goodwill amount. |
| goodwillToNetAssets | Decimal \| None | No | None | Goodwill-to-net-assets ratio. |
| roe | Decimal \| None | No | None | Return on equity ratio. |
| debtRatio | Decimal \| None | No | None | Debt ratio. |
| grossMargin | Decimal \| None | No | None | Gross-margin ratio. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.fundamental.industry_comparison(...)`

Return source-provided industry comparison metrics for one instrument.

**Dataset:** `fundamental.industry_comparison`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.fundamental.industry_comparison(request: 'FundamentalIndustryComparisonRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[IndustryComparisonData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | FundamentalIndustryComparisonRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `IndustryComparisonRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[IndustryComparisonData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `IndustryComparisonData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| industryName | str \| None | Yes | Normalized industry name field. |
| metrics | list[IndustryComparisonMetric] | No | Industry comparison metric rows. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`IndustryComparisonMetric`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| metric | Literal['eps', 'revenue', 'net_profit', 'book_value_per_share', 'roe', 'debt_ratio', 'gross_margin', 'revenue_growth', 'net_profit_growth', 'market_cap', 'pe', 'pb', 'dividend_yield'] | Yes | — | Ranking metric used for the row. |
| metricBasis | Literal['financial_period', 'market_snapshot'] | Yes | — | Allowed values: financial_period, market_snapshot. |
| companyValue | Decimal \| None | No | None | Normalized company value field. |
| industryAvg | Decimal \| None | No | None | Normalized industry avg field. |
| industryMax | Decimal \| None | No | None | Normalized industry max field. |
| industryMin | Decimal \| None | No | None | Normalized industry min field. |
| periodEnd | date \| None | No | None | Optional financial-reporting period end date. |
| reportedPeriodLabel | str | Yes | — | Source reporting-period label. |
| observationAt | datetime \| None | No | None | Normalized observation at field. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.fundamental.revenue_breakdown(...)`

Return the company's normalized revenue breakdown rows.

**Dataset:** `fundamental.revenue_breakdown`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.fundamental.revenue_breakdown(request: 'RevenueBreakdownRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RevenueBreakdownData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | RevenueBreakdownRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `RevenueBreakdownRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[RevenueBreakdownData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `RevenueBreakdownData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| breakdowns | list[RevenueBreakdownRow] | No | Revenue-breakdown rows. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`RevenueBreakdownRow`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| reportedPeriodLabel | str | Yes | — | Source reporting-period label. |
| periodEnd | date \| None | No | None | Optional financial-reporting period end date. |
| dimension | Literal['product', 'region', 'industry'] | Yes | — | Allowed values: product, region, industry. |
| itemName | str | Yes | — | Normalized item name field. |
| revenue | Decimal \| None | Yes | — | Revenue amount when available. |
| revenueShare | Decimal \| None | No | None | Normalized revenue share field. |
| currency | 'CNY' | Yes | — | Currency code. |
| sourceGroup | Literal['detail', 'others'] | Yes | — | Allowed values: detail, others. |
| isRollup | bool | Yes | — | Normalized is rollup field. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

## `financial`

Structured financial statements.

### `fx.financial.statements(...)`

Return normalized financial-statement line items for the requested statement type and periods.

**Dataset:** `financial.statement`
**Schema version:** `1.0`
**Implemented Providers:** `tonghuashun.financial`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.financial.statements(instrument_id: 'InstrumentId | None' = None, statement_type: 'StatementType | None' = None, *, period_end: 'date | None' = None, max_periods: 'int | None' = None, request: 'FinancialStatementRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FinancialStatementData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId \| None | No | None | Complete InstrumentId for the target instrument. |
| statement_type | StatementType \| None | No | None | StatementType selection. |
| period_end | date \| None | No | None | Optional reporting period end date. |
| max_periods | int \| None | No | None | Optional maximum number of financial periods. |
| request | FinancialStatementRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `FinancialStatementRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | Yes | — | Financial statement type. |
| periodEnd | date \| None | No | None | Optional financial-reporting period end date. |
| maxPeriods | int \| None | No | None | Normalized max periods field. |

#### Return value

The public method annotation is `FetchResult[FinancialStatementData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `FinancialStatementData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| statementType | Literal['balance_sheet', 'income_statement', 'cash_flow_statement'] | No | Financial statement type. |
| periods | list[FinancialStatementPeriod] | No | Reporting-period or holder-period rows. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`FinancialStatementLineItem`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| lineItemId | str | Yes | — | Normalized line item id field. |
| sourceName | str | Yes | — | Normalized source name field. |
| sourceUnit | str | Yes | — | Normalized source unit field. |
| sourceValue | str \| bool \| int \| Decimal \| None | Yes | — | Normalized source value field. |
| value | Decimal \| None | No | None | Normalized value field. |
| currency | Currency \| None | No | None | Currency code. |
| missingReason | Literal['null', 'false', 'empty_string', 'special_marker'] \| None | No | None | Normalized missing reason field. |

**`FinancialStatementPeriod`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| periodEnd | date | Yes | — | Optional financial-reporting period end date. |
| lineItems | list[FinancialStatementLineItem] | Yes | — | Financial statement line items. |

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tonghuashun.financial`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

## `news`

Individual-stock news search references.

### `fx.news.search(...)`

Search individual-stock news metadata and return serializable document references.

**Dataset:** `news.document`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.news.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, sort: 'str' = 'published_desc', request: 'NewsSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[NewsDocumentRef, ...]]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | No | None | InstrumentId or supported six-digit symbol text for document search. |
| page | int | No | 1 | One-based result page; default 1. |
| page_size | int | No | 20 | Page size; default 20 and capped by the request model. |
| max_results | int \| None | No | None | Optional result cap. |
| since | date \| datetime \| None | No | None | Optional inclusive lower publication-time bound. |
| until | date \| datetime \| None | No | None | Optional inclusive upper publication-time bound. |
| sort | str | No | 'published_desc' | Document ordering; the public default is published_desc. |
| request | NewsSearchRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `NewsSearchRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |
| page | int | No | 1 | One-based result page; default 1. |
| pageSize | int | No | 20 | Normalized page size field. |
| maxResults | int \| None | No | None | Normalized max results field. |
| since | date \| datetime \| None | No | None | Optional inclusive lower publication-time bound. |
| until | date \| datetime \| None | No | None | Optional inclusive upper publication-time bound. |
| sort | Literal['published_desc', 'published_asc'] | No | 'published_desc' | Document ordering; the public default is published_desc. |

#### Return value

The public method annotation is `FetchResult[NewsDocumentData]`. FetchResult.data: tuple[NewsDocumentRef, ...]. The `data` payload inside each StandardRecord is the `NewsDocumentData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| documentId | str | No | FinchX document identity. |
| sourceDocumentId | str | No | Source-side document identity. |
| title | str | No | Document title. |
| contentText | str \| None | Yes | Fetched document text when content is available. |
| summary | str \| None | Yes | Short source-provided summary when available. |
| publishedAt | datetime \| None | Yes | Publication timestamp supplied by the source. |
| sourceOccurrences | list[NewsSourceOccurrence] | No | Source-side occurrences retained during document normalization. |
| url | AnyUrl | No | Normalized url field. |
| originalUrl | AnyUrl \| None | Yes | Original document URL when supplied. |
| contentAvailable | bool | No | Whether document content is available in this result. |
| source | str \| None | Yes | Normalized source field. |
| relatedInstruments | list[InstrumentId] | No | Instruments related to the document. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |

**`NewsSourceOccurrence`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| providerId | str | Yes | — | Normalized provider id field. |
| sourceDocumentId | str | Yes | — | Source-side document identity. |
| sourceUrl | AnyUrl \| None | No | None | Direct source URL or source endpoint reference. |
| documentUrl | AnyUrl \| None | No | None | Normalized document url field. |
| publishedAt | datetime \| None | No | None | Publication timestamp supplied by the source. |
| capturedAt | datetime | Yes | — | Timezone-aware time when FinchX captured the source observation. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.news`, `eastmoney.market_news`, `aigupiao.market_news`, `baidu.finscope.market_news`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

## `disclosure`

Individual-stock disclosure search references.

### `fx.disclosure.search(...)`

Search individual-stock disclosures and return serializable notice references.

**Dataset:** `disclosure.document`
**Schema version:** `1.0`
**Implemented Providers:** `eastmoney.disclosure`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.disclosure.search(instrument: 'InstrumentId | str | None' = None, *, page: 'int' = 1, page_size: 'int' = 20, max_results: 'int | None' = None, since: 'date | datetime | None' = None, until: 'date | datetime | None' = None, categories: 'Sequence[str] | None' = None, sort: 'str' = 'published_desc', request: 'DisclosureSearchRequest | None' = None, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[tuple[DisclosureDocumentRef, ...]]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument | InstrumentId \| str \| None | No | None | InstrumentId or supported six-digit symbol text for document search. |
| page | int | No | 1 | One-based result page; default 1. |
| page_size | int | No | 20 | Page size; default 20 and capped by the request model. |
| max_results | int \| None | No | None | Optional result cap. |
| since | date \| datetime \| None | No | None | Optional inclusive lower publication-time bound. |
| until | date \| datetime \| None | No | None | Optional inclusive upper publication-time bound. |
| categories | Sequence[str] \| None | No | None | Optional disclosure category codes or names. |
| sort | str | No | 'published_desc' | Document ordering; the public default is published_desc. |
| request | DisclosureSearchRequest \| None | No | None | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `DisclosureSearchRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |
| page | int | No | 1 | One-based result page; default 1. |
| pageSize | int | No | 20 | Normalized page size field. |
| maxResults | int \| None | No | None | Normalized max results field. |
| since | date \| datetime \| None | No | None | Optional inclusive lower publication-time bound. |
| until | date \| datetime \| None | No | None | Optional inclusive upper publication-time bound. |
| sort | Literal['published_desc', 'published_asc'] | No | 'published_desc' | Document ordering; the public default is published_desc. |
| categories | list[str] \| None | No | None | Disclosure categories. |

#### Return value

The public method annotation is `FetchResult[DisclosureDocumentData]`. FetchResult.data: tuple[DisclosureDocumentRef, ...]. The `data` payload inside each StandardRecord is the `DisclosureDocumentData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| documentId | str | No | FinchX document identity. |
| sourceDocumentId | str | No | Source-side document identity. |
| title | str | No | Document title. |
| contentText | str \| None | Yes | Fetched document text when content is available. |
| noticeDate | date | No | Disclosure notice date. |
| publishedAt | datetime \| None | Yes | Publication timestamp supplied by the source. |
| sourceRecordedAt | datetime \| None | Yes | Source-side recorded timestamp, distinct from publication and capture time. |
| categories | list[DisclosureCategory] | No | Disclosure categories. |
| relatedInstruments | list[InstrumentId] | No | Instruments related to the document. |
| contentAvailable | bool | No | Whether document content is available in this result. |
| pdfAvailable | bool | No | Whether a PDF attachment is available. |
| originalDocumentUrl | AnyUrl | No | Original disclosure document URL. |
| attachments | list[DisclosureAttachment] | No | Disclosure attachments. |
| sourceType | str \| None | Yes | Source document type label. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`DisclosureAttachment`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| sequence | int \| None | No | None | Normalized sequence field. |
| size | int \| None | No | None | Normalized size field. |
| attachmentType | str \| None | No | None | Normalized attachment type field. |
| url | AnyUrl | Yes | — | Normalized url field. |
| webUrl | AnyUrl \| None | No | None | Normalized web url field. |

**`DisclosureCategory`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| name | str | Yes | — | Provider-normalized display name. |
| source | str | No | 'eastmoney' | Normalized source field. |

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `eastmoney.disclosure`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

## `ownership`

Capital structure and shareholder snapshots.

### `fx.ownership.capital_snapshot(...)`

Return total and floating share counts for one instrument.

**Dataset:** `ownership.capital_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.ownership.capital_snapshot(request: 'CapitalSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[CapitalSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | CapitalSnapshotRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `CapitalSnapshotRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[CapitalSnapshotData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `CapitalSnapshotData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| totalShares | int \| None | Yes | Total shares outstanding. |
| floatShares | int \| None | Yes | Floating shares outstanding. |



#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.ownership.float_holder(...)`

Return floating-holder rows for one instrument, optionally as of a requested date.

**Dataset:** `ownership.float_holder`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.float_holder`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.ownership.float_holder(request: 'FloatHolderRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[FloatHolderData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | FloatHolderRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `FloatHolderRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |
| asOf | datetime \| None | No | None | Optional cutoff date for the lookup or calculation. |

#### Return value

The public method annotation is `FetchResult[FloatHolderData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `FloatHolderData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| periods | list[FloatHolderPeriod] | No | Reporting-period or holder-period rows. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`FloatHolderPeriod`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| periodEnd | date | Yes | — | Optional financial-reporting period end date. |
| publishedAt | datetime | Yes | — | Publication timestamp supplied by the source. |
| rows | list[FloatHolderRow] | Yes | — | Normalized rows field. |

**`FloatHolderRow`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| rank | int | Yes | — | Derived from Tencent rows array order. |
| holderId | str \| None | No | None | Normalized holder id field. |
| holderName | str | Yes | — | Normalized holder name field. |
| shares | int | Yes | — | Share quantity. |
| holderType | str | Yes | — | Normalized holder type field. |
| floatShareRatio | Decimal \| None | No | None | Normalized float share ratio field. |
| previousShares | int \| None | No | None | Normalized previous shares field. |
| shareChange | int \| None | No | None | Signed share quantity change. |
| isNewTopFloatHolderEntry | bool \| None | No | None | Derived from bdms=1 after multi-stock adjacent-period validation. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.float_holder`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.ownership.holder_summary_snapshot(...)`

Return shareholder-count, concentration and average-holder metrics.

**Dataset:** `ownership.holder_summary_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.ownership.holder_summary_snapshot(request: 'HolderSummarySnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[HolderSummarySnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | HolderSummarySnapshotRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `HolderSummarySnapshotRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[HolderSummarySnapshotData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `HolderSummarySnapshotData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| shareholderCount | int \| None | Yes | Shareholder count. |
| averageSharesPerHolder | Decimal \| None | Yes | Average shares per holder. |
| shareholderCountChange | Decimal \| None | Yes | Shareholder-count change ratio, not an absolute count delta. |
| top10FloatHolderRatio | Decimal \| None | Yes | Top-ten floating-holder ratio. |
| top10HolderRatio | Decimal \| None | Yes | Top-ten holder ratio. |



#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

## `company`

Executive rosters and executive share-change observations.

### `fx.company.executive_share_change(...)`

Return normalized executive share-change events.

**Dataset:** `company.executive_share_change`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.company.executive_share_change(request: 'ExecutiveShareChangeRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveShareChangeData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | ExecutiveShareChangeRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `ExecutiveShareChangeRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[ExecutiveShareChangeData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `ExecutiveShareChangeData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| changes | list[ExecutiveShareChange] | No | Normalized changes field. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`ExecutiveShareChange`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| eventDate | date \| None | No | None | Executive share-change event date. |
| personName | str \| None | No | None | Executive or related person's name. |
| shareChange | int \| None | No | None | Signed share quantity change. |
| averagePrice | Decimal \| None | No | None | Average event price in CNY per share. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.company.executive_snapshot(...)`

Return the normalized executive roster and roles.

**Dataset:** `company.executive_snapshot`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.company.executive_snapshot(request: 'ExecutiveSnapshotRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[ExecutiveSnapshotData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | ExecutiveSnapshotRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `ExecutiveSnapshotRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[ExecutiveSnapshotData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `ExecutiveSnapshotData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| executives | list[ExecutiveEntry] | No | Executive entries. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`ExecutiveEntry`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| name | str | Yes | — | Provider-normalized display name. |
| roles | list[str] | Yes | — | Executive roles. |
| shares | int \| None | No | None | Share quantity. |
| compensation | Decimal \| None | No | None | Compensation amount when supplied. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

## `corporate_action`

Dividend and share-repurchase observations.

### `fx.corporate_action.dividend(...)`

Return normalized dividend events and their source fields.

**Dataset:** `corporate_action.dividend`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.corporate_action.dividend(request: 'DividendRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DividendData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | DividendRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `DividendRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[DividendData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `DividendData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| dividends | list[Dividend] | No | Dividend event rows. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`Dividend`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| fiscalYear | int \| None | No | None | Normalized fiscal year field. |
| announcementDate | date \| None | No | None | Normalized announcement date field. |
| stockDividendPer10 | Decimal \| None | No | None | Normalized stock dividend per10 field. |
| capitalizationPer10 | Decimal \| None | No | None | Normalized capitalization per10 field. |
| cashDividendPer10 | Decimal \| None | No | None | Normalized cash dividend per10 field. |
| rightsIssuePer10 | Decimal \| None | No | None | Normalized rights issue per10 field. |
| recordDate | date \| None | No | None | Corporate-action record date. |
| exDate | date \| None | No | None | Ex-dividend or ex-rights date. |
| description | str \| None | No | None | Normalized description field. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

### `fx.corporate_action.repurchase(...)`

Return normalized share-repurchase events and their source fields.

**Dataset:** `corporate_action.repurchase`
**Schema version:** `1.0`
**Implemented Providers:** `tencent.finance.qq.f10`
**Routing semantics:** `multi_provider`. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

#### Method signature

```python
fx.corporate_action.repurchase(request: 'RepurchaseRequest', *, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[RepurchaseData]'
```

#### Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| request | RepurchaseRequest | Yes | — | Typed request model. It cannot be combined with the convenience business parameters. |
| provider | str \| None | No | None | Strict Provider id pin. Only the named Provider is used. (keyword-only) |
| use_cache | bool \| None | No | None | Whether the configured cache may be used; None follows the configured CachePolicy. (keyword-only) |

The typed request model is `RepurchaseRequest`. Its fields are:

| Request field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrumentId | InstrumentId | Yes | — | Complete instrument identity: code, market, kind and optional exchange. |

#### Return value

The public method annotation is `FetchResult[RepurchaseData]`. FetchResult.data: StandardRecord. The `data` payload inside each StandardRecord is the `RepurchaseData` schema below.

#### Returned data fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| symbol | str | No | Provider-normalized symbol string for the instrument. |
| repurchases | list[Repurchase] | No | Repurchase event rows. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`Repurchase`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| repurchaseDate | date \| None | No | None | Repurchase date. |
| quantity | int \| None | No | None | Repurchased share quantity. |
| averagePrice | Decimal \| None | No | None | Average event price in CNY per share. |
| currency | Currency \| None | No | None | Currency code. |
| fundAmount | Decimal \| None | No | None | Funds used or announced for the event, in CNY. |
| market | str \| None | No | None | FinchX market identifier. |


#### Example

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

#### Provider behavior and notes

The registry currently implements: `tencent.finance.qq.f10`. Provider selection is controlled by runtime policy unless `provider=` is supplied. The registry marks this Dataset as `multi_provider`; the listed Provider set is the set implemented in this release.

## Computed capability: `market.deviation`

`market.deviation` is a deterministic local computation, not an external Provider. It reuses trading-calendar and Kline Dataset calls, sets `provider=None` on its returned `FetchResult`, and retains underlying provenance.

### `fx.market.deviation(...)`

Compute close-based 10-day and/or 30-day stock-versus-benchmark deviation from FinchX calendar and Kline inputs.

**Dataset identity:** `market.deviation` (computed, schema version `1.0`)
**External Provider:** none; the calculation uses the trading-calendar capability and Klines.
**Default Kline Provider:** `tencent.finance.qq.klines`.

#### Method signature

```python
fx.market.deviation(instrument_id: 'InstrumentId', *, windows: 'Sequence[int]' = (10, 30), as_of: 'date | None' = None, window_convention: 'DeviationWindowConvention' = <DeviationWindowConvention.MAX_DEVIATION_SCAN: 'max_deviation_scan'>, provider: 'str | None' = None, use_cache: 'bool | None' = None) -> 'FetchResult[DeviationData]'
```

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| instrument_id | InstrumentId | Yes | — | Complete SSE/SZSE A-share equity identity. |
| windows | Sequence[int] | No | (10, 30) | Only 10 and 30 are accepted; duplicates are rejected. |
| as_of | date \| None | No | None | Cutoff date; latest completed session on or before the cutoff is used. |
| window_convention | DeviationWindowConvention | No | max_deviation_scan | `strict_exchange_window` or `max_deviation_scan`. |
| provider | str \| None | No | None | Strict Kline Provider pin. The calendar lookup still uses the runtime's calendar Provider selection. |
| use_cache | bool \| None | No | None | Passed to underlying calendar and Kline fetches. |

#### Calculation rule

For each requested window, `deviation = stock_return - benchmark_return`, where each return is calculated from the selected baseline close/point to the completed end date. The default `max_deviation_scan` chooses the eligible start that maximizes this difference; `strict_exchange_window` uses the exchange-shaped start. The 10-day thresholds are `+1.00` and `-0.50`; the 30-day thresholds are `+2.00` and `-0.70`. These are ratios, so `0.03` means 3%. A positive deviation means the stock outperformed its benchmark over the selected window; a negative deviation means it underperformed.

Stock input uses Tencent QFQ daily Kline closes; the benchmark is an unadjusted index series. The result reports `priceBasis="qfq_stock__raw_index"`, `calculationMode="official_close"`, and rule version `cn-a-exchange-2026-07-06+finchx-v1`. It does not make network requests as a separate deviation Provider, but it does call the underlying calendar and Kline capabilities.

Supported benchmark mapping: SSE `60xxxx` → SSE A Share Index `000002`; SSE `68xxxx` → SSE STAR 50 Index `000688`; SZSE `00xxxx` → SZSE A Share Index `399107`; SZSE `30xxxx` → ChiNext Composite Index `399102`. BSE and unsupported code prefixes raise the existing invalid-request boundary.

#### Computed return fields

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| instrumentId | InstrumentId | No | Complete instrument identity: code, market, kind and optional exchange. |
| board | str | No | Resolved board classification used by the deviation benchmark mapping. |
| effectiveAsOf | date | No | Latest completed trading session actually used by the calculation. |
| calculationMode | 'official_close' | No | Frozen calculation mode; v1 is official_close. |
| priceBasis | 'qfq_stock__raw_index' | No | Frozen price basis; v1 is qfq_stock__raw_index. |
| ruleVersion | str | No | Version of the deviation calculation rule set. |
| windows | list[DeviationWindowData] | No | Computed observations for each requested window. |

#### Nested record types

The following object types are used by the fields above. Enum values are shown inline in the type column.

**`DeviationWindowData`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| windowDays | Literal[10, 30] | Yes | — | Selected deviation window: 10 or 30 trading days. |
| windowConvention | DeviationWindowConvention | Yes | — | Window interpretation: strict_exchange_window or max_deviation_scan. |
| tradingSessions | int | Yes | — | Number of aligned trading sessions used by the calculation. |
| startDate | date | Yes | — | Inclusive start date of the requested range or selected window. |
| baselineDate | date | Yes | — | Session immediately preceding the selected window start. |
| endDate | date | Yes | — | Inclusive end date of the requested range or selected window. |
| startPrice | Decimal | Yes | — | Stock price at the selected baseline date. |
| windowStartPrice | Decimal | Yes | — | Stock price at the selected window start date. |
| currentPrice | Decimal | Yes | — | Current-session price in CNY per share. |
| benchmarkInstrument | InstrumentId | Yes | — | Audited index instrument used as the benchmark. |
| benchmarkName | str | Yes | — | Human-readable benchmark name. |
| benchmarkStart | Decimal | Yes | — | Benchmark point at the selected baseline date. |
| benchmarkCurrent | Decimal | Yes | — | Benchmark point at the calculation end date. |
| stockReturn | Decimal | Yes | — | Cumulative stock return over the selected baseline and end date. |
| benchmarkReturn | Decimal | Yes | — | Cumulative benchmark return over the selected baseline and end date. |
| deviation | Decimal | Yes | — | Stock return minus benchmark return, represented as a ratio. |
| upperThreshold | Decimal | Yes | — | Upper deviation threshold for the selected window. |
| lowerThreshold | Decimal | Yes | — | Lower deviation threshold for the selected window. |
| remainingToUpper | Decimal | Yes | — | Upper threshold minus the computed deviation. |
| remainingToLower | Decimal | Yes | — | Computed deviation minus the lower threshold. |
| upperTriggerPrice | Decimal | Yes | — | Deterministic upper trigger-price estimate holding benchmark return constant. |
| lowerTriggerPrice | Decimal | Yes | — | Deterministic lower trigger-price estimate holding benchmark return constant. |
| remainingPricePctToUpper | Decimal | Yes | — | Price-space distance to the upper trigger estimate. |
| remainingPricePctToLower | Decimal | Yes | — | Price-space distance to the lower trigger estimate. |

**`InstrumentId`**
| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| code | str | Yes | — | Exchange-specific instrument code. |
| market | Market | Yes | — | FinchX market identifier. |
| kind | InstrumentKind | Yes | — | Instrument kind. |
| exchange | Exchange \| None | No | None | Exchange identity when required by the dataset. |


#### Example

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

A computed deviation is not an official exchange announcement, not an intraday estimate, and not a product exclusion or trigger state. Insufficient history, missing aligned closes, non-positive prices and unsupported identities produce an error rather than a zero value.

## Optional dependency reference

| Extra | Package | Capability |
| --- | --- | --- |
| `calendar` | `pandas_market_calendars` | Optional trading-calendar Provider `pandas_market_calendars`. |
| `jygs` | `playwright` | Authenticated `jiuyangongshe.daily_replay`; also requires `JYGS_SESSION`. |

From a source checkout, install with `python -m pip install ".[calendar]"` or `python -m pip install ".[jygs]"`. After PyPI publication, use `pip install "finchx[calendar]"` or `pip install "finchx[jygs]"`.

## Third-party data notice

FinchX provides software for accessing and normalizing third-party data sources. FinchX does not redistribute third-party market datasets. Users are responsible for complying with the terms and policies of the respective data providers.

## License

FinchX is licensed under Apache-2.0. Third-party data is not covered by the FinchX license.
