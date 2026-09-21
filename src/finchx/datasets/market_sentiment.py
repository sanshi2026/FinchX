"""Aigupiao market sentiment snapshot contract and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator

from finchx.contracts import (
    Amount,
    DataStatus,
    Percentage,
    Provenance,
    ProvenanceClass,
    Quality,
    QualityIssue,
    QualityIssueKind,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.contracts.units import DecimalString
from finchx.datasets.definition import DatasetDefinition


class MarketSentimentRequest(ContractModel):
    """Request one current Aigupiao market sentiment snapshot."""


class MarketSentimentData(ContractModel):
    """Source-defined short-term market sentiment metrics."""

    market_temperature: DecimalString = Field(
        alias="marketTemperature",
        description="Aigupiao source-defined sentiment temperature; not a physical temperature or ratio.",
    )
    total_turnover: Amount | None = Field(default=None, alias="totalTurnover")
    forecasted_turnover: Amount | None = Field(
        default=None,
        alias="forecastedTurnover",
        description="Source forecast, not observed turnover.",
    )
    turnover_change_amount: Amount | None = Field(
        default=None,
        alias="turnoverChangeAmount",
        description="Source-reported change in turnover amount versus the prior day.",
    )
    blast_break_ratio: Percentage | None = Field(
        default=None,
        alias="blastBreakRatio",
        description="Source-defined ratio; FinchX does not reproduce the denominator.",
    )
    previous_limit_up_break_change_ratio: Percentage | None = Field(
        default=None,
        alias="previousLimitUpBreakChangeRatio",
        description="Source-defined previous broken-limit performance ratio.",
    )
    stop_trading_count: int = Field(alias="stopTradingCount", strict=True, ge=0)
    one_limit_up_count: int = Field(alias="oneLimitUpCount", strict=True, ge=0)
    two_limit_up_count: int = Field(alias="twoLimitUpCount", strict=True, ge=0)
    three_limit_up_count: int = Field(alias="threeLimitUpCount", strict=True, ge=0)
    high_limit_up_count: int = Field(alias="highLimitUpCount", strict=True, ge=0)
    two_limit_up_promotion_ratio: Percentage | None = Field(
        default=None,
        alias="twoLimitUpPromotionRatio",
        description="Source-defined promotion ratio; FinchX does not reproduce the denominator.",
    )
    three_limit_up_promotion_ratio: Percentage | None = Field(
        default=None,
        alias="threeLimitUpPromotionRatio",
        description="Source-defined promotion ratio; FinchX does not reproduce the denominator.",
    )
    high_limit_up_promotion_ratio: Percentage | None = Field(
        default=None,
        alias="highLimitUpPromotionRatio",
        description="Source-defined promotion ratio; FinchX does not reproduce the denominator.",
    )
    previous_limit_up_theme_change_ratio: Percentage | None = Field(
        default=None,
        alias="previousLimitUpThemeChangeRatio",
        description="Source-defined previous limit-up group performance ratio.",
    )
    previous_consecutive_limit_up_theme_change_ratio: Percentage | None = Field(
        default=None,
        alias="previousConsecutiveLimitUpThemeChangeRatio",
        description="Source-defined previous consecutive-limit-up group performance ratio.",
    )

    @field_validator("market_temperature")
    @classmethod
    def temperature_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("market temperature must be finite")
        return value


MARKET_SENTIMENT_DATASET: DatasetDefinition[MarketSentimentRequest, MarketSentimentData] = DatasetDefinition(
    name="market.sentiment_snapshot",
    schema_version="1.0",
    request_type=MarketSentimentRequest,
    data_type=MarketSentimentData,
)


@dataclass(frozen=True)
class _ProviderMarketSentiment:
    market_temperature: Decimal
    total_turnover_cny: Decimal | None
    forecasted_turnover_cny: Decimal | None
    turnover_change_amount_cny: Decimal | None
    blast_break_percent_points: Decimal | None
    previous_limit_up_break_change_percent_points: Decimal | None
    stop_trading_count: int
    one_limit_up_count: int
    two_limit_up_count: int
    three_limit_up_count: int
    high_limit_up_count: int
    two_limit_up_promotion_percent_points: Decimal | None
    three_limit_up_promotion_percent_points: Decimal | None
    high_limit_up_promotion_percent_points: Decimal | None
    previous_limit_up_theme_change_percent_points: Decimal | None
    previous_consecutive_limit_up_theme_change_percent_points: Decimal | None
    raw_payload: dict[str, object]
    source_url: str
    captured_at: datetime


def normalize_market_sentiment(
    request: MarketSentimentRequest,
    row: _ProviderMarketSentiment,
    *,
    source: Source,
) -> StandardRecord:
    if not isinstance(request, MarketSentimentRequest):
        raise ValueError("request must be a MarketSentimentRequest")
    if row.captured_at.tzinfo is None or row.captured_at.utcoffset() is None:
        raise ValueError("provider returned a naive captured_at timestamp")
    data = MarketSentimentData(
        marketTemperature=row.market_temperature,
        totalTurnover=row.total_turnover_cny,
        forecastedTurnover=row.forecasted_turnover_cny,
        turnoverChangeAmount=row.turnover_change_amount_cny,
        blastBreakRatio=(
            None if row.blast_break_percent_points is None else row.blast_break_percent_points / Decimal("100")
        ),
        previousLimitUpBreakChangeRatio=(
            None
            if row.previous_limit_up_break_change_percent_points is None
            else row.previous_limit_up_break_change_percent_points / Decimal("100")
        ),
        stopTradingCount=row.stop_trading_count,
        oneLimitUpCount=row.one_limit_up_count,
        twoLimitUpCount=row.two_limit_up_count,
        threeLimitUpCount=row.three_limit_up_count,
        highLimitUpCount=row.high_limit_up_count,
        twoLimitUpPromotionRatio=(
            None
            if row.two_limit_up_promotion_percent_points is None
            else row.two_limit_up_promotion_percent_points / Decimal("100")
        ),
        threeLimitUpPromotionRatio=(
            None
            if row.three_limit_up_promotion_percent_points is None
            else row.three_limit_up_promotion_percent_points / Decimal("100")
        ),
        highLimitUpPromotionRatio=(
            None
            if row.high_limit_up_promotion_percent_points is None
            else row.high_limit_up_promotion_percent_points / Decimal("100")
        ),
        previousLimitUpThemeChangeRatio=(
            None
            if row.previous_limit_up_theme_change_percent_points is None
            else row.previous_limit_up_theme_change_percent_points / Decimal("100")
        ),
        previousConsecutiveLimitUpThemeChangeRatio=(
            None
            if row.previous_consecutive_limit_up_theme_change_percent_points is None
            else row.previous_consecutive_limit_up_theme_change_percent_points / Decimal("100")
        ),
    )
    return StandardRecord(
        dataset=MARKET_SENTIMENT_DATASET.name,
        schemaVersion=MARKET_SENTIMENT_DATASET.schema_version,
        recordId=f"aigupiao-market-sentiment:{row.captured_at.isoformat()}",
        entityId="market:cn_a",
        capturedAt=row.captured_at,
        source=Source(providerId=source.provider_id, sourceUrl=row.source_url or source.source_url),
        status=DataStatus.LIVE,
        quality=Quality(
            issues=[
                QualityIssue(
                    kind=QualityIssueKind.ESTIMATED,
                    detail="marketTemperature and forecastedTurnover are source-derived or estimated metrics.",
                )
            ]
        ),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="aigupiao-market-sentiment-normalizer/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


__all__ = [
    "MARKET_SENTIMENT_DATASET",
    "MarketSentimentData",
    "MarketSentimentRequest",
    "normalize_market_sentiment",
]
