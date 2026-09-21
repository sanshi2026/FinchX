# Market Quote and Ranking Dataset Contracts v1

## Dataset identities and operation scopes

The market quote Dataset identity is market.quote@1.0. Its request,
MarketQuoteUniverseRequest, asks for a CN_A_SHARE snapshot. The request scope
is market-wide; it does not encode a provider page size, offset, endpoint, or
source-specific sort token. Each returned MarketQuoteData describes one
canonical InstrumentId and becomes one StandardRecord.

The market ranking Dataset identity is market.ranking@1.0. Its request
requires a universe, criterion, direction, and limit. limit=None asks for the
complete ranking. Provider pagination parameters are not part of this
contract.

The ranking result contains one record per ranked instrument. It carries
the complete MarketQuoteData payload plus the universe, direction, 1-based
position, and a criterion-discriminated metric. MarketRankingData inherits the
quote fields so quote and ranking rows share the same normalized field names,
units, and optional-field semantics. Universe is repeated in each row so a
standalone StandardRecord remains self-describing.

## Quote payload

MarketQuoteData uses the existing InstrumentId and contains:

- instrumentId: required canonical instrument identity.
- price: required Price, expressed in CNY per share.
- name: optional source-reported display name.
- priceChange: optional signed Price value in CNY per share.
- changeRate: optional Percentage ratio fraction.
- changeRate5d, changeRate10d, changeRate20d, changeRate60d, changeRate52w,
  and changeRateYtd: optional Percentage ratio fractions for the indicated
  source-designated windows.
- amplitude: optional Percentage ratio fraction.
- volumeRatio: optional non-negative Ratio in times; 2.35 means 2.35x.
- volume: optional whole-share count.
- amount: optional monetary amount in CNY.
- turnoverRate: optional Percentage ratio fraction.
- marketCap and floatMarketCap: optional monetary amounts in CNY.
- peTtm: optional ValuationMultiple expressed in times; negative values are
  allowed because a loss-making company can have a negative P/E.
- mainNetInflow, mainInflow, mainOutflow, mainInflow5d, and mainOutflow5d:
  optional Amount values in CNY, preserving the provider-reported flow metrics.
  Their classification and calculation methods are provider-defined; use them
  for trends within a provider and do not compare them as equivalent across
  data sources. The `5d` fields preserve the provider's period label without
  assuming a calendar-day or trading-session definition.

Optional values serialize as JSON null when unavailable. Zero remains a
numeric value and is not converted to null. A missing required price is a
validation failure. Provider fields outside this contract are rejected.
PriceChange uses the existing Price unit because Price already accepts signed
Decimal values and expresses the same CNY-per-share dimension. No separate
price-delta type is needed.

When one or more optional quote fields are unavailable, the standardized
record retains status live for the successfully captured snapshot and records
a partial quality issue listing those fields.

## Compatibility note

The public contract omits `priceToBook` from the `market.quote@1.0` payload;
consumers
of that field must stop reading it. The Dataset remains at `1.0` because this is
a correction before a stable public release, not a released schema migration.
The same pre-release compatibility policy applies to the market.ranking@1.0
payload, which now includes the complete quote fields.

## Ranking criteria and value types

The v1 public criteria are:

| Criterion | Value type | Unit |
| --- | --- | --- |
| turnover | Amount | CNY |
| change_percent | Percentage | ratio fraction |
| volume | Shares | whole shares |

The metric.criterion discriminator fixes the corresponding metric.value type
in both Python and JSON Schema. Its value must agree with the corresponding
quote field (amount, changeRate, or volume). Invalid combinations fail
validation. position is a positive integer assigned from the ordered provider
result.

## Time semantics

capturedAt is the timezone-aware instant when FinchX captures a response.
These current-snapshot contracts do not infer a market event time. Unless a
source supplies verified timestamps, eventAt, publishedAt, updatedAt, and
asOf remain null. capturedAt is never copied into those fields.

Rows parsed from one HTTP response share the same capture timestamp. Different
pages in one market-wide snapshot may have different capture timestamps.

## Source-scoped fields and exclusions

The current v1 public contract omits Tencent's raw `pn` field. A same-source
cross-check once considered a `priceToBook` mapping, but that mapping is not
part of the public contract and the observation is not a guarantee of stable
field semantics. The
contract preserves provider-reported money-flow amounts for within-provider
trend analysis; their calculation categories are not guaranteed to be
comparable across providers. Speed ranking, source state, source security-type
tokens, and raw provider fields remain omitted.
