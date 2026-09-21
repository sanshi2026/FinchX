"""The stable market.quote listing contract and record normalization."""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from pydantic import Field, field_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    Percentage,
    Price,
    Provenance,
    ProvenanceClass,
    Quality,
    QualityIssue,
    QualityIssueKind,
    Ratio,
    Shares,
    Source,
    StandardRecord,
    ValuationMultiple,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.instrument import InstrumentUniverse, InstrumentUniverseRequest
from finchx.entities import InstrumentId, InstrumentKind, Market, format_symbol


class MarketQuoteUniverseRequest(InstrumentUniverseRequest):
    """Request one market-wide quote snapshot."""

    pass


class MarketQuoteData(ContractModel):
    """One provider-neutral quote row for a canonical instrument."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    name: str | None = Field(default=None, min_length=1, pattern=r".*\S.*")
    price: Price
    price_change: Price | None = Field(
        default=None,
        alias="priceChange",
        description="Signed absolute price change in CNY per share.",
    )
    change_rate: Percentage | None = Field(default=None, alias="changeRate")
    change_rate_5d: Percentage | None = Field(
        default=None,
        alias="changeRate5d",
        description="Source-designated 5d price change, stored as a ratio fraction.",
    )
    change_rate_10d: Percentage | None = Field(
        default=None,
        alias="changeRate10d",
        description="Source-designated 10d price change, stored as a ratio fraction.",
    )
    change_rate_20d: Percentage | None = Field(
        default=None,
        alias="changeRate20d",
        description="Source-designated 20d price change, stored as a ratio fraction.",
    )
    change_rate_60d: Percentage | None = Field(
        default=None,
        alias="changeRate60d",
        description="Source-designated 60d price change, stored as a ratio fraction.",
    )
    change_rate_52w: Percentage | None = Field(
        default=None,
        alias="changeRate52w",
        description="Price change over the source-designated 52-week period, as a ratio fraction.",
    )
    change_rate_ytd: Percentage | None = Field(
        default=None,
        alias="changeRateYtd",
        description="Year-to-date price change, stored as a ratio fraction.",
    )
    amplitude: Percentage | None = Field(
        default=None,
        description="Intraday price amplitude, stored as a ratio fraction.",
    )
    volume_ratio: Ratio | None = Field(
        default=None,
        alias="volumeRatio",
        description="Non-negative volume ratio in times; 2.35 represents 2.35x.",
        json_schema_extra={"pattern": r"^(?:0|[1-9]\d*)(?:\.\d+)?$"},
    )
    volume: Shares | None = None
    amount: Amount | None = None
    turnover_rate: Percentage | None = Field(default=None, alias="turnoverRate")
    market_cap: Amount | None = Field(default=None, alias="marketCap")
    float_market_cap: Amount | None = Field(default=None, alias="floatMarketCap")
    pe_ttm: ValuationMultiple | None = Field(default=None, alias="peTtm")
    main_net_inflow: Amount | None = Field(default=None, alias="mainNetInflow")
    main_inflow: Amount | None = Field(default=None, alias="mainInflow")
    main_outflow: Amount | None = Field(default=None, alias="mainOutflow")
    main_inflow_5d: Amount | None = Field(default=None, alias="mainInflow5d")
    main_outflow_5d: Amount | None = Field(default=None, alias="mainOutflow5d")

    @field_validator("volume_ratio")
    @classmethod
    def _volume_ratio_is_nonnegative(cls, value: Ratio | None) -> Ratio | None:
        if value is not None and (value < 0 or (value.is_zero() and value.is_signed())):
            raise ValueError("volume ratio must not be negative")
        return value


MARKET_QUOTE_DATASET: DatasetDefinition[MarketQuoteUniverseRequest, MarketQuoteData] = DatasetDefinition(
    name="market.quote",
    schema_version="1.0",
    request_type=MarketQuoteUniverseRequest,
    data_type=MarketQuoteData,
)


@dataclass(frozen=True)
class _ProviderQuoteRow:
    """Typed provider-to-dataset handoff without source-specific field names."""

    data: MarketQuoteData
    source_record_id: str | None = None
    captured_at: datetime | None = None


def _quote_record_id(instrument_id: InstrumentId, captured_at: datetime) -> str:
    return f"{format_symbol(instrument_id)}@{captured_at.isoformat()}"


_QUOTE_OPTIONAL_FIELDS = (
    "name",
    "price_change",
    "change_rate",
    "volume",
    "amount",
    "turnover_rate",
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "change_rate_5d",
    "change_rate_10d",
    "change_rate_20d",
    "change_rate_60d",
    "change_rate_52w",
    "change_rate_ytd",
    "amplitude",
    "volume_ratio",
    "main_net_inflow",
    "main_inflow",
    "main_outflow",
    "main_inflow_5d",
    "main_outflow_5d",
)


def _quote_quality(quote: MarketQuoteData) -> Quality:
    missing_fields = [
        field_name
        for field_name in _QUOTE_OPTIONAL_FIELDS
        if getattr(quote, field_name) is None
    ]
    return Quality(
        issues=[
            QualityIssue(
                kind=QualityIssueKind.PARTIAL,
                detail=f"Optional quote fields unavailable: {', '.join(missing_fields)}",
            )
        ]
        if missing_fields
        else []
    )


def _normalize_quote_rows(
    request: MarketQuoteUniverseRequest,
    rows: Sequence[_ProviderQuoteRow],
    *,
    source: Source,
    captured_at: datetime,
) -> tuple[StandardRecord, ...]:
    if request.universe is not InstrumentUniverse.CN_A_SHARE:
        raise ValueError(f"unsupported quote universe: {request.universe!r}")

    records: list[StandardRecord] = []
    seen: set[str] = set()
    for row in rows:
        quote = row.data
        instrument_id = quote.instrument_id
        if instrument_id.market is not Market.CN_A or instrument_id.kind is not InstrumentKind.EQUITY:
            raise ValueError("CN_A_SHARE quote listing contains a non-A-share-equity identity")
        identity_key = format_symbol(instrument_id)
        if identity_key in seen:
            raise ValueError(f"quote listing contains duplicate identity: {identity_key}")
        seen.add(identity_key)

        quality = _quote_quality(quote)
        record_source = Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=source.source_url,
        )
        record_captured_at = row.captured_at or captured_at
        records.append(
            StandardRecord(
                dataset=MARKET_QUOTE_DATASET.name,
                schemaVersion=MARKET_QUOTE_DATASET.schema_version,
                recordId=_quote_record_id(instrument_id, record_captured_at),
                entityId=instrument_id,
                capturedAt=record_captured_at,
                source=record_source,
                status=DataStatus.LIVE,
                quality=quality,
                provenance=Provenance(
                    recordClass=ProvenanceClass.STANDARDIZED,
                    transformationVersion="market-quote-normalizer/1",
                ),
                data=quote.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
