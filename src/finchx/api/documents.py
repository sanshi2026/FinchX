"""Client namespace implementation: documents."""

from __future__ import annotations

from collections.abc import (
    Iterable,
    Mapping,
    Sequence,
)
from datetime import (
    date,
    datetime,
)
from typing import (
    Literal,
)
from finchx.collectors import (
    FetchResult,
)
from finchx.contracts import (
    StandardRecord,
)
from finchx.datasets import (
    ARTICLE_TOPIC_DATASET,
    TopicArticlesRequest,
    UnsupportedTopicURL,
    classify_topic_url,
    DISCLOSURE_DOCUMENT_DATASET,
    NEWS_DOCUMENT_DATASET,
    DisclosureDocumentRef,
    DisclosureSearchRequest,
    NewsDocumentRef,
    NewsSearchRequest,
    ForumReply,
)
from finchx.datasets.document_common import (
    normalize_document_instrument,
)
from finchx.api._base import (
    _Namespace,
)


class NewsNamespace(_Namespace):
    """Individual-stock news search."""

    def search(
        self,
        instrument: str,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
        sort: str = "published_desc",
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[NewsDocumentRef, ...]]:
        """Search news metadata and return document references in a FetchResult."""
        request = NewsSearchRequest(
            instrumentId=normalize_document_instrument(instrument),
            page=page,
            pageSize=page_size,
            maxResults=max_results,
            since=since,
            until=until,
            sort=sort,
        )
        return self._fetch(
            NEWS_DOCUMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def get_document(self, ref: NewsDocumentRef) -> FetchResult[StandardRecord]:
        """Fetch one complete news document in a FetchResult."""
        return self._client._news_service.get_document(ref)

    def get_documents(self, refs: Iterable[NewsDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch complete news documents in a FetchResult."""
        return self._client._news_service.get_documents(refs)


class DisclosureNamespace(_Namespace):
    """Individual-stock disclosure search."""

    def search(
        self,
        instrument: str,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
        categories: Sequence[str] | None = None,
        sort: str = "published_desc",
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[DisclosureDocumentRef, ...]]:
        """Search disclosures and return document references in a FetchResult."""
        request = DisclosureSearchRequest(
            instrumentId=normalize_document_instrument(instrument),
            page=page,
            pageSize=page_size,
            maxResults=max_results,
            since=since,
            until=until,
            categories=_normalize_disclosure_categories(categories),
            sort=sort,
        )
        return self._fetch(
            DISCLOSURE_DOCUMENT_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def get_document(self, ref: DisclosureDocumentRef) -> FetchResult[StandardRecord]:
        """Fetch one complete disclosure in a FetchResult."""
        return self._client._disclosure_service.get_document(ref)

    def get_documents(self, refs: Iterable[DisclosureDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch complete disclosures in a FetchResult."""
        return self._client._disclosure_service.get_documents(refs)


def _normalize_disclosure_categories(categories: Sequence[str] | None) -> list[str] | None:
    if categories is None:
        return None
    if isinstance(categories, (str, bytes)) or not isinstance(categories, Sequence):
        raise TypeError("categories must be a sequence of category names")
    values = list(categories)
    if not values:
        raise ValueError("categories must contain at least one category name")
    return values


class MarketNewsNamespace(_Namespace):
    """All-market 7x24 news search and detail lookup."""

    def search(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
        sort: str = "published_desc",
    ) -> FetchResult[tuple[NewsDocumentRef, ...]]:
        """Search deduplicated all-market news in a FetchResult."""
        return self._client._market_news_service.search_result(
            page=page,
            page_size=page_size,
            max_results=max_results,
            since=since,
            until=until,
            sort=sort,
        )

    def get_document(self, ref: NewsDocumentRef) -> FetchResult[StandardRecord]:
        """Fetch one complete all-market news document in a FetchResult."""
        return self._client._market_news_service.get_document(ref)

    def get_documents(self, refs: Iterable[NewsDocumentRef]) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch complete all-market news documents in a FetchResult."""
        return self._client._market_news_service.get_documents(refs)


class ArticlesNamespace(_Namespace):
    """Unified THS news and zhibo article details for research evidence."""

    def get(
        self,
        url: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[StandardRecord]:
        """Fetch one article by its public Tonghuashun URL."""
        return self._client._articles_service.get(
            url,
            provider=provider,
            use_cache=use_cache,
        )

    def from_topic(
        self,
        topic_url: str,
        *,
        sort: Literal["recommend"] = "recommend",
        limit: int = 20,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """List supported news refs from a Tonghuashun T-code topic URL."""
        topic_kind, topic_identity = classify_topic_url(topic_url)
        if topic_kind == "deep_topic":
            raise UnsupportedTopicURL(
                "deep-topic report pages have no verified report-scoped news feed; "
                "the public deep-topic items API is a global report index, not related news"
            )
        request = TopicArticlesRequest(topicCode=topic_identity, sort=sort, limit=limit)
        return self._fetch(
            ARTICLE_TOPIC_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )


class ForumNamespace(_Namespace):
    """Public Taoguba forum queries."""

    def replies(
        self,
        *,
        cookies: str | Mapping[str, str],
        user_names: Sequence[str] | None = None,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
    ) -> FetchResult[tuple[ForumReply, ...]]:
        """Fetch qualified replies from the current account's activity feed."""
        return self._client._forum_service.replies(
            cookies=cookies,
            user_names=user_names,
            max_results=max_results,
            since=since,
            until=until,
        )

# Preserve historical public type identities as implementation moves.
NewsNamespace.__module__ = "finchx.client"
DisclosureNamespace.__module__ = "finchx.client"
MarketNewsNamespace.__module__ = "finchx.client"
ArticlesNamespace.__module__ = "finchx.client"
ForumNamespace.__module__ = "finchx.client"
