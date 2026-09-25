from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from types import MethodType, SimpleNamespace

import pytest

from finchx import FinchX
from finchx.collector import Collector
from finchx.datasets import NewsSearchRequest
from finchx.datasets.news import _ProviderNewsRow
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.eastmoney_documents import EastmoneyNewsProvider, _ProviderDocumentPage
from finchx.providers.errors import ProviderError
from finchx.query.documents import NewsService


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


def _row(document_id: str, *, extra: bool = False) -> dict[str, str]:
    row = {
        "Art_ShowTime": "2026-09-22 10:00:00",
        "Art_Code": document_id,
        "Np_dst": "0",
        "Art_Title": f"News {document_id}",
        "Art_SortStart": "20260922100000",
        "Art_OriginUrl": f"https://finance.eastmoney.com/a/{document_id}.html",
        "Art_Url": f"https://finance.eastmoney.com/a/{document_id}.html",
    }
    if extra:
        row["New_Optional_Field"] = "forward-compatible"
    return row


def _document(rows: list[object], **updates: object) -> dict[str, object]:
    data: dict[str, object] = {
        "page_index": 1,
        "totle_hits": len(rows),
        "list": rows,
        "page_size": 20,
    }
    data.update(updates.pop("data", {}))
    document: dict[str, object] = {
        "code": 1,
        "message": "ok",
        "data": data,
    }
    document.update(updates)
    return document


def _provider(rows: list[object], **updates: object) -> EastmoneyNewsProvider:
    return EastmoneyNewsProvider(
        FakeTransport(_document(rows, **updates)),
        clock=lambda: datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
    )


def test_one_drifted_row_is_skipped_and_warning_reaches_fetch_result():
    drifted = {"Art_Code": "202609221234"}
    forward_compatible = _row("202609221235", extra=True)
    for optional_field in ("Np_dst", "Art_SortStart", "Art_OriginUrl"):
        forward_compatible.pop(optional_field)
    provider = _provider([forward_compatible, drifted, _row("202609221236")])
    client = FinchX(collector=Collector(provider_instances={"eastmoney.news": provider}))

    result = client.news.search("600519", provider="eastmoney.news")

    assert len(result.data) == 2
    assert [item.source_document_id for item in result.data] == [
        "202609221235",
        "202609221236",
    ]
    assert len(result.warnings) == 1
    assert "row 1" in result.warnings[0]
    assert "required fields missing" in result.warnings[0]


def test_multiple_drifted_rows_still_return_the_parseable_rows():
    provider = _provider([
        {"Art_Code": "202609221234"},
        _row("202609221235"),
        {"Art_ShowTime": "bad"},
        _row("202609221236"),
    ])
    client = FinchX(collector=Collector(provider_instances={"eastmoney.news": provider}))

    result = client.news.search("600519", provider="eastmoney.news")

    assert len(result.data) == 2
    assert len(result.warnings) == 2
    assert all("Skipped EastMoney news row" in warning for warning in result.warnings)


def test_top_level_schema_drift_remains_provider_error():
    provider = _provider([_row("202609221235")], unexpected="top-level")
    request = NewsSearchRequest(instrumentId=_instrument())

    with pytest.raises(ProviderError, match="news list root fields drifted"):
        provider.fetch_raw_news_page(request)


def test_all_rows_drifted_remains_provider_error():
    provider = _provider([{"Art_Code": "202609221234"}, "not-a-row"])
    request = NewsSearchRequest(instrumentId=_instrument())

    with pytest.raises(ProviderError, match="no parseable rows"):
        provider.fetch_raw_news_page(request)


def _provider_row(
    document_id: str,
    published_at: datetime,
    *,
    captured_at: datetime | None = None,
) -> _ProviderNewsRow:
    return _ProviderNewsRow(
        instrument_id=_instrument(),
        document_id=document_id,
        title=f"News {document_id}",
        important=None,
        published_at=published_at,
        url=f"https://finance.eastmoney.com/a/{document_id}.html",
        original_url=None,
        source_name=None,
        content_text=None,
        source_url="https://eastmoney.example/news-list?page=1",
        captured_at=captured_at or datetime(2026, 9, 23, tzinfo=timezone.utc),
    )


def test_news_date_search_scans_pages_and_stops_at_verified_old_page():
    provider = _provider([])
    pages = {
        1: (
            _provider_row("202609231101", datetime(2026, 9, 23, 10, tzinfo=timezone.utc)),
            _provider_row("202609221101", datetime(2026, 9, 22, 10, tzinfo=timezone.utc)),
        ),
        2: (
            _provider_row("202609201101", datetime(2026, 9, 20, 10, tzinfo=timezone.utc)),
            _provider_row("202609191101", datetime(2026, 9, 19, 10, tzinfo=timezone.utc)),
        ),
        3: (
            _provider_row("202609171101", datetime(2026, 9, 17, 10, tzinfo=timezone.utc)),
            _provider_row("202609161101", datetime(2026, 9, 16, 10, tzinfo=timezone.utc)),
        ),
    }
    calls = []

    def fetch_page(self, request):
        calls.append(request.page)
        return _ProviderDocumentPage(
            pages[request.page],
            request.page,
            request.page_size,
            8,
            f"https://eastmoney.example/news-list?page={request.page}",
        )

    provider.fetch_raw_news_page = MethodType(fetch_page, provider)
    request = NewsSearchRequest(
        instrumentId=_instrument(),
        pageSize=2,
        since=date(2026, 9, 20),
    )

    result = NewsService(provider=provider)._search_request_with_warnings(request)

    assert calls == [1, 2, 3]
    assert [item.source_document_id for item in result.records] == [
        "202609231101",
        "202609221101",
        "202609201101",
    ]
    assert result.warnings == ()


def test_news_date_search_warns_when_bounded_page_limit_may_hide_matches():
    provider = _provider([])
    calls = []
    base = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)

    def fetch_page(self, request):
        calls.append(request.page)
        document_id = f"20260923{request.page:04d}"
        row = _provider_row(
            document_id,
            base - timedelta(days=request.page - 1),
        )
        return _ProviderDocumentPage(
            (row,), request.page, request.page_size, 100,
            f"https://eastmoney.example/news-list?page={request.page}",
        )

    provider.fetch_raw_news_page = MethodType(fetch_page, provider)
    outcome = NewsService(provider=provider)._search_request_with_warnings(
        NewsSearchRequest(instrumentId=_instrument(), pageSize=1, since=date(2026, 1, 1))
    )

    assert calls == list(range(1, 51))
    assert len(outcome.records) == 50
    assert any("stopped after 50 pages" in warning and "incomplete" in warning for warning in outcome.warnings)


def test_news_source_url_is_query_page_document_url_is_article_and_detail_uses_fresh_capture():
    provider = _provider([])
    listed = _provider_row("202609231101", datetime(2026, 9, 23, 10, tzinfo=timezone.utc))

    def fetch_page(self, request):
        return _ProviderDocumentPage(
            (listed,), request.page, request.page_size, 1,
            "https://eastmoney.example/news-list?page=1",
        )

    provider.fetch_raw_news_page = MethodType(fetch_page, provider)
    ref = NewsService(provider=provider)._search_request(
        NewsSearchRequest(instrumentId=_instrument())
    )[0]
    assert str(ref.source_url) == "https://eastmoney.example/news-list?page=1"
    assert str(ref.document_url) == listed.url

    detail_capture = datetime(2026, 9, 24, 2, tzinfo=timezone.utc)
    detail_row = _ProviderNewsRow(
        instrument_id=None,
        document_id=listed.document_id,
        title=listed.title,
        important=listed.important,
        published_at=listed.published_at,
        url=listed.url,
        original_url=None,
        source_name="EastMoney",
        content_text="Complete story",
        source_url=ref.source_url.__str__(),
        captured_at=detail_capture,
    )
    provider.fetch_content = lambda _document_id: detail_row

    detail = NewsService(provider=provider).get_document(ref)

    assert detail.data.captured_at == detail_capture
    assert detail.to_dicts()[0]["url"] == listed.url
    assert detail.to_dicts()[0]["contentText"] == "Complete story"
