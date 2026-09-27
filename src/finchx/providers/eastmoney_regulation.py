"""Conservative EastMoney regulation/abnormal-move HTTP adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from finchx.contracts import Source
from finchx.datasets.market_regulation import (
    AbnormalCountsRequest,
    AbnormalRecordsRequest,
    RegulationWatchlistRequest,
    SeverePredictionsRequest,
)
from finchx.providers.errors import ProviderError
from finchx.providers.http import (
    DEFAULT_HEADERS,
    call_with_transient_retries,
    http_status_failure_reason,
)

EASTMONEY_REGULATION_PROVIDER_ID = "eastmoney.regulation"
EASTMONEY_WATCHLIST_URL = "https://mobappconfig.securities.eastmoney.com/emcfg/stock_monitor.json"
EASTMONEY_DATACENTER_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
EASTMONEY_PREDICTION_LIST_URL = "https://dycalchis.eastmoney.com/price-anomaly/list"
EASTMONEY_ABNORMAL_COUNTS_URL = "https://dycalchis.eastmoney.com/price-anomaly/count"
_TIMEOUT_SECONDS = 6.0
_MAX_POOL_PAGES = 10
_MAX_PAGE_SIZE = 200
_REFERER = "https://vipmoney.eastmoney.com/collect/watchstock/unusual.html"
_WATCHLIST_REFERER = "https://vipmoney.eastmoney.com/collect/min_data/point_stock_monitor/index.html"
_MISSING = {"", "-", "--"}
_DATA_CENTER_COLUMNS = {
    "abnormal_events": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,UNUSUAL_TYPE,START_DATE,END_DATE,INFO_CODE,NOTICE_DATE,UNUSUAL_REASON,UNUSUAL_REASON_TYPE,MRAKET_TYPE",
    "severe_events": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,UNUSUAL_TYPE,START_DATE,END_DATE,INFO_CODE,NOTICE_DATE,UNUSUAL_REASON,UNUSUAL_REASON_TYPE,MRAKET_TYPE,PREDICT_START_DATE,PREDICT_END_DATE,IS_HIS",
    "prediction_history": "SECUCODE,IS_SYSDATE,SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,MARKET_CODE,CHANGE_RATE,MAX_DAYS,DEVUATION_VALUE,CHANGE_RATE_TARGET,IS_HAPPEN,UNUSUAL_TYPE,IS_POSITIVE,RANK_TYPE",
}


class _HttpResponse:
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body


class _Transport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _HttpResponse: ...


class _UrllibTransport:
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _HttpResponse:
        request_url = f"{url}?{urlencode(params)}" if params else url
        request = Request(request_url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return _HttpResponse(int(response.status), body.decode(charset))
        except HTTPError as exc:
            return _HttpResponse(int(exc.code), "")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            raise _TransportFailure(type(exc).__name__) from exc


class _TransportFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class _ProviderRegulationResponse:
    rows: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, Any]
    warnings: tuple[str, ...] = ()


class EastmoneyRegulationProvider:
    """Fetch the four frozen EastMoney regulation capabilities."""

    provider_id = EASTMONEY_REGULATION_PROVIDER_ID

    def __init__(
        self,
        transport: _Transport | None = None,
        *,
        timeout_seconds: float = _TIMEOUT_SECONDS,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._transport = transport or _UrllibTransport()
        self._timeout_seconds = float(timeout_seconds)
        self._source = Source(providerId=self.provider_id)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_watchlist(self, request: RegulationWatchlistRequest) -> _ProviderRegulationResponse:
        self._check_request(request, RegulationWatchlistRequest)
        response, payload, request_url, params = self._get_json(EASTMONEY_WATCHLIST_URL, {}, referer=_WATCHLIST_REFERER)
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            self._fail("stock_monitor.json must be a JSON array of objects")
        for index, row in enumerate(payload):
            _require_fields(row, ("STKCODE", "STKNAME", "MARKET"), f"watchlist row {index}")
        return _ProviderRegulationResponse(
            rows=tuple(payload),
            metadata={
                "provider": "eastmoney",
                "logical_capability": "market.regulation_watchlist",
                "source_url": request_url,
                "request_parameters": params,
                "page_complete": True,
                "collection_complete": True,
                "upstream_page_rows": len(payload),
                "returned_count": len(payload),
                "unclassified_count": len(payload),
            },
        )

    def fetch_abnormal_records(self, request: AbnormalRecordsRequest) -> _ProviderRegulationResponse:
        self._check_request(request, AbnormalRecordsRequest)
        report_name, filter_text, sort_columns, sort_types = _record_query(request)
        params = {
            "reportName": report_name,
            "columns": _DATA_CENTER_COLUMNS[request.dataset],
            "quoteColumns": "",
            "filter": filter_text,
            "pageNumber": request.page,
            "pageSize": request.page_size,
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": "SECURITIES",
            "client": "APP",
        }
        response, payload, request_url, normalized_params = self._get_json(
            EASTMONEY_DATACENTER_URL, params, referer=_REFERER
        )
        if not isinstance(payload, dict):
            self._fail("DataCenter response must be an object")
        if payload.get("success") is not True or _source_integer(payload.get("code"), "DataCenter.code") != 0:
            self._fail(f"DataCenter business failure: code={payload.get('code')!r}")
        result = payload.get("result")
        if not isinstance(result, dict):
            self._fail("DataCenter successful response omitted the result object")
        rows = result.get("data")
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            self._fail("DataCenter result.data must be an array of objects")
        required_by_dataset = {
            "abnormal_events": ("SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "UNUSUAL_TYPE"),
            "severe_events": ("SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "UNUSUAL_TYPE", "IS_HIS"),
            "prediction_history": ("SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "TRADE_DATE", "IS_HAPPEN", "IS_SYSDATE", "IS_POSITIVE"),
        }
        for index, row in enumerate(rows):
            _require_fields(row, required_by_dataset[request.dataset], f"{request.dataset} row {index}")
        total_count = _source_integer(result.get("count"), "DataCenter.result.count")
        pages = _source_integer(result.get("pages"), "DataCenter.result.pages")
        if total_count < 0 or pages < 0:
            self._fail("DataCenter count/pages must not be negative")
        if total_count > 0 and pages < 1:
            self._fail("DataCenter count is positive but pages is empty")
        metadata = {
            "provider": "eastmoney",
            "logical_capability": "market.abnormal_records",
            "records_dataset": request.dataset,
            "report_name": report_name,
            "source_url": request_url,
            "request_parameters": normalized_params,
            "upstream_page": request.page,
            "page_size": request.page_size,
            "upstream_pages": pages,
            "upstream_total_count": total_count,
            "upstream_page_rows": len(rows),
            "returned_count": len(rows),
            "page_complete": True,
            "collection_complete": request.page == 1 and pages <= 1,
            "has_more": request.page < pages,
            "upstream_version": _json_value(payload.get("version")),
            "upstream_message": _json_value(payload.get("message")),
            "upstream_code": _json_value(payload.get("code")),
        }
        return _ProviderRegulationResponse(rows=tuple(rows), metadata=metadata)

    def fetch_severe_predictions(self, request: SeverePredictionsRequest) -> _ProviderRegulationResponse:
        self._check_request(request, SeverePredictionsRequest)
        params: dict[str, str | int] = {
            **_DY_COMMON_PARAMS,
            "pageSize": _MAX_PAGE_SIZE,
            "pageNo": 1,
            "riseOnly": int(request.rise_only),
            "showBJS": int(request.include_bse),
        }
        return self._fetch_dy_pool(
            request=request,
            endpoint=EASTMONEY_PREDICTION_LIST_URL,
            params=params,
            capability="market.severe_predictions",
            referer=_REFERER,
            rows_required=("c", "n", "s", "e", "o"),
        )

    def fetch_abnormal_counts(self, request: AbnormalCountsRequest) -> _ProviderRegulationResponse:
        self._check_request(request, AbnormalCountsRequest)
        sort_key = {"count": 0, "price": 1, "max_deviation": 2}[request.sort_by]
        sort_direction = {"desc": 0, "asc": 1}[request.order]
        params: dict[str, str | int] = {
            **_DY_COMMON_PARAMS,
            "pageSize": _MAX_PAGE_SIZE,
            "pageNo": 1,
            "sortKey": sort_key,
            "sortDir": sort_direction,
        }
        return self._fetch_dy_pool(
            request=request,
            endpoint=EASTMONEY_ABNORMAL_COUNTS_URL,
            params=params,
            capability="market.abnormal_counts",
            referer=_REFERER,
            rows_required=("c", "n", "s", "t"),
        )

    def _fetch_dy_pool(
        self,
        *,
        request: SeverePredictionsRequest | AbnormalCountsRequest,
        endpoint: str,
        params: Mapping[str, str | int],
        capability: str,
        referer: str,
        rows_required: tuple[str, ...],
    ) -> _ProviderRegulationResponse:
        rows: list[Mapping[str, Any]] = []
        warnings: list[str] = []
        page_hashes: set[str] = set()
        raw_page_values: list[dict[str, Any]] = []
        first_pages: int | None = None
        observed_max_pages = 0
        source_date: str | None = None
        source_open: Any = None
        source_count: Any = None
        pages_requested = 0
        page_complete = True
        collection_complete = True
        pagination_consistent = True
        for page_no in range(1, _MAX_POOL_PAGES + 1):
            page_params = dict(params)
            page_params["pageNo"] = page_no
            response, payload, request_url, normalized_params = self._get_json(endpoint, page_params, referer=referer)
            if not isinstance(payload, dict):
                self._fail(f"{capability} response must be an object")
            if _source_integer(payload.get("result"), f"{capability}.result") != 0:
                self._fail(f"{capability} business failure: {payload.get('msg')!r}")
            page_rows = payload.get("data")
            if not isinstance(page_rows, list) or not all(isinstance(row, dict) for row in page_rows):
                self._fail(f"{capability}.data must be an array of objects")
            for index, row in enumerate(page_rows):
                _require_fields(row, rows_required, f"{capability} page {page_no} row {index}")
            pages = _source_integer(payload.get("pages"), f"{capability}.pages")
            if pages < 0:
                self._fail(f"{capability}.pages must not be negative")
            observed_max_pages = max(observed_max_pages, pages)
            raw_date = payload.get("date")
            if raw_date is not None:
                parsed_date = _source_date(raw_date, f"{capability}.date")
                if source_date is None:
                    source_date = parsed_date.isoformat()
                elif source_date != parsed_date.isoformat():
                    pagination_consistent = False
                    warnings.append("Source date changed between pages; collection may not be a consistent snapshot.")
            if first_pages is None:
                first_pages = pages
                source_open = _json_value(payload.get("open"))
                source_count = _json_value(payload.get("count"))
            elif pages != first_pages:
                pagination_consistent = False
                warnings.append("Provider page count changed during collection; collection may be incomplete.")
            # Empty pages can occur between non-empty pages on a changing
            # source. They are not evidence that pagination is complete, and
            # repeated empty contents must not trigger duplicate-page stop.
            if page_rows:
                digest = _page_digest(page_rows)
                if digest in page_hashes:
                    collection_complete = False
                    warnings.append(f"Repeated provider page {page_no} detected; collection stopped early.")
                    break
                page_hashes.add(digest)
            rows.extend(page_rows)
            pages_requested += 1
            raw_page_values.append({
                "page": page_no,
                "source_url": request_url,
                "request_parameters": normalized_params,
                "row_count": len(page_rows),
            })
            if page_no >= pages:
                break
        else:
            page_complete = True
            collection_complete = False
            warnings.append(f"Provider pagination stopped at the {_MAX_POOL_PAGES}-page safety limit.")
        if first_pages is None:
            self._fail(f"{capability} returned no first page")
        if first_pages > _MAX_POOL_PAGES:
            collection_complete = False
        metadata = {
            "provider": "eastmoney",
            "logical_capability": capability,
            "source_url": endpoint,
            "request_parameters": dict(params),
            "source_date": source_date,
            "provider_open_raw": source_open,
            "provider_count_raw": source_count,
            "upstream_pages": first_pages,
            "upstream_pages_observed_max": observed_max_pages,
            "upstream_pages_requested": pages_requested,
            "upstream_page_rows": len(rows),
            "returned_count": len(rows),
            "page_complete": page_complete,
            "collection_complete": (
                collection_complete
                and pagination_consistent
                and (
                    (first_pages == 0 and not rows)
                    or pages_requested == first_pages
                )
            ),
            "has_more": pages_requested < observed_max_pages,
            "pagination_consistent": pagination_consistent,
            "page_references": raw_page_values,
        }
        return _ProviderRegulationResponse(rows=tuple(rows), metadata=metadata, warnings=tuple(warnings))

    def _get_json(
        self,
        endpoint: str,
        params: Mapping[str, str | int],
        *,
        referer: str,
    ) -> tuple[_HttpResponse, Any, str, dict[str, Any]]:
        request_url = f"{endpoint}?{urlencode(params)}" if params else endpoint
        headers = dict(DEFAULT_HEADERS)
        headers["Referer"] = referer
        response = call_with_transient_retries(
            lambda: self._request_response(endpoint, params=params, headers=headers)
        )
        if not response.body.strip():
            self._fail("EastMoney returned an empty response body")
        try:
            payload = json.loads(
                response.body,
                parse_float=Decimal,
                parse_constant=self._reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"EastMoney returned invalid JSON ({type(exc).__name__})")
        normalized_params = {key: _json_value(value) for key, value in params.items()}
        return response, payload, request_url, normalized_params

    def _request_response(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
    ) -> _HttpResponse:
        """Issue one HTTP attempt and raise retry-classifiable ProviderErrors."""

        try:
            response = self._transport.get(
                endpoint,
                params=params,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
            )
        except _TransportFailure as exc:
            self._fail(f"EastMoney transport failure: {exc}")
        except Exception as exc:
            self._fail(f"EastMoney transport failure: {type(exc).__name__}")
        failure = http_status_failure_reason(response.status_code)
        if failure is not None:
            self._fail(f"EastMoney returned {failure}")
        return response

    def _check_request(self, request: object, expected: type[Any]) -> None:
        if not isinstance(request, expected):
            self._fail(f"request must be a {expected.__name__}")

    @staticmethod
    def _reject_json_constant(value: str) -> NoReturn:
        raise ValueError(f"non-finite JSON constant {value}")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self._source, reason)


_DY_COMMON_PARAMS: dict[str, str | int] = {
    "team": "h5",
    "product": "EastMoney",
    "client": "WAP",
    "version": "9001",
    "name": "WAP",
    "user": "123",
}


def _record_query(request: AbnormalRecordsRequest) -> tuple[str, str, str, str]:
    if request.dataset == "prediction_history":
        report_name = "RPT_WATCH_UNUSUAL_FLUCTUATE"
        sort_columns, sort_types = "TRADE_DATE", "-1"
        filters: list[str] = []
        if request.triggered == "yes":
            filters.append('(IS_HAPPEN="1")')
        elif request.triggered == "no":
            filters.append('(IS_HAPPEN="0")')
        if request.rise_only is True:
            filters.append('(IS_POSITIVE="1")')
        return report_name, "".join(filters), sort_columns, sort_types
    report_name = "RPT_APP_UNUSUALBASIC"
    sort_columns, sort_types = "NOTICE_DATE,END_DATE", "-1,-1"
    filters = [f'(UNUSUAL_TYPE="{"001" if request.dataset == "abnormal_events" else "002"}")']
    if request.dataset == "severe_events":
        effective_status = request.status or "current"
        if effective_status != "all":
            filters.append(f'(IS_HIS="{"1" if effective_status == "current" else "0"}")')
    return report_name, "".join(filters), sort_columns, sort_types


def _require_fields(raw: Mapping[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in raw]
    if missing:
        raise ProviderError(
            Source(providerId=EASTMONEY_REGULATION_PROVIDER_ID),
            f"{label} omitted required fields: {', '.join(missing)}",
        )


def _source_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ProviderError(Source(providerId=EASTMONEY_REGULATION_PROVIDER_ID), f"{label} must be an integer")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ProviderError(Source(providerId=EASTMONEY_REGULATION_PROVIDER_ID), f"{label} is not an integer") from exc
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        raise ProviderError(Source(providerId=EASTMONEY_REGULATION_PROVIDER_ID), f"{label} must be a finite integer")
    return int(parsed)


def _source_date(value: Any, label: str) -> date:
    if isinstance(value, bool):
        raise ProviderError(Source(providerId=EASTMONEY_REGULATION_PROVIDER_ID), f"{label} must be YYYYMMDD")
    text = str(value)
    if not re.fullmatch(r"[0-9]{8}", text):
        raise ProviderError(Source(providerId=EASTMONEY_REGULATION_PROVIDER_ID), f"{label} must be YYYYMMDD")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise ProviderError(Source(providerId=EASTMONEY_REGULATION_PROVIDER_ID), f"{label} is not a valid date") from exc


def _page_digest(rows: list[Mapping[str, Any]]) -> str:
    encoded = json.dumps(_json_value(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "EASTMONEY_ABNORMAL_COUNTS_URL",
    "EASTMONEY_DATACENTER_URL",
    "EASTMONEY_PREDICTION_LIST_URL",
    "EASTMONEY_REGULATION_PROVIDER_ID",
    "EASTMONEY_WATCHLIST_URL",
    "EastmoneyRegulationProvider",
]
