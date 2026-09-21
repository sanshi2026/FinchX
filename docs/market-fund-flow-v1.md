# Market Fund Flow v1

## Scope

This document defines three single-equity contracts backed by Tencent:

- market.fund_flow_snapshot@1.0: one source trading day's summary.
- market.fund_flow_intraday@1.0: the source's cumulative point for each returned minute.
- market.fund_flow_daily@1.0: up to the 20 latest source trading days.

The Provider makes one Tencent request and parses all four response blocks once. The typed source response can feed the three Dataset normalizers without another request. The five-day block only checks consistency; it is not a Dataset. No cache, retry, fallback, Collector, scheduling, or storage is included.

## Identity and time

Every request uses a complete InstrumentId. Supported identities are SSE equities with 60 / 68 prefixes and SZSE equities with 00 / 30 prefixes. Index, ETF, and BSE identities are rejected.

tradeDate comes from Tencent history dates and is cross-checked against the date in the intraday timestamps. time is source market-local HH:MM without a timezone. Neither field is FinchX capturedAt; capturedAt records when FinchX received the response. A post-close live response does not establish intraday freshness.

## Snapshot fields

All monetary values are Decimal CNY. Source percentage points are divided by 100 and exposed as ratio fractions.

| Field | Meaning |
|---|---|
| mainNetInflow | Tencent main net inflow |
| mainInflow, mainOutflow | Gross main flow |
| mainInflowRate, mainOutflowRate | Main flow ratio fractions |
| retailInflow, retailOutflow | Gross retail flow |
| retailInflowRate, retailOutflowRate | Retail flow ratio fractions |
| superLargeNetInflow, largeNetInflow | Main flow source categories |
| mediumNetInflow, smallNetInflow | Retail flow source categories |

Tencent describes main flow as super-large plus large orders. It classifies each trade as main when amount is at least CNY 200,000 or volume is at least 60,000 shares. This is Tencent's methodology. The source does not document more detailed cutoffs between order-size categories, so FinchX does not define any.

retailInflow - retailOutflow is available to consumers as arithmetic. It is not a Tencent-provided net-flow field and is not duplicated in the snapshot payload.

## Intraday fields

Each row contains instrumentId, tradeDate, time, and price, plus:

- cumulativeMainNetInflow
- cumulativeRetailNetInflow
- cumulativeSuperLargeNetInflow
- cumulativeLargeNetInflow
- cumulativeMediumNetInflow
- cumulativeSmallNetInflow
- cumulativeMainInflow
- cumulativeMainOutflow

All flow fields are Decimal CNY. Net values may be positive or negative. The two gross main flow totals are non-negative.

Tencent's values accumulate from market open through the stated minute. They are not per-minute deltas. FinchX retains the source values and does not derive deltas or signals.

## Daily fields

Each row contains instrumentId, tradeDate, mainNetInflow, and close. All amounts and prices are Decimal; close is CNY per share. The Provider requests at most 20 latest returned trading days. Tencent price was matched exactly to the existing unadjusted Tencent daily Kline close for all 60 dates checked across three sample stocks.

avgIn is omitted because its meaning is unverified. Tencent history summary fields v0 / v2 / v4 are verified rolling sums of the daily records and are used only for source validation. v1 / v3 / v5 are omitted because their denominator and sign semantics were not established.

## Source checks

The Provider checks stock identity, required blocks, source dates, duplicate and ascending times/dates, finite numeric values, source arithmetic, and the consistency of the snapshot, minute, five-day, daily, and summary blocks. Integer source rounding is allowed up to CNY 1 for arithmetic identities and five-day totals; observed arithmetic residuals were at most CNY 1. Main gross inflow/outflow must be non-decreasing within the returned sequence. Net-flow values are not required to be monotone.

Unknown formatted codes may receive HTTP 200 with code=0, msg=ok, all-zero snapshot values, and empty trend/history arrays. Since that source response does not distinguish an invalid security from an empty result, the Provider fails when required minute or history rows are empty rather than emitting zero records.

## Excluded source fields

The Dataset contracts omit source ranking, market-cap ratios, Tencent-generated Chinese summary text, history summary fields, avgIn, activeFlow, prec, insCode, and ffHide. The five-day block is only a consistency check; it does not create a public five-day Dataset.
