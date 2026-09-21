# Market Quote Snapshot and Orderbook v1

## Scope

- `market.quote_snapshot@1.0` describes the current quote of one explicit instrument. It supports SSE/SZSE equities and the verified indices SSE 000001, SZSE 399001, and SZSE 399006.
- `market.orderbook@1.0` describes up to five bid and ask levels for one SSE/SZSE equity. Indices have no five-level book capability.
- The market-wide `market.quote@1.0` dataset remains separate. A quote snapshot is not ranking, a market scan, or Kline data.

## Request identities

Construct requests with a full `InstrumentId`; code alone is insufficient. The request models check market, kind, exchange, and supported code family.

```python
from finchx.datasets import MarketQuoteSnapshotRequest, MarketOrderbookRequest
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

moutai = InstrumentId(
    code="600519", market=Market.CN_A, exchange=Exchange.SSE,
    kind=InstrumentKind.EQUITY,
)
quote_request = MarketQuoteSnapshotRequest(instrumentId=moutai)
book_request = MarketOrderbookRequest(instrumentId=moutai)
```

An index snapshot is valid, for example `InstrumentId(code="000001", market=Market.CN_A, exchange=Exchange.SSE, kind=InstrumentKind.INDEX)`. Passing that index to `MarketOrderbookRequest` raises a request validation error.

## Shared Tencent source result

`TencentQuoteProvider` uses `qt.gtimg.cn`. One source request and one parser result carry both snapshot and equity book values:

```python
from finchx.providers import TencentQuoteProvider

provider = TencentQuoteProvider()
raw = provider.fetch_raw_quote(quote_request.instrument_id)
# The same raw object can be passed to the quote_snapshot and orderbook
# Dataset normalizers when both records are needed.
```

Provider parsing validates the Tencent response and full requested identity. Dataset normalization converts Tencent hands to whole shares, ten-thousand CNY to CNY, and percentage points to a ratio fraction. There is no implicit second request, cache, collector, fallback, or runtime routing.

## Quote snapshot fields

| Field | Contract meaning |
|---|---|
| `instrumentId` | Full CN A-share identity |
| `price` | Current CNY per share; required |
| `previousClose`, `open`, `high`, `low` | CNY per share |
| `priceChange` | Signed change in CNY per share |
| `changeRate` | Ratio fraction; 3% is `0.03` |
| `volume` | Cumulative session volume in whole shares |
| `amount` | Cumulative session amount in CNY |
| `sourceTimestamp` | Tencent quote timestamp in Asia/Shanghai, separate from envelope `capturedAt`; required |

`price` and `amount` are `Decimal` values encoded as JSON strings. `volume` is a strict whole-share integer. Optional source fields that are absent are serialized as `null`; zero remains a source-provided zero.

## Orderbook fields

Each record contains `instrumentId`, `bids`, and `asks`. A level has:

```json
{"level": 1, "price": "1259.21", "size": 700}
```

`level` preserves the source slot from 1 to 5; `price` is CNY per share; `size` is whole shares. Bids are sorted highest to lowest and asks lowest to highest. A zero price, zero size, or unavailable slot is omitted. A partial real book carries `status=live` and a partial quality issue. If every equity depth slot is zero or absent, the payload has empty arrays with `status=missing`; those arrays do not claim that the market has a real, confirmed empty book.

## Time and status

The source reports a 14-digit timestamp parsed in Asia/Shanghai; direct captures in the trading session and after the 15:00 close showed different source-time ages across instruments. Treat `sourceTimestamp` as Tencent-reported time, not a confirmed trade-event time. `capturedAt` records when FinchX fetched the response. No freshness SLA is defined, so callers should compare these timestamps using their own operating policy; the Dataset does not infer `delayed` from an unverified threshold. A 15:02 equity response returned a valid quote and no book levels; that one sample does not define behavior for halted stocks or all non-trading periods.

## Provenance

The provider ID is `tencent.finance.qq`. Production uses the `qt.gtimg.cn`
endpoint; SQT is not configured as a fallback. Provider parsing and
normalization are covered by the offline test suite.
