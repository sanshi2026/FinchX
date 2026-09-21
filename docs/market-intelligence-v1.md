# Market intelligence contracts v1

Updated: 2026-09-20 (Asia/Shanghai)

This document defines four independent Dataset contracts from Aigupiao. They
are snapshots of source-defined market activity, not investment advice,
derived sentiment models, or cross-provider rankings.

## Public Dataset names

| Dataset | Request | Record shape |
| --- | --- | --- |
| `market.sentiment_snapshot@1.0` | `MarketSentimentRequest` | one market-level snapshot |
| `market.consecutive_limit_up_snapshot@1.0` | `MarketConsecutiveLimitUpRequest` | one record per current series row |
| `market.dragon_tiger_list@1.0` | `MarketDragonTigerListRequest(tradeDate)` | one record per dated instrument/trade occurrence |
| `market.dragon_tiger_detail@1.0` | `MarketDragonTigerDetailRequest(instrumentId, tradeDate, tradeId)` | one detailed instrument/trade occurrence |

The corresponding JSON Schemas are in `finchx.schemas/v1/`:

- `market-sentiment-snapshot.schema.json`
- `market-consecutive-limit-up-snapshot.schema.json`
- `market-dragon-tiger-list.schema.json`
- `market-dragon-tiger-detail.schema.json`

## Contract semantics

### `market.sentiment_snapshot`

Public data fields are `marketTemperature`, `totalTurnover`,
`forecastedTurnover`, `turnoverChangeAmount`, `blastBreakRatio`,
`previousLimitUpBreakChangeRatio`, `stopTradingCount`, `oneLimitUpCount`,
`twoLimitUpCount`, `threeLimitUpCount`, `highLimitUpCount`,
`twoLimitUpPromotionRatio`, `threeLimitUpPromotionRatio`,
`highLimitUpPromotionRatio`, `previousLimitUpThemeChangeRatio`, and
`previousConsecutiveLimitUpThemeChangeRatio`.

Amounts are CNY `Decimal` values. Source percentage points become ratio
fractions (`2.50%` becomes `0.025`). `marketTemperature` is kept as a
decimal string because the source defines it as a sentiment indicator, not a
physical temperature or ratio. Source-derived temperature/forecast values are
marked with an `estimated` quality issue.

### `market.consecutive_limit_up_snapshot`

Each record contains `instrumentId`, `name`, `tradeDate`, `lastPrice`,
`change`, `changeRatio`, `turnoverRatio`, `amount`, `limitUpTime`, `state`,
`isConsecutiveLimitUp`, `consecutiveLimitUpCount`,
`previousConsecutiveLimitUpCount`, `themeId`, `themeName`, `floatShares`,
`totalShares`, and `marketCap`.

`instrumentId` is always an explicit CN_A equity on SSE, SZSE, or BSE. The
source prefix (`sh`, `sz`, or `bj`) is used for exchange identity and is
preserved when requests are built. `marketCap` is CNY; the source `whole`
value is converted from 100-million-CNY units. Only exact `N连板` states with
`series_limit_up=yes` derive `consecutiveLimitUpCount`; `N天M板` is not treated
as an `N连板` count.

`eventAt` is the source `tradeDate` plus `limitUpTime` in `Asia/Shanghai`.
`capturedAt` is Provider capture time and is not used as event time.

### `market.dragon_tiger_list`

Each record contains `instrumentId`, `name`, `tradeDate`, `tradeId`,
`closePrice`, `changeRatio`, `amount`, `totalBuy`, `totalNet`, `explanation`,
`threeDayFlag`, `themeId`, and `themeName`.

The identity includes `tradeId`; duplicate instruments with distinct trade IDs
are valid separate occurrences. The list endpoint does not provide a reliable
total-sell field, so `totalSell` is intentionally absent from this contract.

### `market.dragon_tiger_detail`

The detail record contains the list fields plus `totalSell`, `commentKind`,
`commentObjectId`, `buySeats`, and `sellSeats`.

Each public seat has `rank`, `seatName`, `sourceSeatCode`, `hasDetails`,
`buyAmount`, `sellAmount`, and `netAmount`. `rank` is one-based array order,
not a source ranking, and this transformation is recorded in provenance. Buy
and sell arrays are independent and may have different lengths; seat codes are
not required to be unique across the two sides.

## Provider boundary

The public contracts expose normalized CNY amounts, ratio fractions, explicit
instrument identities, and stable field names. Aigupiao field names, raw unit
suffixes, analysis flags, seat percentages, and unconfirmed classifications
remain Provider/raw payload data. Provider exact-key validation rejects source
drift instead of silently widening the public contract.

The implementation does not reuse the independent EastMoney limit-up pool
contracts. The Aigupiao series snapshot has a different source, state model,
market-cap/share fields, and consecutive-limit-up semantics. It also does not
introduce a generic market-sentiment score or merge Dragon Tiger list and
detail into one Dataset.

## Quality and availability

Successful source responses are `live`; optional empty values are `None` and
not zero. Missing required data, malformed responses, identity mismatches,
schema drift, and HTTP failures are Provider failures rather than successful
empty snapshots. The contracts add no cache, retry policy, fallback source,
storage, scheduler, or implicit network access during import.
