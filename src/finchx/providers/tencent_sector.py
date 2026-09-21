"""Tencent plateNew source adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Any, Callable, NoReturn
from urllib.parse import urlencode

from finchx.contracts import Source
from finchx.datasets.market_instrument_sector_snapshot import (
    MarketInstrumentSectorSnapshotRequest,
    _ProviderInstrumentSectorSnapshot,
    _ProviderSectorEntry,
    _validate_sector_instrument,
)
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


TENCENT_PLATE_NEW_ENDPOINT = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/stockinfo/plateNew"
)
_EXCHANGE_PREFIX = {Exchange.SSE: "sh", Exchange.SZSE: "sz"}
_BLOCK_FIELDS = {
    "area": {"id", "name", "zdf"},
    "concept": {"id", "name", "tag", "zdf"},
    "plate": {"code", "id", "level", "name", "zdf"},
}


class TencentSectorProvider:
    """Fetch and validate one current plateNew response."""

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
            sourceUrl=TENCENT_PLATE_NEW_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_instrument_sector_snapshot(
        self,
        request: MarketInstrumentSectorSnapshotRequest,
    ) -> _ProviderInstrumentSectorSnapshot:
        if not isinstance(request, MarketInstrumentSectorSnapshotRequest):
            self._fail("request must be a MarketInstrumentSectorSnapshotRequest")
        try:
            _validate_sector_instrument(request.instrument_id)
        except ValueError as exc:
            self._fail(str(exc))
        prefix = _EXCHANGE_PREFIX[request.instrument_id.exchange]
        symbol = f"{prefix}{request.instrument_id.code}"
        params = {"code": symbol, "app": "wzq", "zdf": "1"}
        request_url = f"{TENCENT_PLATE_NEW_ENDPOINT}?{urlencode(params)}"
        try:
            response = self._transport.get(
                TENCENT_PLATE_NEW_ENDPOINT,
                params=params,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent plateNew transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent plateNew transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent plateNew returned {status_reason}")
        if not response.text.strip():
            self._fail("Tencent plateNew returned an empty payload")
        document = self._decode(response.text)
        self._validate_root(document)
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        entries: list[_ProviderSectorEntry] = []
        data = document["data"]
        for block in ("area", "plate", "concept"):
            raw_rows = data.get(block)
            if not isinstance(raw_rows, list):
                self._fail(f"Tencent plateNew data.{block} must be an array")
            for index, raw in enumerate(raw_rows):
                entries.append(self._parse_entry(block, raw, index))
        return _ProviderInstrumentSectorSnapshot(
            instrument_id=request.instrument_id,
            entries=tuple(entries),
            source_record_id=f"{symbol}:plateNew",
            source_url=request_url,
            captured_at=captured_at,
        )

    def _decode(self, text: str) -> dict[str, Any]:
        try:
            document = json.loads(
                text,
                parse_float=Decimal,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Tencent plateNew returned malformed JSON: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Tencent plateNew JSON root must be an object")
        return document

    def _validate_root(self, document: Mapping[str, Any]) -> None:
        if document.get("code") not in (0, "0") or isinstance(document.get("code"), bool):
            self._fail(f"Tencent plateNew source code indicates failure: {document.get('code')!r}")
        if not isinstance(document.get("msg"), str):
            self._fail("Tencent plateNew response msg must be a string")
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("Tencent plateNew data must be an object")
        for block in _BLOCK_FIELDS:
            if block not in data:
                self._fail(f"Tencent plateNew response omitted data.{block}")

    def _parse_entry(self, block: str, raw: Any, index: int) -> _ProviderSectorEntry:
        context = f"data.{block}[{index}]"
        if not isinstance(raw, dict):
            self._fail(f"Tencent plateNew {context} must be an object")
        unexpected = set(raw) - _BLOCK_FIELDS[block]
        if unexpected:
            self._fail(f"Tencent plateNew {context} has unexpected fields: {sorted(unexpected)}")
        source_id = raw.get("id")
        source_code = raw.get("code")
        if source_id is None:
            source_id = source_code
        if not isinstance(source_id, str) or not source_id.strip():
            self._fail(f"Tencent plateNew {context}.id/code must be non-empty text")
        if source_code is not None and source_code != source_id:
            self._fail(f"Tencent plateNew {context}.code and id disagree")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            self._fail(f"Tencent plateNew {context}.name must be non-empty text")
        level = self._optional_int(raw.get("level"), f"{context}.level")
        tag = self._optional_text(raw.get("tag"), f"{context}.tag")
        change = self._optional_decimal(raw.get("zdf"), f"{context}.zdf")
        return _ProviderSectorEntry(
            block=block, provider_sector_id=source_id, name=name, level=level,
            tag=tag, change_pct_percent=change,
        )

    def _optional_text(self, value: Any, label: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            self._fail(f"Tencent plateNew {label} must be text")
        return value.strip() or None

    def _optional_int(self, value: Any, label: str) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            self._fail(f"Tencent plateNew {label} must be an integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            self._fail(f"Tencent plateNew {label} must be an integer")
        if str(parsed) != str(value).strip():
            self._fail(f"Tencent plateNew {label} must be an integer")
        return parsed

    def _optional_decimal(self, value: Any, label: str) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "-", "--"}):
            return None
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            self._fail(f"Tencent plateNew {label} is not a valid Decimal")
        if not parsed.is_finite():
            self._fail(f"Tencent plateNew {label} must be finite")
        return parsed

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)
