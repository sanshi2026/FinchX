"""Tencent ltgd source adapter for historical top float holders."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, NoReturn
from urllib.parse import urlencode

from finchx.contracts import Source
from finchx.datasets.fundamental_common import FundamentalRequest
from finchx.datasets.market_instrument_sector_snapshot import _validate_sector_instrument
from finchx.entities import Exchange
from finchx.providers.errors import ProviderError
from finchx.providers.http import (
    DEFAULT_TIMEOUT_SECONDS,
    build_headers,
    http_status_failure_reason,
)
from finchx.providers.tencent import (
    _TencentTransport,
    _TencentTransportFailure,
    _UrllibTencentTransport,
    _reject_json_constant,
)


TENCENT_FLOAT_HOLDER_ENDPOINT = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/hs/ltgd/get"
)
_EXCHANGE_PREFIX = {Exchange.SSE: "sh", Exchange.SZSE: "sz"}
_ASSIGNMENT = re.compile(r"^\s*v_liutonggd\s*=\s*(\{.*\})\s*;?\s*$", re.DOTALL)
_HEADERS = build_headers(referer="https://stockapp.finance.qq.com/")
_SOURCE_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class _FloatHolderRow:
    holder_id: str | None
    holder_name: str
    shares: int
    holder_type: str
    float_share_ratio: Decimal | None
    bdms: int | None
    previous_shares: int | None


@dataclass(frozen=True)
class _FloatHolderPeriod:
    period_end: date
    published_at: datetime
    rows: tuple[_FloatHolderRow, ...]


@dataclass(frozen=True)
class _ProviderFloatHolderPayload:
    instrument_id: Any
    raw_payload: Mapping[str, Any]
    periods: tuple[_FloatHolderPeriod, ...]
    source_record_id: str
    source_url: str
    captured_at: datetime


FLOAT_HOLDER_FIELD_INVENTORY = frozenset(
    {
        "code",
        "msg",
        "data.data[].pdt",
        "data.data[].dt",
        "data.history[]",
        "data.data[].rows[].gddm",
        "data.data[].rows[].gdmc",
        "data.data[].rows[].cgsl",
        "data.data[].rows[].gfxz",
        "data.data[].rows[].ltbl",
        "data.data[].rows[].bdms",
        "data.data[].rows[].sqcgsl",
    }
)
_EXPECTED_FIELDS = {
    "data.data[]": {"pdt", "dt", "rows"},
    "data.data[].rows[]": {"gddm", "gdmc", "cgsl", "gfxz", "ltbl", "bdms", "sqcgsl"},
}


def iter_float_holder_leaf_paths(value: Any, path: str = "") -> set[str]:
    """Return normalized ltgd leaf paths, replacing array indexes with ``[]``."""
    if isinstance(value, Mapping):
        paths: set[str] = set()
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            paths.update(iter_float_holder_leaf_paths(child, child_path))
        return paths
    if isinstance(value, list):
        paths: set[str] = set()
        for child in value:
            paths.update(iter_float_holder_leaf_paths(child, f"{path}[]"))
        return paths
    return {path}


class TencentFloatHolderProvider:
    """Fetch and validate one complete ltgd historical holder response."""

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
            sourceUrl=TENCENT_FLOAT_HOLDER_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_float_holders(
        self,
        request: FundamentalRequest,
    ) -> _ProviderFloatHolderPayload:
        if not isinstance(request, FundamentalRequest):
            self._fail("request must be a FundamentalRequest")
        try:
            _validate_sector_instrument(request.instrument_id)
        except ValueError as exc:
            self._fail(str(exc))
        prefix = _EXCHANGE_PREFIX[request.instrument_id.exchange]
        symbol = f"{prefix}{request.instrument_id.code}"
        params = {"type": "ltgd", "_var": "v_liutonggd", "code": symbol}
        request_url = f"{TENCENT_FLOAT_HOLDER_ENDPOINT}?{urlencode(params)}"
        try:
            response = self._transport.get(
                TENCENT_FLOAT_HOLDER_ENDPOINT,
                params=params,
                headers=_HEADERS,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent ltgd transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent ltgd transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent ltgd returned {status_reason}")
        if not response.text.strip():
            self._fail("Tencent ltgd returned an empty payload")
        document = self._decode(response.text)
        self._validate_document(document, request)
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        periods = self._parse_periods(document["data"]["data"])
        return _ProviderFloatHolderPayload(
            instrument_id=request.instrument_id,
            raw_payload=document,
            periods=periods,
            source_record_id=f"{symbol}:ltgd",
            source_url=request_url,
            captured_at=captured_at,
        )

    fetch_raw_float_holder = fetch_raw_float_holders

    def _decode(self, text: str) -> dict[str, Any]:
        matched = _ASSIGNMENT.fullmatch(text.strip())
        if matched is None:
            self._fail("Tencent ltgd response is not a valid v_liutonggd assignment")
        try:
            document = json.loads(matched.group(1), parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Tencent ltgd assignment contains malformed JSON: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Tencent ltgd JSON root must be an object")
        return document

    def _validate_document(self, document: Mapping[str, Any], request: FundamentalRequest) -> None:
        if document.get("code") not in (0, "0") or isinstance(document.get("code"), bool):
            self._fail(f"Tencent ltgd source code indicates failure: {document.get('code')!r}")
        if not isinstance(document.get("msg"), str):
            self._fail("Tencent ltgd response msg must be text")
        if set(document) != {"code", "msg", "data"}:
            self._fail(f"Tencent ltgd root has unexpected fields: {sorted(set(document) - {'code', 'msg', 'data'})}")
        data = document.get("data")
        if not isinstance(data, dict) or set(data) - {"data", "history"}:
            self._fail("Tencent ltgd data has unexpected fields")
        blocks = data.get("data")
        if not isinstance(blocks, list):
            self._fail("Tencent ltgd data.data must be an array")
        history = data.get("history", [])
        if not isinstance(history, list) or any(not isinstance(item, str) for item in history):
            self._fail("Tencent ltgd data.history must be a string array")
        for block in blocks:
            if not isinstance(block, dict):
                self._fail("Tencent ltgd data.data rows must be objects")
            self._validate_mapping_fields("data.data[]", block)
            rows = block.get("rows")
            if not isinstance(rows, list):
                self._fail("Tencent ltgd data.data[].rows must be an array")
            for row in rows:
                if not isinstance(row, dict):
                    self._fail("Tencent ltgd holder rows must be objects")
                self._validate_mapping_fields("data.data[].rows[]", row)

    def _parse_periods(self, blocks: list[dict[str, Any]]) -> tuple[_FloatHolderPeriod, ...]:
        periods: list[_FloatHolderPeriod] = []
        previous_period: date | None = None
        seen: set[date] = set()
        for block_index, block in enumerate(blocks):
            period_end = self._period_date(block.get("pdt"), f"data.data[{block_index}].pdt")
            if period_end in seen:
                self._fail(f"Tencent ltgd contains duplicate period {period_end.isoformat()}")
            if previous_period is not None and period_end >= previous_period:
                self._fail("Tencent ltgd periods are not in descending order")
            seen.add(period_end)
            previous_period = period_end
            published_at = self._published_time(block.get("dt"), f"data.data[{block_index}].dt")
            rows: list[_FloatHolderRow] = []
            for row_index, raw in enumerate(block["rows"]):
                rows.append(self._parse_row(raw, f"data.data[{block_index}].rows[{row_index}]"))
            periods.append(
                _FloatHolderPeriod(
                    period_end=period_end,
                    published_at=published_at,
                    rows=tuple(rows),
                )
            )
        return tuple(periods)

    def _parse_row(self, raw: Mapping[str, Any], context: str) -> _FloatHolderRow:
        holder_id = self._optional_text(raw.get("gddm"), f"{context}.gddm")
        holder_name = self._required_text(raw.get("gdmc"), f"{context}.gdmc")
        shares = self._required_nonnegative_int(raw.get("cgsl"), f"{context}.cgsl")
        holder_type = self._required_text(raw.get("gfxz"), f"{context}.gfxz")
        float_share_ratio = self._percent(raw.get("ltbl"), f"{context}.ltbl")
        bdms = self._optional_flag(raw.get("bdms"), f"{context}.bdms")
        previous_shares = self._optional_nonnegative_int(raw.get("sqcgsl"), f"{context}.sqcgsl")
        return _FloatHolderRow(
            holder_id=holder_id,
            holder_name=holder_name,
            shares=shares,
            holder_type=holder_type,
            float_share_ratio=float_share_ratio,
            bdms=bdms,
            previous_shares=previous_shares,
        )

    def _validate_mapping_fields(self, path: str, value: Mapping[str, Any]) -> None:
        unexpected = set(value) - _EXPECTED_FIELDS[path]
        if unexpected:
            self._fail(f"Tencent ltgd {path} has unexpected fields: {sorted(unexpected)}")

    def _period_date(self, value: Any, label: str) -> date:
        if not isinstance(value, str):
            self._fail(f"Tencent ltgd {label} must be an ISO date")
        try:
            return date.fromisoformat(value)
        except ValueError:
            self._fail(f"Tencent ltgd {label} is not an ISO date")

    def _published_time(self, value: Any, label: str) -> datetime:
        if not isinstance(value, str):
            self._fail(f"Tencent ltgd {label} must be source datetime text")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            self._fail(f"Tencent ltgd {label} is not parseable")
        return parsed.replace(tzinfo=_SOURCE_TZ)

    def _optional_text(self, value: Any, label: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            self._fail(f"Tencent ltgd {label} must be text")
        return value.strip() or None

    def _required_text(self, value: Any, label: str) -> str:
        result = self._optional_text(value, label)
        if result is None:
            self._fail(f"Tencent ltgd {label} must be non-empty text")
        return result

    def _optional_nonnegative_int(self, value: Any, label: str) -> int | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        if isinstance(value, bool):
            self._fail(f"Tencent ltgd {label} must be an integer")
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            self._fail(f"Tencent ltgd {label} must be an integer")
        if str(parsed) != str(value).strip() or parsed < 0:
            self._fail(f"Tencent ltgd {label} must be a non-negative integer")
        return parsed

    def _required_nonnegative_int(self, value: Any, label: str) -> int:
        parsed = self._optional_nonnegative_int(value, label)
        if parsed is None:
            self._fail(f"Tencent ltgd {label} is required")
        return parsed

    def _optional_flag(self, value: Any, label: str) -> int | None:
        parsed = self._optional_nonnegative_int(value, label)
        if parsed is not None and parsed not in (0, 1):
            self._fail(f"Tencent ltgd {label} must be 0 or 1")
        return parsed

    def _percent(self, value: Any, label: str) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            self._fail(f"Tencent ltgd {label} is not a valid Decimal")
        if not parsed.is_finite():
            self._fail(f"Tencent ltgd {label} must be finite")
        return parsed / Decimal("100")

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)


__all__ = [
    "FLOAT_HOLDER_FIELD_INVENTORY",
    "TENCENT_FLOAT_HOLDER_ENDPOINT",
    "TencentFloatHolderProvider",
    "_FloatHolderPeriod",
    "_FloatHolderRow",
    "_ProviderFloatHolderPayload",
    "iter_float_holder_leaf_paths",
]
