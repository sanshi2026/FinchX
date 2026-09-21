"""Source adapters for market-level 7x24 news."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import json
import re
import time
from typing import Any, NoReturn
from urllib.parse import parse_qs, urlencode, urlparse

from finchx.contracts import Source
from finchx.datasets.news import MarketNewsSearchRequest, _ProviderNewsRow
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.eastmoney_documents import (
    _ParsedNewsHtml,
    _ProviderDocumentPage,
    _parse_html_news,
)
from finchx.providers.eastmoney_market import (
    _EastmoneyTransport,
    _EastmoneyTransportFailure,
    _UrllibEastmoneyTransport,
)
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, build_headers, http_status_failure_reason


EASTMONEY_FAST_NEWS_ENDPOINT = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
AIGUPIAO_EXPRESS_ENDPOINT = "https://apis.aigupiao.com/Express/express_list/"
BAIDU_FINSCOPE_ENDPOINT = "https://finance.pae.baidu.com/selfselect/expressnews"
_TZ = timezone(timedelta(hours=8))
_JSONP = re.compile(r"^\s*[A-Za-z_$][A-Za-z0-9_$.]*\s*\((.*)\)\s*;?\s*$", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value.strip()


def _int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{label} must be an integer")
    try:
        return int(str(value))
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc


def _source_time(value: object, label: str) -> datetime:
    try:
        return datetime.strptime(_text(value, label), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_TZ)
    except ValueError as exc:
        raise ValueError(f"{label} is not a source datetime") from exc


def _unix_time(value: object, label: str) -> datetime:
    timestamp = _int(value, label)
    if timestamp < 0:
        raise ValueError(f"{label} cannot be negative")
    return datetime.fromtimestamp(timestamp, tz=_TZ)


def _plain(value: str) -> str:
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = _TAG.sub("", value).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(" ".join(line.split()) for line in value.split("\n") if line.strip()).strip()


def _instrument(code: object, exchange: object) -> InstrumentId | None:
    if not isinstance(code, str):
        return None
    code = code.strip()
    if code[:2].lower() in ("sh", "sz"):
        exchange = "1" if code[:2].lower() == "sh" else "0"
        code = code[2:]
    if not re.fullmatch(r"[0-9]{6}", code):
        return None
    if exchange in ("1", 1, "SH", "sh"):
        target, prefixes = Exchange.SSE, ("60", "68")
    elif exchange in ("0", 0, "SZ", "sz"):
        target, prefixes = Exchange.SZSE, ("00", "30")
    else:
        return None
    if not code.startswith(prefixes):
        return None
    return InstrumentId(code=code, market=Market.CN_A, kind=InstrumentKind.EQUITY, exchange=target)


def _related_eastmoney(value: object) -> tuple[InstrumentId, ...]:
    if not isinstance(value, list):
        raise ValueError("EastMoney stockList must be an array")
    result = []
    for item in value:
        if isinstance(item, str) and "." in item:
            market, code = item.split(".", 1)
            candidate = _instrument(code, market)
            if candidate is not None and candidate not in result:
                result.append(candidate)
    return tuple(result)


def _related_aigupiao(value: object) -> tuple[InstrumentId, ...]:
    if not isinstance(value, list):
        raise ValueError("Aigupiao stock_infos must be an array")
    result = []
    for item in value:
        if isinstance(item, Mapping):
            candidate = _instrument(item.get("code"), None)
            if candidate is not None and candidate not in result:
                result.append(candidate)
    return tuple(result)


def _related_baidu(value: object) -> tuple[InstrumentId, ...]:
    if not isinstance(value, list):
        raise ValueError("Baidu entity must be an array")
    result = []
    for item in value:
        if isinstance(item, Mapping) and item.get("market") == "ab":
            candidate = _instrument(item.get("code"), item.get("exchange"))
            if candidate is not None and candidate not in result:
                result.append(candidate)
    return tuple(result)


class _Base:
    provider_id: str
    endpoint: str

    def __init__(self, transport: _EastmoneyTransport | None, *, clock: Any | None, headers: Mapping[str, str]):
        self._transport = transport or _UrllibEastmoneyTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._headers = dict(headers)
        self._source = Source(providerId=self.provider_id, sourceUrl=self.endpoint)

    @property
    def source(self) -> Source:
        return self._source

    def _json(self, endpoint: str, params: Mapping[str, str | int]) -> tuple[dict[str, Any], str]:
        request_url = f"{endpoint}?{urlencode(params)}"
        try:
            response = self._transport.get(
                endpoint, params=params, headers=self._headers, timeout_seconds=DEFAULT_TIMEOUT_SECONDS
            )
        except _EastmoneyTransportFailure as exc:
            self._fail(f"transport failure: {exc}")
        except Exception as exc:
            self._fail(f"transport failure: {type(exc).__name__}")
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            self._fail(reason)
        if not response.text.strip():
            self._fail("empty response body")
        candidate = response.text.strip()
        matched = _JSONP.fullmatch(candidate)
        if matched:
            candidate = matched.group(1)
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"malformed JSON/JSONP ({type(exc).__name__})")
        if not isinstance(value, dict):
            self._fail("response root must be an object")
        return value, request_url

    def _captured(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return value

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)

    def _detail_row(self, document_id: str, title: str, url: str, content: str, *, derived=False):
        return _ProviderNewsRow(
            instrument_id=None, document_id=document_id, title=title, published_at=None, url=url,
            original_url=None, source_name=None, content_text=content, source_url=self.endpoint,
            captured_at=self._captured(), public_document_id=f"{self.provider_id}:market_news:{document_id}",
            title_derived=derived,
        )


class EastmoneyMarketNewsProvider(_Base):
    provider_id = "eastmoney.market_news"
    endpoint = EASTMONEY_FAST_NEWS_ENDPOINT

    def __init__(self, transport=None, *, clock=None):
        super().__init__(transport, clock=clock, headers=build_headers(referer="https://finance.eastmoney.com/"))

    def fetch_raw_news_page(self, request: MarketNewsSearchRequest) -> _ProviderDocumentPage:
        if not isinstance(request, MarketNewsSearchRequest):
            self._fail("request must be a MarketNewsSearchRequest")
        trace = str(int(time.time() * 1000))
        params = {
            "client": "web", "biz": "web_724", "fastColumn": 102,
            "sortEnd": request.cursor or "", "pageSize": request.page_size,
            "req_trace": trace, "_": str(int(trace) + 1),
        }
        document, request_url = self._json(self.endpoint, params)
        if set(document) != {"req_trace", "code", "message", "data"}:
            self._fail("EastMoney fast-news root fields drifted")
        if document.get("code") not in (1, "1") or not isinstance(document.get("message"), str):
            self._fail(f"EastMoney fast-news indicates failure: {document.get('message')!r}")
        data = document.get("data")
        if data is None:
            return _ProviderDocumentPage((), request.page, request.page_size, 0, request_url)
        if not isinstance(data, Mapping) or set(data) != {"sortEnd", "index", "total", "size", "fastNewsList"}:
            self._fail("EastMoney fast-news data fields drifted")
        size = _int(data.get("size"), "fastNews.size")
        total = _int(data.get("total"), "fastNews.total")
        if size != request.page_size or not 1 <= size <= 100:
            self._fail("EastMoney fast-news size was clamped or unsafe")
        raw_rows = data.get("fastNewsList")
        if not isinstance(raw_rows, list):
            self._fail("EastMoney fast-news list must be an array")
        rows = []
        for raw in raw_rows:
            if not isinstance(raw, Mapping) or not {"summary", "code", "title", "showTime", "stockList"} <= set(raw):
                self._fail("EastMoney fast-news row fields drifted")
            try:
                code = _text(raw.get("code"), "fastNews.code")
                if not re.fullmatch(r"[0-9]{12,24}", code):
                    raise ValueError("fastNews.code is invalid")
                title = _text(raw.get("title"), "fastNews.title")
                summary = _text(raw.get("summary"), "fastNews.summary")
                published = _source_time(raw.get("showTime"), "fastNews.showTime")
                related = _related_eastmoney(raw.get("stockList"))
            except ValueError as exc:
                self._fail(str(exc))
            rows.append(_ProviderNewsRow(
                instrument_id=None, document_id=code, title=title, published_at=published,
                url=f"https://finance.eastmoney.com/a/{code}.html", original_url=None,
                source_name=None, content_text=None, source_url=request_url, captured_at=self._captured(),
                summary=summary, related_instruments=related,
                public_document_id=f"{self.provider_id}:market_news:{code}",
            ))
        cursor = _text(data.get("sortEnd"), "fastNews.sortEnd")
        return _ProviderDocumentPage(tuple(rows), request.page, size, total, request_url, cursor)

    def fetch_content(self, document_id: str, *, document_url: str | None = None) -> _ProviderNewsRow:
        if not isinstance(document_id, str) or not re.fullmatch(r"[0-9]{12,24}", document_id):
            self._fail("EastMoney fast-news document ID is invalid")
        url = document_url or f"https://finance.eastmoney.com/a/{document_id}.html"
        try:
            response = self._transport.get(
                url, params={}, headers=build_headers(referer="https://finance.eastmoney.com/"),
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS
            )
        except _EastmoneyTransportFailure as exc:
            self._fail(f"detail transport failure: {exc}")
        except Exception as exc:
            self._fail(f"detail transport failure: {type(exc).__name__}")
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            self._fail(f"detail returned {reason}")
        try:
            parsed: _ParsedNewsHtml = _parse_html_news(response.text, document_id=document_id)
        except ValueError as exc:
            self._fail(str(exc))
        return _ProviderNewsRow(
            instrument_id=None, document_id=document_id, title=parsed.title, published_at=parsed.published_at,
            url=url, original_url=None, source_name=parsed.source_name, content_text=parsed.content_text,
            source_url=url, captured_at=self._captured(),
            public_document_id=f"{self.provider_id}:market_news:{document_id}",
        )


class AigupiaoMarketNewsProvider(_Base):
    provider_id = "aigupiao.market_news"
    endpoint = AIGUPIAO_EXPRESS_ENDPOINT

    def __init__(self, transport=None, *, clock=None):
        super().__init__(
            transport, clock=clock,
            headers=build_headers(referer="https://www.aigupiao.com/", accept="application/json, text/plain, */*"),
        )

    def fetch_raw_news_page(self, request: MarketNewsSearchRequest) -> _ProviderDocumentPage:
        if not isinstance(request, MarketNewsSearchRequest):
            self._fail("request must be a MarketNewsSearchRequest")
        params = {
            "before": request.cursor or 0, "source": "pc", "web_data": "yes",
            "number": request.page_size, "u_id": 1124938, "division": "", "express_show_type": 1,
        }
        document, request_url = self._json(self.endpoint, params)
        if set(document) != {"rslt", "data", "last_time", "date_time"} or document.get("rslt") != "succ":
            self._fail("Aigupiao response envelope drifted or failed")
        buckets = document.get("data")
        if not isinstance(buckets, Mapping):
            self._fail("Aigupiao data must be an object")
        rows = []
        for bucket in buckets.values():
            if not isinstance(bucket, Mapping) or not {"title", "data"} <= set(bucket):
                self._fail("Aigupiao bucket fields drifted")
            raw_rows = bucket.get("data")
            if not isinstance(raw_rows, list):
                self._fail("Aigupiao bucket data must be an array")
            for raw in raw_rows:
                required = {"id", "content", "rec_time", "web_content", "url", "important", "stock_infos"}
                if not isinstance(raw, Mapping) or not required <= set(raw):
                    self._fail("Aigupiao row fields drifted")
                try:
                    code = str(_int(raw.get("id"), "Aigupiao.id"))
                    content = _plain(_text(raw.get("web_content") or raw.get("content"), "Aigupiao.content"))
                    match = re.search(r"【([^】]+)】", content)
                    title = match.group(1).strip() if match else content[:80].strip()
                    url = _text(raw.get("url"), "Aigupiao.url")
                    published = _unix_time(raw.get("rec_time"), "Aigupiao.rec_time")
                    related = _related_aigupiao(raw.get("stock_infos"))
                except ValueError as exc:
                    self._fail(str(exc))
                rows.append(_ProviderNewsRow(
                    instrument_id=None, document_id=code, title=title, published_at=published, url=url,
                    original_url=None, source_name=None, content_text=content, source_url=request_url,
                    captured_at=self._captured(), related_instruments=related,
                    public_document_id=f"{self.provider_id}:market_news:{code}", title_derived=match is not None,
                ))
        cursor = document.get("last_time")
        next_cursor = str(cursor) if cursor not in (None, "", 0, "0") else None
        return _ProviderDocumentPage(tuple(rows), request.page, request.page_size, None, request_url, next_cursor)

    def fetch_content(self, document_id: str, *, document_url: str | None = None) -> _ProviderNewsRow:
        if not document_url:
            self._fail("Aigupiao full document requires the Ref source URL")
        try:
            response = self._transport.get(
                document_url, params={}, headers=self._headers, timeout_seconds=DEFAULT_TIMEOUT_SECONDS
            )
        except _EastmoneyTransportFailure as exc:
            self._fail(f"detail transport failure: {exc}")
        except Exception as exc:
            self._fail(f"detail transport failure: {type(exc).__name__}")
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            self._fail(f"detail returned {reason}")
        content = _plain(response.text)
        if not content:
            self._fail("detail returned empty content")
        match = re.search(r"【([^】]+)】", content)
        return self._detail_row(
            document_id, match.group(1).strip() if match else content[:80].strip(),
            document_url, content, derived=match is not None,
        )


class BaiduFinscopeMarketNewsProvider(_Base):
    provider_id = "baidu.finscope.market_news"
    endpoint = BAIDU_FINSCOPE_ENDPOINT

    def __init__(self, transport=None, *, clock=None):
        super().__init__(
            transport, clock=clock,
            headers=build_headers(
                referer="https://gushitong.baidu.com/",
                accept="application/json, text/plain, */*",
                extra={"Origin": "https://gushitong.baidu.com"},
            ),
        )

    def fetch_raw_news_page(self, request: MarketNewsSearchRequest) -> _ProviderDocumentPage:
        if not isinstance(request, MarketNewsSearchRequest):
            self._fail("request must be a MarketNewsSearchRequest")
        params = {
            "rn": request.page_size, "pn": request.page - 1, "tag": "",
            "filterByUserStocks": 0, "finClientType": "pc",
        }
        document, request_url = self._json(self.endpoint, params)
        if set(document) != {"QueryID", "ResultCode", "Result"} or str(document.get("ResultCode")) != "0":
            self._fail("Baidu Finscope response envelope drifted or failed")
        result = document.get("Result")
        if not isinstance(result, Mapping) or not isinstance(result.get("content"), Mapping):
            self._fail("Baidu Finscope Result fields drifted")
        raw_rows = result["content"].get("list")
        if not isinstance(raw_rows, list):
            self._fail("Baidu Finscope list must be an array")
        rows = []
        for raw in raw_rows:
            required = {"loc", "title", "content", "publish_time", "entity"}
            if not isinstance(raw, Mapping) or not required <= set(raw):
                self._fail("Baidu Finscope row fields drifted")
            content_obj = raw.get("content")
            if not isinstance(content_obj, Mapping) or not isinstance(content_obj.get("items"), list):
                self._fail("Baidu Finscope content.items must be an array")
            text_items = [
                item.get("data") for item in content_obj["items"]
                if isinstance(item, Mapping) and item.get("type") == "text" and isinstance(item.get("data"), str)
            ]
            content = _plain("\n\n".join(text_items))
            if not content:
                self._fail("Baidu Finscope content.items contained no text")
            third_url = raw.get("third_url") if isinstance(raw.get("third_url"), str) else ""
            source_id = parse_qs(urlparse(third_url).query).get("d", [""])[0] if third_url else ""
            document_id = source_id or _text(raw.get("loc"), "Baidu.loc")
            rows.append(_ProviderNewsRow(
                instrument_id=None, document_id=document_id, title=_text(raw.get("title"), "Baidu.title"),
                published_at=_unix_time(raw.get("publish_time"), "Baidu.publish_time"),
                url=third_url or self.endpoint, original_url=None,
                source_name=raw.get("provider") if isinstance(raw.get("provider"), str) else None,
                content_text=content, source_url=request_url, captured_at=self._captured(),
                related_instruments=_related_baidu(raw.get("entity")),
                public_document_id=f"{self.provider_id}:market_news:{document_id}",
            ))
        return _ProviderDocumentPage(tuple(rows), request.page, request.page_size, None, request_url)

    def fetch_content(self, document_id: str, *, document_url: str | None = None) -> _ProviderNewsRow:
        url = document_url or self.endpoint
        try:
            response = self._transport.get(
                url, params={}, headers=self._headers, timeout_seconds=DEFAULT_TIMEOUT_SECONDS
            )
        except _EastmoneyTransportFailure as exc:
            self._fail(f"detail transport failure: {exc}")
        except Exception as exc:
            self._fail(f"detail transport failure: {type(exc).__name__}")
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            self._fail(f"detail returned {reason}")
        content = _plain(response.text)
        if not content:
            self._fail("detail returned empty content")
        return self._detail_row(document_id, content[:80], url, content)


__all__ = [
    "AIGUPIAO_EXPRESS_ENDPOINT",
    "BAIDU_FINSCOPE_ENDPOINT",
    "EASTMONEY_FAST_NEWS_ENDPOINT",
    "AigupiaoMarketNewsProvider",
    "BaiduFinscopeMarketNewsProvider",
    "EastmoneyMarketNewsProvider",
]
