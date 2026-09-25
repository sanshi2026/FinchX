"""Small public research-oriented query services for news and disclosures."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from finchx.collectors import FetchResult
from finchx.contracts import Source, StandardRecord
from finchx.datasets.disclosure import (
    DISCLOSURE_DOCUMENT_DATASET,
    DisclosureDocumentRef,
    DisclosureSearchRequest,
    normalize_disclosure_document,
    normalize_disclosure_search,
)
from finchx.datasets.document_common import (
    DOCUMENT_SEARCH_MAX_PAGES,
    DescendingTimestampPages,
    matches_datetime_range,
    normalize_document_instrument,
)
from finchx.datasets.news import (
    NEWS_DOCUMENT_DATASET,
    NewsDocumentRef,
    NewsSearchRequest,
    normalize_news_document,
    normalize_news_search,
)
from finchx.providers.eastmoney_documents import EastmoneyDisclosureProvider, EastmoneyNewsProvider
from finchx.providers.errors import ProviderError


def _document_fetch_result(
    data: Any,
    *,
    dataset: Any,
    warnings: tuple[str, ...] = (),
) -> FetchResult[Any]:
    records = data if isinstance(data, tuple) else (data,)
    provider_ids: list[str] = []
    sources: list[Source] = []
    seen_sources: set[tuple[str, str | None, str | None]] = set()
    for record in records:
        candidates = [record.source]
        for occurrence in getattr(record, "source_occurrences", ()):
            candidates.append(
                Source(
                    providerId=occurrence.provider_id,
                    sourceRecordId=occurrence.source_document_id,
                    sourceUrl=occurrence.source_url,
                )
            )
        for reference in record.provenance.source_references:
            candidates.append(
                Source(
                    providerId=reference.provider_id,
                    sourceRecordId=reference.source_record_id,
                    sourceUrl=reference.source_url,
                )
            )
        for candidate in candidates:
            if candidate.provider_id not in provider_ids:
                provider_ids.append(candidate.provider_id)
            key = (
                candidate.provider_id,
                candidate.source_record_id,
                str(candidate.source_url) if candidate.source_url is not None else None,
            )
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(candidate)
    captured_times = [record.captured_at for record in records]
    captured_times.extend(
        occurrence.captured_at
        for record in records
        for occurrence in getattr(record, "source_occurrences", ())
    )
    captured_at = max(captured_times, default=datetime.now(timezone.utc))
    return FetchResult(
        data=data,
        dataset=dataset,
        provider=provider_ids[0] if len(provider_ids) == 1 else None,
        captured_at=captured_at,
        warnings=warnings,
        provenance=tuple(sources),
    )


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


@dataclass(frozen=True)
class _NewsSearchOutcome:
    records: tuple[NewsDocumentRef, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _DisclosureSearchOutcome:
    records: tuple[DisclosureDocumentRef, ...]
    warnings: tuple[str, ...] = ()


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
        return self._search_request_with_warnings(request).records

    def _search_request_with_warnings(self, request: NewsSearchRequest) -> _NewsSearchOutcome:
        records: list[NewsDocumentRef] = []
        warnings: list[str] = []
        seen: dict[str, str] = {}
        page_index = request.page
        exhaustive = request.max_results is not None and request.sort == "published_asc"
        scan_pages = (
            request.max_results is not None
            or request.since is not None
            or request.until is not None
            or exhaustive
        )
        page_limit = DOCUMENT_SEARCH_MAX_PAGES if scan_pages else 1
        chronology = DescendingTimestampPages()
        pages_scanned = 0
        while True:
            page_request = request if page_index == request.page else request.model_copy(update={"page": page_index})
            page = self.provider.fetch_raw_news_page(page_request)
            pages_scanned += 1
            warnings.extend(getattr(page, "warnings", ()))
            page_has_new = False
            page_has_parseable = False
            for row_index, row in enumerate(page.rows):
                if row.document_id in seen:
                    if seen[row.document_id] != row.title:
                        raise ValueError("duplicate news document IDs have conflicting titles")
                    continue
                seen[row.document_id] = row.title
                page_has_new = True
                try:
                    candidate = normalize_news_search(request, row, source=self.provider.source)
                except (TypeError, ValueError) as exc:
                    warnings.append(
                        f"Skipped EastMoney news row {row_index}: normalization failed: {exc}"
                    )
                    continue
                page_has_parseable = True
                if not matches_datetime_range(candidate.published_at, since=request.since, until=request.until):
                    continue
                records.append(candidate)
                if request.max_results is not None and not exhaustive and len(records) >= request.max_results:
                    break
            if page_has_new and not page_has_parseable:
                raise ProviderError(
                    self.provider.source,
                    "EastMoney news page contained no normalizable rows",
                )
            if request.max_results is not None and not exhaustive and len(records) >= request.max_results:
                break
            if page.rows and not page_has_new:
                raise ValueError("news pagination made no progress")
            if chronology.page_is_before_since(
                tuple(row.published_at for row in page.rows),
                request.since,
            ):
                break
            has_more = bool(page.rows) and (
                page_index * page.page_size < page.total_hits
                if page.total_hits is not None
                else len(page.rows) >= page.page_size
            )
            if not scan_pages or not has_more:
                break
            if pages_scanned >= page_limit:
                warnings.append(
                    f"News search stopped after {page_limit} pages; results may be incomplete."
                )
                break
            page_index += 1
        records.sort(key=lambda record: record.published_at, reverse=request.sort == "published_desc")
        return _NewsSearchOutcome(
            tuple(records[: request.max_results] if request.max_results is not None else records),
            tuple(warnings),
        )

    def _get_document_record(self, ref: NewsDocumentRef) -> StandardRecord:
        source_id = _validate_document_ref(ref, NewsDocumentRef, kind="news", source=self.provider.source)
        return normalize_news_document(
            ref,
            self.provider.fetch_content(source_id),
            source=self.provider.source,
        )

    def get_document(self, ref: NewsDocumentRef) -> FetchResult[StandardRecord]:
        return _document_fetch_result(
            self._get_document_record(ref),
            dataset=NEWS_DOCUMENT_DATASET,
        )

    def get_documents(self, refs: Iterable[NewsDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        records = tuple(self._get_document_record(ref) for ref in refs)
        return _document_fetch_result(records, dataset=NEWS_DOCUMENT_DATASET)


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
        return self._search_request_with_warnings(request).records

    def _search_request_with_warnings(
        self,
        request: DisclosureSearchRequest,
    ) -> _DisclosureSearchOutcome:
        records: list[DisclosureDocumentRef] = []
        warnings: list[str] = []
        seen: dict[str, str] = {}
        page_index = request.page
        exhaustive = request.max_results is not None and request.sort == "published_asc"
        scan_pages = (
            request.max_results is not None
            or request.since is not None
            or request.until is not None
            or exhaustive
        )
        page_limit = DOCUMENT_SEARCH_MAX_PAGES if scan_pages else 1
        chronology = DescendingTimestampPages()
        pages_scanned = 0
        requested_categories = set(request.categories or [])
        while True:
            page_request = request if page_index == request.page else request.model_copy(update={"page": page_index})
            page = self.provider.fetch_raw_disclosure_page(page_request)
            pages_scanned += 1
            warnings.extend(getattr(page, "warnings", ()))
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
            if request.max_results is not None and not exhaustive and len(records) >= request.max_results:
                break
            if page.rows and not page_has_new:
                raise ValueError("disclosure pagination made no progress")
            if chronology.page_is_before_since(
                tuple(row.published_candidate for row in page.rows),
                request.since,
            ):
                break
            has_more = bool(page.rows) and (
                page_index * page.page_size < page.total_hits
                if page.total_hits is not None
                else len(page.rows) >= page.page_size
            )
            if not scan_pages or not has_more:
                break
            if pages_scanned >= page_limit:
                warnings.append(
                    f"Disclosure search stopped after {page_limit} pages; results may be incomplete."
                )
                break
            page_index += 1
        records.sort(key=lambda record: record.published_at, reverse=request.sort == "published_desc")
        return _DisclosureSearchOutcome(
            tuple(records[: request.max_results] if request.max_results is not None else records),
            tuple(warnings),
        )

    def _get_document_record(self, ref: DisclosureDocumentRef) -> StandardRecord:
        source_id = _validate_document_ref(ref, DisclosureDocumentRef, kind="disclosure", source=self.provider.source)
        return normalize_disclosure_document(
            ref,
            self.provider.fetch_content(source_id),
            source=self.provider.source,
        )

    def get_document(self, ref: DisclosureDocumentRef) -> FetchResult[StandardRecord]:
        return _document_fetch_result(
            self._get_document_record(ref),
            dataset=DISCLOSURE_DOCUMENT_DATASET,
        )

    def get_documents(self, refs: Iterable[DisclosureDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        records = tuple(self._get_document_record(ref) for ref in refs)
        return _document_fetch_result(records, dataset=DISCLOSURE_DOCUMENT_DATASET)


__all__ = ["DisclosureService", "NewsService"]
