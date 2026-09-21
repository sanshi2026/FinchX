"""SZSE official and pandas_market_calendars adapters for trading_calendar."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
import calendar as month_calendar
import json
import re
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from finchx.contracts import Source
from finchx.datasets.trading_calendar import (
    TradingCalendarRequest,
    _ProviderCalendarDay,
)
from finchx.entities import Market
from finchx.providers.errors import ProviderError
from finchx.providers.http import (
    DEFAULT_TIMEOUT_SECONDS,
    build_headers,
    http_status_failure_reason,
)


SZSE_CALENDAR_ENDPOINT = (
    "https://www.szse.cn/api/report/exchange/onepersistenthour/monthList"
)
PMC_CALENDAR_NAME = "SSE"
_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
_HEADERS = build_headers(referer="https://www.szse.cn/aboutus/calendar/")
_ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


@dataclass(frozen=True)
class _CalendarHttpResponse:
    status_code: int
    body: bytes


class _CalendarTransport(Protocol):
    """Small injectable HTTP seam used by the official provider."""

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _CalendarHttpResponse: ...


class _TransportFailure(RuntimeError):
    pass


class _UrllibCalendarTransport:
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _CalendarHttpResponse:
        request_url = f"{url}?{urlencode(params)}"
        request = Request(request_url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return _CalendarHttpResponse(
                    status_code=int(response.status),
                    body=response.read(),
                )
        except HTTPError as exc:
            return _CalendarHttpResponse(status_code=int(exc.code), body=b"")
        except (URLError, TimeoutError, OSError) as exc:
            raise _TransportFailure(type(exc).__name__) from exc


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _require_capture_time(value: datetime, provider_id: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        source = Source(providerId=provider_id)
        raise ProviderError(source, "capture clock must return a timezone-aware datetime")
    return value


def _month_sequence(start: date, end: date) -> tuple[tuple[int, int], ...]:
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return tuple(months)


def _expected_month_dates(year: int, month: int) -> set[date]:
    last_day = month_calendar.monthrange(year, month)[1]
    return {date(year, month, day) for day in range(1, last_day + 1)}


def _parse_szse_month(
    body: bytes,
    *,
    year: int,
    month: int,
    source: Source,
) -> dict[date, bool]:
    month_label = f"{year:04d}-{month:02d}"
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise ProviderError(source, f"invalid JSON for month {month_label}") from exc

    if not isinstance(payload, dict):
        raise ProviderError(source, f"invalid envelope for month {month_label}")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise ProviderError(source, f"missing calendar list for month {month_label}")

    expected = _expected_month_dates(year, month)
    parsed: dict[date, bool] = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ProviderError(
                source,
                f"invalid envelope row {position} for month {month_label}",
            )
        raw_date = row.get("jyrq")
        if not isinstance(raw_date, str) or _ISO_DATE.fullmatch(raw_date) is None:
            raise ProviderError(
                source,
                f"invalid date at row {position} for month {month_label}",
            )
        try:
            day = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ProviderError(
                source,
                f"invalid date at row {position} for month {month_label}",
            ) from exc
        if day.year != year or day.month != month:
            raise ProviderError(
                source,
                f"month mismatch for month {month_label}: received {day.isoformat()}",
            )
        if day in parsed:
            raise ProviderError(
                source,
                f"duplicate date {day.isoformat()} for month {month_label}",
            )
        flag = row.get("jybz")
        if not isinstance(flag, str) or flag not in {"0", "1"}:
            raise ProviderError(
                source,
                f"invalid trading flag for {day.isoformat()}",
            )
        parsed[day] = flag == "1"

    missing = expected - set(parsed)
    if missing:
        first_missing = min(missing)
        raise ProviderError(
            source,
            f"missing date(s) for month {month_label}: {len(missing)}, "
            f"first {first_missing.isoformat()}",
        )
    return parsed


class TradingCalendarProvider(Protocol):
    """Capability to return every natural date in a requested range."""

    @property
    def source(self) -> Source: ...

    def get_calendar(
        self,
        request: TradingCalendarRequest,
    ) -> Sequence[_ProviderCalendarDay]: ...


class SzseTradingCalendarProvider:
    """Fetch and validate explicit daily flags from the SZSE monthly endpoint."""

    def __init__(
        self,
        transport: _CalendarTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport or _UrllibCalendarTransport()
        self._clock = clock or _default_clock
        self._source = Source(
            providerId="szse.official.calendar",
            sourceUrl=SZSE_CALENDAR_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def get_calendar(
        self,
        request: TradingCalendarRequest,
    ) -> tuple[_ProviderCalendarDay, ...]:
        if not isinstance(request, TradingCalendarRequest):
            raise TypeError("request must be a TradingCalendarRequest")
        if request.market is not Market.CN_A:
            raise ProviderError(self.source, "unsupported market; expected Market.CN_A")

        all_rows: dict[date, _ProviderCalendarDay] = {}
        for year, month in _month_sequence(request.start_date, request.end_date):
            month_label = f"{year:04d}-{month:02d}"
            try:
                response = self._transport.get(
                    SZSE_CALENDAR_ENDPOINT,
                    params={"month": month_label},
                    headers=_HEADERS,
                    timeout_seconds=_TIMEOUT_SECONDS,
                )
            except _TransportFailure as exc:
                raise ProviderError(
                    self.source,
                    f"transport failure for month {month_label} ({exc})",
                ) from exc
            except Exception as exc:
                raise ProviderError(
                    self.source,
                    f"transport failure for month {month_label} ({type(exc).__name__})",
                ) from exc

            captured_at = _require_capture_time(self._clock(), self.source.provider_id)
            status_reason = http_status_failure_reason(response.status_code)
            if status_reason is not None:
                raise ProviderError(
                    self.source,
                    f"HTTP failure for month {month_label} ({status_reason})",
                )
            month_flags = _parse_szse_month(
                response.body,
                year=year,
                month=month,
                source=self.source,
            )
            for day, is_trading_day in month_flags.items():
                all_rows[day] = _ProviderCalendarDay(
                    date=day,
                    is_trading_day=is_trading_day,
                    captured_at=captured_at,
                )

        first = request.start_date
        last = request.end_date
        selected = tuple(
            row
            for day, row in sorted(all_rows.items())
            if first <= day <= last
        )
        expected_count = (last - first).days + 1
        if len(selected) != expected_count:
            raise ProviderError(
                self.source,
                f"range incomplete after monthly merge: expected {expected_count}, got {len(selected)}",
            )
        return selected


class PmcTradingCalendarProvider:
    """Expand the installed pandas_market_calendars SSE sessions to natural dates."""

    calendar_name = PMC_CALENDAR_NAME

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or _default_clock
        self._source = Source(providerId="pandas_market_calendars")
        import pandas_market_calendars as mcal

        available = set(mcal.get_calendar_names())
        if self.calendar_name not in available:
            raise ProviderError(
                self.source,
                f"required PMC calendar {self.calendar_name!r} is unavailable",
            )
        try:
            self._calendar = mcal.get_calendar(self.calendar_name)
        except Exception as exc:
            raise ProviderError(
                self.source,
                f"could not load PMC calendar {self.calendar_name!r} ({type(exc).__name__})",
            ) from exc
        self.version = str(mcal.__version__)

    @property
    def source(self) -> Source:
        return self._source

    def get_calendar(
        self,
        request: TradingCalendarRequest,
    ) -> tuple[_ProviderCalendarDay, ...]:
        if not isinstance(request, TradingCalendarRequest):
            raise TypeError("request must be a TradingCalendarRequest")
        if request.market is not Market.CN_A:
            raise ProviderError(self.source, "unsupported market; expected Market.CN_A")
        try:
            schedule = self._calendar.schedule(
                start_date=request.start_date.isoformat(),
                end_date=request.end_date.isoformat(),
            )
            session_dates: set[date] = set()
            for session in schedule.index:
                session_day = session.date()
                if not isinstance(session_day, date):
                    raise ValueError("schedule index did not contain calendar dates")
                if session_day < request.start_date or session_day > request.end_date:
                    raise ValueError(f"schedule date outside request: {session_day.isoformat()}")
                if session_day in session_dates:
                    raise ValueError(f"duplicate schedule date: {session_day.isoformat()}")
                session_dates.add(session_day)
        except Exception as exc:
            raise ProviderError(
                self.source,
                f"PMC schedule failure ({type(exc).__name__})",
            ) from exc

        captured_at = _require_capture_time(self._clock(), self.source.provider_id)
        count = (request.end_date - request.start_date).days + 1
        return tuple(
            _ProviderCalendarDay(
                date=day,
                is_trading_day=day in session_dates,
                captured_at=captured_at,
            )
            for day in (
                date.fromordinal(request.start_date.toordinal() + offset)
                for offset in range(count)
            )
        )
