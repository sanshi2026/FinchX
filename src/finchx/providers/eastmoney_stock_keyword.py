"""EastMoney getHotStockRankList Provider."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from finchx.contracts import Source
from finchx.datasets.market_stock_keyword import (
    MarketStockKeywordRequest,
    _ProviderStockKeywordEntry,
    _ProviderStockKeywordSnapshot,
    _validate_stock_keyword_instrument,
)
from finchx.entities import Exchange
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, http_status_failure_reason


EASTMONEY_STOCK_KEYWORD_ENDPOINT = (
    "https://emappdata.eastmoney.com/stockrank/getHotStockRankList"
)
_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
_HEADERS = {"Content-Type": "application/json"}
_SOURCE_TIMEZONE = ZoneInfo("Asia/Shanghai")
_SOURCE_CODE_BY_EXCHANGE = {
    Exchange.SSE: "SH",
    Exchange.SZSE: "SZ",
    Exchange.BSE: "BJ",
}
_ROOT_FIELDS = {"globalId", "message", "status", "code", "data", "stack"}
_ROW_FIELDS = {"calcTime", "srcSecurityCode", "conceptName", "conceptId", "hitCount", "flag"}
_CALC_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_CONCEPT_ID = re.compile(r"^BK[0-9]{4}$")


class _StockKeywordHttpResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class _StockKeywordTransport(Protocol):
    """Replaceable POST seam used by the Provider and offline fixtures."""

    def post(
        self,
        url: str,
        *,
        json_payload: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _StockKeywordHttpResponse: ...


class _StockKeywordTransportFailure(RuntimeError):
    pass


class _UrllibStockKeywordTransport:
    def post(
        self,
        url: str,
        *,
        json_payload: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _StockKeywordHttpResponse:
        request = Request(
            url,
            data=json.dumps(dict(json_payload), ensure_ascii=False).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return _StockKeywordHttpResponse(int(response.status), body.decode(charset))
        except HTTPError as exc:
            return _StockKeywordHttpResponse(int(exc.code), "")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            raise _StockKeywordTransportFailure(type(exc).__name__) from exc


class EastMoneyStockKeywordProvider:
    """Fetch EastMoney's source-ranked hot keywords for one equity."""

    def __init__(
        self,
        transport: _StockKeywordTransport | None = None,
        *,
        clock=None,
    ) -> None:
        self._transport = transport or _UrllibStockKeywordTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(
            providerId="eastmoney.stockrank",
            sourceUrl=EASTMONEY_STOCK_KEYWORD_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_stock_keyword(
        self,
        request: MarketStockKeywordRequest,
    ) -> _ProviderStockKeywordSnapshot:
        if not isinstance(request, MarketStockKeywordRequest):
            self._fail("request must be a MarketStockKeywordRequest")
        try:
            _validate_stock_keyword_instrument(request.instrument_id)
        except ValueError as exc:
            self._fail(f"unsupported market or exchange request: {exc}")

        instrument = request.instrument_id
        source_code = f"{_SOURCE_CODE_BY_EXCHANGE[instrument.exchange]}{instrument.code}"
        payload = {"srcSecurityCode": source_code}
        try:
            response = self._transport.post(
                EASTMONEY_STOCK_KEYWORD_ENDPOINT,
                json_payload=payload,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _StockKeywordTransportFailure as exc:
            self._fail(f"EastMoney stockrank transport failure: {exc}")
        except Exception as exc:
            self._fail(f"EastMoney stockrank transport failure: {type(exc).__name__}")

        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"EastMoney stockrank returned {status_reason}")
        if not response.text.strip():
            self._fail("schema drift: EastMoney stockrank returned an empty response body")
        document = self._decode(response.text)
        self._validate_root(document)
        data = document["data"]
        entries: list[_ProviderStockKeywordEntry] = []
        for index, raw in enumerate(data):
            entries.append(self._parse_row(raw, index, source_code))

        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        suffix = "empty" if not entries else str(entries[0].calculated_at.isoformat())
        return _ProviderStockKeywordSnapshot(
            instrument_id=instrument,
            entries=tuple(entries),
            source_record_id=f"{source_code}:stockrank:{suffix}",
            source_url=EASTMONEY_STOCK_KEYWORD_ENDPOINT,
            captured_at=captured_at,
        )

    def _decode(self, text: str) -> dict[str, Any]:
        try:
            document = json.loads(text, parse_constant=self._reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"schema drift: EastMoney stockrank returned malformed JSON ({type(exc).__name__})")
        if not isinstance(document, dict):
            self._fail("schema drift: EastMoney stockrank response root must be an object")
        return document

    def _validate_root(self, document: Mapping[str, Any]) -> None:
        unexpected = set(document) - _ROOT_FIELDS
        missing = {"code", "status", "message", "data"} - set(document)
        if unexpected:
            self._fail(f"schema drift: EastMoney stockrank root has unexpected fields: {sorted(unexpected)}")
        if missing:
            self._fail(f"schema drift: EastMoney stockrank root omitted fields: {sorted(missing)}")
        if isinstance(document.get("code"), bool) or document.get("code") not in (0, "0"):
            self._fail(
                f"EastMoney stockrank source error code={document.get('code')!r} "
                f"message={document.get('message')!r}"
            )
        if isinstance(document.get("status"), bool) or document.get("status") not in (0, "0"):
            self._fail(
                f"EastMoney stockrank source error status={document.get('status')!r} "
                f"message={document.get('message')!r}"
            )
        if not isinstance(document.get("message"), str):
            self._fail("schema drift: EastMoney stockrank message must be text")
        if not isinstance(document.get("data"), list):
            self._fail("schema drift: EastMoney stockrank data must be an array")

    def _parse_row(
        self,
        raw: Any,
        index: int,
        expected_source_code: str,
    ) -> _ProviderStockKeywordEntry:
        context = f"data[{index}]"
        if not isinstance(raw, dict):
            self._fail(f"schema drift: EastMoney stockrank {context} must be an object")
        unexpected = set(raw) - _ROW_FIELDS
        required = _ROW_FIELDS - {"flag"}
        missing = required - set(raw)
        if unexpected:
            self._fail(f"schema drift: EastMoney stockrank {context} has unexpected fields: {sorted(unexpected)}")
        if missing:
            self._fail(f"schema drift: EastMoney stockrank {context} omitted fields: {sorted(missing)}")
        source_code = raw["srcSecurityCode"]
        if not isinstance(source_code, str) or source_code != expected_source_code:
            self._fail(
                f"EastMoney stockrank identity mismatch: expected {expected_source_code!r}, got {source_code!r}"
            )
        name = raw["conceptName"]
        if not isinstance(name, str) or not name.strip():
            self._fail(f"schema drift: EastMoney stockrank {context}.conceptName must be non-empty text")
        concept_id = raw["conceptId"]
        if not isinstance(concept_id, str) or _CONCEPT_ID.fullmatch(concept_id) is None:
            self._fail(f"schema drift: EastMoney stockrank {context}.conceptId is not a BK namespace id")
        hit_count = raw["hitCount"]
        if isinstance(hit_count, bool) or not isinstance(hit_count, int) or hit_count < 0:
            self._fail(f"schema drift: EastMoney stockrank {context}.hitCount must be a non-negative integer")
        if "flag" in raw:
            flag = raw["flag"]
            if isinstance(flag, bool) or not isinstance(flag, int):
                self._fail(f"schema drift: EastMoney stockrank {context}.flag must be an integer")
        calculated_at = self._parse_calculated_at(raw["calcTime"], context)
        return _ProviderStockKeywordEntry(
            keyword_name=name.strip(),
            provider_keyword_id=concept_id,
            hit_count=hit_count,
            calculated_at=calculated_at,
        )

    def _parse_calculated_at(self, value: Any, context: str) -> datetime:
        if not isinstance(value, str):
            self._fail(f"schema drift: EastMoney stockrank {context}.calcTime must be text")
        try:
            return datetime.strptime(value, _CALC_TIME_FORMAT).replace(tzinfo=_SOURCE_TIMEZONE)
        except ValueError as exc:
            self._fail(f"schema drift: EastMoney stockrank {context}.calcTime is not YYYY-MM-DD HH:MM:SS ({exc})")

    @staticmethod
    def _reject_json_constant(value: str) -> NoReturn:
        raise ValueError(f"non-finite JSON constant {value}")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)


__all__ = [
    "EASTMONEY_STOCK_KEYWORD_ENDPOINT",
    "EastMoneyStockKeywordProvider",
]
