"""Tencent's market-wide A-share listing, quote, and ranking adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import ValidationError

from finchx.contracts import Source
from finchx.datasets.instrument import (
    InstrumentUniverse,
    InstrumentUniverseRequest,
    _ProviderInstrumentRow,
)
from finchx.datasets.market_quote import (
    MarketQuoteData,
    MarketQuoteUniverseRequest,
    _ProviderQuoteRow,
)
from finchx.datasets.market_ranking import (
    ChangePercentRankingMetric,
    MarketRankingRequest,
    RankingCriterion,
    RankingDirection,
    TurnoverRankingMetric,
    VolumeRankingMetric,
    _ProviderRankingRow,
)
from finchx.entities import (
    Exchange,
    InstrumentId,
    InstrumentKind,
    Market,
    format_symbol,
    normalize_symbol,
)
from finchx.providers.errors import ProviderError
from finchx.providers.http import (
    DEFAULT_TIMEOUT_SECONDS,
    build_headers,
    http_status_failure_reason,
)
from finchx.providers.instrument import InstrumentListingProvider
from finchx.providers.market_quote import MarketQuoteProvider
from finchx.providers.market_ranking import MarketRankingProvider


TENCENT_RANK_ENDPOINT = (
    "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"
)
_PAGE_SIZE = 100
_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
_HEADERS = build_headers(referer="https://finance.qq.com/")
_PREFIX_EXCHANGES = {
    "sh": Exchange.SSE,
    "sz": Exchange.SZSE,
    "bj": Exchange.BSE,
}
_EQUITY_STOCK_TYPES = frozenset({"GP-A", "GP-A-KCB", "GP-A-CYB", "GP"})
_SORT_TYPES = {
    RankingCriterion.TURNOVER: "turnover",
    RankingCriterion.CHANGE_PERCENT: "priceRatio",
    RankingCriterion.VOLUME: "volume",
}
_MISSING_NUMERIC = frozenset({"", "--", "-"})
_INTEGER_TEXT = re.compile(r"^[0-9]+$")
_JSONP = re.compile(r"^[\w$.]+\s*\((.*)\)\s*;?\s*$", re.DOTALL)
_DECIMAL_100 = Decimal("100")
_DECIMAL_10_000 = Decimal("10000")
_DECIMAL_100_MILLION = Decimal("100000000")


@dataclass(frozen=True)
class _TencentHttpResponse:
    status_code: int
    text: str


class _TencentTransport(Protocol):
    """Replaceable HTTP seam used by the adapter and offline tests."""

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _TencentHttpResponse: ...


class _UrllibTencentTransport:
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _TencentHttpResponse:
        query = urlencode(params)
        request_url = f"{url}?{query}" if query else url
        request = Request(request_url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return _TencentHttpResponse(
                    status_code=int(response.status),
                    text=body.decode(charset),
                )
        except HTTPError as exc:
            # Preserve the status for explicit ProviderError handling; do not
            # parse an upstream error body as a source payload.
            return _TencentHttpResponse(status_code=int(exc.code), text="")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            raise _TencentTransportFailure(type(exc).__name__) from exc


class _TencentTransportFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class _TencentMarketRow:
    instrument_id: InstrumentId
    source_code: str
    stock_type: str
    name: str
    price: Decimal | None
    price_change: Decimal | None
    change_rate: Decimal | None
    volume: int | None
    amount: Decimal | None
    turnover_rate: Decimal | None
    market_cap: Decimal | None
    float_market_cap: Decimal | None
    pe_ttm: Decimal | None
    change_rate_5d: Decimal | None
    change_rate_10d: Decimal | None
    change_rate_20d: Decimal | None
    change_rate_60d: Decimal | None
    change_rate_52w: Decimal | None
    change_rate_ytd: Decimal | None
    amplitude: Decimal | None
    volume_ratio: Decimal | None
    main_net_inflow: Decimal | None
    main_inflow: Decimal | None
    main_outflow: Decimal | None
    main_inflow_5d: Decimal | None
    main_outflow_5d: Decimal | None
    speed: Decimal | None
    captured_at: datetime
    row_context: str


class _RowParseFailure(ValueError):
    pass


class TencentMarketProvider(
    InstrumentListingProvider,
    MarketQuoteProvider,
    MarketRankingProvider,
):
    """Fetch Tencent's all-A-share rank list and adapt its rows to FinchX."""

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
            sourceUrl=TENCENT_RANK_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def list_instruments(
        self,
        request: InstrumentUniverseRequest,
    ) -> Sequence[_ProviderInstrumentRow]:
        self._require_a_share_universe(request.universe)
        rows = self._acquire_rows(sort_type="turnover", direct="down", limit=None)
        return tuple(
            _ProviderInstrumentRow(
                code=row.instrument_id.code,
                market=row.instrument_id.market.value,
                exchange=row.instrument_id.exchange.value,
                kind=row.instrument_id.kind.value,
                name=row.name,
                source_record_id=row.source_code,
                captured_at=row.captured_at,
            )
            for row in rows
        )

    def fetch_quotes(
        self,
        request: MarketQuoteUniverseRequest,
    ) -> Sequence[_ProviderQuoteRow]:
        self._require_a_share_universe(request.universe)
        rows = self._acquire_rows(sort_type="turnover", direct="down", limit=None)
        quotes: list[_ProviderQuoteRow] = []
        for row in rows:
            quote = self._quote_data(row)
            quotes.append(
                _ProviderQuoteRow(
                    data=quote,
                    source_record_id=row.source_code,
                    captured_at=row.captured_at,
                )
            )
        return tuple(quotes)

    def fetch_ranking(
        self,
        request: MarketRankingRequest,
    ) -> Sequence[_ProviderRankingRow]:
        self._require_a_share_universe(request.universe)
        sort_type = _SORT_TYPES[request.criterion]
        direct = "up" if request.direction is RankingDirection.ASCENDING else "down"
        rows = self._acquire_rows(
            sort_type=sort_type,
            direct=direct,
            limit=request.limit,
        )
        rankings: list[_ProviderRankingRow] = []
        for row in rows:
            try:
                if request.criterion is RankingCriterion.TURNOVER:
                    if row.amount is None:
                        self._missing_ranking_metric(row, "turnover")
                    metric = TurnoverRankingMetric(
                        criterion="turnover",
                        value=row.amount,
                    )
                elif request.criterion is RankingCriterion.CHANGE_PERCENT:
                    if row.change_rate is None:
                        self._missing_ranking_metric(row, "zdf")
                    metric = ChangePercentRankingMetric(
                        criterion="change_percent",
                        value=row.change_rate,
                    )
                else:
                    if row.volume is None:
                        self._missing_ranking_metric(row, "volume")
                    metric = VolumeRankingMetric(
                        criterion="volume",
                        value=row.volume,
                    )
            except ValidationError as exc:
                fields = _validation_fields(exc)
                self._fail(
                    f"ranking metric validation failed for {format_symbol(row.instrument_id)} "
                    f"at {row.row_context}; fields={fields}"
                )
            quote = self._quote_data(row)
            rankings.append(
                _ProviderRankingRow(
                    data=quote,
                    metric=metric,
                    source_record_id=row.source_code,
                    captured_at=row.captured_at,
                )
            )
        return tuple(rankings)

    def _quote_data(self, row: _TencentMarketRow) -> MarketQuoteData:
        if row.price is None:
            self._fail(
                f"required field zxj is missing for {format_symbol(row.instrument_id)}; "
                f"{row.row_context}"
            )
        try:
            return MarketQuoteData(
                instrumentId=row.instrument_id,
                name=row.name,
                price=row.price,
                priceChange=row.price_change,
                changeRate=row.change_rate,
                volume=row.volume,
                amount=row.amount,
                turnoverRate=row.turnover_rate,
                marketCap=row.market_cap,
                floatMarketCap=row.float_market_cap,
                peTtm=row.pe_ttm,
                changeRate5d=row.change_rate_5d,
                changeRate10d=row.change_rate_10d,
                changeRate20d=row.change_rate_20d,
                changeRate60d=row.change_rate_60d,
                changeRate52w=row.change_rate_52w,
                changeRateYtd=row.change_rate_ytd,
                amplitude=row.amplitude,
                volumeRatio=row.volume_ratio,
                mainNetInflow=row.main_net_inflow,
                mainInflow=row.main_inflow,
                mainOutflow=row.main_outflow,
                mainInflow5d=row.main_inflow_5d,
                mainOutflow5d=row.main_outflow_5d,
            )
        except ValidationError as exc:
            fields = _validation_fields(exc)
            self._fail(
                f"quote row contract validation failed for "
                f"{format_symbol(row.instrument_id)} at {row.row_context}; fields={fields}"
            )

    def _require_a_share_universe(self, universe: InstrumentUniverse) -> None:
        if universe is not InstrumentUniverse.CN_A_SHARE:
            self._fail(f"unsupported instrument universe: {universe!r}")

    def _missing_ranking_metric(self, row: _TencentMarketRow, field: str) -> NoReturn:
        self._fail(
            f"required ranking field {field} is missing for "
            f"{format_symbol(row.instrument_id)} at {row.row_context}"
        )

    def _acquire_rows(
        self,
        *,
        sort_type: str,
        direct: str,
        limit: int | None,
    ) -> tuple[_TencentMarketRow, ...]:
        rows: list[_TencentMarketRow] = []
        seen: set[str] = set()
        offset = 0
        expected_total: int | None = None

        while limit is None or len(rows) < limit:
            remaining = None if limit is None else limit - len(rows)
            count = _PAGE_SIZE if remaining is None else min(_PAGE_SIZE, remaining)
            page, page_total = self._fetch_page(
                sort_type=sort_type,
                direct=direct,
                offset=offset,
                count=count,
            )
            if expected_total is None:
                expected_total = page_total
            elif page_total != expected_total:
                self._fail(
                    f"pagination total drift at offset={offset}: "
                    f"expected {expected_total}, received {page_total}"
                )

            if page_total == 0:
                if rows or page or offset != 0:
                    self._fail(f"invalid empty ranking total at offset={offset}")
                return ()
            if offset >= page_total:
                self._fail(
                    f"pagination offset reached total before request: "
                    f"offset={offset}, total={page_total}"
                )
            if len(page) > count:
                self._fail(
                    f"Tencent returned {len(page)} rows for count={count} at offset={offset}"
                )
            if offset + len(page) > page_total:
                self._fail(
                    f"Tencent page extends beyond total at offset={offset}: "
                    f"rows={len(page)}, total={page_total}"
                )
            if not page:
                self._fail(
                    f"pagination ended early at offset={offset} before total={page_total}"
                )

            for row in page:
                identity_key = format_symbol(row.instrument_id)
                if identity_key in seen:
                    self._fail(
                        f"duplicate instrument id {identity_key} at {row.row_context}"
                    )
                seen.add(identity_key)
                rows.append(row)

            offset += len(page)
            wanted = page_total if limit is None else min(limit, page_total)
            if len(rows) >= wanted:
                if len(rows) != wanted:
                    self._fail(
                        f"pagination returned more rows than expected: "
                        f"expected={wanted}, received={len(rows)}"
                    )
                return tuple(rows)

            if len(page) < count:
                self._fail(
                    f"short page before total at offset={offset - len(page)}: "
                    f"received={len(page)}, requested={count}, total={page_total}"
                )

        return tuple(rows)

    def _fetch_page(
        self,
        *,
        sort_type: str,
        direct: str,
        offset: int,
        count: int,
    ) -> tuple[tuple[_TencentMarketRow, ...], int]:
        params: dict[str, str | int] = {
            "_appver": "11.17.0",
            "board_code": "aStock",
            "sort_type": sort_type,
            "direct": direct,
            "offset": offset,
            "count": count,
        }
        try:
            response = self._transport.get(
                TENCENT_RANK_ENDPOINT,
                params=params,
                headers=dict(_HEADERS),
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            detail = (
                str(exc)
                if isinstance(exc, _TencentTransportFailure)
                else type(exc).__name__
            )
            self._fail(f"transport failure at offset={offset}: {detail[:160]}")

        if not isinstance(response, _TencentHttpResponse):
            self._fail(f"transport returned an unsupported response object at offset={offset}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(
                f"HTTP failure at offset={offset}: {status_reason}"
            )
        if not isinstance(response.text, str) or not response.text.strip():
            self._fail(f"empty HTTP response body at offset={offset}")

        captured_at = self._clock()
        if (
            not isinstance(captured_at, datetime)
            or captured_at.tzinfo is None
            or captured_at.utcoffset() is None
        ):
            self._fail("capture clock must return a timezone-aware datetime")

        try:
            document = _decode_json_or_jsonp(response.text)
        except ValueError as exc:
            self._fail(f"invalid JSON response at offset={offset}: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail(f"invalid Tencent response envelope at offset={offset}: expected object")
        self._check_status(document, f"response at offset={offset}")

        data = document.get("data")
        if not isinstance(data, dict):
            self._fail(f"invalid Tencent response envelope at offset={offset}: missing data object")
        self._check_status(data, f"data at offset={offset}")

        raw_rows = data.get("rank_list")
        if not isinstance(raw_rows, list):
            self._fail(f"invalid Tencent response at offset={offset}: data.rank_list must be an array")
        total = _parse_total(data.get("total"), offset=offset, fail=self._fail)
        response_offset = data.get("offset")
        if response_offset is not None:
            parsed_offset = _parse_total(response_offset, offset=offset, fail=self._fail, field="data.offset")
            if parsed_offset != offset:
                self._fail(
                    f"Tencent response offset mismatch: requested={offset}, received={parsed_offset}"
                )

        parsed_rows: list[_TencentMarketRow] = []
        for index, raw_row in enumerate(raw_rows):
            row_context = f"offset={offset}, row={index}"
            try:
                parsed_rows.append(
                    _parse_market_row(
                        raw_row,
                        captured_at=captured_at,
                        row_context=row_context,
                    )
                )
            except _RowParseFailure as exc:
                self._fail(f"invalid Tencent row at {row_context}: {exc}")
        return tuple(parsed_rows), total

    def _check_status(self, obj: Mapping[str, Any], context: str) -> None:
        error = obj.get("error")
        if error not in (None, "", 0, False):
            self._fail(f"Tencent error node at {context}: {_safe_value(error)}")
        for key in ("status", "code"):
            if key not in obj or obj[key] is None:
                continue
            value = obj[key]
            if isinstance(value, bool):
                success = value
            elif isinstance(value, (int, Decimal)):
                success = value in (0, 200)
            elif isinstance(value, str):
                success = value.strip().casefold() in {"0", "200", "ok", "success"}
            else:
                success = False
            if not success:
                self._fail(f"Tencent {key} indicates failure at {context}: {_safe_value(value)}")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)


def _reject_json_constant(token: str) -> NoReturn:
    raise ValueError(f"invalid JSON constant {token}")


def _decode_json_or_jsonp(text: str) -> Any:
    value = text.strip()
    if not value.startswith(("{", "[")):
        matched = _JSONP.fullmatch(value)
        if matched is None:
            raise ValueError("response is neither JSON nor JSONP")
        value = matched.group(1)
    return json.loads(
        value,
        parse_float=Decimal,
        parse_constant=_reject_json_constant,
    )


def _parse_market_row(
    raw: Any,
    *,
    captured_at: datetime,
    row_context: str,
) -> _TencentMarketRow:
    if not isinstance(raw, dict):
        raise _RowParseFailure("field row must be an object")

    source_code = _required_text(raw.get("code"), "code", row_context)
    if len(source_code) < 3:
        raise _RowParseFailure(f"field code has no code after a known market prefix: {_safe_value(source_code)}")
    prefix = source_code[:2].casefold()
    exchange = _PREFIX_EXCHANGES.get(prefix)
    if exchange is None:
        raise _RowParseFailure(f"field code has unknown prefix: {_safe_value(source_code)}")
    canonical_code = source_code[2:]
    if not canonical_code:
        raise _RowParseFailure("field code is empty after market prefix")
    try:
        instrument_id = normalize_symbol(
            canonical_code,
            market=Market.CN_A,
            exchange=exchange,
            kind=InstrumentKind.EQUITY,
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise _RowParseFailure(f"field code does not form a canonical equity identity: {type(exc).__name__}") from exc

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _RowParseFailure(f"field name is required and non-empty: {_safe_value(name)}")
    stock_type = raw.get("stock_type")
    if not isinstance(stock_type, str) or stock_type not in _EQUITY_STOCK_TYPES:
        raise _RowParseFailure(
            f"field stock_type is unsupported: {_safe_value(stock_type)}"
        )

    price = _optional_decimal(raw.get("zxj"), "zxj", row_context)
    price_change = _optional_decimal(raw.get("zd"), "zd", row_context)
    change_rate = _optional_percentage(raw.get("zdf"), "zdf", row_context)
    change_rate_5d = _optional_percentage(raw.get("zdf_d5"), "zdf_d5", row_context)
    change_rate_10d = _optional_percentage(raw.get("zdf_d10"), "zdf_d10", row_context)
    change_rate_20d = _optional_percentage(raw.get("zdf_d20"), "zdf_d20", row_context)
    change_rate_60d = _optional_percentage(raw.get("zdf_d60"), "zdf_d60", row_context)
    change_rate_52w = _optional_percentage(raw.get("zdf_w52"), "zdf_w52", row_context)
    change_rate_ytd = _optional_percentage(raw.get("zdf_y"), "zdf_y", row_context)
    amplitude = _optional_percentage(raw.get("zf"), "zf", row_context)
    volume_ratio = _optional_decimal(raw.get("lb"), "lb", row_context)
    volume_lots = _optional_decimal(raw.get("volume"), "volume", row_context)
    turnover_wan = _optional_decimal(raw.get("turnover"), "turnover", row_context)
    turnover_rate = _optional_percentage(raw.get("hsl"), "hsl", row_context)
    market_cap_yi = _optional_decimal(raw.get("zsz"), "zsz", row_context)
    float_cap_yi = _optional_decimal(raw.get("ltsz"), "ltsz", row_context)
    pe_ttm = _optional_decimal(raw.get("pe_ttm"), "pe_ttm", row_context)
    main_net_inflow_wan = _optional_decimal(raw.get("zljlr"), "zljlr", row_context)
    main_inflow_wan = _optional_decimal(raw.get("zllr"), "zllr", row_context)
    main_outflow_wan = _optional_decimal(raw.get("zllc"), "zllc", row_context)
    main_inflow_5d_wan = _optional_decimal(raw.get("zllr_d5"), "zllr_d5", row_context)
    main_outflow_5d_wan = _optional_decimal(raw.get("zllc_d5"), "zllc_d5", row_context)
    speed = _optional_decimal(raw.get("speed"), "speed", row_context)

    volume_shares: int | None = None
    if volume_lots is not None:
        shares = volume_lots * _DECIMAL_100
        if shares != shares.to_integral_value():
            raise _RowParseFailure(
                f"field volume cannot be represented as whole shares: {_safe_value(raw.get('volume'))}"
            )
        volume_shares = int(shares)
        if volume_shares < 0:
            raise _RowParseFailure(
                f"field volume must not be negative: {_safe_value(raw.get('volume'))}"
            )

    return _TencentMarketRow(
        instrument_id=instrument_id,
        source_code=source_code,
        stock_type=stock_type,
        name=name,
        price=price,
        price_change=price_change,
        change_rate=change_rate,
        change_rate_5d=change_rate_5d,
        change_rate_10d=change_rate_10d,
        change_rate_20d=change_rate_20d,
        change_rate_60d=change_rate_60d,
        change_rate_52w=change_rate_52w,
        change_rate_ytd=change_rate_ytd,
        amplitude=amplitude,
        volume_ratio=volume_ratio,
        volume=volume_shares,
        amount=None if turnover_wan is None else turnover_wan * _DECIMAL_10_000,
        turnover_rate=turnover_rate,
        market_cap=None if market_cap_yi is None else market_cap_yi * _DECIMAL_100_MILLION,
        float_market_cap=None if float_cap_yi is None else float_cap_yi * _DECIMAL_100_MILLION,
        pe_ttm=pe_ttm,
        main_net_inflow=None if main_net_inflow_wan is None else main_net_inflow_wan * _DECIMAL_10_000,
        main_inflow=None if main_inflow_wan is None else main_inflow_wan * _DECIMAL_10_000,
        main_outflow=None if main_outflow_wan is None else main_outflow_wan * _DECIMAL_10_000,
        main_inflow_5d=None if main_inflow_5d_wan is None else main_inflow_5d_wan * _DECIMAL_10_000,
        main_outflow_5d=None if main_outflow_5d_wan is None else main_outflow_5d_wan * _DECIMAL_10_000,
        speed=speed,
        captured_at=captured_at,
        row_context=row_context,
    )


def _required_text(value: Any, field: str, row_context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _RowParseFailure(
            f"field {field} is required and non-empty at {row_context}: {_safe_value(value)}"
        )
    return value


def _optional_decimal(value: Any, field: str, row_context: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text in _MISSING_NUMERIC:
            return None
    elif isinstance(value, bool):
        raise _RowParseFailure(f"field {field} is not numeric at {row_context}: {_safe_value(value)}")
    elif isinstance(value, Decimal):
        decimal_value = value
        text = ""
    elif isinstance(value, int):
        decimal_value = Decimal(value)
        text = ""
    else:
        raise _RowParseFailure(f"field {field} is not numeric at {row_context}: {_safe_value(value)}")

    if text:
        try:
            decimal_value = Decimal(text)
        except InvalidOperation as exc:
            raise _RowParseFailure(
                f"field {field} has invalid decimal at {row_context}: {_safe_value(value)}"
            ) from exc
    if not decimal_value.is_finite():
        raise _RowParseFailure(
            f"field {field} must be finite at {row_context}: {_safe_value(value)}"
        )
    return decimal_value


def _optional_percentage(value: Any, field: str, row_context: str) -> Decimal | None:
    percentage_points = _optional_decimal(value, field, row_context)
    return None if percentage_points is None else percentage_points / _DECIMAL_100


def _parse_total(
    value: Any,
    *,
    offset: int,
    fail: Callable[[str], NoReturn],
    field: str = "data.total",
) -> int:
    if isinstance(value, bool) or value is None:
        fail(f"invalid Tencent {field} at offset={offset}: {_safe_value(value)}")
    if isinstance(value, int):
        total = value
    elif isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value():
            fail(f"invalid Tencent {field} at offset={offset}: {_safe_value(value)}")
        total = int(value)
    elif isinstance(value, str) and _INTEGER_TEXT.fullmatch(value.strip()):
        total = int(value.strip())
    else:
        fail(f"invalid Tencent {field} at offset={offset}: {_safe_value(value)}")
    if total < 0:
        fail(f"invalid Tencent {field} at offset={offset}: {_safe_value(value)}")
    return total


def _safe_value(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 80 else f"{text[:77]}..."


def _validation_fields(exc: ValidationError) -> str:
    fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
    return ",".join(fields)
