"""Contracts for news articles discovered through a Tonghuashun topic feed."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from typing import Annotated, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, field_validator

from finchx.contracts import (
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    QualityIssue,
    QualityIssueKind,
    Source,
    SourceReference,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.article_detail import ArticleDetailRequest
from finchx.datasets.definition import DatasetDefinition


_T_CODE = re.compile(r"^T[A-Za-z0-9]{6}$")
_DEEP_TOPIC_ID = re.compile(r"^dt_[0-9A-Z]{26}$")
_T_TOPIC_PATHS = frozenset(
    {
        "/lgt/main/frontend-main-service/topic/index.html",
        "/m/topic/index.html",
    }
)
_DEEP_TOPIC_PATH = re.compile(r"^/deep-topic/topic/(dt_[0-9A-Z]{26})$")
TopicLimit = Annotated[int, Field(strict=True, ge=1, le=100)]


class UnsupportedTopicURL(ValueError):
    """A recognized topic URL whose related content cannot be listed safely."""


def classify_topic_url(url: str) -> tuple[Literal["t_code", "deep_topic"], str]:
    """Validate the supported public topic URLs and return kind plus identity.

    T-code URLs are accepted only on the two known community paths. Deep-topic
    report URLs are recognized separately so the API can return a clear
    unsupported-source error instead of misreading their opaque ID as a T-code.
    """

    if not isinstance(url, str) or not url.strip():
        raise ValueError("topic_url must be a non-empty Tonghuashun topic URL")
    candidate = url.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("topic_url is malformed") from exc
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("topic_url must be an absolute HTTPS Tonghuashun URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("topic_url must not contain user credentials")
    if port not in (None, 443):
        raise ValueError("topic_url must use the default HTTPS port")

    host = parsed.hostname.casefold()
    if host == "t.10jqka.com.cn" and parsed.path in _T_TOPIC_PATHS:
        codes = parse_qs(parsed.query, keep_blank_values=True).get("code", [])
        if len(codes) != 1 or not _T_CODE.fullmatch(codes[0]):
            raise ValueError("topic_url must contain exactly one valid T-code in its code query parameter")
        return "t_code", codes[0]

    if host == "news.10jqka.com.cn":
        match = _DEEP_TOPIC_PATH.fullmatch(parsed.path)
        if match and _DEEP_TOPIC_ID.fullmatch(match.group(1)):
            return "deep_topic", match.group(1)
        if parsed.path.startswith("/deep-topic/topic/"):
            raise ValueError("topic_url contains an invalid deep-topic identifier")

    raise ValueError("unsupported Tonghuashun topic URL host or path")


class TopicArticlesRequest(ContractModel):
    """A topic-code keyed, bounded request for supported article refs."""

    topic_code: str = Field(
        alias="topicCode",
        strict=True,
        pattern=r"^T[A-Za-z0-9]{6}$",
        description="Validated T-code extracted from an allowlisted topic URL; it is the cache identity.",
    )
    sort: Literal["recommend"] = Field(
        default="recommend",
        description="Recommendation feed followed by its ordinary feed; other tab cursors are not exposed.",
    )
    limit: TopicLimit = Field(
        default=20,
        description="Maximum number of supported news and long-article records after filtering the mixed feed.",
    )


class TopicArticleData(ContractModel):
    """A discovered news or long-article ref accepted by ``articles.get``."""

    topic_code: str = Field(alias="topicCode", pattern=r"^T[A-Za-z0-9]{6}$")
    rank: int = Field(ge=1, description="Position in the source-ordered, filtered article list.")
    content_id: str = Field(
        alias="contentId",
        pattern=r"^\d{6,16}$",
        description="Numeric Tonghuashun article sequence ID from the topic item.",
    )
    content_type: Literal["news", "zhibo"] = Field(
        alias="contentType",
        description="Verified type=8 news and type=2 long articles use the existing news or zhibo detail route.",
    )
    title: str = Field(min_length=1, description="Article title supplied by the topic feed.")
    url: str = Field(
        description="Public news or zhibo article URL accepted by fx.articles.get(url).",
    )
    published_at: datetime = Field(
        alias="publishedAt",
        description="Source article timestamp normalized from epoch milliseconds to Asia/Shanghai.",
    )
    source_name: str | None = Field(
        default=None,
        alias="sourceName",
        description="Publisher or media label supplied by the topic feed item.",
    )

    @field_validator("url")
    @classmethod
    def url_must_be_a_matching_article_page(cls, value: str, info) -> str:
        request = ArticleDetailRequest(url=value)
        content_type = info.data.get("content_type")
        if request.content_type != content_type:
            raise ValueError("topic article contentType must match its detail URL route")
        content_id = info.data.get("content_id")
        if content_id is not None and request.content_id != content_id:
            raise ValueError("topic article URL ID must match contentId")
        return request.url


ARTICLE_TOPIC_DATASET: DatasetDefinition[TopicArticlesRequest, TopicArticleData] = DatasetDefinition(
    "articles.topic", "1.0", TopicArticlesRequest, TopicArticleData
)


def normalize_topic_articles(
    request: TopicArticlesRequest,
    raw: Mapping[str, object],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    """Validate topic-feed rows and build source-aware FinchX records."""

    if not isinstance(raw, Mapping):
        raise ValueError("topic Provider result must be a mapping")
    rows = raw.get("rows")
    if not isinstance(rows, list):
        raise ValueError("topic Provider result must include a rows list")
    captured_at = raw.get("capturedAt")
    if not isinstance(captured_at, datetime) or captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("topic capture timestamp must be timezone-aware")
    source_url = raw.get("sourceUrl")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise ValueError("topic Provider result must include its HTTPS feed URL")
    partial_detail = str(raw.get("partialDetail") or "").strip()
    records: list[StandardRecord] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("topic Provider row must be a mapping")
        item_raw = row.get("data")
        if not isinstance(item_raw, Mapping):
            raise ValueError("topic Provider row must contain a data object")
        item = TopicArticleData.model_validate(item_raw)
        if item.topic_code != request.topic_code:
            raise ValueError("topic Provider row code does not match the request")
        identity = (item.content_type, item.content_id)
        if identity in seen:
            raise ValueError(f"duplicate topic article identity: {item.content_type}:{item.content_id}")
        seen.add(identity)
        row_source_url = row.get("sourceUrl") or source_url
        if not isinstance(row_source_url, str) or not row_source_url.startswith("https://"):
            raise ValueError("topic Provider row must include its HTTPS feed URL")
        source_record_id = f"{request.topic_code}:{item.content_type}:{item.content_id}"
        article_entity_id = f"tonghuashun:article:{item.content_id}"
        issue_list = (
            [QualityIssue(kind=QualityIssueKind.PARTIAL, detail=partial_detail)]
            if partial_detail
            else []
        )
        records.append(
            StandardRecord(
                dataset=ARTICLE_TOPIC_DATASET.name,
                schemaVersion=ARTICLE_TOPIC_DATASET.schema_version,
                recordId=(
                    f"tonghuashun:topic-article:{request.topic_code}:"
                    f"{item.content_type}:{item.content_id}"
                ),
                entityId=article_entity_id,
                eventAt=item.published_at,
                publishedAt=item.published_at,
                capturedAt=captured_at,
                source=Source(
                    providerId=source.provider_id,
                    sourceRecordId=source_record_id,
                    sourceUrl=row_source_url,
                ),
                status=DataStatus.LIVE,
                quality=Quality(issues=issue_list),
                provenance=Provenance(
                    recordClass=ProvenanceClass.STANDARDIZED,
                    transformationVersion="tonghuashun-topic-articles-normalizer/1",
                    sourceReferences=[
                        SourceReference(
                            providerId=source.provider_id,
                            sourceRecordId=source_record_id,
                            sourceUrl=row_source_url,
                        )
                    ],
                ),
                data=item.model_dump(mode="json", by_alias=True),
            )
        )

    if len(records) > request.limit:
        raise ValueError("topic Provider returned more records than requested")
    return tuple(records)


__all__ = [
    "ARTICLE_TOPIC_DATASET",
    "TopicArticleData",
    "TopicArticlesRequest",
    "UnsupportedTopicURL",
    "classify_topic_url",
    "normalize_topic_articles",
]
