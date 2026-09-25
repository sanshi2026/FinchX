"""Direct iWenCai adapters for screener, SkillHub search, and report detail."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
import re
import secrets
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from finchx.contracts import (
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    SourceReference,
    StandardRecord,
)
from finchx.datasets.iwencai import (
    IwencaiReportDetailData,
    IwencaiReportDetailRequest,
    IwencaiSearchData,
    IwencaiSearchHit,
    IwencaiSearchRequest,
    IwencaiSelectionData,
    IwencaiSelectionRequest,
    IwencaiSelectionRow,
)
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, http_status_failure_reason
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


IWENCAI_SCREENER_URL = "https://www.iwencai.com/screener"
IWENCAI_SEARCH_URL = "https://openapi.iwencai.com/v1/comprehensive/search"
IWENCAI_QUERY_URL = "https://openapi.iwencai.com/v1/query2data"
IWENCAI_REPORT_DETAIL_URL = "https://ms.10jqka.com.cn/gateway/unified-wap/v1/information/notice-detail"
IWENCAI_STREAM_URL = "https://www.iwencai.com/gateway/aime/stream-query"
IWENCAI_RENDER_URL = "https://www.iwencai.com/gateway/render/encrypt/getData"
IWENCAI_SOURCE = "ths_iwencai_pc_xuangu"
IWENCAI_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
_CODE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
_CODE_WITH_EXCHANGE = re.compile(r"^(\d{6})(?:\.(SH|SZ|BJ))?$", re.IGNORECASE)
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_MISSING = frozenset({"", "-", "--", "—", "N/A", "n/a", "None", "null"})


class IwencaiResponse:
    """Small transport response used by the provider and offline tests."""

    def __init__(
        self,
        status_code: int,
        text: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = dict(headers or {})

    def iter_lines(self) -> list[str]:
        return self.text.splitlines()


class IwencaiTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        json_payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> IwencaiResponse: ...

    def post_form(
        self,
        url: str,
        *,
        form_payload: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> IwencaiResponse: ...


class _UrllibIwencaiTransport:
    def post(
        self,
        url: str,
        *,
        json_payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> IwencaiResponse:
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
                return IwencaiResponse(
                    int(response.status),
                    body.decode(charset),
                    response.headers,
                )
        except HTTPError as error:
            try:
                body = error.read().decode("utf-8", errors="replace")
            except OSError:
                body = ""
            return IwencaiResponse(int(error.code), body)
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as error:
            raise ConnectionError(type(error).__name__) from error

    def post_form(
        self,
        url: str,
        *,
        form_payload: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> IwencaiResponse:
        request = Request(
            url,
            data=urlencode(dict(form_payload), safe="*").encode("ascii"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return IwencaiResponse(
                    int(response.status),
                    body.decode(charset, errors="replace"),
                    response.headers,
                )
        except HTTPError as error:
            try:
                body = error.read().decode("utf-8", errors="replace")
            except OSError:
                body = ""
            return IwencaiResponse(int(error.code), body)
        except (URLError, TimeoutError, OSError) as error:
            raise ConnectionError(type(error).__name__) from error


class IwencaiProvider:
    """Implement the current webpage and SkillHub iWenCai protocols.

    The screener endpoint is a private webpage protocol and requires the
    caller's Cookie header. Semantic search uses the official SkillHub
    OpenAPI and additionally requires an API key. Report detail calls the
    JSON endpoint used by its linked report page and requires a Cookie header.
    """

    provider_id = "iwencai"

    def __init__(
        self,
        transport: IwencaiTransport | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        user_agent: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0 or not math.isfinite(timeout_seconds):
            raise ValueError("timeout_seconds must be positive and finite")
        self._transport = transport or _UrllibIwencaiTransport()
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._base_url = (base_url or os.environ.get("IWENCAI_BASE_URL") or "https://openapi.iwencai.com").rstrip("/")
        self._user_agent = user_agent.strip() if user_agent and user_agent.strip() else IWENCAI_DEFAULT_USER_AGENT
        self._timeout_seconds = timeout_seconds
        self._source = Source(providerId=self.provider_id, sourceUrl="https://www.iwencai.com")

    @property
    def source(self) -> Source:
        return self._source

    def fetch(self, *, request: Any) -> tuple[StandardRecord, ...]:
        if isinstance(request, IwencaiSelectionRequest):
            return self.select(request)
        if isinstance(request, IwencaiSearchRequest):
            return self.search(request)
        if isinstance(request, IwencaiReportDetailRequest):
            return self.report_detail(request)
        raise TypeError("request must be an iWenCai request model")

    def select(self, request: IwencaiSelectionRequest) -> tuple[StandardRecord, ...]:
        if not isinstance(request, IwencaiSelectionRequest):
            raise TypeError("request must be an IwencaiSelectionRequest")
        headers = self._web_headers(
            request.cookies,
            referer=IWENCAI_SCREENER_URL,
            accept="text/event-stream, application/json",
        )
        body = {
            "version": "3.4.1",
            "session_id": uuid4().hex,
            "user_id": "",
            "source": IWENCAI_SOURCE,
            "input_type": "click",
            "question": request.query,
            "add_info": {
                "merge_repeat": True,
                "async_generate_data": True,
                "show_searching": True,
                "urp": {"is_lowcode": 1, "component_version": "1.1.4"},
            },
            "entity_info": {"device_type": "pc"},
            "events": [
                {
                    "event_name": "ab_test",
                    "event_type": "front_trigger",
                    "content": {"deep_research": 1},
                }
            ],
        }
        response = self._post(IWENCAI_STREAM_URL, body, headers)
        payloads = self._stream_payloads(response)
        table = next(
            (component for payload in payloads if (component := self._table_component(payload))),
            None,
        )
        if table is None:
            raise ProviderError(self._source, "screener did not return a final table; check whether the Cookie expired")
        descriptor_extra = self._component_extra(table)
        reported_count = self._positive_int(descriptor_extra.get("row_count"), "row_count")
        if reported_count <= 0:
            raise ProviderError(self._source, "screener returned zero rows")

        raw_records: list[dict[str, Any]] = []
        page_count = min(max(1, math.ceil(reported_count / request.page_size)), request.max_pages)
        for page in range(1, page_count + 1):
            page_extra, page_records = self._render_page(
                descriptor_extra, page, request.page_size, request.cookies
            )
            raw_records.extend(page_records)
            page_reported_count = self._positive_int(page_extra.get("row_count"), "row_count") or reported_count
            if len(raw_records) >= page_reported_count or len(page_records) < request.page_size:
                break

        rows = self._normalize_selection_rows(raw_records)
        if not rows:
            raise ProviderError(self._source, "screener returned rows but no recognizable stock code/name fields")
        captured_at = datetime.now(timezone.utc)
        return tuple(
            self._selection_record(row, captured_at=captured_at)
            for row in rows
        )

    def search(self, request: IwencaiSearchRequest) -> tuple[StandardRecord, ...]:
        if not isinstance(request, IwencaiSearchRequest):
            raise TypeError("request must be an IwencaiSearchRequest")
        api_key = (request.api_key or self._api_key or os.environ.get("IWENCAI_API_KEY", "")).strip()
        if not api_key:
            raise ProviderError(self._source, "semantic search requires IWENCAI_API_KEY or an api_key argument")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
            **self._claw_headers(),
        }
        cookie = self._cookie_header(request.cookies)
        if cookie:
            headers["Cookie"] = cookie
        payload = {
            "channels": [request.channel],
            "app_id": "AIME_SKILL",
            "query": request.query,
            "size": request.size,
        }
        response = self._post(f"{self._base_url}/v1/comprehensive/search", payload, headers)
        document = self._json_document(response, "semantic search")
        if document.get("status_code", 0) not in (0, "0"):
            raise ProviderError(self._source, f"semantic search error: {document.get('status_msg', '')}")
        raw_articles = document.get("data") or []
        if not isinstance(raw_articles, list):
            raise ProviderError(self._source, "semantic search data must be an array")
        articles = self._normalize_search_hits(raw_articles)
        if request.deduplicate:
            articles = self._deduplicate(articles)
        captured_at = datetime.now(timezone.utc)
        return tuple(
            self._search_record(article, captured_at=captured_at)
            for article in articles
        )

    def report_detail(
        self,
        request: IwencaiReportDetailRequest,
    ) -> tuple[StandardRecord, ...]:
        """Fetch report content through the endpoint used by the report page."""

        if not isinstance(request, IwencaiReportDetailRequest):
            raise TypeError("request must be an IwencaiReportDetailRequest")
        report_url, duid = self._report_url_and_duid(request.url)
        headers = self._web_headers(
            request.cookies,
            referer=report_url,
            accept="application/json",
        )
        headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://ms.10jqka.com.cn",
        })
        if request.user_agent and request.user_agent.strip():
            headers["User-Agent"] = request.user_agent.strip()
        response = self._post_form(
            IWENCAI_REPORT_DETAIL_URL,
            {
                "type": "report",
                "duid": duid,
                "query_source": "guide",
                "query": "*:*",
            },
            headers,
        )
        detail = self._normalize_report_detail(response, request, report_url)
        captured_at = datetime.now(timezone.utc)
        return (self._report_detail_record(detail, captured_at=captured_at),)

    def _render_page(
        self,
        params: Mapping[str, Any],
        page: int,
        page_size: int,
        cookies: str | dict[str, str],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        request_params = {key: value for key, value in params.items() if key not in {"token", "per_page", "stock_code_list"}}
        request_params.update({"source": IWENCAI_SOURCE, "page": page, "perpage": page_size})
        response = self._post(
            IWENCAI_RENDER_URL,
            request_params,
            self._web_headers(
                cookies,
                referer=f"{IWENCAI_SCREENER_URL}/result",
                accept="application/json",
            ),
        )
        payload = self._json_document(response, "screener page")
        component = self._table_component(payload)
        if component is None:
            raise ProviderError(self._source, "screener page did not return a table component")
        return self._component_extra(component), self._component_rows(component)

    def _post(self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]) -> IwencaiResponse:
        try:
            response = self._transport.post(
                url,
                json_payload=payload,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception as error:
            raise ProviderError(self._source, f"transport failure: {type(error).__name__}: {error}") from error
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            raise ProviderError(self._source, reason)
        if not response.text.strip():
            raise ProviderError(self._source, "upstream returned an empty response body")
        return response

    def _post_form(
        self,
        url: str,
        payload: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> IwencaiResponse:
        post_form = getattr(self._transport, "post_form", None)
        if not callable(post_form):
            raise ProviderError(self._source, "transport does not support report detail form requests")
        try:
            response = post_form(
                url,
                form_payload=payload,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception as error:
            raise ProviderError(self._source, f"transport failure: {type(error).__name__}: {error}") from error
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            raise ProviderError(self._source, reason)
        if not response.text.strip():
            raise ProviderError(self._source, "report detail returned an empty response body")
        return response

    def _web_headers(
        self,
        cookies: str | dict[str, str],
        *,
        referer: str,
        accept: str,
    ) -> dict[str, str]:
        return {
            "Accept": accept,
            "Content-Type": "application/json",
            "Origin": "https://www.iwencai.com",
            "Referer": referer,
            "User-Agent": self._user_agent,
            "Cookie": self._cookie_header(cookies),
        }

    @staticmethod
    def _cookie_header(cookies: str | dict[str, str] | None) -> str:
        if cookies is None:
            return ""
        if isinstance(cookies, str):
            value = cookies.strip()
            if not value:
                raise ValueError("cookies must be non-empty")
            return value
        if not isinstance(cookies, dict) or not cookies:
            raise ValueError("cookies must be a non-empty cookie string or mapping")
        pairs = []
        for name, value in cookies.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(value, str):
                raise ValueError("cookie names and values must be strings")
            pairs.append(f"{name.strip()}={value}")
        return "; ".join(pairs)

    @staticmethod
    def _claw_headers(call_type: str = "normal") -> dict[str, str]:
        return {
            "X-Claw-Call-Type": call_type,
            "X-Claw-Skill-Id": "report-search",
            "X-Claw-Skill-Version": "2.0.0",
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": secrets.token_hex(32),
        }

    @staticmethod
    def _json_document(response: IwencaiResponse, label: str) -> dict[str, Any]:
        try:
            value = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as error:
            raise ProviderError(self._source, f"{label} returned malformed JSON") from error
        if not isinstance(value, dict):
            raise ProviderError(self._source, f"{label} response root must be an object")
        return value

    @staticmethod
    def _stream_payloads(response: IwencaiResponse) -> list[dict[str, Any]]:
        payloads = []
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            value = line[5:].strip()
            if not value or value == "[DONE]":
                continue
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                payloads.append(decoded)
        return payloads

    @staticmethod
    def _table_component(payload: Mapping[str, Any]) -> dict[str, Any] | None:
        answer = payload.get("answer", payload)
        if not isinstance(answer, dict):
            return None
        candidates: list[Mapping[str, Any]] = []
        section = payload.get("section")
        if isinstance(section, dict):
            candidates.append(section)
        candidates.append(answer)
        result_page = answer.get("result_page")
        if isinstance(result_page, dict):
            candidates.append({"result_page": result_page})
        for candidate in candidates:
            page = candidate.get("result_page")
            components = page.get("components") if isinstance(page, dict) else candidate.get("components")
            if not isinstance(components, list):
                continue
            for component in components:
                if isinstance(component, dict) and (
                    component.get("chart_type") == "jgyXuanguTable1"
                    or component.get("show_type") == "jgyXuanguTable1"
                ):
                    return component
        return None

    @staticmethod
    def _component_extra(component: Mapping[str, Any]) -> dict[str, Any]:
        data = component.get("data")
        meta = data.get("meta") if isinstance(data, dict) else None
        extra = meta.get("extra") if isinstance(meta, dict) else None
        return extra if isinstance(extra, dict) else {}

    @staticmethod
    def _component_rows(component: Mapping[str, Any]) -> list[dict[str, Any]]:
        data = component.get("data")
        records = data.get("datas") if isinstance(data, dict) else None
        return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []

    @classmethod
    def _normalize_selection_rows(cls, records: list[dict[str, Any]]) -> list[IwencaiSelectionData]:
        rows: list[IwencaiSelectionData] = []
        seen: set[str] = set()
        for source in records:
            raw = cls._clean_mapping(source)
            code = next(
                (
                    match.group(1)
                    for key, value in raw.items()
                    if key in {"code", "代码", "股票代码"} or "代码" in key
                    for match in [cls._match_code(value)]
                    if match
                ),
                None,
            )
            if code is None:
                continue
            try:
                instrument_id = cls._instrument_id(code, raw)
            except ValueError:
                continue
            if instrument_id.code in seen:
                continue
            seen.add(instrument_id.code)

            name = cls._text_field(raw, ("股票简称", "股票名称", "名称", "name"))
            price = cls._decimal_field(cls._value_field(raw, ("最新价", "收盘价", "price")))
            change_rate = cls._percentage_field(
                cls._value_field(raw, ("最新涨跌幅", "涨跌幅", "changePercent", "change_rate"))
            )
            amplitude = cls._percentage_field(cls._value_field(raw, ("振幅", "amplitude")))
            volume = cls._integer_field(cls._value_field(raw, ("成交量", "volume")))
            amount = cls._decimal_field(cls._value_field(raw, ("成交额", "amount")), amount=True)
            turnover_rate = cls._percentage_field(cls._value_field(raw, ("换手率", "turnoverRate", "turnover_rate")))

            recognized = {
                key
                for key in raw
                if key in {"code", "代码", "股票代码", "股票简称", "股票名称", "名称", "name", "market_code"}
                or any(token in key for token in ("最新价", "收盘价", "price", "最新涨跌幅", "涨跌幅", "changePercent", "change_rate", "振幅", "amplitude", "成交量", "volume", "成交额", "amount", "换手率", "turnoverRate", "turnover_rate"))
            }
            extra_fields = {
                key: cls._clean_value(value)
                for key, value in raw.items()
                if key not in recognized
            }
            rows.append(
                IwencaiSelectionData(
                    instrumentId=instrument_id,
                    name=name,
                    price=price,
                    changeRate=change_rate,
                    amplitude=amplitude,
                    volume=volume,
                    amount=amount,
                    turnoverRate=turnover_rate,
                    extraFields=extra_fields,
                )
            )
        return rows

    @staticmethod
    def _match_code(value: Any) -> re.Match[str] | None:
        return _CODE.search(str(value)) if isinstance(value, (str, int)) else None

    @staticmethod
    def _clean_mapping(value: Mapping[Any, Any]) -> dict[str, Any]:
        return {
            str(key).replace(" ", "").strip(): item
            for key, item in value.items()
            if item is not None
        }

    @classmethod
    def _value_field(cls, raw: Mapping[str, Any], labels: tuple[str, ...]) -> Any:
        for key, value in raw.items():
            if any(label.casefold() in key.casefold() for label in labels):
                return value
        return None

    @classmethod
    def _text_field(cls, raw: Mapping[str, Any], labels: tuple[str, ...]) -> str | None:
        value = cls._value_field(raw, labels)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _numeric(value: Any, *, amount: bool = False) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        source_float = isinstance(value, float)
        if isinstance(value, Decimal):
            number = value
        else:
            text = str(value).strip().replace(",", "")
            if text in _MISSING:
                return None
            multiplier = Decimal("1")
            if text.endswith("亿"):
                multiplier = Decimal("100000000")
                text = text[:-1].strip()
            elif text.endswith("万"):
                multiplier = Decimal("10000")
                text = text[:-1].strip()
            if text.endswith("%"):
                text = text[:-1].strip()
            if not _NUMBER.fullmatch(text):
                return None
            try:
                number = Decimal(text) * multiplier
            except InvalidOperation:
                return None
        if not number.is_finite():
            return None
        if source_float:
            # JSON floats from the upstream table often contain binary-noise
            # tails such as 3.4709999999999996.  The source publishes six
            # decimal places for these quote metrics, so round only values
            # that arrived as floats; strings remain exact.
            try:
                number = number.quantize(Decimal("0.000001"))
            except InvalidOperation:
                return None
        return number.normalize()

    @classmethod
    def _decimal_field(cls, value: Any, *, amount: bool = False) -> Decimal | None:
        return cls._numeric(value, amount=amount)

    @classmethod
    def _percentage_field(cls, value: Any) -> Decimal | None:
        number = cls._numeric(value)
        return number / Decimal("100") if number is not None else None

    @classmethod
    def _integer_field(cls, value: Any) -> int | None:
        number = cls._numeric(value)
        if number is None or number != number.to_integral_value() or number < 0:
            return None
        return int(number)

    @staticmethod
    def _clean_value(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key).strip(): IwencaiProvider._clean_value(item) for key, item in value.items() if item is not None}
        if isinstance(value, list):
            return [IwencaiProvider._clean_value(item) for item in value]
        if isinstance(value, float) and math.isfinite(value):
            return Decimal(str(value))
        if isinstance(value, str):
            return value.strip()
        return value

    @classmethod
    def _instrument_id(cls, code: str, raw: Mapping[str, Any]) -> InstrumentId:
        source_value = next((value for key, value in raw.items() if key in {"code", "代码", "股票代码"} or "代码" in key), code)
        match = _CODE_WITH_EXCHANGE.fullmatch(str(source_value).strip())
        if match is None:
            match = _CODE_WITH_EXCHANGE.fullmatch(code)
        if match is None:
            raise ValueError("invalid iWenCai stock code")
        stock_code, suffix = match.groups()
        exchange = {
            "SH": Exchange.SSE,
            "SZ": Exchange.SZSE,
            "BJ": Exchange.BSE,
        }.get(suffix.upper() if suffix else "")
        if exchange is None:
            market_code = str(raw.get("market_code", "")).strip()
            exchange = {"17": Exchange.SSE, "33": Exchange.SZSE}.get(market_code)
        if exchange is None:
            if stock_code.startswith("6"):
                exchange = Exchange.SSE
            elif stock_code.startswith(("0", "3")):
                exchange = Exchange.SZSE
            elif stock_code.startswith(("4", "8")):
                exchange = Exchange.BSE
        if exchange is None:
            raise ValueError("cannot identify iWenCai stock exchange")
        return InstrumentId(
            code=stock_code,
            market=Market.CN_A,
            kind=InstrumentKind.EQUITY,
            exchange=exchange,
        )

    @staticmethod
    def _positive_int(value: Any, label: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 0
        return parsed if parsed >= 0 else 0

    @classmethod
    def _normalize_search_hits(cls, records: list[Any]) -> list[IwencaiSearchHit]:
        hits: list[IwencaiSearchHit] = []
        for raw in records:
            if not isinstance(raw, dict):
                continue
            extra = raw.get("extra") or {}
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except json.JSONDecodeError:
                    extra = {"raw": extra}
            if not isinstance(extra, dict):
                extra = {"value": extra}
            try:
                score = float(raw.get("score", 0) or 0)
            except (TypeError, ValueError):
                score = 0.0
            normalized = {
                key: cls._clean_value(value)
                for key, value in raw.items()
                if key not in {"uid", "title", "publish_date", "score", "extra"}
            }
            normalized.update(cls._clean_mapping(extra))
            url = cls._first_url(normalized)
            for key in ("url", "link", "document_url", "documentUrl", "report_url", "reportUrl"):
                normalized.pop(key, None)
            hits.append(IwencaiSearchHit(
                uid=str(raw["uid"]) if raw.get("uid") else None,
                title=str(raw.get("title", "") or "").strip(),
                publishedAt=str(raw["publish_date"]).strip() if raw.get("publish_date") else None,
                url=url,
                score=score,
                extraFields=normalized,
            ))
        return hits

    @staticmethod
    def _first_url(values: Mapping[str, Any]) -> str | None:
        for key in ("url", "link", "document_url", "documentUrl", "report_url", "reportUrl"):
            value = values.get(key)
            if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
                return value.strip()
        return None

    @staticmethod
    def _report_url_and_duid(value: str) -> tuple[str, str]:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme.casefold() != "https" or hostname != "ms.10jqka.com.cn":
            raise ValueError("report detail url must use https://ms.10jqka.com.cn")
        if parsed.path != "/businesspage-outer/research-report/index.html":
            raise ValueError("url is not a supported iWenCai research report page")
        duids = parse_qs(parsed.query).get("duid", [])
        if len(duids) != 1 or re.fullmatch(r"[A-Za-z0-9_-]{1,200}", duids[0]) is None:
            raise ValueError("report detail url must contain one valid duid query parameter")
        return value, duids[0]

    @classmethod
    def _normalize_report_detail(
        cls,
        response: IwencaiResponse,
        request: IwencaiReportDetailRequest,
        report_url: str,
    ) -> IwencaiReportDetailData:
        document = cls._json_document(response, "report detail")
        if document.get("status_code", 0) not in (0, "0"):
            raise ProviderError(
                Source(providerId="iwencai", sourceUrl=report_url),
                f"report detail error: {document.get('status_msg', '')}",
            )
        data = document.get("data")
        word_data = data.get("wordData") if isinstance(data, dict) else None
        if not isinstance(word_data, dict):
            raise ProviderError(Source(providerId="iwencai", sourceUrl=report_url), "report detail response has no wordData object")
        content = str(word_data.get("content") or "").strip()
        if not content:
            raise ProviderError(Source(providerId="iwencai", sourceUrl=report_url), "report detail contained no readable content")
        known = {
            "UID", "title", "content", "organize", "researcher", "pubtime", "ctime",
            "usa_server", "amazon_server", "amazonJapan_server", "click", "month_click",
            "ext", "path",
        }
        extra = {
            str(key): cls._clean_value(value)
            for key, value in word_data.items()
            if key not in known
        }
        report_source_url = None
        if isinstance(data, dict) and data.get("site_url"):
            report_source_url = str(data["site_url"]).strip() or None
        _, duid = cls._report_url_and_duid(report_url)
        source_document_id = str(word_data.get("UID") or request.uid or duid).strip()
        published_at = cls._parse_published_at(word_data.get("pubtime") or request.published_at)
        return IwencaiReportDetailData(
            documentId=f"iwencai:report:{source_document_id}",
            sourceDocumentId=source_document_id,
            title=str(word_data.get("title") or request.title or "").strip(),
            contentText=content,
            publishedAt=published_at,
            contentAvailable=True,
            relatedInstruments=[],
            url=report_url,
            originalUrl=report_source_url,
            organization=str(word_data.get("organize") or "").strip() or None,
            analyst=str(word_data.get("researcher") or "").strip() or None,
            fileExtension=str(word_data.get("ext") or "").strip() or None,
            sourceCreatedAt=str(word_data.get("ctime") or "") or None,
            extraFields=extra,
        )

    @staticmethod
    def _parse_published_at(value: Any) -> datetime | None:
        if value is None or not str(value).strip():
            return None
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _deduplicate(articles: list[IwencaiSearchHit]) -> list[IwencaiSearchHit]:
        best: dict[str, IwencaiSearchHit] = {}
        for article in articles:
            key = article.uid or f"{article.title}|{article.published_at or ''}"
            if key not in best or article.score > best[key].score:
                best[key] = article
        return sorted(best.values(), key=lambda item: item.published_at or "", reverse=True)

    def _selection_record(
        self,
        data: IwencaiSelectionData,
        *,
        captured_at: datetime,
    ) -> StandardRecord:
        payload = data.model_dump(mode="json", by_alias=True)
        source = Source(
            providerId=self.provider_id,
            sourceRecordId=data.instrument_id.code,
            sourceUrl=IWENCAI_SCREENER_URL,
        )
        return StandardRecord(
            dataset="iwencai.selection",
            schemaVersion="1.0",
            recordId=f"iwencai.selection:{data.instrument_id.code}@{captured_at.isoformat()}",
            entityId=data.instrument_id,
            capturedAt=captured_at,
            source=source,
            status=DataStatus.LIVE,
            quality=Quality(),
            provenance=Provenance(
                recordClass=ProvenanceClass.STANDARDIZED,
                transformationVersion="iwencai-selection-normalizer/1",
            ),
            data=payload,
        )

    def _search_record(
        self,
        data: IwencaiSearchData,
        *,
        captured_at: datetime,
    ) -> StandardRecord:
        source_record_id = data.uid or f"{data.title}|{data.published_at or ''}"
        return StandardRecord(
            dataset="iwencai.search",
            schemaVersion="1.0",
            recordId=f"iwencai.search:{source_record_id}@{captured_at.isoformat()}",
            entityId=source_record_id,
            publishedAt=None,
            capturedAt=captured_at,
            source=Source(
                providerId=self.provider_id,
                sourceRecordId=source_record_id,
                sourceUrl=IWENCAI_SEARCH_URL,
            ),
            status=DataStatus.LIVE,
            quality=Quality(),
            provenance=Provenance(
                recordClass=ProvenanceClass.STANDARDIZED,
                transformationVersion="iwencai-search-normalizer/1",
            ),
            data=data.model_dump(mode="json", by_alias=True),
        )

    def _report_detail_record(
        self,
        data: IwencaiReportDetailData,
        *,
        captured_at: datetime,
    ) -> StandardRecord:
        source_record_id = data.source_document_id
        source_reference = SourceReference(
            providerId=self.provider_id,
            sourceRecordId=source_record_id,
            sourceUrl=str(data.url),
        )
        return StandardRecord(
            dataset="iwencai.report_detail",
            schemaVersion="1.0",
            recordId=data.document_id,
            entityId=data.related_instruments[0] if data.related_instruments else data.document_id,
            publishedAt=data.published_at,
            capturedAt=captured_at,
            source=Source(
                providerId=self.provider_id,
                sourceRecordId=source_record_id,
                sourceUrl=str(data.url),
            ),
            status=DataStatus.LIVE,
            quality=Quality(),
            provenance=Provenance(
                recordClass=ProvenanceClass.STANDARDIZED,
                transformationVersion="iwencai-report-detail-normalizer/1",
                sourceReferences=[source_reference],
            ),
            data=data.model_dump(mode="json", by_alias=True),
        )


__all__ = [
    "IWENCAI_QUERY_URL",
    "IWENCAI_REPORT_DETAIL_URL",
    "IWENCAI_RENDER_URL",
    "IWENCAI_SEARCH_URL",
    "IWENCAI_SCREENER_URL",
    "IWENCAI_STREAM_URL",
    "IwencaiProvider",
    "IwencaiResponse",
    "IwencaiTransport",
]
