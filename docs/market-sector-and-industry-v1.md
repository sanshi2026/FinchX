# Market sector snapshot and industry comparison v1

## market.instrument_sector_snapshot@1.0

请求一个完整的 SSE/SZSE A 股 InstrumentId。Provider 每次请求 Tencent plateNew；Dataset 将 area、plate、concept 合并为 sectors：

- area → sectorType=area
- plate → sectorType=industry
- concept → sectorType=concept

每个 entry 包含 sectorName、providerNamespace=tencent_plate、providerSectorId、可选 level/tag 和 changePct。Tencent zdf 是百分比点，FinchX 用 ratio，例如 0.90 → 0.009。tag 空字符串标准化为 null。

所有名称以“昨日”开头的 concept 都不进入公共结果；这是业务过滤，不是 source parser 删除原始字段。当前 Dataset 只有观察时间 capturedAt，不声称历史 membership 生效时间。

## market.industry_comparison@1.0

请求一个完整的 SSE/SZSE A 股 InstrumentId。Provider 每次请求 Tencent hypm，解析 gg_hypm assignment。结果包含：

- industry：providerNamespace=tencent_hypm、providerIndustryId、名称；
- instrumentValues：PE、EPS（CNY/股）、市值（CNY）；
- industryRanks：PE/EPS/市值的 Tencent source rank；
- industryAggregate：行业 count、平均 PE/EPS/市值；
- marketAggregate：沪深市场平均 PE/EPS/市值。

Tencent zsz 与 avg_zsz 的来源单位是亿元，FinchX 乘 100000000 后以 CNY Decimal 输出。sclx 只用于 Provider 的 SSE/SZSE 一致性校验，不作为公共分类字段。

不要将 tencent_plate 与 tencent_hypm 的 ID 直接 join。例如 tencent_plate:01801151 和 tencent_hypm:012021 即使名称接近，也不是同一 ID。当前不提供 SectorAlias 或 SectorMapping。

本 Dataset 是 comparison snapshot，不是行业排行榜列表、valuation truth source 或 fundamental truth source。未来正式 valuation/fundamental Dataset 不能默认以这些 Tencent comparison values 替代。

## 与 market.stock_keyword@1.0 的边界

`market.stock_keyword` 是独立的 EastMoney source-ranked、随时间变化的热门关键词/概念关联。其 `eastmoney_stockrank` namespace、`providerKeywordId`、`hitCount` 和 `calculatedAt` 不与 `tencent_plate` / `tencent_hypm` 做隐式按 ID 或名称 join；`market.instrument_sector_snapshot` 的当前 Tencent 板块关联语义保持不变。

本阶段没有缓存、Collector、storage、TTL、自动 fallback 或 runtime routing policy。
