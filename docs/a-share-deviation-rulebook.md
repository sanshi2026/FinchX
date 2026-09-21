# A股偏离值管理规则手册

Version: `cn-a-exchange-2026-07-06+finchx-v1`

Freeze date: 2026-09-21

This document is the specification for FinchX's single-instrument deviation
Foundation.  It separates exchange facts and FinchX deterministic computation.
It is not a claim that FinchX can replace
an exchange announcement.

## 1. Purpose and scope

The capability accepts a complete A-share `InstrumentId` and computes 10-day
and 30-day cumulative price-deviation observations.  Version 1 supports:

* SSE main-board A shares;
* SSE STAR stocks;
* SZSE main-board A shares; and
* SZSE ChiNext stocks.

BSE is explicitly unsupported in the deviation capability.  This is not a
statement that BSE has no abnormal-volatility rules; it means that this
version has not audited and frozen a BSE rule, benchmark, and price source.

The capability is single-instrument and stateless.  It does not scan the
market, persist triggers, apply application-specific exclusions, or enrich results with
sectors or keywords.

## 2. Three rule layers

### A. Exchange rules

The current official baseline is the SSE and SZSE 2026 trading-rule revision,
effective 2026-07-06.  The official sources are:

* [SSE Trading Rules (2026 revision)](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)
* [SZSE notice for the 2026 revision](https://investor.szse.cn/lawrules/rule/trade/t20260424_620190.html)
* [SZSE Trading Rules (2026 revision), official PDF](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf)

The exchange facts used here are the cumulative formula, the 10/30-day
thresholds, corporate-action price adjustment, exclusion of no-price-limit
securities, and recalculation after the exchange's announcement or resumption
rule.  A program's calculation is not itself an exchange announcement.

### B. FinchX deterministic computation

FinchX provides a reproducible calculation over explicit Kline and calendar
inputs.  It records the benchmark, price basis, effective date, window
convention, rule version, and source provenance.  It does not infer a
regulatory state from a computed threshold crossing.

### C. Downstream application workflow (outside FinchX)

Downstream applications may select candidates, rank near-threshold names,
persist product events, apply independent exclusions, and display enriched
results. Those rules are not exchange "regulatory periods" and are not
implemented in this version.

## 3. Definition and thresholds

For a selected window:

```text
stock_return     = P_end / P_baseline - 1
benchmark_return = I_end / I_baseline - 1
deviation        = stock_return - benchmark_return
```

`baseline` is the closing price/point immediately preceding the selected
window start.  Percentages are represented as ratios (`0.03` means 3%).

| Window | Upper threshold | Lower threshold |
|---:|---:|---:|
| 10 trading days | `+1.00` | `-0.50` |
| 30 trading days | `+2.00` | `-0.70` |

This is a cumulative formula, not a sum of daily deviations.

## 4. Audited benchmark mapping

| Complete identity | Board classification | Benchmark | Code |
|---|---|---|---|
| `SSE` + `60xxxx` | SSE main board | SSE A Share Index | `000002` |
| `SSE` + `68xxxx` | STAR | SSE STAR 50 Index | `000688` |
| `SZSE` + `00xxxx` | SZSE main board | SZSE A Share Index | `399107` |
| `SZSE` + `30xxxx` | ChiNext | ChiNext Composite Index | `399102` |

The official index references are the [SSE A Share methodology](https://www.sse.com.cn/market/sseindex/indexlist/indexdetails/indexmethods/c1/000002_000002hbook_CN.pdf),
[SSE STAR 50 methodology](https://www.sse.com.cn/market/sseindex/indexlist/indexdetails/indexmethods/c1/000688_000688hbook_CN.pdf),
[SZSE A Share methodology](https://www.szse.cn/marketServices/message/index/project/P020250711381739218475.pdf),
and the [SZSE index methodology directory](https://www.szse.cn/marketServices/message/index/).

The resolver uses the full `InstrumentId`, not a bare code.  It never falls
back from `000002` to `000001` or from `399107` to `399106`.

## 5. Window and trading-day convention

Trading days come from FinchX `reference.trading_calendar@1.0`, not from
natural-day subtraction or a simple weekday rule.  `asOf` is resolved to the
latest completed trading session on or before the requested date; the result
records the resulting `effectiveAsOf`.

Two conventions are intentionally distinct:

### Strict exchange-shaped window

For `W` equal to 10 or 30, the endpoint is the last completed session.  The
window contains the preceding `W` trading sessions and uses the session before
that window as `baselineDate`.  The endpoint is `endDate`.  This is the mode
for exchange-announcement comparison.

### FinchX maximum-deviation scan

The default product calculation enumerates eligible starts in the recent
`W`-session lookback, with one preceding baseline session for each candidate.
Every candidate uses the same completed endpoint and the same benchmark.  It
selects the start maximizing:

```text
(P_end / P_baseline - 1) - (I_end / I_baseline - 1)
```

It does not first maximize stock return.  The result is labeled
`windowConvention=max_deviation_scan`; it must be called a FinchX computed
deviation rather than an official exchange trigger.  Strict mode is labeled
`strict_exchange_window`.

Both stock and benchmark must have positive closes/points on every selected
key date.  No missing or halted stock price is filled with the previous close.
The two series are joined by date and are never silently cross-source mixed.

## 6. Corporate actions and price basis

The exchange rule requires closing-price adjustment when the security has an
ex-rights or ex-dividend event in the interval.  FinchX v1 uses the audited
source-provided basis:

```text
stock:     Tencent QFQ daily close (market.klines adjustment=qfq)
benchmark: Tencent published daily index point (unadjusted index series)
```

The result exposes `priceBasis=qfq_stock__raw_index`.  The Tencent adapter's
QFQ series is selected explicitly; `none` and `hfq` are not accepted for this
calculation.  If a future source cannot explain its corporate-action basis,
the result is not computed.

## 7. Strict versus current estimate

The public v1 result is close-based and uses the latest completed trading day.
It is not a current intraday regulatory estimate.  `capturedAt` is acquisition
time and never replaces `effectiveAsOf` or `endDate`.

A future intraday mode must identify itself as an estimate and synchronize
stock and benchmark observations.  It must not reuse the close-based label.

## 8. Result fields and threshold space

Each window result contains the instrument and board identity, effective and
window dates, benchmark identity and name, stock/benchmark returns, deviation,
upper and lower thresholds, remaining deviation on both sides, start/current
prices, trigger prices, price basis, window convention, rule version, and
source provenance.

For threshold `T` and selected benchmark return `B`:

```text
trigger_price = start_price * (1 + T + B)
```

Thus the positive trigger uses `start_price*(2+B)` for 10 days and
`start_price*(3+B)` for 30 days.  Remaining deviation is:

```text
remaining_to_upper = upper_threshold - deviation
remaining_to_lower = deviation - lower_threshold
```

Remaining price space is:

```text
remaining_price_pct_to_upper = upper_trigger_price / current_price - 1
remaining_price_pct_to_lower = lower_trigger_price / current_price - 1
```

These are deterministic estimates holding the selected benchmark return
constant; they are not price promises or exchange price limits.  Internal
calculations use `Decimal`; display rounding must not feed back into trigger
logic.

## 9. Errors, no-data, and support boundaries

The capability distinguishes unsupported identity, invalid request, source
failure, insufficient history, and missing/invalid prices.  It does not turn a
source error into an empty successful calculation, and it does not turn BSE
into a zero deviation.

BSE returns an explicit unsupported result/error under FinchX's existing
request semantics.  It does not use an SSE/SZSE benchmark.  For a stock with
insufficient history, a missing endpoint price, or an unavailable benchmark,
the computation is not produced and no zero is substituted.

The prior `market.stock_keyword` BSE path is separate: EastMoney
`code=0,data=[]` remains a successful empty data result, with Health success and
Quality `no_data`.  It does not imply BSE deviation support.

## 10. Provenance and runtime boundary

`fx.market.deviation(...)` is a computed capability.  It does not create an
external `DeviationProvider`.  It reuses existing Kline and calendar
capabilities, calls a pure deterministic calculator, and retains the stock,
benchmark, and calendar source references in computed provenance.

The calculation is stateless and never reads downstream application state.  Health
describes underlying request execution; Quality describes whether the
computed result is usable; Observability records the selected Kline/calendar
sources and cache/retry facts.

## 11. Downstream application boundary

A downstream workflow may look like:

```text
candidate selection
  -> active exclusion lookup
  -> FinchX deviation calls
  -> near-threshold ranking
  -> trigger detection
  -> trigger persistence
  -> display enrichment
```

The future exclusion key must include `instrument + deviation_type`, where
`deviation_type` is independently `10d` or `30d`.  Product fields should be
named `exclusionStartDate`/`exclusionEndDate` or
`cooldownStartDate`/`cooldownEndDate`, never as an unqualified official
"regulatory start/end" period.  FinchX continues to calculate both windows
regardless of downstream product state.

## 12. Rule version and future changes

The frozen rule version is
`cn-a-exchange-2026-07-06+finchx-v1`.  A future exchange change to thresholds,
benchmarks, adjustment or recalculation rules requires a new version and new
fixtures.  Old observations must remain reproducible under their recorded
version; rules must not silently change based only on today's date.

## 13. Acceptance cases

The deterministic engine must cover:

* stock return `+80%`, benchmark return `+20%`, deviation `+60%`;
* a candidate with lower stock return but higher deviation wins the maximum
  deviation scan;
* 10-day upper threshold `1.00` and 30-day upper threshold `2.00`;
* lower thresholds `-0.50` and `-0.70`;
* weekend/holiday effective-date resolution;
* insufficient history, missing close, non-positive close, and unsupported BSE;
* stock QFQ versus benchmark raw-index basis; and
* successful BSE `stock_keyword` empty data with Health success and Quality
  `no_data`.

## 14. Data-quality and source-evidence rules

The following rules make the result non-computable rather than inventing a
price or a zero:

* the requested endpoint must be a completed trading session;
* weekends, holidays, and exchange closures are resolved by
  `reference.trading_calendar`, never by weekday arithmetic;
* a missing, duplicate, mismatched, or non-positive stock/index close rejects
  the calculation;
* a halted or otherwise unavailable key close is not filled with the previous
  close;
* insufficient history rejects the result; and
* a benchmark is never substituted across markets or silently mixed with a
  different price basis.

The exchange exclusion for securities without price limits is a regulatory
classification fact.  This v1 computed capability does not claim to determine
whether an exchange has formally classified a security as abnormal or to
replace an exchange announcement; that requires an independently audited
listing/status and announcement source.  `Health` describes request
execution, `Quality` describes result usability, and `Observability` records
the selected sources and runtime path.

`effectiveAsOf` is the completed market date used for calculation.  It is
distinct from `capturedAt`, which is acquisition time, and from any downstream
trigger or exclusion date.  Provenance should retain the stock,
benchmark, and calendar source references, together with the frozen
`priceBasis` and `ruleVersion`.

## 15. Downstream workflow naming boundary

If a downstream application records a product exclusion after a calculated
threshold event on trading day `T`, its dates should be named
`exclusionStartDate`/`exclusionEndDate` or
`cooldownStartDate`/`cooldownEndDate`.  They must not be named an unqualified
official “regulatory start/end” period.  The event identity must include
`instrument + deviation_type`, with `deviation_type` independently equal to
`10d` or `30d`; an active 10-day product exclusion does not suppress 30-day
calculation.  This downstream state is never read or changed by
`fx.market.deviation(...)`.

## 16. References

The primary official references are the exchange rule pages and index
methodologies linked above.  For later announcement cross-checks, retain the
[SSE severe-abnormal-volatility information page](https://www.sse.com.cn/disclosure/diclosure/ycjyxx/main/)
and the [SZSE ChiNext Composite methodology](https://www.szse.cn/marketServices/message/index/project/P020250711382092170016.pdf)
alongside the rule version.  These references support auditability; they do
not change the v1 benchmark mapping or calculation mode.

The implementation inventory is maintained in
[`client-api-inventory.md`](client-api-inventory.md) and the related public
API documents. This file is the authoritative rulebook for the computed
capability.
