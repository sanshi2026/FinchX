# FinchX

English | [简体中文](https://github.com/sanshi2026/FinchX/blob/main/README.zh-CN.md)

[PyPI](https://pypi.org/project/finchx/) · [Source code](https://github.com/sanshi2026/FinchX) · [Release notes](https://github.com/sanshi2026/FinchX/blob/main/CHANGELOG.md) · [License](https://github.com/sanshi2026/FinchX/blob/main/LICENSE)

FinchX is an independent Python library for accessing and normalizing A-share market data from registered third-party providers. Its typed client groups common requests for quotes, financial and company data, news, documents, and market rankings.

## Install

```bash
python -m pip install finchx
```

Requires Python 3.10 or newer. The base install includes FinchX's required runtime dependencies.

Optional integrations:

- `calendar` adds the `pandas_market_calendars` trading-calendar provider: `python -m pip install "finchx[calendar]"`.
- `jygs` enables the authenticated Jiuyangongshe daily-replay provider: `python -m pip install "finchx[jygs]"`. It also needs Chromium: `python -m playwright install chromium`.

## Quickstart

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # Six-digit A-share code.
)

# result.data contains StandardRecord values; each record.data is its business payload.
if result.data:
    record = result.data[0]
    print(record.data["price"])

# to_dicts() exports business payloads as a list of dictionaries.
rows = result.to_dicts()
print(rows[:1])
print(result.warnings)
```

For daily history, `fx.market.ohlcv(...)` accepts inclusive start and end dates:

```python
from finchx import FinchX

fx = FinchX()
bars = fx.market.ohlcv(
    instrument="600519",  # Six-digit A-share code.
    start_date="2026-09-01",  # Inclusive start date.
    end_date="2026-09-23",  # Inclusive end date.
    adjustment="qfq",  # Forward-adjust stock prices.
)
print(bars.to_dicts()[:1])
```

Use `adjustment="qfq"` for forward-adjusted prices, `"hfq"` for backward-adjusted prices, or `None` for unadjusted equities. Index OHLCV requires `None`.

## Find an API by use case

- **Quotes and history:** `fx.market.quote(...)`, `fx.market.quote_snapshot(...)`, `fx.market.ohlcv(...)`, `fx.market.deviation(...)`.
- **Reference and company data:** `fx.reference.trading_calendar(...)`, `fx.fundamental.financial_summary(...)`, `fx.financial.statements(...)`, plus `fx.ownership`, `fx.company`, and `fx.corporate_action`.
- **News and documents:** `fx.news.search(...)`, `fx.disclosure.search(...)`, `fx.market_news.search(...)`, and `fx.articles.get(...)`.
- **Rankings and discovery:** `fx.hotlist.stocks(...)`, `fx.hotlist.sectors(...)`, and `fx.iwencai.select(...)`.

These are starting points, not a complete endpoint list. The API reference has full signatures, data fields, return shapes, and provider details.

## Inputs and source access

Single-instrument endpoints accept six-digit codes; the endpoint determines whether a code such as `000001` means a stock or an index. Date-only parameters accept `datetime.date` or `YYYY-MM-DD`, `YYYYMMDD`, and `YYYY/MM/DD` strings; ambiguous formats such as `09/01/2026` are rejected. News, disclosure, all-market news, and forum time bounds also accept timezone-aware `datetime` values.

Some source features require caller-provided credentials, including a login Cookie for `fx.iwencai.select(...)`, an API key for `fx.iwencai.search(...)`, and a session Cookie for `fx.forum.replies(...)` or `fx.market.daily_replay(...)`. Keep credentials out of source control.

FinchX normalizes responses from third-party providers but does not redistribute their datasets. Data availability, fields, freshness, and terms depend on each provider.

## Full API reference

- [English API reference](https://github.com/sanshi2026/FinchX/blob/main/docs/DATA_API_REFERENCE.md)
- [简体中文 API 参考](https://github.com/sanshi2026/FinchX/blob/main/docs/DATA_API_REFERENCE.zh-CN.md)

FinchX is licensed under Apache-2.0. Third-party provider data remains subject to its provider's terms.
