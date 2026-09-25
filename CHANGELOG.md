# FinchX Release Notes

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
