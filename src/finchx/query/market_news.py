"""Public query service for market-level 7x24 news and deterministic deduplication."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import hashlib
import html
import re
import unicodedata
from typing import Any, Protocol

from finchx.contracts import StandardRecord
from finchx.datasets.document_common import matches_datetime_range
from finchx.datasets.news import (
    MarketNewsSearchRequest,
    NewsDocumentRef,
    _ProviderNewsRow,
    _news_record,
    _news_ref_from_record,
    normalize_news_document,
)
from finchx.providers.market_news import (
    AigupiaoMarketNewsProvider,
    BaiduFinscopeMarketNewsProvider,
    EastmoneyMarketNewsProvider,
)


class _MarketProvider(Protocol):
    provider_id: str

    @property
    def source(self) -> Any: ...

    def fetch_raw_news_page(self, request: MarketNewsSearchRequest) -> Any: ...

    def fetch_content(self, document_id: str, *, document_url: str | None = None) -> _ProviderNewsRow: ...


def _normalized_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(unicodedata.normalize("NFKC", value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = " ".join(value.split()).strip()
    value = value.strip(" \t\\n\\r\\u3000()[]{}<>:;,，。！？!?—-·")
    return value


def _fingerprint(record: StandardRecord) -> tuple[str, datetime] | None:
    data = record.data
    title = _normalized_text(data.get("title"))
    body = _normalized_text(data.get("contentText") or data.get("summary"))
    if body.startswith(f"【{title}】"):
        body = body[len(title) + 2:].strip()
    if title and body.startswith(title):
        body = body[len(title):].strip(" ：:，,。.!！")
    published = record.published_at
    if not title or not body or published is None:
        return None
    raw = f"{title}\0{body}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), published


def _same_event(left: tuple[str, datetime], right: tuple[str, datetime]) -> bool:
    return left[0] == right[0] and abs(left[1] - right[1]) <= timedelta(minutes=10)


def _merge_refs(refs: list[NewsDocumentRef]) -> NewsDocumentRef:
    first = refs[0]
    occurrences = []
    references = []
    seen_occurrences: set[tuple[str, str]] = set()
    seen_references: set[tuple[str, str | None]] = set()
    for ref in refs:
        for occurrence in ref.source_occurrences:
            key = (occurrence.provider_id, occurrence.source_document_id)
            if key not in seen_occurrences:
                seen_occurrences.add(key)
                occurrences.append(occurrence)
        for reference in ref.provenance.source_references:
            key = (reference.provider_id, reference.source_record_id)
            if key not in seen_references:
                seen_references.add(key)
                references.append(reference)
    provenance = first.provenance.model_copy(update={"source_references": references})
    return first.model_copy(update={"source_occurrences": occurrences, "provenance": provenance})


class MarketNewsService:
    """Search market news across sources and retain every deduplicated occurrence."""

    def __init__(self, providers: Iterable[_MarketProvider] | None = None) -> None:
        self.providers = tuple(providers or (
            EastmoneyMarketNewsProvider(),
            AigupiaoMarketNewsProvider(),
            BaiduFinscopeMarketNewsProvider(),
        ))
        if not self.providers:
            raise ValueError("MarketNewsService requires at least one provider")
        provider_ids = [provider.provider_id for provider in self.providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("MarketNewsService provider IDs must be unique")

    def search(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: Any = None,
        until: Any = None,
        sort: str = "published_desc",
    ) -> tuple[NewsDocumentRef, ...]:
        request = MarketNewsSearchRequest(
            page=page,
            pageSize=page_size,
            maxResults=max_results,
            since=since,
            until=until,
            sort=sort,
        )
        return self._search_request(request)

    def _search_request(self, request: MarketNewsSearchRequest) -> tuple[NewsDocumentRef, ...]:
        candidates: list[tuple[NewsDocumentRef, StandardRecord]] = []
        source_seen: set[tuple[str, str]] = set()
        cursors: dict[str, str | None] = {provider.provider_id: None for provider in self.providers}
        active = set(cursors)
        page_index = request.page
        first_round = True

        while active:
            round_added = 0
            next_active: set[str] = set()
            for provider in self.providers:
                if provider.provider_id not in active:
                    continue
                provider_request = request.model_copy(
                    update={
                        "page": page_index,
                        "max_results": None,
                        "cursor": cursors[provider.provider_id],
                    }
                )
                page_result = provider.fetch_raw_news_page(provider_request)
                rows = tuple(page_result.rows)
                for row in rows:
                    source_key = (provider.provider_id, row.document_id)
                    if source_key in source_seen:
                        continue
                    source_seen.add(source_key)
                    record = _news_record(row, source=provider.source, instrument_id=None)
                    ref = _news_ref_from_record(record)
                    if not matches_datetime_range(ref.published_at, since=request.since, until=request.until):
                        continue
                    candidates.append((ref, record))
                    round_added += 1
                token = getattr(page_result, "next_page_token", None)
                has_more = bool(rows) and (
                    token is not None or len(rows) >= request.page_size
                )
                if has_more:
                    if token is None and page_result.page_index == page_index:
                        next_active.add(provider.provider_id)
                    elif token not in (None, cursors[provider.provider_id]):
                        next_active.add(provider.provider_id)
                    cursors[provider.provider_id] = token
            if request.max_results is None:
                break
            if request.sort == "published_desc" and len(candidates) >= request.max_results:
                break
            if not next_active or (not round_added and not first_round):
                break
            active = next_active
            page_index += 1
            first_round = False

        candidates.sort(
            key=lambda item: (
                item[0].published_at,
                item[0].source.provider_id,
                item[0].source_document_id,
            ),
            reverse=request.sort == "published_desc",
        )
        selected: list[NewsDocumentRef] = []
        selected_fingerprints: list[tuple[str, datetime]] = []
        selected_source_keys: set[tuple[str, str]] = set()
        for ref, record in candidates:
            source_key = (ref.source.provider_id, ref.source_document_id)
            if source_key in selected_source_keys:
                continue
            duplicate_index = None
            candidate_fingerprint = _fingerprint(record)
            if candidate_fingerprint is not None:
                for index, fingerprint in enumerate(selected_fingerprints):
                    if _same_event(candidate_fingerprint, fingerprint):
                        duplicate_index = index
                        break
            if duplicate_index is not None:
                selected[duplicate_index] = _merge_refs([selected[duplicate_index], ref])
                selected_source_keys.add(source_key)
                continue
            selected.append(ref)
            selected_source_keys.add(source_key)
            if candidate_fingerprint is not None:
                selected_fingerprints.append(candidate_fingerprint)
            else:
                selected_fingerprints.append(("", datetime.min))
        selected.sort(key=lambda ref: ref.published_at, reverse=request.sort == "published_desc")
        return tuple(selected[: request.max_results] if request.max_results is not None else selected)

    def get_document(self, ref: NewsDocumentRef) -> StandardRecord:
        provider = next((item for item in self.providers if item.provider_id == ref.source.provider_id), None)
        if provider is None:
            raise ValueError("document ref provider is not configured")
        source_id = ref.source_document_id
        expected_id = f"{provider.provider_id}:market_news:{source_id}"
        if ref.document_id != expected_id:
            raise ValueError("document ref documentId/sourceDocumentId do not match")
        if ref.source.source_record_id not in (None, source_id):
            raise ValueError("document ref sourceRecordId does not match sourceDocumentId")
        return normalize_news_document(
            ref,
            provider.fetch_content(source_id, document_url=str(ref.source_url)),
            source=provider.source,
        )

    def get_documents(self, refs: Iterable[NewsDocumentRef]) -> tuple[StandardRecord, ...]:
        return tuple(self.get_document(ref) for ref in refs)


__all__ = ["MarketNewsService"]
