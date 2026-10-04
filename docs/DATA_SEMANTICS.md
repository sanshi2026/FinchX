# Source data semantics

FinchX preserves source observations and applies explicit type/unit normalization.
It does not silently supply business interpretations that the source did not give.
Keep numeric zero distinct from missing/null. `capturedAt` describes acquisition;
it is not a publication date, report period, or a market business timestamp.

| Meaning | Caller guidance |
| --- | --- |
| Target/report period | Annual, single quarter and year-to-date quarter are different. Keep native period labels; a period end alone does not establish the basis. |
| Observation kind | Financial summary/actual statement, company guidance, individual institutional forecast and institutional aggregate are distinct records. |
| Metric | EPS, revenue, net profit and profit attributable to the parent are distinct. Do not relabel net profit as parent-attributable profit without evidence. EPS basic/diluted basis may be unspecified. |
| Amount and unit | Use the endpoint's documented normalized unit. Preserve source name/unit/value where supplied; never infer an undocumented currency from a ticker alone. |
| Date precision | Preserve date-only publication information as date precision; an encoded midnight is not evidence of a precise source clock. |
| Coverage and access | Check `status`, quality, warnings and retrieval metadata. No rows or a successful transport alone does not prove full coverage. |
| Revisions | Keep source record/report identity and publication/acquisition dates when storing history; latest-only replacement is an application storage choice. |

Never divide an annual forecast by four to manufacture quarter estimates, or treat
company guidance as a broker forecast. A quarter without native coverage remains
uncovered. No earnings-forecast endpoint is included in 2.0.3.

## Existing contracts and optional audit information

`FetchResult.to_dicts()` returns business payloads only. Source identity,
provenance, attempts, cache state and result metadata remain on the result/records.
Optional metadata may be absent in older cached records; use guarded access.
Ordinary descriptive notes belong in provenance/metadata, not newly added warnings.
Warnings retain their established failure/partial-result meaning.

`financial.statements` retains `sourceName`, `sourceUnit`, `sourceValue`, normalized
`value`, `currency` and `missingReason` on each line item. The financial summary
endpoint is a different contract: it does not expose original per-metric value
strings or source units and must not be presented as a raw report table.

In 2.0.3, `fundamental.financial_summary` adds the optional
`source_financial_periods` entry to the existing `provenance.adjustments` list.
Its `details.periods` align with the business `periods` list and retain
`reportedPeriodLabel`, nullable `periodEnd`, `periodType` and `sourceFields`
(Python metric names mapped to the provider's input field paths). The source
mapping describes the field used by the provider, including its existing precise
field preference; it does not contain the original raw response/value strings.

`periodBasis`, `netProfitAttribution` and `epsBasis` are explicitly `unspecified`
because the summary contract does not establish single-quarter/cumulative basis,
parent attribution, or basic/diluted EPS. The existing `annual/interim/unknown`
classification and all normalized values remain unchanged; `interim` is not a
promise of single-quarter values. The normalizer transformation version advances
to `/2`, independently of the unchanged Dataset schema `1.0`.

```python
from finchx import FinchX

result = FinchX().fundamental.financial_summary("300308")
rows = result.to_dicts()
record = result.data  # Financial summary returns one StandardRecord.
context = next(
    (a.details for a in record.provenance.adjustments
     if a.name == "source_financial_periods"),
    None,
)
# context is absent on older records; inspect native labels before comparison.
print(context)
```

The `iwencai.select` core/dynamic-column behavior remains unchanged. `extraFields`
holds unrecognized columns; it is not guaranteed to contain the entire source row.
Providers may retain raw responses internally, but no universal raw-response
export or new credential handling is introduced.

Public accessibility and an open-source adapter do not confer redistribution
rights for source data, reports or attachments. Callers must follow source terms
and authorized access boundaries; FinchX does not bypass paywalls or authentication.
