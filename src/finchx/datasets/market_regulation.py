"""EastMoney regulation and abnormal-move contracts and normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any, Literal

from pydantic import Field, RootModel, field_validator, model_validator

from finchx.contracts import (
    DataStatus,
    Percentage,
    Price,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    StandardRecord,
)
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

_PROVIDER_ID = "eastmoney.regulation"
_DATA_CENTER_RECORDS_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
_WATCHLIST_EXCHANGE = {"1": Exchange.SSE, "0": Exchange.SZSE, "B": Exchange.BSE}
_SECUCODE_PATTERN = re.compile(r"^(?P<code>[0-9]{6})\.(?P<exchange>SH|SZ|BJ)$")
_SECUCODE_EXCHANGE = {"SH": Exchange.SSE, "SZ": Exchange.SZSE, "BJ": Exchange.BSE}
_BOARD_EXCHANGE = {"4": Exchange.SZSE, "5": Exchange.SSE, "6": Exchange.BSE}
_BOARD_NAMES = {"1": "main_board", "4": "chinext", "5": "star_market", "6": "bse"}

RecordsDataset = Literal["abnormal_events", "severe_events", "prediction_history"]
TriggeredFilter = Literal["all", "yes", "no"]


class RegulationWatchlistRequest(ContractModel):
    """Latest-only risk-monitoring list request."""


class AbnormalRecordsRequest(ContractModel):
    """One upstream page for one of the three permitted records datasets."""

    dataset: RecordsDataset = Field(description="Select abnormal_events, severe_events, or prediction_history on this shared Dataset.")
    page: int = Field(default=1, strict=True, ge=1, description="One-based upstream page number; each request fetches this page only.")
    page_size: int = Field(default=20, alias="pageSize", strict=True, ge=1, le=200, description="Rows requested from the upstream page; maximum 200.")
    status: Literal["current", "history", "all"] | None = Field(default=None, description="severe_events only; None defaults to current provider rows.")
    triggered: TriggeredFilter | None = Field(default=None, description="prediction_history local/server filter: all, yes, or no; unknown flags do not match yes/no.")
    rise_only: bool | None = Field(default=None, alias="riseOnly", description="prediction_history only; true is pushed to the validated positive-flag filter.")
    include_current: bool | None = Field(default=None, alias="includeCurrent", description="prediction_history only; false filters current-session rows locally, while unknown source flags remain unknown.")

    @model_validator(mode="after")
    def validate_dataset_options(self) -> "AbnormalRecordsRequest":
        if self.dataset == "severe_events":
            if any(value is not None for value in (self.triggered, self.rise_only, self.include_current)):
                raise ValueError("triggered, rise_only and include_current apply only to prediction_history")
        elif self.dataset == "prediction_history":
            if self.status is not None:
                raise ValueError("status applies only to severe_events")
        elif any(value is not None for value in (self.status, self.triggered, self.rise_only, self.include_current)):
            raise ValueError("status and prediction filters do not apply to abnormal_events")
        return self


class SeverePredictionsRequest(ContractModel):
    """Bounded complete-pool request for the current provider prediction pool."""

    rise_only: bool = Field(default=False, alias="riseOnly", description="Include only rising rows when true.")
    include_bse: bool = Field(default=True, alias="includeBse", description="Request BSE rows from the provider when true.")


class AbnormalCountsRequest(ContractModel):
    """Bounded complete-pool request for the provider's 10-day count pool."""

    sort_by: Literal["count", "price", "max_deviation"] = Field(default="count", alias="sortBy", description="Provider sort key: count, price, or maximum deviation.")
    order: Literal["asc", "desc"] = Field(default="desc", description="Provider sort direction.")


class RegulationWatchlistData(ContractModel):
    dataset: Literal["regulation_watchlist"]
    code: str = Field(description="Original source security code.")
    name: str = Field(description="Security name supplied by the source.")
    instrument_id: InstrumentId | None = Field(default=None, alias="instrumentId", description="Null because stock_monitor.json does not provide a verified instrument identity.")
    exchange: Exchange | None = Field(default=None, description="Exchange decoded from MARKET: 1 is SSE, 0 is SZSE, B is BSE; unknown codes remain null.")
    monitor_start_date: date | None = Field(default=None, alias="monitorStartDate", description="Source monitoring start date.")
    expected_end_date: date | None = Field(default=None, alias="expectedEndDate", description="Source monitoring end date when supplied.")
    notice_url: str | None = Field(default=None, alias="noticeUrl", description="Source-linked notice URL when supplied.")
    provider_values: dict[str, Any] = Field(alias="providerValues", description="Original EastMoney row values, including unrecognized markers.")


class _EventBaseData(ContractModel):
    code: str = Field(description="Six-digit instrument code reported by EastMoney.")
    name: str = Field(description="Security name supplied by EastMoney.")
    instrument_id: InstrumentId = Field(alias="instrumentId", description="Instrument identity decoded from SECUCODE.")
    exchange: Exchange = Field(description="Exchange decoded from the SECUCODE suffix.")
    event_start_date: date | None = Field(default=None, alias="eventStartDate", description="Source event start date when supplied.")
    event_end_date: date | None = Field(default=None, alias="eventEndDate", description="Source event end date when supplied.")
    announcement_id: str | None = Field(default=None, alias="announcementId", description="Source INFO_CODE when supplied.")
    announcement_date: date | None = Field(default=None, alias="announcementDate", description="Announcement date supplied by EastMoney.")
    announcement_url: str | None = Field(default=None, alias="announcementUrl", description="EastMoney notice URL formed from INFO_CODE when present.")
    reason_text: str | None = Field(default=None, alias="reasonText", description="Source abnormality reason text.")
    reason_type_text: str | None = Field(default=None, alias="reasonTypeText", description="Source abnormality reason-type text.")
    disclosure_exchange: str | None = Field(default=None, alias="disclosureExchange", description="Original disclosure-market text; not normalized to FinchX Exchange.")
    provider_event_type: str = Field(alias="providerEventType", description="Original UNUSUAL_TYPE marker: 001 ordinary or 002 severe.")
    provider_values: dict[str, Any] = Field(alias="providerValues", description="Original EastMoney values retained for audit.")


class AbnormalEventData(_EventBaseData):
    dataset: Literal["abnormal_events"]
    event_type: Literal["ordinary"] = Field(alias="eventType", description="Normalized event class for UNUSUAL_TYPE=001.")


class SevereEventData(_EventBaseData):
    dataset: Literal["severe_events"]
    event_type: Literal["severe"] = Field(alias="eventType", description="Normalized event class for UNUSUAL_TYPE=002.")
    expected_monitor_start_date: date | None = Field(default=None, alias="expectedMonitorStartDate", description="Provider prediction monitoring start date.")
    expected_monitor_end_date: date | None = Field(default=None, alias="expectedMonitorEndDate", description="Provider prediction monitoring end date.")
    provider_monitor_status: Literal["current", "history", "unknown"] = Field(alias="providerMonitorStatus", description="IS_HIS=1 maps to current, 0 to history; other values remain unknown.")
    provider_monitor_status_raw: str | None = Field(default=None, alias="providerMonitorStatusRaw", description="Original IS_HIS marker.")


class PredictionHistoryData(ContractModel):
    dataset: Literal["prediction_history"]
    code: str = Field(description="Six-digit instrument code reported by EastMoney.")
    name: str = Field(description="Security name supplied by EastMoney.")
    instrument_id: InstrumentId = Field(alias="instrumentId", description="Instrument identity decoded from SECUCODE.")
    exchange: Exchange = Field(description="Exchange decoded from the SECUCODE suffix.")
    trade_date: date = Field(alias="tradeDate", description="Prediction-history trade date.")
    change_ratio: Percentage | None = Field(default=None, alias="changeRatio", description="Source CHANGE_RATE percentage points divided by 100; 3% is 0.03.")
    deviation_window_days: int | None = Field(default=None, alias="deviationWindowDays", description="Source MAX_DAYS value; preserved as supplied without asserting a calculation convention.")
    deviation: Percentage | None = Field(default=None, description="Source DEVUATION_VALUE percentage points divided by 100.")
    trigger_change_ratio: Percentage | None = Field(default=None, alias="triggerChangeRatio", description="Source CHANGE_RATE_TARGET percentage points divided by 100.")
    is_triggered: bool | None = Field(default=None, alias="isTriggered", description="IS_HAPPEN 1 maps to true, 0 to false; unknown values remain null.")
    provider_rule_text: str | None = Field(default=None, alias="providerRuleText", description="Original UNUSUAL_TYPE text; it is not coerced to an event-code enum.")
    provider_current_session_flag: bool | None = Field(default=None, alias="providerCurrentSessionFlag", description="IS_SYSDATE 1 maps to true, 0 to false; unknown values remain null.")
    provider_positive_flag: bool | None = Field(default=None, alias="providerPositiveFlag", description="IS_POSITIVE 1 maps to true, 0 to false; unknown values remain null.")
    provider_market_code: str | None = Field(default=None, alias="providerMarketCode", description="Original MARKET_CODE value; its semantics are provider-specific.")
    provider_values: dict[str, Any] = Field(alias="providerValues", description="Original EastMoney values retained for audit, including RANK_TYPE.")


class AbnormalRecordData(RootModel[AbnormalEventData | SevereEventData | PredictionHistoryData]):
    """The one public abnormal-record Dataset's discriminated row types."""


class SeverePredictionData(ContractModel):
    dataset: Literal["severe_predictions"]
    code: str = Field(description="Six-digit instrument code supplied by the prediction pool.")
    name: str = Field(description="Security name supplied by the prediction pool.")
    instrument_id: InstrumentId | None = Field(default=None, alias="instrumentId", description="Identity decoded from the provider board code when recognized; otherwise null.")
    exchange: Exchange | None = Field(default=None, description="Exchange decoded from s: 4 is SZSE, 5 is SSE, 6 is BSE; unknown board codes remain null.")
    provider_market_code: int | str | None = Field(default=None, alias="providerMarketCode", description="Original m value; it is not used alone to infer the exchange.")
    provider_board_code: int | str | None = Field(default=None, alias="providerBoardCode", description="Original s board code.")
    provider_rule_code: int | str | None = Field(default=None, alias="providerRuleCode", description="Original e rule code; retained even when FinchX cannot interpret it.")
    rule_semantic_id: str | None = Field(default=None, alias="ruleSemanticId", description="Stable FinchX interpretation derived from recognized board and rule codes; null for unknown rules.")
    rule_label: str | None = Field(default=None, alias="ruleLabel", description="Readable label for the recognized rule; the provider values remain available separately.")
    deviation: Percentage | None = Field(default=None, description="Source x percentage points divided by 100; 95.69 becomes 0.9569.")
    deviation_window_days: int | None = Field(default=None, alias="deviationWindowDays", description="Source d value retained as supplied.")
    trigger_change_ratio: Percentage | None = Field(default=None, alias="triggerChangeRatio", description="Source t trigger percentage points divided by 100.")
    change_ratio: Percentage | None = Field(default=None, alias="changeRatio", description="Source a percentage points divided by 100.")
    horizon: Literal["current_session", "next_session", "unknown"] = Field(description="Derived from o: 0/1 are current-session states, 2 is next-session, other values are unknown.")
    is_triggered: bool | None = Field(default=None, alias="isTriggered", description="o=0 maps to false, 1 to true, and 2 or unknown values to null.")
    provider_signal_state: int | str | None = Field(default=None, alias="providerSignalState", description="Original o signal-state value.")
    provider_values: dict[str, Any] = Field(alias="providerValues", description="Original provider row, including source percentage values.")


class AbnormalCountData(ContractModel):
    dataset: Literal["abnormal_counts"]
    code: str = Field(description="Six-digit instrument code supplied by the count pool.")
    name: str = Field(description="Security name supplied by the count pool.")
    instrument_id: InstrumentId | None = Field(default=None, alias="instrumentId", description="Identity decoded from the provider board code when recognized; otherwise null.")
    exchange: Exchange | None = Field(default=None, description="Exchange decoded from s: 4 is SZSE, 5 is SSE, 6 is BSE; unknown board codes remain null.")
    provider_market_code: int | str | None = Field(default=None, alias="providerMarketCode", description="Original m value; it is not used alone to infer the exchange.")
    provider_board_code: int | str | None = Field(default=None, alias="providerBoardCode", description="Original s board code.")
    price: Price | None = Field(default=None, description="Source price in CNY per share.")
    change_ratio: Percentage | None = Field(default=None, alias="changeRatio", description="Source a percentage points divided by 100.")
    abnormal_count: int | None = Field(default=None, alias="abnormalCount", description="Number from /count.t; it is a row-level count, not a pool total.")
    max_deviation_10d: Percentage | None = Field(default=None, alias="maxDeviation10d", description="Source x percentage points divided by 100.")
    provider_values: dict[str, Any] = Field(alias="providerValues", description="Original provider row retained, including d whose semantics are not asserted.")


MARKET_REGULATION_WATCHLIST_DATASET: DatasetDefinition[
    RegulationWatchlistRequest, RegulationWatchlistData
] = DatasetDefinition(
    name="market.regulation_watchlist",
    schema_version="1.0",
    request_type=RegulationWatchlistRequest,
    data_type=RegulationWatchlistData,
)
MARKET_ABNORMAL_RECORDS_DATASET: DatasetDefinition[
    AbnormalRecordsRequest, AbnormalRecordData
] = DatasetDefinition(
    name="market.abnormal_records",
    schema_version="1.0",
    request_type=AbnormalRecordsRequest,
    data_type=AbnormalRecordData,
)
MARKET_SEVERE_PREDICTIONS_DATASET: DatasetDefinition[
    SeverePredictionsRequest, SeverePredictionData
] = DatasetDefinition(
    name="market.severe_predictions",
    schema_version="1.0",
    request_type=SeverePredictionsRequest,
    data_type=SeverePredictionData,
)
MARKET_ABNORMAL_COUNTS_DATASET: DatasetDefinition[
    AbnormalCountsRequest, AbnormalCountData
] = DatasetDefinition(
    name="market.abnormal_counts",
    schema_version="1.0",
    request_type=AbnormalCountsRequest,
    data_type=AbnormalCountData,
)


def normalize_watchlist(
    request: RegulationWatchlistRequest,
    rows: Sequence[Mapping[str, Any]],
    *,
    captured_at: datetime,
    source: Source,
    source_url: str,
) -> tuple[StandardRecord, ...]:
    output: list[StandardRecord] = []
    for raw in rows:
        code = _required_text(raw.get("STKCODE"), "watchlist.STKCODE")
        name = _required_text(raw.get("STKNAME"), "watchlist.STKNAME")
        raw_market = _required_text(raw.get("MARKET"), "watchlist.MARKET")
        exchange = _WATCHLIST_EXCHANGE.get(raw_market)
        instrument_id = None
        provider_values = _raw_values(raw)
        data = RegulationWatchlistData(
            dataset="regulation_watchlist",
            code=code,
            name=name,
            instrumentId=instrument_id,
            exchange=exchange,
            monitorStartDate=_optional_source_date(raw.get("VALIDATESTARTDATE"), "VALIDATESTARTDATE"),
            expectedEndDate=_optional_source_date(raw.get("VALIDATEENDDATE"), "VALIDATEENDDATE"),
            noticeUrl=_optional_text(raw.get("LINK_URL")),
            providerValues=provider_values,
        )
        output.append(
            _standard_record(
                MARKET_REGULATION_WATCHLIST_DATASET.name,
                data,
                entity_id=_watchlist_entity_id(code, raw_market),
                source=source,
                source_url=source_url,
                source_record_id=code,
                captured_at=captured_at,
            )
        )
    return tuple(output)


def normalize_abnormal_records(
    request: AbnormalRecordsRequest,
    rows: Sequence[Mapping[str, Any]],
    *,
    captured_at: datetime,
    source: Source,
    source_url: str,
) -> tuple[StandardRecord, ...]:
    output: list[StandardRecord] = []
    for raw in rows:
        _require_fields(raw, ("SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "UNUSUAL_TYPE"), "records")
        identity = _identity_from_secu_code(raw.get("SECUCODE"), InstrumentKind.EQUITY)
        if identity is None:
            raise ValueError("records.SECUCODE must use a recognized SH/SZ/BJ suffix")
        code = _required_text(raw.get("SECURITY_CODE"), "records.SECURITY_CODE")
        name = _required_text(raw.get("SECURITY_NAME_ABBR"), "records.SECURITY_NAME_ABBR")
        notice_date = _optional_source_date(raw.get("NOTICE_DATE"), "NOTICE_DATE")
        trade_date = _optional_source_date(raw.get("TRADE_DATE"), "TRADE_DATE")

        provider_values = _raw_values(raw)
        source_id = _optional_text(raw.get("INFO_CODE")) or _row_digest(raw)
        if request.dataset == "abnormal_events":
            if _source_text(raw.get("UNUSUAL_TYPE"), "UNUSUAL_TYPE") != "001":
                raise ValueError("abnormal_events returned a non-ordinary UNUSUAL_TYPE")
            data: ContractModel = AbnormalEventData(
                dataset="abnormal_events",
                code=code,
                name=name,
                instrumentId=identity,
                exchange=identity.exchange,
                eventStartDate=_optional_source_date(raw.get("START_DATE"), "START_DATE"),
                eventEndDate=_optional_source_date(raw.get("END_DATE"), "END_DATE"),
                announcementId=_optional_text(raw.get("INFO_CODE")),
                announcementDate=notice_date,
                announcementUrl=_announcement_url(raw.get("INFO_CODE")),
                reasonText=_optional_text(raw.get("UNUSUAL_REASON")),
                reasonTypeText=_optional_text(raw.get("UNUSUAL_REASON_TYPE")),
                disclosureExchange=_optional_text(raw.get("MRAKET_TYPE")),
                providerEventType=_source_text(raw.get("UNUSUAL_TYPE"), "UNUSUAL_TYPE"),
                eventType="ordinary",
                providerValues=provider_values,
            )
        elif request.dataset == "severe_events":
            if _source_text(raw.get("UNUSUAL_TYPE"), "UNUSUAL_TYPE") != "002":
                raise ValueError("severe_events returned a non-severe UNUSUAL_TYPE")
            raw_status = _optional_text(raw.get("IS_HIS"))
            provider_status = {"1": "current", "0": "history"}.get(raw_status, "unknown")
            effective_status = request.status or "current"
            if effective_status != "all" and provider_status != effective_status:
                continue
            data = SevereEventData(
                dataset="severe_events",
                code=code,
                name=name,
                instrumentId=identity,
                exchange=identity.exchange,
                eventStartDate=_optional_source_date(raw.get("START_DATE"), "START_DATE"),
                eventEndDate=_optional_source_date(raw.get("END_DATE"), "END_DATE"),
                announcementId=_optional_text(raw.get("INFO_CODE")),
                announcementDate=notice_date,
                announcementUrl=_announcement_url(raw.get("INFO_CODE")),
                reasonText=_optional_text(raw.get("UNUSUAL_REASON")),
                reasonTypeText=_optional_text(raw.get("UNUSUAL_REASON_TYPE")),
                disclosureExchange=_optional_text(raw.get("MRAKET_TYPE")),
                providerEventType=_source_text(raw.get("UNUSUAL_TYPE"), "UNUSUAL_TYPE"),
                eventType="severe",
                expectedMonitorStartDate=_optional_source_date(raw.get("PREDICT_START_DATE"), "PREDICT_START_DATE"),
                expectedMonitorEndDate=_optional_source_date(raw.get("PREDICT_END_DATE"), "PREDICT_END_DATE"),
                providerMonitorStatus=provider_status,
                providerMonitorStatusRaw=raw_status,
                providerValues=provider_values,
            )
        else:
            if trade_date is None:
                raise ValueError("prediction_history.TRADE_DATE is required")
            triggered = _flag(raw.get("IS_HAPPEN"))
            positive = _flag(raw.get("IS_POSITIVE"))
            current = _flag(raw.get("IS_SYSDATE"))
            if request.triggered == "yes" and triggered is not True:
                continue
            if request.triggered == "no" and triggered is not False:
                continue
            if request.rise_only is True and positive is not True:
                continue
            if request.include_current is False and current is True:
                continue
            market_code = _optional_text(raw.get("MARKET_CODE"))
            data = PredictionHistoryData(
                dataset="prediction_history",
                code=code,
                name=name,
                instrumentId=identity,
                exchange=identity.exchange,
                tradeDate=trade_date,
                changeRatio=_ratio_from_percent(raw.get("CHANGE_RATE"), "CHANGE_RATE"),
                deviationWindowDays=_optional_integer(raw.get("MAX_DAYS"), "MAX_DAYS"),
                deviation=_ratio_from_percent(raw.get("DEVUATION_VALUE"), "DEVUATION_VALUE"),
                triggerChangeRatio=_ratio_from_percent(raw.get("CHANGE_RATE_TARGET"), "CHANGE_RATE_TARGET"),
                isTriggered=triggered,
                providerRuleText=_optional_text(raw.get("UNUSUAL_TYPE")),
                providerCurrentSessionFlag=current,
                providerPositiveFlag=positive,
                providerMarketCode=market_code,
                providerValues=provider_values,
            )
        output.append(
            _standard_record(
                MARKET_ABNORMAL_RECORDS_DATASET.name,
                data,
                entity_id=identity,
                source=source,
                source_url=source_url,
                source_record_id=source_id,
                captured_at=captured_at,
            )
        )
    return tuple(output)


def normalize_severe_predictions(
    request: SeverePredictionsRequest,
    rows: Sequence[Mapping[str, Any]],
    *,
    captured_at: datetime,
    source: Source,
    source_url: str,
) -> tuple[StandardRecord, ...]:
    output: list[StandardRecord] = []
    for raw in rows:
        _require_fields(raw, ("c", "n", "s", "e", "o"), "price-anomaly.list")
        code = _required_code(raw.get("c"), "price-anomaly.list.c")
        name = _required_text(raw.get("n"), "price-anomaly.list.n")
        board = _optional_integer_or_text(raw.get("s"), "price-anomaly.list.s")
        rule = _optional_integer_or_text(raw.get("e"), "price-anomaly.list.e")
        exchange = _BOARD_EXCHANGE.get(str(board))
        identity = InstrumentId(code=code, market=Market.CN_A, kind=InstrumentKind.EQUITY, exchange=exchange) if exchange else None
        state = _optional_integer_or_text(raw.get("o"), "price-anomaly.list.o")
        horizon: Literal["current_session", "next_session", "unknown"] = (
            "current_session" if state in (0, 1) else "next_session" if state == 2 else "unknown"
        )
        is_triggered = False if state == 0 else True if state == 1 else None
        semantic_id, label = _rule_semantics(board, rule)
        data = SeverePredictionData(
            dataset="severe_predictions",
            code=code,
            name=name,
            instrumentId=identity,
            exchange=exchange,
            providerMarketCode=_optional_integer_or_text(raw.get("m"), "price-anomaly.list.m"),
            providerBoardCode=board,
            providerRuleCode=rule,
            ruleSemanticId=semantic_id,
            ruleLabel=label,
            deviation=_ratio_from_percent(raw.get("x"), "price-anomaly.list.x"),
            deviationWindowDays=_optional_integer(raw.get("d"), "price-anomaly.list.d"),
            triggerChangeRatio=_ratio_from_percent(raw.get("t"), "price-anomaly.list.t"),
            changeRatio=_ratio_from_percent(raw.get("a"), "price-anomaly.list.a"),
            horizon=horizon,
            isTriggered=is_triggered,
            providerSignalState=_optional_integer_or_text(raw.get("o"), "price-anomaly.list.o"),
            providerValues=_raw_values(raw),
        )
        output.append(
            _standard_record(
                MARKET_SEVERE_PREDICTIONS_DATASET.name,
                data,
                entity_id=identity or f"eastmoney.price_anomaly:{code}",
                source=source,
                source_url=source_url,
                source_record_id=_row_digest(raw),
                captured_at=captured_at,
            )
        )
    return tuple(output)


def normalize_abnormal_counts(
    request: AbnormalCountsRequest,
    rows: Sequence[Mapping[str, Any]],
    *,
    captured_at: datetime,
    source: Source,
    source_url: str,
) -> tuple[StandardRecord, ...]:
    output: list[StandardRecord] = []
    for raw in rows:
        _require_fields(raw, ("c", "n", "s", "t"), "price-anomaly.count")
        code = _required_code(raw.get("c"), "price-anomaly.count.c")
        name = _required_text(raw.get("n"), "price-anomaly.count.n")
        board = _optional_integer_or_text(raw.get("s"), "price-anomaly.count.s")
        exchange = _BOARD_EXCHANGE.get(str(board))
        identity = InstrumentId(code=code, market=Market.CN_A, kind=InstrumentKind.EQUITY, exchange=exchange) if exchange else None
        data = AbnormalCountData(
            dataset="abnormal_counts",
            code=code,
            name=name,
            instrumentId=identity,
            exchange=exchange,
            providerMarketCode=_optional_integer_or_text(raw.get("m"), "price-anomaly.count.m"),
            providerBoardCode=board,
            price=_optional_price(raw.get("p"), "price-anomaly.count.p"),
            changeRatio=_ratio_from_percent(raw.get("a"), "price-anomaly.count.a"),
            abnormalCount=_optional_integer(raw.get("t"), "price-anomaly.count.t"),
            maxDeviation10d=_ratio_from_percent(raw.get("x"), "price-anomaly.count.x"),
            providerValues=_raw_values(raw),
        )
        output.append(
            _standard_record(
                MARKET_ABNORMAL_COUNTS_DATASET.name,
                data,
                entity_id=identity or f"eastmoney.price_anomaly:{code}",
                source=source,
                source_url=source_url,
                source_record_id=_row_digest(raw),
                captured_at=captured_at,
            )
        )
    return tuple(output)


def local_filter_records(
    request: AbnormalRecordsRequest,
    rows: Sequence[Mapping[str, Any]],
    *,
    captured_at: datetime,
    source: Source,
    source_url: str,
) -> tuple[StandardRecord, ...]:
    """Normalize every source row before applying verified local filters."""

    normalized = normalize_abnormal_records(
        request.model_copy(update={"include_current": None, "triggered": None, "rise_only": None}),
        rows,
        captured_at=captured_at,
        source=source,
        source_url=source_url,
    )
    if request.dataset == "prediction_history":
        selected: list[StandardRecord] = []
        for record in normalized:
            data = record.data
            raw = data.get("providerValues", {})
            if request.triggered == "yes" and _flag(raw.get("IS_HAPPEN")) is not True:
                continue
            if request.triggered == "no" and _flag(raw.get("IS_HAPPEN")) is not False:
                continue
            if request.rise_only is True and _flag(raw.get("IS_POSITIVE")) is not True:
                continue
            if request.include_current is False and _flag(raw.get("IS_SYSDATE")) is True:
                continue
            selected.append(record)
        return tuple(selected)
    return normalized


def _standard_record(
    dataset: str,
    data: ContractModel,
    *,
    entity_id: InstrumentId | str,
    source: Source,
    source_url: str,
    source_record_id: str,
    captured_at: datetime,
) -> StandardRecord:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    if source.provider_id != _PROVIDER_ID:
        raise ValueError("regulation source provider id does not match the Dataset")
    return StandardRecord(
        dataset=dataset,
        schemaVersion="1.0",
        recordId=f"{dataset}:{_row_digest(data.model_dump(mode='json', by_alias=True))}",
        entityId=entity_id,
        capturedAt=captured_at,
        source=Source(providerId=source.provider_id, sourceRecordId=source_record_id, sourceUrl=source_url),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="market-regulation/1",
        ),
        data=data.model_dump(mode="json", by_alias=True),
    )


def _watchlist_entity_id(code: str, provider_market: str) -> InstrumentId | str:
    return f"eastmoney.watchlist:{provider_market}:{code}"


def _identity_from_secu_code(value: object, kind: InstrumentKind) -> InstrumentId | None:
    if not isinstance(value, str):
        return None
    matched = _SECUCODE_PATTERN.fullmatch(value)
    if matched is None:
        return None
    return InstrumentId(
        code=matched.group("code"),
        market=Market.CN_A,
        kind=kind,
        exchange=_SECUCODE_EXCHANGE[matched.group("exchange")],
    )


def _rule_semantics(board: int | str | None, rule: int | str | None) -> tuple[str | None, str | None]:
    if type(board) is not int or type(rule) is not int:
        return None, None
    board_key = str(board)
    board_name = _BOARD_NAMES.get(board_key)
    if board_name is None:
        return None, None
    repeat_rules = {
        (1, 1): ("main_board_10d_4_same_direction_events", "10-day period: 4 same-direction ordinary events"),
        (4, 2): ("chinext_10d_3_same_direction_events", "10-day period: 3 same-direction ordinary events"),
        (5, 3): ("star_market_10d_3_same_direction_events", "10-day period: 3 same-direction ordinary events"),
        (6, 8): ("bse_10d_3_same_direction_events", "10-day period: 3 same-direction ordinary events"),
    }
    if (board, rule) in repeat_rules:
        return repeat_rules[(board, rule)]
    thresholds = {
        False: {4: (10, Decimal("1.00")), 5: (10, Decimal("-0.50")), 6: (30, Decimal("2.00")), 7: (30, Decimal("-0.70"))},
        True: {4: (10, Decimal("1.50")), 5: (10, Decimal("-0.60")), 6: (30, Decimal("3.00")), 7: (30, Decimal("-0.75"))},
    }
    if rule not in (4, 5, 6, 7):
        return None, None
    days, threshold = thresholds[board == 6][rule]
    direction = "up" if threshold > 0 else "down"
    encoded = format(abs(threshold).normalize(), "f").replace(".", "p")
    semantic_id = f"{board_name}_{days}d_{direction}_{encoded}_percent_deviation"
    label = f"{days}-day cumulative deviation {format(threshold.normalize(), '+f')}%"
    return semantic_id, label


def _announcement_url(value: object) -> str | None:
    code = _optional_text(value)
    return f"https://np-info.eastmoney.com/wap/notice/?infocode={code}" if code else None


def _row_digest(raw: object) -> str:
    def encode(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, Mapping):
            return {str(key): encode(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [encode(item) for item in value]
        return value
    payload = json.dumps(encode(raw), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _raw_values(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _raw_scalar(value) for key, value in raw.items()}


def _raw_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return _raw_values(value)
    if isinstance(value, (list, tuple)):
        return [_raw_scalar(item) for item in value]
    return value


def _ratio_from_percent(value: object, label: str) -> Percentage | None:
    parsed = _optional_decimal(value, label)
    if parsed is None:
        return None
    return format(parsed / Decimal("100"), "f")  # type: ignore[return-value]


def _optional_price(value: object, label: str) -> Price | None:
    parsed = _optional_decimal(value, label)
    if parsed is None:
        return None
    return format(parsed, "f")  # type: ignore[return-value]


def _optional_decimal(value: object, label: str) -> Decimal | None:
    if value is None or (isinstance(value, str) and value.strip() in {"", "-", "--"}):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal, float)):
        raise ValueError(f"{label} must be a numeric source value or null")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} is not numeric") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be finite")
    return parsed


def _optional_integer(value: object, label: str) -> int | None:
    if value is None or (isinstance(value, str) and value.strip() in {"", "-", "--"}):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{label} must be an integer source value or null")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} is not an integer") from exc
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        raise ValueError(f"{label} must be a finite integer")
    return int(parsed)


def _optional_integer_or_text(value: object, label: str) -> int | str | None:
    if value is None:
        return None
    try:
        return _optional_integer(value, label)
    except ValueError:
        if isinstance(value, str) and value.strip() not in {"", "-", "--"}:
            return value.strip()
        if isinstance(value, Decimal) and value.is_finite():
            return format(value, "f")
        raise


def _flag(value: object) -> bool | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value == 1 if value in (0, 1) else None
    if isinstance(value, str):
        token = value.strip()
        return True if token == "1" else False if token == "0" else None
    return None


def _optional_source_date(value: object, label: str) -> date | None:
    if value is None or (isinstance(value, str) and value.strip() in {"", "-", "--"}):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a date string or null")
    text = value.strip()
    if len(text) == 8 and text.isdigit():
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError as exc:
            raise ValueError(f"{label} is not an ISO date") from exc
    candidate = text[:10] if len(text) >= 10 else text
    try:
        return date.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{label} is not an ISO date") from exc


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value.strip()


def _required_code(value: object, label: str) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value).zfill(6)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{6}", value):
        raise ValueError(f"{label} must be a six-character numeric code")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        return str(value)
    return None


def _source_text(value: object, label: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError(f"{label} must be non-empty")
    return text


def _require_fields(raw: Mapping[str, Any], fields: Sequence[str], label: str) -> None:
    missing = [name for name in fields if name not in raw]
    if missing:
        raise ValueError(f"{label} omitted required fields: {', '.join(missing)}")


__all__ = [
    "AbnormalCountData",
    "AbnormalCountsRequest",
    "AbnormalEventData",
    "AbnormalRecordData",
    "AbnormalRecordsRequest",
    "MARKET_ABNORMAL_COUNTS_DATASET",
    "MARKET_ABNORMAL_RECORDS_DATASET",
    "MARKET_REGULATION_WATCHLIST_DATASET",
    "MARKET_SEVERE_PREDICTIONS_DATASET",
    "PredictionHistoryData",
    "RegulationWatchlistData",
    "RegulationWatchlistRequest",
    "SevereEventData",
    "SeverePredictionData",
    "SeverePredictionsRequest",
    "local_filter_records",
    "normalize_abnormal_counts",
    "normalize_abnormal_records",
    "normalize_severe_predictions",
    "normalize_watchlist",
]
