# FinchX

FinchX is an independent Python package for A-share market data, intended for open-source development.

## Status

FinchX version 1.0.0 is a local public release candidate. The v1 Client/API
surface is frozen and has not been published to PyPI. The package provides
explicit namespaces for the current public Dataset inventory, while routing,
retry/fallback, cache, storage, and diagnostics remain owned by the lower-level
Collector runtime.

## License and third-party data

FinchX's own code and project materials are licensed under the Apache License
2.0; see [LICENSE](LICENSE). Third-party market data accessed through FinchX
remains subject to the applicable provider terms. FinchX does not grant rights
to redistribute provider datasets, and users are responsible for confirming
the terms that apply to their use of any upstream source or sample data.

## Installation

FinchX has not been published to PyPI. From a FinchX source checkout, install
the package with:

```bash
python -m pip install .
```

For development, use editable installation:

```bash
python -m pip install -e ".[dev,calendar]"
```

To install a locally built wheel, pass its path to pip:

```bash
python -m pip install /path/to/finchx-1.0.0-py3-none-any.whl
```

## Requirements

Python >=3.10. Python 3.10–3.13 are declared compatible; a complete multi-version
matrix is still pending. The base install contains the core runtime dependency;
optional capabilities are available through extras when installing from source:

```bash
python -m pip install ".[calendar]"
python -m pip install ".[jygs]"
```

`calendar` enables the `pandas_market_calendars` trading-calendar fallback.
`jygs` enables the authenticated Jiyangongshe browser provider. Neither is
required for `from finchx import FinchX` or `FinchX()`.

## Canonical quickstart

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()
print(result.data)
print(result.provider, result.captured_at)
```

The fetch call may access the configured data source. Constructing `FinchX()`
itself does not access the network, create a default SQLite file, start a
browser, or require optional dependencies.

Every public Client endpoint returns a `FetchResult`. Common fields are
`data`, `dataset`, `provider`, `captured_at`, `warnings`, `provenance`,
`attempts`, `fallback_used`, and `cache_hit`.

The `market` namespace also provides the computed deviation Foundation. It
returns close-based 10-day/30-day results for supported SSE and SZSE equities,
with `qfq_stock__raw_index` price basis and explicit benchmark provenance:

```python
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

instrument = InstrumentId(
    code="600519", market=Market.CN_A, kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = fx.market.deviation(instrument, windows=(10, 30))
```

This computed capability is outside the Provider-backed 42-endpoint inventory;
see [`docs/a-share-deviation-rulebook.md`](docs/a-share-deviation-rulebook.md).

## Explicit Provider selection

Use `provider=` when a request must be pinned to one registered Provider:

```python
result = fx.market.quote(provider="tencent.finance.qq.market")
```

This is a strict pin: if that Provider fails, FinchX does not silently fall
back to another Provider. Without an explicit Provider, the lower-level
Collector may apply its bounded retry/fallback policy.

## Namespace overview

| Namespace | Scope |
| --- | --- |
| `reference` | instrument identity and trading calendars |
| `market` | quotes, rankings, pools, flows, intraday data, klines and hot keyword/concept relationships |
| `fundamental` | company and industry fundamentals |
| `financial` | financial statements |
| `news` | individual-stock news references |
| `disclosure` | individual-stock disclosure references |
| `ownership` | capital and holder snapshots |
| `company` | executive snapshots and share changes |
| `corporate_action` | dividends and repurchases |

The complete frozen 9-namespace / 42-endpoint inventory is in
[`docs/public-api.md`](docs/public-api.md) and the detailed request-model table
is in [`docs/client-api-inventory.md`](docs/client-api-inventory.md).

## Optional dependencies

Install only the extra needed by the capability:

```bash
python -m pip install ".[calendar]"
python -m pip install ".[jygs]"
```

`calendar` is needed for the `pandas_market_calendars` trading-calendar
fallback, especially when selecting `provider="pandas_market_calendars"`.
`jygs` is needed for the authenticated Jiyangongshe browser Provider. The
`dev` extra contains test and schema-validation tooling.

If an optional dependency is missing, base imports and `FinchX()` still work.
The selected capability raises `MissingOptionalDependency` and identifies the
missing dependency; install the corresponding extra and retry.

## Common errors

- `AuthenticationError`: the data source requires credentials or an
  authenticated session.
- `SchemaDrift`: the external response no longer matches the expected source
  structure.
- `InvalidRequest`: the supplied arguments or Dataset request semantics are
  invalid.
- `MissingOptionalDependency`: the selected capability needs an uninstalled
  optional dependency.

## API layers

The primary API is `from finchx import FinchX`. Advanced callers can use
`Collector`, `FetchResult`, `RoutingPolicy`, `CachePolicy`, and `FetchAttempt`
from `finchx.collector` / `finchx.collectors`, storage contracts from
`finchx.storage`, and process-local diagnostic monitors from `finchx.health`,
`finchx.quality`, and `finchx.observability`.

Provider adapters, routing handlers, namespace implementation classes, private
helpers, and names beginning with `_` are implementation details rather than
the primary compatibility surface.

## Compatibility

The current v1.0 public Client surface, endpoint names, principal signatures,
and `FetchResult` return contract are protected as a compatibility contract.
A future breaking change requires an explicit versioning decision. FinchX 1.0.0
is a release candidate; PyPI publication, the v1.0 tag, and a GitHub Release
have not been created.
