"""Tonghuashun hot-list Dataset contracts and standard-record normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, RootModel, model_validator

from finchx.contracts import (
    DataStatus, Percentage, Provenance, ProvenanceClass, Quality, QualityIssue,
    QualityIssueKind, Source, SourceReference, StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol


HotlistLimit = Annotated[int, Field(strict=True, ge=1)]


class HotStocksRequest(ContractModel):
    category: Literal["popular", "rising", "new", "technical", "value", "trend"] = "popular"
    period: Literal["1h", "24h"] | None = None
    limit: HotlistLimit = 20

    @model_validator(mode="after")
    def fixed_day_categories(self) -> "HotStocksRequest":
        if self.category not in {"popular", "rising"} and self.period == "1h":
            raise ValueError("new, technical, value, and trend categories only support period='24h'")
        return self


class HotSectorsRequest(ContractModel):
    sector_type: Literal["concept", "industry", "index"] = Field(default="concept", alias="sectorType")
    limit: HotlistLimit = 20


class HotConvertibleBondsRequest(ContractModel):
    limit: HotlistLimit = 20


class HotEtfsRequest(ContractModel):
    category: Literal["popular", "t0", "price_limit_20", "cross_border", "commodity"] = "popular"
    limit: HotlistLimit = 20


class HotContentRequest(ContractModel):
    content_type: Literal["topic", "comment", "article"] = Field(default="topic", alias="contentType")
    limit: HotlistLimit = 20


class HotStockData(ContractModel):
    rank: int = Field(ge=1)
    symbol: str = Field(min_length=6, max_length=6)
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str
    category: Literal["popular", "rising", "new", "technical", "value", "trend"]
    period: Literal["1h", "24h"]
    change_pct: Percentage | None = Field(default=None, alias="changePct")
    heat: Decimal | None = None
    rank_change: int | None = Field(default=None, alias="rankChange")
    concept_tags: list[str] = Field(default_factory=list, alias="conceptTags")
    popularity_tag: str | None = Field(default=None, alias="popularityTag")
    analysis_title: str | None = Field(default=None, alias="analysisTitle")
    analysis: str | None = None
    search_count: int | None = Field(default=None, alias="searchCount")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    pe: Decimal | None = None


class HotSectorData(ContractModel):
    rank: int = Field(ge=1)
    sector_code: str = Field(alias="sectorCode", min_length=1)
    name: str
    sector_type: Literal["concept", "industry", "index"] = Field(alias="sectorType")
    change_pct: Percentage | None = Field(default=None, alias="changePct")
    heat: Decimal | None = None
    rank_change: int | None = Field(default=None, alias="rankChange")
    tag: str | None = None
    hot_tag: str | None = Field(default=None, alias="hotTag")
    related_etf_symbol: str | None = Field(default=None, alias="relatedEtfSymbol")
    related_etf_name: str | None = Field(default=None, alias="relatedEtfName")
    related_etf_change_pct: Percentage | None = Field(default=None, alias="relatedEtfChangePct")


class HotConvertibleBondData(ContractModel):
    rank: int = Field(ge=1)
    symbol: str = Field(min_length=6, max_length=6)
    name: str
    change_pct: Percentage | None = Field(default=None, alias="changePct")
    heat: Decimal | None = None


class HotEtfData(ContractModel):
    rank: int = Field(ge=1)
    symbol: str = Field(min_length=6, max_length=6)
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str
    change_pct: Percentage | None = Field(default=None, alias="changePct")
    heat: Decimal
    tags: list[str] = Field(default_factory=list)


class HotRelatedStock(ContractModel):
    symbol: str = Field(min_length=6, max_length=6)
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str
    change_pct: Percentage | None = Field(default=None, alias="changePct")


class HotTopicData(ContractModel):
    content_type: Literal["topic"] = Field(alias="contentType")
    rank: int = Field(ge=1)
    title: str
    summary: str | None = None
    heat: Decimal | None = None
    url: str | None = None
    related_stocks: list[HotRelatedStock] = Field(default_factory=list, alias="relatedStocks")


class HotCommentData(ContractModel):
    content_type: Literal["comment"] = Field(alias="contentType")
    rank: int = Field(ge=1)
    symbol: str = Field(min_length=6, max_length=6)
    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str
    change_pct: Percentage | None = Field(default=None, alias="changePct")
    heat: Decimal | None = None
    text: str | None = None
    likes: int | None = None
    content_id: str | None = Field(default=None, alias="contentId")


class HotArticleRelatedStock(ContractModel):
    """Article associations can reference markets outside FinchX's CN_A identity model."""

    symbol: str = Field(min_length=1, max_length=32, description="Original source instrument code, retained verbatim.")
    instrument_id: InstrumentId | None = Field(
        default=None,
        alias="instrumentId",
        description="A classified CN_A equity or ETF identity when the source market and code range are verified; otherwise null.",
    )
    name: str
    change_pct: Percentage | None = Field(default=None, alias="changePct")
    source_market: str | None = Field(
        default=None,
        alias="sourceMarket",
        description="Original Tonghuashun stockMarket identifier; not a FinchX market enum.",
    )


class HotArticleData(ContractModel):
    content_type: Literal["article"] = Field(alias="contentType")
    rank: int = Field(ge=1)
    title: str
    heat: Decimal | None = None
    like_ratio: Percentage | None = Field(default=None, alias="likeRatio")
    comment_ratio: Percentage | None = Field(default=None, alias="commentRatio")
    content_id: str | None = Field(default=None, alias="contentId")
    url: str | None = None
    related_stocks: list[HotArticleRelatedStock] = Field(
        default_factory=list,
        alias="relatedStocks",
        description="Article associations preserve source codes, names, and stockMarket markers; instrumentId is null if market or security type cannot be represented.",
    )


HotContentItem: TypeAlias = Annotated[
    HotTopicData | HotCommentData | HotArticleData,
    Field(discriminator="content_type"),
]


class HotContentData(RootModel[HotContentItem]):
    """A schema-generating discriminated union for content榜 shapes."""


HOT_STOCKS_DATASET: DatasetDefinition[HotStocksRequest, HotStockData] = DatasetDefinition(
    "hotlist.stocks", "1.0", HotStocksRequest, HotStockData
)
HOT_SECTORS_DATASET: DatasetDefinition[HotSectorsRequest, HotSectorData] = DatasetDefinition(
    "hotlist.sectors", "1.0", HotSectorsRequest, HotSectorData
)
HOT_CONVERTIBLE_BONDS_DATASET: DatasetDefinition[HotConvertibleBondsRequest, HotConvertibleBondData] = DatasetDefinition(
    "hotlist.convertible_bonds", "1.0", HotConvertibleBondsRequest, HotConvertibleBondData
)
HOT_ETFS_DATASET: DatasetDefinition[HotEtfsRequest, HotEtfData] = DatasetDefinition(
    "hotlist.etfs", "1.0", HotEtfsRequest, HotEtfData
)
HOT_CONTENT_DATASET: DatasetDefinition[HotContentRequest, HotContentData] = DatasetDefinition(
    "hotlist.content", "1.0", HotContentRequest, HotContentData
)

_HOTLIST_DATASETS = {
    HOT_STOCKS_DATASET.name: HOT_STOCKS_DATASET,
    HOT_SECTORS_DATASET.name: HOT_SECTORS_DATASET,
    HOT_CONVERTIBLE_BONDS_DATASET.name: HOT_CONVERTIBLE_BONDS_DATASET,
    HOT_ETFS_DATASET.name: HOT_ETFS_DATASET,
    HOT_CONTENT_DATASET.name: HOT_CONTENT_DATASET,
}

_ARTICLE_RATIO_PARTIAL_DETAIL = (
    "Source like/comment ratio units are unverified; values were omitted."
)
_ARTICLE_UNSUPPORTED_RELATED_DETAIL = (
    "Some article associations use non-CN_A or unverified source markets; their source symbol, name, and stockMarket were retained without an InstrumentId."
)
_ARTICLE_STOCK_CLASSIFICATION = {
    "17": (Exchange.SSE, (("60", "68"), InstrumentKind.EQUITY), (("50", "51", "52", "56", "58"), InstrumentKind.ETF)),
    "33": (Exchange.SZSE, (("00", "30"), InstrumentKind.EQUITY), (("15", "16", "18"), InstrumentKind.ETF)),
}


def _article_related_instrument(symbol: str, source_market: object) -> InstrumentId | None:
    """Build only market-and-kind identities supported by verified THS source fields."""
    if len(symbol) != 6 or not symbol.isascii() or not symbol.isdigit():
        return None
    classification = _ARTICLE_STOCK_CLASSIFICATION.get(str(source_market))
    if classification is None:
        return None
    exchange, *security_kinds = classification
    for prefixes, kind in security_kinds:
        if symbol.startswith(prefixes):
            return _instrument(symbol, kind=kind, exchange=exchange)
    return None


def _instrument(
    symbol: str,
    *,
    kind: InstrumentKind = InstrumentKind.EQUITY,
    exchange: Exchange | None = None,
    infer_exchange: bool = True,
) -> InstrumentId:
    if not isinstance(symbol, str) or len(symbol) != 6 or not symbol.isascii() or not symbol.isdigit():
        raise ValueError(f"hotlist returned an invalid six-digit symbol: {symbol!r}")
    if exchange is None and infer_exchange:
        if symbol.startswith(("60", "68", "50", "51", "52", "56", "58")):
            exchange = Exchange.SSE
        elif symbol.startswith(("00", "30", "15", "16", "18")):
            exchange = Exchange.SZSE
        elif symbol.startswith(("4", "8", "9")):
            exchange = Exchange.BSE
        else:
            raise ValueError(f"hotlist symbol has no supported CN exchange mapping: {symbol!r}")
    return InstrumentId(code=symbol, market=Market.CN_A, kind=kind, exchange=exchange)


def _fraction(value: object) -> object:
    if value is None:
        return None
    # The supported change fields are source percentage points. Article ratio
    # fields are handled separately and remain None until their units are verified.
    if isinstance(value, Decimal):
        return value / Decimal(100)
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return Decimal(str(value)) / Decimal(100)
    raise ValueError("percentage source value must be numeric")


def _record_data(
    dataset: str,
    data: dict[str, object],
    *,
    instrument_exchange: object = None,
    infer_exchange: bool = True,
) -> ContractModel:
    if dataset == HOT_STOCKS_DATASET.name:
        values = dict(data)
        values["instrumentId"] = _instrument(str(values["symbol"]))
        values["changePct"] = _fraction(values.get("changePct"))
        return HotStockData.model_validate(values)
    if dataset == HOT_SECTORS_DATASET.name:
        values = dict(data)
        values["changePct"] = _fraction(values.get("changePct"))
        values["relatedEtfChangePct"] = _fraction(values.get("relatedEtfChangePct"))
        return HotSectorData.model_validate(values)
    if dataset == HOT_CONVERTIBLE_BONDS_DATASET.name:
        values = dict(data)
        values["changePct"] = _fraction(values.get("changePct"))
        return HotConvertibleBondData.model_validate(values)
    if dataset == HOT_ETFS_DATASET.name:
        values = dict(data)
        exchange = Exchange(instrument_exchange) if instrument_exchange is not None else None
        values["instrumentId"] = _instrument(
            str(values["symbol"]), kind=InstrumentKind.ETF, exchange=exchange,
            infer_exchange=infer_exchange,
        )
        values["changePct"] = _fraction(values.get("changePct"))
        return HotEtfData.model_validate(values)
    if dataset == HOT_CONTENT_DATASET.name:
        values = dict(data)
        if values.get("contentType") == "article":
            related = []
            for stock in values.get("relatedStocks", []):
                source_market = stock.get("sourceMarket")
                symbol = str(stock["symbol"])
                instrument_id = _article_related_instrument(symbol, source_market)
                related.append({
                    **stock,
                    "instrumentId": instrument_id,
                    "changePct": _fraction(stock.get("changePct")),
                })
            values["relatedStocks"] = related
        else:
            values["relatedStocks"] = [
                {**stock, "instrumentId": _instrument(str(stock["symbol"])), "changePct": _fraction(stock.get("changePct"))}
                for stock in values.get("relatedStocks", [])
            ]
        if values.get("contentType") == "comment":
            values["instrumentId"] = _instrument(str(values["symbol"]))
            values["changePct"] = _fraction(values.get("changePct"))
            values.pop("relatedStocks", None)
        if values.get("contentType") == "article":
            # Never let unverified upstream units enter a FinchX Percentage field.
            values["likeRatio"] = None
            values["commentRatio"] = None
            item = HotArticleData.model_validate(values)
        elif values.get("contentType") == "comment":
            item = HotCommentData.model_validate(values)
        else:
            item = HotTopicData.model_validate(values)
        return item
    raise ValueError(f"unsupported hotlist dataset: {dataset}")


def normalize_hotlist(
    request: ContractModel,
    rows: list[dict[str, object]],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    """Validate Provider mappings and build standard records for one hotlist Dataset."""
    dataset_name = next(
        (name for name, definition in _HOTLIST_DATASETS.items() if isinstance(request, definition.request_type)),
        None,
    )
    if dataset_name is None:
        raise ValueError("request is not a registered hotlist request")
    definition = _HOTLIST_DATASETS[dataset_name]
    records: list[StandardRecord] = []
    seen: set[str] = set()
    for row in rows:
        raw_data = row.get("data")
        metadata = row.get("__finchx", {})
        if not isinstance(raw_data, dict) or not isinstance(metadata, dict):
            raise ValueError("hotlist Provider row must contain data and __finchx metadata objects")
        data = _record_data(
            dataset_name,
            raw_data,
            instrument_exchange=metadata.get("instrumentExchange"),
            infer_exchange=metadata.get("inferInstrumentExchange", True),
        )
        values = data.model_dump(mode="json", by_alias=True)
        rank = values["rank"]
        entity_id: InstrumentId | str
        if dataset_name == HOT_STOCKS_DATASET.name or dataset_name == HOT_ETFS_DATASET.name:
            entity_id = data.instrument_id  # type: ignore[attr-defined]
        elif dataset_name == HOT_CONVERTIBLE_BONDS_DATASET.name:
            entity_id = f"CN_CONVERTIBLE_BOND:{values['symbol']}"
        elif dataset_name == HOT_SECTORS_DATASET.name:
            entity_id = f"THS_SECTOR:{values['sectorType']}:{values['sectorCode']}"
        elif values["contentType"] == "comment":
            entity_id = data.instrument_id  # type: ignore[attr-defined]
        else:
            entity_id = str(metadata.get("sourceRecordId") or f"{values['contentType']}:{rank}")
        record_id = str(metadata.get("recordId") or f"{dataset_name}:{entity_id}:{rank}")
        if record_id in seen:
            raise ValueError(f"duplicate hotlist record identity: {record_id}")
        seen.add(record_id)
        captured_at = metadata.get("capturedAt") or datetime.now(timezone.utc)
        if not isinstance(captured_at, datetime):
            raise ValueError("hotlist capture timestamp must be a datetime")
        partial_details = []
        if metadata.get("partial"):
            detail = metadata.get("partialDetail") or "Optional hotlist enrichment data was unavailable."
            partial_details.append(str(detail))
        if dataset_name == HOT_CONTENT_DATASET.name and values.get("contentType") == "article":
            partial_details.append(_ARTICLE_RATIO_PARTIAL_DETAIL)
            if any(stock.get("instrumentId") is None for stock in values.get("relatedStocks", [])):
                partial_details.append(_ARTICLE_UNSUPPORTED_RELATED_DETAIL)
        issues = []
        if partial_details:
            issues.append(QualityIssue(
                kind=QualityIssueKind.PARTIAL,
                detail=" ".join(dict.fromkeys(partial_details)),
            ))
        records.append(StandardRecord(
            dataset=definition.name,
            schemaVersion=definition.schema_version,
            recordId=record_id,
            entityId=entity_id,
            capturedAt=captured_at,
            source=Source(
                providerId=source.provider_id,
                sourceRecordId=str(metadata.get("sourceRecordId") or record_id),
                sourceUrl=str(metadata.get("sourceUrl") or source.source_url),
            ),
            status=DataStatus.LIVE,
            quality=Quality(issues=issues),
            provenance=Provenance(
                recordClass=ProvenanceClass.STANDARDIZED,
                transformationVersion="ths-hotlist-normalizer/1",
                sourceReferences=[
                    SourceReference.model_validate(reference)
                    for reference in metadata.get("sourceReferences", [])
                ],
            ),
            data=values,
        ))
    if len(records) > request.limit:  # type: ignore[attr-defined]
        raise ValueError("Provider returned more hotlist records than requested")
    return tuple(records)


__all__ = [
    "HOT_CONTENT_DATASET", "HOT_CONVERTIBLE_BONDS_DATASET", "HOT_ETFS_DATASET",
    "HOT_SECTORS_DATASET", "HOT_STOCKS_DATASET", "HotArticleData",
    "HotArticleRelatedStock", "HotCommentData", "HotContentData", "HotContentRequest", "HotConvertibleBondData",
    "HotConvertibleBondsRequest", "HotEtfData", "HotEtfsRequest", "HotRelatedStock",
    "HotSectorData", "HotSectorsRequest", "HotStockData", "HotStocksRequest",
    "HotTopicData", "normalize_hotlist",
]
