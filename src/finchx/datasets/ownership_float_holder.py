"""Historical top float-holder observations from Tencent ltgd/get."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field, field_validator

from finchx.contracts import Percentage, Shares, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.providers.tencent_float_holder import (
    _FloatHolderPeriod,
    _FloatHolderRow,
    _ProviderFloatHolderPayload,
)


class FloatHolderRequest(FundamentalRequest):
    as_of: datetime | None = Field(default=None, alias="asOf")

    @field_validator("as_of")
    @classmethod
    def as_of_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("asOf must include a timezone offset")
        return value


class FloatHolderRow(ContractModel):
    rank: int = Field(ge=1, strict=True, description="Derived from Tencent rows array order.")
    holder_id: str | None = Field(default=None, alias="holderId")
    holder_name: str = Field(alias="holderName", min_length=1)
    shares: Shares
    holder_type: str = Field(alias="holderType", min_length=1)
    float_share_ratio: Percentage | None = Field(default=None, alias="floatShareRatio")
    previous_shares: Shares | None = Field(default=None, alias="previousShares")
    share_change: int | None = Field(default=None, alias="shareChange", strict=True)
    is_new_top_float_holder_entry: bool | None = Field(
        default=None,
        alias="isNewTopFloatHolderEntry",
        description="Derived from bdms=1 after multi-stock adjacent-period validation.",
    )


class FloatHolderPeriod(ContractModel):
    period_end: date = Field(alias="periodEnd")
    published_at: datetime = Field(alias="publishedAt")
    rows: list[FloatHolderRow]

    @field_validator("published_at")
    @classmethod
    def published_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("publishedAt must include a timezone offset")
        return value


class FloatHolderData(ContractModel):
    symbol: str = Field(min_length=1)
    periods: list[FloatHolderPeriod]


OWNERSHIP_FLOAT_HOLDER_DATASET = DatasetDefinition(
    name="ownership.float_holder",
    schema_version="1.0",
    request_type=FloatHolderRequest,
    data_type=FloatHolderData,
)


def _row_model(row: _FloatHolderRow, rank: int) -> FloatHolderRow:
    previous_shares = row.previous_shares
    return FloatHolderRow(
        rank=rank,
        holderId=row.holder_id,
        holderName=row.holder_name,
        shares=row.shares,
        holderType=row.holder_type,
        floatShareRatio=row.float_share_ratio,
        previousShares=previous_shares,
        shareChange=None if previous_shares is None else row.shares - previous_shares,
        isNewTopFloatHolderEntry=None if row.bdms is None else row.bdms == 1,
    )


def _period_model(period: _FloatHolderPeriod) -> FloatHolderPeriod:
    return FloatHolderPeriod(
        periodEnd=period.period_end,
        publishedAt=period.published_at,
        rows=[_row_model(row, rank) for rank, row in enumerate(period.rows, start=1)],
    )


def normalize_float_holder(
    request: FloatHolderRequest,
    row: _ProviderFloatHolderPayload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, FloatHolderRequest):
        raise ValueError("request must be a FloatHolderRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned float holders for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    periods = [
        _period_model(period)
        for period in row.periods
        if request.as_of is None or period.published_at <= request.as_of
    ]
    data = FloatHolderData(
        symbol=canonical_symbol(request.instrument_id),
        periods=periods,
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=OWNERSHIP_FLOAT_HOLDER_DATASET.name,
        schema_version=OWNERSHIP_FLOAT_HOLDER_DATASET.schema_version,
        transformation_version="tencent-ltgd-float-holder-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
        as_of=request.as_of,
    )


__all__ = [
    "FloatHolderData",
    "FloatHolderPeriod",
    "FloatHolderRequest",
    "FloatHolderRow",
    "OWNERSHIP_FLOAT_HOLDER_DATASET",
    "normalize_float_holder",
]
