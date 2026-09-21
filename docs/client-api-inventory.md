# FinchX Client API Inventory

The final frozen inventory: every public Dataset has one explicit typed Client
method. Every method returns the existing `FetchResult` envelope; document
search methods return their existing `DocumentRef` tuple inside that envelope.
The version in this table is the current public Dataset schema version.

| Namespace | Method | Dataset | Schema version | Request model | Return contract |
| --- | --- | --- | --- | --- | --- |
| reference | `instrument` | `instrument` | `1.0` | `InstrumentRequest` | `FetchResult[InstrumentData]` |
| reference | `trading_calendar` | `trading_calendar` | `1.0` | `TradingCalendarRequest` | `FetchResult[TradingCalendarData]` |
| market | `breadth` | `market.breadth` | `1.0` | `MarketBreadthRequest` | `FetchResult[MarketBreadthData]` |
| market | `broken_limit_pool` | `market.broken_limit_pool` | `1.0` | `MarketBrokenLimitPoolRequest` | `FetchResult[MarketBrokenLimitPoolData]` |
| market | `consecutive_limit_up` | `market.consecutive_limit_up_snapshot` | `1.0` | `MarketConsecutiveLimitUpRequest` | `FetchResult[MarketConsecutiveLimitUpData]` |
| market | `daily_replay` | `market.daily_replay` | `1.0` | `MarketDailyReplayRequest` | `FetchResult[MarketDailyReplayData]` |
| market | `dragon_tiger_detail` | `market.dragon_tiger_detail` | `1.0` | `MarketDragonTigerDetailRequest` | `FetchResult[MarketDragonTigerDetailData]` |
| market | `dragon_tiger_list` | `market.dragon_tiger_list` | `1.0` | `MarketDragonTigerListRequest` | `FetchResult[MarketDragonTigerListData]` |
| market | `equity_intraday` | `market.equity_intraday` | `1.0` | `EquityIntradayRequest` | `FetchResult[EquityIntradayData]` |
| market | `equity_intraday_5d` | `market.equity_intraday_5d` | `1.0` | `EquityIntraday5dRequest` | `FetchResult[EquityIntradayData]` |
| market | `fund_flow_daily` | `market.fund_flow_daily` | `1.0` | `MarketFundFlowRequest` | `FetchResult[MarketFundFlowDailyData]` |
| market | `fund_flow_intraday` | `market.fund_flow_intraday` | `1.0` | `MarketFundFlowRequest` | `FetchResult[MarketFundFlowIntradayData]` |
| market | `fund_flow_snapshot` | `market.fund_flow_snapshot` | `1.0` | `MarketFundFlowRequest` | `FetchResult[MarketFundFlowSnapshotData]` |
| market | `index_intraday` | `market.index_intraday` | `1.0` | `IndexIntradayRequest` | `FetchResult[IndexIntradayData]` |
| market | `index_intraday_5d` | `market.index_intraday_5d` | `1.0` | `IndexIntraday5dRequest` | `FetchResult[IndexIntradayData]` |
| market | `industry_comparison` | `market.industry_comparison` | `1.0` | `MarketIndustryComparisonRequest` | `FetchResult[MarketIndustryComparisonData]` |
| market | `instrument_sector_snapshot` | `market.instrument_sector_snapshot` | `1.0` | `MarketInstrumentSectorSnapshotRequest` | `FetchResult[MarketInstrumentSectorSnapshotData]` |
| market | `stock_keyword` | `market.stock_keyword` | `1.0` | `MarketStockKeywordRequest` | `FetchResult[MarketStockKeywordData]` |
| market | `ohlcv` | `market.klines` | `1.0` | `KlinesRequest` | `FetchResult[MarketKlineData]` |
| market | `limit_down_pool` | `market.limit_down_pool` | `1.0` | `MarketLimitDownPoolRequest` | `FetchResult[MarketLimitDownPoolData]` |
| market | `limit_up_pool` | `market.limit_up_pool` | `1.0` | `MarketLimitUpPoolRequest` | `FetchResult[MarketLimitUpPoolData]` |
| market | `orderbook` | `market.orderbook` | `1.0` | `MarketOrderbookRequest` | `FetchResult[MarketOrderbookData]` |
| market | `quote` | `market.quote` | `1.0` | `MarketQuoteUniverseRequest` | `FetchResult[MarketQuoteData]` |
| market | `quote_snapshot` | `market.quote_snapshot` | `1.0` | `MarketQuoteSnapshotRequest` | `FetchResult[MarketQuoteSnapshotData]` |
| market | `ranking` | `market.ranking` | `1.0` | `MarketRankingRequest` | `FetchResult[MarketRankingData]` |
| market | `sentiment` | `market.sentiment_snapshot` | `1.0` | `MarketSentimentRequest` | `FetchResult[MarketSentimentData]` |
| market | `strong_pool` | `market.strong_pool` | `1.0` | `MarketStrongPoolRequest` | `FetchResult[MarketStrongPoolData]` |
| market | `yesterday_limit_up_pool` | `market.yesterday_limit_up_pool` | `1.0` | `MarketYesterdayLimitUpPoolRequest` | `FetchResult[MarketYesterdayLimitUpPoolData]` |
| fundamental | `company_profile` | `fundamental.company_profile` | `1.0` | `CompanyProfileRequest` | `FetchResult[CompanyProfileData]` |
| fundamental | `financial_summary` | `fundamental.financial_summary` | `1.0` | `FinancialSummaryRequest` | `FetchResult[FinancialSummaryData]` |
| fundamental | `industry_comparison` | `fundamental.industry_comparison` | `1.0` | `IndustryComparisonRequest` | `FetchResult[IndustryComparisonData]` |
| fundamental | `revenue_breakdown` | `fundamental.revenue_breakdown` | `1.0` | `RevenueBreakdownRequest` | `FetchResult[RevenueBreakdownData]` |
| financial | `statements` | `financial.statement` | `1.0` | `FinancialStatementRequest` | `FetchResult[FinancialStatementData]` |
| news | `search` | `news.document` | `1.0` | `NewsSearchRequest` | `FetchResult[tuple[NewsDocumentRef, ...]]` |
| disclosure | `search` | `disclosure.document` | `1.0` | `DisclosureSearchRequest` | `FetchResult[tuple[DisclosureDocumentRef, ...]]` |
| ownership | `capital_snapshot` | `ownership.capital_snapshot` | `1.0` | `CapitalSnapshotRequest` | `FetchResult[CapitalSnapshotData]` |
| ownership | `float_holder` | `ownership.float_holder` | `1.0` | `FloatHolderRequest` | `FetchResult[FloatHolderData]` |
| ownership | `holder_summary_snapshot` | `ownership.holder_summary_snapshot` | `1.0` | `HolderSummarySnapshotRequest` | `FetchResult[HolderSummarySnapshotData]` |
| company | `executive_share_change` | `company.executive_share_change` | `1.0` | `ExecutiveShareChangeRequest` | `FetchResult[ExecutiveShareChangeData]` |
| company | `executive_snapshot` | `company.executive_snapshot` | `1.0` | `ExecutiveSnapshotRequest` | `FetchResult[ExecutiveSnapshotData]` |
| corporate_action | `dividend` | `corporate_action.dividend` | `1.0` | `DividendRequest` | `FetchResult[DividendData]` |
| corporate_action | `repurchase` | `corporate_action.repurchase` | `1.0` | `RepurchaseRequest` | `FetchResult[RepurchaseData]` |

Source of truth in code: `finchx.client.CLIENT_ENDPOINTS`. The endpoint methods
are written explicitly; the inventory is not used to generate methods. Stage
12.2 final freeze tests protect the namespace/method set and the public method
parameter shape.

## Computed capabilities outside the Dataset inventory

`market.deviation` is a computed capability, not a Provider-backed public
Dataset. It therefore does not add a `CLIENT_ENDPOINTS` entry, Provider
Registry entry, Dataset–Provider pair, or namespace. Its explicit typed Client
method is:

| Namespace | Method | Computed result | Request | Return contract |
| --- | --- | --- | --- | --- |
| market | `deviation` | `market.deviation` computed identity | `InstrumentId` plus optional `windows`, `as_of`, `window_convention`, `provider`, `use_cache` | `FetchResult[DeviationData]` |

The method reuses the existing trading-calendar and Kline capabilities and
keeps their provenance. It creates no `DeviationProvider`; the pure
calculation and frozen rule version are documented in
[`a-share-deviation-rulebook.md`](a-share-deviation-rulebook.md).
