"""Financial-period and market-snapshot comparison rows from Tencent hydb."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from finchx.contracts import (
    Amount,
    DataStatus,
    Percentage,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    SourceReference,
    StandardRecord,
    ValuationMultiple,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol
from finchx.providers.tencent_f10 import _IndustryComparison, _ProviderF10Payload


class IndustryComparisonRequest(FundamentalRequest):
    pass


MetricValue = Amount | Percentage | ValuationMultiple
MetricName = Literal[
    "eps",
    "revenue",
    "net_profit",
    "book_value_per_share",
    "roe",
    "debt_ratio",
    "gross_margin",
    "revenue_growth",
    "net_profit_growth",
    "market_cap",
    "pe",
    "pb",
    "dividend_yield",
]


class IndustryComparisonMetric(ContractModel):
    metric: MetricName
    metric_basis: Literal["financial_period", "market_snapshot"] = Field(alias="metricBasis")
    company_value: MetricValue | None = Field(default=None, alias="companyValue")
    industry_avg: MetricValue | None = Field(default=None, alias="industryAvg")
    industry_max: MetricValue | None = Field(default=None, alias="industryMax")
    industry_min: MetricValue | None = Field(default=None, alias="industryMin")
    period_end: date | None = Field(default=None, alias="periodEnd")
    reported_period_label: str = Field(alias="reportedPeriodLabel", min_length=1)
    observation_at: datetime | None = Field(default=None, alias="observationAt")


class IndustryComparisonData(ContractModel):
    symbol: str = Field(min_length=1)
    industry_name: str | None = Field(default=None, alias="industryName")
    metrics: list[IndustryComparisonMetric]


FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET = DatasetDefinition(
    name="fundamental.industry_comparison",
    schema_version="1.0",
    request_type=IndustryComparisonRequest,
    data_type=IndustryComparisonData,
)


_FINANCIAL_METRICS = (
    "eps", "revenue", "net_profit", "book_value_per_share", "roe", "debt_ratio",
    "gross_margin", "revenue_growth", "net_profit_growth",
)
_MARKET_METRICS = ("market_cap", "pe", "pb", "dividend_yield")


def _aware(captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")


def _metric_model(
    comparison: _IndustryComparison,
    metric: str,
    *,
    financial: bool,
) -> IndustryComparisonMetric:
    company = comparison.company.get(metric)
    average = comparison.industry_average.get(metric)
    maximum = comparison.industry_max.get(metric)
    minimum = comparison.industry_min.get(metric)
    return IndustryComparisonMetric(
        metric=metric,
        metricBasis="financial_period" if financial else "market_snapshot",
        companyValue=company,
        industryAvg=average,
        industryMax=maximum,
        industryMin=minimum,
        periodEnd=comparison.period_end if financial else None,
        reportedPeriodLabel=comparison.reported_period_label,
        observationAt=None if financial else comparison.source_updated_at,
    )


def normalize_industry_comparison(
    request: IndustryComparisonRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, IndustryComparisonRequest):
        raise ValueError("request must be an IndustryComparisonRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned industry comparison for a different instrument")
    _aware(row.captured_at)
    comparison = row.industry_comparison
    if comparison is None:
        raise ValueError("Tencent jiankuang hydb comparison is missing")
    metrics = [
        _metric_model(comparison, metric, financial=True) for metric in _FINANCIAL_METRICS
    ] + [
        _metric_model(comparison, metric, financial=False) for metric in _MARKET_METRICS
    ]
    data = IndustryComparisonData(
        symbol=canonical_symbol(request.instrument_id),
        industryName=comparison.industry_name,
        metrics=metrics,
    )
    return StandardRecord(
        dataset=FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET.name,
        schemaVersion=FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET.schema_version,
        recordId=f"{canonical_symbol(request.instrument_id)}@{row.captured_at.isoformat()}",
        entityId=request.instrument_id,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url or source.source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="tencent-jiankuang-industry-comparison-normalizer/1",
            sourceReferences=[
                SourceReference(
                    providerId=source.provider_id,
                    sourceRecordId=row.source_record_id,
                    sourceUrl=row.source_url or source.source_url,
                )
            ],
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET",
    "IndustryComparisonData",
    "IndustryComparisonMetric",
    "IndustryComparisonRequest",
    "normalize_industry_comparison",
]
