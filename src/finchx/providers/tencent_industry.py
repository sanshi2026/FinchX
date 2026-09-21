"""Tencent hypm industry comparison source adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, NoReturn
from urllib.parse import urlencode

from finchx.contracts import Source
from finchx.datasets.market_industry_comparison import (
    MarketIndustryComparisonRequest,
    _ProviderIndustryComparison,
)
from finchx.datasets.market_instrument_sector_snapshot import _validate_sector_instrument
from finchx.entities import Exchange
from finchx.providers.errors import ProviderError
from finchx.providers.http import http_status_failure_reason
from finchx.providers.tencent import (
    _HEADERS,
    _TIMEOUT_SECONDS,
    _TencentTransport,
    _TencentTransportFailure,
    _UrllibTencentTransport,
    _reject_json_constant,
)


TENCENT_HYPM_ENDPOINT = "https://proxy.finance.qq.com/ifzqgtimg/appstock/hs/hypm/get"
_EXCHANGE_PREFIX = {Exchange.SSE: "sh", Exchange.SZSE: "sz"}
_ASSIGNMENT = re.compile(r"^\s*gg_hypm\s*=\s*(\{.*\})\s*;?\s*$", re.DOTALL)
_MARKET_TYPE = {Exchange.SSE: "1", Exchange.SZSE: "51"}
_BLOCK_FIELDS = {
    "hyinfo": {"dm", "hymc"},
    "data": {"sclx", "mgsy", "zsz", "syl"},
    "pm": {"syl_pm", "zsz_pm", "mgsy_pm"},
    "plate_avg": {"count", "avg_syl", "avg_mgsy", "avg_zsz"},
    "shsz_avg": {"avg_zsz", "avg_syl", "avg_mgsy"},
}


class TencentIndustryComparisonProvider:
    """Fetch and validate Tencent's current industry comparison assignment."""

    def __init__(
        self,
        transport: _TencentTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport or _UrllibTencentTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(providerId="tencent.finance.qq", sourceUrl=TENCENT_HYPM_ENDPOINT)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_industry_comparison(
        self,
        request: MarketIndustryComparisonRequest,
    ) -> _ProviderIndustryComparison:
        if not isinstance(request, MarketIndustryComparisonRequest):
            self._fail("request must be a MarketIndustryComparisonRequest")
        try:
            _validate_sector_instrument(request.instrument_id)
        except ValueError as exc:
            self._fail(str(exc))
        prefix = _EXCHANGE_PREFIX[request.instrument_id.exchange]
        symbol = f"{prefix}{request.instrument_id.code}"
        params = {"code": symbol, "_var": "gg_hypm"}
        request_url = f"{TENCENT_HYPM_ENDPOINT}?{urlencode(params)}"
        try:
            response = self._transport.get(
                TENCENT_HYPM_ENDPOINT,
                params=params,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent hypm transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent hypm transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent hypm returned {status_reason}")
        if not response.text.strip():
            self._fail("Tencent hypm returned an empty payload")
        document = self._decode(response.text)
        self._validate_root(document)
        data = document["data"]
        hyinfo = self._mapping(data, "hyinfo")
        comparison = self._mapping(data, "data")
        ranks = self._mapping(data, "pm")
        industry_avg = self._mapping(data, "plate_avg")
        market_avg = self._mapping(data, "shsz_avg")
        market_type = comparison.get("sclx")
        if market_type is not None:
            if market_type != _MARKET_TYPE[request.instrument_id.exchange]:
                self._fail("Tencent hypm sclx does not match requested exchange")
        industry_id = self._required_text(hyinfo.get("dm"), "data.hyinfo.dm")
        industry_name = self._required_text(hyinfo.get("hymc"), "data.hyinfo.hymc")
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return _ProviderIndustryComparison(
            instrument_id=request.instrument_id,
            provider_industry_id=industry_id,
            industry_name=industry_name,
            instrument_price_earnings=self._optional_decimal(comparison.get("syl"), "data.syl"),
            instrument_earnings_per_share=self._optional_decimal(comparison.get("mgsy"), "data.mgsy"),
            instrument_market_cap_100m=self._optional_source_market_cap(comparison.get("zsz"), "data.zsz"),
            price_earnings_rank=self._optional_int(ranks.get("syl_pm"), "pm.syl_pm"),
            earnings_per_share_rank=self._optional_int(ranks.get("mgsy_pm"), "pm.mgsy_pm"),
            market_capitalization_rank=self._optional_int(ranks.get("zsz_pm"), "pm.zsz_pm"),
            industry_count=self._optional_int(industry_avg.get("count"), "plate_avg.count"),
            industry_price_earnings_average=self._optional_decimal(industry_avg.get("avg_syl"), "plate_avg.avg_syl"),
            industry_earnings_per_share_average=self._optional_decimal(industry_avg.get("avg_mgsy"), "plate_avg.avg_mgsy"),
            industry_market_cap_100m_average=self._optional_source_market_cap(industry_avg.get("avg_zsz"), "plate_avg.avg_zsz"),
            market_price_earnings_average=self._optional_decimal(market_avg.get("avg_syl"), "shsz_avg.avg_syl"),
            market_earnings_per_share_average=self._optional_decimal(market_avg.get("avg_mgsy"), "shsz_avg.avg_mgsy"),
            market_market_cap_100m_average=self._optional_source_market_cap(market_avg.get("avg_zsz"), "shsz_avg.avg_zsz"),
            source_record_id=f"{symbol}:hypm:{industry_id}",
            source_url=request_url,
            captured_at=captured_at,
        )

    def _decode(self, text: str) -> dict[str, Any]:
        matched = _ASSIGNMENT.fullmatch(text.strip())
        if matched is None:
            self._fail("Tencent hypm response is not a valid gg_hypm assignment")
        try:
            document = json.loads(
                matched.group(1),
                parse_float=Decimal,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Tencent hypm assignment contains malformed JSON: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Tencent hypm JSON root must be an object")
        return document

    def _validate_root(self, document: Mapping[str, Any]) -> None:
        if document.get("code") not in (0, "0") or isinstance(document.get("code"), bool):
            self._fail(f"Tencent hypm source code indicates failure: {document.get('code')!r}")
        if document.get("msg") != "OK":
            self._fail(f"Tencent hypm source message is not OK: {document.get('msg')!r}")
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("Tencent hypm data must be an object")
        for block in _BLOCK_FIELDS:
            if block not in data or not isinstance(data[block], dict):
                self._fail(f"Tencent hypm data.{block} must be an object")
            unexpected = set(data[block]) - _BLOCK_FIELDS[block]
            if unexpected:
                self._fail(f"Tencent hypm data.{block} has unexpected fields: {sorted(unexpected)}")

    def _mapping(self, data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
        value = data.get(name)
        if not isinstance(value, dict):
            self._fail(f"Tencent hypm data.{name} must be an object")
        return value

    def _required_text(self, value: Any, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            self._fail(f"Tencent hypm {label} must be non-empty text")
        return value.strip()

    def _optional_decimal(self, value: Any, label: str) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "-", "--"}):
            return None
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            self._fail(f"Tencent hypm {label} is not a valid Decimal")
        if not parsed.is_finite():
            self._fail(f"Tencent hypm {label} must be finite")
        return parsed

    def _optional_source_market_cap(self, value: Any, label: str) -> Decimal | None:
        parsed = self._optional_decimal(value, label)
        if parsed is None:
            return None
        if parsed < 0:
            self._fail(f"Tencent hypm {label} must not be negative")
        return parsed

    def _optional_int(self, value: Any, label: str) -> int | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "-", "--"}):
            return None
        if isinstance(value, bool):
            self._fail(f"Tencent hypm {label} must be an integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            self._fail(f"Tencent hypm {label} must be an integer")
        if isinstance(value, Decimal) and value != parsed:
            self._fail(f"Tencent hypm {label} must be an integer")
        if isinstance(value, str) and str(parsed) != value.strip():
            self._fail(f"Tencent hypm {label} must be an integer")
        if parsed < 0:
            self._fail(f"Tencent hypm {label} must not be negative")
        return parsed

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)
