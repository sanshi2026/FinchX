# Symbols and Dataset Definitions v1

## Symbol identity

FinchX canonical symbols use four colon-separated fields:

    market:exchange:kind:code

For example, **cn_a:sse:equity:600519** identifies a China A-share equity at SSE. A dash in the exchange field means that the venue is intentionally unspecified, as in **cn_a:-:index:000001**. The code field uses UTF-8 percent-encoding, so punctuation and whitespace already accepted by InstrumentId round-trip without changing the identity. Ordinary numeric codes remain readable.

Use parse_symbol for canonical text, format_symbol for the canonical form of an existing InstrumentId, and normalize_symbol for either canonical text or a raw code with explicit context. Tokens for market, exchange, and kind are case-insensitive; formatting emits lowercase tokens. The code is preserved exactly, including letter case.

A raw code by itself is ambiguous. normalize_symbol("000001") and normalize_symbol("600519") raise AmbiguousSymbolError. Raw-code normalization requires market and kind; exchange can be supplied when known and otherwise remains None. No code-range rules infer an exchange or instrument kind.

Input is not trimmed. Unencoded whitespace in input is rejected. Provider-specific spellings such as sh600519, 600519.SH, SH.600519, and 1.600519 are not FinchX canonical symbols and are not aliases. Explicit context applies only to the code string supplied by the caller.

Normalization validates identity shape and the declared Market, Exchange, and InstrumentKind tokens. The current Market is cn_a; its declared venues are sse, szse, and bse. It does not establish whether an instrument exists. Future Instrument data is responsible for existence and lifecycle facts.

The three public errors are SymbolError, AmbiguousSymbolError, and InvalidSymbolError.

## Dataset identity and definition

DatasetId is a validated string shared by Dataset definitions and StandardRecord.dataset. It is intentionally open rather than an enum. Names start with a lowercase letter, use lowercase letters and digits within a segment, and separate segments with a dot or underscore. Underscores may also continue a segment. Empty segments, uppercase letters, whitespace, and slashes are rejected. Examples include instrument, trading_calendar, market.quote, market.klines, and future name fundamental.balance_sheet.

DatasetDefinition[RequestT, DataT] is a frozen declaration with a Dataset name, a non-empty schema version label, and Python classes for the request and dataset data payload. The data type describes the dataset payload; StandardRecord remains the shared outer record envelope. Dataset-specific request and data classes will be defined by their own datasets.

Definitions do not fetch or execute anything. They carry no provider, URL, storage, cache, retry, authentication, or transport settings. There is no global registry: a validated value object and a typed declaration are enough for the current boundary, and callers can import definitions directly without dynamic discovery.

The existing StandardRecord.schemaVersion contract remains 1.0. Dataset definitions carry their dataset schema version as an opaque non-empty string; this Stage does not define schema migration or version negotiation.
