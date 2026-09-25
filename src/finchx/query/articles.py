"""Public article-detail orchestration over FinchX Collector and Storage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from finchx.collectors import FetchResult
from finchx.collectors.errors import (
    AllProvidersFailed,
    AuthenticationError,
    CollectorError,
    ProviderExecutionError,
    RateLimitError,
    SourceUnavailable,
    Timeout,
)
from finchx.contracts import Source, StandardRecord
from finchx.datasets.article_detail import (
    ARTICLE_DETAIL_DATASET,
    ArticleDetailData,
    ArticleDetailRequest,
)
from finchx.providers.errors import ProviderError
from finchx.providers.ths_articles import ARTICLE_PROVIDER_ID, ArticleDetailSourceError
from finchx.storage import Cache, MemoryStorage, StorageKey


_SUCCESS_TTL_SECONDS = 24 * 60 * 60
_NEGATIVE_TTLS = {"not_found": 15 * 60, "unauthorized": 60, "blocked": 60, "rate_limited": 30}


class ArticleDetailService:
    """Fetch one unified THS article detail and keep a bounded categorized cache."""

    def __init__(self, collector: Any, *, cache: Cache | None = None) -> None:
        self._collector = collector
        self._cache = cache or Cache(MemoryStorage())

    def get(
        self,
        url: str,
        *,
        provider: str | None = None,
        use_cache: bool | None = None,
    ) -> FetchResult[StandardRecord]:
        request = ArticleDetailRequest(url=url)
        if use_cache is not None and type(use_cache) is not bool:
            raise TypeError("use_cache must be a bool or None")
        key = _cache_key(request)
        if use_cache is not False:
            cached = self._cache.get(key)
            if cached is not None and isinstance(cached.data, Mapping):
                cached_result = _success_from_cache(cached.data, request)
                if cached_result is not None:
                    return cached_result
                cached_error = _failure_from_cache(cached.data, request)
                if cached_error is not None:
                    raise cached_error

        try:
            result = self._collector.fetch(
                ARTICLE_DETAIL_DATASET,
                provider=provider,
                use_cache=False,
                request=request,
            )
            if not isinstance(result.data, StandardRecord):
                raise TypeError("article detail Provider did not return a StandardRecord")
            record = _adapt_record_for_request(result.data, request)
            if use_cache is not False:
                self._cache.put(
                    key,
                    {
                        "outcome": "success",
                        "record": record.model_dump(mode="json", by_alias=True),
                        "warnings": list(result.warnings),
                        "fallbackUsed": result.fallback_used,
                    },
                    ttl=_SUCCESS_TTL_SECONDS,
                    source=record.source,
                    provenance=record.provenance,
                    metadata={"outcome": "success"},
                )
            return FetchResult(
                data=record,
                dataset=ARTICLE_DETAIL_DATASET,
                provider=record.source.provider_id,
                captured_at=record.captured_at,
                warnings=result.warnings,
                provenance=(record.source,),
                attempts=result.attempts,
                fallback_used=result.fallback_used,
                cache_hit=False,
            )
        except (AllProvidersFailed, CollectorError, ProviderError) as exc:
            error_code, error_message = _error_details(exc)
            source = Source(providerId=ARTICLE_PROVIDER_ID, sourceRecordId=request.content_id)
            ttl = _NEGATIVE_TTLS.get(error_code, 0)
            if use_cache is not False and ttl:
                self._cache.put(
                    key,
                    {"outcome": "failed", "errorCode": error_code, "errorMessage": error_message[:500]},
                    ttl=ttl,
                    source=source,
                    metadata={"outcome": "failed", "errorCode": error_code},
                )
            raise


def _cache_key(request: ArticleDetailRequest) -> StorageKey:
    return StorageKey.from_dataset(
        ARTICLE_DETAIL_DATASET,
        {"url": request.url},
    )


def _error_details(error: BaseException) -> tuple[str, str]:
    if isinstance(error, AllProvidersFailed):
        error = error.last_error
    if isinstance(error, ArticleDetailSourceError):
        return error.error_code, error.reason
    if isinstance(error, AuthenticationError):
        return "unauthorized", str(error)
    if isinstance(error, RateLimitError):
        return "rate_limited", str(error)
    if isinstance(error, Timeout):
        return "timeout", str(error)
    if isinstance(error, SourceUnavailable):
        return "network_error", str(error)
    if isinstance(error, ProviderError):
        reason = error.reason
        lowered = reason.casefold()
        if "404" in lowered:
            return "not_found", reason
        if "401" in lowered:
            return "unauthorized", reason
        if "403" in lowered or "blocked" in lowered:
            return "blocked", reason
        if "429" in lowered or "rate limit" in lowered:
            return "rate_limited", reason
        if "timed out" in lowered or "timeout" in lowered:
            return "timeout", reason
        if "transport failure" in lowered or "server error" in lowered:
            return "network_error", reason
        return "fetch_error", reason
    if isinstance(error, ProviderExecutionError):
        return "fetch_error", error.reason
    return "fetch_error", str(error) or type(error).__name__


def _success_from_cache(value: Mapping[str, Any], request: ArticleDetailRequest) -> FetchResult[StandardRecord] | None:
    if value.get("outcome") != "success" or not isinstance(value.get("record"), Mapping):
        return None
    try:
        record = _adapt_record_for_request(StandardRecord.model_validate(value["record"]), request)
    except Exception:
        return None
    return FetchResult(
        data=record,
        dataset=ARTICLE_DETAIL_DATASET,
        provider=record.source.provider_id,
        captured_at=record.captured_at,
        warnings=tuple(value.get("warnings") or ()),
        provenance=(record.source,),
        fallback_used=bool(value.get("fallbackUsed")),
        cache_hit=True,
    )


def _failure_from_cache(value: Mapping[str, Any], request: ArticleDetailRequest) -> ArticleDetailSourceError | None:
    if value.get("outcome") != "failed":
        return None
    error_code = str(value.get("errorCode") or "fetch_error")
    message = str(value.get("errorMessage") or error_code)
    source = Source(providerId=ARTICLE_PROVIDER_ID, sourceRecordId=request.content_id)
    return ArticleDetailSourceError(source, message, error_code=error_code)


def _adapt_record_for_request(record: StandardRecord, request: ArticleDetailRequest) -> StandardRecord:
    try:
        detail = ArticleDetailData.model_validate(record.data)
    except Exception:
        return record
    payload = detail.model_dump(mode="json", by_alias=True)
    payload["contentId"] = request.content_id
    return record.model_copy(update={"data": payload})


__all__ = ["ArticleDetailService"]
