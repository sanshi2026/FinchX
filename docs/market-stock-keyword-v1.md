# `market.stock_keyword@1.0`

`market.stock_keyword` 是一个按完整 `InstrumentId` 请求的、EastMoney
source-provided 的当前个股热门关键词 / 热门概念快照。它表达“来源当前把这只
股票命中到哪些热门概念”，不等同于 `market.instrument_sector_snapshot` 的
当前板块归属关系，也不进行 Tencent/EastMoney 跨源 join。

## Request

```python
from finchx import FinchX
from finchx.datasets import MarketStockKeywordRequest
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

instrument = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = FinchX().market.stock_keyword(
    MarketStockKeywordRequest(instrumentId=instrument),
)
```

Provider-side exchange mapping is explicit: `SSE→SH`, `SZSE→SZ`, `BSE→BJ`.
BSE requests are accepted by the source, but the audited BSE samples returned
the legal empty result `code=0,data=[]`; FinchX does not invent BSE keywords.

## Payload

`FetchResult.data` is the existing `StandardRecord` envelope. Its `data` payload
has `instrumentId` and `keywords`. Each keyword has:

- `keywordName`: EastMoney `conceptName`;
- `providerNamespace`: fixed `eastmoney_stockrank`;
- `providerKeywordId`: EastMoney `conceptId`, retained as source-scoped identity;
- `hitCount`: EastMoney integer hit count, not renamed to `heat`;
- `calculatedAt`: EastMoney `calcTime`, interpreted as `Asia/Shanghai` because the
  source string has no timezone offset.

`capturedAt` remains FinchX's actual Provider capture time and is not substituted
by `calculatedAt`. A successful `keywords=[]` response is a valid empty result.

The source's `flag`, `globalId`, and `stack` are validated only as optional source
fields and are not public Dataset fields. Unknown source fields, missing required
identity/value fields, malformed roots, invalid counts and invalid times are
schema drift. Source non-zero status/code and transport failures remain Provider
errors under the existing Collector error classification.

The public JSON Schema is packaged as
`finchx.schemas/v1/market-stock-keyword.schema.json`.
