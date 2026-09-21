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

The Client exposes nine namespaces: `reference`, `market`, `fundamental`,
`financial`, `news`, `disclosure`, `ownership`, `company`, and
`corporate_action`. The frozen surface contains 42 Provider-backed Dataset
methods. `market.deviation` is a separate computed capability that combines
calendar and Kline results locally.

Each Provider-backed operation has a Dataset definition containing:

- a stable Dataset name;
- a schema version (`1.0` in this release);
- a typed request model; and
- a typed normalized payload model.

Definitions describe contracts only. They do not contain URLs, headers,
credentials, retry settings, cache settings, or other transport configuration.

## Identity and symbols

`InstrumentId` is explicit: `code`, `market`, `kind`, and an optional
`exchange`. FinchX does not infer an exchange or instrument kind from a bare
stock code. Symbol helpers can normalize a value only when the caller supplies
enough context to make the identity unambiguous.

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

The registry maps Dataset contracts to implemented Provider identities. A
`provider=` argument is a strict pin: a failure of that Provider is not silently
redirected to another one. Without a pin, the configured runtime policy controls
retry and fallback behavior. The registry inventory describes implemented
Providers, not an upstream service-level guarantee or a permanent routing
order.

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
announcement. See [DEVIATION.md](DEVIATION.md) for the calculation boundary.
