"""Client namespace implementation: reference."""

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
    TRADING_CALENDAR_DATASET,
    TradingCalendarRequest,
)
from finchx.entities import (
    Market,
)
from finchx.api._base import (
    _Namespace,
)


class ReferenceNamespace(_Namespace):
    """Reference and identity lookups."""

    def trading_calendar(
        self,
        start_date: date | str,
        end_date: date | str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Return one trading-day flag per natural date in an inclusive A-share range."""

        request = TradingCalendarRequest(
            market=Market.CN_A,
            startDate=start_date,
            endDate=end_date,
        )
        return self._fetch(
            TRADING_CALENDAR_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

# Preserve historical public type identities as implementation moves.
ReferenceNamespace.__module__ = "finchx.client"
