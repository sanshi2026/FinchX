# 2.0.3 compatibility and upgrade checks

2.0.3 structural changes preserve the 2.0.2 public call contracts,
Dataset identifiers/schema versions, model paths and business JSON payloads.
The earnings-forecast draft remains excluded.

| Surface | 2.0.3 behavior |
| --- | --- |
| `from finchx import FinchX` and `finchx.client` namespace imports | Same names, parameters and return contracts; implementation moved to `api/`. |
| `finchx.collector`, `finchx.collectors`, `finchx.collectors.core` | Historical public classes re-exported; class identities keep the old module names. |
| `finchx.datasets.TradingCalendarService`, old service module | Same class as `finchx.query.trading_calendar.TradingCalendarService`; export resolved lazily to avoid a Dataset/Collector import cycle. |
| Dataset and Pydantic classes | Original module paths and schemas; historical storage remains readable. |
| Retry/fallback/cache/provenance/raw transport | Existing behavior retained; normalizer adds the financial-summary audit adjustment documented separately. |
| `IwencaiProvider` extension methods | Original private normalization/helpers and dynamic-column behavior retained for the existing StockX adapter. |
| `providers/tencent_klines.py` | Path and content retained, including StockX's special qfqday repair fingerprint. |
| Warnings | No new informational warnings; StockX screening currently rejects any warning. |

StockX's market, screening and deviation calls do not need caller-code changes
for this restructuring. Its optional
financial-summary provenance consumption can use guarded access; existing calls
and business rows are unchanged. The private Wencai inheritance seam is preserved
for compatibility, not a new public extension API guarantee.

The F10 financial-summary route returns a single `StandardRecord`, as it did in
2.0.2. The legacy Client annotation describes a record tuple; this preparation
preserves that annotation as part of the frozen surface rather than changing the
runtime shape. Use `result.to_dicts()` for a uniform list of business dictionaries.

StockX market, screening and deviation integration was checked against a frozen
source snapshot. Research uses a separate installed-package execution path and
tool/field allow-lists. Existing tool and field contracts were checked offline;
model-driven Research was not accepted end to end. Its ongoing version-policy and
model changes belong to StockX and are outside this FinchX release.

Before publication, verify:

- frozen public methods/defaults/types, registry identities and JSON schemas;
- old import paths, source input validation and deviation output cases;
- the stored 2.0.2 JSON/SQLite samples, typed scalars and zero/null distinctions;
- provider subclassing, dynamic field preservation and unchanged warning behavior;
- routing, retries, fallback and cache metadata round-trips with offline fixtures;
- deterministic bilingual API generation, complete offline regression and wheel/sdist inventory;
- construction/import with network access blocked and no filesystem outputs;
- a fresh isolated installation using the built wheel, without upgrading StockX.

Offline/mocked compatibility checks do not establish live upstream availability,
authorization, data completeness, or execution of StockX's ongoing Research work.
Real DeepSeek/model calls are outside this tool-only integration; it is not a
Research end-to-end acceptance test.

## Isolated integration evidence (2026-10-04)

The fixed 2.0.3 wheel and sdist were installed only in temporary environments.
All 206 package files match both distributions and the reviewed working tree;
66 bundled schemas are present. The wheel SHA-256 is
`f88709a56824809b399d3e88bf62339fc5692da650f2dc2fd14018d8b7f6d946`;
the sdist SHA-256 is
`20b04925adcfe7b0261410196ccda54066aaa3db9b019df5dcaf039b3cacb568`.
Both pass `twine check` and isolated import/construction/schema smoke tests.
These hashes identify the historical integration inputs; final release artifact
hashes are recorded by the release verification, since packaging metadata and
build timestamps may differ.

| Installed-wheel regression environment | Result |
| --- | --- |
| Python 3.10.20 / Pydantic 2.13.5 | 732 passed |
| Python 3.12.14 / Pydantic 2.13.5 | 732 passed |
| Python 3.12.14 / Pydantic 2.9.0 (dependency floor) | 732 passed |
| Python 3.13.2 / Pydantic 2.11.9 | 732 passed |

Python 3.11 and Linux/GitHub Actions were not executed locally. Calendar tests
on the borrowed Python 3.12 environment emit 24 existing third-party deprecation
warnings. Schema regression comparisons normalize known upstream Decimal-pattern
emission and equivalent JSON Schema defaults/singleton enum spelling; application
constraints and packaged schemas remain intact. The 168 model schemas from
released 2.0.2 and this wheel are identical when generated under the same
Pydantic 2.9.0 environment.

A frozen snapshot of actual StockX source was copied to a temporary directory, with no credentials,
production storage or configuration. Subsequent independent changes to StockX
Research/ModelGateway are outside this snapshot. Seventy existing screening/deviation/auction
tests, 153 dashboard-related backend tests, ten additional actual-adapter checks,
and 36 frontend tests pass. The frontend typecheck and production build pass.
Date-stamped synthetic fixtures for 2026-09-28 and 2026-09-29 exercise actual
FinchX provider normalization/Collector calls, StockX market/auction adapters,
collection services, isolated snapshot storage, dashboard API reads and scenario
mapping. Collector transport inputs are fixtures; this is not live market coverage
or an acceptance test of the production subprocess/collector scheduler.

Eight Chromium checks against the isolated production-built StockX frontend
verify ranking and all five pool tables, auction ranking, current/next-session
deviation rendering, the visible refresh button and historical date switching.
API reads preserve archived JSON bytes; missing/uncovered datasets remain visibly
partial or unavailable. No real environment was upgraded, no production data was
written, and the temporary server was stopped. This validates UI rendering and
local date handling in addition to callable APIs.

A separate bounded live smoke made six anonymous public Tencent requests, all
HTTP 200: two indices through StockX's market adapter, a 300308 orderbook, QFQ
history, financial summary and equity intraday data. Authenticated Iwencai was
not called; dynamic fields/warnings were tested offline. Live auction-time,
full-market ranking/pool completeness, and model-driven Research remain untested.
The historical integration snapshot rejected the new wheel before HTTP access;
that observation is preserved in the separate acceptance evidence, and does not
establish the outcome of StockX's subsequent independent changes. Zero model calls
were made; Research end-to-end acceptance remains untested.
