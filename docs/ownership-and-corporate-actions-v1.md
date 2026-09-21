# Ownership and corporate actions v1

公共 Dataset contract。所有 Dataset 都是 `schemaVersion=1.0`；字段语义和
来源边界由本文件及对应 Schema 定义。

## Dataset definitions

| Dataset | 类型 | 来源 | 主要 contract |
|---|---|---|---|
| `ownership.capital_snapshot@1.0` | snapshot | `jiankuang.gdgb` | `symbol`, `totalShares`, `floatShares` |
| `ownership.holder_summary_snapshot@1.0` | snapshot | `jiankuang.gdgb` | shareholder count, average shares, holder concentration ratios |
| `ownership.float_holder@1.0` | historical / PIT | `ltgd/get` | period blocks, published time, ranked rows, previous shares and derived change |
| `company.executive_snapshot@1.0` | snapshot | `jiankuang.ggjj` | executive name, roles, shares, CNY compensation |
| `company.executive_share_change@1.0` | event | `jiankuang.ggzjc` | event date, person, signed share change, average price |
| `corporate_action.dividend@1.0` | event/history | `jiankuang.fhsp` | fiscal year, announcement/record/ex dates, per-ten-share terms, description |
| `corporate_action.repurchase@1.0` | event/history | `jiankuang.huigou` | date, quantity, average price, CNY fund amount, optional market |

No aggregate `ownership.f10` or `company.f10` Dataset is created.

## Time semantics

`capturedAt` is the FinchX acquisition time for every record. jiankuang snapshot Dataset 不填写伪造的 `periodEnd` 或 `publishedAt`。ltgd period blocks carry `periodEnd=pdt` and `publishedAt=dt`; an optional `asOf` on `FloatHolderRequest` is copied to StandardRecord and filters out periods whose published time is later than the cutoff.

`periodEnd` is not a visibility time. A 2026-06-30 holder period published on 2026-08-26 is not visible to an as-of query on 2026-08-25.

## Source bundle reuse

The shared `TencentF10Provider` remains the only jiankuang Provider. A caller may acquire one bundle with `fetch_bundle()` and pass the same payload to all related normalizers in this contract. This is invocation-scoped reuse only: no cache, Collector, storage, registry, scheduler, or cross-call reuse is introduced.

The ltgd Provider is intentionally separate because it is a different Tencent endpoint and response contract. A combined invocation therefore has one jiankuang request plus one ltgd request.

## Units and nullability

- Share counts are integer shares when the source is a count; fractional averages and per-ten-share terms use exact Decimal strings.
- Monetary values are CNY Decimal strings; prices are CNY/share Decimal strings.
- Percentage-point source fields are normalized to ratio fractions.
- `sqcgsl`, `holderId`, source dates represented by `-`, and unavailable optional fields remain null. Null is never replaced by zero.
- Dividend zero values remain zero, so “no distribution” and unavailable values remain distinguishable.

## Deferred source material

`jiankuang.pxmzb` is retained as raw-only because its abbreviations and units
are not sufficiently verified for a stable public Dataset. No capital-return
Dataset is created. Automated research features are outside this contract.
