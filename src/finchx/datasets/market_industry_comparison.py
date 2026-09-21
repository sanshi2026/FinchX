"""Tencent hypm industry comparison snapshot contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

_CNY_PER_100M = Decimal("100000000")

from pydantic import Field, model_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    StandardRecord,
    ValuationMultiple,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.datasets.market_instrument_sector_snapshot import (
    _validate_sector_instrument,
)
from finchx.entities import InstrumentId, format_symbol


class MarketIndustryComparisonRequest(ContractModel):
    """Request Tencent hypm comparison values for one fully identified equity."""

    instrument_id: InstrumentId = Field(alias="instrumentId")

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketIndustryComparisonRequest:
        _validate_sector_instrument(self.instrument_id)
        return self


class IndustryIdentity(ContractModel):
    provider_namespace: Literal["tencent_hypm"] = Field(alias="providerNamespace")
    provider_industry_id: str = Field(alias="providerIndustryId", min_length=1, pattern=r".*\S.*")
    name: str = Field(min_length=1, pattern=r".*\S.*")


class IndustryComparisonValues(ContractModel):
    price_earnings: ValuationMultiple | None = Field(default=None, alias="priceEarnings")
    earnings_per_share: Amount | None = Field(
        default=None,
        alias="earningsPerShare",
        description="Tencent mgsy, in CNY per share; reporting-period semantics are not supplied here.",
    )
    market_capitalization: Amount | None = Field(
        default=None,
        alias="marketCapitalization",
        description="Tencent zsz converted from 100 million CNY to CNY.",
    )


class IndustryComparisonRanks(ContractModel):
    price_earnings_rank: int | None = Field(default=None, alias="priceEarningsRank", ge=1)
    earnings_per_share_rank: int | None = Field(default=None, alias="earningsPerShareRank", ge=1)
    market_capitalization_rank: int | None = Field(default=None, alias="marketCapitalizationRank", ge=1)


class IndustryAggregate(IndustryComparisonValues):
    count: int | None = Field(default=None, ge=0)


class MarketAggregate(IndustryComparisonValues):
    pass


class MarketIndustryComparisonData(ContractModel):
    instrument_id: InstrumentId = Field(alias="instrumentId")
    industry: IndustryIdentity
    instrument_values: IndustryComparisonValues = Field(alias="instrumentValues")
    industry_ranks: IndustryComparisonRanks = Field(alias="industryRanks")
    industry_aggregate: IndustryAggregate = Field(alias="industryAggregate")
    market_aggregate: MarketAggregate = Field(alias="marketAggregate")

    @model_validator(mode="after")
    def validate_instrument(self) -> MarketIndustryComparisonData:
        _validate_sector_instrument(self.instrument_id)
        return self


MARKET_INDUSTRY_COMPARISON_DATASET: DatasetDefinition[
    MarketIndustryComparisonRequest, MarketIndustryComparisonData
] = DatasetDefinition(
    name="market.industry_comparison",
    schema_version="1.0",
    request_type=MarketIndustryComparisonRequest,
    data_type=MarketIndustryComparisonData,
)


@dataclass(frozen=True)
class _ProviderIndustryComparison:
    instrument_id: InstrumentId
    provider_industry_id: str
    industry_name: str
    instrument_price_earnings: Decimal | None
    instrument_earnings_per_share: Decimal | None
    instrument_market_cap_100m: Decimal | None
    price_earnings_rank: int | None
    earnings_per_share_rank: int | None
    market_capitalization_rank: int | None
    industry_count: int | None
    industry_price_earnings_average: Decimal | None
    industry_earnings_per_share_average: Decimal | None
    industry_market_cap_100m_average: Decimal | None
    market_price_earnings_average: Decimal | None
    market_earnings_per_share_average: Decimal | None
    market_market_cap_100m_average: Decimal | None
    source_record_id: str
    source_url: str
    captured_at: datetime


def _aware_capture_time(captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")


def normalize_industry_comparison(
    request: MarketIndustryComparisonRequest,
    row: _ProviderIndustryComparison,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, MarketIndustryComparisonRequest):
        raise ValueError("request must be a MarketIndustryComparisonRequest")
    _validate_sector_instrument(request.instrument_id)
    if row.instrument_id != request.instrument_id:
        raise ValueError("provider returned industry comparison for a different instrument")
    _aware_capture_time(row.captured_at)
    data = MarketIndustryComparisonData(
        instrumentId=request.instrument_id,
        industry=IndustryIdentity(
            providerNamespace="tencent_hypm",
            providerIndustryId=row.provider_industry_id,
            name=row.industry_name,
        ),
        instrumentValues=IndustryComparisonValues(
            priceEarnings=row.instrument_price_earnings,
            earningsPerShare=row.instrument_earnings_per_share,
            marketCapitalization=(None if row.instrument_market_cap_100m is None else row.instrument_market_cap_100m * _CNY_PER_100M),
        ),
        industryRanks=IndustryComparisonRanks(
            priceEarningsRank=row.price_earnings_rank,
            earningsPerShareRank=row.earnings_per_share_rank,
            marketCapitalizationRank=row.market_capitalization_rank,
        ),
        industryAggregate=IndustryAggregate(
            count=row.industry_count,
            priceEarnings=row.industry_price_earnings_average,
            earningsPerShare=row.industry_earnings_per_share_average,
            marketCapitalization=(None if row.industry_market_cap_100m_average is None else row.industry_market_cap_100m_average * _CNY_PER_100M),
        ),
        marketAggregate=MarketAggregate(
            priceEarnings=row.market_price_earnings_average,
            earningsPerShare=row.market_earnings_per_share_average,
            marketCapitalization=(None if row.market_market_cap_100m_average is None else row.market_market_cap_100m_average * _CNY_PER_100M),
        ),
    )
    return StandardRecord(
        dataset=MARKET_INDUSTRY_COMPARISON_DATASET.name,
        schemaVersion=MARKET_INDUSTRY_COMPARISON_DATASET.schema_version,
        recordId=f"{format_symbol(request.instrument_id)}@{row.captured_at.isoformat()}",
        entityId=request.instrument_id,
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url or source.source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="tencent-hypm-industry-comparison-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )
