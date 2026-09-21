# Tencent market provider v1

FinchX's Tencent provider reads the market-wide A-share rank endpoint
`https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList` and
supports the `instrument`, `market.quote`, and `market.ranking` datasets.

The provider uses Tencent's reported `total` and offset-based pages as the
completeness boundary. It fails on missing totals, short pages before the
reported end, early empty pages, duplicate instrument identities, excess
rows, response-offset mismatches, or total drift. A valid zero-total response
returns an empty dataset. Full listing and quote requests traverse the
reported total with pages of 100 rows; finite ranking limits request only the
remaining count. Each page receives its own timezone-aware `capturedAt`; event,
publication, update, and as-of times remain unset.

Tencent's explicit `sh`, `sz`, and `bj` prefixes map to SSE, SZSE, and BSE;
unknown prefixes and stock types fail. `zxj`, `zd`, and `pe_ttm` remain direct
Decimal values. `zdf`, `zdf_d5`, `zdf_d10`, `zdf_d20`, `zdf_d60`,
`zdf_w52`, `zdf_y`, `zf`, and `hsl` convert percentage points to ratio
fractions by dividing by 100. They map to `changeRate`, the corresponding
period-specific `changeRate*` fields, `amplitude`, and `turnoverRate`.
`zdf_w52` is exposed as 52-week change, consistent with the confirmed period
label. An older wrapper called
`zdf_y` a yearly change, which did not distinguish year-to-date from a trailing
year; this migration maps it to year-to-date per the confirmed field
semantics. Tencent's endpoint-specific official field dictionary was not
available for independent verification. `lb` maps directly, without percent
conversion, to the non-negative dimensionless `volumeRatio` (`2.35` means
`2.35x`). `volume` converts lots to shares by multiplying by 100, `turnover` converts
ten-thousand CNY to CNY, and `zsz`/`ltsz` convert hundred-million CNY to CNY.

Offline provider tests use injected transports and the fixtures under
`tests/fixtures/tencent/`; pytest does not call Tencent. Public ranking v1
supports turnover, change percentage, and volume. Raw Tencent `pn` is ignored
and never appears in public `market.quote` data. The mapping to `priceToBook`
is not part of this public contract. An earlier same-source
comparison found exact matches for 50 instruments between `pn` and the PB
value at field 46 from Tencent's `qt.gtimg.cn` quote endpoint; that historical
observation is retained as audit evidence, not as a current public mapping.
Tencent `zljlr`, `zllr`, `zllc`, `zllr_d5`, and `zllc_d5`
are retained as `mainNetInflow`, `mainInflow`, `mainOutflow`, `mainInflow5d`,
and `mainOutflow5d`, with raw values multiplied by 10,000 into CNY following
the current Tencent convention used by the adapter. These are provider-reported
trend values; cross-provider methodology is not standardized. Their arithmetic
net relationship held within 0.01 raw units on all 5,565 rows in the
2026-09-17 snapshot; this does not independently define Tencent's business
classification. The `5d` calendar-versus-trading-session window remains
unspecified. `speed` remains unverified and outside the public payload. The special
meaning of a zero `zxj` is also not established; none occurred in the live
2026-09-17 full-market snapshot.
