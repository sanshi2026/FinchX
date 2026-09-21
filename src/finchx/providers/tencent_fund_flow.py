"""Tencent hsfundtab source adapter for snapshot, intraday, and daily fund flow."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, NoReturn
from urllib.parse import urlencode

from finchx.contracts import Source
from finchx.datasets.market_fund_flow import (
    _ProviderFundFlowDailyRow,
    _ProviderFundFlowIntradayRow,
    _ProviderFundFlowResponse,
    _ProviderFundFlowSnapshot,
    _validate_fund_flow_instrument,
)
from finchx.entities import Exchange, InstrumentId
from finchx.providers.errors import ProviderError
from finchx.providers.http import http_status_failure_reason
from finchx.providers.tencent import (
    _HEADERS,
    _TIMEOUT_SECONDS,
    _TencentTransport,
    _TencentTransportFailure,
    _UrllibTencentTransport,
    _reject_json_constant,
)

TENCENT_FUND_FLOW_ENDPOINT = (
    "https://proxy.finance.qq.com/cgi/cgi-bin/fundflow/hsfundtab"
)
_FUND_FLOW_TYPES = (
    "historyFundFlow,fiveDayFundFlow,todayFundTrend,todayFundFlow"
)
_EXCHANGE_PREFIX = {Exchange.SSE: "sh", Exchange.SZSE: "sz"}
_TIMESTAMP_PATTERN = re.compile(r"^[0-9]{12}$")
_ARITHMETIC_TOLERANCE = Decimal("1")
_PERCENT_TOTAL_TOLERANCE = Decimal("1")


class TencentFundFlowProvider:
    """Fetch one Tencent response for reuse by all three fund-flow Dataset normalizers."""

    def __init__(
        self,
        transport: _TencentTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport or _UrllibTencentTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(
            providerId="tencent.finance.qq",
            sourceUrl=TENCENT_FUND_FLOW_ENDPOINT,
        )

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_fund_flow(
        self,
        instrument_id: InstrumentId,
    ) -> _ProviderFundFlowResponse:
        """Return typed source facts once so each Dataset can normalize without another fetch."""

        if not isinstance(instrument_id, InstrumentId):
            self._fail("request must provide one explicit InstrumentId")
        try:
            _validate_fund_flow_instrument(instrument_id)
        except ValueError as exc:
            self._fail(str(exc))
        prefix = _EXCHANGE_PREFIX[instrument_id.exchange]
        symbol = f"{prefix}{instrument_id.code}"
        params = {
            "code": symbol,
            "type": _FUND_FLOW_TYPES,
            "klineNeedDay": "20",
        }
        request_url = f"{TENCENT_FUND_FLOW_ENDPOINT}?{urlencode(params)}"
        try:
            response = self._transport.get(
                TENCENT_FUND_FLOW_ENDPOINT,
                params=params,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent hsfundtab transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent hsfundtab transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent hsfundtab returned {status_reason}")
        if not response.text.strip():
            self._fail("Tencent hsfundtab returned an empty payload")
        document = self._decode_response(response.text)
        self._check_response_status(document)

        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        return self._parse_response(
            document,
            instrument_id=instrument_id,
            symbol=symbol,
            request_url=request_url,
            captured_at=captured_at,
        )

    def _decode_response(self, text: str) -> dict[str, Any]:
        try:
            document = json.loads(
                text,
                parse_float=Decimal,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Tencent hsfundtab returned malformed JSON: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Tencent hsfundtab JSON root must be an object")
        return document

    def _check_response_status(self, document: dict[str, Any]) -> None:
        if "code" not in document:
            self._fail("Tencent hsfundtab response omitted its code")
        code = document["code"]
        if isinstance(code, bool) or code not in (0, "0"):
            self._fail(f"Tencent hsfundtab source code indicates failure: {code!r}")
        if document.get("msg") != "ok":
            self._fail(f"Tencent hsfundtab source message is not ok: {document.get('msg')!r}")

    def _parse_response(
        self,
        document: dict[str, Any],
        *,
        instrument_id: InstrumentId,
        symbol: str,
        request_url: str,
        captured_at: datetime,
    ) -> _ProviderFundFlowResponse:
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("Tencent hsfundtab data must be an object")
        today = self._required_mapping(data, "todayFundFlow")
        trend = self._required_mapping(data, "todayFundTrend")
        five_day = self._required_mapping(data, "fiveDayFundFlow")
        history = self._required_mapping(data, "historyFundFlow")

        for block_name, block in (
            ("todayFundFlow", today),
            ("todayFundTrend", trend),
            ("fiveDayFundFlow", five_day),
            ("historyFundFlow", history),
        ):
            returned_code = block.get("stockCode")
            if returned_code is not None and returned_code != symbol:
                self._fail(
                    f"Tencent {block_name} stockCode does not match requested {symbol}"
                )
        if today.get("stockCode") != symbol or trend.get("stockCode") != symbol:
            self._fail("Tencent fund-flow identity fields do not match the requested symbol")

        daily_rows = self._parse_history(
            history,
            instrument_id=instrument_id,
            symbol=symbol,
            request_url=request_url,
            captured_at=captured_at,
        )
        intraday_rows = self._parse_trend(
            trend,
            instrument_id=instrument_id,
            symbol=symbol,
            request_url=request_url,
            captured_at=captured_at,
        )
        trade_date = daily_rows[-1].trade_date
        if any(row.trade_date != trade_date for row in intraday_rows):
            self._fail("Tencent history and intraday blocks report different trade dates")

        snapshot = self._parse_snapshot(
            today,
            instrument_id=instrument_id,
            trade_date=trade_date,
            symbol=symbol,
            request_url=request_url,
            captured_at=captured_at,
        )
        self._validate_five_day(
            five_day,
            daily_rows=daily_rows,
            symbol=symbol,
        )
        self._validate_summary(history, daily_rows=daily_rows, symbol=symbol)
        self._validate_snapshot_trend(snapshot, intraday_rows[-1])

        return _ProviderFundFlowResponse(
            instrument_id=instrument_id,
            snapshot=snapshot,
            intraday_rows=intraday_rows,
            daily_rows=daily_rows,
        )

    def _parse_snapshot(
        self,
        raw: Mapping[str, Any],
        *,
        instrument_id: InstrumentId,
        trade_date: date,
        symbol: str,
        request_url: str,
        captured_at: datetime,
    ) -> _ProviderFundFlowSnapshot:
        values = {
            name: self._decimal(raw.get(source_name), f"todayFundFlow.{source_name}")
            for name, source_name in (
                ("main_net_inflow", "mainNetIn"),
                ("main_inflow", "mainIn"),
                ("main_inflow_rate_percent", "mainInRate"),
                ("main_outflow", "mainOut"),
                ("main_outflow_rate_percent", "mainOutRate"),
                ("retail_inflow", "retailIn"),
                ("retail_inflow_rate_percent", "retailInRate"),
                ("retail_outflow", "retailOut"),
                ("retail_outflow_rate_percent", "retailOutRate"),
                ("super_large_net_inflow", "superFlow"),
                ("large_net_inflow", "bigFlow"),
                ("medium_net_inflow", "normalFlow"),
                ("small_net_inflow", "smallFlow"),
            )
        }
        for name in (
            "main_inflow",
            "main_outflow",
            "retail_inflow",
            "retail_outflow",
        ):
            if values[name] < 0:
                self._fail(f"Tencent todayFundFlow.{name} must not be negative")
        rates = (
            values["main_inflow_rate_percent"],
            values["main_outflow_rate_percent"],
            values["retail_inflow_rate_percent"],
            values["retail_outflow_rate_percent"],
        )
        if any(rate < 0 or rate > 100 for rate in rates):
            self._fail("Tencent fund-flow percentage must be between 0 and 100")
        if abs(sum(rates, Decimal(0)) - Decimal("100")) > _PERCENT_TOTAL_TOLERANCE:
            self._fail("Tencent fund-flow percentages do not sum to approximately 100")
        self._check_close(
            values["main_net_inflow"],
            values["main_inflow"] - values["main_outflow"],
            "todayFundFlow mainNetIn versus mainIn - mainOut",
        )
        self._check_close(
            values["super_large_net_inflow"] + values["large_net_inflow"],
            values["main_net_inflow"],
            "todayFundFlow superFlow + bigFlow versus mainNetIn",
        )
        retail_net = values["retail_inflow"] - values["retail_outflow"]
        self._check_close(
            retail_net,
            values["medium_net_inflow"] + values["small_net_inflow"],
            "todayFundFlow retail net versus normalFlow + smallFlow",
        )
        self._check_close(
            values["main_net_inflow"] + retail_net,
            Decimal(0),
            "todayFundFlow main and retail net flow",
        )
        return _ProviderFundFlowSnapshot(
            instrument_id=instrument_id,
            trade_date=trade_date,
            **values,
            source_record_id=f"{symbol}:{trade_date.isoformat()}:todayFundFlow",
            source_url=request_url,
            captured_at=captured_at,
        )

    def _parse_trend(
        self,
        raw: Mapping[str, Any],
        *,
        instrument_id: InstrumentId,
        symbol: str,
        request_url: str,
        captured_at: datetime,
    ) -> tuple[_ProviderFundFlowIntradayRow, ...]:
        source_rows = raw.get("minList")
        if not isinstance(source_rows, list) or not source_rows:
            self._fail("Tencent todayFundTrend.minList is missing or empty")
        rows: list[_ProviderFundFlowIntradayRow] = []
        seen: set[str] = set()
        previous_time: str | None = None
        previous_main_inflow: Decimal | None = None
        previous_main_outflow: Decimal | None = None
        for index, source_row in enumerate(source_rows):
            context = f"todayFundTrend.minList[{index}]"
            if not isinstance(source_row, dict):
                self._fail(f"Tencent {context} must be an object")
            timestamp_text = source_row.get("time")
            if not isinstance(timestamp_text, str) or not _TIMESTAMP_PATTERN.fullmatch(timestamp_text):
                self._fail(f"Tencent {context}.time must be YYYYMMDDHHMM")
            if timestamp_text in seen:
                self._fail(f"Tencent fund-flow trend contains duplicate minute {timestamp_text}")
            seen.add(timestamp_text)
            try:
                timestamp = datetime.strptime(timestamp_text, "%Y%m%d%H%M")
            except ValueError:
                self._fail(f"Tencent {context}.time is not a valid date/time")
            if previous_time is not None and timestamp_text <= previous_time:
                self._fail("Tencent fund-flow trend time ordering is not strictly ascending")
            previous_time = timestamp_text
            trade_date = timestamp.date()
            time_text = timestamp.strftime("%H:%M")
            values = {
                name: self._decimal(source_row.get(source_name), f"{context}.{source_name}")
                for name, source_name in (
                    ("cumulative_main_net_inflow", "MainNetInflow"),
                    ("cumulative_retail_net_inflow", "RetailNetInflow"),
                    ("cumulative_super_large_net_inflow", "SuperNetInflow"),
                    ("cumulative_large_net_inflow", "BigNetInflow"),
                    ("cumulative_medium_net_inflow", "NormalNetInflow"),
                    ("cumulative_small_net_inflow", "SmallNetInflow"),
                    ("cumulative_main_inflow", "MainInflow"),
                    ("cumulative_main_outflow", "MainOutflow"),
                )
            }
            price = self._decimal(source_row.get("Price"), f"{context}.Price")
            if price <= 0:
                self._fail(f"Tencent {context}.Price must be positive")
            if values["cumulative_main_inflow"] < 0 or values["cumulative_main_outflow"] < 0:
                self._fail(f"Tencent {context} cumulative gross flow must not be negative")
            self._check_close(
                values["cumulative_main_net_inflow"],
                values["cumulative_main_inflow"] - values["cumulative_main_outflow"],
                f"{context} MainNetInflow versus MainInflow - MainOutflow",
            )
            self._check_close(
                values["cumulative_super_large_net_inflow"]
                + values["cumulative_large_net_inflow"],
                values["cumulative_main_net_inflow"],
                f"{context} SuperNetInflow + BigNetInflow versus MainNetInflow",
            )
            self._check_close(
                values["cumulative_medium_net_inflow"]
                + values["cumulative_small_net_inflow"],
                values["cumulative_retail_net_inflow"],
                f"{context} NormalNetInflow + SmallNetInflow versus RetailNetInflow",
            )
            self._check_close(
                values["cumulative_main_net_inflow"]
                + values["cumulative_retail_net_inflow"],
                Decimal(0),
                f"{context} main and retail net flow",
            )
            if (
                previous_main_inflow is not None
                and values["cumulative_main_inflow"] < previous_main_inflow
            ):
                self._fail("Tencent cumulative MainInflow decreased")
            if (
                previous_main_outflow is not None
                and values["cumulative_main_outflow"] < previous_main_outflow
            ):
                self._fail("Tencent cumulative MainOutflow decreased")
            previous_main_inflow = values["cumulative_main_inflow"]
            previous_main_outflow = values["cumulative_main_outflow"]
            rows.append(
                _ProviderFundFlowIntradayRow(
                    instrument_id=instrument_id,
                    trade_date=trade_date,
                    time=time_text,
                    price=price,
                    **values,
                    source_record_id=f"{symbol}:{timestamp_text}",
                    source_url=request_url,
                    captured_at=captured_at,
                )
            )
        return tuple(rows)

    def _parse_history(
        self,
        raw: Mapping[str, Any],
        *,
        instrument_id: InstrumentId,
        symbol: str,
        request_url: str,
        captured_at: datetime,
    ) -> tuple[_ProviderFundFlowDailyRow, ...]:
        source_rows = raw.get("oneDayKlineList")
        if not isinstance(source_rows, list) or not source_rows:
            self._fail("Tencent historyFundFlow.oneDayKlineList is missing or empty")
        if len(source_rows) > 20:
            self._fail("Tencent historyFundFlow returned more than 20 requested days")
        rows: list[_ProviderFundFlowDailyRow] = []
        previous_date: date | None = None
        seen: set[date] = set()
        for index, source_row in enumerate(source_rows):
            context = f"historyFundFlow.oneDayKlineList[{index}]"
            if not isinstance(source_row, dict):
                self._fail(f"Tencent {context} must be an object")
            trade_date = self._date(source_row.get("date"), f"{context}.date")
            if trade_date in seen:
                self._fail(f"Tencent historyFundFlow contains duplicate date {trade_date}")
            seen.add(trade_date)
            if previous_date is not None and trade_date <= previous_date:
                self._fail("Tencent fund-flow history dates are not strictly ascending")
            previous_date = trade_date
            main_net_inflow = self._decimal(
                source_row.get("mainNetIn"),
                f"{context}.mainNetIn",
            )
            close = self._decimal(source_row.get("price"), f"{context}.price")
            if close <= 0:
                self._fail(f"Tencent {context}.price must be positive")
            rows.append(
                _ProviderFundFlowDailyRow(
                    instrument_id=instrument_id,
                    trade_date=trade_date,
                    main_net_inflow=main_net_inflow,
                    close=close,
                    source_record_id=f"{symbol}:{trade_date.isoformat()}:historyFundFlow",
                    source_url=request_url,
                    captured_at=captured_at,
                )
            )
        return tuple(rows)

    def _validate_five_day(
        self,
        raw: Mapping[str, Any],
        *,
        daily_rows: Sequence[_ProviderFundFlowDailyRow],
        symbol: str,
    ) -> None:
        source_rows = raw.get("DayMainNetInList")
        if not isinstance(source_rows, list):
            self._fail("Tencent fiveDayFundFlow.DayMainNetInList must be an array")
        expected_count = min(5, len(daily_rows))
        if len(source_rows) != expected_count:
            self._fail("Tencent five-day list length does not match available history")
        parsed: list[tuple[date, Decimal]] = []
        seen: set[date] = set()
        for index, source_row in enumerate(source_rows):
            context = f"fiveDayFundFlow.DayMainNetInList[{index}]"
            if not isinstance(source_row, dict):
                self._fail(f"Tencent {context} must be an object")
            returned_code = source_row.get("stockCode")
            if returned_code is not None and returned_code != symbol:
                self._fail(f"Tencent {context}.stockCode does not match {symbol}")
            trade_date = self._date(source_row.get("date"), f"{context}.date")
            if trade_date in seen:
                self._fail("Tencent five-day fund-flow list contains a duplicate date")
            seen.add(trade_date)
            value = self._decimal(source_row.get("mainNetIn"), f"{context}.mainNetIn")
            parsed.append((trade_date, value))
        if any(left[0] >= right[0] for left, right in zip(parsed, parsed[1:])):
            self._fail("Tencent five-day fund-flow dates are not strictly ascending")
        expected = daily_rows[-expected_count:]
        for (actual_date, actual_value), daily in zip(parsed, expected, strict=True):
            if actual_date != daily.trade_date or actual_value != daily.main_net_inflow:
                self._fail("Tencent five-day list does not match history daily records")
        reported_total = self._decimal(
            raw.get("fiveDayMainNetIn"),
            "fiveDayFundFlow.fiveDayMainNetIn",
        )
        computed_total = sum((value for _, value in parsed), Decimal(0))
        self._check_close(
            reported_total,
            computed_total,
            "fiveDayFundFlow total versus DayMainNetInList sum",
        )

    def _validate_summary(
        self,
        history: Mapping[str, Any],
        *,
        daily_rows: Sequence[_ProviderFundFlowDailyRow],
        symbol: str,
    ) -> None:
        summary = history.get("summary")
        if not isinstance(summary, dict):
            self._fail("Tencent historyFundFlow.summary must be an object")
        for key, count in (("v0", 5), ("v2", 10), ("v4", 20)):
            expected_rows = daily_rows[-min(count, len(daily_rows)):]
            expected_total = sum(
                (row.main_net_inflow for row in expected_rows),
                Decimal(0),
            )
            reported_total = self._decimal(
                summary.get(key),
                f"historyFundFlow.summary.{key}",
            )
            self._check_close(
                reported_total,
                expected_total,
                f"historyFundFlow.summary.{key} versus recent daily sum",
            )

    def _validate_snapshot_trend(
        self,
        snapshot: _ProviderFundFlowSnapshot,
        final_row: _ProviderFundFlowIntradayRow,
    ) -> None:
        checks = (
            (final_row.cumulative_main_net_inflow, snapshot.main_net_inflow, "main net inflow"),
            (final_row.cumulative_main_inflow, snapshot.main_inflow, "main inflow"),
            (final_row.cumulative_main_outflow, snapshot.main_outflow, "main outflow"),
            (
                final_row.cumulative_retail_net_inflow,
                snapshot.retail_inflow - snapshot.retail_outflow,
                "retail net inflow",
            ),
            (
                final_row.cumulative_super_large_net_inflow,
                snapshot.super_large_net_inflow,
                "super-large net inflow",
            ),
            (
                final_row.cumulative_large_net_inflow,
                snapshot.large_net_inflow,
                "large net inflow",
            ),
            (
                final_row.cumulative_medium_net_inflow,
                snapshot.medium_net_inflow,
                "medium net inflow",
            ),
            (
                final_row.cumulative_small_net_inflow,
                snapshot.small_net_inflow,
                "small net inflow",
            ),
        )
        for left, right, label in checks:
            self._check_close(left, right, f"todayFundTrend final versus todayFundFlow {label}")

    def _required_mapping(self, data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        value = data.get(key)
        if not isinstance(value, dict):
            self._fail(f"Tencent hsfundtab data is missing required {key} object")
        return value

    def _decimal(self, value: object, label: str) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            self._fail(f"Tencent {label} must be a numeric string or number")
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            self._fail(f"Tencent {label} is not a valid Decimal")
        if not parsed.is_finite():
            self._fail(f"Tencent {label} must be finite")
        return parsed

    def _date(self, value: object, label: str) -> date:
        if not isinstance(value, str):
            self._fail(f"Tencent {label} must be an ISO date string")
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            self._fail(f"Tencent {label} is not a valid date")
        if parsed.isoformat() != value:
            self._fail(f"Tencent {label} is not a canonical ISO date")
        return parsed

    def _check_close(self, actual: Decimal, expected: Decimal, label: str) -> None:
        if abs(actual - expected) > _ARITHMETIC_TOLERANCE:
            self._fail(
                f"Tencent {label} differs by more than "
                f"{_ARITHMETIC_TOLERANCE} CNY"
            )

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self._source, reason)
