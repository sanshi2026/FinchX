"""The canonical CN_A natural-date trading calendar contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from pydantic import Field, field_validator, model_validator

from finchx.contracts import (
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Market


class TradingCalendarRequest(ContractModel):
    """Inclusive natural-date range for the shared China A-share calendar."""

    market: Market
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")

    @field_validator("market")
    @classmethod
    def market_must_be_cn_a(cls, value: Market) -> Market:
        if value is not Market.CN_A:
            raise ValueError("trading_calendar supports only Market.CN_A")
        return value

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def dates_must_not_be_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime):
            raise ValueError("trading calendar bounds must be dates, not datetimes")
        return value

    @model_validator(mode="after")
    def start_must_not_follow_end(self) -> TradingCalendarRequest:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        return self


class TradingCalendarData(ContractModel):
    """Whether one natural date is an A-share trading day."""

    date: date
    is_trading_day: bool = Field(alias="isTradingDay", strict=True)


TRADING_CALENDAR_DATASET: DatasetDefinition[
    TradingCalendarRequest, TradingCalendarData
] = DatasetDefinition(
    name="trading_calendar",
    schema_version="1.0",
    request_type=TradingCalendarRequest,
    data_type=TradingCalendarData,
)


@dataclass(frozen=True)
class _ProviderCalendarDay:
    """A provider-neutral day and the acquisition time of its source result."""

    date: date
    is_trading_day: bool
    captured_at: datetime


def _calendar_dates(request: TradingCalendarRequest) -> tuple[date, ...]:
    count = (request.end_date - request.start_date).days + 1
    return tuple(request.start_date + timedelta(days=offset) for offset in range(count))


def _normalize_calendar_rows(
    request: TradingCalendarRequest,
    rows: Sequence[_ProviderCalendarDay],
    *,
    source: Source,
) -> tuple[StandardRecord, ...]:
    """Validate full natural-date coverage and build canonical records."""

    expected_dates = _calendar_dates(request)
    expected = set(expected_dates)
    seen: set[date] = set()

    for row in rows:
        if not isinstance(row, _ProviderCalendarDay):
            raise ValueError("provider returned a row with an unsupported type")
        if not isinstance(row.date, date) or isinstance(row.date, datetime):
            raise ValueError("provider returned an invalid calendar date")
        if row.date in seen:
            raise ValueError(f"provider returned duplicate date {row.date.isoformat()}")
        if row.date not in expected:
            raise ValueError(f"provider returned date outside request: {row.date.isoformat()}")
        if not isinstance(row.is_trading_day, bool):
            raise ValueError(f"provider returned an invalid flag for {row.date.isoformat()}")
        if (
            not isinstance(row.captured_at, datetime)
            or row.captured_at.tzinfo is None
            or row.captured_at.utcoffset() is None
        ):
            raise ValueError("provider returned a naive captured_at timestamp")
        seen.add(row.date)

    missing = expected - seen
    if missing:
        first_missing = min(missing)
        raise ValueError(
            f"provider omitted {len(missing)} requested date(s), first {first_missing.isoformat()}"
        )

    records: list[StandardRecord] = []
    for row in sorted(rows, key=lambda item: item.date):
        data = TradingCalendarData(
            date=row.date,
            isTradingDay=row.is_trading_day,
        )
        record_source = Source(
            providerId=source.provider_id,
            sourceRecordId=source.source_record_id,
            sourceUrl=source.source_url,
        )
        identity = f"CN_A:{row.date.isoformat()}"
        records.append(
            StandardRecord(
                dataset=TRADING_CALENDAR_DATASET.name,
                schemaVersion=TRADING_CALENDAR_DATASET.schema_version,
                recordId=identity,
                entityId=identity,
                eventAt=None,
                asOf=None,
                capturedAt=row.captured_at,
                source=record_source,
                status=DataStatus.LIVE,
                quality=Quality(),
                provenance=Provenance(
                    recordClass=ProvenanceClass.STANDARDIZED,
                    transformationVersion="trading-calendar-normalizer/1",
                ),
                data=data.model_dump(mode="json", by_alias=True),
            )
        )
    return tuple(records)
