"""Dividend and capitalization actions from Tencent jiankuang.fhsp."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from finchx.contracts import Amount, ShareQuantity, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.providers.tencent_f10 import _ProviderF10Payload


class DividendRequest(FundamentalRequest):
    pass


class Dividend(ContractModel):
    fiscal_year: int | None = Field(default=None, alias="fiscalYear", strict=True)
    announcement_date: date | None = Field(default=None, alias="announcementDate")
    stock_dividend_per_10: ShareQuantity | None = Field(default=None, alias="stockDividendPer10")
    capitalization_per_10: ShareQuantity | None = Field(default=None, alias="capitalizationPer10")
    cash_dividend_per_10: Amount | None = Field(default=None, alias="cashDividendPer10")
    rights_issue_per_10: ShareQuantity | None = Field(default=None, alias="rightsIssuePer10")
    record_date: date | None = Field(default=None, alias="recordDate")
    ex_date: date | None = Field(default=None, alias="exDate")
    description: str | None = None


class DividendData(ContractModel):
    symbol: str = Field(min_length=1)
    dividends: list[Dividend]


CORPORATE_ACTION_DIVIDEND_DATASET = DatasetDefinition(
    name="corporate_action.dividend",
    schema_version="1.0",
    request_type=DividendRequest,
    data_type=DividendData,
)


def normalize_dividend(
    request: DividendRequest,
    row: _ProviderF10Payload,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, DividendRequest):
        raise ValueError("request must be a DividendRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned dividends for a different instrument")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = DividendData(
        symbol=canonical_symbol(request.instrument_id),
        dividends=[
            Dividend(
                fiscalYear=item.fiscal_year,
                announcementDate=item.announcement_date,
                stockDividendPer10=item.stock_dividend_per_10,
                capitalizationPer10=item.capitalization_per_10,
                cashDividendPer10=item.cash_dividend_per_10,
                rightsIssuePer10=item.rights_issue_per_10,
                recordDate=item.record_date,
                exDate=item.ex_date,
                description=item.description,
            )
            for item in row.dividends
        ],
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=CORPORATE_ACTION_DIVIDEND_DATASET.name,
        schema_version=CORPORATE_ACTION_DIVIDEND_DATASET.schema_version,
        transformation_version="tencent-jiankuang-dividend-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "CORPORATE_ACTION_DIVIDEND_DATASET",
    "Dividend",
    "DividendData",
    "DividendRequest",
    "normalize_dividend",
]
