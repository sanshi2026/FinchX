# Trading Calendar

English | [简体中文](TRADING_CALENDAR.zh-CN.md)


`trading_calendar@1.0` returns one row for every natural date in an inclusive
range. Each row contains `date` and `isTradingDay`. Rows are sorted ascending,
complete, non-duplicated, and represented in the shared `Market.CN_A` scope for
SSE, SZSE, and BSE equity use cases.

The calendar answers whether a date is a trading day. It does not return
session hours, lunch breaks, open/close timestamps, or previous/next-session
helpers.

## Request

```python
from datetime import date
from finchx import FinchX
from finchx.entities import Market

result = FinchX().reference.trading_calendar(
    date(2026, 9, 1), date(2026, 9, 30), market=Market.CN_A
)
for record in result.data:
    print(record.data["date"], record.data["isTradingDay"])
```

Bounds are inclusive. The only supported market is `Market.CN_A`; callers do
not select an exchange.

## Providers

The primary online source is `szse.official.calendar`, which requests each
calendar month intersecting the range from the official SZSE monthly calendar.
The response must explicitly contain every natural date in the requested month;
FinchX never fills missing rows from weekday rules.

`pandas_market_calendars` is the optional offline fallback Provider. Install it
with the `calendar` extra. The fallback expands the package's exchange schedule
to all natural dates and marks session membership. Its holiday table is
package-version dependent, so the Provider id remains visible in provenance.

If any primary month fails transport, parsing, or completeness validation, the
runtime uses the configured fallback policy for the complete requested range;
it does not mix primary and fallback rows in one result.

## Record semantics

The stable record identity is `CN_A:YYYY-MM-DD`. Calendar dates are labels, not
instants, so `eventAt` and `asOf` are null. `capturedAt` records when the source
response was obtained, and `source.providerId` identifies the primary or
fallback Provider.

The normative schema is packaged at
`finchx.schemas/v1/trading-calendar.schema.json` and is loaded through the
package resource API.
