"""Unified company financial-period summary from Tencent jiankuang."""

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
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol
from finchx.providers.tencent_f10 import _FinancialPeriod, _ProviderF10Payload


class FinancialSummaryRequest(FundamentalRequest):
    pass


class FinancialSummaryPeriod(ContractModel):
    period_end: date | None = Field(default=None, alias="periodEnd")
    reported_period_label: str = Field(alias="reportedPeriodLabel", min_length=1)
    period_type: Literal["annual", "interim", "unknown"] = Field(alias="periodType")
    eps: Amount | None = None
    revenue: Amount | None = None
    revenue_growth: Percentage | None = Field(default=None, alias="revenueGrowth")
    net_profit: Amount | None = Field(default=None, alias="netProfit")
    net_profit_growth: Percentage | None = Field(default=None, alias="netProfitGrowth")
    book_value_per_share: Amount | None = Field(default=None, alias="bookValuePerShare")
    net_assets: Amount | None = Field(default=None, alias="netAssets")
    goodwill: Amount | None = None
    goodwill_to_net_assets: Percentage | None = Field(default=None, alias="goodwillToNetAssets")
    roe: Percentage | None = None
    debt_ratio: Percentage | None = Field(default=None, alias="debtRatio")
    gross_margin: Percentage | None = Field(default=None, alias="grossMargin")


class FinancialSummaryData(ContractModel):
    symbol: str = Field(min_length=1)
    periods: list[FinancialSummaryPeriod]


FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET = DatasetDefinition(
    name="fundamental.financial_summary",
    schema_version="1.0",
    request_type=FinancialSummaryRequest,
    data_type=FinancialSummaryData,
)


def _aware(captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")


def _period_model(row: _FinancialPeriod) -> FinancialSummaryPeriod:
    return FinancialSummaryPeriod(
        periodEnd=row.period_end,
        reportedPeriodLabel=row.reported_period_label,
        periodType=row.period_type,
        eps=row.metrics.get("eps"),
        revenue=row.metrics.get("revenue"),
        revenueGrowth=row.metrics.get("revenue_growth"),
        netProfit=row.metrics.get("net_profit"),
        netProfitGrowth=row.metrics.get("net_profit_growth"),
        bookValuePerShare=row.metrics.get("book_value_per_share"),
        netAssets=row.metrics.get("net_assets"),
        goodwill=row.metrics.get("goodwill"),
        goodwillToNetAssets=row.metrics.get("goodwill_to_net_assets"),
        roe=row.metrics.get("roe"),
        debtRatio=row.metrics.get("debt_ratio"),
        grossMargin=row.metrics.get("gross_margin"),
    )


def normalize_financial_summary(
    request: FinancialSummaryRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, FinancialSummaryRequest):
        raise ValueError("request must be a FinancialSummaryRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned financial summary for a different instrument")
    _aware(row.captured_at)
    periods: list[FinancialSummaryPeriod] = []
    if row.current_financial is not None:
        periods.append(_period_model(row.current_financial))
    periods.extend(_period_model(item) for item in row.historical_financial)
    data = FinancialSummaryData(
        symbol=canonical_symbol(request.instrument_id),
        periods=periods,
    )
    return StandardRecord(
        dataset=FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET.name,
        schemaVersion=FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET.schema_version,
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
            transformationVersion="tencent-jiankuang-financial-summary-normalizer/1",
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
    "FinancialSummaryData",
    "FinancialSummaryPeriod",
    "FinancialSummaryRequest",
    "FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET",
    "normalize_financial_summary",
]
