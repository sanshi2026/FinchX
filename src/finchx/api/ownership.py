"""Client namespace implementation: ownership."""

from __future__ import annotations

from finchx.collectors import (
    FetchResult,
)
from finchx.contracts import (
    StandardRecord,
)
from finchx.datasets import (
    COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET,
    COMPANY_EXECUTIVE_SNAPSHOT_DATASET,
    CORPORATE_ACTION_DIVIDEND_DATASET,
    CORPORATE_ACTION_REPURCHASE_DATASET,
    OWNERSHIP_CAPITAL_SNAPSHOT_DATASET,
    OWNERSHIP_FLOAT_HOLDER_DATASET,
    OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET,
    CapitalSnapshotRequest,
    DividendRequest,
    ExecutiveShareChangeRequest,
    ExecutiveSnapshotRequest,
    FloatHolderRequest,
    HolderSummarySnapshotRequest,
    RepurchaseRequest,
)
from finchx.api._base import (
    _RequestNamespace,
)


class OwnershipNamespace(_RequestNamespace):
    """Shareholding and ownership snapshots."""

    def capital_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a capital snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_CAPITAL_SNAPSHOT_DATASET,
            instrument,
            CapitalSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def float_holder(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch floating-holder data in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_FLOAT_HOLDER_DATASET,
            instrument,
            FloatHolderRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def holder_summary_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch a holder-summary snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET,
            instrument,
            HolderSummarySnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )


class CompanyNamespace(_RequestNamespace):
    """Company management and executive data."""

    def executive_snapshot(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch an executive snapshot in a FetchResult."""
        return self._fetch_instrument_request(
            COMPANY_EXECUTIVE_SNAPSHOT_DATASET,
            instrument,
            ExecutiveSnapshotRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def executive_share_change(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch executive share changes in a FetchResult."""
        return self._fetch_instrument_request(
            COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET,
            instrument,
            ExecutiveShareChangeRequest,
            provider=provider,
            use_cache=use_cache,
        )


class CorporateActionNamespace(_RequestNamespace):
    """Dividend and repurchase observations."""

    def dividend(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch dividend actions in a FetchResult."""
        return self._fetch_instrument_request(
            CORPORATE_ACTION_DIVIDEND_DATASET,
            instrument,
            DividendRequest,
            provider=provider,
            use_cache=use_cache,
        )

    def repurchase(
        self,
        instrument: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch repurchase actions in a FetchResult."""
        return self._fetch_instrument_request(
            CORPORATE_ACTION_REPURCHASE_DATASET,
            instrument,
            RepurchaseRequest,
            provider=provider,
            use_cache=use_cache,
        )

# Preserve historical public type identities as implementation moves.
OwnershipNamespace.__module__ = "finchx.client"
CompanyNamespace.__module__ = "finchx.client"
CorporateActionNamespace.__module__ = "finchx.client"
