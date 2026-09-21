"""The stable market.ranking contract with criterion-discriminated values."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Sequence, TypeAlias

from pydantic import Field

from finchx.contracts import (
    Amount,
    DataStatus,
    Percentage,
    Provenance,
    ProvenanceClass,
    Shares,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.instrument import InstrumentUniverse
from finchx.datasets.market_quote import MarketQuoteData, _quote_quality
from finchx.entities import InstrumentId, InstrumentKind, Market, format_symbol


class RankingCriterion(str, Enum):
    TURNOVER = "turnover"
    CHANGE_PERCENT = "change_percent"
    VOLUME = "volume"


class RankingDirection(str, Enum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


RankingLimit = Annotated[int, Field(strict=True, ge=1)]
RankingPosition = Annotated[int, Field(strict=True, ge=1)]


class MarketRankingRequest(ContractModel):
    universe: InstrumentUniverse
    criterion: RankingCriterion
    direction: RankingDirection
    limit: RankingLimit | None


class TurnoverRankingMetric(ContractModel):
    criterion: Literal["turnover"]
    value: Amount


class ChangePercentRankingMetric(ContractModel):
    criterion: Literal["change_percent"]
    value: Percentage


class VolumeRankingMetric(ContractModel):
    criterion: Literal["volume"]
    value: Shares


RankingMetric: TypeAlias = Annotated[
    TurnoverRankingMetric | ChangePercentRankingMetric | VolumeRankingMetric,
    Field(discriminator="criterion"),
]


class MarketRankingData(MarketQuoteData):
    """One ranked instrument with the full quote payload and ranking metadata."""

    universe: InstrumentUniverse
    direction: RankingDirection
    position: RankingPosition
    metric: RankingMetric


MARKET_RANKING_DATASET: DatasetDefinition[MarketRankingRequest, MarketRankingData] = DatasetDefinition(
    name="market.ranking",
    schema_version="1.0",
    request_type=MarketRankingRequest,
    data_type=MarketRankingData,
)


@dataclass(frozen=True)
class _ProviderRankingRow:
    """Typed ranking handoff with a full quote and ranking metric."""

    data: MarketQuoteData
    metric: RankingMetric
    source_record_id: str | None = None
    captured_at: datetime | None = None

    @property
    def instrument_id(self) -> InstrumentId:
        return self.data.instrument_id


def _ranking_record_id(
    instrument_id: InstrumentId,
    criterion: RankingCriterion,
    direction: RankingDirection,
    captured_at: datetime,
) -> str:
    return (
        f"{criterion.value}:{direction.value}:{format_symbol(instrument_id)}"
        f"@{captured_at.isoformat()}"
    )


def _normalize_ranking_rows(
    request: MarketRankingRequest,
    rows: Sequence[_ProviderRankingRow],
    *,
    source: Source,
    captured_at: datetime,
) -> tuple[StandardRecord, ...]:
    if request.universe is not InstrumentUniverse.CN_A_SHARE:
        raise ValueError(f"unsupported ranking universe: {request.universe!r}")
    if request.limit is not None and len(rows) > request.limit:
        raise ValueError("provider returned more ranking rows than the requested limit")

    records: list[StandardRecord] = []
    seen: set[str] = set()
    for position, row in enumerate(rows, start=1):
        quote = row.data
        instrument_id = quote.instrument_id
        if instrument_id.market is not Market.CN_A or instrument_id.kind is not InstrumentKind.EQUITY:
            raise ValueError("CN_A_SHARE ranking contains a non-A-share-equity identity")
        identity_key = format_symbol(instrument_id)
        if identity_key in seen:
            raise ValueError(f"ranking contains duplicate identity: {identity_key}")
        seen.add(identity_key)
        if row.metric.criterion != request.criterion.value:
            raise ValueError(
                "provider ranking metric does not match the requested criterion"
            )
        quote_metric_value = {
            "turnover": quote.amount,
            "change_percent": quote.change_rate,
            "volume": quote.volume,
        }[request.criterion.value]
        if row.metric.value != quote_metric_value:
            raise ValueError("provider ranking metric does not match the quote field")

        payload_values = quote.model_dump(mode="python")
        payload_values.update(
            universe=request.universe,
            direction=request.direction,
            position=position,
            metric=row.metric,
        )
        payload = MarketRankingData.model_validate(payload_values)
        record_source = Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=source.source_url,
        )
        record_captured_at = row.captured_at or captured_at
        records.append(
            StandardRecord(
                dataset=MARKET_RANKING_DATASET.name,
                schemaVersion=MARKET_RANKING_DATASET.schema_version,
                recordId=_ranking_record_id(
                    instrument_id,
                    request.criterion,
                    request.direction,
                    record_captured_at,
                ),
                entityId=instrument_id,
                capturedAt=record_captured_at,
                source=record_source,
                status=DataStatus.LIVE,
                quality=_quote_quality(quote),
                provenance=Provenance(
                    recordClass=ProvenanceClass.STANDARDIZED,
                    transformationVersion="market-ranking-normalizer/1",
                ),
                data=payload.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
