# Market breadth and independent pools v1

This document defines six EastMoney-backed Dataset contracts:

- `market.breadth@1.0`
- `market.limit_up_pool@1.0`
- `market.limit_down_pool@1.0`
- `market.yesterday_limit_up_pool@1.0`
- `market.strong_pool@1.0`
- `market.broken_limit_pool@1.0`

Each pool has its own request, source row parser, public payload, Schema, normalizer, fixture and tests. There is no `market.limit_pool`, `market.anomaly_pool`, or shared public pool payload.

## Breadth

EastMoney `getTopicZDFenBu` returns the source date and 23 one-key objects in `data.fenbu`. FinchX preserves every bucket in `distribution` and derives `advancing`, `declining`, `unchanged`, `total`, the limit-up/down counts and the over-10-percent counts. The `11` and `-11` buckets are the limit-up and limit-down counts; `10` and `-10` are the separate over-10-percent buckets.

## Pool values and identity

The EastMoney pool identity is formed from `c` and the verified `m` mapping (`0` SZSE, `1` SSE). Other values fail closed. Prices `p` and `ztp` are source thousandths of CNY and become `Price` decimals after division by 1000. `zdp`, `zf` and `hs` are percentage points and become FinchX ratio fractions after division by 100. `amount`, `ltsz` and `tshare` are CNY decimals. `lb` is a dimensionless volume ratio. Source HHMMSS fields become market-local `HH:MM:SS` strings and remain separate from `capturedAt`.

The five pool payloads keep their source-specific fields:

- limit-up: consecutive limit-up days, first/latest touch times, queued amount, break count and `zttj` statistics;
- limit-down: dynamic P/E, queued amount, last touch time, limit-price traded amount, consecutive days and opening count;
- yesterday limit-up: current-session values plus explicitly previous-day first touch time and previous-day consecutive days;
- strong: 60-day-high flag, verified selection reason and volume ratio;
- broken-limit: current-session amplitude, first upper-limit touch and break count.

`ztf`, pool `zs`, and the yesterday-pool `zttj` anchor remain source-layer unresolved and are not exposed in the public contracts.

## Pagination and source errors

Pool providers validate JSONP, `rc`, `data`, `qdate`, `tc`, page size, duplicate identities, empty pages before `tc`, missing fields and unexpected fields. `tc=0` with an empty pool is a successful empty Dataset. Captured fixtures retain the original JSONP shape under `tests/fixtures/eastmoney/pools/`.

## Scope exclusion

`market.session` is outside this contract. The historical Tencent
`/fs/app/get` response did not result in a Dataset, Schema, Provider, or
runtime dependency. `trading_calendar` remains independent.
