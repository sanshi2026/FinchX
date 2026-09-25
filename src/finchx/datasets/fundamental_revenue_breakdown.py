"""Principal revenue breakdown from Tencent jiankuang.zysr."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from finchx.contracts import (
    Amount,
    Currency,
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
from finchx.providers.tencent_f10 import _ProviderF10Payload, _RevenueRow


class RevenueBreakdownRequest(FundamentalRequest):
    pass


class RevenueBreakdownRow(ContractModel):
    reported_period_label: str = Field(alias="reportedPeriodLabel", min_length=1)
    period_end: date | None = Field(default=None, alias="periodEnd")
    dimension: Literal["product", "region", "industry"]
    item_name: str = Field(alias="itemName", min_length=1)
    revenue: Amount | None
    revenue_share: Percentage | None = Field(default=None, alias="revenueShare")
    currency: Literal["CNY"]
    source_group: Literal["detail", "others"] = Field(alias="sourceGroup")
    is_rollup: bool = Field(alias="isRollup")


class RevenueBreakdownData(ContractModel):
    symbol: str = Field(min_length=1)
    breakdowns: list[RevenueBreakdownRow]


FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET = DatasetDefinition(
    name="fundamental.revenue_breakdown",
    schema_version="1.0",
    request_type=RevenueBreakdownRequest,
    data_type=RevenueBreakdownData,
)


def _aware(captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")


def _row_model(row: _RevenueRow) -> RevenueBreakdownRow:
    return RevenueBreakdownRow(
        reportedPeriodLabel=row.reported_period_label,
        periodEnd=row.period_end,
        dimension=row.dimension,
        itemName=row.item_name,
        revenue=row.revenue,
        revenueShare=row.revenue_share,
        currency=Currency.CNY,
        sourceGroup=row.source_group,
        isRollup=row.is_rollup,
    )


def normalize_revenue_breakdown(
    request: RevenueBreakdownRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, RevenueBreakdownRequest):
        raise ValueError("request must be a RevenueBreakdownRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned revenue breakdown for a different instrument")
    _aware(row.captured_at)
    data = RevenueBreakdownData(
        symbol=canonical_symbol(request.instrument_id),
        breakdowns=[_row_model(item) for item in row.revenue_rows],
    )
    return StandardRecord(
        dataset=FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET.name,
        schemaVersion=FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET.schema_version,
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
            transformationVersion="tencent-jiankuang-revenue-breakdown-normalizer/1",
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
    "FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET",
    "RevenueBreakdownData",
    "RevenueBreakdownRequest",
    "RevenueBreakdownRow",
    "normalize_revenue_breakdown",
]
