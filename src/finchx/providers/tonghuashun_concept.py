"""Tonghuashun concept page adapter."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import html
import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import quote

from finchx.contracts import Source
from finchx.datasets.market_concept import (
    ConceptRef,
    ConceptListRequest,
    ConceptQuoteSnapshotRequest,
    ConceptOhlcvRequest,
)
from finchx.providers.errors import ProviderError


LIST_URL = "https://q.10jqka.com.cn/gn/"
DETAIL_URL = "https://q.10jqka.com.cn/gn/detail/code/{}/"
QUOTE_URL = "https://d.10jqka.com.cn/v2/realhead/bk_{}/last.js"
KLINE_URL = "https://d.10jqka.com.cn/v4/line/bk_{}/01/{}.js"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Referer": LIST_URL,
    "Accept": "text/html,application/javascript,application/json,*/*;q=0.8",
}
_DECIMAL_PLACEHOLDERS = {"", "-", "--", "—", "N/A", "null", "None"}
_CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


class TonghuashunConceptProvider:
    """Fetch concept directory, detail, quote, and daily bars from THS."""

    def __init__(
        self,
        opener: Callable[..., Any] | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._open = opener or urllib.request.urlopen
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(providerId="tonghuashun.concept", sourceUrl=LIST_URL)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_concept_list(self, request: ConceptListRequest) -> list[dict[str, Any]]:
        if not isinstance(request, ConceptListRequest):
            self._fail("request must be a ConceptListRequest")
        text = self._get(LIST_URL)
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        pattern = re.compile(
            r'<a\b[^>]*href=["\']https?://q\.10jqka\.com\.cn/gn/detail/code/(\d+)/[^"\']*["\'][^>]*>(.*?)</a>',
            re.I | re.S,
        )
        for match in pattern.finditer(text):
            concept_id = match.group(1)
            name = _text(match.group(2))
            if not name or concept_id in seen:
                continue
            seen.add(concept_id)
            rows.append(_concept_payload(concept_id, name))
        if not rows:
            self._fail("concept listing contained no recognizable concept links")
        captured_at = self._capture_time()
        return [
            {**row, "__finchx": self._metadata(LIST_URL, row["providerSectorId"], captured_at)}
            for row in rows
        ]

    def fetch_raw_concept_quote_snapshot(
        self, request: ConceptQuoteSnapshotRequest
    ) -> dict[str, Any]:
        if not isinstance(request, ConceptQuoteSnapshotRequest):
            self._fail("request must be a ConceptQuoteSnapshotRequest")
        ref, quote_id, detail = self._resolve(request.concept)
        quote_url = QUOTE_URL.format(quote_id)
        items = self._parse_realhead_items(self._get(quote_url), ref, quote_id)

        change_percent = self._dec(items.get("199112"))
        flow_yi = _detail_metric(detail, "资金净流入(亿)", self)
        timestamp = _parse_source_timestamp(items.get("updateTime") or items.get("time"), self)
        volume = _whole_shares(items.get("13"), self, required=False)
        rise_count = _whole_count(items.get("38"), self)
        fall_count = _whole_count(items.get("39"), self)
        return {
            "concept": ref,
            "indexLevel": self._dec(items.get("10")),
            "previousClose": self._dec(items.get("6")),
            "open": self._dec(items.get("7")),
            "high": self._dec(items.get("8")),
            "low": self._dec(items.get("9")),
            "levelChange": self._dec(items.get("264648")),
            "changeRate": change_percent / Decimal(100) if change_percent is not None else None,
            # Verified against the official detail page: these raw values are shares and CNY.
            "volume": volume,
            "amount": self._dec(items.get("19")),
            "netMoneyFlow": flow_yi * Decimal(100_000_000) if flow_yi is not None else None,
            "riseCount": rise_count,
            "fallCount": fall_count,
            "sourceTimestamp": timestamp,
            "__finchx": self._metadata(
                quote_url,
                ref.provider_sector_id,
                self._capture_time(),
                source_references=[
                    {
                        "providerId": self._source.provider_id,
                        "sourceRecordId": ref.provider_sector_id,
                        "sourceUrl": DETAIL_URL.format(quote(ref.provider_sector_id)),
                    }
                ],
            ),
        }

    def fetch_raw_concept_ohlcv(self, request: ConceptOhlcvRequest) -> list[dict[str, Any]]:
        if not isinstance(request, ConceptOhlcvRequest):
            self._fail("request must be a ConceptOhlcvRequest")
        ref, quote_id, _ = self._resolve(request.concept)
        rows_by_date: dict[date, dict[str, Any]] = {}
        captured_at = self._capture_time()

        def parse_payload(data: str, source_url: str) -> list[dict[str, Any]]:
            parsed: list[dict[str, Any]] = []
            if not data.strip():
                return parsed
            for line_number, line in enumerate(data.split(";"), start=1):
                if not line.strip():
                    continue
                columns = line.split(",")
                if len(columns) < 7:
                    self._fail(f"daily K-line row {line_number} has fewer than seven columns")
                try:
                    bar_date = datetime.strptime(columns[0], "%Y%m%d").date()
                except ValueError:
                    self._fail(f"daily K-line row {line_number} has an invalid date")
                if not request.start_date <= bar_date <= request.end_date:
                    continue
                open_value, high, low, close = (
                    self._required_dec(value, f"daily K-line {bar_date} OHLC")
                    for value in columns[1:5]
                )
                volume = _whole_shares(columns[5], self, required=True)
                amount = self._dec(columns[6])
                parsed.append(
                    {
                        "concept": ref,
                        "barDate": bar_date,
                        "open": open_value,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume,
                        "amount": amount,
                        "__finchx": self._metadata(
                            source_url,
                            f"{ref.provider_sector_id}:{bar_date.isoformat()}",
                            captured_at,
                            source_references=[
                                {
                                    "providerId": self._source.provider_id,
                                    "sourceRecordId": ref.provider_sector_id,
                                    "sourceUrl": DETAIL_URL.format(quote(ref.provider_sector_id)),
                                }
                            ],
                        ),
                    }
                )
            return parsed

        for year in range(request.start_date.year, request.end_date.year + 1):
            kline_url = KLINE_URL.format(quote_id, year)
            payload = self._jsonp(self._get(kline_url))
            data = payload.get("data")
            if not isinstance(data, str):
                self._fail("daily K-line JSONP payload data must be a CSV string")
            for row in parse_payload(data, kline_url):
                bar_date = row["barDate"]
                if bar_date in rows_by_date:
                    self._fail(f"annual K-line source repeated bar date {bar_date}")
                rows_by_date[bar_date] = row

        # The annual file can lag the most recent bars. Merge the current year's
        # rolling last.js data so a request that includes today's session gets
        # the bar published by Tonghuashun's latest-data endpoint.
        current_year = captured_at.astimezone(_CHINA_TZ).year
        if request.start_date.year <= current_year <= request.end_date.year:
            latest_url = KLINE_URL.format(quote_id, "last")
            payload = self._jsonp(self._get(latest_url))
            data = payload.get("data")
            if not isinstance(data, str):
                self._fail("latest daily K-line JSONP payload data must be a CSV string")
            for row in parse_payload(data, latest_url):
                bar_date = row["barDate"]
                existing = rows_by_date.get(bar_date)
                if existing is None:
                    rows_by_date[bar_date] = row
                    continue
                for field in ("open", "high", "low", "close", "volume", "amount"):
                    old_value, new_value = existing[field], row[field]
                    if old_value is not None and new_value is not None and old_value != new_value:
                        self._fail(f"annual and latest K-line sources conflict for {bar_date} {field}")
                    if new_value is None:
                        row[field] = old_value
                rows_by_date[bar_date] = row

        return [rows_by_date[bar_date] for bar_date in sorted(rows_by_date)]

    def _concept(self, value: ConceptRef | str) -> ConceptRef:
        if isinstance(value, ConceptRef):
            return value
        if not isinstance(value, str) or not value.strip():
            self._fail("concept must be a ConceptRef or exact concept name")
        rows = self.fetch_raw_concept_list(ConceptListRequest())
        matches = [row for row in rows if row["sectorName"] == value.strip()]
        if len(matches) != 1:
            self._fail("concept name is missing or ambiguous; pass a ConceptRef")
        return ConceptRef.model_validate(
            {key: value for key, value in matches[0].items() if not key.startswith("__")}
        )

    def _resolve(self, concept: ConceptRef | str) -> tuple[ConceptRef, str, str]:
        return self._resolve_ref(self._concept(concept))

    def _resolve_ref(self, ref: ConceptRef) -> tuple[ConceptRef, str, str]:
        text = self._get(DETAIL_URL.format(quote(ref.provider_sector_id)))
        ids = set(
            re.findall(
                rf"{re.escape(ref.sector_name)}\s*<span>\s*(\d{{5,10}})\s*</span>",
                text,
                re.I,
            )
        )
        ids.update(re.findall(r"\bbk_(\d{5,10})\b", text, re.I))
        ids.discard(ref.provider_sector_id)
        if len(ids) != 1:
            self._fail("concept detail page did not expose one unique quote ID")
        return ref, ids.pop(), text

    def _parse_realhead_items(
        self, text: str, ref: ConceptRef, quote_id: str
    ) -> dict[str, Any]:
        payload = self._jsonp(text)
        items = payload.get("items")
        if not isinstance(items, dict):
            self._fail("realhead JSONP payload must contain an items object")
        source_quote_id = items.get("5")
        if source_quote_id is None:
            self._fail("realhead payload did not expose its quote ID")
        if str(source_quote_id) != quote_id:
            self._fail("realhead quote ID does not match the concept detail page")
        source_name = items.get("name")
        if source_name and str(source_name) != ref.sector_name:
            self._fail("realhead concept name does not match the concept detail page")
        return items

    def _get(self, url: str) -> str:
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            response = self._open(req, timeout=15)
            payload = response.read()
            status = getattr(response, "status", 200)
            if status >= 400:
                self._fail(f"HTTP {status} from {url}")
            if not payload:
                self._fail(f"empty source response from {url}")
            return payload.decode("gb18030", "replace")
        except ProviderError:
            raise
        except urllib.error.HTTPError as exc:
            self._fail(f"HTTP {exc.code} from {url}")
        except Exception as exc:
            self._fail(f"HTTP request failed ({type(exc).__name__}) for {url}")

    def _jsonp(self, text: str) -> dict[str, Any]:
        match = re.fullmatch(r"\s*[A-Za-z_$][\w$]*\((\s*\{.*\}\s*)\)\s*;?\s*", text, re.S)
        if not match:
            self._fail("malformed JSONP response")
        try:
            document = json.loads(
                match.group(1),
                parse_float=Decimal,
                parse_constant=lambda value: self._fail(f"invalid JSON number {value}"),
            )
        except ProviderError:
            raise
        except Exception:
            self._fail("malformed JSONP JSON")
        if not isinstance(document, dict):
            self._fail("JSONP payload root must be an object")
        return document

    def _dec(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        text = str(value).strip()
        if text in _DECIMAL_PLACEHOLDERS:
            return None
        try:
            result = value if isinstance(value, Decimal) else Decimal(text)
        except (InvalidOperation, ValueError):
            self._fail("invalid decimal value from source")
        if not result.is_finite():
            self._fail("non-finite decimal value from source")
        return result

    def _required_dec(self, value: Any, field: str) -> Decimal:
        result = self._dec(value)
        if result is None:
            self._fail(f"required {field} is missing")
        return result

    def _fail(self, message: str) -> None:
        raise ProviderError(self._source, message)

    def _capture_time(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return value

    def _metadata(
        self,
        source_url: str,
        source_record_id: str,
        captured_at: datetime,
        *,
        source_references: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return {
            "sourceUrl": source_url,
            "sourceRecordId": source_record_id,
            "capturedAt": captured_at,
            "sourceReferences": source_references or [],
        }


def _concept_payload(concept_id: str, name: str) -> dict[str, str]:
    return {
        "sectorType": "concept",
        "sectorName": name,
        "providerNamespace": "tonghuashun_concept",
        "providerSectorId": concept_id,
    }


def _text(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value)).split())


def _whole_shares(value: Any, provider: TonghuashunConceptProvider, *, required: bool) -> int | None:
    amount = provider._dec(value)
    if amount is None:
        if required:
            provider._fail("required share volume is missing")
        return None
    if amount != amount.to_integral_value() or amount < 0:
        provider._fail("share volume must be a non-negative whole number of shares")
    return int(amount)


def _whole_count(value: Any, provider: TonghuashunConceptProvider) -> int | None:
    amount = provider._dec(value)
    if amount is None:
        return None
    if amount != amount.to_integral_value() or amount < 0:
        provider._fail("rise/fall count must be a non-negative whole number")
    return int(amount)


def _detail_metric(
    text: str, label: str, provider: TonghuashunConceptProvider
) -> Decimal | None:
    label_pattern = re.escape(label)
    match = re.search(
        rf"<dt>\s*{label_pattern}\s*</dt>\s*<dd\b[^>]*>\s*([^<]+)",
        text,
        re.I | re.S,
    )
    if not match:
        return None
    value = match.group(1).strip().replace(",", "")
    if value in _DECIMAL_PLACEHOLDERS:
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        provider._fail(f"invalid {label} value on concept detail page")
    if not result.is_finite():
        provider._fail(f"non-finite {label} value on concept detail page")
    return result


def _parse_source_timestamp(value: Any, provider: TonghuashunConceptProvider) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r"\s*北京时间$", "", text)
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=_CHINA_TZ)
        except ValueError:
            pass
    provider._fail("realhead source timestamp has an unrecognized format")
