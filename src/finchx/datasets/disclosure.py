"""Stable contract and normalization for EastMoney individual-stock disclosures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pydantic import AnyUrl, Field, field_validator

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
from finchx.datasets.document_common import TimedDocumentSearchRequest
from finchx.entities import InstrumentId


class DisclosureSearchRequest(TimedDocumentSearchRequest):
    categories: list[str] | None = None

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("categories must contain at least one category name")
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("categories must contain non-empty text")
        return list(dict.fromkeys(normalized))


class DisclosureCategory(ContractModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: str = "eastmoney"


class DisclosureDocumentRef(ContractModel):
    """Serializable list metadata used to fetch one full disclosure."""

    document_id: str = Field(alias="documentId", min_length=1)
    source_document_id: str = Field(alias="sourceDocumentId", min_length=1)
    title: str = Field(min_length=1)
    published_at: datetime = Field(alias="publishedAt")
    notice_date: date = Field(alias="noticeDate")
    categories: list[DisclosureCategory]
    related_instruments: list[InstrumentId] = Field(alias="relatedInstruments")
    source_url: AnyUrl = Field(alias="sourceUrl")
    original_document_url: AnyUrl = Field(alias="originalDocumentUrl")
    source_type: str | None = Field(default=None, alias="sourceType")
    source: Source
    captured_at: datetime = Field(alias="capturedAt")
    provenance: Provenance


class DisclosureAttachment(ContractModel):
    sequence: int | None = Field(default=None, alias="sequence", ge=1)
    size: int | None = Field(default=None, ge=0)
    attachment_type: str | None = Field(default=None, alias="attachmentType")
    url: AnyUrl
    web_url: AnyUrl | None = Field(default=None, alias="webUrl")


class DisclosureDocumentData(ContractModel):
    document_id: str = Field(alias="documentId", min_length=1)
    source_document_id: str = Field(alias="sourceDocumentId", min_length=1)
    title: str = Field(min_length=1)
    content_text: str | None = Field(default=None, alias="contentText")
    notice_date: date = Field(alias="noticeDate")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    categories: list[DisclosureCategory]
    related_instruments: list[InstrumentId] = Field(alias="relatedInstruments")
    content_available: bool = Field(alias="contentAvailable")
    pdf_available: bool = Field(alias="pdfAvailable")
    original_document_url: AnyUrl = Field(alias="originalDocumentUrl")
    attachments: list[DisclosureAttachment]
    source_type: str | None = Field(default=None, alias="sourceType")


DISCLOSURE_DOCUMENT_DATASET: DatasetDefinition[
    DisclosureSearchRequest, DisclosureDocumentData
] = DatasetDefinition(
    name="disclosure.document",
    schema_version="1.0",
    request_type=DisclosureSearchRequest,
    data_type=DisclosureDocumentData,
)


@dataclass(frozen=True)
class _ProviderDisclosureCategory:
    code: str
    name: str


@dataclass(frozen=True)
class _ProviderDisclosureSecurity:
    instrument_id: InstrumentId
    short_name: str
    ann_type: str
    inner_code: str


@dataclass(frozen=True)
class _ProviderDisclosureAttachment:
    sequence: int | None
    size: int | None
    attachment_type: str | None
    url: str
    web_url: str | None


@dataclass(frozen=True)
class _ProviderDisclosureRow:
    document_id: str
    title: str
    notice_date: date
    published_candidate: datetime | None
    display_time: datetime | None
    ei_time: datetime | None
    sort_date: datetime | None
    categories: tuple[_ProviderDisclosureCategory, ...]
    securities: tuple[_ProviderDisclosureSecurity, ...]
    source_type: str | None
    content_text: str | None
    attachments: tuple[_ProviderDisclosureAttachment, ...]
    source_url: str
    captured_at: datetime


def _disclosure_record(
    row: _ProviderDisclosureRow,
    *,
    source: Source,
    requested_instrument: InstrumentId | None,
) -> StandardRecord:
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    related = [item.instrument_id for item in row.securities]
    if requested_instrument is not None and requested_instrument not in related:
        raise ValueError("provider returned a disclosure for a different instrument")
    data = DisclosureDocumentData(
        documentId=f"eastmoney:disclosure:{row.document_id}",
        sourceDocumentId=row.document_id,
        title=row.title,
        contentText=row.content_text,
        noticeDate=row.notice_date,
        publishedAt=row.published_candidate,
        categories=[
            DisclosureCategory(code=item.code, name=item.name) for item in row.categories
        ],
        relatedInstruments=related,
        contentAvailable=row.content_text is not None,
        pdfAvailable=bool(row.attachments),
        originalDocumentUrl=f"https://data.eastmoney.com/notices/detail/{row.document_id}.html",
        attachments=[
            DisclosureAttachment(
                sequence=item.sequence,
                size=item.size,
                attachmentType=item.attachment_type,
                url=item.url,
                webUrl=item.web_url,
            )
            for item in row.attachments
        ],
        sourceType=row.source_type,
    )
    source_url = row.source_url or source.source_url
    source_ref = SourceReference(
        providerId=source.provider_id,
        sourceRecordId=row.document_id,
        sourceUrl=source_url,
    )
    entity_id = requested_instrument or (related[0] if related else data.document_id)
    return StandardRecord(
        dataset=DISCLOSURE_DOCUMENT_DATASET.name,
        schemaVersion=DISCLOSURE_DOCUMENT_DATASET.schema_version,
        recordId=data.document_id,
        entityId=entity_id,
        publishedAt=data.published_at,
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
            transformationVersion="eastmoney-disclosure-normalizer/1",
            sourceReferences=[source_ref],
            adjustments=[
                Adjustment(
                    name="eastmoney-disclosure-time-semantics",
                    details={
                        "publishedAtBasis": "display_time",
                        "sourceRecordedAtBasis": "EastMoney internal record time",
                        "sourceRecordedAt": row.ei_time.isoformat() if row.ei_time is not None else None,
                        "sortDate": row.sort_date.isoformat() if row.sort_date is not None else None,
                    },
                )
            ],
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


def _disclosure_ref_from_record(record: StandardRecord) -> DisclosureDocumentRef:
    data = DisclosureDocumentData.model_validate(record.data)
    return DisclosureDocumentRef(
        documentId=data.document_id,
        sourceDocumentId=data.source_document_id,
        title=data.title,
        publishedAt=data.published_at,
        noticeDate=data.notice_date,
        categories=data.categories,
        relatedInstruments=data.related_instruments,
        sourceUrl=record.source.source_url,
        originalDocumentUrl=data.original_document_url,
        sourceType=data.source_type,
        source=record.source,
        capturedAt=record.captured_at,
        provenance=record.provenance,
    )


def normalize_disclosure_search(
    request: DisclosureSearchRequest,
    row: _ProviderDisclosureRow,
    *,
    source: Source,
) -> DisclosureDocumentRef:
    if not isinstance(request, DisclosureSearchRequest):
        raise ValueError("request must be a DisclosureSearchRequest")
    return _disclosure_ref_from_record(
        _disclosure_record(row, source=source, requested_instrument=request.instrument_id)
    )


def normalize_disclosure_document(
    ref: DisclosureDocumentRef,
    row: _ProviderDisclosureRow,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(ref, DisclosureDocumentRef):
        raise ValueError("ref must be a DisclosureDocumentRef")
    if ref.source.provider_id != source.provider_id:
        raise ValueError("document ref provider does not match the configured provider")
    if ref.source_document_id != row.document_id:
        raise ValueError("document ref sourceDocumentId does not match fetched content")
    if ref.document_id != f"eastmoney:disclosure:{row.document_id}":
        raise ValueError("document ref documentId does not match fetched content")
    if row.notice_date != ref.notice_date:
        raise ValueError("document ref noticeDate does not match fetched content")
    recorded_at = next(
        (
            adjustment.details.get("sourceRecordedAt")
            for adjustment in ref.provenance.adjustments
            if adjustment.name == "eastmoney-disclosure-time-semantics"
        ),
        None,
    )
    if row.ei_time is not None and recorded_at is not None:
        try:
            recorded_at_value = datetime.fromisoformat(recorded_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("document ref provenance has an invalid EastMoney sourceRecordedAt") from exc
        if recorded_at_value != row.ei_time:
            raise ValueError("document ref source-recorded time does not match fetched content")
    content_related = [item.instrument_id for item in row.securities]
    if content_related and not any(item in ref.related_instruments for item in content_related):
        raise ValueError("document ref relatedInstruments do not match fetched content")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = DisclosureDocumentData(
        documentId=ref.document_id,
        sourceDocumentId=ref.source_document_id,
        title=ref.title,
        contentText=row.content_text,
        noticeDate=ref.notice_date,
        publishedAt=ref.published_at,
        categories=ref.categories,
        relatedInstruments=ref.related_instruments,
        contentAvailable=row.content_text is not None,
        pdfAvailable=bool(row.attachments),
        originalDocumentUrl=ref.original_document_url,
        attachments=[
            DisclosureAttachment(
                sequence=item.sequence,
                size=item.size,
                attachmentType=item.attachment_type,
                url=item.url,
                webUrl=item.web_url,
            )
            for item in row.attachments
        ],
        sourceType=ref.source_type,
    )
    return StandardRecord(
        dataset=DISCLOSURE_DOCUMENT_DATASET.name,
        schemaVersion=DISCLOSURE_DOCUMENT_DATASET.schema_version,
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
    "DISCLOSURE_DOCUMENT_DATASET",
    "DisclosureAttachment",
    "DisclosureCategory",
    "DisclosureDocumentData",
    "DisclosureDocumentRef",
    "DisclosureSearchRequest",
    "normalize_disclosure_document",
    "normalize_disclosure_search",
]
