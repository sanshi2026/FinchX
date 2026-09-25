"""Shared request validation for source-backed document datasets."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from finchx.contracts.models import ContractModel
from finchx.entities import (
    Exchange,
    InstrumentId,
    InstrumentKind,
    Market,
    normalize_instrument,
)


DocumentSort = Literal["published_desc", "published_asc"]
DOCUMENT_SEARCH_MAX_PAGES = 50
_SUPPORTED_EQUITY_PREFIXES = {
    Exchange.SSE: ("60", "68"),
    Exchange.SZSE: ("00", "30"),
}


def validate_document_instrument(instrument: InstrumentId) -> InstrumentId:
    """Validate an SSE/SZSE equity identity used by document sources."""

    if not isinstance(instrument, InstrumentId):
        raise ValueError("instrument must be an InstrumentId")
    if instrument.market is not Market.CN_A or instrument.kind is not InstrumentKind.EQUITY:
        raise ValueError("document datasets support CN_A equities only")
    prefixes = _SUPPORTED_EQUITY_PREFIXES.get(instrument.exchange)
    if prefixes is None:
        raise ValueError("document datasets require an explicit SSE or SZSE equity")
    if (
        len(instrument.code) != 6
        or not instrument.code.isascii()
        or not instrument.code.isdigit()
        or not instrument.code.startswith(prefixes)
    ):
        raise ValueError("equity code does not match its explicit SSE/SZSE identity")
    return instrument


def normalize_document_instrument(value: InstrumentId | str) -> InstrumentId:
    """Normalize a canonical symbol or a verified six-digit A-share code.

    The bare-code convenience is intentionally limited to the unambiguous
    SSE/SZSE equity prefixes used by the EastMoney stock endpoints.  It does
    not perform an existence lookup or infer an index/ETF identity.
    """

    if isinstance(value, InstrumentId):
        return validate_document_instrument(value)
    return validate_document_instrument(normalize_instrument(value))


class DocumentSearchRequest(ContractModel):
    """Common public search controls shared by news and disclosures."""

    instrument_id: InstrumentId = Field(alias="instrumentId")
    page: int = Field(default=1, strict=True, ge=1)
    page_size: int = Field(default=20, alias="pageSize", strict=True, ge=1, le=200)
    max_results: int | None = Field(default=None, alias="maxResults", strict=True, ge=1)

    @field_validator("instrument_id")
    @classmethod
    def validate_instrument(cls, value: InstrumentId) -> InstrumentId:
        return validate_document_instrument(value)

    @model_validator(mode="after")
    def validate_paging_combination(self) -> DocumentSearchRequest:
        if self.max_results is not None and self.page != 1:
            raise ValueError("maxResults requires page=1; page and maxResults cannot be combined ambiguously")
        return self


class TimedDocumentSearchRequest(DocumentSearchRequest):
    """Common time controls for document sources with a proven timestamp."""

    since: date | datetime | None = None
    until: date | datetime | None = None
    sort: DocumentSort = "published_desc"

    @field_validator("since", "until")
    @classmethod
    def datetime_bounds_must_be_aware(cls, value: date | datetime | None) -> date | datetime | None:
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("since/until datetimes must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> TimedDocumentSearchRequest:
        if (self.since is not None or self.until is not None) and self.page != 1:
            raise ValueError("since/until requires page=1 for a complete date-range search")
        if self.since is not None and self.until is not None:
            if _bound_datetime(self.since) > _bound_datetime(self.until):
                raise ValueError("since must not be later than until")
        return self


_SOURCE_TIMEZONE = timezone(timedelta(hours=8))


def _bound_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("since/until datetimes must include a timezone offset")
        return value
    return datetime.combine(value, time.min, tzinfo=_SOURCE_TIMEZONE)


def matches_datetime_range(
    value: datetime | None,
    *,
    since: date | datetime | None,
    until: date | datetime | None,
) -> bool:
    if value is None:
        return False if since is not None or until is not None else True
    if since is not None and value < _bound_datetime(since):
        return False
    if until is not None:
        # Date-only until values are inclusive through that source-local day.
        upper = _bound_datetime(until)
        if isinstance(until, date) and not isinstance(until, datetime):
            upper = datetime.combine(until, time.max, tzinfo=upper.tzinfo)
        if value > upper:
            return False
    return True


def matches_date_range(
    value: date | None,
    *,
    since: date | datetime | None,
    until: date | datetime | None,
) -> bool:
    if value is None:
        return False if since is not None or until is not None else True
    if since is not None and value < _bound_datetime(since).date():
        return False
    if until is not None and value > _bound_datetime(until).date():
        return False
    return True


class DescendingTimestampPages:
    """Track whether source pages are consistently newest-first.

    A date search may stop once a whole page is older than ``since`` only
    while every observed page has timestamps and the source order remains
    descending across both rows and page boundaries.
    """

    def __init__(self) -> None:
        self._descending = True
        self._previous_oldest: datetime | None = None

    def page_is_before_since(
        self,
        values: list[datetime | None] | tuple[datetime | None, ...],
        since: date | datetime | None,
    ) -> bool:
        if since is None or not values:
            return False
        if any(
            value is None or value.tzinfo is None or value.utcoffset() is None
            for value in values
        ):
            self._descending = False
            return False
        timestamps = tuple(value for value in values if value is not None)
        if any(earlier < later for earlier, later in zip(timestamps, timestamps[1:])):
            self._descending = False
        if self._previous_oldest is not None and self._previous_oldest < timestamps[0]:
            self._descending = False
        self._previous_oldest = timestamps[-1]
        return self._descending and timestamps[0] < _bound_datetime(since)


__all__ = [
    "DocumentSearchRequest",
    "DOCUMENT_SEARCH_MAX_PAGES",
    "DescendingTimestampPages",
    "DocumentSort",
    "TimedDocumentSearchRequest",
    "matches_date_range",
    "matches_datetime_range",
    "normalize_document_instrument",
    "validate_document_instrument",
]
