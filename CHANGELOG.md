# FinchX Release Notes

## 2.0.2 — 2026-10-02

FinchX 2.0.2 introduces scenario-based deviation results and improves source fidelity, pagination reporting, and safe diagnostics across market providers.

### Breaking changes

- **Deviation results:** `market.deviation` now treats `as_of` as the observation session and returns `pre_open`, `current`, and `next_session` rows for each requested 10- or 30-session window (six rows by default). The Dataset schema advances to `2.0`. Remove `window_convention` and the lower-threshold fields; migrate `startPrice` (`start_price`) to `stockBaselinePrice` (`stock_baseline_price`). `remainingPricePctToUpper` is removed, and `remainingToUpper` now means `upperTriggerPrice / currentPrice - 1`, including negative values.
- **Order book slots:** `market.orderbook` now preserves all five Tencent levels in source order, including explicit zeroes and missing values, and includes `sourceTimestamp`. Callers that assumed the levels were filtered and sorted by price should use the source level numbers instead. Quantities remain normalized from hands to whole shares.

### `market.deviation`

- Select the maximum-deviation interval and the minimum theoretical `upperTriggerPrice` independently. Select the minimum from unrounded candidates, round the returned price upward to CNY 0.01, and retain the selected unrounded price and candidate basis in metadata.
- Keep `pre_open` stock history on provider QFQ levels. For intraday rows, bridge QFQ history to the stock quote's `previousClose`; after the session, prefer each side's same-day daily bar and request a quote only for a side whose bar is missing. Quote timestamps and provenance are reported per side, and quote-backed terminals are not described as confirmed daily closes.
- Tencent equity `qfq` Klines use `qfqday` when available. If Tencent omits that key but returns a valid `day` array, FinchX returns the bars as unadjusted (`adjustment="none"`) with source-series metadata and a warning. A present empty `qfqday` returns no bars without falling back to `day`; a malformed array remains an error. Deviation results identify whether prices use `qfq_stock__raw_index` or `raw_stock__raw_index`.

### Provider and contract improvements

- Tencent Kline requests retry transient transport and HTTP failures within a bounded total time budget and expose safe per-attempt diagnostics.
- Tencent market listings, quotes, and rankings, plus EastMoney market pools, validate paginated totals and handle cross-page duplicates. When duplicate rows make a snapshot incomplete, results carry a warning and coverage metadata.
- `market.daily_replay` reports safe transport stages for Playwright startup, Chromium launch, navigation, and expected Jiuyangongshe API responses. It classifies access failures only from explicit HTTP 401/403 or source `errCode=1/110` responses; cookie values, query parameters, and raw browser exceptions are suppressed.
- Hotlist Decimal fields now publish JSON Schemas that match their string serialization.
- Updates the English and Simplified Chinese API references, examples, schemas, and regression coverage for the revised contracts.

## 2.0.1 — 2026-09-27

FinchX 2.0.1 expands verified index quote-snapshot coverage and adds EastMoney regulation datasets while retaining the package's established typed results and schema-versioning rules.

Dataset schema identifiers are independent of the Python package version. Existing Dataset schemas remain at `1.0`; the package version does not change their identities.

### Highlights

- Extends `market.quote_snapshot` to the seven verified SSE and SZSE index identities and documents the already-supported index use of `market.ohlcv`; index OHLCV uses `adjustment=None`.
- Adds EastMoney regulation watchlists, paged abnormal-event and prediction-history records, severe-prediction pools, and abnormal-count pools. Source values and unknown states remain available for audit.
- Extends `FetchResult.metadata` with pagination and collection-completeness details while preserving existing data and `to_dicts()` behavior.
- Makes `DeviationWindowConvention` and its two accepted string values explicit across the client, service, and pure calculator. The default calculation remains unchanged.
- Updates the English and Simplified Chinese API references and adds reproducible upstream-verification notes for the EastMoney mappings.

## 2.0.0 — 2026-09-25

FinchX 2.0.0 expands the typed client and revises several public API contracts. Review the migration notes before upgrading from 1.0.0.

Dataset schema identifiers are independent of the Python package version. Registered Dataset schemas remain at `1.0` in this release; the package version does not change their identities.

### Highlights

- Adds Tonghuashun stock, sector, convertible-bond, ETF, and content rankings, plus sector market data, forum replies, and article-detail retrieval.
- Expands news and disclosure retrieval with timezone-aware filters, bounded pagination, clearer partial-result warnings, and source provenance.
- Simplifies single-instrument inputs and documents the public client in English and Simplified Chinese.
- Validates release tags, source tests, built artifacts, and artifact identity before the trusted PyPI publishing job.

### Breaking changes and migration

- **News article URLs:** `NewsDocumentRef.sourceUrl` identifies the source search or list page. Use `documentUrl` (Python: `document_url`) for the article page. Update callers that treated `source_url` as the article URL.
- **Disclosure timestamps:** `sourceRecordedAt` is no longer a top-level business field. It is preserved in `provenance.adjustments`; use `publishedAt` for the displayed notice publication time.
- **Client inputs:** public client methods use their documented direct arguments. Migrate calls that passed legacy Request objects to the corresponding keyword arguments in the API reference.
- **Trading calendar:** `fx.reference.trading_calendar(...)` is fixed to the A-share market and no longer accepts a public `market` argument. Remove that argument from callers.
- **Article details:** `fx.articles.get(...)` accepts a supported article URL; content IDs and extra locator arguments are no longer accepted. Use the URL from a supported article reference, such as `fx.hotlist.content(content_type="article")` or `fx.articles.from_topic(...)`.

See the [English API reference](docs/DATA_API_REFERENCE.md) and [Simplified Chinese API reference](docs/DATA_API_REFERENCE.zh-CN.md) for current signatures and return fields.

## 1.0.0 — 2026-09-21

Initial PyPI release.
