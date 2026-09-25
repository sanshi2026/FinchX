"""Stable contract and normalization for EastMoney individual-stock news."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pydantic import AnyUrl, Field, field_validator, model_validator

from finchx.contracts import (
    Adjustment,
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    SourceReference,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.document_common import (
    DocumentSort,
    TimedDocumentSearchRequest,
    _bound_datetime,
)
from finchx.entities import InstrumentId


class MarketNewsSearchRequest(ContractModel):
    """Bounded market-level 7x24 news search controls."""

    page: int = Field(default=1, strict=True, ge=1)
    page_size: int = Field(default=20, alias="pageSize", strict=True, ge=1, le=20)
    max_results: int | None = Field(default=None, alias="maxResults", strict=True, ge=1)
    cursor: str | None = Field(default=None, min_length=1)
    since: date | datetime | None = None
    until: date | datetime | None = None
    sort: DocumentSort = "published_desc"

    @field_validator("since", "until")
    @classmethod
    def datetime_bounds_must_be_aware(cls, value: date | datetime | None) -> date | datetime | None:
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("since/until datetimes must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> MarketNewsSearchRequest:
        if self.max_results is not None and self.page != 1:
            raise ValueError("maxResults requires page=1; page and maxResults cannot be combined ambiguously")
        if (self.since is not None or self.until is not None) and self.page != 1:
            raise ValueError("since/until requires page=1 for a complete date-range search")
        if self.since is not None and self.until is not None:
            if _bound_datetime(self.since) > _bound_datetime(self.until):
                raise ValueError("since must not be later than until")
        return self


class NewsSourceOccurrence(ContractModel):
    """One source-side occurrence retained when market news is deduplicated."""

    provider_id: str = Field(alias="providerId", min_length=1)
    source_document_id: str = Field(alias="sourceDocumentId", min_length=1)
    source_url: AnyUrl | None = Field(default=None, alias="sourceUrl")
    document_url: AnyUrl | None = Field(default=None, alias="documentUrl")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    captured_at: datetime = Field(alias="capturedAt")


class NewsSearchRequest(TimedDocumentSearchRequest):
    """Search metadata for one explicitly routed SSE/SZSE equity."""


class NewsDocumentRef(ContractModel):
    """Serializable search metadata used to fetch one full news document."""

    document_id: str = Field(alias="documentId", min_length=1)
    source_document_id: str = Field(alias="sourceDocumentId", min_length=1)
    title: str = Field(min_length=1)
    important: bool | None = Field(
        default=None,
        strict=True,
        description=(
            "Normalized source importance marker: True when the source marks the item important; "
            "False when it does not; None when unavailable."
        ),
    )
    published_at: datetime = Field(alias="publishedAt")
    source_url: AnyUrl = Field(
        alias="sourceUrl",
        description="The provider page or query URL where this source occurrence was found.",
    )
    document_url: AnyUrl = Field(
        alias="documentUrl",
        description="The URL of the article body used when fetching its full content.",
    )
    original_url: AnyUrl | None = Field(default=None, alias="originalUrl")
    related_instruments: list[InstrumentId] = Field(alias="relatedInstruments")
    source: Source
    captured_at: datetime = Field(alias="capturedAt")
    provenance: Provenance
    source_occurrences: list[NewsSourceOccurrence] = Field(
        default_factory=list,
        alias="sourceOccurrences",
    )


    summary: str | None = None
class NewsDocumentData(ContractModel):
    document_id: str = Field(alias="documentId", min_length=1)
    source_document_id: str = Field(alias="sourceDocumentId", min_length=1)
    title: str = Field(min_length=1)
    important: bool | None = Field(
        default=None,
        strict=True,
        description=(
            "Normalized source importance marker: True when the source marks the item important; "
            "False when it does not; None when unavailable."
        ),
    )
    content_text: str | None = Field(default=None, alias="contentText")
    summary: str | None = None
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    source_occurrences: list[NewsSourceOccurrence] = Field(
        default_factory=list,
        alias="sourceOccurrences",
    )
    url: AnyUrl
    original_url: AnyUrl | None = Field(default=None, alias="originalUrl")
    content_available: bool = Field(alias="contentAvailable")
    source: str | None = None
    related_instruments: list[InstrumentId] = Field(alias="relatedInstruments")

    @field_validator("content_text")
    @classmethod
    def content_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("contentText must be non-blank when present")
        return value


NEWS_DOCUMENT_DATASET: DatasetDefinition[NewsSearchRequest, NewsDocumentData] = DatasetDefinition(
    name="news.document",
    schema_version="1.0",
    request_type=NewsSearchRequest,
    data_type=NewsDocumentData,
)


@dataclass(frozen=True)
class _ProviderNewsRow:
    instrument_id: InstrumentId | None
    document_id: str
    title: str
    published_at: datetime | None
    url: str
    original_url: str | None
    source_name: str | None
    content_text: str | None
    source_url: str
    captured_at: datetime
    important: bool | None = None
    summary: str | None = None
    related_instruments: tuple[InstrumentId, ...] = ()
    public_document_id: str | None = None
    title_derived: bool = False
    sort_start: str | None = None
    np_dst: str | None = None

def _news_document_id(row: _ProviderNewsRow) -> str:
    return row.public_document_id or f"eastmoney:news:{row.document_id}"


def _source_occurrence(
    row: _ProviderNewsRow,
    *,
    source: Source,
) -> NewsSourceOccurrence:
    return NewsSourceOccurrence(
        providerId=source.provider_id,
        sourceDocumentId=row.document_id,
        sourceUrl=row.source_url or source.source_url,
        documentUrl=row.url,
        publishedAt=row.published_at,
        capturedAt=row.captured_at,
    )



def _news_record(
    row: _ProviderNewsRow,
    *,
    source: Source,
    instrument_id: InstrumentId | None,
) -> StandardRecord:
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    related = list(row.related_instruments)
    if instrument_id is not None and instrument_id not in related:
        related.insert(0, instrument_id)
    document_id = _news_document_id(row)
    data = NewsDocumentData(
        summary=row.summary,
        documentId=document_id,
        sourceDocumentId=row.document_id,
        title=row.title,
        important=row.important,
        contentText=row.content_text,
        publishedAt=row.published_at,
        url=row.url,
        originalUrl=row.original_url,
        contentAvailable=row.content_text is not None or bool(row.url),
        source=row.source_name,
        relatedInstruments=related,
        sourceOccurrences=[_source_occurrence(row, source=source)],
    )
    source_url = row.source_url or source.source_url
    adjustments = []
    if row.title_derived:
        adjustments.append(
            Adjustment(
                name="title-derived-from-source-content",
                version="1",
                details={"sourceDocumentId": row.document_id},
            )
        )
    source_ref = SourceReference(
        providerId=source.provider_id,
        sourceRecordId=row.document_id,
        sourceUrl=source_url,
    )
    return StandardRecord(
        dataset=NEWS_DOCUMENT_DATASET.name,
        schemaVersion=NEWS_DOCUMENT_DATASET.schema_version,
        recordId=data.document_id,
        entityId=instrument_id or (related[0] if related else data.document_id),
        publishedAt=row.published_at,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.document_id,
            sourceUrl=source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="eastmoney-news-normalizer/1",
            sourceReferences=[source_ref],
            adjustments=adjustments,
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


def _news_ref_from_record(record: StandardRecord) -> NewsDocumentRef:
    data = NewsDocumentData.model_validate(record.data)
    return NewsDocumentRef(
        documentId=data.document_id,
        sourceDocumentId=data.source_document_id,
        title=data.title,
        important=data.important,
        summary=data.summary,
        publishedAt=data.published_at,
        sourceUrl=record.source.source_url,
        documentUrl=data.url,
        originalUrl=data.original_url,
        relatedInstruments=data.related_instruments,
        source=record.source,
        capturedAt=record.captured_at,
        sourceOccurrences=data.source_occurrences or [
            NewsSourceOccurrence(
                providerId=record.source.provider_id,
                sourceDocumentId=record.source.source_record_id or data.source_document_id,
                sourceUrl=record.source.source_url,
                documentUrl=data.url,
                publishedAt=data.published_at,
                capturedAt=record.captured_at,
            )
        ],
        provenance=record.provenance,
    )


def normalize_news_search(
    request: NewsSearchRequest,
    row: _ProviderNewsRow,
    *,
    source: Source,
) -> NewsDocumentRef:
    if not isinstance(request, NewsSearchRequest):
        raise ValueError("request must be a NewsSearchRequest")
    if row.instrument_id is not None and row.instrument_id != request.instrument_id:
        raise ValueError("provider returned news for a different instrument")
    return _news_ref_from_record(_news_record(row, source=source, instrument_id=request.instrument_id))


def normalize_news_document(
    ref: NewsDocumentRef,
    row: _ProviderNewsRow,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(ref, NewsDocumentRef):
        raise ValueError("ref must be a NewsDocumentRef")
    if ref.source.provider_id != source.provider_id:
        raise ValueError("document ref provider does not match the configured provider")
    if ref.source_document_id != row.document_id:
        raise ValueError("document ref sourceDocumentId does not match fetched content")
    if ref.document_id != _news_document_id(row):
        raise ValueError("document ref documentId does not match fetched content")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = NewsDocumentData(
        documentId=ref.document_id,
        sourceDocumentId=ref.source_document_id,
        title=ref.title,
        important=ref.important,
        summary=row.summary,
        contentText=row.content_text,
        publishedAt=ref.published_at,
        url=ref.document_url,
        originalUrl=ref.original_url,
        contentAvailable=row.content_text is not None,
        source=row.source_name,
        relatedInstruments=ref.related_instruments,
        sourceOccurrences=ref.source_occurrences,
    )
    return StandardRecord(
        dataset=NEWS_DOCUMENT_DATASET.name,
        schemaVersion=NEWS_DOCUMENT_DATASET.schema_version,
        recordId=ref.document_id,
        entityId=ref.related_instruments[0] if ref.related_instruments else ref.document_id,
        publishedAt=ref.published_at,
        capturedAt=row.captured_at,
        source=ref.source,
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=ref.provenance,
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "MarketNewsSearchRequest",
    "NEWS_DOCUMENT_DATASET",
    "NewsSourceOccurrence",
    "NewsDocumentData",
    "NewsDocumentRef",
    "NewsSearchRequest",
    "normalize_news_document",
    "normalize_news_search",
]
