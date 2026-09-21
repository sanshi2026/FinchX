# Fundamental F10 v1

Tencent jiankuang 是一个聚合 endpoint。一次请求由 TencentF10Provider
完整解析，再由四个 Dataset normalizer 消费不同 section；不建立四个重复
HTTP Provider。Provider 每次调用重新请求，没有 cache、Collector、fallback、
storage 或 runtime routing。

## Tencent F10 source bundle

`jiankuang` 是一个完整 Tencent F10 source bundle。四个 Dataset contract 保持独立，但同一 instrument、同一次调用上下文内应通过 `TencentF10Provider.fetch_bundle()` 只获取一次 HTTP payload，然后将同一个已获取 bundle 传给多个 normalizer。Dataset split 表示语义、Schema 和 Canonical contract split，不表示 HTTP acquisition split。

单 Dataset 调用仍只需一次 `jiankuang` 请求；同一次调用同时生成四个
Dataset 也只需一次请求。当前不提供跨调用 persistent cache；下一次独立调用会
重新获取 source bundle。

## Dataset

### fundamental.company_profile@1.0

主要来源 gsjj。data 至少包含 symbol、companyName、businessDescription、issuePrice（CNY/股 Decimal）和 listingDate。symbol 是 FinchX canonical symbol；entityId 仍在 StandardRecord envelope 中。jg 在三个样本上验证为发行价格；dy 保持 raw-only，不猜语义。plate/concept/area 不进入 profile。

### fundamental.financial_summary@1.0

主要来源 zyzb、hydb.stock、hytrend。data 为 symbol + periods[]；每个期间包含 periodEnd、reportedPeriodLabel、periodType，以及 eps、revenue、revenueGrowth、netProfit、netProfitGrowth、bookValuePerShare、netAssets、goodwill、goodwillToNetAssets、roe、debtRatio、grossMargin。当前期 machine numeric 的 hydb.stock 值优先于 zyzb display 值；金额为 CNY Decimal，ratio 字段为百分比除以 100 后的 ratio。hytrend 年度数据并入本 Dataset，不建立 financial_trend。

### fundamental.revenue_breakdown@1.0

主要来源 zysr。data 为 symbol + breakdowns[]；每行包含 reportedPeriodLabel、periodEnd（可靠时）、dimension、itemName、revenue（CNY Decimal）、revenueShare（ratio）、currency=CNY、sourceGroup=detail|others、isRollup。sector 映射为 industry，但不等同于独立的 security sector taxonomy。“其他收入之和”是 detail rollup；others 是 leaf rows，默认 aggregation 不 double count。

### fundamental.industry_comparison@1.0

主要来源 hydb。data 为 symbol、industryName 和 long-form metrics[]。metric 支持 eps、revenue、net_profit、book_value_per_share、roe、debt_ratio、gross_margin、revenue_growth、net_profit_growth、market_cap、pe、pb、dividend_yield。每行包含 metricBasis、companyValue、industryAvg、industryMax、industryMin、reportedPeriodLabel、periodEnd、observationAt。

财务指标使用 metricBasis=financial_period 和 periodEnd；PE/PB/market cap/dividend yield 使用 metricBasis=market_snapshot、periodEnd=null、observationAt=create_time。hymax/hymin 未提供的 metric 为 null，不填零。Tencent industry code/name 与 Tencent plate code/name 不做 join，不创建 SectorAlias。

## 时间、来源与已知限制

StandardRecord 的 capturedAt 表示 FinchX 获取时刻；jiankuang 单独不提供可靠公告发布时间，因此不填 publishedAt/availableAt，也不声称严格 PIT visibility。hydb.create_time 只是 source-side generated/updated timestamp。raw-only sections 不作为本 Dataset 的 public contract；本文件不实现 ownership、executive、insider trade、dividend、repurchase 或 capital return。
