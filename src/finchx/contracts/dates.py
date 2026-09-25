"""Shared parsing for public calendar-date inputs."""

from __future__ import annotations

from datetime import date, datetime
import re


_DATE_PATTERNS = (
    re.compile(r"^(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})$"),
    re.compile(r"^(?P<year>[0-9]{4})(?P<month>[0-9]{2})(?P<day>[0-9]{2})$"),
    re.compile(r"^(?P<year>[0-9]{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})$"),
)
_AMBIGUOUS_DATE_PATTERN = re.compile(r"^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$")


def _parse_date_string(value: str) -> date:
    for pattern in _DATE_PATTERNS:
        match = pattern.fullmatch(value)
        if match is not None:
            try:
                return date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
            except ValueError as exc:
                raise ValueError(
                    f"invalid date input {value!r}; expected a real calendar date"
                ) from exc
    if _AMBIGUOUS_DATE_PATTERN.fullmatch(value):
        raise ValueError(
            f"ambiguous date input {value!r}; use YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD"
        )
    raise ValueError(
        f"invalid date input {value!r}; use YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD"
    )


def normalize_date_input(value: date | str) -> date:
    """Normalize an unambiguous public date input to ``datetime.date``.

    ``datetime`` is deliberately rejected even though it subclasses ``date``;
    callers should use a calendar date for date-only request fields.
    """

    if isinstance(value, datetime):
        raise ValueError("date input must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return _parse_date_string(value)
    raise TypeError(
        f"date input must be a datetime.date or string in YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD; got {type(value).__name__}"
    )


__all__ = ["normalize_date_input"]
