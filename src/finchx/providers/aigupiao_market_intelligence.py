"""Aigupiao market sentiment, consecutive-limit-up, and Dragon Tiger adapters."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
import time
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from finchx.contracts import Source
from finchx.datasets.market_consecutive_limit_up import (
    MarketConsecutiveLimitUpRequest,
    _ProviderConsecutiveLimitUpRow,
)
from finchx.datasets.market_dragon_tiger import (
    MarketDragonTigerDetailRequest,
    MarketDragonTigerListRequest,
    _ProviderDragonTigerDetail,
    _ProviderDragonTigerListRow,
    _ProviderDragonTigerSeat,
)
from finchx.datasets.market_sentiment import (
    MarketSentimentRequest,
    _ProviderMarketSentiment,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, build_headers, http_status_failure_reason


AIGUPIAO_MARKET_SENTIMENT_ENDPOINT = (
    "https://igp-img-upload-1251605428.cos.ap-shanghai.myqcloud.com/"
    "cos_data/market_sentiment_list_client.json"
)
AIGUPIAO_SERIES_LIMIT_UP_ENDPOINT = "https://app.aigupiao.com/stock/getAnalysisInfo"
AIGUPIAO_DRAGON_TIGER_LIST_ENDPOINT = "https://app.aigupiao.com/goapi/dragon_tiger/lists"
AIGUPIAO_DRAGON_TIGER_DETAIL_ENDPOINT = "https://app.aigupiao.com/goapi/dragon_tiger/deal_detail"

_SENTIMENT_FIELDS = {
    "market_temperature",
    "total_turnover",
    "turnover_chg",
    "forecasted_turnover",
    "turnover_growing_data",
    "median_val",
    "blast_break_pct",
    "limit_up_break_chg_pct",
    "stop_trad_stock_num",
    "one_limit_up_stock_num",
    "two_limit_up_stock_num",
    "three_limit_up_stock_num",
    "high_limit_up_stock_num",
    "two_limit_up_stock_rate",
    "three_limit_up_stock_rate",
    "high_limit_up_stock_rate",
    "raising_limit_theme_chg_pct",
    "repetition_limit_theme_chg_pct",
}
_SERIES_FIELDS = {
    "last_price",
    "change_pct",
    "code",
    "name",
    "limit_up_time",
    "day",
    "x_series_limit_up",
    "series_limit_up",
    "state",
    "last_day_continuous_up_times",
    "turnover_rate",
    "amount",
    "whole",
    "chg",
    "ltg",
    "zgb",
    "theme_id",
    "theme_name",
}
_DRAGON_LIST_FIELDS = {
    "code",
    "name",
    "explanation",
    "close_price",
    "change_rate",
    "accum_amount",
    "total_buy",
    "is_stock_list",
    "total_net",
    "three_day_flag",
    "trade_id",
    "theme_id",
    "theme_name",
    "flag",
    "theme_info",
}
_DRAGON_DETAIL_FIELDS = {
    "accum_amount",
    "buy_fives",
    "change_rate",
    "close_price",
    "code",
    "comment_kind",
    "comment_o_id",
    "explanation",
    "name",
    "sell_fives",
    "total_buy",
    "total_net",
    "total_sell",
}
_SEAT_FIELDS = {
    "name",
    "code",
    "has_details",
    "buy",
    "sell",
    "net",
    "buy_percentage",
    "sell_percentage",
    "flag",
}
_SOURCE_PREFIX_TO_EXCHANGE = {"sh": Exchange.SSE, "sz": Exchange.SZSE, "bj": Exchange.BSE}
_EXCHANGE_TO_SOURCE_PREFIX = {value: key for key, value in _SOURCE_PREFIX_TO_EXCHANGE.items()}
_AMOUNT_UNITS = {"万亿": Decimal("1000000000000"), "亿": Decimal("100000000"), "万": Decimal("10000"), "元": Decimal("1")}
_AMOUNT_PATTERN = re.compile(r"^([+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+))(?:(万亿|亿|万|元))?$")
_PERCENT_PATTERN = re.compile(r"^([+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+))%$")
_TEMPERATURE_PATTERN = re.compile(r"^([+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+))°C$")


class _AigupiaoHttpResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class _AigupiaoTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _AigupiaoHttpResponse: ...


class _UrllibAigupiaoTransport:
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _AigupiaoHttpResponse:
        request = Request(f"{url}?{urlencode(params)}", headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return _AigupiaoHttpResponse(int(response.status), body.decode(charset))
        except HTTPError as exc:
            return _AigupiaoHttpResponse(int(exc.code), "")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            raise RuntimeError(type(exc).__name__) from exc


class _AigupiaoBase:
    def __init__(self, transport: _AigupiaoTransport | None, *, clock: Any | None, source: Source, headers: Mapping[str, str]) -> None:
        self._transport = transport or _UrllibAigupiaoTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = source
        self._headers = dict(headers)

    @property
    def source(self) -> Source:
        return self._source

    def _captured(self) -> datetime:
        captured = self._clock()
        if captured.tzinfo is None or captured.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return captured

    def _request(self, endpoint: str, params: Mapping[str, str | int]) -> tuple[dict[str, Any], str]:
        request_url = f"{endpoint}?{urlencode(params)}"
        try:
            response = self._transport.get(
                endpoint,
                params=params,
                headers=self._headers,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            self._fail(f"transport failure: {type(exc).__name__}")
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            self._fail(reason)
        if not response.text.strip():
            self._fail("empty response body")
        try:
            document = json.loads(response.text, parse_float=Decimal, parse_constant=self._reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"malformed JSON response ({type(exc).__name__})")
        if not isinstance(document, dict):
            self._fail("response root must be an object")
        return document, request_url

    @staticmethod
    def _reject_json_constant(value: str) -> NoReturn:
        raise ValueError(f"unsupported JSON constant: {value}")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)

    def _require_keys(self, value: Mapping[str, Any], expected: set[str], context: str) -> None:
        keys = set(value)
        missing = expected - keys
        unexpected = keys - expected
        if missing:
            self._fail(f"{context} omitted required fields: {', '.join(sorted(missing))}")
        if unexpected:
            self._fail(f"{context} schema drift added fields: {', '.join(sorted(unexpected))}")

    def _text(self, value: object, label: str, *, allow_empty: bool = False) -> str | None:
        if value is None and allow_empty:
            return None
        if not isinstance(value, str):
            self._fail(f"{label} must be text")
        if not value.strip() and not allow_empty:
            self._fail(f"{label} must not be empty")
        return value.strip() or None

    def _decimal(self, value: object, label: str, *, allow_empty: bool = False) -> Decimal | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            if allow_empty:
                return None
            self._fail(f"{label} must be numeric")
        if isinstance(value, bool):
            self._fail(f"{label} must be numeric")
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            self._fail(f"{label} is not a valid Decimal ({type(exc).__name__})")
        if not parsed.is_finite():
            self._fail(f"{label} must be finite")
        return parsed

    def _amount(self, value: object, label: str, *, allow_empty: bool = False) -> Decimal | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            if allow_empty:
                return None
            self._fail(f"{label} must be an amount")
        if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
            return self._decimal(value, label)
        if not isinstance(value, str):
            self._fail(f"{label} must be an amount")
        match = _AMOUNT_PATTERN.fullmatch(value.strip())
        if match is None:
            self._fail(f"{label} has an unsupported amount format")
        return Decimal(match.group(1)) * _AMOUNT_UNITS.get(match.group(2) or "元", Decimal("1"))

    def _percent(self, value: object, label: str, *, allow_empty: bool = False) -> Decimal | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            if allow_empty:
                return None
            self._fail(f"{label} must be a percentage")
        if not isinstance(value, str):
            self._fail(f"{label} must be a percentage string")
        match = _PERCENT_PATTERN.fullmatch(value.strip())
        if match is None:
            self._fail(f"{label} must end with %")
        return Decimal(match.group(1))

    def _int(self, value: object, label: str, *, allow_empty: bool = False) -> int | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            if allow_empty:
                return None
            self._fail(f"{label} must be an integer")
        if isinstance(value, bool):
            self._fail(f"{label} must be an integer")
        try:
            parsed = int(str(value).strip())
        except ValueError:
            self._fail(f"{label} must be an integer")
        return parsed


def _instrument_from_source(value: object, label: str) -> InstrumentId:
    if not isinstance(value, str) or not re.fullmatch(r"(?i)(sh|sz|bj)[0-9]{6}", value):
        raise ValueError(f"{label} must be an explicit sh/sz/bj six-digit source code")
    prefix = value[:2].lower()
    return InstrumentId(
        code=value[2:],
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=_SOURCE_PREFIX_TO_EXCHANGE[prefix],
    )


def _source_code(instrument: InstrumentId) -> str:
    try:
        prefix = _EXCHANGE_TO_SOURCE_PREFIX[instrument.exchange]
    except KeyError as exc:
        raise ValueError("instrument exchange cannot be represented by Aigupiao source code") from exc
    return f"{prefix}{instrument.code}"


def _series_time(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
        raise ValueError(f"{label} must be HH:MM")
    return value


class AigupiaoMarketSentimentProvider(_AigupiaoBase):
    endpoint = AIGUPIAO_MARKET_SENTIMENT_ENDPOINT
    provider_id = "aigupiao.market_sentiment"

    def __init__(self, transport: _AigupiaoTransport | None = None, *, clock: Any | None = None) -> None:
        super().__init__(
            transport,
            clock=clock,
            source=Source(providerId=self.provider_id, sourceUrl=self.endpoint),
            headers=build_headers(
                accept="text/javascript, application/javascript, */*; q=0.01",
                referer="https://www.10jqka.com.cn/",
            ),
        )

    def fetch_snapshot(self, request: MarketSentimentRequest | None = None) -> _ProviderMarketSentiment:
        request = request or MarketSentimentRequest()
        if not isinstance(request, MarketSentimentRequest):
            self._fail("request must be a MarketSentimentRequest")
        document, request_url = self._request(self.endpoint, {"ts": int(time.time() * 1000)})
        self._require_keys(document, {"code", "data", "message", "status"}, "sentiment root")
        if str(document.get("code")) != "0" or document.get("status") != "success":
            self._fail(f"sentiment source indicates failure: {document.get('message')!r}")
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("sentiment data must be an object")
        self._require_keys(data, _SENTIMENT_FIELDS, "sentiment data")
        try:
            temperature = data["market_temperature"]
            if not isinstance(temperature, str):
                raise ValueError("market_temperature must be text")
            match = _TEMPERATURE_PATTERN.fullmatch(temperature.strip())
            if match is None:
                raise ValueError("market_temperature must use a numeric °C source display")
            return _ProviderMarketSentiment(
                market_temperature=Decimal(match.group(1)),
                total_turnover_cny=self._amount(data["total_turnover"], "total_turnover", allow_empty=True),
                forecasted_turnover_cny=self._amount(data["forecasted_turnover"], "forecasted_turnover", allow_empty=True),
                turnover_change_amount_cny=self._amount(data["turnover_growing_data"], "turnover_growing_data", allow_empty=True),
                blast_break_percent_points=self._percent(data["blast_break_pct"], "blast_break_pct", allow_empty=True),
                previous_limit_up_break_change_percent_points=self._percent(data["limit_up_break_chg_pct"], "limit_up_break_chg_pct", allow_empty=True),
                stop_trading_count=self._int(data["stop_trad_stock_num"], "stop_trad_stock_num"),
                one_limit_up_count=self._int(data["one_limit_up_stock_num"], "one_limit_up_stock_num"),
                two_limit_up_count=self._int(data["two_limit_up_stock_num"], "two_limit_up_stock_num"),
                three_limit_up_count=self._int(data["three_limit_up_stock_num"], "three_limit_up_stock_num"),
                high_limit_up_count=self._int(data["high_limit_up_stock_num"], "high_limit_up_stock_num"),
                two_limit_up_promotion_percent_points=self._percent(data["two_limit_up_stock_rate"], "two_limit_up_stock_rate", allow_empty=True),
                three_limit_up_promotion_percent_points=self._percent(data["three_limit_up_stock_rate"], "three_limit_up_stock_rate", allow_empty=True),
                high_limit_up_promotion_percent_points=self._percent(data["high_limit_up_stock_rate"], "high_limit_up_stock_rate", allow_empty=True),
                previous_limit_up_theme_change_percent_points=self._percent(data["raising_limit_theme_chg_pct"], "raising_limit_theme_chg_pct", allow_empty=True),
                previous_consecutive_limit_up_theme_change_percent_points=self._percent(data["repetition_limit_theme_chg_pct"], "repetition_limit_theme_chg_pct", allow_empty=True),
                raw_payload=document,
                source_url=request_url,
                captured_at=self._captured(),
            )
        except ValueError as exc:
            self._fail(str(exc))


class AigupiaoSeriesLimitUpProvider(_AigupiaoBase):
    endpoint = AIGUPIAO_SERIES_LIMIT_UP_ENDPOINT
    provider_id = "aigupiao.series_limit_up"

    def __init__(self, transport: _AigupiaoTransport | None = None, *, clock: Any | None = None) -> None:
        super().__init__(
            transport,
            clock=clock,
            source=Source(providerId=self.provider_id, sourceUrl=self.endpoint),
            headers=build_headers(accept="application/json, text/plain, */*", referer="https://www.aigupiao.com/"),
        )

    def fetch_snapshot(self, request: MarketConsecutiveLimitUpRequest | None = None) -> tuple[_ProviderConsecutiveLimitUpRow, ...]:
        request = request or MarketConsecutiveLimitUpRequest()
        if not isinstance(request, MarketConsecutiveLimitUpRequest):
            self._fail("request must be a MarketConsecutiveLimitUpRequest")
        params = {
            "number": 500,
            "md": "91f02684e9b752ddcec405e72b0b203d",
            "st_stock": "n",
            "type": "series_limit_up",
            "page": 1,
            "source": "pc",
            "u_id": "1124938",
            "new_stock": "n",
            "sort_mode": "desc",
            "sort_type": "limit_up_state",
        }
        document, request_url = self._request(self.endpoint, params)
        self._require_keys(document, {"status", "code", "message", "data"}, "series root")
        if document.get("status") != "success" or str(document.get("code")) != "0":
            self._fail(f"series source indicates failure: {document.get('message')!r}")
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("series data must be an object")
        self._require_keys(data, {"total", "list"}, "series data")
        rows = data.get("list")
        if not isinstance(rows, list):
            self._fail("series list must be an array")
        total = self._int(data.get("total"), "series total")
        if total != len(rows):
            self._fail("series total does not match list length")
        captured_at = self._captured()
        parsed: list[_ProviderConsecutiveLimitUpRow] = []
        try:
            for index, raw in enumerate(rows):
                if not isinstance(raw, dict):
                    self._fail(f"series row {index} must be an object")
                self._require_keys(raw, _SERIES_FIELDS, f"series row {index}")
                instrument = _instrument_from_source(raw["code"], f"series row {index}.code")
                day = str(raw["day"])
                trade_date = datetime.strptime(day, "%Y-%m-%d").date()
                series_flag = raw["series_limit_up"]
                if series_flag not in ("yes", "no"):
                    self._fail(f"series row {index}.series_limit_up must be yes/no")
                last_price = self._decimal(raw["last_price"], f"series row {index}.last_price")
                total_shares = self._int(raw["zgb"], f"series row {index}.zgb")
                market_cap_100m = self._decimal(raw["whole"], f"series row {index}.whole")
                if last_price < 0 or total_shares < 0 or market_cap_100m < 0:
                    self._fail(f"series row {index} contains a negative price/share/market-cap value")
                expected_market_cap = last_price * total_shares
                if abs(market_cap_100m * Decimal("100000000") - expected_market_cap) > max(Decimal("10000000"), expected_market_cap * Decimal("0.01")):
                    self._fail(f"series row {index}.whole is inconsistent with last_price * zgb")
                parsed.append(_ProviderConsecutiveLimitUpRow(
                    instrument_id=instrument,
                    name=self._text(raw["name"], f"series row {index}.name"),
                    trade_date=trade_date,
                    last_price=last_price,
                    change=self._decimal(raw["chg"], f"series row {index}.chg"),
                    change_percent_points=self._decimal(raw["change_pct"], f"series row {index}.change_pct"),
                    turnover_percent_points=self._decimal(raw["turnover_rate"], f"series row {index}.turnover_rate"),
                    amount_cny=self._amount(raw["amount"], f"series row {index}.amount"),
                    limit_up_time=_series_time(raw["limit_up_time"], f"series row {index}.limit_up_time"),
                    source_series_limit_up=self._int(raw["x_series_limit_up"], f"series row {index}.x_series_limit_up"),
                    is_consecutive_limit_up=series_flag == "yes",
                    state=self._text(raw["state"], f"series row {index}.state"),
                    previous_consecutive_limit_up_count=self._int(raw["last_day_continuous_up_times"], f"series row {index}.last_day_continuous_up_times"),
                    theme_id=self._int(raw["theme_id"], f"series row {index}.theme_id", allow_empty=True),
                    theme_name=self._text(raw["theme_name"], f"series row {index}.theme_name", allow_empty=True),
                    float_shares=self._int(raw["ltg"], f"series row {index}.ltg"),
                    total_shares=total_shares,
                    market_cap_100m_cny=market_cap_100m,
                    raw_payload=raw,
                    source_record_id=f"{day}:{raw['code']}",
                    source_url=request_url,
                    captured_at=captured_at,
                ))
        except (ValueError, TypeError) as exc:
            self._fail(str(exc))
        return tuple(parsed)


class AigupiaoDragonTigerProvider(_AigupiaoBase):
    provider_id = "aigupiao.dragon_tiger"

    def __init__(self, transport: _AigupiaoTransport | None = None, *, clock: Any | None = None) -> None:
        super().__init__(
            transport,
            clock=clock,
            source=Source(providerId=self.provider_id, sourceUrl=AIGUPIAO_DRAGON_TIGER_LIST_ENDPOINT),
            headers=build_headers(accept="application/json, text/plain, */*", referer="https://www.aigupiao.com/"),
        )

    def fetch_list(self, request: MarketDragonTigerListRequest) -> tuple[_ProviderDragonTigerListRow, ...]:
        if not isinstance(request, MarketDragonTigerListRequest):
            self._fail("request must be a MarketDragonTigerListRequest")
        params = {
            "number": 500,
            "md": "91f02684e9b752ddcec405e72b0b203d",
            "source": "pc",
            "user_id": 1124938,
            "day": request.trade_date.isoformat(),
        }
        document, request_url = self._request(AIGUPIAO_DRAGON_TIGER_LIST_ENDPOINT, params)
        self._require_keys(document, {"code", "count", "data", "message", "stock_list_count"}, "Dragon Tiger list root")
        if str(document.get("code")) != "1":
            self._fail(f"Dragon Tiger list source indicates failure: {document.get('message')!r}")
        rows = document.get("data")
        if not isinstance(rows, list):
            self._fail("Dragon Tiger list data must be an array")
        count = self._int(document.get("count"), "Dragon Tiger list count")
        if count < 0:
            self._fail("Dragon Tiger list count must not be negative")
        captured_at = self._captured()
        parsed: list[_ProviderDragonTigerListRow] = []
        try:
            for index, raw in enumerate(rows):
                if not isinstance(raw, dict):
                    self._fail(f"Dragon Tiger list row {index} must be an object")
                self._require_keys(raw, _DRAGON_LIST_FIELDS, f"Dragon Tiger list row {index}")
                parsed.append(_ProviderDragonTigerListRow(
                    instrument_id=_instrument_from_source(raw["code"], f"Dragon Tiger list row {index}.code"),
                    name=self._text(raw["name"], f"Dragon Tiger list row {index}.name"),
                    trade_date=request.trade_date,
                    trade_id=self._text(raw["trade_id"], f"Dragon Tiger list row {index}.trade_id"),
                    close_price=self._decimal(raw["close_price"], f"Dragon Tiger list row {index}.close_price"),
                    change_percent_points=self._decimal(raw["change_rate"], f"Dragon Tiger list row {index}.change_rate"),
                    amount_cny=self._amount(raw["accum_amount"], f"Dragon Tiger list row {index}.accum_amount"),
                    total_buy_cny=self._amount(raw["total_buy"], f"Dragon Tiger list row {index}.total_buy"),
                    total_net_cny=self._amount(raw["total_net"], f"Dragon Tiger list row {index}.total_net"),
                    explanation=self._text(raw["explanation"], f"Dragon Tiger list row {index}.explanation"),
                    three_day_flag=self._text(raw["three_day_flag"], f"Dragon Tiger list row {index}.three_day_flag", allow_empty=True),
                    theme_id=self._int(raw["theme_id"], f"Dragon Tiger list row {index}.theme_id", allow_empty=True),
                    theme_name=self._text(raw["theme_name"], f"Dragon Tiger list row {index}.theme_name", allow_empty=True),
                    raw_payload=raw,
                    source_url=request_url,
                    captured_at=captured_at,
                ))
        except (ValueError, TypeError) as exc:
            self._fail(str(exc))
        return tuple(parsed)

    def fetch_detail(self, request: MarketDragonTigerDetailRequest) -> _ProviderDragonTigerDetail:
        if not isinstance(request, MarketDragonTigerDetailRequest):
            self._fail("request must be a MarketDragonTigerDetailRequest")
        source_code = _source_code(request.instrument_id)
        params = {
            "day": request.trade_date.isoformat(),
            "code": source_code,
            "trade_id": request.trade_id,
        }
        document, request_url = self._request(AIGUPIAO_DRAGON_TIGER_DETAIL_ENDPOINT, params)
        self._require_keys(document, {"code", "data", "message"}, "Dragon Tiger detail root")
        if str(document.get("code")) != "1":
            self._fail(f"Dragon Tiger detail source indicates failure: {document.get('message')!r}")
        raw = document.get("data")
        if not isinstance(raw, dict):
            self._fail("Dragon Tiger detail data must be an object")
        self._require_keys(raw, _DRAGON_DETAIL_FIELDS, "Dragon Tiger detail data")
        try:
            response_code = _instrument_from_source(raw["code"], "Dragon Tiger detail code")
            if response_code != request.instrument_id:
                self._fail("Dragon Tiger detail code does not match requested instrument")
            buy_rows = self._parse_seats(raw["buy_fives"], "buy_fives")
            sell_rows = self._parse_seats(raw["sell_fives"], "sell_fives")
            captured_at = self._captured()
            return _ProviderDragonTigerDetail(
                instrument_id=response_code,
                name=self._text(raw["name"], "Dragon Tiger detail name"),
                trade_date=request.trade_date,
                trade_id=request.trade_id,
                close_price=self._decimal(raw["close_price"], "Dragon Tiger detail close_price"),
                change_percent_points=self._decimal(raw["change_rate"], "Dragon Tiger detail change_rate"),
                amount_cny=self._amount(raw["accum_amount"], "Dragon Tiger detail accum_amount"),
                total_buy_cny=self._amount(raw["total_buy"], "Dragon Tiger detail total_buy"),
                total_sell_cny=self._amount(raw["total_sell"], "Dragon Tiger detail total_sell"),
                total_net_cny=self._amount(raw["total_net"], "Dragon Tiger detail total_net"),
                explanation=self._text(raw["explanation"], "Dragon Tiger detail explanation"),
                comment_kind=self._text(raw["comment_kind"], "Dragon Tiger detail comment_kind", allow_empty=True),
                comment_object_id=None if raw["comment_o_id"] is None else str(raw["comment_o_id"]),
                buy_seats=buy_rows,
                sell_seats=sell_rows,
                raw_payload=document,
                source_url=request_url,
                captured_at=captured_at,
            )
        except (ValueError, TypeError) as exc:
            self._fail(str(exc))

    def _parse_seats(self, value: object, label: str) -> tuple[_ProviderDragonTigerSeat, ...]:
        if not isinstance(value, list):
            self._fail(f"Dragon Tiger {label} must be an array")
        seats: list[_ProviderDragonTigerSeat] = []
        try:
            for index, raw in enumerate(value):
                if not isinstance(raw, dict):
                    self._fail(f"Dragon Tiger {label}[{index}] must be an object")
                self._require_keys(raw, _SEAT_FIELDS, f"Dragon Tiger {label}[{index}]")
                has_details = raw["has_details"]
                if has_details is not None and has_details not in ("yes", "no"):
                    self._fail(f"Dragon Tiger {label}[{index}].has_details must be yes/no/null")
                seats.append(_ProviderDragonTigerSeat(
                    seat_name=self._text(raw["name"], f"Dragon Tiger {label}[{index}].name"),
                    source_seat_code=None if raw["code"] is None else str(raw["code"]),
                    has_details=None if has_details is None else has_details == "yes",
                    buy_amount_cny=self._amount(raw["buy"], f"Dragon Tiger {label}[{index}].buy"),
                    sell_amount_cny=self._amount(raw["sell"], f"Dragon Tiger {label}[{index}].sell"),
                    net_amount_cny=self._amount(raw["net"], f"Dragon Tiger {label}[{index}].net"),
                    raw_payload=raw,
                ))
        except (ValueError, TypeError) as exc:
            self._fail(str(exc))
        return tuple(seats)


__all__ = [
    "AIGUPIAO_DRAGON_TIGER_DETAIL_ENDPOINT",
    "AIGUPIAO_DRAGON_TIGER_LIST_ENDPOINT",
    "AIGUPIAO_MARKET_SENTIMENT_ENDPOINT",
    "AIGUPIAO_SERIES_LIMIT_UP_ENDPOINT",
    "AigupiaoDragonTigerProvider",
    "AigupiaoMarketSentimentProvider",
    "AigupiaoSeriesLimitUpProvider",
]
