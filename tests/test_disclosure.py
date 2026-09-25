from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from types import MethodType, SimpleNamespace

import pytest

from finchx import FinchX
from finchx.collector import Collector
from finchx.datasets import DisclosureSearchRequest
from finchx.datasets.disclosure import _ProviderDisclosureRow, normalize_disclosure_document
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.eastmoney_documents import (
    EastmoneyDisclosureProvider,
    _ProviderDocumentPage,
    _ProviderDisclosureCategory,
    _ProviderDisclosureSecurity,
)
from finchx.providers.errors import ProviderError
from finchx.query.documents import DisclosureService


class FakeTransport:
    def __init__(self, document: dict[str, object]) -> None:
        self.document = document

    def get(self, _url, *, params, headers, timeout_seconds):
        return SimpleNamespace(status_code=200, text=json.dumps(self.document))


def _instrument() -> InstrumentId:
    return InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )


def _row(document_id: str = "202609221235", *, extra: bool = False) -> dict[str, object]:
    row: dict[str, object] = {
        "art_code": f"AN{document_id}",
        "codes": [
            {
                "ann_type": "A",
                "inner_code": "123456",
                "market_code": "1",
                "short_name": "贵州茅台",
                "stock_code": "600519",
            }
        ],
        "columns": [{"column_code": "010301", "column_name": "定期报告"}],
        "display_time": "2026-09-22 10:00:00",
        "eiTime": "2026-09-22 10:00:00",
        "language": "0",
        "listing_state": "1",
        "notice_date": "2026-09-22",
        "product_code": "600519",
        "sort_date": "2026-09-22 10:00:00",
        "source_type": "公告",
        "title": f"Disclosure {document_id}",
        "title_ch": f"公告 {document_id}",
        "title_en": f"Disclosure {document_id}",
    }
    if extra:
        row["financial_report"] = {"period": "2026H1"}
    return row


def _document(rows: list[object], **updates: object) -> dict[str, object]:
    data: dict[str, object] = {
        "list": rows,
        "page_index": 1,
        "page_size": 20,
        "total_hits": len(rows),
    }
    data.update(updates.pop("data", {}))
    document: dict[str, object] = {"data": data, "error": "", "success": 1}
    document.update(updates)
    return document


def _provider(rows: list[object], **updates: object) -> EastmoneyDisclosureProvider:
    return EastmoneyDisclosureProvider(
        FakeTransport(_document(rows, **updates)),
        clock=lambda: datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
    )


def test_disclosure_search_accepts_extra_top_level_row_fields_and_to_dicts_hides_them():
    provider = _provider([_row("202609221235"), _row("202609221236", extra=True)])
    client = FinchX(collector=Collector(provider_instances={"eastmoney.disclosure": provider}))

    result = client.disclosure.search("600519", provider="eastmoney.disclosure")
    rows = result.to_dicts()

    assert result.provider == "eastmoney.disclosure"
    assert len(result.data) == 2
    assert len(rows) == 2
    assert all("financial_report" not in row for row in rows)
    assert all("sourceRecordedAt" not in row for row in rows)
    time_metadata = next(
        item for item in result.data[0].provenance.adjustments
        if item.name == "eastmoney-disclosure-time-semantics"
    )
    assert time_metadata.details["sourceRecordedAtBasis"] == "EastMoney internal record time"


def test_disclosure_list_still_requires_existing_top_level_fields():
    row = _row()
    row.pop("title")
    provider = _provider([row])

    with pytest.raises(ProviderError, match="disclosure row 0 fields drifted"):
        provider.fetch_raw_disclosure_page(DisclosureSearchRequest(instrumentId=_instrument()))


def test_disclosure_list_still_validates_existing_field_values():
    row = _row()
    row["art_code"] = "not-an-eastmoney-id"
    provider = _provider([row])

    with pytest.raises(ProviderError, match="row 0 has an invalid art_code"):
        provider.fetch_raw_disclosure_page(DisclosureSearchRequest(instrumentId=_instrument()))


def test_disclosure_list_keeps_nested_codes_and_columns_strict():
    row = _row()
    row["codes"][0]["new_field"] = "not allowed"
    provider = _provider([row])

    with pytest.raises(ProviderError, match=r"row 0\.codes\[0\] fields drifted"):
        provider.fetch_raw_disclosure_page(DisclosureSearchRequest(instrumentId=_instrument()))


def test_disclosure_search_rejects_bare_category_string_and_empty_categories():
    client = FinchX()
    with pytest.raises(TypeError, match="sequence of category names"):
        client.disclosure.search("600519", categories="年报")
    with pytest.raises(ValueError, match="at least one category"):
        client.disclosure.search("600519", categories=[])


def _provider_row(document_id: str, published_at: datetime, *, captured_at=None) -> _ProviderDisclosureRow:
    return _ProviderDisclosureRow(
        document_id=document_id,
        title=f"Disclosure {document_id}",
        notice_date=published_at.date(),
        published_candidate=published_at,
        display_time=published_at,
        ei_time=published_at,
        sort_date=published_at,
        categories=(_ProviderDisclosureCategory("annual", "年报"),),
        securities=(_ProviderDisclosureSecurity(_instrument(), "贵州茅台", "A", "123456"),),
        source_type="公告",
        content_text=None,
        attachments=(),
        source_url="https://eastmoney.example/disclosure-list?page=1",
        captured_at=captured_at or datetime(2026, 9, 23, tzinfo=timezone.utc),
    )


def test_disclosure_date_search_scans_pages_and_stops_at_verified_old_page():
    provider = _provider([])
    pages = {
        1: (
            _provider_row("AN202609231101", datetime(2026, 9, 23, 10, tzinfo=timezone.utc)),
            _provider_row("AN202609221101", datetime(2026, 9, 22, 10, tzinfo=timezone.utc)),
        ),
        2: (
            _provider_row("AN202609201101", datetime(2026, 9, 20, 10, tzinfo=timezone.utc)),
            _provider_row("AN202609191101", datetime(2026, 9, 19, 10, tzinfo=timezone.utc)),
        ),
        3: (
            _provider_row("AN202609171101", datetime(2026, 9, 17, 10, tzinfo=timezone.utc)),
            _provider_row("AN202609161101", datetime(2026, 9, 16, 10, tzinfo=timezone.utc)),
        ),
    }
    calls = []

    def fetch_page(self, request):
        calls.append(request.page)
        return _ProviderDocumentPage(
            pages[request.page], request.page, request.page_size, 8,
            f"https://eastmoney.example/disclosure-list?page={request.page}",
        )

    provider.fetch_raw_disclosure_page = MethodType(fetch_page, provider)
    outcome = DisclosureService(provider=provider)._search_request_with_warnings(
        DisclosureSearchRequest(
            instrumentId=_instrument(),
            pageSize=2,
            since=date(2026, 9, 20),
        )
    )

    assert calls == [1, 2, 3]
    assert [item.source_document_id for item in outcome.records] == [
        "AN202609231101",
        "AN202609221101",
        "AN202609201101",
    ]
    assert outcome.warnings == ()


def test_disclosure_date_search_warns_at_page_cap_and_moves_source_time_to_provenance():
    provider = _provider([])
    calls = []
    base = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)

    def fetch_page(self, request):
        calls.append(request.page)
        row = _provider_row(
            f"AN20260923{request.page:04d}",
            base - timedelta(days=request.page - 1),
        )
        return _ProviderDocumentPage(
            (row,), request.page, request.page_size, 100,
            f"https://eastmoney.example/disclosure-list?page={request.page}",
        )

    provider.fetch_raw_disclosure_page = MethodType(fetch_page, provider)
    outcome = DisclosureService(provider=provider)._search_request_with_warnings(
        DisclosureSearchRequest(
            instrumentId=_instrument(),
            pageSize=1,
            since=date(2026, 1, 1),
        )
    )

    assert calls == list(range(1, 51))
    assert len(outcome.records) == 50
    assert any("stopped after 50 pages" in warning and "incomplete" in warning for warning in outcome.warnings)

    ref = outcome.records[0]
    assert "sourceRecordedAt" not in ref.model_dump(by_alias=True)
    adjustment = next(item for item in ref.provenance.adjustments if item.name == "eastmoney-disclosure-time-semantics")
    assert adjustment.details["sourceRecordedAt"] == base.isoformat()
    fresh_capture = datetime(2026, 9, 24, 2, tzinfo=timezone.utc)
    detail_record = normalize_disclosure_document(
        ref,
        replace(
            _provider_row(ref.source_document_id, base),
            captured_at=fresh_capture,
        ),
        source=provider.source,
    )
    assert detail_record.captured_at == fresh_capture
    assert "sourceRecordedAt" not in detail_record.data
