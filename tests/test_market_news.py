from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from finchx import FinchX
from finchx.collectors import FetchResult
from finchx.contracts import Source
from finchx.datasets import NEWS_DOCUMENT_DATASET, MarketNewsSearchRequest
from finchx.datasets.news import _ProviderNewsRow
from finchx.providers.eastmoney_documents import _ProviderDocumentPage
from finchx.providers.errors import ProviderError
from finchx.providers.market_news import (
    BAIDU_FINSCOPE_ENDPOINT,
    AigupiaoMarketNewsProvider,
    BaiduFinscopeMarketNewsProvider,
)
from finchx.query.market_news import MarketNewsService


CAPTURED_AT = datetime(2026, 9, 23, 8, tzinfo=timezone.utc)


class FakeBaiduTransport:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.document = {
            "QueryID": "query-1",
            "ResultCode": "0",
            "Result": {"content": {"list": rows}},
        }

    def get(self, _url, *, params, headers, timeout_seconds):
        self.calls.append((_url, dict(params)))
        return SimpleNamespace(status_code=200, text=json.dumps(self.document))


class FakeAigupiaoTransport:
    def __init__(self, rows: list[dict[str, object]], details: dict[str, str] | None = None) -> None:
        self.details = details or {}
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.document = {
            "rslt": "succ",
            "data": {"2026-09-23-3": {"title": "2026-09-23", "data": rows}},
            "last_time": 0,
            "date_time": "2026-09-23 08:00:00",
        }

    def get(self, _url, *, params, headers, timeout_seconds):
        self.calls.append((_url, dict(params)))
        if _url in self.details:
            return SimpleNamespace(status_code=200, text=self.details[_url])
        return SimpleNamespace(status_code=200, text=json.dumps(self.document))


def _baidu_row(
    document_id: str,
    *,
    title: object = "Source title",
    include_title: bool = True,
    body: str = "Baidu source body",
    extra: bool = False,
) -> dict[str, object]:
    row: dict[str, object] = {
        "loc": f"loc-{document_id}",
        "content": {"items": [{"type": "text", "data": body}]},
        "publish_time": 1780000000,
        "important": "0",
        "entity": [],
    }
    if include_title:
        row["title"] = title
    if extra:
        row["important"] = "1"
        row["tag"] = "forward-compatible"
        row["evaluate"] = {"score": 1}
    return row


def _baidu_provider(rows: list[dict[str, object]]) -> BaiduFinscopeMarketNewsProvider:
    return BaiduFinscopeMarketNewsProvider(
        FakeBaiduTransport(rows),
        clock=lambda: CAPTURED_AT,
    )


def _baidu_page(provider: BaiduFinscopeMarketNewsProvider):
    return provider.fetch_raw_news_page(MarketNewsSearchRequest(pageSize=20))


def _aigupiao_row(document_id: str, *, important: object = "no") -> dict[str, object]:
    return {
        "id": int(document_id) if document_id.isdigit() else 1550000,
        "content": f"Aigupiao body {document_id}",
        "web_content": f"【Aigupiao title {document_id}】Aigupiao body {document_id}",
        "rec_time": "1780000000",
        "url": f"https://www.aigupiao.com/express/{document_id}",
        "important": important,
        "stock_infos": [],
    }


def _aigupiao_provider(
    rows: list[dict[str, object]],
    *,
    details: dict[str, str] | None = None,
) -> AigupiaoMarketNewsProvider:
    return AigupiaoMarketNewsProvider(
        FakeAigupiaoTransport(rows, details),
        clock=lambda: CAPTURED_AT,
    )


def test_aigupiao_provider_normalizes_yes_no_importance_to_boolean():
    page = _aigupiao_provider([
        _aigupiao_row("1550001", important="yes"),
        _aigupiao_row("1550002", important="no"),
    ]).fetch_raw_news_page(MarketNewsSearchRequest(pageSize=20))

    assert [row.important for row in page.rows] == [True, False]


@pytest.mark.parametrize("important", ["", "maybe", None, 1])
def test_aigupiao_provider_rejects_unknown_importance_markers(important: object):
    with pytest.raises(ProviderError, match="Aigupiao.important"):
        _aigupiao_provider([_aigupiao_row("1550003", important=important)]).fetch_raw_news_page(
            MarketNewsSearchRequest(pageSize=20)
        )


def _aigupiao_detail_html(payload: object) -> str:
    return (
        "<html><head><style>.客服{display:none}</style>"
        "<script>var _Libs = {}; function noisy() { return true; }</script></head>"
        "<body><nav>导航</nav><div class='comment'>评论</div>"
        "var rslt_content = "
        + json.dumps(payload, ensure_ascii=False)
        + ";<section>客服 加载中</section><script>var page_json = {}; </script></body></html>"
    )


def _aigupiao_detail_provider(payload: object, document_id: str = "1550001") -> AigupiaoMarketNewsProvider:
    row = _aigupiao_row(document_id)
    url = str(row["url"])
    return _aigupiao_provider(
        [row],
        details={url: _aigupiao_detail_html(payload)},
    )


def test_aigupiao_detail_uses_structured_payload_and_keeps_link_text_only():
    provider = _aigupiao_detail_provider({
        "id": "1550001",
        "title": "Structured title",
            "content": '正文 <a href="https://example.com">链接文字</a><br>包含 { 花括号 }; 和转义字符 "x"。',
    })
    row = _aigupiao_row("1550001")

    detail = provider.fetch_content("1550001", document_url=str(row["url"]))

    assert detail.title == "Structured title"
    assert detail.content_text == '正文 链接文字\n包含 { 花括号 }; 和转义字符 "x"。'
    assert all(noise not in (detail.content_text or "") for noise in (
        "var _Libs", "rslt_content", "<script", "function(", "导航", "评论", "客服", "加载中",
    ))


@pytest.mark.parametrize(
    "html",
    [
        "<html>正文但没有 payload</html>",
        "<html>var rslt_content = {not-json};</html>",
        "<html>var rslt_content = [1, 2];</html>",
    ],
)
def test_aigupiao_detail_rejects_missing_or_malformed_payload(html: str):
    row = _aigupiao_row("1550001")
    provider = _aigupiao_provider([row], details={str(row["url"]): html})

    with pytest.raises(ProviderError, match="rslt_content"):
        provider.fetch_content("1550001", document_url=str(row["url"]))


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "Title", "content": "body"},
        {"id": "other", "title": "Title", "content": "body"},
        {"id": "1550001", "title": "Title"},
        {"id": "1550001", "title": "Title", "content": ""},
        {"id": "1550001", "title": "Title", "content": None},
    ],
)
def test_aigupiao_detail_rejects_invalid_identity_or_content(payload: dict[str, object]):
    provider = _aigupiao_detail_provider(payload)
    row = _aigupiao_row("1550001")

    with pytest.raises(ProviderError):
        provider.fetch_content("1550001", document_url=str(row["url"]))


def test_aigupiao_detail_derives_title_only_when_payload_title_is_invalid():
    provider = _aigupiao_detail_provider({
        "id": "1550001",
        "title": None,
        "content": "正文标题来源",
    })
    row = _aigupiao_row("1550001")

    detail = provider.fetch_content("1550001", document_url=str(row["url"]))

    assert detail.title == "正文标题来源"
    assert detail.title_derived is True


def test_default_market_news_service_uses_only_aigupiao_and_baidu():
    service = MarketNewsService()

    assert [provider.provider_id for provider in service.providers] == [
        "aigupiao.market_news",
        "baidu.finscope.market_news",
    ]


def test_baidu_provider_derives_title_only_when_title_key_is_missing():
    body = "  <b>" + ("Derived title " * 10) + "</b>  "
    row = _baidu_page(_baidu_provider([_baidu_row("missing", include_title=False, body=body)])).rows[0]

    assert row.title == ("Derived title " * 10).strip()[:80]
    assert row.title_derived is True


def test_baidu_provider_keeps_source_title_and_mixed_page_order():
    page = _baidu_page(
        _baidu_provider([
            _baidu_row("with-title", title="Source headline"),
            _baidu_row("without-title", include_title=False, body="Derived headline body"),
        ])
    )

    assert [row.document_id for row in page.rows] == ["loc-with-title", "loc-without-title"]
    assert page.rows[0].title == "Source headline"
    assert page.rows[0].title_derived is False
    assert page.rows[1].title == "Derived headline body"
    assert page.rows[1].title_derived is True


def test_baidu_provider_preserves_strict_required_fields_and_unknown_fields():
    page = _baidu_page(_baidu_provider([_baidu_row("extra", extra=True)]))

    assert len(page.rows) == 1
    result = _service(
        _BaiduServiceProvider(_baidu_provider([_baidu_row("extra", extra=True)]))
    ).search_result()
    public_row = result.to_dicts()[0]
    assert public_row["title"] == "Source title"
    assert "title_derived" not in public_row
    assert public_row["important"] is True


@pytest.mark.parametrize("important", ["", "maybe", None, 1])
def test_baidu_provider_rejects_unknown_importance_markers(important: object):
    row = _baidu_row("invalid-importance")
    row["important"] = important

    with pytest.raises(ProviderError, match="Baidu.important"):
        _baidu_page(_baidu_provider([row]))


class _BaiduServiceProvider:
    def __init__(self, provider: BaiduFinscopeMarketNewsProvider) -> None:
        self._provider = provider
        self.provider_id = provider.provider_id

    @property
    def source(self) -> Source:
        return self._provider.source

    def fetch_raw_news_page(self, request):
        return self._provider.fetch_raw_news_page(request)

    def fetch_content(
        self,
        document_id: str,
        *,
        document_url: str | None = None,
        source_page_url: str | None = None,
    ) -> _ProviderNewsRow:
        return self._provider.fetch_content(
            document_id,
            document_url=document_url,
            source_page_url=source_page_url,
        )


def _baidu_source_page_url(*, rn: object = 20, pn: object = 0) -> str:
    return f"{BAIDU_FINSCOPE_ENDPOINT}?rn={rn}&pn={pn}&tag=&filterByUserStocks=0&finClientType=pc"


def test_baidu_detail_reuses_source_search_page_and_never_requests_document_url():
    transport = FakeBaiduTransport([_baidu_row("target", body="Baidu clean body")])
    provider = BaiduFinscopeMarketNewsProvider(transport, clock=lambda: CAPTURED_AT)
    row = _baidu_page(provider).rows[0]

    detail = provider.fetch_content(
        row.document_id,
        document_url="http://live.financebe.com/stock/detail.html?d=target",
        source_page_url=_baidu_source_page_url(),
    )

    assert detail.content_text == "Baidu clean body"
    assert all(url == BAIDU_FINSCOPE_ENDPOINT for url, _ in transport.calls)
    assert not any("live.financebe.com" in url for url, _ in transport.calls)


@pytest.mark.parametrize(
    "source_page_url",
    [
        None,
        "https://example.com/selfselect/expressnews?rn=20&pn=0",
        f"{BAIDU_FINSCOPE_ENDPOINT}?rn=20&rn=10&pn=0",
        f"{BAIDU_FINSCOPE_ENDPOINT}?rn=0&pn=0",
        f"{BAIDU_FINSCOPE_ENDPOINT}?rn=21&pn=0",
        f"{BAIDU_FINSCOPE_ENDPOINT}?rn=20&pn=-1",
        f"{BAIDU_FINSCOPE_ENDPOINT}?rn=bad&pn=0",
    ],
)
def test_baidu_detail_rejects_untrusted_or_invalid_source_page_url(source_page_url: str | None):
    provider = BaiduFinscopeMarketNewsProvider(
        FakeBaiduTransport([_baidu_row("target")]),
        clock=lambda: CAPTURED_AT,
    )

    with pytest.raises(ProviderError, match="Baidu detail"):
        provider.fetch_content(
            "loc-target",
            document_url="http://live.financebe.com/stock/detail.html?d=target",
            source_page_url=source_page_url,
        )


def test_baidu_detail_rejects_target_missing_from_source_page():
    provider = BaiduFinscopeMarketNewsProvider(
        FakeBaiduTransport([_baidu_row("other")]),
        clock=lambda: CAPTURED_AT,
    )

    with pytest.raises(ProviderError, match="was not found"):
        provider.fetch_content("loc-target", source_page_url=_baidu_source_page_url())


def _assert_clean_detail_rows(result: FetchResult, expected_ids: list[str]) -> None:
    rows = result.to_dicts()
    assert [row["sourceDocumentId"] for row in rows] == expected_ids
    assert [record.data["contentText"] for record in result.data] == [row["contentText"] for row in rows]
    for row in rows:
        content = row["contentText"] or ""
        assert all(noise not in content for noise in (
            "var _Libs", "rslt_content", "<script", "function(", "导航", "评论", "客服", "加载中",
        ))


def test_aigupiao_service_single_and_same_provider_batch_details_are_clean_and_ordered():
    raw_rows = [_aigupiao_row("1550001"), _aigupiao_row("1550002")]
    details = {
        str(row["url"]): _aigupiao_detail_html({
            "id": str(row["id"]),
            "title": f"Title {row['id']}",
            "content": f"Aigupiao clean {row['id']} <a href='https://example.com'>link</a>",
        })
        for row in raw_rows
    }
    service = MarketNewsService([_aigupiao_provider(raw_rows, details=details)])
    search_result = service.search_result(max_results=2)

    single = service.get_document(search_result.data[0])
    batch = service.get_documents(search_result.data[::-1])

    assert single.provider == "aigupiao.market_news"
    assert single.provenance[0].provider_id == "aigupiao.market_news"
    single_id = search_result.data[0].source_document_id
    assert single.to_dicts()[0]["contentText"] == f"Aigupiao clean {single_id} link"
    _assert_clean_detail_rows(batch, [ref.source_document_id for ref in search_result.data[::-1]])
    assert batch.provider == "aigupiao.market_news"


def test_baidu_service_single_and_same_provider_batch_details_are_clean_and_ordered():
    raw_rows = [
        _baidu_row("one", body="Baidu clean one"),
        _baidu_row("two", body="Baidu clean two", include_title=False),
    ]
    transport = FakeBaiduTransport(raw_rows)
    provider = BaiduFinscopeMarketNewsProvider(transport, clock=lambda: CAPTURED_AT)
    service = MarketNewsService([provider])
    search_result = service.search_result(max_results=2)

    single = service.get_document(search_result.data[0])
    batch = service.get_documents(search_result.data[::-1])

    assert single.provider == "baidu.finscope.market_news"
    single_id = search_result.data[0].source_document_id.removeprefix("loc-")
    assert single.to_dicts()[0]["contentText"] == f"Baidu clean {single_id}"
    _assert_clean_detail_rows(batch, [ref.source_document_id for ref in search_result.data[::-1]])
    assert batch.provider == "baidu.finscope.market_news"
    assert all(url == BAIDU_FINSCOPE_ENDPOINT for url, _ in transport.calls)


def test_mixed_provider_batch_details_keep_input_order_and_metadata():
    aig_row = _aigupiao_row("1550003")
    aig = _aigupiao_provider(
        [aig_row],
        details={str(aig_row["url"]): _aigupiao_detail_html({
            "id": "1550003",
            "title": "Aigupiao title",
            "content": "Aigupiao mixed clean",
        })},
    )
    baidu = BaiduFinscopeMarketNewsProvider(
        FakeBaiduTransport([_baidu_row("mixed", body="Baidu mixed clean")]),
        clock=lambda: CAPTURED_AT,
    )
    service = MarketNewsService([aig, baidu])
    search_result = service.search_result(max_results=2)
    detail_result = service.get_documents(search_result.data)

    assert detail_result.provider is None
    assert {source.provider_id for source in detail_result.provenance} == {
        "aigupiao.market_news",
        "baidu.finscope.market_news",
    }
    assert [record.source.provider_id for record in detail_result.data] == [
        ref.source.provider_id for ref in search_result.data
    ]
    _assert_clean_detail_rows(detail_result, [ref.source_document_id for ref in search_result.data])


@pytest.mark.parametrize("missing", ["loc", "content", "publish_time", "entity"])
def test_baidu_provider_still_rejects_missing_required_fields(missing: str):
    row = _baidu_row("missing-required")
    row.pop(missing)

    with pytest.raises(ProviderError, match="row fields drifted"):
        _baidu_page(_baidu_provider([row]))


@pytest.mark.parametrize("title", ["", None, 123])
def test_baidu_provider_rejects_present_invalid_titles(title: object):
    with pytest.raises(ValueError, match="Baidu.title"):
        _baidu_page(_baidu_provider([_baidu_row("invalid-title", title=title)]))


@pytest.mark.parametrize(
    "content",
    [
        {},
        {"items": "not-a-list"},
        {"items": [{"type": "image", "data": "not text"}]},
        {"items": [{"type": "text", "data": ""}]},
    ],
)
def test_baidu_provider_keeps_content_items_strict(content: object):
    row = _baidu_row("invalid-content")
    row["content"] = content

    with pytest.raises(ProviderError):
        _baidu_page(_baidu_provider([row]))


def test_baidu_service_result_exposes_derived_title_and_existing_adjustment():
    result = _service(
        _BaiduServiceProvider(
            _baidu_provider([
                _baidu_row("missing", include_title=False, body="Derived title from body"),
                _baidu_row("normal", title="Normal source title"),
            ])
        )
    ).search_result()

    assert [ref.title for ref in result.data] == ["Normal source title", "Derived title from body"]
    derived = next(ref for ref in result.data if ref.source_document_id == "loc-missing")
    normal = next(ref for ref in result.data if ref.source_document_id == "loc-normal")
    assert [item.name for item in derived.provenance.adjustments] == [
        "title-derived-from-source-content"
    ]
    assert normal.provenance.adjustments == []
    assert [row["title"] for row in result.to_dicts()] == [
        "Normal source title",
        "Derived title from body",
    ]


class FakeMarketNewsProvider:
    def __init__(self, provider_id: str, rows: tuple[_ProviderNewsRow, ...]) -> None:
        self.provider_id = provider_id
        self._rows = rows
        self._source = Source(providerId=provider_id, sourceUrl=f"https://{provider_id}.example/news")

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_news_page(self, request):
        return _ProviderDocumentPage(
            self._rows,
            request.page,
            request.page_size,
            len(self._rows),
            str(self._source.source_url),
        )

    def fetch_content(
        self,
        document_id: str,
        *,
        document_url: str | None = None,
        source_page_url: str | None = None,
    ) -> _ProviderNewsRow:
        return next(row for row in self._rows if row.document_id == document_id)


class PagedMarketNewsProvider(FakeMarketNewsProvider):
    def __init__(self, provider_id: str, pages: dict[int, tuple[_ProviderNewsRow, ...]], *, total_hits: int) -> None:
        all_rows = tuple(row for page_rows in pages.values() for row in page_rows)
        super().__init__(provider_id, all_rows)
        self.pages = pages
        self.total_hits = total_hits

    def fetch_raw_news_page(self, request):
        rows = self.pages.get(request.page, ())
        return _ProviderDocumentPage(
            rows,
            request.page,
            request.page_size,
            self.total_hits,
            str(self.source.source_url),
            has_more=request.page * request.page_size < self.total_hits,
        )


def _row(
    provider_id: str,
    document_id: str,
    *,
    published_at: datetime,
    captured_at: datetime = CAPTURED_AT,
    title: str | None = None,
    content: str | None = None,
    important: bool | None = None,
) -> _ProviderNewsRow:
    url = f"https://{provider_id}.example/news/{document_id}"
    return _ProviderNewsRow(
        instrument_id=None,
        document_id=document_id,
        title=title or f"News {document_id}",
        published_at=published_at,
        url=url,
        original_url=None,
        source_name=provider_id,
        content_text=content or f"Body {document_id}",
        source_url=url,
        captured_at=captured_at,
        important=important,
        public_document_id=f"{provider_id}:market_news:{document_id}",
    )


def _service(*providers: FakeMarketNewsProvider) -> MarketNewsService:
    return MarketNewsService(providers)


def test_market_news_search_result_wraps_single_provider_refs_with_metadata():
    first_time = CAPTURED_AT - timedelta(hours=1)
    latest_time = CAPTURED_AT + timedelta(minutes=1)
    provider = FakeMarketNewsProvider(
        "fake.one",
        (
            _row("fake.one", "one", published_at=latest_time, captured_at=first_time),
            _row("fake.one", "two", published_at=first_time, captured_at=latest_time),
        ),
    )

    result = _service(provider).search_result()

    assert isinstance(result, FetchResult)
    assert isinstance(result.data, tuple)
    assert result.dataset is NEWS_DOCUMENT_DATASET
    assert result.provider == "fake.one"
    assert result.captured_at == latest_time
    assert result.provenance == tuple(ref.source for ref in result.data)
    assert result.warnings == ()
    assert result.attempts == ()
    assert result.fallback_used is False
    assert result.cache_hit is False
    assert len(result.to_dicts()) == len(result.data) == 2


def test_market_news_search_result_keeps_unified_importance_across_providers():
    published_at = CAPTURED_AT - timedelta(minutes=1)
    result = _service(
        FakeMarketNewsProvider(
            "aigupiao.market_news",
            (_row("aigupiao.market_news", "important", published_at=published_at, important=True),),
        ),
        FakeMarketNewsProvider(
            "baidu.finscope.market_news",
            (_row("baidu.finscope.market_news", "ordinary", published_at=published_at, important=False),),
        ),
    ).search_result()

    assert {ref.important for ref in result.data} == {True, False}
    assert {row["important"] for row in result.to_dicts()} == {True, False}


def test_market_news_date_search_scans_pages_and_stops_at_verified_old_page():
    pages = {
        1: (
            _row("fake.one", "one", published_at=datetime(2026, 9, 23, 10, tzinfo=timezone.utc)),
            _row("fake.one", "two", published_at=datetime(2026, 9, 22, 10, tzinfo=timezone.utc)),
        ),
        2: (
            _row("fake.one", "three", published_at=datetime(2026, 9, 20, 10, tzinfo=timezone.utc)),
            _row("fake.one", "four", published_at=datetime(2026, 9, 19, 10, tzinfo=timezone.utc)),
        ),
        3: (
            _row("fake.one", "five", published_at=datetime(2026, 9, 17, 10, tzinfo=timezone.utc)),
            _row("fake.one", "six", published_at=datetime(2026, 9, 16, 10, tzinfo=timezone.utc)),
        ),
    }
    provider = PagedMarketNewsProvider("fake.one", pages, total_hits=8)

    result = _service(provider).search_result(page_size=2, since="2026-09-20")

    assert [ref.source_document_id for ref in result.data] == ["one", "two", "three"]
    assert result.warnings == ()


def test_market_news_repeated_cursor_warns_that_search_may_be_incomplete():
    class RepeatingCursorProvider(FakeMarketNewsProvider):
        def __init__(self):
            super().__init__(
                "fake.cursor",
                (
                    _row("fake.cursor", "newer", published_at=datetime(2026, 9, 23, 10, tzinfo=timezone.utc)),
                    _row("fake.cursor", "older", published_at=datetime(2026, 9, 22, 10, tzinfo=timezone.utc)),
                ),
            )
            self.calls = 0

        def fetch_raw_news_page(self, request):
            row = self._rows[self.calls]
            self.calls += 1
            return _ProviderDocumentPage(
                (row,),
                request.page,
                request.page_size,
                None,
                str(self.source.source_url),
                next_page_token="same-cursor",
                has_more=True,
            )

    provider = RepeatingCursorProvider()
    result = _service(provider).search_result(page_size=1, since="2026-09-20")

    assert [ref.source_document_id for ref in result.data] == ["newer", "older"]
    assert provider.calls == 2
    assert any("cursor did not advance" in warning and "incomplete" in warning for warning in result.warnings)


def test_market_news_date_search_warns_when_page_limit_may_hide_matches():
    pages = {}
    base = CAPTURED_AT
    for page_index in range(1, 51):
        pages[page_index] = (
            _row(
                "fake.one",
                f"item-{page_index}",
                published_at=base - timedelta(days=page_index - 1),
            ),
        )
    provider = PagedMarketNewsProvider("fake.one", pages, total_hits=100)

    result = _service(provider).search_result(page_size=1, since="2026-01-01")

    assert len(result.data) == 50
    assert any("stopped after 50 pages" in warning and "incomplete" in warning for warning in result.warnings)


def test_market_news_search_result_marks_mixed_providers_as_ambiguous():
    published_at = CAPTURED_AT - timedelta(minutes=1)
    result = _service(
        FakeMarketNewsProvider("fake.one", (_row("fake.one", "one", published_at=published_at),)),
        FakeMarketNewsProvider("fake.two", (_row("fake.two", "two", published_at=published_at),)),
    ).search_result()

    assert result.provider is None
    assert {source.provider_id for source in result.provenance} == {"fake.one", "fake.two"}
    assert len(result.data) == 2


def test_market_news_dedup_keeps_occurrences_and_mixed_provider_metadata():
    published_at = CAPTURED_AT - timedelta(minutes=1)
    rows = (
        _row("fake.one", "one", published_at=published_at, title="Same", content="Same body"),
    )
    other_rows = (
        _row("fake.two", "two", published_at=published_at + timedelta(minutes=5), title="Same", content="Same body"),
    )

    result = _service(
        FakeMarketNewsProvider("fake.one", rows),
        FakeMarketNewsProvider("fake.two", other_rows),
    ).search_result()

    assert len(result.data) == 1
    assert {item.provider_id for item in result.data[0].source_occurrences} == {"fake.one", "fake.two"}
    assert {item.provider_id for item in result.data[0].provenance.source_references} == {"fake.one", "fake.two"}
    assert result.provider is None
    assert {source.provider_id for source in result.provenance} == {"fake.one", "fake.two"}
    assert {source.source_record_id for source in result.provenance} == {"one", "two"}


def test_market_news_empty_search_result_has_empty_tuple_and_timezone_aware_capture():
    result = _service(FakeMarketNewsProvider("fake.one", ())).search_result()

    assert result.data == ()
    assert result.provider is None
    assert result.captured_at.tzinfo is not None
    assert result.captured_at.utcoffset() is not None
    assert result.provenance == ()
    assert result.to_dicts() == []


def test_market_news_search_result_chains_into_single_and_batch_details():
    provider = FakeMarketNewsProvider(
        "fake.one",
        (_row("fake.one", "one", published_at=CAPTURED_AT, content="Complete body"),),
    )
    service = _service(provider)
    client = FinchX()
    client._market_news_service = service

    search_result = client.market_news.search(max_results=1)
    detail_result = client.market_news.get_document(search_result.data[0])
    details_result = client.market_news.get_documents(search_result.data)

    assert detail_result.to_dicts()[0]["contentText"] == "Complete body"
    assert len(details_result.to_dicts()) == 1
