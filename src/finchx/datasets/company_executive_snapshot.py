"""Current executive snapshot from Tencent jiankuang.ggjj."""

from __future__ import annotations

from pydantic import Field

from finchx.contracts import Amount, Shares, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.providers.tencent_f10 import _ProviderF10Payload


class ExecutiveSnapshotRequest(FundamentalRequest):
    pass


class ExecutiveEntry(ContractModel):
    name: str = Field(min_length=1)
    roles: list[str]
    shares: Shares | None = None
    compensation: Amount | None = None


class ExecutiveSnapshotData(ContractModel):
    symbol: str = Field(min_length=1)
    executives: list[ExecutiveEntry]


COMPANY_EXECUTIVE_SNAPSHOT_DATASET = DatasetDefinition(
    name="company.executive_snapshot",
    schema_version="1.0",
    request_type=ExecutiveSnapshotRequest,
    data_type=ExecutiveSnapshotData,
)


def normalize_executive_snapshot(
    request: ExecutiveSnapshotRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, ExecutiveSnapshotRequest):
        raise ValueError("request must be an ExecutiveSnapshotRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned executives for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = ExecutiveSnapshotData(
        symbol=canonical_symbol(request.instrument_id),
        executives=[
            ExecutiveEntry(
                name=entry.name,
                roles=list(entry.roles),
                shares=entry.shares,
                compensation=entry.compensation,
            )
            for entry in row.executive_snapshots
        ],
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=COMPANY_EXECUTIVE_SNAPSHOT_DATASET.name,
        schema_version=COMPANY_EXECUTIVE_SNAPSHOT_DATASET.schema_version,
        transformation_version="tencent-jiankuang-executive-snapshot-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "COMPANY_EXECUTIVE_SNAPSHOT_DATASET",
    "ExecutiveEntry",
    "ExecutiveSnapshotData",
    "ExecutiveSnapshotRequest",
    "normalize_executive_snapshot",
]
