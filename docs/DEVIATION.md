# Market Deviation

English | [简体中文](DEVIATION.zh-CN.md)


`market.deviation` is a deterministic FinchX computation for one explicitly
identified A-share equity. It compares the stock's close-based return with an
audited board benchmark over a requested 10- or 30-trading-day window.

It is not an exchange announcement, an intraday estimate, a market-wide scan,
or an application-specific trigger state.

## Scope

Version 1 supports SSE `60xxxx` and `68xxxx` equities and SZSE `00xxxx` and
`30xxxx` equities. BSE is unsupported because this version does not freeze a
corresponding benchmark, rule set, and price source.

The input must be a complete `InstrumentId` with an explicit SSE or SZSE
exchange. Unsupported identities and insufficient aligned history raise the
existing request or no-data errors; they do not produce a zero value.

## Benchmarks

| Equity identity | Board | Benchmark |
| --- | --- | --- |
| SSE `60xxxx` | SSE main board | SSE A Share Index `000002` |
| SSE `68xxxx` | STAR | SSE STAR 50 Index `000688` |
| SZSE `00xxxx` | SZSE main board | SZSE A Share Index `399107` |
| SZSE `30xxxx` | ChiNext | ChiNext Composite Index `399102` |

The mapping uses the complete identity, not a bare code. The resolved benchmark
is included in each returned window.

## Calculation

For each selected window:

```text
stock_return     = stock_end / stock_baseline - 1
benchmark_return = index_end / index_baseline - 1
deviation        = stock_return - benchmark_return
```

The baseline is the close or index point immediately preceding the selected
window start. Ratios use decimal fractions: `0.03` means 3%.

| Window | Upper threshold | Lower threshold |
| ---: | ---: | ---: |
| 10 trading days | `+1.00` | `-0.50` |
| 30 trading days | `+2.00` | `-0.70` |

The default `max_deviation_scan` convention selects the eligible start that
maximizes the stock-minus-benchmark difference. `strict_exchange_window` uses
the exchange-shaped start. Trading sessions come from
`reference.trading_calendar`, never from simple weekday arithmetic.

## Price basis and provenance

Stock input uses Tencent QFQ daily Kline closes. Benchmark input uses an
unadjusted index series. The returned fields identify:

- `calculationMode = "official_close"`;
- `priceBasis = "qfq_stock__raw_index"`; and
- `ruleVersion = "cn-a-exchange-2026-07-06+finchx-v1"`.

The computed result has no external deviation Provider. Its `FetchResult`
provider is `None`; the result retains the calendar and Kline source facts used
by the calculation.

## API

```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

instrument = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = FinchX().market.deviation(instrument, windows=(10, 30))
for window in result.data.windows:
    print(window.window_days, window.deviation)
```

For the complete signature, return fields, thresholds, and limitations, see
the [`market.deviation` section in the API reference](DATA_API_REFERENCE.md#computed-capability-marketdeviation).
