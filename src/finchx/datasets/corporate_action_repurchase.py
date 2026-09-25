"""Verified non-empty Tencent jiankuang.huigou repurchase observations."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from finchx.contracts import Amount, Currency, Price, Shares, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.providers.tencent_f10 import _ProviderF10Payload


class RepurchaseRequest(FundamentalRequest):
    pass


class Repurchase(ContractModel):
    repurchase_date: date | None = Field(default=None, alias="repurchaseDate")
    quantity: Shares | None = None
    average_price: Price | None = Field(default=None, alias="averagePrice")
    currency: Currency | None = None
    fund_amount: Amount | None = Field(default=None, alias="fundAmount")
    market: str | None = None


class RepurchaseData(ContractModel):
    symbol: str = Field(min_length=1)
    repurchases: list[Repurchase]


CORPORATE_ACTION_REPURCHASE_DATASET = DatasetDefinition(
    name="corporate_action.repurchase",
    schema_version="1.0",
    request_type=RepurchaseRequest,
    data_type=RepurchaseData,
)


def normalize_repurchase(
    request: RepurchaseRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, RepurchaseRequest):
        raise ValueError("request must be a RepurchaseRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned repurchases for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = RepurchaseData(
        symbol=canonical_symbol(request.instrument_id),
        repurchases=[
            Repurchase(
                repurchaseDate=item.repurchase_date,
                quantity=item.quantity,
                averagePrice=item.average_price,
                currency=item.currency,
                fundAmount=item.fund_amount,
                market=item.market,
            )
            for item in row.repurchases
        ],
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=CORPORATE_ACTION_REPURCHASE_DATASET.name,
        schema_version=CORPORATE_ACTION_REPURCHASE_DATASET.schema_version,
        transformation_version="tencent-jiankuang-repurchase-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "CORPORATE_ACTION_REPURCHASE_DATASET",
    "Repurchase",
    "RepurchaseData",
    "RepurchaseRequest",
    "normalize_repurchase",
]
