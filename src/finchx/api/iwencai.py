"""Client namespace implementation: iwencai."""

from __future__ import annotations

from collections.abc import (
    Mapping,
)
from finchx.collectors import (
    FetchResult,
)
from finchx.contracts import (
    StandardRecord,
)
from finchx.datasets import (
    IWENCAI_REPORT_DETAIL_DATASET,
    IWENCAI_SEARCH_DATASET,
    IWENCAI_SELECTION_DATASET,
    IwencaiReportDetailRequest,
    IwencaiSearchRequest,
    IwencaiSelectionRequest,
)
from finchx.api._base import (
    _RequestNamespace,
)


class IwencaiNamespace(_RequestNamespace):
    """iWenCai's cookie-backed screener, search, and report details."""

    def select(
        self,
        query: str,
        *,
        cookies: str | Mapping[str, str],
        user_agent: str | None = None,
        page_size: int = 100,
        max_pages: int = 100,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Run the final table rendered by ``iwencai.com/screener``.

        A caller-owned Cookie header is mandatory.  The result contains one
        standardized ``StandardRecord`` per stock; dynamic source columns
        are retained under ``extraFields``.
        """

        request = IwencaiSelectionRequest(
            query=query,
            cookies=cookies,
            userAgent=user_agent,
            pageSize=page_size,
            maxPages=max_pages,
        )
        return self._fetch(
            IWENCAI_SELECTION_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def search(
        self,
        query: str,
        *,
        channel: str = "report",
        size: int = 50,
        cookies: str | Mapping[str, str] | None = None,
        api_key: str | None = None,
        deduplicate: bool = True,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Search reports, announcements, or news with SkillHub OpenAPI.

        The API key is read from ``IWENCAI_API_KEY`` when omitted.  Cookies
        are accepted and forwarded for one consistent credential surface, but
        the OpenAPI authorization is the API key plus X-Claw headers.  The
        result contains one standardized ``StandardRecord`` per hit.
        """

        request = IwencaiSearchRequest(
            query=query,
            channel=channel,
            size=size,
            cookies=cookies,
            apiKey=api_key,
            deduplicate=deduplicate,
        )
        return self._fetch(
            IWENCAI_SEARCH_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def report_detail(
        self,
        url: str,
        *,
        cookies: str | Mapping[str, str],
        uid: str | None = None,
        title: str | None = None,
        published_at: str | None = None,
        user_agent: str | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Fetch report text and metadata linked from ``iwencai.search``.

        Pass the hit's ``url`` field, for example
        ``fx.iwencai.report_detail(hit["url"], cookies=...)``.  The request
        requires the caller's iWenCai/THS cookie.
        """

        request = IwencaiReportDetailRequest(
            url=url,
            cookies=cookies,
            uid=uid,
            title=title,
            publishedAt=published_at,
            userAgent=user_agent,
        )
        return self._fetch(
            IWENCAI_REPORT_DETAIL_DATASET,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def detail(
        self,
        url: str,
        *,
        cookies: str | Mapping[str, str],
        uid: str | None = None,
        title: str | None = None,
        published_at: str | None = None,
        user_agent: str | None = None,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[tuple[StandardRecord, ...]]:
        """Alias for :meth:`report_detail`."""

        return self.report_detail(
            url,
            cookies=cookies,
            uid=uid,
            title=title,
            published_at=published_at,
            user_agent=user_agent,
            provider=provider,
            use_cache=use_cache,
        )

# Preserve historical public type identities as implementation moves.
IwencaiNamespace.__module__ = "finchx.client"
