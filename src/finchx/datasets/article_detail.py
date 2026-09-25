"""Standard article-detail contracts for provider-neutral research evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date as Date, datetime
import hashlib
import json
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import AnyUrl, Field, field_validator, model_validator

from finchx.contracts import (
    Adjustment,
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Percentage,
    Source,
    SourceReference,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.hotlist import HotArticleRelatedStock
from finchx.entities import InstrumentId


ArticleKind = Literal["news", "zhibo"]
ArticleFetchMethod = Literal["detail_api", "embedded_state", "dom", "zhibo_html"]
_NEWS_PATH = re.compile(r"^/(?P<date>\d{8})/c(?P<content_id>\d+)\.shtml$", re.IGNORECASE)
_ZHIBO_PATHS = (
    re.compile(r"^/m/zhibo/pid_(\d+)\.shtml$", re.IGNORECASE),
    re.compile(r"^/pid_(\d+)\.shtml$", re.IGNORECASE),
)
_MARKDOWN_URL = re.compile(r"^\s*\[[^\]]*\]\((https?://[^()\s]+)\)\s*$", re.IGNORECASE)
_ARTICLE_NEWS_HOSTS = frozenset({"news.10jqka.com.cn", "stock.10jqka.com.cn"})
_ARTICLE_ID = re.compile(r"^\d{6,20}$")
_IMAGE_WITH_SOURCE = re.compile(r"<img\b[^>]*\bsrc\s*=", re.IGNORECASE)


def unwrap_markdown_url(value: str) -> str:
    """Unwrap a full Markdown link only when a field expects a URL."""

    value = value.strip()
    match = _MARKDOWN_URL.fullmatch(value)
    return match.group(1) if match else value


def normalize_http_url(value: Any) -> str | None:
    """Return a bare absolute HTTP(S) URL, unwrapping presentation markup."""

    if not isinstance(value, str) or not value.strip():
        return None
    candidate = unwrap_markdown_url(value)
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    try:
        parsed = urlsplit(candidate)
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return candidate


def article_url_details(url: str) -> tuple[ArticleKind, str, str, Date | None]:
    """Validate a supported article URL and return its route identity.

    Only known news hosts and the community host are accepted. Tracking
    query/fragment components are omitted from the canonical URL. Community
    mobile share links resolve to the same desktop URL and cache identity.
    """

    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty Tonghuashun article URL")
    normalized = normalize_http_url(url)
    if normalized is None:
        raise ValueError("url must be an absolute HTTP(S) Tonghuashun article URL")
    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme.casefold() not in {"http", "https"} or parsed.username or parsed.password:
        raise ValueError("url must be an HTTP(S) Tonghuashun article URL")
    if parsed.port is not None:
        default_port = 443 if parsed.scheme.casefold() == "https" else 80
        if parsed.port != default_port:
            raise ValueError("url must use the default HTTP(S) port")
    if host == "t.10jqka.com.cn":
        for pattern in _ZHIBO_PATHS:
            match = pattern.fullmatch(parsed.path)
            if match:
                content_id = match.group(1)
                if not _ARTICLE_ID.fullmatch(content_id):
                    break
                return "zhibo", f"https://t.10jqka.com.cn/pid_{content_id}.shtml", content_id, None
        raise ValueError("unsupported Tonghuashun community article URL")
    if host in _ARTICLE_NEWS_HOSTS:
        match = _NEWS_PATH.fullmatch(parsed.path)
        if match:
            content_id = match.group("content_id")
            if not _ARTICLE_ID.fullmatch(content_id):
                raise ValueError("article URL contains an invalid content ID")
            date_text = match.group("date")
            try:
                # Python 3.10 does not accept compact YYYYMMDD in fromisoformat.
                article_date = Date(
                    int(date_text[:4]), int(date_text[4:6]), int(date_text[6:8])
                )
            except ValueError as exc:
                raise ValueError("article URL contains an invalid news date") from exc
            return (
                "news",
                f"https://{host}/{date_text}/c{content_id}.shtml",
                content_id,
                article_date,
            )
    raise ValueError("unsupported Tonghuashun article URL")


def classify_article_url(url: str) -> tuple[ArticleKind, str, str]:
    """Return ``(kind, canonical_url, content_id)`` for a supported URL."""

    kind, canonical_url, content_id, _ = article_url_details(url)
    return kind, canonical_url, content_id


class ArticleDetailRequest(ContractModel):
    """A validated public Tonghuashun news or community article URL."""

    url: str = Field(
        strict=True,
        min_length=1,
        description=(
            "Public Tonghuashun article URL. News URLs use /YYYYMMDD/c<ID>.shtml; "
            "community URLs use /pid_<ID>.shtml or /m/zhibo/pid_<ID>.shtml."
        ),
    )

    @field_validator("url")
    @classmethod
    def validate_and_canonicalize_url(cls, value: str) -> str:
        return article_url_details(value)[1]

    @property
    def content_id(self) -> str:
        return article_url_details(self.url)[2]

    @property
    def content_type(self) -> ArticleKind:
        return article_url_details(self.url)[0]

    @property
    def date(self) -> Date | None:
        return article_url_details(self.url)[3]


class ArticleRelatedStock(ContractModel):
    """A merged article association with explicit contributing sources."""

    symbol: str = Field(
        min_length=1,
        max_length=32,
        description="Original source security code, retained verbatim.",
    )
    instrument_id: InstrumentId | None = Field(
        default=None,
        alias="instrumentId",
        description="FinchX identity when the security and market can be classified; otherwise null.",
    )
    name: str = Field(min_length=1, description="Source-provided security name.")
    change_pct: Percentage | None = Field(
        default=None,
        alias="changePct",
        description="Price change as a ratio fraction; source percentage points are divided by 100.",
    )
    source_market: str | None = Field(
        default=None,
        alias="sourceMarket",
        description="Original Tonghuashun stockMarket marker; not a FinchX market enum.",
    )
    sources: list[Literal["hotlist", "detail"]] = Field(
        default_factory=list,
        description="Input sources that contributed this association.",
    )


class ArticleDetailData(ContractModel):
    """CamelCase business payload carried by an ``articles.detail`` record."""

    content_id: str = Field(
        alias="contentId",
        min_length=1,
        description="Tonghuashun article identifier from the source URL.",
    )
    content_type: ArticleKind = Field(
        alias="contentType",
        description="Article category: ordinary news or community zhibo.",
    )
    title: str | None = Field(default=None, description="Article title.")
    content_html: str | None = Field(
        default=None,
        alias="contentHtml",
        description="Sanitized article-body HTML, excluding comments and disclaimers.",
    )
    content_text: str | None = Field(
        default=None,
        alias="contentText",
        description=(
            "Plain-text extraction of the sanitized article body; may be empty when the body contains a sourced image."
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        alias="publishedAt",
        description="Timezone-aware publication time when supplied by the source.",
    )
    source_name: str | None = Field(
        default=None,
        alias="sourceName",
        description="Publisher or media name supplied by the source.",
    )
    author: str | None = Field(default=None, description="Article author or byline.")
    source_url: AnyUrl | None = Field(
        default=None,
        alias="sourceUrl",
        description="Upstream API or page URL used to retrieve the article.",
    )
    page_url: AnyUrl | None = Field(
        default=None,
        alias="pageUrl",
        description="Canonical public article page URL derived from the input URL.",
    )
    ai_summary: str | None = Field(
        default=None,
        alias="aiSummary",
        description="Source-provided AI summary, when available.",
    )
    disclaimer: str | None = Field(
        default=None,
        description="Disclaimer text extracted separately from the article body.",
    )
    comments: list[str] = Field(
        default_factory=list,
        description="Community comments extracted separately from the article body.",
    )
    related_stocks: list[ArticleRelatedStock] = Field(
        default_factory=list,
        alias="relatedStocks",
        description="Stock associations reported by the article detail source.",
    )
    fetch_method: ArticleFetchMethod | None = Field(
        default=None,
        alias="fetchMethod",
        description="Extraction path used for the article body.",
    )
    raw_hash: str | None = Field(
        default=None,
        alias="rawHash",
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the raw API article body or fetched HTML page.",
    )
    content_available: bool = Field(
        alias="contentAvailable",
        description="Whether a usable article title and body were retrieved.",
    )
    error_code: str | None = Field(
        default=None,
        alias="errorCode",
        description="Categorized fetch failure code when content is unavailable.",
    )
    error_message: str | None = Field(
        default=None,
        alias="errorMessage",
        description="Short source or parsing failure reason when content is unavailable.",
    )

    @model_validator(mode="after")
    def validate_availability(self) -> ArticleDetailData:
        if self.content_available:
            if not self.title or not self.title.strip():
                raise ValueError("available article details require a non-empty title")
            if not self.content_html or not self.content_html.strip():
                raise ValueError("available article details require contentHtml")
            if not self.content_text or not self.content_text.strip():
                if not is_usable_article_body(self.content_html or "", self.content_text or ""):
                    raise ValueError("available article details require readable text or a sourced image")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("available article details cannot carry a fetch error")
        elif not self.error_code:
            raise ValueError("unavailable article details require an errorCode")
        return self


ARTICLE_DETAIL_DATASET: DatasetDefinition[ArticleDetailRequest, ArticleDetailData] = (
    DatasetDefinition(
        name="articles.detail",
        schema_version="1.0",
        request_type=ArticleDetailRequest,
        data_type=ArticleDetailData,
    )
)


def is_usable_article_body(content_html: str, content_text: str | None) -> bool:
    """Accept readable text or a sanitized, sourced image as an article body."""

    return bool((content_text or "").strip() or _IMAGE_WITH_SOURCE.search(content_html))


def _stock_identity(row: Mapping[str, Any]) -> str:
    symbol = str(row.get("symbol") or "").strip().upper()
    market = str(row.get("sourceMarket", row.get("source_market")) or "").strip()
    if symbol and market:
        return f"source:{market}:{symbol}"
    instrument = row.get("instrumentId", row.get("instrument_id"))
    if instrument is not None:
        if isinstance(instrument, Mapping):
            return "instrument:" + json.dumps(
                dict(instrument), sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
        return "instrument:" + str(instrument)
    if symbol:
        return f"symbol:{symbol}"
    return "name:" + str(row.get("name") or "").strip().casefold()


def merge_related_stocks(
    list_stocks: list[HotArticleRelatedStock] | list[Mapping[str, Any]],
    detail_stocks: list[Mapping[str, Any]],
) -> list[ArticleRelatedStock]:
    """Merge associations by instrument identity and retain source labels."""

    merged: dict[str, dict[str, Any]] = {}
    for label, rows in (("hotlist", list_stocks), ("detail", detail_stocks)):
        for candidate in rows:
            raw = candidate.model_dump(mode="json", by_alias=True) if isinstance(candidate, HotArticleRelatedStock) else dict(candidate)
            symbol = str(raw.get("symbol") or raw.get("code") or "").strip()
            name = str(raw.get("name") or raw.get("securityName") or symbol).strip()
            if not symbol or not name:
                continue
            row = {
                "symbol": symbol,
                "instrumentId": raw.get("instrumentId", raw.get("instrument_id")),
                "name": name,
                "changePct": raw.get("changePct", raw.get("change_pct", raw.get("rise_and_fall"))),
                "sourceMarket": raw.get("sourceMarket", raw.get("source_market", raw.get("stockMarket"))),
                "sources": [label],
            }
            key = _stock_identity(row)
            current = merged.get(key)
            if current is None:
                merged[key] = row
                continue
            if label not in current["sources"]:
                current["sources"].append(label)
            # Keep list-side quote data when available; detail fills gaps.
            for field in ("instrumentId", "changePct", "sourceMarket"):
                if current.get(field) is None and row.get(field) is not None:
                    current[field] = row[field]
            if not current.get("name") and name:
                current["name"] = name
    return [ArticleRelatedStock.model_validate(row) for row in merged.values()]


def normalize_article_detail(
    request: ArticleDetailRequest,
    raw: Mapping[str, Any],
    *,
    source: Source,
) -> StandardRecord:
    """Normalize a provider parse into FinchX's standard record envelope."""

    if not isinstance(request, ArticleDetailRequest):
        raise ValueError("request must be an ArticleDetailRequest")
    if not isinstance(raw, Mapping):
        raise ValueError("article provider result must be a mapping")
    raw_id = str(raw.get("contentId") or raw.get("content_id") or request.content_id)
    if raw_id != request.content_id:
        raise ValueError("provider article contentId does not match the request")
    content_html = str(raw.get("contentHtml") or "")
    content_text = str(raw.get("contentText") or "")
    if not is_usable_article_body(content_html, content_text):
        raise ValueError("article provider result must contain readable text or a sourced image")
    content_type = raw.get("contentType") or raw.get("content_type")
    if content_type is not None and content_type != request.content_type:
        raise ValueError("article provider contentType does not match the request URL")
    content_type = request.content_type
    page_url_value = normalize_http_url(raw.get("pageUrl"))
    if page_url_value:
        page_kind, page_canonical, page_id, _ = article_url_details(page_url_value)
        if page_kind != request.content_type or page_id != request.content_id:
            raise ValueError("article provider pageUrl does not match the request URL")
        page_url_value = page_canonical
    published_at = raw.get("publishedAt")
    if published_at is not None and (
        not isinstance(published_at, datetime)
        or published_at.tzinfo is None
        or published_at.utcoffset() is None
    ):
        raise ValueError("article publishedAt must be a timezone-aware datetime")
    captured_at = raw.get("capturedAt")
    if not isinstance(captured_at, datetime) or captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("article capturedAt must be a timezone-aware datetime")

    raw_hash = hashlib.sha256(content_html.encode("utf-8")).hexdigest()
    data = ArticleDetailData(
        contentId=request.content_id,
        contentType=content_type,
        title=str(raw.get("title") or "").strip() or None,
        contentHtml=content_html,
        contentText=content_text.strip(),
        publishedAt=published_at,
        sourceName=raw.get("sourceName"),
        author=raw.get("author"),
        sourceUrl=normalize_http_url(raw.get("sourceUrl")),
        pageUrl=page_url_value,
        aiSummary=raw.get("aiSummary"),
        disclaimer=raw.get("disclaimer"),
        comments=raw.get("comments") or [],
        relatedStocks=merge_related_stocks([], list(raw.get("relatedStocks") or [])),
        fetchMethod=raw.get("fetchMethod"),
        rawHash=raw.get("rawHash") or raw_hash,
        contentAvailable=True,
    )
    if not data.title:
        raise ValueError("article source did not provide a title")
    record_source = Source(
        providerId=source.provider_id,
        sourceRecordId=request.content_id,
        sourceUrl=normalize_http_url(raw.get("sourceUrl")) or source.source_url,
    )
    references = [
        SourceReference(
            providerId=source.provider_id,
            sourceRecordId=request.content_id,
            sourceUrl=normalize_http_url(raw.get("sourceUrl")) or source.source_url,
        )
    ]
    return StandardRecord(
        dataset=ARTICLE_DETAIL_DATASET.name,
        schemaVersion=ARTICLE_DETAIL_DATASET.schema_version,
        recordId=f"tonghuashun:article:{request.content_id}",
        entityId=f"tonghuashun:article:{request.content_id}",
        eventAt=published_at,
        publishedAt=published_at,
        capturedAt=captured_at,
        source=record_source,
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="ths-article-detail-normalizer/1",
            sourceReferences=references,
            adjustments=[
                Adjustment(
                    name="article-body-extracted",
                    version="1",
                    details={"fetchMethod": data.fetch_method},
                )
            ],
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "ARTICLE_DETAIL_DATASET",
    "ArticleDetailData",
    "ArticleDetailRequest",
    "ArticleFetchMethod",
    "ArticleKind",
    "ArticleRelatedStock",
    "article_url_details",
    "classify_article_url",
    "is_usable_article_body",
    "merge_related_stocks",
    "normalize_article_detail",
    "normalize_http_url",
    "unwrap_markdown_url",
]
