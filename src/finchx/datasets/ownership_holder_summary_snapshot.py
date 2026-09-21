"""Current shareholder summary snapshot from Tencent jiankuang.gdgb."""

from __future__ import annotations

from pydantic import Field

from finchx.contracts import Percentage, ShareQuantity, Shares, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.providers.tencent_f10 import _ProviderF10Payload


class HolderSummarySnapshotRequest(FundamentalRequest):
    pass


class HolderSummarySnapshotData(ContractModel):
    symbol: str = Field(min_length=1)
    shareholder_count: Shares | None = Field(default=None, alias="shareholderCount")
    average_shares_per_holder: ShareQuantity | None = Field(
        default=None,
        alias="averageSharesPerHolder",
        description="Exact share count per holder; Tencent rjcg display units are normalized to shares.",
    )
    shareholder_count_change: Percentage | None = Field(
        default=None,
        alias="shareholderCountChange",
        description="Tencent gdrshb, normalized from percentage points to a ratio; not an absolute count delta.",
    )
    top10_float_holder_ratio: Percentage | None = Field(default=None, alias="top10FloatHolderRatio")
    top10_holder_ratio: Percentage | None = Field(default=None, alias="top10HolderRatio")


OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET = DatasetDefinition(
    name="ownership.holder_summary_snapshot",
    schema_version="1.0",
    request_type=HolderSummarySnapshotRequest,
    data_type=HolderSummarySnapshotData,
)


def normalize_holder_summary_snapshot(
    request: HolderSummarySnapshotRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, HolderSummarySnapshotRequest):
        raise ValueError("request must be a HolderSummarySnapshotRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned holder summary for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    summary = row.holder_summary
    data = HolderSummarySnapshotData(
        symbol=canonical_symbol(request.instrument_id),
        shareholderCount=summary.shareholder_count,
        averageSharesPerHolder=summary.average_shares_per_holder,
        shareholderCountChange=summary.shareholder_count_change,
        top10FloatHolderRatio=summary.top10_float_holder_ratio,
        top10HolderRatio=summary.top10_holder_ratio,
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET.name,
        schema_version=OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET.schema_version,
        transformation_version="tencent-jiankuang-holder-summary-snapshot-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "HolderSummarySnapshotData",
    "HolderSummarySnapshotRequest",
    "OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET",
    "normalize_holder_summary_snapshot",
]
