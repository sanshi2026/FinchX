"""Public query service for financial.statement."""

from __future__ import annotations

from datetime import date

from finchx.datasets.financial_statement import (
    FinancialStatementRequest,
    normalize_financial_statement,
)
from finchx.entities import InstrumentInput, normalize_instrument
from finchx.providers.tonghuashun_financial import TonghuashunFinancialProvider


class FinancialStatementService:
    """Fetch one Tonghuashun response and expose normalized report periods."""

    def __init__(self, provider: TonghuashunFinancialProvider | None = None) -> None:
        self.provider = provider or TonghuashunFinancialProvider()

    def get_statement(
        self,
        instrument: InstrumentInput,
        statement_type: str,
        *,
        period_end: date | None = None,
        max_periods: int | None = None,
    ):
        request = FinancialStatementRequest(
            instrumentId=normalize_instrument(instrument),
            statementType=statement_type,
            periodEnd=period_end,
            maxPeriods=max_periods,
        )
        return normalize_financial_statement(
            request,
            self.provider.fetch_raw_statement(request),
            source=self.provider.source,
        )

    def get(
        self,
        instrument: InstrumentInput,
        statement_type: str,
        *,
        period_end: date | None = None,
        max_periods: int | None = None,
    ):
        return self.get_statement(
            instrument,
            statement_type,
            period_end=period_end,
            max_periods=max_periods,
        )


__all__ = ["FinancialStatementService"]
