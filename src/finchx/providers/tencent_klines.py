"""Tencent newfqkline adapter for daily equity and index Klines."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import random
import re
from typing import Any, Callable, NoReturn

from pydantic import ValidationError

from finchx.contracts import Source
from finchx.datasets.market_klines import (
    MarketKlineData,
    KlineAdjustment,
    KlinesRequest,
    _ProviderKlineRow,
)
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


class TencentKlinesProvider(KlinesProvider):
    """Fetch a complete requested Tencent daily window, paging by end date."""

    def __init__(
        self,
        transport: _TencentTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport or _UrllibTencentTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(
            providerId="tencent.finance.qq",
            sourceUrl=TENCENT_KLINE_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_klines(self, request: KlinesRequest) -> tuple[_ProviderKlineRow, ...]:
        if not isinstance(request, KlinesRequest):
            self._fail("request must be a KlinesRequest")
        symbol = self._source_symbol(request.instrument_id)
        source_adjustment = request.adjustment or KlineAdjustment.NONE
        cursor = request.end_date
        collected: list[MarketKlineData] = []
        seen_dates: set[date] = set()

        for _ in range(_MAX_PAGES):
            page = self._fetch_page(
                request,
                symbol=symbol,
                end_date=cursor,
                source_adjustment=source_adjustment,
            )
            if not page:
                break

            page_dates = [bar.bar_date for bar in page]
            for bar in page:
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
            if earliest <= request.start_date or len(page) < _PAGE_SIZE:
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

        return tuple(
            _ProviderKlineRow(
                data=bar,
                source_record_id=(
                    f"{symbol}:{bar.bar_date.isoformat()}:{source_adjustment.value}"
                ),
                captured_at=captured_at,
            )
            for bar in sorted(collected, key=lambda item: item.bar_date)
        )

    def _fetch_page(
        self,
        request: KlinesRequest,
        *,
        symbol: str,
        end_date: date,
        source_adjustment: KlineAdjustment,
    ) -> tuple[MarketKlineData, ...]:
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
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent newfqkline transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent newfqkline transport failure: {type(exc).__name__}")

        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent newfqkline returned {status_reason}")
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
        raw_rows = symbol_data.get(series_key)
        if not isinstance(raw_rows, list):
            self._fail(f"Tencent payload for {symbol} omitted the {series_key} array")

        bars: list[MarketKlineData] = []
        seen: set[date] = set()
        for index, raw_row in enumerate(raw_rows):
            bar = self._parse_bar(
                raw_row,
                instrument_id=request.instrument_id,
                adjustment=(
                    request.adjustment
                    if request.instrument_id.kind is InstrumentKind.EQUITY
                    else KlineAdjustment.NOT_APPLICABLE
                ),
                row_context=f"{symbol} {series_key} row {index}",
            )
            if bar.bar_date in seen:
                self._fail(f"Tencent returned duplicate date within page: {bar.bar_date.isoformat()}")
            seen.add(bar.bar_date)
            bars.append(bar)
        return tuple(bars)

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
                self._fail("Tencent index Klines supports only the verified SSE/SZSE identities")
            prefix = _EXCHANGE_PREFIXES[instrument_id.exchange]
            return f"{prefix}{instrument_id.code}"
        if instrument_id.kind is not InstrumentKind.EQUITY:
            self._fail("Tencent Klines supports equity and the verified index identities only")
        prefix = _EXCHANGE_PREFIXES.get(instrument_id.exchange)
        if prefix is None:
            self._fail("Tencent daily Klines supports only explicit SSE and SZSE identities")
        return f"{prefix}{instrument_id.code}"

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)
