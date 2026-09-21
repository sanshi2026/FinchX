"""Tonghuashun financial-statement source adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from typing import Any

from finchx.contracts import Source
from finchx.datasets.financial_statement import FinancialStatementRequest
from finchx.providers.eastmoney_market import (
    _EastmoneyTransport,
    _EastmoneyTransportFailure,
    _UrllibEastmoneyTransport,
)
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, build_headers, http_status_failure_reason


TONGHUASHUN_FINANCIAL_ENDPOINT = "https://basic.10jqka.com.cn/api/stock/finance"
STATEMENT_SOURCE_TYPES = {
    "balance_sheet": "debt",
    "income_statement": "benefit",
    "cash_flow_statement": "cash",
}
_FINANCIAL_FIELDS = frozenset(
    {"title", "report", "simple", "year", "report_yoy", "simple_yoy", "simple_mom", "year_yoy"}
)
_FIELD_FINANCIAL_FIELDS = frozenset({"title", "report", "simple", "year"})


@dataclass(frozen=True)
class _ProviderFinancialStatement:
    instrument_id: Any
    statement_type: str
    source_report_type: str
    raw_payload: Mapping[str, Any]
    flash_data: Mapping[str, Any]
    field_flash_data: Mapping[str, Any]
    source_record_id: str
    source_url: str
    captured_at: datetime


class TonghuashunFinancialProvider:
    provider_id = "tonghuashun.financial"

    def __init__(self, transport: _EastmoneyTransport | None = None, *, clock: Any | None = None) -> None:
        self._transport = transport or _UrllibEastmoneyTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(providerId=self.provider_id, sourceUrl="https://basic.10jqka.com.cn")

    @property
    def source(self) -> Source:
        return self._source

    def _fail(self, reason: str) -> None:
        raise ProviderError(self.source, reason)

    def fetch_raw_statement(self, request: FinancialStatementRequest) -> _ProviderFinancialStatement:
        if not isinstance(request, FinancialStatementRequest):
            self._fail("request must be a FinancialStatementRequest")
        source_report_type = STATEMENT_SOURCE_TYPES.get(request.statement_type)
        if source_report_type is None:
            self._fail("statement type is not supported")
        code = request.instrument_id.code
        endpoint = f"{TONGHUASHUN_FINANCIAL_ENDPOINT}/{code}_{source_report_type}.json"
        headers = build_headers(
            accept="application/json, text/javascript, */*; q=0.01",
            referer=f"https://basic.10jqka.com.cn/{code}/finance.html",
            extra={"X-Requested-With": "XMLHttpRequest"},
        )
        try:
            response = self._transport.get(endpoint, params={}, headers=headers, timeout_seconds=DEFAULT_TIMEOUT_SECONDS)
        except _EastmoneyTransportFailure as exc:
            self._fail(f"transport failure: {exc}")
        except Exception as exc:
            self._fail(f"transport failure: {type(exc).__name__}")
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            self._fail(reason)
        if not response.text.strip():
            self._fail("empty response body")
        try:
            payload = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"malformed JSON ({type(exc).__name__})")
        if not isinstance(payload, dict) or set(payload) != {"flashData", "fieldflashData"}:
            self._fail("Tonghuashun financial root fields drifted")
        decoded: list[Mapping[str, Any]] = []
        for name, expected_fields in (("flashData", _FINANCIAL_FIELDS), ("fieldflashData", _FIELD_FINANCIAL_FIELDS)):
            value = payload.get(name)
            if not isinstance(value, str) or not value.strip():
                self._fail(f"Tonghuashun {name} must be a JSON string")
            try:
                section = json.loads(value)
            except (json.JSONDecodeError, ValueError) as exc:
                self._fail(f"Tonghuashun {name} is malformed JSON ({type(exc).__name__})")
            allowed_fields = {expected_fields}
            if name == "fieldflashData":
                allowed_fields.add(_FINANCIAL_FIELDS)
            if not isinstance(section, dict) or set(section) not in allowed_fields:
                self._fail(f"Tonghuashun {name} fields drifted")
            self._validate_section(section, name)
            decoded.append(section)
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return _ProviderFinancialStatement(
            instrument_id=request.instrument_id,
            statement_type=request.statement_type,
            source_report_type=source_report_type,
            raw_payload=payload,
            flash_data=decoded[0],
            field_flash_data=decoded[1],
            source_record_id=f"{code}_{source_report_type}",
            source_url=endpoint,
            captured_at=captured_at,
        )

    def _validate_section(self, section: Mapping[str, Any], label: str) -> None:
        title = section.get("title")
        report = section.get("report")
        if not isinstance(title, list) or not isinstance(report, list) or not title or not report:
            self._fail(f"Tonghuashun {label} title/report must be non-empty arrays")
        if len(title) != len(report):
            self._fail(f"Tonghuashun {label} title/report row counts differ")
        periods = report[0]
        if not isinstance(periods, list) or not periods:
            self._fail(f"Tonghuashun {label} report header is not an array")
        for value in periods:
            if not isinstance(value, str):
                self._fail(f"Tonghuashun {label} report period is not text")
            try:
                date.fromisoformat(value)
            except ValueError:
                self._fail(f"Tonghuashun {label} report period is not ISO date: {value!r}")
        if not isinstance(title[0], str):
            self._fail(f"Tonghuashun {label} title header is malformed")
        for index, row in enumerate(title[1:], start=1):
            if not isinstance(row, list) or len(row) < 2 or not isinstance(row[0], str):
                self._fail(f"Tonghuashun {label} title row {index} is malformed")
        for index, row in enumerate(report):
            if not isinstance(row, list) or len(row) != len(periods):
                self._fail(f"Tonghuashun {label} report row {index} length differs from periods")


__all__ = ["STATEMENT_SOURCE_TYPES", "TONGHUASHUN_FINANCIAL_ENDPOINT", "TonghuashunFinancialProvider", "_ProviderFinancialStatement"]
