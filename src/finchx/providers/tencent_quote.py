"""Tencent qt.gtimg.cn single-equity/index quote source adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Callable, NoReturn
from zoneinfo import ZoneInfo


from finchx.contracts import Source
from finchx.datasets.market_quote_snapshot import (
    _ProviderQuoteSnapshotRow,
    _ProviderRawBookLevel,
    _validate_snapshot_instrument,
)
from finchx.entities import Exchange, InstrumentId
from finchx.providers.errors import ProviderError
from finchx.providers.http import http_status_failure_reason
from finchx.providers.tencent import (
    _HEADERS,
    _TIMEOUT_SECONDS,
    _TencentHttpResponse,
    _TencentTransport,
    _TencentTransportFailure,
    _UrllibTencentTransport,
)

TENCENT_QUOTE_ENDPOINT = "https://qt.gtimg.cn"
_EXCHANGE_PREFIX = {Exchange.SSE: "sh", Exchange.SZSE: "sz"}
_ASSIGNMENT = re.compile(r'^\s*v_(sh|sz)([0-9]{6})="([^"\r\n]*)";?\s*$')
_TIMESTAMP = re.compile(r"^[0-9]{14}$")
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_MIN_FIELD_COUNT = 58


class TencentQuoteProvider:
    """Fetch and parse one raw Tencent quote response for reuse by Dataset normalizers."""

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
            sourceUrl=TENCENT_QUOTE_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_quote(self, instrument_id: InstrumentId) -> _ProviderQuoteSnapshotRow:
        """Return one typed source result; pass it to either or both normalizers."""

        if not isinstance(instrument_id, InstrumentId):
            self._fail("request must provide one explicit InstrumentId")
        try:
            _validate_snapshot_instrument(instrument_id)
        except ValueError as exc:
            self._fail(str(exc))
        prefix = _EXCHANGE_PREFIX.get(instrument_id.exchange)
        if prefix is None:
            self._fail("Tencent qt quote supports SSE and SZSE instruments only")
        symbol = f"{prefix}{instrument_id.code}"
        request_url = f"{TENCENT_QUOTE_ENDPOINT}/q={symbol}"
        try:
            response = self._transport.get(
                request_url,
                params={},
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent qt transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent qt transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent qt returned {status_reason}")
        if not response.text.strip():
            self._fail("Tencent qt returned an empty payload")

        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return self._parse_response(
            response,
            instrument_id=instrument_id,
            symbol=symbol,
            request_url=request_url,
            captured_at=captured_at,
        )

    def _parse_response(
        self,
        response: _TencentHttpResponse,
        *,
        instrument_id: InstrumentId,
        symbol: str,
        request_url: str,
        captured_at: datetime,
    ) -> _ProviderQuoteSnapshotRow:
        matched = _ASSIGNMENT.fullmatch(response.text.strip())
        if matched is None:
            self._fail("Tencent qt response is not a valid quote assignment")
        source_prefix, source_code, raw_values = matched.groups()
        expected_prefix = _EXCHANGE_PREFIX[instrument_id.exchange]
        if source_prefix != expected_prefix or source_code != instrument_id.code:
            self._fail("Tencent qt response symbol does not match the requested identity")
        fields = raw_values.split("~")
        if len(fields) < _MIN_FIELD_COUNT:
            self._fail(
                f"Tencent qt quote schema drift: expected at least {_MIN_FIELD_COUNT} fields, got {len(fields)}"
            )
        if fields[2] != instrument_id.code:
            self._fail("Tencent qt payload identity does not match the requested instrument")

        def optional_decimal(index: int, label: str) -> Decimal | None:
            value = fields[index].strip()
            if value in {"", "--", "-"}:
                return None
            try:
                parsed = Decimal(value)
            except InvalidOperation:
                self._fail(f"Tencent qt field {label} is not numeric")
            if not parsed.is_finite():
                self._fail(f"Tencent qt field {label} is not finite")
            return parsed

        price = optional_decimal(3, "price")
        if price is None:
            self._fail("Tencent qt required price is missing")
        volume_a = optional_decimal(6, "volume")
        volume_b = optional_decimal(36, "duplicate volume")
        if volume_a is not None and volume_b is not None and volume_a != volume_b:
            self._fail("Tencent qt duplicate volume fields disagree")
        volume_hands = volume_a if volume_a is not None else volume_b
        for volume in (volume_a, volume_b):
            if volume is not None and (volume < 0 or volume != volume.to_integral_value()):
                self._fail("Tencent qt volume must be a non-negative whole number of hands")

        timestamp_text = fields[30].strip()
        if _TIMESTAMP.fullmatch(timestamp_text) is None:
            self._fail("Tencent qt source timestamp is not YYYYMMDDHHmmss")
        try:
            source_timestamp = datetime.strptime(timestamp_text, "%Y%m%d%H%M%S").replace(
                tzinfo=_SHANGHAI
            )
        except ValueError:
            self._fail("Tencent qt source timestamp is not a valid calendar time")

        def parse_book(side_start: int) -> tuple[_ProviderRawBookLevel, ...]:
            slots: list[_ProviderRawBookLevel] = []
            for level in range(1, 6):
                price_value = optional_decimal(side_start + (level - 1) * 2, f"book price {level}")
                size_value = optional_decimal(side_start + (level - 1) * 2 + 1, f"book size {level}")
                if price_value is not None and price_value < 0:
                    self._fail("Tencent qt book price cannot be negative")
                if size_value is not None and (
                    size_value < 0 or size_value != size_value.to_integral_value()
                ):
                    self._fail("Tencent qt book size must be a non-negative whole number of hands")
                slots.append(
                    _ProviderRawBookLevel(
                        level=level,
                        price=price_value,
                        size_hands=size_value,
                    )
                )
            return tuple(slots)

        amount = optional_decimal(57, "amount")
        if amount is not None and amount < 0:
            self._fail("Tencent qt amount cannot be negative")
        return _ProviderQuoteSnapshotRow(
            instrument_id=instrument_id,
            price=price,
            previous_close=optional_decimal(4, "previous close"),
            open=optional_decimal(5, "open"),
            high=optional_decimal(33, "high"),
            low=optional_decimal(34, "low"),
            price_change=optional_decimal(31, "price change"),
            change_rate_percent_points=optional_decimal(32, "change rate"),
            volume_hands=volume_hands,
            amount_ten_thousand_cny=amount,
            source_timestamp=source_timestamp,
            bids=parse_book(9),
            asks=parse_book(19),
            source_record_id=symbol,
            source_url=request_url,
            captured_at=captured_at,
        )

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)
