"""EastMoney breadth and market-pool source adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from finchx.contracts import Source
from finchx.datasets.market_breadth import (
    MarketBreadthRequest,
    _BUCKETS_BY_SOURCE_CODE,
    _ProviderBreadth,
)
from finchx.datasets.market_broken_limit_pool import (
    MarketBrokenLimitPoolRequest,
    _ProviderBrokenLimitPoolRow,
)
from finchx.datasets.market_limit_down_pool import (
    MarketLimitDownPoolRequest,
    _ProviderLimitDownRow,
)
from finchx.datasets.market_limit_up_pool import (
    MarketLimitUpPoolRequest,
    _ProviderLimitUpRow,
)
from finchx.datasets.market_strong_pool import (
    MarketStrongPoolRequest,
    StrongPoolSelectionReason,
    _ProviderStrongPoolRow,
)
from finchx.datasets.market_yesterday_limit_up_pool import (
    MarketYesterdayLimitUpPoolRequest,
    _ProviderYesterdayLimitUpRow,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.errors import ProviderError
from finchx.providers.http import (
    DEFAULT_TIMEOUT_SECONDS,
    build_headers,
    http_status_failure_reason,
)


EASTMONEY_BREADTH_ENDPOINT = "https://push2ex.eastmoney.com/getTopicZDFenBu"
EASTMONEY_LIMIT_UP_POOL_ENDPOINT = "https://push2ex.eastmoney.com/getTopicZTPool"
EASTMONEY_LIMIT_DOWN_POOL_ENDPOINT = "https://push2ex.eastmoney.com/getTopicDTPool"
EASTMONEY_YESTERDAY_LIMIT_UP_POOL_ENDPOINT = "https://push2ex.eastmoney.com/getYesterdayZTPool"
EASTMONEY_STRONG_POOL_ENDPOINT = "https://push2ex.eastmoney.com/getTopicQSPool"
EASTMONEY_BROKEN_LIMIT_POOL_ENDPOINT = "https://push2ex.eastmoney.com/getTopicZBPool"

_UT = "7eea3edcaed734bea9cbfc24409ed989"
_DPT = "wz.ztzt"
_PAGE_SIZE = 1000
_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
_CALLBACK = "finchxEastmoney"
_JSONP = re.compile(r"^\s*[A-Za-z_$][A-Za-z0-9_$.]*\s*\((.*)\)\s*;?\s*$", re.DOTALL)
_HEADERS = build_headers(referer="https://quote.eastmoney.com/ztb/detail")
_EXCHANGE_BY_SOURCE_M = {0: Exchange.SZSE, 1: Exchange.SSE}
_MISSING_NUMBERS = frozenset({"", "-", "--"})


class _EastmoneyHttpResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class _EastmoneyTransportFailure(RuntimeError):
    pass


class _EastmoneyTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _EastmoneyHttpResponse: ...


class _UrllibEastmoneyTransport:
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _EastmoneyHttpResponse:
        query = urlencode(params)
        request = Request(f"{url}?{query}", headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return _EastmoneyHttpResponse(int(response.status), body.decode(charset))
        except HTTPError as exc:
            return _EastmoneyHttpResponse(int(exc.code), "")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            raise _EastmoneyTransportFailure(type(exc).__name__) from exc


class _EastmoneyProviderBase:
    def __init__(
        self,
        transport: _EastmoneyTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        page_size: int = _PAGE_SIZE,
    ) -> None:
        if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1 or page_size > _PAGE_SIZE:
            raise ValueError(f"page_size must be an integer from 1 through {_PAGE_SIZE}")
        self._transport = transport or _UrllibEastmoneyTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._page_size = page_size
        self._source = Source(providerId="eastmoney.push2ex")

    @property
    def source(self) -> Source:
        return self._source

    def _request_document(
        self,
        endpoint: str,
        params: Mapping[str, str | int],
    ) -> tuple[dict[str, Any], str]:
        request_url = f"{endpoint}?{urlencode(params)}"
        try:
            response = self._transport.get(
                endpoint,
                params=params,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _EastmoneyTransportFailure as exc:
            self._fail(f"EastMoney transport failure: {exc}")
        except Exception as exc:
            self._fail(f"EastMoney transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"EastMoney returned {status_reason}")
        if not response.text.strip():
            self._fail("EastMoney returned an empty body")
        matched = _JSONP.fullmatch(response.text)
        if matched is None:
            self._fail("EastMoney response is not a valid JSONP callback")
        try:
            document = json.loads(
                matched.group(1),
                parse_float=Decimal,
                parse_constant=self._reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"EastMoney JSONP contains malformed JSON ({type(exc).__name__})")
        if not isinstance(document, dict):
            self._fail("EastMoney JSONP payload root must be an object")
        self._validate_rc(document)
        return document, request_url

    def _validate_rc(self, document: Mapping[str, Any]) -> None:
        rc = document.get("rc")
        if isinstance(rc, bool) or rc not in (0, "0"):
            self._fail(f"EastMoney source rc indicates failure: {rc!r}")

    def _page_data(
        self,
        document: Mapping[str, Any],
        *,
        requested_date: date,
        page_index: int,
    ) -> tuple[dict[str, Any], int, list[Mapping[str, Any]]]:
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail(f"EastMoney page {page_index} omitted data object")
        qdate = self._source_date(data.get("qdate"), "data.qdate")
        if qdate != requested_date:
            self._fail(
                f"EastMoney qdate mismatch: requested {requested_date.isoformat()}, got {qdate.isoformat()}"
            )
        tc = self._integer(data.get("tc"), "data.tc")
        if tc < 0:
            self._fail("EastMoney data.tc must not be negative")
        pool = data.get("pool")
        if not isinstance(pool, list):
            self._fail(f"EastMoney page {page_index} pool must be an array")
        if not all(isinstance(row, dict) for row in pool):
            self._fail(f"EastMoney page {page_index} contains a non-object pool row")
        return data, tc, pool

    def _breadth_data(self, document: Mapping[str, Any]) -> Mapping[str, Any]:
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("EastMoney breadth response omitted data object")
        return data

    def _source_date(self, value: object, label: str) -> date:
        if isinstance(value, bool):
            self._fail(f"EastMoney {label} must be YYYYMMDD")
        text = str(value)
        if not re.fullmatch(r"[0-9]{8}", text):
            self._fail(f"EastMoney {label} must be YYYYMMDD")
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            self._fail(f"EastMoney {label} is not a valid calendar date")

    def _instrument(self, raw: Mapping[str, Any], *, context: str) -> InstrumentId:
        code = raw.get("c")
        if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
            self._fail(f"{context}.c must be a six-character numeric code")
        market_number = self._integer(raw.get("m"), f"{context}.m")
        exchange = _EXCHANGE_BY_SOURCE_M.get(market_number)
        if exchange is None:
            self._fail(f"{context}.m has no verified FinchX exchange mapping: {market_number}")
        return InstrumentId(
            code=code,
            market=Market.CN_A,
            kind=InstrumentKind.EQUITY,
            exchange=exchange,
        )

    def _source_row_shape(
        self,
        raw: Mapping[str, Any],
        *,
        allowed: set[str],
        required: set[str],
        context: str,
    ) -> None:
        keys = set(raw)
        missing = required - keys
        unexpected = keys - allowed
        if missing:
            self._fail(f"{context} omitted required fields: {', '.join(sorted(missing))}")
        if unexpected:
            self._fail(f"{context} schema drift added fields: {', '.join(sorted(unexpected))}")

    def _decimal(self, value: object, label: str) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            self._fail(f"EastMoney {label} must be a numeric source value")
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            self._fail(f"EastMoney {label} is not a valid Decimal ({type(exc).__name__})")
        if not parsed.is_finite():
            self._fail(f"EastMoney {label} must be finite")
        return parsed

    def _optional_decimal(self, value: object, label: str) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in _MISSING_NUMBERS):
            return None
        parsed = self._decimal(value, label)
        return parsed

    def _integer(self, value: object, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            self._fail(f"EastMoney {label} must be an integer source value")
        try:
            parsed = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            self._fail(f"EastMoney {label} is not an integer ({type(exc).__name__})")
        if not parsed.is_finite() or parsed != parsed.to_integral_value():
            self._fail(f"EastMoney {label} must be a finite integer")
        return int(parsed)

    def _optional_integer(self, value: object, label: str) -> int | None:
        if value is None or (isinstance(value, str) and value.strip() in _MISSING_NUMBERS):
            return None
        return self._integer(value, label)

    def _source_time(self, value: object, label: str) -> str | None:
        if value is None or (isinstance(value, str) and value.strip() in _MISSING_NUMBERS):
            return None
        source_time = self._integer(value, label)
        if source_time == 0:
            return None
        text = str(source_time).zfill(6)
        if not re.fullmatch(r"[0-9]{6}", text):
            self._fail(f"EastMoney {label} is not HHMMSS")
        try:
            parsed = datetime.strptime(text, "%H%M%S")
        except ValueError:
            self._fail(f"EastMoney {label} is not a valid HHMMSS time")
        return parsed.strftime("%H:%M:%S")

    def _zttj(self, raw: object, label: str) -> tuple[int, int]:
        if not isinstance(raw, dict):
            self._fail(f"EastMoney {label} must be an object")
        if set(raw) != {"days", "ct"}:
            self._fail(f"EastMoney {label} must contain exactly days and ct")
        days = self._integer(raw.get("days"), f"{label}.days")
        count = self._integer(raw.get("ct"), f"{label}.ct")
        if days < 0 or count < 0 or count > days:
            self._fail(f"EastMoney {label} has invalid day / limit-up counts")
        return days, count

    def _required_text(self, value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            self._fail(f"{label} must be non-empty text")
        return value

    def _positive_integer(self, value: object, label: str) -> int:
        parsed = self._integer(value, label)
        if parsed <= 0:
            self._fail(f"{label} must be positive")
        return parsed

    def _non_negative_integer(self, value: object, label: str) -> int:
        parsed = self._integer(value, label)
        if parsed < 0:
            self._fail(f"{label} must not be negative")
        return parsed

    def _boolean_flag(self, value: object, label: str) -> bool:
        parsed = self._integer(value, label)
        if parsed not in (0, 1):
            self._fail(f"{label} must be 0 or 1")
        return parsed == 1

    def _captured_at(self) -> datetime:
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return captured_at

    def _common_params(self) -> dict[str, str | int]:
        return {
            "cb": _CALLBACK,
            "ut": _UT,
            "dpt": _DPT,
            "_": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
        }

    @staticmethod
    def _reject_json_constant(value: str) -> NoReturn:
        raise ValueError(f"non-finite JSON constant {value}")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self._source, reason)



class EastmoneyBreadthProvider(_EastmoneyProviderBase):
    """Fetch and validate EastMoney's 23-bucket breadth snapshot."""

    def fetch_raw_breadth(self, request: MarketBreadthRequest) -> _ProviderBreadth:
        if not isinstance(request, MarketBreadthRequest):
            self._fail("request must be a MarketBreadthRequest")
        params = self._common_params()
        document, request_url = self._request_document(EASTMONEY_BREADTH_ENDPOINT, params)
        data = self._breadth_data(document)
        trade_date = self._source_date(data.get("qdate"), "data.qdate")
        fenbu = data.get("fenbu")
        if not isinstance(fenbu, list) or len(fenbu) != len(_BUCKETS_BY_SOURCE_CODE):
            self._fail("EastMoney data.fenbu must contain one object per breadth bucket")
        raw_buckets: dict[str, Any] = {}
        for index, item in enumerate(fenbu):
            if not isinstance(item, dict) or len(item) != 1:
                self._fail(f"EastMoney data.fenbu[{index}] must contain exactly one bucket")
            bucket_key = next(iter(item))
            if bucket_key in raw_buckets:
                self._fail(f"EastMoney data.fenbu contains duplicate bucket {bucket_key}")
            raw_buckets[bucket_key] = item[bucket_key]
        expected_keys = {str(code) for code in _BUCKETS_BY_SOURCE_CODE}
        if set(raw_buckets) != expected_keys:
            self._fail("EastMoney breadth distribution is missing buckets or has schema drift")
        counts = {
            code: self._integer(raw_buckets[str(code)], f"data.fenbu.{code}")
            for code in _BUCKETS_BY_SOURCE_CODE
        }
        if any(count < 0 for count in counts.values()):
            self._fail("EastMoney breadth counts must not be negative")
        captured_at = self._captured_at()
        return _ProviderBreadth(
            trade_date=trade_date,
            counts_by_source_code=counts,
            source_record_id=f"{trade_date.isoformat()}:fenbu",
            source_url=request_url,
            captured_at=captured_at,
        )


class EastmoneyLimitUpPoolProvider(_EastmoneyProviderBase):
    """Fetch the separate EastMoney limit-up pool and normalize its own row shape."""

    def fetch_raw_limit_up_pool(
        self, request: MarketLimitUpPoolRequest
    ) -> tuple[_ProviderLimitUpRow, ...]:
        if not isinstance(request, MarketLimitUpPoolRequest):
            self._fail("request must be a MarketLimitUpPoolRequest")
        rows: list[tuple[Mapping[str, Any], str]] = []
        expected_total: int | None = None
        seen: set[tuple[str, str]] = set()
        page_index = 0
        while expected_total is None or len(rows) < expected_total:
            params = self._common_params()
            params.update({
                "Pageindex": page_index,
                "pagesize": self._page_size,
                "sort": "fbt:asc",
                "date": request.trade_date.strftime("%Y%m%d"),
            })
            document, request_url = self._request_document(EASTMONEY_LIMIT_UP_POOL_ENDPOINT, params)
            _, total, page_rows = self._page_data(document, requested_date=request.trade_date, page_index=page_index)
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                self._fail("EastMoney limit-up pool tc changed between pages")
            if expected_total == 0:
                if page_rows:
                    self._fail("EastMoney limit-up pool returned rows with tc=0")
                break
            if not page_rows:
                self._fail(f"EastMoney limit-up pool page {page_index} is empty before tc was reached")
            if len(page_rows) > self._page_size or len(rows) + len(page_rows) > expected_total:
                self._fail("EastMoney limit-up pool page size exceeds requested tc")
            for raw in page_rows:
                instrument = self._instrument(raw, context="limit-up pool row")
                identity = (instrument.exchange.value, instrument.code)
                if identity in seen:
                    self._fail(f"EastMoney limit-up pool repeated instrument {instrument.code}")
                seen.add(identity)
                rows.append((raw, request_url))
            if len(rows) < expected_total and len(page_rows) < self._page_size:
                self._fail("EastMoney limit-up pool ended on a short page before tc")
            page_index += 1
        if expected_total is None or len(rows) != expected_total:
            self._fail("EastMoney limit-up pool returned an incomplete count")
        captured_at = self._captured_at()
        allowed = {"c", "m", "n", "p", "zdp", "amount", "ltsz", "tshare", "hs", "lbc", "fbt", "lbt", "fund", "zbc", "hybk", "zttj"}
        parsed: list[_ProviderLimitUpRow] = []
        for raw, request_url in rows:
            self._source_row_shape(raw, allowed=allowed, required=allowed, context="limit-up row")
            instrument = self._instrument(raw, context="limit-up row")
            name = self._required_text(raw.get("n"), "limit-up row.n")
            days, count = self._zttj(raw.get("zttj"), "limit-up row.zttj")
            parsed.append(_ProviderLimitUpRow(
                instrument_id=instrument,
                trade_date=request.trade_date,
                name=name,
                price_milli_cny=self._decimal(raw.get("p"), "limit-up row.p"),
                change_percent_points=self._decimal(raw.get("zdp"), "limit-up row.zdp"),
                amount_cny=self._decimal(raw.get("amount"), "limit-up row.amount"),
                float_market_cap_cny=self._decimal(raw.get("ltsz"), "limit-up row.ltsz"),
                market_cap_cny=self._decimal(raw.get("tshare"), "limit-up row.tshare"),
                turnover_percent_points=self._decimal(raw.get("hs"), "limit-up row.hs"),
                consecutive_days=self._positive_integer(raw.get("lbc"), "limit-up row.lbc"),
                first_limit_up_time=self._source_time(raw.get("fbt"), "limit-up row.fbt"),
                last_limit_up_time=self._source_time(raw.get("lbt"), "limit-up row.lbt"),
                limit_up_queue_amount_cny=self._optional_decimal(raw.get("fund"), "limit-up row.fund"),
                break_count=self._non_negative_integer(raw.get("zbc"), "limit-up row.zbc"),
                industry=self._required_text(raw.get("hybk"), "limit-up row.hybk"),
                stats_days=days,
                stats_count=count,
                source_record_id=f"{request.trade_date.isoformat()}:{instrument.exchange.value}:{instrument.code}",
                source_url=request_url,
                captured_at=captured_at,
            ))
        return tuple(parsed)


class EastmoneyLimitDownPoolProvider(_EastmoneyProviderBase):
    """Fetch the separate EastMoney limit-down pool and its down-specific fields."""

    def fetch_raw_limit_down_pool(
        self, request: MarketLimitDownPoolRequest
    ) -> tuple[_ProviderLimitDownRow, ...]:
        if not isinstance(request, MarketLimitDownPoolRequest):
            self._fail("request must be a MarketLimitDownPoolRequest")
        rows: list[tuple[Mapping[str, Any], str]] = []
        expected_total: int | None = None
        seen: set[tuple[str, str]] = set()
        page_index = 0
        while expected_total is None or len(rows) < expected_total:
            params = self._common_params()
            params.update({"Pageindex": page_index, "pagesize": self._page_size, "sort": "fund:asc", "date": request.trade_date.strftime("%Y%m%d")})
            document, request_url = self._request_document(EASTMONEY_LIMIT_DOWN_POOL_ENDPOINT, params)
            _, total, page_rows = self._page_data(document, requested_date=request.trade_date, page_index=page_index)
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                self._fail("EastMoney limit-down pool tc changed between pages")
            if expected_total == 0:
                if page_rows:
                    self._fail("EastMoney limit-down pool returned rows with tc=0")
                break
            if not page_rows:
                self._fail(f"EastMoney limit-down pool page {page_index} is empty before tc was reached")
            if len(page_rows) > self._page_size or len(rows) + len(page_rows) > expected_total:
                self._fail("EastMoney limit-down pool page size exceeds requested tc")
            for raw in page_rows:
                instrument = self._instrument(raw, context="limit-down pool row")
                identity = (instrument.exchange.value, instrument.code)
                if identity in seen:
                    self._fail(f"EastMoney limit-down pool repeated instrument {instrument.code}")
                seen.add(identity)
                rows.append((raw, request_url))
            if len(rows) < expected_total and len(page_rows) < self._page_size:
                self._fail("EastMoney limit-down pool ended on a short page before tc")
            page_index += 1
        if expected_total is None or len(rows) != expected_total:
            self._fail("EastMoney limit-down pool returned an incomplete count")
        captured_at = self._captured_at()
        allowed = {"c", "m", "n", "p", "zdp", "amount", "ltsz", "tshare", "pe", "hs", "fund", "lbt", "fba", "days", "oc", "hybk"}
        required = allowed - {"pe"}
        parsed: list[_ProviderLimitDownRow] = []
        for raw, request_url in rows:
            self._source_row_shape(raw, allowed=allowed, required=required, context="limit-down row")
            instrument = self._instrument(raw, context="limit-down row")
            parsed.append(_ProviderLimitDownRow(
                instrument_id=instrument,
                trade_date=request.trade_date,
                name=self._required_text(raw.get("n"), "limit-down row.n"),
                price_milli_cny=self._decimal(raw.get("p"), "limit-down row.p"),
                change_percent_points=self._decimal(raw.get("zdp"), "limit-down row.zdp"),
                amount_cny=self._decimal(raw.get("amount"), "limit-down row.amount"),
                float_market_cap_cny=self._decimal(raw.get("ltsz"), "limit-down row.ltsz"),
                market_cap_cny=self._decimal(raw.get("tshare"), "limit-down row.tshare"),
                price_earnings_ratio=self._optional_decimal(raw.get("pe"), "limit-down row.pe"),
                turnover_percent_points=self._decimal(raw.get("hs"), "limit-down row.hs"),
                limit_down_queue_amount_cny=self._optional_decimal(raw.get("fund"), "limit-down row.fund"),
                last_limit_down_time=self._source_time(raw.get("lbt"), "limit-down row.lbt"),
                board_traded_amount_cny=self._optional_decimal(raw.get("fba"), "limit-down row.fba"),
                consecutive_days=self._positive_integer(raw.get("days"), "limit-down row.days"),
                open_count=self._non_negative_integer(raw.get("oc"), "limit-down row.oc"),
                industry=self._required_text(raw.get("hybk"), "limit-down row.hybk"),
                source_record_id=f"{request.trade_date.isoformat()}:{instrument.exchange.value}:{instrument.code}",
                source_url=request_url,
                captured_at=captured_at,
            ))
        return tuple(parsed)


class EastmoneyYesterdayLimitUpPoolProvider(_EastmoneyProviderBase):
    """Fetch yesterday's limit-up set with current-session performance fields."""

    def fetch_raw_yesterday_limit_up_pool(
        self, request: MarketYesterdayLimitUpPoolRequest
    ) -> tuple[_ProviderYesterdayLimitUpRow, ...]:
        if not isinstance(request, MarketYesterdayLimitUpPoolRequest):
            self._fail("request must be a MarketYesterdayLimitUpPoolRequest")
        rows: list[tuple[Mapping[str, Any], str]] = []
        expected_total: int | None = None
        seen: set[tuple[str, str]] = set()
        page_index = 0
        while expected_total is None or len(rows) < expected_total:
            params = self._common_params()
            params.update({"Pageindex": page_index, "pagesize": self._page_size, "sort": "zs:desc", "date": request.trade_date.strftime("%Y%m%d")})
            document, request_url = self._request_document(EASTMONEY_YESTERDAY_LIMIT_UP_POOL_ENDPOINT, params)
            _, total, page_rows = self._page_data(document, requested_date=request.trade_date, page_index=page_index)
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                self._fail("EastMoney yesterday limit-up pool tc changed between pages")
            if expected_total == 0:
                if page_rows:
                    self._fail("EastMoney yesterday limit-up pool returned rows with tc=0")
                break
            if not page_rows:
                self._fail(f"EastMoney yesterday limit-up pool page {page_index} is empty before tc was reached")
            if len(page_rows) > self._page_size or len(rows) + len(page_rows) > expected_total:
                self._fail("EastMoney yesterday limit-up pool page size exceeds requested tc")
            for raw in page_rows:
                instrument = self._instrument(raw, context="yesterday limit-up row")
                identity = (instrument.exchange.value, instrument.code)
                if identity in seen:
                    self._fail(f"EastMoney yesterday limit-up pool repeated instrument {instrument.code}")
                seen.add(identity)
                rows.append((raw, request_url))
            if len(rows) < expected_total and len(page_rows) < self._page_size:
                self._fail("EastMoney yesterday limit-up pool ended on a short page before tc")
            page_index += 1
        if expected_total is None or len(rows) != expected_total:
            self._fail("EastMoney yesterday limit-up pool returned an incomplete count")
        captured_at = self._captured_at()
        allowed = {"c", "m", "n", "p", "ztp", "zdp", "amount", "ltsz", "tshare", "hs", "zf", "zs", "yfbt", "ylbc", "hybk", "zttj"}
        parsed: list[_ProviderYesterdayLimitUpRow] = []
        for raw, request_url in rows:
            self._source_row_shape(raw, allowed=allowed, required=allowed, context="yesterday limit-up row")
            instrument = self._instrument(raw, context="yesterday limit-up row")
            stats_days, stats_count = self._zttj(raw.get("zttj"), "yesterday limit-up row.zttj")
            parsed.append(_ProviderYesterdayLimitUpRow(
                instrument_id=instrument,
                trade_date=request.trade_date,
                name=self._required_text(raw.get("n"), "yesterday limit-up row.n"),
                current_price_milli_cny=self._decimal(raw.get("p"), "yesterday limit-up row.p"),
                current_limit_up_price_milli_cny=self._decimal(raw.get("ztp"), "yesterday limit-up row.ztp"),
                change_percent_points=self._decimal(raw.get("zdp"), "yesterday limit-up row.zdp"),
                amount_cny=self._decimal(raw.get("amount"), "yesterday limit-up row.amount"),
                float_market_cap_cny=self._decimal(raw.get("ltsz"), "yesterday limit-up row.ltsz"),
                market_cap_cny=self._decimal(raw.get("tshare"), "yesterday limit-up row.tshare"),
                turnover_percent_points=self._decimal(raw.get("hs"), "yesterday limit-up row.hs"),
                amplitude_percent_points=self._decimal(raw.get("zf"), "yesterday limit-up row.zf"),
                speed_raw=self._optional_decimal(raw.get("zs"), "yesterday limit-up row.zs"),
                yesterday_first_limit_up_time=self._source_time(raw.get("yfbt"), "yesterday limit-up row.yfbt"),
                yesterday_consecutive_days=self._positive_integer(raw.get("ylbc"), "yesterday limit-up row.ylbc"),
                stats_days_raw=stats_days,
                stats_count_raw=stats_count,
                industry=self._required_text(raw.get("hybk"), "yesterday limit-up row.hybk"),
                source_record_id=f"{request.trade_date.isoformat()}:{instrument.exchange.value}:{instrument.code}",
                source_url=request_url,
                captured_at=captured_at,
            ))
        return tuple(parsed)


class EastmoneyStrongPoolProvider(_EastmoneyProviderBase):
    """Fetch the separate EastMoney strong pool."""

    def fetch_raw_strong_pool(
        self, request: MarketStrongPoolRequest
    ) -> tuple[_ProviderStrongPoolRow, ...]:
        if not isinstance(request, MarketStrongPoolRequest):
            self._fail("request must be a MarketStrongPoolRequest")
        rows: list[tuple[Mapping[str, Any], str]] = []
        expected_total: int | None = None
        seen: set[tuple[str, str]] = set()
        page_index = 0
        while expected_total is None or len(rows) < expected_total:
            params = self._common_params()
            params.update({"Pageindex": page_index, "pagesize": self._page_size, "sort": "zdp:desc", "date": request.trade_date.strftime("%Y%m%d")})
            document, request_url = self._request_document(EASTMONEY_STRONG_POOL_ENDPOINT, params)
            _, total, page_rows = self._page_data(document, requested_date=request.trade_date, page_index=page_index)
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                self._fail("EastMoney strong pool tc changed between pages")
            if expected_total == 0:
                if page_rows:
                    self._fail("EastMoney strong pool returned rows with tc=0")
                break
            if not page_rows:
                self._fail(f"EastMoney strong pool page {page_index} is empty before tc was reached")
            if len(page_rows) > self._page_size or len(rows) + len(page_rows) > expected_total:
                self._fail("EastMoney strong pool page size exceeds requested tc")
            for raw in page_rows:
                instrument = self._instrument(raw, context="strong-pool row")
                identity = (instrument.exchange.value, instrument.code)
                if identity in seen:
                    self._fail(f"EastMoney strong pool repeated instrument {instrument.code}")
                seen.add(identity)
                rows.append((raw, request_url))
            if len(rows) < expected_total and len(page_rows) < self._page_size:
                self._fail("EastMoney strong pool ended on a short page before tc")
            page_index += 1
        if expected_total is None or len(rows) != expected_total:
            self._fail("EastMoney strong pool returned an incomplete count")
        captured_at = self._captured_at()
        allowed = {"c", "m", "n", "p", "ztp", "ztf", "zdp", "amount", "ltsz", "tshare", "hs", "nh", "cc", "lb", "zs", "zttj", "hybk"}
        parsed: list[_ProviderStrongPoolRow] = []
        for raw, request_url in rows:
            self._source_row_shape(raw, allowed=allowed, required=allowed, context="strong-pool row")
            instrument = self._instrument(raw, context="strong-pool row")
            new_high = self._boolean_flag(raw.get("nh"), "strong-pool row.nh")
            code = self._integer(raw.get("cc"), "strong-pool row.cc")
            reason_by_code = {
                1: StrongPoolSelectionReason.SIXTY_DAY_HIGH,
                2: StrongPoolSelectionReason.RECENT_MULTIPLE_LIMIT_UPS,
                3: StrongPoolSelectionReason.SIXTY_DAY_HIGH_AND_RECENT_MULTIPLE_LIMIT_UPS,
            }
            reason = reason_by_code.get(code)
            if reason is None:
                self._fail(f"strong-pool row.cc has unknown selection reason {code}")
            if (code in (1, 3)) != new_high:
                self._fail("strong-pool row.cc and nh selection reason disagree")
            days, count = self._zttj(raw.get("zttj"), "strong-pool row.zttj")
            ztf = raw.get("ztf")
            if ztf is not None and not isinstance(ztf, (str, int)):
                self._fail("strong-pool row.ztf has unexpected source type")
            parsed.append(_ProviderStrongPoolRow(
                instrument_id=instrument,
                trade_date=request.trade_date,
                name=self._required_text(raw.get("n"), "strong-pool row.n"),
                price_milli_cny=self._decimal(raw.get("p"), "strong-pool row.p"),
                limit_up_price_milli_cny=self._decimal(raw.get("ztp"), "strong-pool row.ztp"),
                change_percent_points=self._decimal(raw.get("zdp"), "strong-pool row.zdp"),
                amount_cny=self._decimal(raw.get("amount"), "strong-pool row.amount"),
                float_market_cap_cny=self._decimal(raw.get("ltsz"), "strong-pool row.ltsz"),
                market_cap_cny=self._decimal(raw.get("tshare"), "strong-pool row.tshare"),
                turnover_percent_points=self._decimal(raw.get("hs"), "strong-pool row.hs"),
                is_sixty_day_high=new_high,
                selection_reason=reason,
                volume_ratio=self._decimal(raw.get("lb"), "strong-pool row.lb"),
                speed_raw=self._optional_decimal(raw.get("zs"), "strong-pool row.zs"),
                ztf_raw=None if ztf is None else str(ztf),
                stats_days=days,
                stats_count=count,
                industry=self._required_text(raw.get("hybk"), "strong-pool row.hybk"),
                source_record_id=f"{request.trade_date.isoformat()}:{instrument.exchange.value}:{instrument.code}",
                source_url=request_url,
                captured_at=captured_at,
            ))
        return tuple(parsed)


class EastmoneyBrokenLimitPoolProvider(_EastmoneyProviderBase):
    """Fetch the current-day pool of stocks that opened after touching limit-up."""

    def fetch_raw_broken_limit_pool(
        self, request: MarketBrokenLimitPoolRequest
    ) -> tuple[_ProviderBrokenLimitPoolRow, ...]:
        if not isinstance(request, MarketBrokenLimitPoolRequest):
            self._fail("request must be a MarketBrokenLimitPoolRequest")
        rows: list[tuple[Mapping[str, Any], str]] = []
        expected_total: int | None = None
        seen: set[tuple[str, str]] = set()
        page_index = 0
        while expected_total is None or len(rows) < expected_total:
            params = self._common_params()
            params.update({"Pageindex": page_index, "pagesize": self._page_size, "sort": "fbt:asc", "date": request.trade_date.strftime("%Y%m%d")})
            document, request_url = self._request_document(EASTMONEY_BROKEN_LIMIT_POOL_ENDPOINT, params)
            _, total, page_rows = self._page_data(document, requested_date=request.trade_date, page_index=page_index)
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                self._fail("EastMoney broken-limit pool tc changed between pages")
            if expected_total == 0:
                if page_rows:
                    self._fail("EastMoney broken-limit pool returned rows with tc=0")
                break
            if not page_rows:
                self._fail(f"EastMoney broken-limit pool page {page_index} is empty before tc was reached")
            if len(page_rows) > self._page_size or len(rows) + len(page_rows) > expected_total:
                self._fail("EastMoney broken-limit pool page size exceeds requested tc")
            for raw in page_rows:
                instrument = self._instrument(raw, context="broken-limit row")
                identity = (instrument.exchange.value, instrument.code)
                if identity in seen:
                    self._fail(f"EastMoney broken-limit pool repeated instrument {instrument.code}")
                seen.add(identity)
                rows.append((raw, request_url))
            if len(rows) < expected_total and len(page_rows) < self._page_size:
                self._fail("EastMoney broken-limit pool ended on a short page before tc")
            page_index += 1
        if expected_total is None or len(rows) != expected_total:
            self._fail("EastMoney broken-limit pool returned an incomplete count")
        captured_at = self._captured_at()
        allowed = {"c", "m", "n", "p", "ztp", "zdp", "amount", "ltsz", "tshare", "hs", "fbt", "zbc", "zf", "zs", "zttj", "hybk"}
        parsed: list[_ProviderBrokenLimitPoolRow] = []
        for raw, request_url in rows:
            self._source_row_shape(raw, allowed=allowed, required=allowed, context="broken-limit row")
            instrument = self._instrument(raw, context="broken-limit row")
            days, count = self._zttj(raw.get("zttj"), "broken-limit row.zttj")
            parsed.append(_ProviderBrokenLimitPoolRow(
                instrument_id=instrument,
                trade_date=request.trade_date,
                name=self._required_text(raw.get("n"), "broken-limit row.n"),
                price_milli_cny=self._decimal(raw.get("p"), "broken-limit row.p"),
                limit_up_price_milli_cny=self._decimal(raw.get("ztp"), "broken-limit row.ztp"),
                change_percent_points=self._decimal(raw.get("zdp"), "broken-limit row.zdp"),
                amount_cny=self._decimal(raw.get("amount"), "broken-limit row.amount"),
                float_market_cap_cny=self._decimal(raw.get("ltsz"), "broken-limit row.ltsz"),
                market_cap_cny=self._decimal(raw.get("tshare"), "broken-limit row.tshare"),
                turnover_percent_points=self._decimal(raw.get("hs"), "broken-limit row.hs"),
                amplitude_percent_points=self._decimal(raw.get("zf"), "broken-limit row.zf"),
                first_limit_up_time=self._source_time(raw.get("fbt"), "broken-limit row.fbt"),
                break_count=self._positive_integer(raw.get("zbc"), "broken-limit row.zbc"),
                speed_raw=self._optional_decimal(raw.get("zs"), "broken-limit row.zs"),
                stats_days=days,
                stats_count=count,
                industry=self._required_text(raw.get("hybk"), "broken-limit row.hybk"),
                source_record_id=f"{request.trade_date.isoformat()}:{instrument.exchange.value}:{instrument.code}",
                source_url=request_url,
                captured_at=captured_at,
            ))
        return tuple(parsed)
