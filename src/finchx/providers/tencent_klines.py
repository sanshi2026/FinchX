"""Tencent newfqkline adapter for daily equity and index Klines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import errno
import json
import math
import random
import re
import socket
import ssl
from time import monotonic, sleep
from typing import Any, Callable, NoReturn

from pydantic import ValidationError

from finchx.contracts import Source
from finchx.datasets.market_klines import (
    MarketKlineData,
    KlineAdjustment,
    KlinesRequest,
    _ProviderKlineRow,
)
from finchx.datasets.provider_rows import _ProviderRowsResponse
from finchx.entities import Exchange, InstrumentId, InstrumentKind
from finchx.providers.errors import ProviderError
from finchx.providers.http import http_status_failure_reason
from finchx.providers.market_klines import KlinesProvider
from finchx.providers.tencent import (
    _HEADERS,
    _TIMEOUT_SECONDS,
    _RowParseFailure,
    _TencentTransport,
    _TencentTransportFailure,
    _UrllibTencentTransport,
    _optional_decimal,
    _reject_json_constant,
    _safe_value,
    _validation_fields,
)


TENCENT_KLINE_ENDPOINT = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
)
_PAGE_SIZE = 800
_MAX_PAGES = 128
_MAX_ATTEMPTS = 4
_RETRY_DELAYS_SECONDS = (0.25, 0.5, 1.0)
_RATE_LIMIT_RETRY_DELAYS_SECONDS = (2.0, 4.0, 8.0)
_TOTAL_REQUEST_BUDGET_SECONDS = 45.0
_EXCHANGE_PREFIXES = {
    Exchange.SSE: "sh",
    Exchange.SZSE: "sz",
}
_INDEX_IDENTITIES = {
    (Exchange.SSE, "000001"),
    (Exchange.SSE, "000002"),
    (Exchange.SSE, "000688"),
    (Exchange.SZSE, "399001"),
    (Exchange.SZSE, "399006"),
    (Exchange.SZSE, "399102"),
    (Exchange.SZSE, "399107"),
}
_ADJUSTMENT_RESPONSE_KEYS = {
    KlineAdjustment.NONE: ("kline_day", "day"),
    KlineAdjustment.QFQ: ("kline_dayqfq", "qfqday"),
    KlineAdjustment.HFQ: ("kline_dayhfq", "hfqday"),
}
_ASSIGNMENT = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*=\s*(.*?)\s*;?\s*$", re.DOTALL)


def _classify_transport_failure(
    error: BaseException,
) -> tuple[str, str, str, bool]:
    """Describe only safe exception types and numeric OS errors."""

    pending: list[BaseException] = [error]
    seen: set[int] = set()
    chain: list[BaseException] = []
    while pending:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        chain.append(current)
        for nested in (current.__cause__, current.__context__, getattr(current, "reason", None)):
            if isinstance(nested, BaseException) and id(nested) not in seen:
                pending.append(nested)

    for current in chain:
        if isinstance(current, ssl.SSLError):
            return "tls", "tls_failure", f"{type(current).__name__} during TLS", False
        if isinstance(current, socket.gaierror):
            error_number = current.errno
            return (
                "transport",
                "dns_resolution",
                f"{type(current).__name__}(errno={error_number})",
                True,
            )
        if isinstance(current, (TimeoutError, socket.timeout)):
            return "transport", "timeout", f"{type(current).__name__}", True

    for current in chain:
        if isinstance(current, OSError):
            error_number = current.errno
            transient_numbers = {
                errno.ECONNABORTED,
                errno.ECONNREFUSED,
                errno.ECONNRESET,
                errno.EHOSTUNREACH,
                errno.ENETUNREACH,
                errno.EPIPE,
                errno.ETIMEDOUT,
            }
            return (
                "transport",
                "connection",
                f"{type(current).__name__}(errno={error_number})",
                error_number in transient_numbers,
            )

    transport_error = next(
        (current for current in chain if isinstance(current, _TencentTransportFailure)),
        error,
    )
    return (
        "transport",
        "transport_error",
        type(transport_error).__name__,
        False,
    )


@dataclass(frozen=True)
class _KlineAttemptFailure:
    attempt: int
    stage: str
    category: str
    safe_reason: str
    retryable: bool


@dataclass(frozen=True)
class _FetchedKlinePage:
    bars: tuple[MarketKlineData, ...]
    adjustment: KlineAdjustment
    source_series: str
    used_qfq_day_fallback: bool = False


class TencentKlinesError(ProviderError):
    """Safe structured failure for a Tencent Kline request and its retries."""

    def __init__(
        self,
        source: Source,
        *,
        stage: str,
        category: str,
        safe_reason: str,
        retryable: bool,
        attempts: tuple[_KlineAttemptFailure, ...],
        retry_budget_exhausted: bool = False,
    ) -> None:
        self.provider_id = source.provider_id
        self.stage = stage
        self.category = category
        self.safe_reason = safe_reason
        self.retryable = retryable
        self.attempts = tuple(attempts)
        self.attempt_count = len(self.attempts)
        self.attempt = self.attempts[-1].attempt if self.attempts else 0
        self.retry_budget_exhausted = retry_budget_exhausted
        attempt_text = "; ".join(
            f"#{item.attempt} {item.stage}/{item.category}: {item.safe_reason} "
            f"(retryable={str(item.retryable).lower()})"
            for item in self.attempts
        )
        reason = (
            f"{stage}/{category}: {safe_reason}; attempt_count={self.attempt_count}; "
            f"retryable={str(retryable).lower()}"
        )
        if attempt_text:
            reason += f"; attempts=[{attempt_text}]"
        if retry_budget_exhausted:
            reason += "; retry_budget_exhausted=true"
        super().__init__(source, reason)

    def with_attempts(
        self,
        attempts: tuple[_KlineAttemptFailure, ...],
        *,
        retry_budget_exhausted: bool | None = None,
    ) -> TencentKlinesError:
        return TencentKlinesError(
            self.source,
            stage=self.stage,
            category=self.category,
            safe_reason=self.safe_reason,
            retryable=self.retryable,
            attempts=attempts,
            retry_budget_exhausted=(
                self.retry_budget_exhausted
                if retry_budget_exhausted is None
                else retry_budget_exhausted
            ),
        )


class TencentKlinesProvider(KlinesProvider):
    """Fetch a complete requested Tencent daily window, paging by end date."""

    def __init__(
        self,
        transport: _TencentTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] = sleep,
        retry_budget_seconds: float = _TOTAL_REQUEST_BUDGET_SECONDS,
    ) -> None:
        if (
            isinstance(retry_budget_seconds, bool)
            or not isinstance(retry_budget_seconds, (int, float))
            or not math.isfinite(float(retry_budget_seconds))
            or retry_budget_seconds <= 0
        ):
            raise ValueError("retry_budget_seconds must be a finite positive number")
        if not callable(sleeper):
            raise TypeError("sleeper must be callable")
        self._transport = transport or _UrllibTencentTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic_clock or monotonic
        self._sleeper = sleeper
        self._retry_budget_seconds = float(retry_budget_seconds)
        self._source = Source(
            providerId="tencent.finance.qq",
            sourceUrl=TENCENT_KLINE_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_klines(
        self, request: KlinesRequest
    ) -> tuple[_ProviderKlineRow, ...] | _ProviderRowsResponse[_ProviderKlineRow]:
        if not isinstance(request, KlinesRequest):
            self._fail(
                "request must be a KlinesRequest",
                stage="request",
                category="invalid_request",
            )
        symbol = self._source_symbol(request.instrument_id)
        source_adjustment = request.adjustment or KlineAdjustment.NONE
        deadline = self._monotonic() + self._retry_budget_seconds
        cursor = request.end_date
        collected: list[MarketKlineData] = []
        seen_dates: set[date] = set()
        actual_adjustment: KlineAdjustment | None = None
        actual_series: str | None = None
        used_qfq_day_fallback = False

        for page_number in range(1, _MAX_PAGES + 1):
            page = self._fetch_page_with_retries(
                request,
                symbol=symbol,
                end_date=cursor,
                source_adjustment=source_adjustment,
                deadline=deadline,
                page_number=page_number,
            )
            if actual_adjustment is None:
                actual_adjustment = page.adjustment
                actual_series = page.source_series
            elif (
                page.adjustment is not actual_adjustment
                or page.source_series != actual_series
            ):
                self._fail(
                    "Tencent adjustment data series changed between Kline pages",
                    stage="response",
                    category="mixed_adjustment_series",
                )
            used_qfq_day_fallback = used_qfq_day_fallback or page.used_qfq_day_fallback

            if not page.bars:
                break

            page_dates = [bar.bar_date for bar in page.bars]
            for bar in page.bars:
                if bar.bar_date in seen_dates:
                    self._fail(
                        f"Tencent returned duplicate date across pages: {bar.bar_date.isoformat()}"
                    )
                if bar.bar_date > cursor:
                    self._fail(
                        f"Tencent returned date after requested page end: {bar.bar_date.isoformat()}"
                    )
                seen_dates.add(bar.bar_date)
                if request.start_date <= bar.bar_date <= request.end_date:
                    collected.append(bar)

            earliest = min(page_dates)
            if earliest <= request.start_date or len(page.bars) < _PAGE_SIZE:
                break

            next_end_date = earliest - timedelta(days=1)
            if next_end_date >= cursor:
                self._fail("Tencent pagination cursor did not move backward")
            cursor = next_end_date
        else:
            self._fail(
                "Tencent pagination safety limit reached before the requested start date"
            )

        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")

        rows = tuple(
            _ProviderKlineRow(
                data=bar,
                source_record_id=(
                    f"{symbol}:{bar.bar_date.isoformat()}:{bar.adjustment.value}"
                ),
                captured_at=captured_at,
                requested_adjustment=source_adjustment,
                source_series=actual_series,
                adjustment_fallback=used_qfq_day_fallback,
            )
            for bar in sorted(collected, key=lambda item: item.bar_date)
        )
        if used_qfq_day_fallback:
            warning = (
                "Tencent did not return qfqday; used day data, which is unadjusted "
                "and is not forward-adjusted."
            )
            return _ProviderRowsResponse(
                rows=rows,
                warnings=(warning,),
                metadata={
                    "requested_adjustment": KlineAdjustment.QFQ.value,
                    "actual_adjustment": KlineAdjustment.NONE.value,
                    "source_series": "day",
                    "adjustment_fallback": True,
                    "adjustment_warning": warning,
                },
            )
        return rows

    def _fetch_page(
        self,
        request: KlinesRequest,
        *,
        symbol: str,
        end_date: date,
        source_adjustment: KlineAdjustment,
        timeout_seconds: float,
        attempt_number: int,
        page_number: int,
    ) -> _FetchedKlinePage:
        try:
            return self._fetch_page_once(
                request,
                symbol=symbol,
                end_date=end_date,
                source_adjustment=source_adjustment,
                timeout_seconds=timeout_seconds,
            )
        except TencentKlinesError as exc:
            failure = _KlineAttemptFailure(
                attempt=attempt_number,
                stage=exc.stage,
                category=exc.category,
                safe_reason=exc.safe_reason,
                retryable=exc.retryable,
            )
            enriched = exc.with_attempts((failure,))
            enriched.page_number = page_number
            raise enriched from exc

    def _fetch_page_once(
        self,
        request: KlinesRequest,
        *,
        symbol: str,
        end_date: date,
        source_adjustment: KlineAdjustment,
        timeout_seconds: float,
    ) -> _FetchedKlinePage:
        response_variable, series_key = _ADJUSTMENT_RESPONSE_KEYS[source_adjustment]
        params = {
            "_var": response_variable,
            # Tencent's tested endpoint pages backward from endDate. Its start
            # parameter did not constrain the returned count window.
            "param": (
                f"{symbol},day,,{end_date.isoformat()},{_PAGE_SIZE},"
                f"{source_adjustment.value}"
            ),
            "r": str(random.random()),
        }
        try:
            response = self._transport.get(
                TENCENT_KLINE_ENDPOINT,
                params=params,
                headers=_HEADERS,
                timeout_seconds=timeout_seconds,
            )
        except _TencentTransportFailure as exc:
            stage, category, safe_reason, retryable = _classify_transport_failure(exc)
            self._fail(
                f"Tencent newfqkline {safe_reason}",
                stage=stage,
                category=category,
                safe_reason=safe_reason,
                retryable=retryable,
            )
        except Exception as exc:
            stage, category, safe_reason, retryable = _classify_transport_failure(exc)
            self._fail(
                f"Tencent newfqkline {safe_reason}",
                stage=stage,
                category=category,
                safe_reason=safe_reason,
                retryable=retryable,
            )

        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            status_code = response.status_code
            retryable = status_code in {408, 425, 429} or 500 <= status_code < 600
            self._fail(
                f"Tencent newfqkline returned {status_reason}",
                stage="http",
                category="transient_http" if retryable else "permanent_http",
                retryable=retryable,
            )
        document = self._decode_response(response.text, expected_variable=response_variable)
        self._check_response_status(document)

        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("Tencent newfqkline data must be an object")
        if symbol not in data:
            returned_symbols = sorted(
                key
                for key in data
                if isinstance(key, str) and re.fullmatch(r"(?:sh|sz|bj)\d+", key)
            )
            if returned_symbols:
                self._fail(
                    f"Tencent returned a different symbol key for requested {symbol}: "
                    f"{', '.join(returned_symbols[:4])}"
                )
            self._fail(f"Tencent response omitted the requested symbol key {symbol}")

        symbol_data = data[symbol]
        if not isinstance(symbol_data, dict):
            self._fail(f"Tencent payload for {symbol} must be an object")
        source_series = series_key
        actual_adjustment = source_adjustment
        used_qfq_day_fallback = False
        if source_adjustment is KlineAdjustment.QFQ and series_key not in symbol_data:
            raw_rows = symbol_data.get("day")
            if not isinstance(raw_rows, list):
                self._fail(
                    f"Tencent payload for {symbol} omitted qfqday and has no valid day array"
                )
            source_series = "day"
            actual_adjustment = KlineAdjustment.NONE
            used_qfq_day_fallback = True
        else:
            raw_rows = symbol_data.get(series_key)
            if not isinstance(raw_rows, list):
                self._fail(f"Tencent payload for {symbol} has an invalid {series_key} array")

        bars: list[MarketKlineData] = []
        seen: set[date] = set()
        for index, raw_row in enumerate(raw_rows):
            bar = self._parse_bar(
                raw_row,
                instrument_id=request.instrument_id,
                adjustment=(
                    actual_adjustment
                    if request.instrument_id.kind is InstrumentKind.EQUITY
                    else KlineAdjustment.NOT_APPLICABLE
                ),
                row_context=f"{symbol} {source_series} row {index}",
            )
            if bar.bar_date in seen:
                self._fail(f"Tencent returned duplicate date within page: {bar.bar_date.isoformat()}")
            seen.add(bar.bar_date)
            bars.append(bar)
        return _FetchedKlinePage(
            bars=tuple(bars),
            adjustment=actual_adjustment,
            source_series=source_series,
            used_qfq_day_fallback=used_qfq_day_fallback,
        )

    def _decode_response(self, text: str, *, expected_variable: str) -> dict[str, Any]:
        value = text.strip()
        matched = _ASSIGNMENT.fullmatch(value)
        if matched is not None:
            variable, value = matched.groups()
            if variable != expected_variable:
                self._fail(
                    f"Tencent response wrapper mismatch: expected {expected_variable}, received {variable}"
                )
        elif not value.startswith("{"):
            self._fail("Tencent response is not the expected variable assignment or JSON object")

        try:
            document = json.loads(
                value,
                parse_float=Decimal,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Tencent response contains malformed JSON: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Tencent response root must be an object")
        return document

    def _check_response_status(self, document: dict[str, Any]) -> None:
        if "code" not in document:
            self._fail("Tencent response omitted its code field")
        code = document["code"]
        if isinstance(code, bool) or code not in (0, 200, "0", "200"):
            self._fail(f"Tencent response code indicates failure: {_safe_value(code)}")

    def _parse_bar(
        self,
        raw: Any,
        *,
        instrument_id: InstrumentId,
        adjustment: KlineAdjustment,
        row_context: str,
    ) -> MarketKlineData:
        if not isinstance(raw, list) or len(raw) < 6:
            self._fail(
                f"invalid Tencent daily bar at {row_context}: expected at least 6 fields"
            )

        raw_date = raw[0]
        if not isinstance(raw_date, str):
            self._fail(f"invalid Tencent date at {row_context}: {_safe_value(raw_date)}")
        try:
            bar_date = date.fromisoformat(raw_date)
        except ValueError:
            self._fail(f"invalid Tencent date at {row_context}: {_safe_value(raw_date)}")
        if bar_date.isoformat() != raw_date:
            self._fail(f"non-canonical Tencent date at {row_context}: {_safe_value(raw_date)}")

        try:
            open_price = self._required_decimal(raw[1], "open", row_context)
            close_price = self._required_decimal(raw[2], "close", row_context)
            high_price = self._required_decimal(raw[3], "high", row_context)
            low_price = self._required_decimal(raw[4], "low", row_context)
            volume_hands = self._required_decimal(raw[5], "volume", row_context)
            amount_wan = _optional_decimal(raw[8], "amount", row_context) if len(raw) > 8 else None
        except _RowParseFailure as exc:
            self._fail(f"invalid Tencent daily bar at {row_context}: {exc}")

        if volume_hands < 0:
            self._fail(f"negative Tencent volume at {row_context}")
        volume_shares = volume_hands * Decimal("100")
        if volume_shares != volume_shares.to_integral_value():
            self._fail(f"Tencent volume does not resolve to whole shares at {row_context}")
        if amount_wan is not None and amount_wan < 0:
            self._fail(f"negative Tencent amount at {row_context}")
        amount_cny = None if amount_wan is None else amount_wan * Decimal("10000")

        try:
            return MarketKlineData(
                instrumentId=instrument_id,
                barDate=bar_date,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=int(volume_shares),
                amount=amount_cny,
                adjustment=adjustment,
            )
        except ValidationError as exc:
            fields = _validation_fields(exc)
            self._fail(f"Tencent bar contract validation failed at {row_context}; fields={fields}")

    def _required_decimal(self, value: Any, field: str, row_context: str) -> Decimal:
        parsed = _optional_decimal(value, field, row_context)
        if parsed is None:
            raise _RowParseFailure(f"required field {field} is missing at {row_context}")
        return parsed

    def _source_symbol(self, instrument_id: InstrumentId) -> str:
        if instrument_id.kind is InstrumentKind.INDEX:
            if (instrument_id.exchange, instrument_id.code) not in _INDEX_IDENTITIES:
                self._fail(
                    "Tencent index Klines supports only the verified SSE/SZSE identities",
                    stage="request",
                    category="invalid_request",
                )
            prefix = _EXCHANGE_PREFIXES[instrument_id.exchange]
            return f"{prefix}{instrument_id.code}"
        if instrument_id.kind is not InstrumentKind.EQUITY:
            self._fail(
                "Tencent Klines supports equity and the verified index identities only",
                stage="request",
                category="invalid_request",
            )
        prefix = _EXCHANGE_PREFIXES.get(instrument_id.exchange)
        if prefix is None:
            self._fail(
                "Tencent daily Klines supports only explicit SSE and SZSE identities",
                stage="request",
                category="invalid_request",
            )
        return f"{prefix}{instrument_id.code}"

    def _fetch_page_with_retries(
        self,
        request: KlinesRequest,
        *,
        symbol: str,
        end_date: date,
        source_adjustment: KlineAdjustment,
        deadline: float,
        page_number: int,
    ) -> _FetchedKlinePage:
        failures: list[_KlineAttemptFailure] = []
        for attempt_number in range(1, _MAX_ATTEMPTS + 1):
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                if failures:
                    error = self._error_from_failure(failures[-1], tuple(failures))
                    error.page_number = page_number
                    raise error
                self._fail(
                    "Tencent Kline total request budget expired before an attempt",
                    stage="deadline",
                    category="retry_budget_exhausted",
                    retryable=False,
                )

            try:
                page = self._fetch_page(
                    request,
                    symbol=symbol,
                    end_date=end_date,
                    source_adjustment=source_adjustment,
                    timeout_seconds=min(_TIMEOUT_SECONDS, remaining),
                    attempt_number=attempt_number,
                    page_number=page_number,
                )
                return page
            except TencentKlinesError as exc:
                failure = exc.attempts[-1]
                failures.append(failure)
                if not exc.retryable:
                    enriched = exc.with_attempts(tuple(failures))
                    enriched.page_number = page_number
                    raise enriched from exc
                if attempt_number >= _MAX_ATTEMPTS:
                    exhausted = exc.with_attempts(
                        tuple(failures), retry_budget_exhausted=True
                    )
                    exhausted.page_number = page_number
                    raise exhausted from exc

                delays = (
                    _RATE_LIMIT_RETRY_DELAYS_SECONDS
                    if failure.category == "transient_http"
                    and "HTTP 429" in failure.safe_reason
                    else _RETRY_DELAYS_SECONDS
                )
                delay = delays[attempt_number - 1]
                if deadline - self._monotonic() <= delay:
                    exhausted = exc.with_attempts(
                        tuple(failures), retry_budget_exhausted=True
                    )
                    exhausted.page_number = page_number
                    raise exhausted from exc
                if delay:
                    self._sleeper(delay)

        raise AssertionError("Tencent Kline retry loop exited unexpectedly")

    def _error_from_failure(
        self,
        failure: _KlineAttemptFailure,
        attempts: tuple[_KlineAttemptFailure, ...],
    ) -> TencentKlinesError:
        return TencentKlinesError(
            self.source,
            stage=failure.stage,
            category=failure.category,
            safe_reason=failure.safe_reason,
            retryable=failure.retryable,
            attempts=attempts,
            retry_budget_exhausted=failure.retryable,
        )

    def _fail(
        self,
        reason: str,
        *,
        stage: str = "response",
        category: str = "schema",
        safe_reason: str | None = None,
        retryable: bool = False,
    ) -> NoReturn:
        raise TencentKlinesError(
            self.source,
            stage=stage,
            category=category,
            safe_reason=safe_reason or reason,
            retryable=retryable,
            attempts=(),
        ) from None
