"""Validation of source calendar, quote and adjustment inputs for deviation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from finchx.collectors.errors import NoData
from finchx.contracts import DataStatus, Source, StandardRecord
from finchx.datasets.market_klines import KlineAdjustment, MarketKlineData
from finchx.datasets.market_quote_snapshot import MARKET_QUOTE_SNAPSHOT_DATASET
from finchx.datasets.market_quote_snapshot import MarketQuoteSnapshotData
from finchx.entities import InstrumentId


_SHANGHAI = timezone(timedelta(hours=8))


def _calendar_sessions(data: Iterable[StandardRecord]) -> tuple[date, ...]:
    sessions: list[date] = []
    for record in data:
        if not isinstance(record, StandardRecord):
            raise NoData("trading_calendar returned an invalid record")
        raw_date = record.data.get("date")
        if not isinstance(raw_date, str):
            raise NoData("trading_calendar returned a record without a date")
        try:
            session_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise NoData("trading_calendar returned an invalid date") from exc
        if record.data.get("isTradingDay") is True:
            sessions.append(session_date)
    return tuple(sorted(set(sessions)))


def _quote_snapshot_data(
    data: object,
    expected: InstrumentId,
    observation_date: date,
    now: datetime,
    captured_at: datetime,
) -> MarketQuoteSnapshotData:
    if not isinstance(data, StandardRecord):
        raise NoData("market.deviation quote_snapshot returned an invalid record")
    if data.dataset != MARKET_QUOTE_SNAPSHOT_DATASET.name:
        raise NoData("market.deviation quote_snapshot returned a different dataset")
    if data.status is not DataStatus.LIVE:
        raise NoData("market.deviation quote_snapshot status is not live")
    if data.entity_id != expected:
        raise NoData("market.deviation quote_snapshot entityId does not match request")
    try:
        quote = MarketQuoteSnapshotData.model_validate(data.data)
    except Exception as exc:
        raise NoData("market.deviation quote_snapshot returned an invalid price") from exc
    if quote.instrument_id != expected:
        raise NoData("market.deviation quote_snapshot instrument does not match request")
    if quote.price <= 0:
        raise NoData("market.deviation quote_snapshot price must be positive")
    local_now = now.astimezone(_SHANGHAI)
    source_time = quote.source_timestamp.astimezone(_SHANGHAI)
    local_captured = captured_at.astimezone(_SHANGHAI)
    if source_time.date() != observation_date:
        raise NoData(
            f"market.deviation quote_snapshot is stale: expected {observation_date.isoformat()}, "
            f"received {source_time.date().isoformat()}"
        )
    if source_time > local_now + timedelta(minutes=1) or source_time > local_captured + timedelta(minutes=1):
        raise NoData("market.deviation quote_snapshot sourceTimestamp is in the future")
    source_clock = source_time.time().replace(tzinfo=None)
    current_clock = local_now.time().replace(tzinfo=None)
    if source_clock < time(9, 15):
        raise NoData("market.deviation quote_snapshot timestamp is before the A-share session")
    if current_clock < time(9, 15):
        raise NoData("market.deviation has no valid same-day quote before the A-share session")
    if current_clock < time(15, 0):
        if time(11, 30) <= current_clock < time(13, 0):
            if source_clock < time(11, 15):
                raise NoData("market.deviation quote_snapshot is stale for the lunch session")
        elif local_now - source_time > timedelta(minutes=20):
            raise NoData("market.deviation quote_snapshot is stale for the current session")
    return quote


def _stock_kline_adjustment(
    data: Iterable[StandardRecord],
    metadata: Any,
) -> KlineAdjustment:
    observed_adjustments: set[KlineAdjustment] = set()
    for record in data:
        if not isinstance(record, StandardRecord):
            raise NoData("market.klines returned an invalid record")
        try:
            bar = MarketKlineData.model_validate(record.data)
        except Exception as exc:
            raise NoData("market.klines returned an invalid bar") from exc
        if bar.adjustment not in (KlineAdjustment.QFQ, KlineAdjustment.NONE):
            raise NoData("market.deviation stock Klines returned an unsupported adjustment mode")
        observed_adjustments.add(bar.adjustment)

    if len(observed_adjustments) > 1:
        raise NoData("market.deviation stock Klines mix adjustment modes")
    observed = next(iter(observed_adjustments), None)
    metadata_adjustment = metadata.get("actual_adjustment") if hasattr(metadata, "get") else None
    if metadata_adjustment is not None:
        try:
            declared = KlineAdjustment(metadata_adjustment)
        except (TypeError, ValueError) as exc:
            raise NoData("market.deviation stock Klines reported an invalid actual_adjustment") from exc
        if declared not in (KlineAdjustment.QFQ, KlineAdjustment.NONE):
            raise NoData("market.deviation stock Klines reported an unsupported actual_adjustment")
        if observed is not None and declared is not observed:
            raise NoData("market.deviation stock Klines metadata conflicts with bar adjustment")
        return declared
    return observed or KlineAdjustment.QFQ


def _merge_provenance(*groups: Iterable[Source]) -> tuple[Source, ...]:
    merged: list[Source] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for group in groups:
        for source in group:
            key = (
                source.provider_id,
                source.source_record_id,
                str(source.source_url) if source.source_url else None,
            )
            if key not in seen:
                seen.add(key)
                merged.append(source)
    return tuple(merged)
