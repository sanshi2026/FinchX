# `market.klines@1.0`

## Scope and providers

`market.klines` is FinchX's shared daily Kline Dataset. Its current
capabilities are:

| Instrument | Provider | Capability |
|---|---|---|
| SSE/SZSE equity | Tencent `newfqkline` | `none`, `qfq`, `hfq` |
| SSE 000001 index | Sohu `mkline`; Tencent `newfqkline` | peer Providers; `not_applicable` |
| SZSE 399001/399006 index | Sohu `mkline`; Tencent `newfqkline` | peer Providers; `not_applicable` |

`SohuKlinesProvider` and `TencentKlinesProvider` independently implement the
same `KlinesProvider` interface and normalize to `market.klines@1.0`. They are
peer implementations: there is no provider priority, automatic fallback,
runtime routing policy, or Collector in the current Stage. A request uses one
Provider; bars and fields are never merged across providers.

Only explicit `Market.CN_A` identities are accepted. Equity routing supports
verified SSE `60`/`68` and SZSE `00`/`30` code families. Index routing supports
only SSE `000001` and SZSE `399001`/`399006`. Index, equity, ETF, and exchange
are never inferred from a bare code. BSE Klines are unsupported.

## Request and result

`KlinesRequest` requires a complete `InstrumentId`, inclusive `startDate` and
`endDate`, and implicit daily frequency. Equity requests must explicitly pass
`adjustment=none`, `qfq`, or `hfq`. Index requests must omit `adjustment`; the
result uses `not_applicable`. Supplying even `adjustment=null` to an index
request is rejected. Reversed dates, datetimes instead of dates, unsupported
identities, and unsupported instrument kinds fail validation.

Each bar is one `StandardRecord` with `instrumentId`, `barDate`, `open`,
`high`, `low`, `close`, `volume`, `amount`, and `adjustment`. Prices and amount
are exact decimal values serialized as canonical strings. `volume` is a
non-negative whole number of shares. `amount` is nullable CNY: null means the
selected source did not provide a usable amount; it is never changed to zero
or estimated. Kline high/low ordering is validated after source-unit
conversion. Bars are returned ascending and filtered to the inclusive request
range. No synthetic halt or holiday bars are created. Duplicate dates,
wrong identity, invalid OHLC, malformed source structure, and incomplete
Tencent pagination fail the provider request.

## Current-day bars

A request may include the current trading date. During market hours, `close`
means the latest price supplied by that source when FinchX captures the
response. The value can change with the source, as can high, low, volume, and
amount. After the close, the same daily bar naturally becomes the final daily
Kline. FinchX does not decide when callers should collect and does not expose a
`partial`, `final`, or `isClosed` flag. Sohu may still return only the prior
complete date; FinchX preserves what each source returns.

## Tencent `newfqkline`

Endpoint:

```text
https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get
```

Explicit SSE routes to `sh{code}` and SZSE to `sz{code}`. Equity modes use the
`day`, `qfqday`, or `hfqday` series. The parser validates the response
assignment and requested source key, reads only the Kline series, and ignores
bundled quote data. Tencent's tested window is count-based from `endDate`, so
the adapter pages backward in windows up to 800 bars until it reaches the
requested start or a shorter source page. It then filters the inclusive range.

Tencent equity and index raw volume is reported in hands and is multiplied by
100 using `Decimal` to produce whole shares. Raw amount is in ten-thousand CNY
and is multiplied by 10,000 using `Decimal`. Index requests omit adjustment in
the public contract; the Tencent endpoint's daily series still requires the
source-side `none` mode, and the returned public adjustment remains
`not_applicable`.

## Sohu `mkline` index source

The Provider uses only this historical endpoint family:

```text
https://hq.stock.sohu.com/mkline/zs/{code末三位}/zs_{code}-10_2.html?_=...
```

Examples include `/zs/001/zs_000001-10_2.html` and
`/zs/006/zs_399006-10_2.html`. It does not call Sohu `quote_k_r`, `-1.html`,
or a separate latest-quote endpoint. A single response contains the long
historical `dataDiv` series; FinchX validates and parses the source rows,
filters the inclusive requested dates, then sorts them ascending.

The verified raw `dataDiv` layout is date, open, close, high, low, volume,
amount, followed by source change fields. Dates are `YYYYMMDD`. Raw volume is
in hands (including decimal hands) and is multiplied by 100 using `Decimal`;
it must resolve exactly to whole shares. Raw amount is in ten-thousand CNY and
is multiplied by 10,000 using `Decimal`. The `amount` therefore enters
`MarketKlineData` as a concrete CNY value; it is not estimated. The source
wrapper, status, type, data array, each row, and duplicate dates are validated.

Sohu's URL uses the `zs` family and does not itself encode SSE versus SZSE.
FinchX validates the full request-bound `InstrumentId` before routing the
verified code and keeps that identity on every result. The Sohu payload does
not independently prove the exchange, so identity is request-bound. Source
URL, provider ID, and source record ID are preserved in `Source` provenance.

## Identity and provenance

A record identifies the standard instrument/date/adjustment value, not the
vendor. Its stable `recordId` is:

```text
<format_symbol>@<YYYY-MM-DD>@<adjustment>
```

Index records end with `@not_applicable`. Tencent and Sohu may therefore
produce the same logical record ID for the same index and date. Their provider
ID, source URL, and source record ID keep provenance distinct. No provider
name is added to `recordId`.

`capturedAt` is FinchX's timezone-aware capture time, not a source event time.
`barDate` is a natural trading-date label and `eventAt` remains null. No
freshness or market-session engine is implemented.

## Source differences and current exclusions

Tencent and Sohu can report different index volume or amount values because
source/statistical conventions can differ. This is accepted source behavior,
not a provider mismatch gate. Each Provider preserves and correctly converts
its own source values; FinchX does not alter them to match another vendor.

Earlier exploratory observations about THS are not part of this public
contract. THS has no production Provider or fixture in the current
implementation.

## Packaging status

- Kline contracts are implemented and tested.
- First-release packaging includes the versioned schema resources.
- The v1 schemas are packaged under `finchx.schemas/v1/`; this packaging
  concern is separate from Klines Provider functionality.

Known limits:

- Tencent is the only current equity Kline Provider.
- Sohu and Tencent index Providers are peers; neither has priority and no
  runtime routing or automatic fallback policy exists.
- BSE, ETF, other index identities, and non-daily intervals are unsupported.
- Sohu identity is request-bound because its index path does not encode the
  exchange.
- Sohu has no separate current-day quote merge; current-date inclusion depends
  on the response returned by the `mkline` endpoint.
- Sohu historical data may contain source-side OHLC anomalies. FinchX does not
  silently repair upstream prices. A requested range containing an invalid
  bar fails validation. An observed example is SSE index `000001` on
  `1996-02-12`: raw row
  `["19960212","523.57","525.77","524.06","523.57","506317.00","2","0.00%","0.36","0.07%"]`
  decodes as O/H/L/C `523.57/524.06/523.57/525.77`, so `high < close` by
  1.71 index points. Tencent for the same date returned
  O/H/L/C `525.63/525.77/522.16/525.77`. The Sohu parser follows the verified
  source field order (open, close, high, low); the inconsistent OHLC is present
  in the raw Sohu row and is rejected by contract validation.
- Provider availability and latest-bar freshness are observations from live
  validation, not a permanent service guarantee.
- The wheel includes `finchx.schemas/v1/market-klines.schema.json`; package
  resource loading is covered by the regression test suite.
