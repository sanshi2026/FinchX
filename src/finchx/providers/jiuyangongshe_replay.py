"""Authenticated Playwright provider for 韭研公社 daily replay snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
import json
import re
import time as monotonic_time
from typing import Any, NoReturn, Protocol

from finchx.contracts import Source
from finchx.datasets.market_daily_replay import (
    MARKET_DAILY_REPLAY_DATASET,
    MarketDailyReplayRequest,
    _ProviderDailyReplay,
    _ProviderReplayStock,
    _ProviderReplayTheme,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.errors import ProviderError


JIYANGONGSHE_PAGE_URL = "https://www.jiuyangongshe.com/action/{date}"
JIYANGONGSHE_API_ORIGIN = "https://web-api.jiuyangongshe.com"
JIYANGONGSHE_COUNT_ENDPOINT = f"{JIYANGONGSHE_API_ORIGIN}/jystock-app/api/v1/action/count-pc"
JIYANGONGSHE_FIELD_ENDPOINT = f"{JIYANGONGSHE_API_ORIGIN}/jystock-app/api/v1/action/field"

_ROOT_FIELDS = {"msg", "errCode", "data", "serverTime"}
_REQUIRED_ROOT_FIELDS = {"msg", "errCode", "data"}
_DIAGRAM_FIELDS = {"action_field_id", "count", "date", "name", "reason"}
_THEME_FIELDS = {
    "action_field_id", "count", "create_time", "date", "delete_time", "is_delete",
    "list", "name", "reason", "sort_no", "status", "update_time",
}
_STOCK_FIELDS = {"article", "code", "name"}
_ARTICLE_FIELDS = {
    "action_info", "article_id", "comment_count", "create_time", "forward_count",
    "is_like", "is_step", "like_count", "step_count", "title", "user", "user_id",
}
_ACTION_INFO_FIELDS = {
    "action_field_id", "action_info_id", "article_id", "create_time", "day",
    "delete_time", "edition", "expound", "is_crawl", "is_delete", "is_recommend",
    "num", "price", "reason", "shares_range", "sort_no", "stock_id", "time",
    "update_time",
}
_SOURCE_PREFIX_TO_EXCHANGE = {"sh": Exchange.SSE, "sz": Exchange.SZSE, "bj": Exchange.BSE}
_TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$")
_CHROMIUM_INSTALL_HINT = "Chromium runtime is unavailable; install it with `python -m playwright install chromium`"


class _MissingPlaywrightError(RuntimeError):
    """Private transport signal converted to the public optional-dependency error."""


class _ChromiumRuntimeError(RuntimeError):
    """Private transport signal whose message is safe to expose to callers."""


@dataclass(frozen=True)
class _CapturedJiyangongshe:
    count_document: dict[str, Any]
    field_document: dict[str, Any]
    count_request_date: date
    field_request_date: date
    field_url: str = JIYANGONGSHE_FIELD_ENDPOINT


class _JiyangongsheTransport(Protocol):
    def fetch(self, requested_date: date, *, timeout_seconds: float) -> _CapturedJiyangongshe: ...


class _PlaywrightJiyangongsheTransport:
    """Fresh, non-persistent browser context used only for one fetch."""

    def __init__(self, session: str, *, page_url_template: str = JIYANGONGSHE_PAGE_URL) -> None:
        self._session = session
        self._page_url_template = page_url_template

    def fetch(self, requested_date: date, *, timeout_seconds: float) -> _CapturedJiyangongshe:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise _MissingPlaywrightError(
                "Playwright is not installed; install `finchx[jygs]`"
            ) from exc

        responses: dict[str, tuple[int, dict[str, Any], date]] = {}
        request_dates: dict[str, date] = {}
        deadline = monotonic_time.monotonic() + timeout_seconds

        with sync_playwright() as playwright:
            browser: Any | None = None
            chromium_failed = False
            try:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context()
            except Exception:
                chromium_failed = True
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass
            if chromium_failed:
                raise _ChromiumRuntimeError(_CHROMIUM_INSTALL_HINT)
            try:
                context.add_cookies([
                    {"name": "SESSION", "value": self._session, "domain": "www.jiuyangongshe.com", "path": "/"},
                    {"name": "SESSION", "value": self._session, "domain": "web-api.jiuyangongshe.com", "path": "/"},
                ])
                page = context.new_page()

                def capture(response: Any) -> None:
                    endpoint = response.url.split("?", 1)[0]
                    if endpoint not in {JIYANGONGSHE_COUNT_ENDPOINT, JIYANGONGSHE_FIELD_ENDPOINT}:
                        return
                    post_data = response.request.post_data
                    if post_data:
                        try:
                            post_payload = json.loads(post_data)
                            request_dates[endpoint] = date.fromisoformat(str(post_payload["date"]))
                        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                            pass
                    try:
                        payload = response.json()
                    except Exception:
                        payload = {"_malformed": True}
                    if isinstance(payload, dict):
                        responses[endpoint] = (response.status, payload, request_dates.get(endpoint, requested_date))

                page.on("response", capture)
                try:
                    page.goto(
                        self._page_url_template.format(date=requested_date.isoformat()),
                        wait_until="domcontentloaded",
                        timeout=max(1, int(timeout_seconds * 1000)),
                    )
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError("page navigation timeout") from exc

                initial_deadline = min(
                    deadline, monotonic_time.monotonic() + min(timeout_seconds, 3.0)
                )
                self._wait_for_responses(page, responses, initial_deadline)
                if JIYANGONGSHE_FIELD_ENDPOINT not in responses:
                    remaining_ms = max(200, int((deadline - monotonic_time.monotonic()) * 1000))
                    try:
                        page.get_by_text("全部异动解析", exact=True).first.click(timeout=remaining_ms)
                    except Exception:
                        pass
                    self._wait_for_responses(page, responses, deadline)
                if JIYANGONGSHE_COUNT_ENDPOINT not in responses:
                    raise RuntimeError("count-pc response timeout")
                if JIYANGONGSHE_FIELD_ENDPOINT not in responses:
                    raise RuntimeError("action/field response timeout")
                count_status, count_document, count_request_date = responses[JIYANGONGSHE_COUNT_ENDPOINT]
                field_status, field_document, field_request_date = responses[JIYANGONGSHE_FIELD_ENDPOINT]
                # Keep HTTP status in the response document for the provider's source-aware error mapping.
                count_document = {"_http_status": count_status, **count_document}
                field_document = {"_http_status": field_status, **field_document}
                return _CapturedJiyangongshe(
                    count_document=count_document,
                    field_document=field_document,
                    count_request_date=count_request_date,
                    field_request_date=field_request_date,
                )
            finally:
                context.close()
                browser.close()

    @staticmethod
    def _wait_for_responses(page: Any, responses: dict[str, Any], deadline: float) -> None:
        while monotonic_time.monotonic() < deadline:
            if JIYANGONGSHE_COUNT_ENDPOINT in responses and JIYANGONGSHE_FIELD_ENDPOINT in responses:
                return
            page.wait_for_timeout(min(100, max(1, int((deadline - monotonic_time.monotonic()) * 1000))))


class JiyangongsheReplayProvider:
    """Fetch and source-validate one authenticated 韭研公社 daily replay."""

    provider_id = "jiuyangongshe.daily_replay"

    def __init__(
        self,
        *,
        transport: _JiyangongsheTransport | None = None,
        clock: Any | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds
        self._source = Source(providerId=self.provider_id, sourceUrl=JIYANGONGSHE_FIELD_ENDPOINT)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_replay(
        self,
        request: MarketDailyReplayRequest,
        *,
        session: str,
    ) -> _ProviderDailyReplay:
        if not isinstance(request, MarketDailyReplayRequest):
            self._fail("request must be a MarketDailyReplayRequest")
        if not isinstance(session, str) or not session.strip():
            self._fail("SESSION must be a non-empty string")
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        transport = self._transport
        if transport is None:
            transport = _PlaywrightJiyangongsheTransport(session.strip())
        transport_failure_reason: str | None = None
        try:
            capture = transport.fetch(request.requested_date, timeout_seconds=self._timeout_seconds)
        except _MissingPlaywrightError as exc:
            from finchx.collectors.errors import MissingOptionalDependency

            raise MissingOptionalDependency(
                MARKET_DAILY_REPLAY_DATASET.name,
                self.provider_id,
                "playwright",
            ) from exc
        except _ChromiumRuntimeError as exc:
            transport_failure_reason = str(exc)
        except Exception as exc:
            transport_failure_reason = f"transport failure ({type(exc).__name__})"
        if transport_failure_reason is not None:
            self._fail_without_context(transport_failure_reason)

        count = self._parse_response(capture.count_document, "count-pc")
        field = self._parse_response(capture.field_document, "action/field")
        if capture.count_request_date > request.requested_date:
            self._fail("count-pc request date is later than requestedDate")
        if capture.field_request_date != self._date_from_count(count):
            self._fail("action/field request date did not match count-pc effective date")
        trade_date = self._date_from_count(count)
        themes, diagram = self._parse_field_data(field, trade_date)
        return _ProviderDailyReplay(
            requested_date=request.requested_date,
            trade_date=trade_date,
            themes=themes,
            diagram_metadata=diagram,
            raw_payload={
                "count": self._sanitize_raw(count),
                "field": self._sanitize_raw(field),
            },
            source_url=capture.field_url,
            captured_at=captured_at,
        )

    def fetch_snapshot(
        self,
        request: MarketDailyReplayRequest,
        *,
        session: str,
    ) -> _ProviderDailyReplay:
        return self.fetch_replay(request, session=session)

    def _parse_response(self, document: Mapping[str, Any], context: str) -> dict[str, Any]:
        if not isinstance(document, dict):
            self._fail(f"{context} response root must be an object")
        http_status = document.pop("_http_status", 200)
        if not isinstance(http_status, int) or isinstance(http_status, bool):
            self._fail(f"{context} HTTP status is invalid")
        if http_status < 200 or http_status >= 300:
            self._fail(f"{context} HTTP failure ({http_status})")
        if document.get("_malformed"):
            self._fail(f"{context} malformed JSON")
        self._require_keys(document, _REQUIRED_ROOT_FIELDS, context, allowed=_ROOT_FIELDS)
        code = str(document["errCode"])
        if code == "1":
            self._fail(f"{context} login invalid (errCode=1)")
        if code == "110":
            self._fail(f"{context} token/signature invalid (errCode=110)")
        if code != "0":
            self._fail(f"{context} source error (errCode={code})")
        return dict(document)

    @classmethod
    def _sanitize_raw(cls, value: Any, key: str | None = None) -> Any:
        if key == "serverTime" or key in {"user", "user_id"}:
            return None
        if isinstance(value, dict):
            return {
                field: sanitized
                for field, raw in value.items()
                if (sanitized := cls._sanitize_raw(raw, field)) is not None
            }
        if isinstance(value, list):
            return [cls._sanitize_raw(item) for item in value]
        return value

    def _date_from_count(self, document: Mapping[str, Any]) -> date:
        value = document.get("data")
        if not isinstance(value, dict):
            self._fail("count-pc data must be an object")
        self._require_keys(value, {"all", "date", "recommend"}, "count-pc data")
        return self._date(value["date"], "count-pc data.date")

    def _parse_field_data(
        self, document: Mapping[str, Any], trade_date: date
    ) -> tuple[tuple[_ProviderReplayTheme, ...], dict[str, Any] | None]:
        data = document.get("data")
        if not isinstance(data, list):
            self._fail("action/field data must be a list")
        if not data:
            return (), None
        diagram: dict[str, Any] | None = None
        start = 0
        first = data[0]
        if isinstance(first, dict) and first.get("name") == "简图":
            self._require_keys(first, _DIAGRAM_FIELDS, "action/field diagram")
            if self._date(first["date"], "action/field diagram.date") != trade_date:
                self._fail("action/field diagram date does not match tradeDate")
            diagram = dict(first)
            start = 1

        themes: list[_ProviderReplayTheme] = []
        for index, raw_theme in enumerate(data[start:], start=start):
            if not isinstance(raw_theme, dict):
                self._fail(f"action/field data[{index}] must be an object")
            self._require_keys(raw_theme, _THEME_FIELDS, f"action/field theme[{index}]")
            theme_date = self._date(raw_theme["date"], f"action/field theme[{index}].date")
            if theme_date != trade_date:
                self._fail(f"action/field theme[{index}] date does not match tradeDate")
            raw_list = raw_theme["list"]
            if not isinstance(raw_list, list):
                self._fail(f"action/field theme[{index}].list must be a list")
            stocks = tuple(self._parse_stock(raw_stock, index, stock_index) for stock_index, raw_stock in enumerate(raw_list))
            themes.append(
                _ProviderReplayTheme(
                    theme_name=self._text(raw_theme["name"], f"theme[{index}].name"),
                    reason=self._text(raw_theme["reason"], f"theme[{index}].reason", allow_empty=True),
                    stock_count=self._int(raw_theme["count"], f"theme[{index}].count"),
                    source_theme_id=self._text(raw_theme["action_field_id"], f"theme[{index}].action_field_id", allow_empty=True),
                    stocks=stocks,
                    raw_payload=dict(raw_theme),
                )
            )
        return tuple(themes), diagram

    def _parse_stock(self, raw_stock: Any, theme_index: int, stock_index: int) -> _ProviderReplayStock:
        context = f"action/field theme[{theme_index}].list[{stock_index}]"
        if not isinstance(raw_stock, dict):
            self._fail(f"{context} must be an object")
        self._require_keys(raw_stock, _STOCK_FIELDS, context)
        code = raw_stock["code"]
        if not isinstance(code, str) or re.fullmatch(r"(?i)(sh|sz|bj)[0-9]{6}", code) is None:
            self._fail(f"{context}.code must be an explicit sh/sz/bj six-digit code")
        prefix = code[:2].lower()
        instrument = InstrumentId(
            code=code[2:], market=Market.CN_A, kind=InstrumentKind.EQUITY,
            exchange=_SOURCE_PREFIX_TO_EXCHANGE[prefix],
        )
        article = raw_stock["article"]
        if not isinstance(article, dict):
            self._fail(f"{context}.article must be an object")
        self._require_keys(article, _ARTICLE_FIELDS, f"{context}.article")
        action_info = article["action_info"]
        if not isinstance(action_info, dict):
            self._fail(f"{context}.article.action_info must be an object")
        self._require_keys(action_info, _ACTION_INFO_FIELDS, f"{context}.article.action_info")
        price_raw = self._decimal(
            action_info["price"], f"{context}.article.action_info.price", allow_empty=True
        )
        shares_range_raw = self._decimal(
            action_info["shares_range"],
            f"{context}.article.action_info.shares_range",
            allow_empty=True,
        )
        return _ProviderReplayStock(
            instrument_id=instrument,
            name=self._text(raw_stock["name"], f"{context}.name"),
            limit_up_time=self._time(action_info["time"], f"{context}.article.action_info.time", allow_empty=True),
            streak_text=self._text(action_info["num"], f"{context}.article.action_info.num", allow_empty=True),
            price_cny=None if price_raw is None else price_raw / Decimal("100"),
            change_ratio=None if shares_range_raw is None else shares_range_raw / Decimal("10000"),
            day=self._int(action_info["day"], f"{context}.article.action_info.day", allow_empty=True),
            edition=self._int(action_info["edition"], f"{context}.article.action_info.edition", allow_empty=True),
            expound=self._text(action_info["expound"], f"{context}.article.action_info.expound", allow_empty=True),
            raw_payload=dict(raw_stock),
        )

    def _require_keys(
        self,
        value: Mapping[str, Any],
        expected: set[str],
        context: str,
        *,
        allowed: set[str] | None = None,
    ) -> None:
        keys = set(value)
        missing = expected - keys
        unexpected = keys - (allowed or expected)
        if missing:
            self._fail(f"{context} omitted required fields: {', '.join(sorted(missing))}")
        if unexpected:
            self._fail(f"{context} schema drift added fields: {', '.join(sorted(unexpected))}")

    def _date(self, value: object, label: str) -> date:
        if not isinstance(value, str):
            self._fail(f"{label} must be an ISO date")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            self._fail(f"{label} must be an ISO date")
            raise AssertionError from exc

    def _time(self, value: object, label: str, *, allow_empty: bool) -> time | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            if allow_empty:
                return None
            self._fail(f"{label} must be a time")
        if not isinstance(value, str) or _TIME_PATTERN.fullmatch(value.strip()) is None:
            self._fail(f"{label} must be HH:MM:SS")
        return time.fromisoformat(value.strip())

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
            parsed = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            self._fail(f"{label} is not a valid Decimal ({type(exc).__name__})")
        if not parsed.is_finite():
            self._fail(f"{label} must be finite")
        return parsed

    def _int(self, value: object, label: str, *, allow_empty: bool = False) -> int | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            if allow_empty:
                return None
            self._fail(f"{label} must be an integer")
        if isinstance(value, bool):
            self._fail(f"{label} must be an integer")
        if isinstance(value, float) and not value.is_integer():
            self._fail(f"{label} must be an integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            self._fail(f"{label} must be an integer")
        return parsed

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self._source, reason)

    def _fail_without_context(self, reason: str) -> NoReturn:
        error = ProviderError(self._source, reason)
        error.__context__ = None
        raise error from None


__all__ = [
    "JIYANGONGSHE_COUNT_ENDPOINT",
    "JIYANGONGSHE_FIELD_ENDPOINT",
    "JIYANGONGSHE_PAGE_URL",
    "JiyangongsheReplayProvider",
]
