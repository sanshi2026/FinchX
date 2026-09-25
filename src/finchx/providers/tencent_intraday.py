"""Tencent intraday endpoints and fail-closed source parsing."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, Mapping, NoReturn
from urllib.parse import urlencode

from finchx.contracts import Source
from finchx.datasets.market_intraday import (
    EquityIntraday5dRequest,
    EquityIntradayRequest,
    IndexIntraday5dRequest,
    IndexIntradayRequest,
    _ProviderIntradayRow,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.errors import ProviderError
from finchx.providers.http import http_status_failure_reason
from finchx.providers.tencent import (
    _HEADERS,
    _TIMEOUT_SECONDS,
    _TencentTransport,
    _TencentTransportFailure,
    _UrllibTencentTransport,
)
from finchx.providers.tencent_quote import _EXCHANGE_PREFIX

TENCENT_DAY_QUERY_ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/day/query"
TENCENT_MINUTE_QUERY_ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/minute/query"

_SUPPORTED_EQUITY_PREFIXES = {
    Exchange.SSE: ("60", "68"),
    Exchange.SZSE: ("00", "30"),
}
_SUPPORTED_INDEX_IDENTITIES = {
    (Exchange.SSE, "000001"),
    (Exchange.SZSE, "399001"),
    (Exchange.SZSE, "399006"),
}
_IDENTIFIER = re.compile(r"^(?:sh|sz)[0-9]{6}$")
_DATE_COMPACT = re.compile(r"^[0-9]{8}$")
_ASSIGNMENT = re.compile(
    r"^\s*([A-Za-z_$][\w$]*)\s*=\s*(\{.*\})\s*;?\s*$",
    re.DOTALL,
)
_HHMM = re.compile(r"^[0-9]{3,4}$")
_SUCCESS_CODES = (0, 200, "0", "200", Decimal(0), Decimal(200))


class TencentIntradayProvider:
    """Fetch one Tencent intraday series; normalization belongs to the Dataset."""

    def __init__(
        self,
        transport: _TencentTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport or _UrllibTencentTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(providerId="tencent.finance.qq")

    @property
    def source(self) -> Source:
        return self._source

    def fetch_equity_intraday(
        self, request: EquityIntradayRequest
    ) -> tuple[_ProviderIntradayRow, ...]:
        self._check_request(request, EquityIntradayRequest)
        return self._fetch_day_query(request.instrument_id)

    def fetch_equity_intraday_5d(
        self, request: EquityIntraday5dRequest
    ) -> tuple[_ProviderIntradayRow, ...]:
        self._check_request(request, EquityIntraday5dRequest)
        return self._fetch_day_query(request.instrument_id)

    def fetch_index_intraday(
        self, request: IndexIntradayRequest
    ) -> tuple[_ProviderIntradayRow, ...]:
        self._check_request(request, IndexIntradayRequest)
        instrument = request.instrument_id
        symbol = self._source_symbol(instrument)
        params = {"_var": f"min_data_{symbol}", "code": symbol}
        document, source_url, captured_at = self._request(
            TENCENT_MINUTE_QUERY_ENDPOINT,
            params,
            expected_variable=f"min_data_{symbol}",
        )
        self._check_response_status(document)
        symbol_data = self._select_symbol_data(document, symbol)
        series = self._object(symbol_data.get("data"), f"data.{symbol}.data")
        trade_date = self._parse_date(
            series.get("date"), f"data.{symbol}.data.date"
        )
        raw_rows = series.get("data")
        rows = self._parse_delimited_rows(
            raw_rows,
            instrument=instrument,
            symbol=symbol,
            trade_date=trade_date,
            source_url=source_url,
            captured_at=captured_at,
            context=f"data.{symbol}.data.data",
        )
        return self._require_rows(rows)

    def fetch_index_intraday_5d(
        self, request: IndexIntraday5dRequest
    ) -> tuple[_ProviderIntradayRow, ...]:
        self._check_request(request, IndexIntraday5dRequest)
        return self._fetch_day_query(request.instrument_id)

    def _fetch_day_query(
        self, instrument: InstrumentId
    ) -> tuple[_ProviderIntradayRow, ...]:
        symbol = self._source_symbol(instrument)
        variable = f"fdays_data_{symbol}"
        params = {"_var": variable, "code": symbol}
        document, source_url, captured_at = self._request(
            TENCENT_DAY_QUERY_ENDPOINT,
            params,
            expected_variable=variable,
        )
        self._check_response_status(document)
        symbol_data = self._select_symbol_data(document, symbol)
        day_list = symbol_data.get("data")
        if not isinstance(day_list, list):
            self._fail(f"data.{symbol}.data must be a date array")

        rows: list[_ProviderIntradayRow] = []
        for day_index, day in enumerate(day_list):
            context = f"data.{symbol}.data[{day_index}]"
            day = self._object(day, context)
            trade_date = self._parse_date(day.get("date"), f"{context}.date")
            if "prec" not in day:
                self._fail(f"{context} omitted prec")
            raw_rows = day.get("data")
            rows.extend(
                self._parse_delimited_rows(
                    raw_rows,
                    instrument=instrument,
                    symbol=symbol,
                    trade_date=trade_date,
                    source_url=source_url,
                    captured_at=captured_at,
                    context=f"{context}.data",
                )
            )
        return self._require_rows(rows)

    def _request(
        self,
        endpoint: str,
        params: Mapping[str, str],
        *,
        expected_variable: str | None,
    ) -> tuple[dict[str, Any], str, datetime]:
        request_url = f"{endpoint}?{urlencode(params)}"
        try:
            response = self._transport.get(
                endpoint,
                params=params,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent intraday transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent intraday transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent intraday returned {status_reason}")
        if not response.text.strip():
            self._fail("Tencent intraday returned an empty payload")

        document = self._decode_response(
            response.text, expected_variable=expected_variable
        )
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return document, request_url, captured_at

    def _decode_response(
        self, text: str, *, expected_variable: str | None
    ) -> dict[str, Any]:
        value = text.strip()
        matched = _ASSIGNMENT.fullmatch(value)
        if matched is not None:
            variable, value = matched.groups()
            if expected_variable is None or variable != expected_variable:
                self._fail(
                    f"Tencent wrapper mismatch: unexpected assignment {variable}"
                )
        elif not value.startswith("{"):
            self._fail("Tencent response is not a JSON object or expected assignment")
        elif expected_variable is not None:
            self._fail("Tencent response omitted its expected JavaScript assignment")

        try:
            document = json.loads(
                value,
                parse_float=Decimal,
                parse_int=Decimal,
                parse_constant=self._reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Tencent response contains malformed JSON: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Tencent response root must be an object")
        return document

    @staticmethod
    def _reject_json_constant(value: str) -> NoReturn:
        raise ValueError(f"non-finite JSON number {value}")

    def _check_response_status(self, document: dict[str, Any]) -> None:
        if "code" not in document:
            return
        code = document["code"]
        if isinstance(code, bool) or code not in _SUCCESS_CODES:
            message = (
                document.get("msg")
                or document.get("message")
                or "source rejected request"
            )
            self._fail(f"Tencent response code indicates failure: {str(message)[:120]}")

    def _select_symbol_data(
        self, document: dict[str, Any], symbol: str
    ) -> dict[str, Any]:
        data = self._object(document.get("data"), "response data")
        if symbol not in data:
            returned = [
                key for key in data
                if isinstance(key, str) and _IDENTIFIER.fullmatch(key)
            ]
            if returned:
                self._fail(
                    f"Tencent response identity mismatch: requested {symbol}, "
                    f"received {returned[0]}"
                )
            self._fail(f"Tencent response omitted requested symbol {symbol}")
        return self._object(data[symbol], f"data.{symbol}")

    def _parse_delimited_rows(
        self,
        raw_rows: object,
        *,
        instrument: InstrumentId,
        symbol: str,
        trade_date: date,
        source_url: str,
        captured_at: datetime,
        context: str,
    ) -> list[_ProviderIntradayRow]:
        if not isinstance(raw_rows, list):
            self._fail(f"{context} must be an array")
        rows: list[_ProviderIntradayRow] = []
        for index, raw in enumerate(raw_rows):
            row_context = f"{context}[{index}]"
            if isinstance(raw, str):
                cells: list[object] = raw.split()
            elif isinstance(raw, list):
                cells = raw
            else:
                self._fail(f"{row_context} must be a whitespace row or four-cell array")
            if len(cells) != 4:
                self._fail(
                    f"{row_context}: source field count {len(cells)}; expected 4"
                )
            rows.append(
                self._make_row(
                    instrument=instrument,
                    symbol=symbol,
                    trade_date=trade_date,
                    raw_time=cells[0],
                    raw_price=cells[1],
                    raw_lots=cells[2],
                    raw_amount=cells[3],
                    source_url=source_url,
                    captured_at=captured_at,
                    context=row_context,
                )
            )
        if not rows:
            self._fail(f"{context} was empty")
        return rows

    def _make_row(
        self,
        *,
        instrument: InstrumentId,
        symbol: str,
        trade_date: date,
        raw_time: object,
        raw_price: object,
        raw_lots: object,
        raw_amount: object,
        source_url: str,
        captured_at: datetime,
        context: str,
    ) -> _ProviderIntradayRow:
        point_time = self._parse_time(raw_time, f"{context} time")
        price = self._parse_decimal(raw_price, f"{context} price")
        lots = self._parse_decimal(raw_lots, f"{context} cumulative volume lots")
        amount = self._parse_decimal(raw_amount, f"{context} cumulative amount CNY")
        if price <= 0:
            self._fail(f"{context}: price must be positive")
        if lots < 0 or lots != lots.to_integral_value():
            self._fail(f"{context}: cumulative volume lots must be a non-negative integer")
        if amount < 0:
            self._fail(f"{context}: cumulative amount CNY must be non-negative")
        return _ProviderIntradayRow(
            instrument_id=instrument,
            trade_date=trade_date,
            time=point_time,
            price=price,
            cumulative_volume_lots=int(lots),
            cumulative_amount_cny=amount,
            source_record_id=f"{symbol}:{trade_date.isoformat()}T{point_time}",
            source_url=source_url,
            captured_at=captured_at,
        )

    def _source_symbol(self, instrument: InstrumentId) -> str:
        if not isinstance(instrument, InstrumentId):
            self._fail("request must provide a complete InstrumentId")
        if instrument.market is not Market.CN_A:
            self._fail("Tencent intraday currently supports only Market.CN_A")
        prefix = _EXCHANGE_PREFIX.get(instrument.exchange)
        if prefix is None:
            self._fail("Tencent intraday supports SSE and SZSE only")
        if instrument.kind is InstrumentKind.EQUITY:
            code_prefixes = _SUPPORTED_EQUITY_PREFIXES[instrument.exchange]
            if (
                len(instrument.code) != 6
                or not instrument.code.isascii()
                or not instrument.code.isdigit()
                or not instrument.code.startswith(code_prefixes)
            ):
                self._fail("equity code does not match its explicit exchange identity")
        elif instrument.kind is InstrumentKind.INDEX:
            if (instrument.exchange, instrument.code) not in _SUPPORTED_INDEX_IDENTITIES:
                self._fail("Tencent intraday index identity is not supported")
        else:
            self._fail("Tencent intraday supports equities and indices only")
        return f"{prefix}{instrument.code}"

    def _parse_time(self, value: object, context: str) -> str:
        if isinstance(value, Decimal) and value == value.to_integral_value():
            text = format(value, "f")
        elif isinstance(value, str):
            text = value.strip()
        else:
            self._fail(f"{context} must be HHMM text")
        if not _HHMM.fullmatch(text):
            self._fail(f"{context} must be HHMM")
        text = text.zfill(4)
        hour, minute = int(text[:2]), int(text[2:])
        if hour > 23 or minute > 59:
            self._fail(f"{context} is not a valid clock time")
        return f"{hour:02d}:{minute:02d}"

    def _parse_date(self, value: object, context: str) -> date:
        if isinstance(value, Decimal) and value == value.to_integral_value():
            value = format(value, "f")
        if not isinstance(value, str):
            self._fail(f"{context} must be YYYYMMDD or YYYY-MM-DD")
        text = value.strip()
        try:
            if _DATE_COMPACT.fullmatch(text):
                return datetime.strptime(text, "%Y%m%d").date()
            return date.fromisoformat(text)
        except ValueError:
            self._fail(f"{context} is not a valid trading date")

    def _parse_decimal(self, value: object, context: str) -> Decimal:
        if isinstance(value, Decimal):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = Decimal(value.strip())
            except InvalidOperation:
                self._fail(f"{context} is not a decimal value")
        else:
            self._fail(f"{context} must be a decimal string or JSON number")
        if not parsed.is_finite():
            self._fail(f"{context} must be finite")
        return parsed

    def _object(self, value: object, context: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            self._fail(f"{context} must be an object")
        return value

    def _require_rows(
        self, rows: list[_ProviderIntradayRow]
    ) -> tuple[_ProviderIntradayRow, ...]:
        if not rows:
            self._fail("Tencent returned no intraday rows")
        return tuple(rows)

    def _check_request(self, request: object, expected_type: type) -> None:
        if not isinstance(request, expected_type):
            self._fail(f"request must be a {expected_type.__name__}")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self._source, reason)
