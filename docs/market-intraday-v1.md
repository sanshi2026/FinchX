# Market Intraday v1

## Scope

This guide covers four single-instrument Dataset contracts:

- market.equity_intraday@1.0: one equity's latest returned trading date.
- market.equity_intraday_5d@1.0: up to five latest returned trading dates for one equity.
- market.index_intraday@1.0: one index's returned session.
- market.index_intraday_5d@1.0: up to five latest returned trading dates for one index.

Each source minute row becomes one StandardRecord. Records sort by (tradeDate, time); capturedAt is FinchX capture time, separate from source trading time.

## Contract

    {
      "instrumentId": {"market": "cn_a", "exchange": "szse", "kind": "equity", "code": "300434"},
      "tradeDate": "2026-09-18",
      "time": "09:30",
      "price": "13.11",
      "volume": 2546100,
      "amount": "33379371.00",
      "cumulativeVolume": 2546100,
      "cumulativeAmount": "33379371.00"
    }

price, amount, and cumulativeAmount are Python Decimal, serialized as decimal strings. volume and cumulativeVolume are whole-share integers. Tencent supplies only cumulative volume in lots and cumulative amount in CNY: FinchX converts cumulative volume with raw lots * 100, then derives volume / amount from the current point minus the previous point within the same tradeDate. The first point for each date uses its cumulative values as that point's minute values. Equal cumulative values (including the 11:30 to 13:00 lunch boundary) produce zero minute values. A decrease in either cumulative series fails normalization. Source cumulative fields remain available alongside FinchX-derived minute fields.

time is source HHMM normalized to HH:MM. Lunch-boundary points at 11:30 and 13:00 are retained even when cumulative totals match. Valid source times after 15:00 are not clipped.

## Tencent Provider mappings

| Dataset | Endpoint | Dataset date selection |
|---|---|---|
| market.equity_intraday | web.ifzq.gtimg.cn/appstock/app/day/query | Latest returned date |
| market.equity_intraday_5d | web.ifzq.gtimg.cn/appstock/app/day/query | Latest up to five returned dates |
| market.index_intraday | web.ifzq.gtimg.cn/appstock/app/minute/query | Source date in response |
| market.index_intraday_5d | web.ifzq.gtimg.cn/appstock/app/day/query | Latest up to five returned dates |

Equity intraday and equity intraday 5d use the same fdays_data_<symbol> assignment, day-query request builder, parser, and typed raw points. The day-query parser reads each date group's data[] and expands every row of HHMM price cumulativeVolumeLots cumulativeAmountCNY. Dataset normalization chooses either the latest one date or the latest five dates; this is the formal upstream for both datasets, not a fallback.

The index minute endpoint uses min_data_<symbol> and a source-specific outer parser. Index 5d uses the shared day-query parser.

Every request requires a complete InstrumentId. Equity datasets accept SSE 60/68 and SZSE 00/30 equity codes. Index datasets accept SSE 000001, SZSE 399001, and SZSE 399006. Response symbol keys are validated against the request identity.

## Validation

The official equity day-query request was previously checked after market close and returned 242 current-date points plus five dates. After the minute-delta normalization change, a constrained network attempt returned URLError for each entry; one user-requested authorized retry then returned HTTP 200 for all four entries. Each response passed its formal parser, normalization, identity, and ordering checks: 242 current-day equity points, 1,210 five-day equity points, 242 current-day index points, and 1,210 five-day index points. Intraday dynamic updates remain unverified because validation was after market close. See docs/stage-5.3b-source-audit.md.

This Stage adds no Collector, cache, fallback, scheduler, storage, minute Kline, or runtime routing.
