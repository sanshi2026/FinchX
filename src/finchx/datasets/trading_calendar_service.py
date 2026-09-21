"""Default source selection and whole-request fallback for trading_calendar."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Callable

from pydantic import ValidationError

from finchx.contracts import StandardRecord
from finchx.datasets.trading_calendar import (
    TradingCalendarRequest,
    _ProviderCalendarDay,
    _normalize_calendar_rows,
)
from finchx.providers.errors import ProviderError
from finchx.providers.trading_calendar import (
    PmcTradingCalendarProvider,
    SzseTradingCalendarProvider,
    TradingCalendarProvider,
    _CalendarTransport,
)


class TradingCalendarService:
    """Fetch the canonical calendar, using PMC for a whole-request fallback."""

    def __init__(
        self,
        *,
        primary_provider: TradingCalendarProvider | None = None,
        fallback_provider: TradingCalendarProvider | None = None,
        primary_transport: _CalendarTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if primary_provider is not None and primary_transport is not None:
            raise ValueError("provide either primary_provider or primary_transport, not both")
        self._primary = (
            primary_provider
            if primary_provider is not None
            else SzseTradingCalendarProvider(transport=primary_transport, clock=clock)
        )
        self._fallback = (
            fallback_provider
            if fallback_provider is not None
            else PmcTradingCalendarProvider(clock=clock)
        )

    @staticmethod
    def _records(
        provider: TradingCalendarProvider,
        request: TradingCalendarRequest,
    ) -> tuple[StandardRecord, ...]:
        rows: Sequence[_ProviderCalendarDay] = provider.get_calendar(request)
        try:
            return _normalize_calendar_rows(
                request,
                rows,
                source=provider.source,
            )
        except ProviderError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise ProviderError(
                provider.source,
                f"provider output failed canonical range validation ({type(exc).__name__})",
            ) from exc

    def get_calendar(
        self,
        request: TradingCalendarRequest,
    ) -> tuple[StandardRecord, ...]:
        """Return a complete inclusive range from one source only."""

        if not isinstance(request, TradingCalendarRequest):
            raise TypeError("request must be a TradingCalendarRequest")
        try:
            return self._records(self._primary, request)
        except ProviderError as primary_error:
            try:
                return self._records(self._fallback, request)
            except ProviderError as fallback_error:
                raise ProviderError(
                    self._fallback.source,
                    "primary failed "
                    f"({self._primary.source.provider_id}: {primary_error.reason}); "
                    "whole-request fallback failed "
                    f"({self._fallback.source.provider_id}: {fallback_error.reason})",
                ) from fallback_error
