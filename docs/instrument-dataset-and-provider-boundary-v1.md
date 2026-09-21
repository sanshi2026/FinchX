# Instrument Dataset and Provider Boundary v1

## Instrument Dataset

`INSTRUMENT_DATASET` declares dataset id `instrument`, request type
`InstrumentRequest`, payload type `InstrumentData`, and dataset schema version
`1.0`. The shared `StandardRecord.schemaVersion` remains the base envelope
version `1.0`; the dataset payload has its own JSON Schema at
`finchx.schemas/v1/instrument.schema.json`.

`InstrumentRequest` accepts one complete `InstrumentId`. A bare code such as
`600519` is not a request identity. Callers must use the existing
`normalize_symbol` API with explicit market and kind, or provide a canonical
symbol; the dataset does not infer exchange, market, or instrument kind.

The minimal provider-neutral payload is `InstrumentData(instrumentId, name)`.
Its identity uses the existing `InstrumentId`; the name is required and must
contain a non-whitespace character. The StandardRecord `entityId` and payload
`instrumentId` carry the same identity. No provider-specific attributes are
part of the public contract.

## Provider boundary

`InstrumentProvider` is a dataset-specific synchronous Protocol. It exposes a
`Source` and fetches one explicit `InstrumentRequest`. A provider adapter owns
source-specific requests, parsing, and validation. It converts its native row
shape into a small internal typed handoff; the dataset normalizer reuses
`normalize_symbol`, verifies the full requested identity, and creates the
`InstrumentData` and `StandardRecord` contracts. Provider-native fields do not
cross into public payloads or public package exports.

Each standardized record retains dataset id, schema version, `InstrumentId`,
provider `Source` and source record id, live status, quality, and a
`standardized` provenance entry with normalizer version. The direct source is
not repeated in provenance references.

A successful exact lookup with no rows returns an empty sequence (and
normalizes to an empty tuple). A provider retrieval or source-parse failure
raises `ProviderError`, which carries the `Source` and a reason; it is never converted
to empty data. An unknown market, exchange, or kind token fails through
the existing strict symbol normalization rules.

## Instrument universe listing operation

`InstrumentUniverseRequest` selects the source-neutral `CN_A_SHARE`
universe. `InstrumentListingProvider.list_instruments()` is a separate capability; it does not
change `InstrumentRequest` or `InstrumentProvider.fetch_instrument()`.

Listing normalizes each row independently into a `StandardRecord` with dataset
id `instrument`, schema version `1.0`, and the existing `InstrumentData`
payload schema. A successful empty listing returns an empty tuple. Duplicate
identities and rows outside the requested A-share-equity universe fail
validation.

The listing operation does not create another `DatasetDefinition` for
`instrument@1.0`. FinchX Dataset identity is the name and schema-version pair;
operation request types do not create new identities. The existing
`INSTRUMENT_DATASET` remains the single-instrument definition.

The contract is covered by offline fake-provider tests. There is no real network
provider, provider or dataset registry, routing, fallback, cache, storage,
retry framework, or authentication behavior.
