"""Stable financial.statement contract and Tonghuashun normalizer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, TYPE_CHECKING

from pydantic import Field

from finchx.contracts import Amount, Currency, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.fundamental_common import FundamentalRequest, canonical_symbol, standardized_fundamental_record
from finchx.entities import InstrumentId

if TYPE_CHECKING:
    from finchx.providers.tonghuashun_financial import _ProviderFinancialStatement


StatementType = Literal["balance_sheet", "income_statement", "cash_flow_statement"]
MissingReason = Literal["null", "false", "empty_string", "special_marker"]


class FinancialStatementRequest(FundamentalRequest):
    statement_type: StatementType = Field(alias="statementType")
    period_end: date | None = Field(default=None, alias="periodEnd")
    max_periods: int | None = Field(default=None, alias="maxPeriods", ge=1)


class FinancialStatementLineItem(ContractModel):
    line_item_id: str = Field(alias="lineItemId", min_length=1)
    source_name: str = Field(alias="sourceName", min_length=1)
    source_unit: str = Field(alias="sourceUnit", min_length=1)
    source_value: str | bool | int | float | None = Field(alias="sourceValue")
    value: Amount | None = None
    currency: Currency | None = None
    missing_reason: MissingReason | None = Field(default=None, alias="missingReason")


class FinancialStatementPeriod(ContractModel):
    period_end: date = Field(alias="periodEnd")
    line_items: list[FinancialStatementLineItem] = Field(alias="lineItems")


class FinancialStatementData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    symbol: str = Field(min_length=1)
    statement_type: StatementType = Field(alias="statementType")
    periods: list[FinancialStatementPeriod]


FINANCIAL_STATEMENT_DATASET: DatasetDefinition[FinancialStatementRequest, FinancialStatementData] = DatasetDefinition(
    name="financial.statement",
    schema_version="1.0",
    request_type=FinancialStatementRequest,
    data_type=FinancialStatementData,
)


_SUFFIXES = (
    ("万亿", Decimal("1000000000000")),
    ("亿", Decimal("100000000")),
    ("万", Decimal("10000")),
)
_SPECIAL_MARKERS = frozenset({"-", "--", "—", "－", "N/A", "n/a"})


def _parse_value(raw: object) -> tuple[Decimal | None, MissingReason | None]:
    if raw is None:
        return None, "null"
    if raw is False:
        return None, "false"
    if isinstance(raw, bool):
        raise ValueError("financial source boolean must be false when used as missing")
    if isinstance(raw, (int, float)):
        text = str(raw)
    elif isinstance(raw, str):
        text = raw.strip()
    else:
        raise ValueError("financial source value must be a scalar")
    if not text:
        return None, "empty_string"
    if text in _SPECIAL_MARKERS:
        return None, "special_marker"
    multiplier = Decimal("1")
    for suffix, factor in _SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            multiplier = factor
            break
    try:
        value = Decimal(text.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"financial source value is not numeric: {raw!r}") from exc
    if not value.is_finite():
        raise ValueError("financial source value must be finite")
    return value * multiplier, None


def _periods(
    request: FinancialStatementRequest,
    row: _ProviderFinancialStatement,
) -> list[FinancialStatementPeriod]:
    section = row.flash_data
    report = section["report"]
    title = section["title"]
    period_labels = report[0]
    periods: list[FinancialStatementPeriod] = []
    for column, label in enumerate(period_labels):
        period_end = date.fromisoformat(label)
        if request.period_end is not None and period_end != request.period_end:
            continue
        line_items: list[FinancialStatementLineItem] = []
        for index in range(1, len(title)):
            source_name = title[index][0].strip()
            source_unit = str(title[index][1]).strip()
            raw_value = report[index][column]
            value, missing_reason = _parse_value(raw_value)
            line_items.append(
                FinancialStatementLineItem(
                    lineItemId=f"tonghuashun:{row.statement_type}:{source_name}",
                    sourceName=source_name,
                    sourceUnit=source_unit or "unknown",
                    sourceValue=raw_value,
                    value=value,
                    currency=Currency.CNY if value is not None else None,
                    missingReason=missing_reason,
                )
            )
        periods.append(FinancialStatementPeriod(periodEnd=period_end, lineItems=line_items))
    if request.period_end is not None and not periods:
        raise ValueError(f"periodEnd {request.period_end.isoformat()} was not present in the source response")
    if request.max_periods is not None:
        periods = periods[: request.max_periods]
    return periods


def normalize_financial_statement(
    request: FinancialStatementRequest,
    row: _ProviderFinancialStatement,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, FinancialStatementRequest):
        raise ValueError("request must be a FinancialStatementRequest")
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned a financial statement for a different instrument")
    if row.statement_type != request.statement_type:
        raise ValueError("provider returned a different statement type")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = FinancialStatementData(
        instrumentId=request.instrument_id,
        symbol=canonical_symbol(request.instrument_id),
        statementType=request.statement_type,
        periods=_periods(request, row),
    )
    return standardized_fundamental_record(
        request=request,
        row=row,
        source=source,
        dataset=FINANCIAL_STATEMENT_DATASET.name,
        schema_version=FINANCIAL_STATEMENT_DATASET.schema_version,
        transformation_version="tonghuashun-financial-statement-normalizer/1",
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "FINANCIAL_STATEMENT_DATASET",
    "FinancialStatementData",
    "FinancialStatementLineItem",
    "FinancialStatementPeriod",
    "FinancialStatementRequest",
    "StatementType",
    "normalize_financial_statement",
]
