"""EastMoney market-wide price-move breadth contract and normalization."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from pydantic import Field, model_validator

from finchx.contracts import DataStatus, Provenance, ProvenanceClass, Quality, Source, StandardRecord
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition


class MarketBreadthBucket(str, Enum):
    LIMIT_DOWN = "limit_down"
    DOWN_OVER_10_PERCENT = "down_over_10_percent"
    DOWN_8_TO_9_PERCENT = "down_8_to_9_percent"
    DOWN_7_TO_8_PERCENT = "down_7_to_8_percent"
    DOWN_6_TO_7_PERCENT = "down_6_to_7_percent"
    DOWN_5_TO_6_PERCENT = "down_5_to_6_percent"
    DOWN_4_TO_5_PERCENT = "down_4_to_5_percent"
    DOWN_3_TO_4_PERCENT = "down_3_to_4_percent"
    DOWN_2_TO_3_PERCENT = "down_2_to_3_percent"
    DOWN_1_TO_2_PERCENT = "down_1_to_2_percent"
    DOWN_0_TO_1_PERCENT = "down_0_to_1_percent"
    UNCHANGED = "unchanged"
    UP_0_TO_1_PERCENT = "up_0_to_1_percent"
    UP_1_TO_2_PERCENT = "up_1_to_2_percent"
    UP_2_TO_3_PERCENT = "up_2_to_3_percent"
    UP_3_TO_4_PERCENT = "up_3_to_4_percent"
    UP_4_TO_5_PERCENT = "up_4_to_5_percent"
    UP_5_TO_6_PERCENT = "up_5_to_6_percent"
    UP_6_TO_7_PERCENT = "up_6_to_7_percent"
    UP_7_TO_8_PERCENT = "up_7_to_8_percent"
    UP_8_TO_9_PERCENT = "up_8_to_9_percent"
    UP_OVER_10_PERCENT = "up_over_10_percent"
    LIMIT_UP = "limit_up"


_BUCKETS_BY_SOURCE_CODE = {
    -11: MarketBreadthBucket.LIMIT_DOWN,
    -10: MarketBreadthBucket.DOWN_OVER_10_PERCENT,
    **{
        code: MarketBreadthBucket[f"DOWN_{abs(code) - 1}_TO_{abs(code)}_PERCENT"]
        for code in range(-9, 0)
    },
    0: MarketBreadthBucket.UNCHANGED,
    **{
        code: MarketBreadthBucket[f"UP_{code - 1}_TO_{code}_PERCENT"]
        for code in range(1, 10)
    },
    10: MarketBreadthBucket.UP_OVER_10_PERCENT,
    11: MarketBreadthBucket.LIMIT_UP,
}
_BUCKET_ORDER = tuple(_BUCKETS_BY_SOURCE_CODE.values())


class MarketBreadthRequest(ContractModel):
    """Request the current observed EastMoney breadth snapshot."""


class MarketBreadthDistributionEntry(ContractModel):
    bucket: MarketBreadthBucket
    count: int = Field(strict=True, ge=0, description="Number of listed stocks in this return bucket.")


class MarketBreadthData(ContractModel):
    """A current market breadth snapshot with the full source distribution."""

    trade_date: date = Field(alias="tradeDate", description="Trade date reported by EastMoney.")
    advancing: int = Field(strict=True, ge=0)
    declining: int = Field(strict=True, ge=0)
    unchanged: int = Field(strict=True, ge=0)
    total: int = Field(strict=True, ge=0)
    limit_up_count: int = Field(alias="limitUpCount", strict=True, ge=0)
    limit_down_count: int = Field(alias="limitDownCount", strict=True, ge=0)
    up_over_10_percent_count: int = Field(alias="upOver10PercentCount", strict=True, ge=0)
    down_over_10_percent_count: int = Field(alias="downOver10PercentCount", strict=True, ge=0)
    distribution: list[MarketBreadthDistributionEntry] = Field(min_length=23, max_length=23)

    @model_validator(mode="after")
    def distribution_and_totals_must_match(self) -> MarketBreadthData:
        counts = Counter(entry.bucket for entry in self.distribution)
        if set(counts) != set(_BUCKET_ORDER) or any(count != 1 for count in counts.values()):
            raise ValueError("distribution must contain each of the 23 breadth buckets exactly once")
        by_bucket = {entry.bucket: entry.count for entry in self.distribution}
        if self.advancing != sum(
            by_bucket[bucket]
            for bucket in _BUCKET_ORDER
            if bucket.value.startswith("up_") or bucket is MarketBreadthBucket.LIMIT_UP
        ):
            raise ValueError("advancing must equal all positive move buckets")
        if self.declining != sum(
            by_bucket[bucket]
            for bucket in _BUCKET_ORDER
            if bucket.value.startswith("down_") or bucket is MarketBreadthBucket.LIMIT_DOWN
        ):
            raise ValueError("declining must equal all negative move buckets")
        if self.unchanged != by_bucket[MarketBreadthBucket.UNCHANGED]:
            raise ValueError("unchanged must equal the flat bucket")
        if self.total != self.advancing + self.declining + self.unchanged:
            raise ValueError("total must equal advancing + declining + unchanged")
        if self.limit_up_count != by_bucket[MarketBreadthBucket.LIMIT_UP]:
            raise ValueError("limitUpCount must equal the limit-up bucket")
        if self.limit_down_count != by_bucket[MarketBreadthBucket.LIMIT_DOWN]:
            raise ValueError("limitDownCount must equal the limit-down bucket")
        if self.up_over_10_percent_count != by_bucket[MarketBreadthBucket.UP_OVER_10_PERCENT]:
            raise ValueError("upOver10PercentCount must equal the >10% bucket")
        if self.down_over_10_percent_count != by_bucket[MarketBreadthBucket.DOWN_OVER_10_PERCENT]:
            raise ValueError("downOver10PercentCount must equal the <-10% bucket")
        if [entry.bucket for entry in self.distribution] != list(_BUCKET_ORDER):
            raise ValueError("distribution must be ordered from limit-down to limit-up")
        return self


MARKET_BREADTH_DATASET: DatasetDefinition[MarketBreadthRequest, MarketBreadthData] = DatasetDefinition(
    name="market.breadth",
    schema_version="1.0",
    request_type=MarketBreadthRequest,
    data_type=MarketBreadthData,
)


@dataclass(frozen=True)
class _ProviderBreadth:
    trade_date: date
    counts_by_source_code: dict[int, int]
    source_record_id: str
    source_url: str
    captured_at: datetime


def normalize_market_breadth(
    request: MarketBreadthRequest,
    row: _ProviderBreadth,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, MarketBreadthRequest):
        raise ValueError("request must be a MarketBreadthRequest")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    if set(row.counts_by_source_code) != set(_BUCKETS_BY_SOURCE_CODE):
        raise ValueError("provider breadth result does not contain all 23 source buckets")
    counts = row.counts_by_source_code
    distribution = [
        MarketBreadthDistributionEntry(bucket=_BUCKETS_BY_SOURCE_CODE[code], count=counts[code])
        for code in sorted(_BUCKETS_BY_SOURCE_CODE)
    ]
    advancing = sum(counts[code] for code in range(1, 12))
    declining = sum(counts[code] for code in range(-11, 0))
    unchanged = counts[0]
    data = MarketBreadthData(
        tradeDate=row.trade_date,
        advancing=advancing,
        declining=declining,
        unchanged=unchanged,
        total=advancing + declining + unchanged,
        limitUpCount=counts[11],
        limitDownCount=counts[-11],
        upOver10PercentCount=counts[10],
        downOver10PercentCount=counts[-10],
        distribution=distribution,
    )
    return StandardRecord(
        dataset=MARKET_BREADTH_DATASET.name,
        schemaVersion=MARKET_BREADTH_DATASET.schema_version,
        recordId=f"eastmoney-breadth:{row.trade_date.isoformat()}",
        entityId="market:cn_a",
        capturedAt=row.captured_at,
        source=Source(
            providerId=source.provider_id,
            sourceRecordId=row.source_record_id,
            sourceUrl=row.source_url,
        ),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="eastmoney-breadth-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )
