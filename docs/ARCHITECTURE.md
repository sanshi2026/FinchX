# FinchX Architecture

FinchX is a typed boundary between application code and registered third-party
A-share data providers. The public design keeps provider-specific transport and
field names behind Dataset contracts, while preserving enough source identity
and provenance for callers to understand where a result came from.

## Runtime flow

```text
FinchX client namespace
        |
        v
Collector: request validation, routing, retry/fallback, cache boundary
        |
        v
Provider Registry -> provider adapter -> source transport and parsing
        |
        v
Dataset normalizer -> StandardRecord / typed document reference
        |
        v
FetchResult with data, source identity, capture time and attempts
```

Constructing `FinchX()` is in-memory only. It does not select a Provider, make a
network request, create a cache, or create a local database file.

## Public boundary

The Client exposes fourteen namespaces: `hotlist`, `reference`, `market`,
`fundamental`, `financial`, `iwencai`, `news`, `disclosure`, `market_news`,
`articles`, `forum`, `ownership`, `company`, and `corporate_action`. The current
surface contains 54 Provider-backed Dataset
methods. `market.deviation` is a separate computed capability that combines
calendar and Kline results locally.

The `iwencai` namespace has three source-specific operations: `select` calls
the web screener and requires a caller-supplied Cookie header; `search` calls
the SkillHub semantic-search OpenAPI and requires an API key plus X-Claw
headers; `report_detail` uses the report page's JSON detail endpoint and
requires the caller's Cookie header. Credentials are request data, not global
Client configuration. Each operation returns standardized `StandardRecord`
values; query-specific columns and report metadata remain under `extraFields`
unless FinchX defines a stable field for them.

Each Provider-backed operation has a Dataset definition containing:

- a stable Dataset name;
- a Dataset schema version (currently `1.0` for each registered Dataset);
- a normalized input contract; and
- a typed normalized payload model.

Definitions describe contracts only. They do not contain URLs, headers,
credentials, retry settings, cache settings, or other transport configuration.

## Identity and symbols

Internally FinchX keeps a normalized identity containing `code`, `market`,
`kind`, and an optional `exchange`. Public Client methods accept plain code
strings and provide the missing context from endpoint semantics: for example,
`000001` is a SZSE equity in a stock endpoint and the SSE index in an index
endpoint. Symbol normalization remains internal to the request pipeline.

`Market.CN_A` is the current market value. `Exchange.SSE`, `Exchange.SZSE`, and
`Exchange.BSE` identify venues; `InstrumentKind` distinguishes equities,
indices, and ETFs.

## Records and provenance

Most Provider-backed results contain `StandardRecord` envelopes. The envelope
separates:

- `status`, which describes acquisition or value status;
- `quality`, which records observations such as stale or partial data;
- `source`, which identifies the direct Provider and optional source record;
- `provenance`, which describes normalization or derivation; and
- market/business timestamps such as `eventAt`, `publishedAt`, `updatedAt`,
  `capturedAt`, and `asOf`.

`capturedAt` is the FinchX acquisition time and is not a substitute for a
source publication time or a market trading-date label. Prices, amounts and
ratios use exact decimal values in Python and canonical decimal strings in JSON
schemas; share counts remain integers.

News and disclosure searches return typed document references. The computed
deviation capability returns a typed `DeviationData` payload directly inside
`FetchResult`, while retaining the underlying source provenance.

## Provider routing

The registry maps Dataset contracts to implemented Provider identities. The
configured runtime policy controls retry and fallback behavior. The registry
inventory describes implemented Providers, not an upstream service-level
guarantee or a permanent routing order.

Provider adapters own source-specific requests, response parsing, and source
validation. Normalizers convert the adapter result into the public Dataset
payload and `StandardRecord`; provider-native fields do not become public fields
unless they are part of a documented Dataset contract.

## Schemas and packaging

Versioned JSON Schemas live under the packaged `finchx.schemas/v1/` resources.
Installed code should load them through the package resource API rather than
assuming a repository-root path. The wheel includes these schema resources and
the public tests validate their presence and representative serialization.

## Computed deviation

`market.deviation` uses the trading-calendar and Kline capabilities as inputs.
It is deterministic, single-instrument, and stateless; it does not create a
Provider, scan the market, persist regulatory events, or infer an exchange
announcement. The bilingual API reference documents its supported equities,
board benchmarks, formulas, thresholds, and price basis.
