# `market.daily_replay@1.0`

Public contract for one authenticated 韭研公社 daily replay snapshot.

## Semantics

`market.daily_replay` represents the complete source-selected replay for one
actual trading day. `requestedDate` is the date requested by the caller;
`tradeDate` is the date returned by the source after its own trading-day
selection. A weekend request can therefore have a different `tradeDate`.
This Dataset does not accumulate history, maintain a theme library, infer
current stock themes, or aggregate across days; those responsibilities belong
to downstream applications.

## Data

The standardized payload contains `requestedDate`, `tradeDate`, and nested
`themes`. Each theme contains `themeName`, nullable `reason`, source-reported
`stockCount`, nullable `sourceThemeId`, and a `stocks` list. Each stock
contains an explicit FinchX `InstrumentId`, `name`, nullable `limitUpTime`,
nullable source `streakText`, CNY/share `price`, ratio-fraction `changeRatio`,
nullable source `day` and `edition`, and the complete source `expound` string.

`price` is converted from the authenticated source integer-cent value to a
CNY Decimal. `shares_range` is converted from source basis points of a
percentage (`1002` means `10.02%`) to a ratio fraction (`0.1002`). `num` is
preserved as source text; `day` and `edition` are preserved only when the
source supplies them and are not recomputed from `streakText`.

A stock occurrence is retained once per source theme. The same
`InstrumentId` may therefore occur in multiple themes. A source count/list
mismatch is retained as returned and recorded as a quality concern; the
returned stock list is not truncated.

## Provider boundary

`JiyangongsheReplayProvider` opens a fresh Playwright Chromium headless
context for each fetch, injects a caller-provided `SESSION` or the
`JYGS_SESSION` environment value, opens the normal action page, and captures
`count-pc` followed by `action/field`. Browser JavaScript remains responsible
for source token/timestamp behavior. No persistent profile, storage state,
DOM/text parsing, stealth setting, fingerprint override, proxy rotation,
CAPTCHA bypass, or signer implementation is used.

Playwright is optional: install the `finchx[jygs]` extra and the matching
Chromium browser for live use. Fixture transports keep offline tests free of
browser and network requirements. The provider maps missing/invalid SESSION,
`errCode=1`, `errCode=110`, HTTP/network/timeout failures, malformed JSON, and
schema drift to explicit `ProviderError` reasons.

The source-only 简图 metadata row is captured in the Provider raw payload and
is intentionally not part of the public normalized Dataset. User identity,
community engagement, source lifecycle/order metadata, and transport timing
fields remain provider-only, raw-only, or not-retained according to the source
audit; they are not leaked into the public contract.
