"""Client namespace implementation: fundamental."""

from __future__ import annotations

from datetime import (
    date,
)
from finchx.collectors import (
    FetchResult,
)
from finchx.contracts import (
    StandardRecord,
)
from finchx.datasets import (
    FINANCIAL_STATEMENT_DATASET,
    FUNDAMENTAL_COMPANY_PROFILE_DATASET,
    FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,
    FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET,
    FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET,
    CompanyProfileRequest,
    FinancialSummaryRequest,
    FinancialStatementRequest,
    RevenueBreakdownRequest,
)
from finchx.datasets.financial_statement import (
    StatementType,
)
from finchx.datasets.fundamental_industry_comparison import (
    IndustryComparisonRequest as FundamentalIndustryComparisonRequest,
)
from finchx.entities import (
    normalize_instrument,
)
from finchx.api._base import (
    _Namespace,
    _RequestNamespace,
)


class FundamentalNamespace(_RequestNamespace):
    """Company and other source-neutral fundamental lookups."""

    def company_profile(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a company's profile in a FetchResult."""
        request = CompanyProfileRequest(
            instrumentId=normalize_instrument(instrument)
        )
        return self._fetch(
            FUNDAMENTAL_COMPANY_PROFILE_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def financial_summary(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a company's financial summary in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,
            instrument,
            FinancialSummaryRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def industry_comparison(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch the fundamental industry comparison in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET,
            instrument,
            FundamentalIndustryComparisonRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def revenue_breakdown(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a company's revenue breakdown in a FetchResult."""
        return self._fetch_instrument_request(
            FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET,
            instrument,
            RevenueBreakdownRequest,
            provider=provider,
            use_cache=use_cache,
        )


class FinancialNamespace(_Namespace):
    """Financial statement lookups."""

    def statements(
        self,
        instrument: str,
        statement_type: StatementType,
        *,
        period_end: date | str | None = None,
        max_periods: int | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch financial statements in a FetchResult."""
        request = FinancialStatementRequest(
            instrumentId=normalize_instrument(instrument),
            statementType=statement_type,
            periodEnd=period_end,
            maxPeriods=max_periods,
        )
        return self._fetch(
            FINANCIAL_STATEMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

# Preserve historical public type identities as implementation moves.
FundamentalNamespace.__module__ = "finchx.client"
FinancialNamespace.__module__ = "finchx.client"
