# FinchX Public API

The v1.0 public Client/API surface includes stock-keyword and computed-deviation
capabilities. The package version is `1.0.0`; it is a local release candidate
and is not published to PyPI. The canonical
user entry is:

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()
```

`FinchX()` is construction-only: it does not access the network, create a
default SQLite file, start a browser or require optional dependencies.

## Frozen Client inventory

The public Client has 9 namespaces and 42 explicit endpoint methods:

- `reference`: `instrument`, `trading_calendar`
- `market`: `breadth`, `broken_limit_pool`, `consecutive_limit_up`,
  `daily_replay`, `dragon_tiger_detail`, `dragon_tiger_list`,
  `equity_intraday`, `equity_intraday_5d`, `fund_flow_daily`,
  `fund_flow_intraday`, `fund_flow_snapshot`, `index_intraday`,
  `index_intraday_5d`, `industry_comparison`, `instrument_sector_snapshot`,
  `stock_keyword`,
  `limit_down_pool`, `limit_up_pool`, `ohlcv`, `orderbook`, `quote`,
  `quote_snapshot`, `ranking`, `sentiment`, `strong_pool`,
  `yesterday_limit_up_pool`
- `fundamental`: `company_profile`, `financial_summary`,
  `industry_comparison`, `revenue_breakdown`
- `financial`: `statements`
- `news`: `search`
- `disclosure`: `search`
- `ownership`: `capital_snapshot`, `float_holder`,
  `holder_summary_snapshot`
- `company`: `executive_share_change`, `executive_snapshot`
- `corporate_action`: `dividend`, `repurchase`

The detailed Dataset, request-model and return-type table is in
[`client-api-inventory.md`](client-api-inventory.md). Its code source of truth
is `finchx.client.CLIENT_ENDPOINTS`; methods remain explicitly written and are
not generated from the table.

## Computed deviation capability

In addition to the 42 explicit Dataset endpoints, the market namespace exposes
the computed Foundation capability:

```python
result = fx.market.deviation(
    instrument_id,
    windows=(10, 30),
    window_convention="max_deviation_scan",
)
```

It returns `FetchResult[DeviationData]`, uses the audited exchange benchmark,
calendar and Kline capabilities, and does not register a fake
`DeviationProvider`. Because it is computed rather than Provider-backed, it is
outside `CLIENT_ENDPOINTS` and does not change the 42-Dataset inventory. The
frozen calculation and support boundary are in
[`a-share-deviation-rulebook.md`](a-share-deviation-rulebook.md).

## Return contract and runtime semantics

Every public Client endpoint returns the existing `FetchResult` envelope. The
most commonly used fields are `data`, `dataset`, `provider`, `captured_at`,
`warnings`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`.

`provider=` is a strict Provider pin: only the named Provider is used, and a
failure does not silently fall back to another Provider. Without an explicit
Provider, the lower-level Collector may apply its bounded retry/fallback policy;
the Client does not promise a particular Provider order. `use_cache=` is passed
through to the Collector.

## API layers

Primary API:

- `FinchX` and its nine namespace objects are the supported first-use surface.

Advanced API:

- `Collector`, `FetchResult`, `FetchAttempt`, `RoutingPolicy` and `CachePolicy`
  are available from `finchx.collector` / `finchx.collectors`.
- `Storage`, `MemoryStorage`, `SQLiteStorage`, `Cache` and related storage
  contracts are available from `finchx.storage`.
- `HealthMonitor`, `QualityMonitor` and `ObservabilityMonitor` are process-local
  diagnostic APIs, not additional Client namespaces or Datasets.

Internal implementation:

- Provider adapters, routing handlers, namespace implementation classes,
  private helpers and names beginning with `_` are not the canonical user API.
  They may change without being a Client compatibility guarantee.
- Existing explicit lower-level exports are retained for advanced callers; they
  are not promoted to the primary API by this freeze.

## Optional dependencies and public errors

The base install is sufficient for `import finchx` and `FinchX()`. Install an
extra only for the related capability from a FinchX source checkout:

```bash
python -m pip install ".[calendar]"
python -m pip install ".[jygs]"
```

`calendar` provides the `pandas_market_calendars` trading-calendar fallback.
`jygs` provides the authenticated Jiyangongshe browser Provider. If the
dependency is absent, the base package remains importable and the selected
capability raises `MissingOptionalDependency`, including the missing dependency
name. The package version is `1.0.0`, but it has not been published to PyPI.

Common public error categories retain their existing meanings:

- `AuthenticationError`: the source requires credentials or an authenticated
  session.
- `SchemaDrift`: the external response no longer matches the expected source
  structure.
- `InvalidRequest`: the request arguments or Dataset semantics are invalid.
- `MissingOptionalDependency`: the selected capability needs an uninstalled
  optional dependency.

## Compatibility rule

The current v1.0 public Client surface, endpoint names, principal signatures
and `FetchResult` return contract are compatibility-protected. A future
breaking public API change requires an explicit versioning decision. This
document does not define a broader SemVer governance process.

The final freeze tests also protect the source-derived registry inventory:
42 registered Datasets, 36 public Provider exports, 29 executable Provider
specifications and 47 registered Dataset–Provider pairs. The computed
`market.deviation` capability remains deliberately outside that Provider-backed
inventory.
