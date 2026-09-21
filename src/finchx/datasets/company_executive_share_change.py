"""Executive share-change events from Tencent jiankuang.ggzjc."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from finchx.contracts import Price, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.providers.tencent_f10 import _ProviderF10Payload


class ExecutiveShareChangeRequest(FundamentalRequest):
    pass


class ExecutiveShareChange(ContractModel):
    event_date: date | None = Field(default=None, alias="eventDate")
    person_name: str | None = Field(default=None, alias="personName")
    share_change: int | None = Field(default=None, alias="shareChange", strict=True)
    average_price: Price | None = Field(default=None, alias="averagePrice")


class ExecutiveShareChangeData(ContractModel):
    symbol: str = Field(min_length=1)
    changes: list[ExecutiveShareChange]


COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET = DatasetDefinition(
    name="company.executive_share_change",
    schema_version="1.0",
    request_type=ExecutiveShareChangeRequest,
    data_type=ExecutiveShareChangeData,
)


def normalize_executive_share_change(
    request: ExecutiveShareChangeRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, ExecutiveShareChangeRequest):
        raise ValueError("request must be an ExecutiveShareChangeRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned executive share changes for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = ExecutiveShareChangeData(
        symbol=canonical_symbol(request.instrument_id),
        changes=[
            ExecutiveShareChange(
                eventDate=change.event_date,
                personName=change.person_name,
                shareChange=change.share_change,
                averagePrice=change.average_price,
            )
            for change in row.executive_share_changes
        ],
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET.name,
        schema_version=COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET.schema_version,
        transformation_version="tencent-jiankuang-executive-share-change-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET",
    "ExecutiveShareChange",
    "ExecutiveShareChangeData",
    "ExecutiveShareChangeRequest",
    "normalize_executive_share_change",
]
