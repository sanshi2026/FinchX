# FinchX

English | [简体中文](README.zh-CN.md)


FinchX is an independent Python library for accessing and normalizing A-share market data from registered third-party providers.

## What is FinchX?

The primary entry point is a small typed client:

```python
from finchx import FinchX

fx = FinchX()
```

FinchX exposes nine namespaces, a stable `FetchResult` envelope, normalized Dataset payloads, provider provenance, bounded runtime routing, and an explicit computed deviation capability.

## Features

- Market quotes, rankings, klines, intraday series, order books, fund flow, pools and sentiment.
- Reference identity and trading calendars.
- Fundamental, financial, ownership, executive and corporate-action data.
- Individual-stock news and disclosure references.
- Source-ranked stock keywords/concepts from the implemented EastMoney contract.
- Deterministic close-based stock-versus-benchmark deviation for supported A-share equities.

## Installation

For the released package:

```bash
pip install finchx
```

For a source checkout:

```bash
python -m pip install .
```

For local development:

```bash
python -m pip install -e ".[dev]"
```

FinchX requires Python 3.10 or newer and the base runtime depends on Pydantic 2.

## Quickstart

### Current quote universe

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()

for record in result.data:
    print(record.data["instrumentId"], record.data["price"])
print(result.provider, result.captured_at)
```

### Single-stock quote

```python
result = fx.market.quote_snapshot("600519")
```

Single-instrument Client endpoints accept either a complete `InstrumentId` or a verified six-digit A-share code. FinchX resolves the code to a `CN_A` equity and infers SSE from `6`, SZSE from `0`/`3`, and BSE from `4`/`8`/`9` when the selected endpoint supports that venue. Index and other ambiguous identities still require an explicit `InstrumentId`.

### Historical OHLCV

```python
from datetime import date
from finchx import FinchX
from finchx.datasets import KlineAdjustment

fx = FinchX()
result = fx.market.ohlcv(
    "600519",
    date(2026, 9, 1),
    date(2026, 9, 18),
    adjustment=KlineAdjustment.QFQ,
)
for record in result.data:
    print(record.data["barDate"], record.data["close"])
```

### News and disclosures

```python
news = fx.news.search("600519", page_size=10)
disclosures = fx.disclosure.search("600519", page_size=10)
print(news.data[0].title if news.data else "no news")
print(disclosures.data[0].title if disclosures.data else "no disclosures")
```

### Financial data

```python
result = fx.fundamental.financial_summary("600519")
print(result.data.data["periods"])
```

### Stock keywords

`market.stock_keyword` returns structured keywords/concepts supplied by the source. It does not perform NLP keyword extraction and does not invent a heat score.

```python
result = fx.market.stock_keyword("600519")
for keyword in result.data.data["keywords"]:
    print(keyword["keywordName"], keyword["hitCount"])
```

### Computed deviation

```python
result = fx.market.deviation("600519", windows=(10, 30))
for window in result.data.windows:
    print(window.window_days, window.deviation)
```

This is a deterministic close-based calculation over FinchX trading-calendar and Kline inputs. It is not an official exchange announcement or an intraday estimate. Version 1 supports SSE `60xxxx` and `68xxxx`, and SZSE `00xxxx` and `30xxxx` equities; BSE is unsupported for this capability.

## Core concepts

### Instrument identity

Single-instrument endpoints accept either a complete `InstrumentId` or a verified six-digit A-share code. The latter is normalized to `Market.CN_A` plus `InstrumentKind.EQUITY`; code prefixes `6`, `0`/`3`, and `4`/`8`/`9` identify SSE, SZSE, and BSE respectively where supported. Index and other ambiguous identities require a complete `InstrumentId` with `code`, `market`, `kind`, and, where needed, an explicit `exchange`.

### FetchResult

Every Client endpoint returns a `FetchResult`. Its public fields include `data`, `dataset`, `dataset_id`, `provider`, `provider_id`, `captured_at`, `warnings`, `provenance`, `attempts`, `fallback_used`, and `cache_hit`. `dataset_id` and `provider_id` are convenience properties for `dataset.name` and `provider`. Most provider-backed endpoints put standardized `StandardRecord` objects in `data`; search endpoints return typed document-reference tuples; the computed deviation endpoint returns `DeviationData` directly. The full contract is in [DATA_API_REFERENCE.md](docs/DATA_API_REFERENCE.md).

### Choosing a Provider

Use `provider=` to pin a request to one registered Provider id:

```python
result = fx.market.quote(provider="tencent.finance.qq.market")
```

This is a strict pin: if the named Provider fails, FinchX does not silently select another Provider. Without an explicit pin, the configured runtime policy chooses among the implemented Providers. The documentation lists implemented Providers; it does not promise a primary/fallback order.

### Cache

Caching is controlled by the Collector configuration. With a configured enabled cache policy, `use_cache=None` follows that policy and `use_cache=False` bypasses the cache. An explicit Provider pin bypasses cached results. `FinchX()` itself does not create a cache or a default storage file.

## Available data

| Namespace | Provides |
| --- | --- |
| `reference` | Instrument identity and trading calendars |
| `market` | Quotes, rankings, klines, intraday, flows, pools, sectors, keywords and sentiment |
| `fundamental` | Company profiles, financial summaries, revenue and industry comparisons |
| `financial` | Financial statements |
| `news` | Individual-stock news references |
| `disclosure` | Individual-stock disclosure references |
| `ownership` | Capital and holder snapshots |
| `company` | Executive snapshots and share changes |
| `corporate_action` | Dividends and repurchases |

The complete 42 Provider-backed / Dataset-backed public endpoints plus the computed `market.deviation` capability are documented in [DATA_API_REFERENCE.md](docs/DATA_API_REFERENCE.md).

## Optional dependencies

The base install remains importable without optional packages.

```bash
python -m pip install ".[calendar]"
python -m pip install ".[jygs]"
```

For the released package, the equivalent forms are `pip install "finchx[calendar]"` and `pip install "finchx[jygs]"`.

- `calendar` installs `pandas_market_calendars` for the `pandas_market_calendars` trading-calendar Provider.
- `jygs` installs Playwright for the authenticated `jiuyangongshe.daily_replay` Provider. That Provider also requires a `JYGS_SESSION` value and a usable browser installation.

Selecting a capability whose optional dependency is absent raises `MissingOptionalDependency` and identifies the dependency.

## Error behavior

Common public error categories include:

- `InvalidRequest`: request values or Dataset semantics are invalid.
- `AuthenticationError`: the source requires credentials or an authenticated session.
- `MissingOptionalDependency`: the selected Provider needs an uninstalled extra.
- `SchemaDrift`: the upstream response no longer matches the Provider contract.
- `AllProvidersFailed`: every Provider allowed by the configured runtime policy failed.
- `NoData`: the Provider completed but did not produce usable data.

## Data sources and third-party notice

FinchX normalizes data returned by registered third-party sources. It does not promise an update frequency, real-time availability, or a particular upstream service level. FinchX does not redistribute third-party market datasets. Users are responsible for complying with the terms and policies of the respective data providers.

## Python support

Python 3.10, 3.11, 3.12 and 3.13 are declared compatible by the package metadata. Provider availability and upstream behavior may vary independently of Python version.

## License

FinchX is licensed under Apache-2.0. Third-party data and provider terms are not covered by the FinchX license.

## Full API reference

See [DATA_API_REFERENCE.md](docs/DATA_API_REFERENCE.md) for the complete Dataset dictionary, exact method signatures, request fields, return fields, Provider mappings, optional dependencies and examples.
