"""Current share-capital snapshot from Tencent jiankuang.gdgb."""

from __future__ import annotations

from pydantic import Field

from finchx.contracts import Shares, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.providers.tencent_f10 import _ProviderF10Payload


class CapitalSnapshotRequest(FundamentalRequest):
    pass


class CapitalSnapshotData(ContractModel):
    symbol: str = Field(min_length=1)
    total_shares: Shares | None = Field(default=None, alias="totalShares")
    float_shares: Shares | None = Field(default=None, alias="floatShares")


OWNERSHIP_CAPITAL_SNAPSHOT_DATASET = DatasetDefinition(
    name="ownership.capital_snapshot",
    schema_version="1.0",
    request_type=CapitalSnapshotRequest,
    data_type=CapitalSnapshotData,
)


def normalize_capital_snapshot(
    request: CapitalSnapshotRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, CapitalSnapshotRequest):
        raise ValueError("request must be a CapitalSnapshotRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned capital data for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = CapitalSnapshotData(
        symbol=canonical_symbol(request.instrument_id),
        totalShares=row.capital_snapshot.total_shares,
        floatShares=row.capital_snapshot.float_shares,
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=OWNERSHIP_CAPITAL_SNAPSHOT_DATASET.name,
        schema_version=OWNERSHIP_CAPITAL_SNAPSHOT_DATASET.schema_version,
        transformation_version="tencent-jiankuang-capital-snapshot-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "CapitalSnapshotData",
    "CapitalSnapshotRequest",
    "OWNERSHIP_CAPITAL_SNAPSHOT_DATASET",
    "normalize_capital_snapshot",
]
