"""Sohu mkline adapter for the explicitly supported daily index series."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, NoReturn, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from finchx.contracts import Source
from finchx.datasets.market_klines import (
    KlineAdjustment,
    KlinesRequest,
    MarketKlineData,
    _ProviderKlineRow,
)
from finchx.entities import Exchange, InstrumentKind
from finchx.providers.errors import ProviderError
from finchx.providers.http import (
    DEFAULT_TIMEOUT_SECONDS,
    build_headers,
    http_status_failure_reason,
)
from finchx.providers.market_klines import KlinesProvider


SOHU_KLINE_ENDPOINT = "https://hq.stock.sohu.com/mkline/{market}/{directory}/{market}_{code}-10_2.html"
_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
_MAX_RESPONSE_BYTES = 12 * 1024 * 1024
_HANDS_TO_SHARES = Decimal("100")
_WAN_TO_CNY = Decimal("10000")
_WRAPPER = re.compile(r"^\s*quote_d_dividend\((.*)\)\s*;?\s*$", re.DOTALL)
_HEADERS = build_headers(
    accept="*/*",
    referer="https://hq.stock.sohu.com/",
)
_SUPPORTED_IDENTITIES = {
    (Exchange.SSE, "000001"),
    (Exchange.SZSE, "399001"),
    (Exchange.SZSE, "399006"),
}


class _SohuHttpResponse(Protocol):
    status_code: int
    text: str


class _SohuResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class _SohuTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _SohuHttpResponse: ...


class _SohuTransportFailure(RuntimeError):
    pass


class _UrllibSohuTransport:
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _SohuResponse:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(body) > _MAX_RESPONSE_BYTES:
                    raise _SohuTransportFailure("response exceeded the 12 MiB safety limit")
                charset = response.headers.get_content_charset() or "utf-8"
                return _SohuResponse(int(response.status), body.decode(charset))
        except HTTPError as exc:
            return _SohuResponse(int(exc.code), "")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            raise _SohuTransportFailure(type(exc).__name__) from exc


class SohuKlinesProvider(KlinesProvider):
    """Fetch one complete Sohu daily index series and filter it locally."""

    def __init__(
        self,
        transport: _SohuTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport or _UrllibSohuTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(
            providerId="sohu.finance",
            sourceUrl=SOHU_KLINE_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_klines(self, request: KlinesRequest) -> tuple[_ProviderKlineRow, ...]:
        if not isinstance(request, KlinesRequest):
            self._fail("request must be a KlinesRequest")
        identity = request.instrument_id
        if identity.kind is not InstrumentKind.INDEX:
            self._fail("Sohu mkline supports index identities only")
        if (identity.exchange, identity.code) not in _SUPPORTED_IDENTITIES:
            self._fail("Sohu mkline supports only the verified SSE/SZSE index identities")

        request_at = self._clock()
        if request_at.tzinfo is None or request_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        endpoint = self._endpoint(identity.code)
        url = f"{endpoint}?_={int(request_at.timestamp() * 1000)}"
        try:
            response = self._transport.get(
                url,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _SohuTransportFailure as exc:
            self._fail(f"Sohu mkline transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Sohu mkline transport failure: {type(exc).__name__}")

        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Sohu mkline returned {status_reason}")
        if len(response.text.encode("utf-8")) > _MAX_RESPONSE_BYTES:
            self._fail("Sohu mkline response exceeded the 12 MiB safety limit")
        document = self._decode_response(response.text)
        self._validate_document(document)
        raw_rows = document["dataDiv"]

        bars: list[MarketKlineData] = []
        seen: set[date] = set()
        for index, raw_row in enumerate(raw_rows):
            bar_date = self._source_date(raw_row, request=request, row_index=index)
            if bar_date in seen:
                self._fail(f"Sohu returned duplicate date: {bar_date.isoformat()}")
            seen.add(bar_date)
            if request.start_date <= bar_date <= request.end_date:
                bars.append(
                    self._parse_bar(
                        raw_row,
                        request=request,
                        row_index=index,
                        bar_date=bar_date,
                    )
                )

        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return tuple(
            _ProviderKlineRow(
                data=bar,
                source_record_id=f"zs_{identity.code}:{bar.bar_date.isoformat()}",
                captured_at=captured_at,
                source_url=url,
            )
            for bar in sorted(bars, key=lambda item: item.bar_date)
        )

    def _endpoint(self, code: str) -> str:
        return SOHU_KLINE_ENDPOINT.format(
            market="zs",
            directory=code[3:],
            code=code,
        )

    def _decode_response(self, text: str) -> dict[str, Any]:
        matched = _WRAPPER.fullmatch(text.strip())
        if matched is None:
            self._fail("Sohu response did not use the quote_d_dividend JavaScript wrapper")
        try:
            document = json.loads(
                matched.group(1),
                parse_float=Decimal,
                parse_constant=self._reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Sohu response contains malformed JSON: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Sohu response root must be an object")
        return document

    def _validate_document(self, document: dict[str, Any]) -> None:
        status = document.get("status")
        if isinstance(status, bool) or status != 0:
            self._fail("Sohu response status indicates failure")
        if document.get("type") != "quote_day":
            self._fail("Sohu response type must be quote_day")
        if "dataDiv" not in document or not isinstance(document["dataDiv"], list):
            self._fail("Sohu response must contain a dataDiv array")

    def _source_date(
        self,
        raw: Any,
        *,
        request: KlinesRequest,
        row_index: int,
    ) -> date:
        context = f"zs_{request.instrument_id.code} dataDiv row {row_index}"
        if not isinstance(raw, list) or len(raw) < 7:
            self._fail(f"invalid Sohu bar at {context}: expected at least 7 fields")
        raw_date = raw[0]
        if not isinstance(raw_date, str) or re.fullmatch(r"[0-9]{8}", raw_date) is None:
            self._fail(f"invalid Sohu date at {context}")
        try:
            return date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
        except ValueError:
            self._fail(f"invalid Sohu date at {context}")

    def _parse_bar(
        self,
        raw: Any,
        *,
        request: KlinesRequest,
        row_index: int,
        bar_date: date,
    ) -> MarketKlineData:
        context = f"zs_{request.instrument_id.code} dataDiv row {row_index}"
        open_price = self._decimal(raw[1], "open", context)
        close_price = self._decimal(raw[2], "close", context)
        high_price = self._decimal(raw[3], "high", context)
        low_price = self._decimal(raw[4], "low", context)
        volume_hands = self._decimal(raw[5], "volume", context)
        amount_wan = self._decimal(raw[6], "amount", context)
        if volume_hands < 0:
            self._fail(f"negative Sohu volume at {context}")
        volume_shares = volume_hands * _HANDS_TO_SHARES
        if volume_shares != volume_shares.to_integral_value():
            self._fail(f"Sohu volume does not resolve to whole shares at {context}")
        if amount_wan < 0:
            self._fail(f"negative Sohu amount at {context}")

        try:
            return MarketKlineData(
                instrumentId=request.instrument_id,
                barDate=bar_date,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=int(volume_shares),
                amount=amount_wan * _WAN_TO_CNY,
                adjustment=KlineAdjustment.NOT_APPLICABLE,
            )
        except ValidationError as exc:
            fields = sorted({".".join(map(str, item.get("loc", ()))) or "bar" for item in exc.errors()})
            self._fail(f"Sohu bar contract validation failed at {context}; fields={fields}")

    def _decimal(self, value: Any, field: str, context: str) -> Decimal:
        if isinstance(value, bool) or value is None:
            self._fail(f"Sohu {field} is missing or invalid at {context}")
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            self._fail(f"Sohu {field} is not decimal at {context}")
        if not parsed.is_finite():
            self._fail(f"Sohu {field} is not finite at {context}")
        return parsed

    @staticmethod
    def _reject_json_constant(value: str) -> NoReturn:
        raise ValueError(f"invalid JSON numeric constant {value}")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)
