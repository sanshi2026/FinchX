"""Public contracts for iWenCai screening, search, and report details.

The provider returns one :class:`~finchx.contracts.StandardRecord` per
selection row or search hit.  The models in this module therefore describe a
single business record, matching the shape used by FinchX's other list
datasets; they are not aggregate ``rows``/``articles`` envelopes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyUrl, Field, field_validator

from finchx.contracts import Amount, Percentage, Price, Shares
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import InstrumentId


CookieInput = str | dict[str, str]


class IwencaiSelectionRequest(ContractModel):
    """A natural-language stock screener query using a user session cookie."""

    query: str = Field(min_length=1, max_length=2_000)
    cookies: CookieInput
    user_agent: str | None = Field(default=None, alias="userAgent", max_length=1_000)
    page_size: int = Field(default=100, alias="pageSize", ge=1, le=100)
    max_pages: int = Field(default=100, alias="maxPages", ge=1, le=100)

    @field_validator("query")
    @classmethod
    def query_must_be_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must be non-empty text")
        return value

    @field_validator("cookies")
    @classmethod
    def cookies_must_be_non_empty(cls, value: CookieInput) -> CookieInput:
        if isinstance(value, str) and not value.strip():
            raise ValueError("cookies must be non-empty")
        if isinstance(value, dict) and not value:
            raise ValueError("cookies must be non-empty")
        return value


class IwencaiSelectionData(ContractModel):
    """One normalized stock row returned by the iWenCai screener."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str | None = Field(default=None, min_length=1)
    price: Price | None = None
    change_rate: Percentage | None = Field(default=None, alias="changeRate")
    amplitude: Percentage | None = None
    volume: Shares | None = None
    amount: Amount | None = None
    turnover_rate: Percentage | None = Field(default=None, alias="turnoverRate")
    extra_fields: dict[str, Any] = Field(default_factory=dict, alias="extraFields")


class IwencaiSearchRequest(ContractModel):
    """A SkillHub semantic search request for reports/news/announcements."""

    query: str = Field(min_length=1, max_length=2_000)
    channel: Literal["report", "announcement", "news"] = "report"
    size: int = Field(default=50, ge=1, le=50)
    cookies: CookieInput | None = None
    api_key: str | None = Field(default=None, alias="apiKey", max_length=2_000)
    deduplicate: bool = True

    @field_validator("query")
    @classmethod
    def query_must_be_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must be non-empty text")
        return value


class IwencaiSearchData(ContractModel):
    """One normalized semantic-search hit."""

    uid: str | None = None
    title: str = ""
    published_at: str | None = Field(default=None, alias="publishedAt")
    url: str | None = Field(default=None, description="Report detail page URL, when supplied by the search result.")
    score: float = 0.0
    extra_fields: dict[str, Any] = Field(default_factory=dict, alias="extraFields")


class IwencaiReportDetailRequest(ContractModel):
    """Fetch the linked report page returned by iWenCai search."""

    url: str = Field(
        min_length=1,
        max_length=4_000,
        description="The report URL from a report-channel iwencai.search hit; it must contain duid.",
    )
    cookies: CookieInput = Field(description="Caller-provided logged-in iWenCai/THS Cookie header.")
    uid: str | None = Field(default=None, max_length=500, description="Optional report UID from the search hit.")
    title: str | None = Field(default=None, max_length=2_000, description="Optional title from the search hit, used as a fallback.")
    published_at: str | None = Field(default=None, alias="publishedAt", max_length=100, description="Optional publication date from the search hit, used as a fallback.")
    user_agent: str | None = Field(default=None, alias="userAgent", max_length=1_000, description="Optional browser User-Agent for the report detail request.")

    @field_validator("url")
    @classmethod
    def url_must_be_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("url must be non-empty text")
        return value

    @field_validator("cookies")
    @classmethod
    def cookies_must_be_non_empty(cls, value: CookieInput) -> CookieInput:
        if isinstance(value, str) and not value.strip():
            raise ValueError("cookies must be non-empty")
        if isinstance(value, dict) and not value:
            raise ValueError("cookies must be non-empty")
        return value


class IwencaiReportDetailData(ContractModel):
    """Normalized content fetched from a linked iWenCai report page."""

    document_id: str = Field(alias="documentId", min_length=1, description="FinchX-owned report document identifier.")
    source_document_id: str = Field(alias="sourceDocumentId", min_length=1, description="Source report UID.")
    title: str = Field(default="", description="Report title.")
    content_text: str = Field(alias="contentText", min_length=1, description="Readable report text returned by the report detail endpoint.")
    published_at: datetime | None = Field(default=None, alias="publishedAt", description="Publication date returned by the report detail endpoint.")
    content_available: bool = Field(alias="contentAvailable", description="Whether readable report text is available.")
    related_instruments: list[InstrumentId] = Field(default_factory=list, alias="relatedInstruments", description="Related securities when provided by the source.")
    url: AnyUrl = Field(description="Report detail page URL.")
    original_url: AnyUrl | None = Field(default=None, alias="originalUrl", description="Publisher or source URL when returned by the report detail endpoint.")
    organization: str | None = Field(default=None, description="Research organization.")
    analyst: str | None = Field(default=None, description="Report analyst or researcher.")
    file_extension: str | None = Field(default=None, alias="fileExtension", description="Source report file extension, when available.")
    source_created_at: str | None = Field(default=None, alias="sourceCreatedAt", description="Source creation timestamp as returned by the report endpoint.")
    extra_fields: dict[str, Any] = Field(default_factory=dict, alias="extraFields", description="Additional report metadata returned by the source.")


# Compatibility names for callers that imported the original nested models.
# They now correctly describe one row/hit, while FetchResult.to_dicts() emits
# one dictionary per StandardRecord.
IwencaiSelectionRow = IwencaiSelectionData
IwencaiSearchHit = IwencaiSearchData


IWENCAI_SELECTION_DATASET = DatasetDefinition(
    name="iwencai.selection",
    schema_version="1.0",
    request_type=IwencaiSelectionRequest,
    data_type=IwencaiSelectionData,
)

IWENCAI_SEARCH_DATASET = DatasetDefinition(
    name="iwencai.search",
    schema_version="1.0",
    request_type=IwencaiSearchRequest,
    data_type=IwencaiSearchData,
)

IWENCAI_REPORT_DETAIL_DATASET = DatasetDefinition(
    name="iwencai.report_detail",
    schema_version="1.0",
    request_type=IwencaiReportDetailRequest,
    data_type=IwencaiReportDetailData,
)


__all__ = [
    "CookieInput",
    "IWENCAI_REPORT_DETAIL_DATASET",
    "IWENCAI_SEARCH_DATASET",
    "IWENCAI_SELECTION_DATASET",
    "IwencaiSearchData",
    "IwencaiSearchHit",
    "IwencaiSearchRequest",
    "IwencaiReportDetailData",
    "IwencaiReportDetailRequest",
    "IwencaiSelectionData",
    "IwencaiSelectionRequest",
    "IwencaiSelectionRow",
]
