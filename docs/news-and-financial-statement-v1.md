# Market news and financial statements v1

更新日期：2026-09-20

## Dataset

本 contract 继续使用既有 `news.document@1.0` 与 `DocumentRef → Full Document`
模型；市场级 7×24 新闻通过 `MarketNewsService` 扩展，不另建新闻 Dataset。

新增的市场新闻能力：

- EastMoney、爱股票、百度 Finscope 三个 source adapter。
- `MarketNewsSearchRequest` 支持有界 page/pageSize、cursor、since/until、published_desc/published_asc 和 maxResults。
- `MarketNewsService.search()` 返回可序列化 `NewsDocumentRef`；`get_document(ref)` 和 `get_documents(refs)` 获取完整正文。
- `sourceOccurrences` 与 provenance.sourceReferences 保留去重前各来源的 source id、来源 URL、正文 URL、发布时间和捕获时间。
- 同来源按 source id；跨来源仅在标题与正文经过 NFKC/HTML/空白规范化后完全一致且发布时间相差不超过 10 分钟时合并。没有 embedding、LLM、模糊阈值或 Provider priority。标题相同但正文不同不会合并。

Aigupiao 没有可靠正式标题字段；当前 public title 是可解释的首个 `【...】` 标题派生（否则使用正文前 80 个字符），并在 provenance adjustment 中记录。来源明确提供的证券关系保留；不做 NLP 证券识别。

## financial.statement@1.0

公共请求必须传入完整的 FinchX `InstrumentId`，不能传裸代码：

```python
FinancialStatementRequest(
    instrumentId=InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    ),
    statementType="balance_sheet",
)
```

公共 statement type：

- `balance_sheet`：Tonghuashun source token `debt`
- `income_statement`：source token `benefit`
- `cash_flow_statement`：source token `cash`

`FinancialStatementService.get_statement()` 只请求对应报表一次；一次响应中的全部历史报告期由 normalizer 处理。可按 `periodEnd` 精确选择一个报告期，或用 `maxPeriods` 限制返回期数。

每个 line item 保留：

- 稳定的 source-scoped `lineItemId`
- 原始 `sourceName`、`sourceUnit`、`sourceValue`
- 标准化 CNY `value`（Decimal wire string）和 `currency`
- 缺失原因：`null`、`false`、`empty_string`、`special_marker`

不翻译、合并或猜测会计科目；source 新增科目保留并可由 schema-drift 检测。Provider 保留完整 raw payload，但 raw wire fields 不作为公共 Dataset contract。

Tonghuashun 当前 endpoint 没有可靠披露日期、历史 revision 或 restatement 时间。因此：

- `periodEnd` 是报告期末，不是披露时间。
- `publishedAt` 和 `asOf` 不伪造，保持 null。
- `capturedAt` 只表示 FinchX 本次抓取时间。
- 当前 contract 不宣称真正 point-in-time 财报查询。

## 明确不属于本阶段

Automated research agent、LLM、新闻摘要/情绪/NLP/embedding、通用 Collector、
cache、storage、scheduler、fallback、Provider priority、财务指标计算、估值模型、
PDF/OCR、FastAPI、CLI、MCP、Docker、Redis、Kafka 和下游应用修改均不在范围内。
