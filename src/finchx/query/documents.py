"""Small public research-oriented query services for news and disclosures."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from finchx.contracts import StandardRecord
from finchx.datasets.disclosure import (
    DisclosureDocumentRef,
    DisclosureSearchRequest,
    normalize_disclosure_document,
    normalize_disclosure_search,
)
from finchx.datasets.document_common import matches_datetime_range, normalize_document_instrument
from finchx.datasets.news import NewsDocumentRef, NewsSearchRequest, normalize_news_document, normalize_news_search
from finchx.providers.eastmoney_documents import EastmoneyDisclosureProvider, EastmoneyNewsProvider


def _document_source_id(document_id: str, *, kind: str) -> str:
    prefix = f"eastmoney:{kind}:"
    if not isinstance(document_id, str) or not document_id.startswith(prefix):
        raise ValueError(f"documentId must use the {prefix} namespace")
    source_id = document_id[len(prefix):]
    if not source_id or ":" in source_id:
        raise ValueError("documentId contains an invalid source identifier")
    if kind == "news" and not source_id.isdigit():
        raise ValueError("news documentId contains an invalid Art_Code")
    if kind == "disclosure" and not source_id.startswith("AN"):
        raise ValueError("disclosure documentId contains an invalid art_code")
    return source_id


def _validate_document_ref(ref: Any, expected_type: type, *, kind: str, source: Any) -> str:
    if not isinstance(ref, expected_type):
        raise ValueError(f"ref must be a {expected_type.__name__}")
    if ref.source.provider_id != source.provider_id:
        raise ValueError("document ref provider does not match the configured provider")
    source_id = _document_source_id(ref.document_id, kind=kind)
    if source_id != ref.source_document_id:
        raise ValueError("document ref documentId/sourceDocumentId do not match")
    if ref.source.source_record_id not in (None, source_id):
        raise ValueError("document ref sourceRecordId does not match sourceDocumentId")
    return source_id


def _build_news_request(
    instrument: Any,
    *,
    page: int,
    page_size: int,
    max_results: int | None,
    since: Any,
    until: Any,
    sort: str,
) -> NewsSearchRequest:
    return NewsSearchRequest(
        instrumentId=normalize_document_instrument(instrument),
        page=page,
        pageSize=page_size,
        maxResults=max_results,
        since=since,
        until=until,
        sort=sort,
    )


def _build_disclosure_request(
    instrument: Any,
    *,
    page: int,
    page_size: int,
    max_results: int | None,
    since: Any,
    until: Any,
    sort: str,
    categories: list[str] | None,
) -> DisclosureSearchRequest:
    return DisclosureSearchRequest(
        instrumentId=normalize_document_instrument(instrument),
        page=page,
        pageSize=page_size,
        maxResults=max_results,
        since=since,
        until=until,
        sort=sort,
        categories=categories,
    )


class NewsService:
    """Search serializable news refs and fetch complete article text."""

    def __init__(self, provider: EastmoneyNewsProvider | None = None) -> None:
        self.provider = provider or EastmoneyNewsProvider()

    def search(
        self,
        instrument: Any,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: Any = None,
        until: Any = None,
        sort: str = "published_desc",
    ) -> tuple[NewsDocumentRef, ...]:
        return self._search_request(
            _build_news_request(
                instrument,
                page=page,
                page_size=page_size,
                max_results=max_results,
                since=since,
                until=until,
                sort=sort,
            )
        )

    def _search_request(self, request: NewsSearchRequest) -> tuple[NewsDocumentRef, ...]:
        records: list[NewsDocumentRef] = []
        seen: dict[str, str] = {}
        page_index = request.page
        exhaustive = request.max_results is not None and request.sort == "published_asc"
        while True:
            page_request = request if page_index == request.page else request.model_copy(update={"page": page_index})
            page = self.provider.fetch_raw_news_page(page_request)
            page_has_new = False
            for row in page.rows:
                if row.document_id in seen:
                    if seen[row.document_id] != row.title:
                        raise ValueError("duplicate news document IDs have conflicting titles")
                    continue
                seen[row.document_id] = row.title
                page_has_new = True
                candidate = normalize_news_search(request, row, source=self.provider.source)
                if not matches_datetime_range(candidate.published_at, since=request.since, until=request.until):
                    continue
                records.append(candidate)
                if request.max_results is not None and not exhaustive and len(records) >= request.max_results:
                    break
            if request.max_results is None or (not exhaustive and len(records) >= request.max_results):
                break
            if page.rows and not page_has_new:
                raise ValueError("news pagination made no progress")
            if not page.rows or len(page.rows) < page.page_size or (page.total_hits is not None and page_index * page.page_size >= page.total_hits):
                break
            page_index += 1
        records.sort(key=lambda record: record.published_at, reverse=request.sort == "published_desc")
        return tuple(records[: request.max_results] if request.max_results is not None else records)

    def get_document(self, ref: NewsDocumentRef) -> StandardRecord:
        source_id = _validate_document_ref(ref, NewsDocumentRef, kind="news", source=self.provider.source)
        return normalize_news_document(
            ref,
            self.provider.fetch_content(source_id),
            source=self.provider.source,
        )

    def get_documents(self, refs: Iterable[NewsDocumentRef]) -> tuple[StandardRecord, ...]:
        return tuple(self.get_document(ref) for ref in refs)


class DisclosureService:
    """Search serializable disclosure refs and fetch complete paginated notices."""

    def __init__(self, provider: EastmoneyDisclosureProvider | None = None) -> None:
        self.provider = provider or EastmoneyDisclosureProvider()

    def search(
        self,
        instrument: Any,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: Any = None,
        until: Any = None,
        categories: list[str] | None = None,
        sort: str = "published_desc",
    ) -> tuple[DisclosureDocumentRef, ...]:
        return self._search_request(
            _build_disclosure_request(
                instrument,
                page=page,
                page_size=page_size,
                max_results=max_results,
                since=since,
                until=until,
                sort=sort,
                categories=categories,
            )
        )

    def _search_request(self, request: DisclosureSearchRequest) -> tuple[DisclosureDocumentRef, ...]:
        records: list[DisclosureDocumentRef] = []
        seen: dict[str, str] = {}
        page_index = request.page
        exhaustive = request.max_results is not None and request.sort == "published_asc"
        requested_categories = set(request.categories or [])
        while True:
            page_request = request if page_index == request.page else request.model_copy(update={"page": page_index})
            page = self.provider.fetch_raw_disclosure_page(page_request)
            page_has_new = False
            for row in page.rows:
                if row.document_id in seen:
                    if seen[row.document_id] != row.title:
                        raise ValueError("duplicate disclosure document IDs have conflicting titles")
                    continue
                seen[row.document_id] = row.title
                page_has_new = True
                candidate = normalize_disclosure_search(request, row, source=self.provider.source)
                if requested_categories and not any(
                    item.code in requested_categories or item.name in requested_categories
                    for item in candidate.categories
                ):
                    continue
                if not matches_datetime_range(candidate.published_at, since=request.since, until=request.until):
                    continue
                records.append(candidate)
                if request.max_results is not None and not exhaustive and len(records) >= request.max_results:
                    break
            if request.max_results is None or (not exhaustive and len(records) >= request.max_results):
                break
            if page.rows and not page_has_new:
                raise ValueError("disclosure pagination made no progress")
            if not page.rows or len(page.rows) < page.page_size or (page.total_hits is not None and page_index * page.page_size >= page.total_hits):
                break
            page_index += 1
        records.sort(key=lambda record: record.published_at, reverse=request.sort == "published_desc")
        return tuple(records[: request.max_results] if request.max_results is not None else records)

    def get_document(self, ref: DisclosureDocumentRef) -> StandardRecord:
        source_id = _validate_document_ref(ref, DisclosureDocumentRef, kind="disclosure", source=self.provider.source)
        return normalize_disclosure_document(
            ref,
            self.provider.fetch_content(source_id),
            source=self.provider.source,
        )

    def get_documents(self, refs: Iterable[DisclosureDocumentRef]) -> tuple[StandardRecord, ...]:
        return tuple(self.get_document(ref) for ref in refs)


__all__ = ["DisclosureService", "NewsService"]
