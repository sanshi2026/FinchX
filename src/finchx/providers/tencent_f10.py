"""Tencent jiankuang F10 source adapter.

The endpoint is deliberately fetched once and represented as one complete
source payload.  Dataset normalizers consume the typed source sections they
need while ``raw_payload`` keeps every source field available to offline
audits until FinchX has a storage layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, NoReturn
from urllib.parse import urlencode

from finchx.contracts import Source
from finchx.datasets.fundamental_common import FundamentalRequest
from finchx.entities import Exchange
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


TENCENT_F10_ENDPOINT = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/stockinfo/jiankuang"
)
_EXCHANGE_PREFIX = {Exchange.SSE: "sh", Exchange.SZSE: "sz"}
_JSONP = re.compile(r"^\s*[\w$.]+\s*\((.*)\)\s*;?\s*$", re.DOTALL)

@dataclass(frozen=True)
class _FinancialPeriod:
    reported_period_label: str
    period_end: date | None
    period_type: str
    metrics: Mapping[str, Decimal | None]
    source_fields: Mapping[str, str]


@dataclass(frozen=True)
class _RevenueRow:
    reported_period_label: str
    period_end: date | None
    dimension: str
    item_name: str
    revenue: Decimal | None
    revenue_share: Decimal | None
    source_group: str
    is_rollup: bool
    source_unit: str | None
    source_income: str | None
    source_share: str | None


@dataclass(frozen=True)
class _CompanyProfile:
    company_name: str | None
    business_description: str | None
    issue_price: Decimal | None
    listing_date: date | None


@dataclass(frozen=True)
class _CapitalSnapshot:
    total_shares: int | None
    float_shares: int | None


@dataclass(frozen=True)
class _HolderSummarySnapshot:
    shareholder_count: int | None
    average_shares_per_holder: Decimal | None
    shareholder_count_change: Decimal | None
    top10_float_holder_ratio: Decimal | None
    top10_holder_ratio: Decimal | None


@dataclass(frozen=True)
class _ExecutiveSnapshot:
    name: str
    roles: tuple[str, ...]
    shares: int | None
    compensation: Decimal | None


@dataclass(frozen=True)
class _ExecutiveShareChange:
    event_date: date | None
    person_name: str | None
    share_change: int | None
    average_price: Decimal | None


@dataclass(frozen=True)
class _Dividend:
    fiscal_year: int | None
    announcement_date: date | None
    stock_dividend_per_10: Decimal | None
    capitalization_per_10: Decimal | None
    cash_dividend_per_10: Decimal | None
    rights_issue_per_10: Decimal | None
    record_date: date | None
    ex_date: date | None
    description: str | None


@dataclass(frozen=True)
class _Repurchase:
    repurchase_date: date | None
    quantity: int | None
    average_price: Decimal | None
    currency: str | None
    fund_amount: Decimal | None
    market: str | None


@dataclass(frozen=True)
class _IndustryComparison:
    reported_period_label: str
    period_end: date | None
    industry_name: str | None
    company: Mapping[str, Decimal | None]
    industry_average: Mapping[str, Decimal | None]
    industry_max: Mapping[str, Decimal | None]
    industry_min: Mapping[str, Decimal | None]
    source_updated_at: datetime | None


@dataclass(frozen=True)
class _ProviderF10Payload:
    instrument_id: Any
    raw_payload: Mapping[str, Any]
    company_profile: _CompanyProfile
    capital_snapshot: _CapitalSnapshot
    holder_summary: _HolderSummarySnapshot
    executive_snapshots: tuple[_ExecutiveSnapshot, ...]
    executive_share_changes: tuple[_ExecutiveShareChange, ...]
    dividends: tuple[_Dividend, ...]
    repurchases: tuple[_Repurchase, ...]
    current_financial: _FinancialPeriod | None
    historical_financial: tuple[_FinancialPeriod, ...]
    revenue_rows: tuple[_RevenueRow, ...]
    industry_comparison: _IndustryComparison | None
    source_record_id: str
    source_url: str
    captured_at: datetime


F10_SECTION_NAMES = (
    "zyzb",
    "gsjj",
    "zysr",
    "gdgb",
    "ggzjc",
    "ggjj",
    "fhsp",
    "pxmzb",
    "huigou",
    "hydb",
    "hytrend",
)

# This inventory is intentionally explicit.  The field-coverage test compares
# every leaf path in the committed raw fixtures with this set, so a newly
# observed Tencent field cannot disappear silently.
F10_FIELD_INVENTORY = frozenset(
    {
        "code", "msg",
        "data.zyzb.date", "data.zyzb.detail.date", "data.zyzb.detail.mgsy",
        "data.zyzb.detail.jlr", "data.zyzb.detail.jlrzzl", "data.zyzb.detail.yyzsr", "data.zyzb.detail.yysr",
        "data.zyzb.detail.zsrzzl", "data.zyzb.detail.srzzl", "data.zyzb.detail.mgjzc",
        "data.zyzb.detail.sy", "data.zyzb.detail.jzc", "data.zyzb.detail.sy_jzc",
        "data.zyzb.detail.jzcsyl", "data.zyzb.detail.zcfzl", "data.zyzb.detail.syl",
        "data.zyzb.detail.sjl",
        "data.gsjj.gsmz", "data.gsjj.yw", "data.gsjj.jg", "data.gsjj.riqi",
        "data.gsjj.dy", "data.gsjj.plate[].name", "data.gsjj.plate[].id",
        "data.gsjj.plate[].level", "data.gsjj.concept[].name", "data.gsjj.concept[].id",
        "data.gsjj.concept[].tag", "data.gsjj.area[].name", "data.gsjj.area[].id",
        "data.zysr[].date", "data.zysr[].detail[].type", "data.zysr[].detail[].detail[].name",
        "data.zysr[].detail[].detail[].unit", "data.zysr[].detail[].detail[].income",
        "data.zysr[].detail[].detail[].zb", "data.zysr[].detail[].others[].name",
        "data.zysr[].detail[].others[].unit", "data.zysr[].detail[].others[].income",
        "data.zysr[].detail[].others[].zb",
        "data.gdgb.zgb", "data.gdgb.ltgb", "data.gdgb.zgb_r", "data.gdgb.gdrshb",
        "data.gdgb.rjcg", "data.gdgb.gdrs", "data.gdgb.ltgdzb", "data.gdgb.gdzb",
        "data.ggzjc[].date", "data.ggzjc[].gg", "data.ggzjc[].bdl", "data.ggzjc[].jj",
        "data.ggjj[].gg", "data.ggjj[].zw", "data.ggjj[].cgs", "data.ggjj[].xc",
        "data.fhsp[].nd", "data.fhsp[].date", "data.fhsp[].type", "data.fhsp[].sg",
        "data.fhsp[].zz", "data.fhsp[].fh", "data.fhsp[].pg", "data.fhsp[].djr",
        "data.fhsp[].cqr", "data.fhsp[].content", "data.pxmzb.pxmzb", "data.pxmzb.px",
        "data.pxmzb.fx", "data.pxmzb.zf", "data.pxmzb.pg", "data.pxmzb.no[]",
        "data.huigou[].REDEMPTION_QUANTITY", "data.huigou[].REDEEN_AVG_PRICE",
        "data.huigou[].CURRENCY", "data.huigou[].FUND", "data.huigou[].REP_DATE",
        "data.huigou[].MARKET",
        "data.hydb.date", "data.hydb.hyname", "data.hydb.stock.stockcode",
        "data.hydb.stock.date", "data.hydb.stock.industry", "data.hydb.stock.mgsy",
        "data.hydb.stock.yysr", "data.hydb.stock.jlr", "data.hydb.stock.mgjzc",
        "data.hydb.stock.jzcsyl", "data.hydb.stock.sc", "data.hydb.stock.zsz",
        "data.hydb.stock.create_time", "data.hydb.stock.Fzcfzl", "data.hydb.stock.Fmll",
        "data.hydb.stock.Fyszs", "data.hydb.stock.Fjlrzs", "data.hydb.stock.sjl",
        "data.hydb.stock.syl", "data.hydb.stock.gxl", "data.hydb.stock.f_mgsy",
        "data.hydb.stock.f_yysr", "data.hydb.stock.f_jlr", "data.hydb.stock.f_mgjzc",
        "data.hydb.stock.f_jzcsyl", "data.hydb.stock.f_zsz", "data.hydb.stock.f_Fzcfzl",
        "data.hydb.stock.f_Fmll", "data.hydb.stock.f_Fyszs", "data.hydb.stock.f_Fjlrzs",
        "data.hydb.stock.f_gxl", "data.hydb.stock.f_syl", "data.hydb.stock.f_sjl",
        "data.hydb.stock.stockname",
        "data.hydb.hy.mgsy", "data.hydb.hy.yysr", "data.hydb.hy.jlr",
        "data.hydb.hy.mgjzc", "data.hydb.hy.jzcsyl", "data.hydb.hy.zsz",
        "data.hydb.hy.Fzcfzl", "data.hydb.hy.Fmll", "data.hydb.hy.Fyszs",
        "data.hydb.hy.Fjlrzs", "data.hydb.hy.sjl", "data.hydb.hy.syl", "data.hydb.hy.gxl",
        "data.hydb.hy.f_mgsy", "data.hydb.hy.f_yysr", "data.hydb.hy.f_jlr",
        "data.hydb.hy.f_mgjzc", "data.hydb.hy.f_jzcsyl", "data.hydb.hy.f_zsz",
        "data.hydb.hy.f_Fzcfzl", "data.hydb.hy.f_Fmll", "data.hydb.hy.f_Fyszs",
        "data.hydb.hy.f_Fjlrzs", "data.hydb.hy.f_gxl", "data.hydb.hy.f_syl", "data.hydb.hy.f_sjl",
        "data.hydb.hymax.mgsy", "data.hydb.hymax.yysr", "data.hydb.hymax.jlr",
        "data.hydb.hymax.mgjzc", "data.hydb.hymax.jzcsyl", "data.hydb.hymax.zsz",
        "data.hydb.hymin.mgsy", "data.hydb.hymin.yysr", "data.hydb.hymin.jlr",
        "data.hydb.hymin.mgjzc", "data.hydb.hymin.jzcsyl", "data.hydb.hymin.zsz",
        "data.hytrend[].date", "data.hytrend[].yyzsr", "data.hytrend[].yysr",
        "data.hytrend[].t_yyzsr", "data.hytrend[].t_yysr", "data.hytrend[].f_yyzsr",
        "data.hytrend[].f_yysr", "data.hytrend[].jlr", "data.hytrend[].t_jlr",
        "data.hytrend[].f_jlr", "data.hytrend[].mgsy", "data.hytrend[].t_mgsy",
        "data.hytrend[].f_mgsy",
    }
)

_EXPECTED_FIELDS: dict[str, set[str]] = {
    "zyzb": {"date", "detail"},
    "zyzb.detail": {"date", "mgsy", "jlr", "jlrzzl", "yyzsr", "yysr", "zsrzzl", "srzzl", "mgjzc", "sy", "jzc", "sy_jzc", "jzcsyl", "zcfzl", "syl", "sjl"},
    "gsjj": {"gsmz", "yw", "jg", "riqi", "dy", "plate", "concept", "area"},
    "gsjj.plate[]": {"name", "id", "level"},
    "gsjj.concept[]": {"name", "id", "tag"},
    "gsjj.area[]": {"name", "id"},
    "zysr[]": {"date", "detail"},
    "zysr[].detail[]": {"type", "detail", "others"},
    "zysr[].detail[].detail[]": {"name", "unit", "income", "zb"},
    "zysr[].detail[].others[]": {"name", "unit", "income", "zb"},
    "gdgb": {"zgb", "ltgb", "zgb_r", "gdrshb", "rjcg", "gdrs", "ltgdzb", "gdzb"},
    "ggzjc[]": {"date", "gg", "bdl", "jj"},
    "ggjj[]": {"gg", "zw", "cgs", "xc"},
    "fhsp[]": {"nd", "date", "type", "sg", "zz", "fh", "pg", "djr", "cqr", "content"},
    "pxmzb": {"pxmzb", "px", "fx", "zf", "pg", "no"},
    "huigou[]": {"REDEMPTION_QUANTITY", "REDEEN_AVG_PRICE", "CURRENCY", "FUND", "REP_DATE", "MARKET"},
    "hydb": {"date", "hyname", "stock", "hy", "hymax", "hymin"},
    "hydb.stock": {"stockcode", "date", "industry", "mgsy", "yysr", "jlr", "mgjzc", "jzcsyl", "sc", "zsz", "create_time", "Fzcfzl", "Fmll", "Fyszs", "Fjlrzs", "sjl", "syl", "gxl", "f_mgsy", "f_yysr", "f_jlr", "f_mgjzc", "f_jzcsyl", "f_zsz", "f_Fzcfzl", "f_Fmll", "f_Fyszs", "f_Fjlrzs", "f_gxl", "f_syl", "f_sjl", "stockname"},
    "hydb.hy": {"mgsy", "yysr", "jlr", "mgjzc", "jzcsyl", "zsz", "Fzcfzl", "Fmll", "Fyszs", "Fjlrzs", "sjl", "syl", "gxl", "f_mgsy", "f_yysr", "f_jlr", "f_mgjzc", "f_jzcsyl", "f_zsz", "f_Fzcfzl", "f_Fmll", "f_Fyszs", "f_Fjlrzs", "f_gxl", "f_syl", "f_sjl"},
    "hydb.hymax": {"mgsy", "yysr", "jlr", "mgjzc", "jzcsyl", "zsz"},
    "hydb.hymin": {"mgsy", "yysr", "jlr", "mgjzc", "jzcsyl", "zsz"},
    "hytrend[]": {"date", "yyzsr", "yysr", "t_yyzsr", "t_yysr", "f_yyzsr", "f_yysr", "jlr", "t_jlr", "f_jlr", "mgsy", "t_mgsy", "f_mgsy"},
}


def iter_f10_leaf_paths(value: Any, path: str = "") -> set[str]:
    """Return normalized JSON leaf paths, replacing array indexes with ``[]``."""
    if isinstance(value, Mapping):
        paths: set[str] = set()
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            paths.update(iter_f10_leaf_paths(child, child_path))
        return paths
    if isinstance(value, list):
        paths: set[str] = set()
        for child in value:
            paths.update(iter_f10_leaf_paths(child, f"{path}[]"))
        return paths
    return {path}


class TencentF10Provider:
    """Fetch and parse one complete Tencent jiankuang response."""

    def __init__(
        self,
        transport: _TencentTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport or _UrllibTencentTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(providerId="tencent.finance.qq", sourceUrl=TENCENT_F10_ENDPOINT)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_bundle(self, request: FundamentalRequest) -> _ProviderF10Payload:
        """Acquire one complete jiankuang source bundle for this request context."""
        return self.fetch_raw_f10(request)

    def fetch_raw_f10(self, request: FundamentalRequest) -> _ProviderF10Payload:
        if not isinstance(request, FundamentalRequest):
            self._fail("request must be a FundamentalRequest")
        try:
            from finchx.datasets.market_instrument_sector_snapshot import _validate_sector_instrument
            _validate_sector_instrument(request.instrument_id)
        except ValueError as exc:
            self._fail(str(exc))
        prefix = _EXCHANGE_PREFIX[request.instrument_id.exchange]
        symbol = f"{prefix}{request.instrument_id.code}"
        params = {"code": symbol, "app": "official_website"}
        request_url = f"{TENCENT_F10_ENDPOINT}?{urlencode(params)}"
        try:
            response = self._transport.get(
                TENCENT_F10_ENDPOINT,
                params=params,
                headers=_HEADERS,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        except _TencentTransportFailure as exc:
            self._fail(f"Tencent jiankuang transport failure: {exc}")
        except Exception as exc:
            self._fail(f"Tencent jiankuang transport failure: {type(exc).__name__}")
        status_reason = http_status_failure_reason(response.status_code)
        if status_reason is not None:
            self._fail(f"Tencent jiankuang returned {status_reason}")
        if not response.text.strip():
            self._fail("Tencent jiankuang returned an empty payload")
        document = self._decode(response.text)
        self._validate_document(document, request)
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("capture clock returned a naive timestamp")
        data = document["data"]
        return _ProviderF10Payload(
            instrument_id=request.instrument_id,
            raw_payload=document,
            company_profile=self._parse_company_profile(data["gsjj"]),
            capital_snapshot=self._parse_capital_snapshot(data["gdgb"]),
            holder_summary=self._parse_holder_summary(data["gdgb"]),
            executive_snapshots=self._parse_executives(data["ggjj"]),
            executive_share_changes=self._parse_executive_share_changes(data["ggzjc"]),
            dividends=self._parse_dividends(data["fhsp"]),
            repurchases=self._parse_repurchases(data["huigou"]),
            current_financial=self._parse_current_financial(data["zyzb"], data["hydb"]),
            historical_financial=self._parse_historical_financial(data["hytrend"]),
            revenue_rows=self._parse_revenue(data["zysr"]),
            industry_comparison=self._parse_industry_comparison(data["hydb"]),
            source_record_id=f"{symbol}:jiankuang",
            source_url=request_url,
            captured_at=captured_at,
        )

    def _decode(self, text: str) -> dict[str, Any]:
        candidate = text.strip()
        matched = _JSONP.fullmatch(candidate)
        if matched is not None:
            candidate = matched.group(1)
        try:
            document = json.loads(candidate, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            self._fail(f"Tencent jiankuang returned malformed JSON/JSONP: {type(exc).__name__}")
        if not isinstance(document, dict):
            self._fail("Tencent jiankuang JSON root must be an object")
        return document

    def _validate_document(self, document: Mapping[str, Any], request: FundamentalRequest) -> None:
        if document.get("code") not in (0, "0") or isinstance(document.get("code"), bool):
            self._fail(f"Tencent jiankuang source code indicates failure: {document.get('code')!r}")
        if not isinstance(document.get("msg"), str):
            self._fail("Tencent jiankuang response msg must be text")
        data = document.get("data")
        if not isinstance(data, dict):
            self._fail("Tencent jiankuang data must be an object")
        if set(document) != {"code", "msg", "data"}:
            self._fail(f"Tencent jiankuang root has unexpected fields: {sorted(set(document) - {'code', 'msg', 'data'})}")
        if set(data) != set(F10_SECTION_NAMES):
            self._fail(f"Tencent jiankuang data sections differ: {sorted(set(data) ^ set(F10_SECTION_NAMES))}")
        for name in F10_SECTION_NAMES:
            self._validate_section_shape(name, data[name])
        stock = data["hydb"].get("stock")
        if isinstance(stock, Mapping):
            if stock.get("stockcode") not in (None, request.instrument_id.code):
                self._fail("Tencent jiankuang stock identity does not match requested code")
            expected_market = _EXCHANGE_PREFIX[request.instrument_id.exchange]
            if stock.get("sc") not in (None, expected_market):
                self._fail("Tencent jiankuang stock identity does not match requested exchange")

    def _validate_section_shape(self, section: str, value: Any) -> None:
        if section in {"zysr", "ggzjc", "ggjj", "fhsp", "hytrend"}:
            if not isinstance(value, list):
                self._fail(f"Tencent jiankuang data.{section} must be an array")
            for item in value:
                if not isinstance(item, dict):
                    self._fail(f"Tencent jiankuang data.{section} rows must be objects")
                self._validate_mapping_fields(section + "[]", item)
        elif section == "huigou":
            if not isinstance(value, list):
                self._fail("Tencent jiankuang data.huigou must be an array")
            for item in value:
                if not isinstance(item, dict):
                    self._fail("Tencent jiankuang data.huigou rows must be objects")
                self._validate_mapping_fields("huigou[]", item)
        else:
            if not isinstance(value, dict):
                self._fail(f"Tencent jiankuang data.{section} must be an object")
            self._validate_mapping_fields(section, value)
        if section == "zysr":
            for period in value:
                for group in period.get("detail", []):
                    if not isinstance(group, dict):
                        self._fail("Tencent jiankuang zysr groups must be objects")
                    self._validate_mapping_fields("zysr[].detail[]", group)
                    for key in ("detail", "others"):
                        for row in group.get(key, []):
                            if not isinstance(row, dict):
                                self._fail(f"Tencent jiankuang zysr {key} rows must be objects")
                            self._validate_mapping_fields(f"zysr[].detail[].{key}[]", row)
        if section == "gsjj":
            for key in ("plate", "concept", "area"):
                for row in value.get(key, []):
                    if not isinstance(row, dict):
                        self._fail(f"Tencent jiankuang gsjj.{key} rows must be objects")
                    self._validate_mapping_fields(f"gsjj.{key}[]", row)
        if section == "hydb":
            for key in ("stock", "hy", "hymax", "hymin"):
                child = value.get(key)
                if not isinstance(child, dict):
                    self._fail(f"Tencent jiankuang hydb.{key} must be an object")
                self._validate_mapping_fields(f"hydb.{key}", child)

    def _validate_mapping_fields(self, path: str, value: Mapping[str, Any]) -> None:
        expected = _EXPECTED_FIELDS.get(path)
        if expected is None:
            self._fail(f"Tencent jiankuang has no field inventory for {path}")
        unexpected = set(value) - expected
        if unexpected:
            self._fail(f"Tencent jiankuang {path} has unexpected fields: {sorted(unexpected)}")

    def _parse_company_profile(self, value: Mapping[str, Any]) -> _CompanyProfile:
        return _CompanyProfile(
            company_name=self._optional_text(value.get("gsmz")),
            business_description=self._optional_text(value.get("yw")),
            issue_price=self._display_price(value.get("jg")),
            listing_date=self._optional_date(value.get("riqi"), "gsjj.riqi"),
        )

    def _parse_capital_snapshot(self, value: Mapping[str, Any]) -> _CapitalSnapshot:
        total_value = value.get("zgb_r") if value.get("zgb_r") not in (None, "") else value.get("zgb")
        return _CapitalSnapshot(
            total_shares=self._share_count(total_value, "gdgb.zgb_r"),
            float_shares=self._share_count(value.get("ltgb"), "gdgb.ltgb"),
        )

    def _parse_holder_summary(self, value: Mapping[str, Any]) -> _HolderSummarySnapshot:
        return _HolderSummarySnapshot(
            shareholder_count=self._share_count(value.get("gdrs"), "gdgb.gdrs"),
            average_shares_per_holder=self._share_decimal(value.get("rjcg"), "gdgb.rjcg"),
            shareholder_count_change=self._percent(value.get("gdrshb")),
            top10_float_holder_ratio=self._percent(value.get("ltgdzb")),
            top10_holder_ratio=self._percent(value.get("gdzb")),
        )

    def _parse_executives(self, rows: list[dict[str, Any]]) -> tuple[_ExecutiveSnapshot, ...]:
        result: list[_ExecutiveSnapshot] = []
        for index, row in enumerate(rows):
            roles = tuple(
                role.strip()
                for role in re.split(r"[,，、]", self._required_text(row.get("zw"), f"ggjj[{index}].zw"))
                if role.strip()
            )
            result.append(
                _ExecutiveSnapshot(
                    name=self._required_text(row.get("gg"), f"ggjj[{index}].gg"),
                    roles=roles,
                    shares=self._share_count(row.get("cgs"), f"ggjj[{index}].cgs"),
                    compensation=self._display_amount(row.get("xc")),
                )
            )
        return tuple(result)

    def _parse_executive_share_changes(
        self,
        rows: list[dict[str, Any]],
    ) -> tuple[_ExecutiveShareChange, ...]:
        result: list[_ExecutiveShareChange] = []
        for index, row in enumerate(rows):
            result.append(
                _ExecutiveShareChange(
                    event_date=self._optional_date(row.get("date"), f"ggzjc[{index}].date"),
                    person_name=self._optional_text(row.get("gg")),
                    share_change=self._signed_share_count(row.get("bdl"), f"ggzjc[{index}].bdl"),
                    average_price=self._display_price(row.get("jj")),
                )
            )
        return tuple(result)

    def _parse_dividends(self, rows: list[dict[str, Any]]) -> tuple[_Dividend, ...]:
        result: list[_Dividend] = []
        for index, row in enumerate(rows):
            result.append(
                _Dividend(
                    fiscal_year=self._optional_year(row.get("nd"), f"fhsp[{index}].nd"),
                    announcement_date=self._optional_date(row.get("date"), f"fhsp[{index}].date"),
                    stock_dividend_per_10=self._share_decimal(row.get("sg"), f"fhsp[{index}].sg"),
                    capitalization_per_10=self._share_decimal(row.get("zz"), f"fhsp[{index}].zz"),
                    cash_dividend_per_10=self._display_amount(row.get("fh")),
                    rights_issue_per_10=self._share_decimal(row.get("pg"), f"fhsp[{index}].pg"),
                    record_date=self._optional_date(row.get("djr"), f"fhsp[{index}].djr"),
                    ex_date=self._optional_date(row.get("cqr"), f"fhsp[{index}].cqr"),
                    description=self._optional_text(row.get("content")),
                )
            )
        return tuple(result)

    def _parse_repurchases(self, rows: list[dict[str, Any]]) -> tuple[_Repurchase, ...]:
        result: list[_Repurchase] = []
        for index, row in enumerate(rows):
            result.append(
                _Repurchase(
                    repurchase_date=self._optional_date(row.get("REP_DATE"), f"huigou[{index}].REP_DATE"),
                    quantity=self._share_count(row.get("REDEMPTION_QUANTITY"), f"huigou[{index}].REDEMPTION_QUANTITY"),
                    average_price=self._display_price(row.get("REDEEN_AVG_PRICE")),
                    currency=self._optional_text(row.get("CURRENCY")),
                    fund_amount=self._display_amount(row.get("FUND")),
                    market=self._optional_text(row.get("MARKET")),
                )
            )
        return tuple(result)

    def _parse_current_financial(self, zyzb: Mapping[str, Any], hydb: Mapping[str, Any]) -> _FinancialPeriod | None:
        label = self._required_text(zyzb.get("date"), "zyzb.date")
        detail = zyzb.get("detail")
        if not isinstance(detail, dict):
            self._fail("Tencent jiankuang zyzb.detail must be an object")
        metrics: dict[str, Decimal | None] = {
            "eps": self._display_amount(detail.get("mgsy")),
            "revenue": self._display_amount(detail.get("yyzsr", detail.get("yysr"))),
            "revenue_growth": self._percent(detail.get("zsrzzl", detail.get("srzzl"))),
            "net_profit": self._display_amount(detail.get("jlr")),
            "net_profit_growth": self._percent(detail.get("jlrzzl")),
            "book_value_per_share": self._display_amount(detail.get("mgjzc")),
            "net_assets": self._display_amount(detail.get("jzc")),
            "goodwill": self._display_amount(detail.get("sy")),
            "goodwill_to_net_assets": self._percent(detail.get("sy_jzc")),
            "roe": self._percent(detail.get("jzcsyl")),
            "debt_ratio": self._percent(detail.get("zcfzl")),
            "gross_margin": None,
        }
        source_fields = {key: f"zyzb.detail.{field}" for key, field in {
            "eps": "mgsy", "revenue": ("yyzsr" if detail.get("yyzsr") is not None else "yysr"), "revenue_growth": "zsrzzl",
            "net_profit": "jlr", "net_profit_growth": "jlrzzl", "book_value_per_share": "mgjzc",
            "net_assets": "jzc", "goodwill": "sy", "goodwill_to_net_assets": "sy_jzc",
            "roe": "jzcsyl", "debt_ratio": "zcfzl",
        }.items()}
        stock = hydb.get("stock") if isinstance(hydb, Mapping) else None
        if isinstance(stock, Mapping):
            precise = self._parse_hydb_metrics(stock)
            for key in ("eps", "revenue", "net_profit", "book_value_per_share", "roe", "debt_ratio", "gross_margin", "revenue_growth", "net_profit_growth"):
                if precise.get(key) is not None:
                    metrics[key] = precise[key]
                    source_fields[key] = f"hydb.stock.{self._hydb_source_field(key)}"
        return _FinancialPeriod(
            reported_period_label=label,
            period_end=self._period_end(label),
            period_type=self._period_type(label),
            metrics=metrics,
            source_fields=source_fields,
        )

    def _parse_historical_financial(self, rows: list[dict[str, Any]]) -> tuple[_FinancialPeriod, ...]:
        result: list[_FinancialPeriod] = []
        for row in rows:
            label = self._required_text(row.get("date"), "hytrend.date")
            revenue_field = "f_yyzsr" if row.get("f_yyzsr") is not None else "f_yysr"
            revenue_growth_field = "t_yyzsr" if row.get("t_yyzsr") is not None else "t_yysr"
            metrics = {
                "eps": self._raw_decimal(row.get("f_mgsy")),
                "revenue": self._raw_decimal(row.get(revenue_field)),
                "revenue_growth": self._percentage_points(row.get(revenue_growth_field)),
                "net_profit": self._raw_decimal(row.get("f_jlr")),
                "net_profit_growth": self._percentage_points(row.get("t_jlr")),
                "book_value_per_share": None, "net_assets": None, "goodwill": None,
                "goodwill_to_net_assets": None, "roe": None, "debt_ratio": None,
                "gross_margin": None,
            }
            result.append(_FinancialPeriod(
                reported_period_label=label,
                period_end=None,
                period_type="annual",
                metrics=metrics,
                source_fields={key: f"hytrend.{field}" for key, field in {
                    "eps": "f_mgsy", "revenue": revenue_field, "revenue_growth": revenue_growth_field,
                    "net_profit": "f_jlr", "net_profit_growth": "t_jlr",
                }.items()},
            ))
        return tuple(result)

    def _parse_revenue(self, rows: list[dict[str, Any]]) -> tuple[_RevenueRow, ...]:
        result: list[_RevenueRow] = []
        for period in rows:
            label = self._required_text(period.get("date"), "zysr[].date")
            for group in period.get("detail", []):
                dimension = {"product": "product", "region": "region", "sector": "industry"}.get(group.get("type"))
                if dimension is None:
                    self._fail(f"Tencent jiankuang zysr has unknown type: {group.get('type')!r}")
                for source_group in ("detail", "others"):
                    for row in group.get(source_group, []):
                        name = self._required_text(row.get("name"), "zysr row name")
                        result.append(_RevenueRow(
                            reported_period_label=label,
                            period_end=self._period_end(label),
                            dimension=dimension,
                            item_name=name,
                            revenue=self._display_amount(row.get("income")),
                            revenue_share=self._percent(row.get("zb")),
                            source_group=source_group,
                            is_rollup=source_group == "detail" and name == "其他收入之和",
                            source_unit=self._optional_text(row.get("unit")),
                            source_income=row.get("income") if isinstance(row.get("income"), str) else None,
                            source_share=row.get("zb") if isinstance(row.get("zb"), str) else None,
                        ))
        return tuple(result)

    def _parse_industry_comparison(self, hydb: Mapping[str, Any]) -> _IndustryComparison | None:
        label = self._required_text(hydb.get("date"), "hydb.date")
        stock = hydb.get("stock")
        industry = hydb.get("hy")
        maximum = hydb.get("hymax")
        minimum = hydb.get("hymin")
        if not all(isinstance(item, dict) for item in (stock, industry, maximum, minimum)):
            return None
        return _IndustryComparison(
            reported_period_label=label,
            period_end=self._optional_date(stock.get("date"), "hydb.stock.date"),
            industry_name=self._optional_text(hydb.get("hyname")),
            company=self._parse_hydb_metrics(stock),
            industry_average=self._parse_hydb_metrics(industry),
            industry_max=self._parse_hydb_extreme(maximum),
            industry_min=self._parse_hydb_extreme(minimum),
            source_updated_at=self._source_time(stock.get("create_time")),
        )

    def _parse_hydb_metrics(self, value: Mapping[str, Any]) -> dict[str, Decimal | None]:
        return {
            "eps": self._raw_decimal(value.get("mgsy")),
            "revenue": self._raw_decimal(value.get("yysr")),
            "net_profit": self._raw_decimal(value.get("jlr")),
            "book_value_per_share": self._raw_decimal(value.get("mgjzc")),
            "roe": self._percentage_points(value.get("jzcsyl")),
            "debt_ratio": self._percentage_points(value.get("Fzcfzl")),
            "gross_margin": self._percentage_points(value.get("Fmll")),
            "revenue_growth": self._percentage_points(value.get("Fyszs")),
            "net_profit_growth": self._percentage_points(value.get("Fjlrzs")),
            "market_cap": self._raw_decimal(value.get("zsz")),
            "pe": self._raw_decimal(value.get("syl")),
            "pb": self._raw_decimal(value.get("sjl")),
            "dividend_yield": self._percentage_points(value.get("gxl")),
        }

    def _parse_hydb_extreme(self, value: Mapping[str, Any]) -> dict[str, Decimal | None]:
        return {
            "eps": self._raw_decimal(value.get("mgsy")),
            "revenue": self._raw_decimal(value.get("yysr")),
            "net_profit": self._raw_decimal(value.get("jlr")),
            "book_value_per_share": self._raw_decimal(value.get("mgjzc")),
            "roe": self._percentage_points(value.get("jzcsyl")),
            "market_cap": self._raw_decimal(value.get("zsz")),
        }

    def _hydb_source_field(self, key: str) -> str:
        return {
            "eps": "mgsy", "revenue": "yysr", "net_profit": "jlr", "book_value_per_share": "mgjzc",
            "roe": "jzcsyl", "debt_ratio": "Fzcfzl", "gross_margin": "Fmll",
            "revenue_growth": "Fyszs", "net_profit_growth": "Fjlrzs",
        }[key]

    def _display_price(self, value: Any) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        if not isinstance(value, str):
            self._fail("Tencent jiankuang issue price must be source text")
        return self._raw_decimal(value.replace("元", "").replace(",", "").strip())

    def _display_quantity(self, value: Any, label: str) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        if not isinstance(value, str):
            self._fail(f"Tencent jiankuang {label} must be source text")
        text = value.replace(",", "").strip()
        for suffix in ("股", "户"):
            if text.endswith(suffix):
                text = text[:-1]
                break
        multiplier = Decimal("1")
        if text.endswith("亿"):
            multiplier = Decimal("100000000")
            text = text[:-1]
        elif text.endswith("万"):
            multiplier = Decimal("10000")
            text = text[:-1]
        elif text.endswith("千"):
            multiplier = Decimal("1000")
            text = text[:-1]
        parsed = self._raw_decimal(text)
        return None if parsed is None else parsed * multiplier

    def _share_decimal(self, value: Any, label: str) -> Decimal | None:
        return self._display_quantity(value, label)

    def _share_count(self, value: Any, label: str) -> int | None:
        parsed = self._display_quantity(value, label)
        if parsed is None:
            return None
        if parsed < 0 or parsed != parsed.to_integral_value():
            self._fail(f"Tencent jiankuang {label} must be a non-negative whole share count")
        return int(parsed)

    def _signed_share_count(self, value: Any, label: str) -> int | None:
        parsed = self._display_quantity(value, label)
        if parsed is None:
            return None
        if parsed != parsed.to_integral_value():
            self._fail(f"Tencent jiankuang {label} must be a whole share count")
        return int(parsed)

    def _optional_year(self, value: Any, label: str) -> int | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}", value.strip()):
            self._fail(f"Tencent jiankuang {label} must be a four-digit year")
        return int(value)

    def _display_amount(self, value: Any) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        if not isinstance(value, str):
            self._fail("Tencent jiankuang display amount must be source text")
        text = value.replace(",", "").replace("元", "").strip()
        multiplier = Decimal("1")
        if text.endswith("亿"):
            multiplier = Decimal("100000000")
            text = text[:-1]
        elif text.endswith("万"):
            multiplier = Decimal("10000")
            text = text[:-1]
        return self._raw_decimal(text) * multiplier if self._raw_decimal(text) is not None else None

    def _percent(self, value: Any) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        if not isinstance(value, str):
            self._fail("Tencent jiankuang percentage must be source text")
        return self._raw_decimal(value.replace("%", "").strip()) / Decimal("100")

    def _percentage_points(self, value: Any) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        return self._raw_decimal(value) / Decimal("100")

    def _raw_decimal(self, value: Any) -> Decimal | None:
        if value is None or (isinstance(value, str) and value.strip() in {"", "--", "-"}):
            return None
        try:
            result = value if isinstance(value, Decimal) else Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            self._fail(f"Tencent jiankuang value is not a valid Decimal: {value!r}")
        if not result.is_finite():
            self._fail("Tencent jiankuang Decimal must be finite")
        return result

    def _period_end(self, label: str) -> date | None:
        match = re.fullmatch(r"(\d{4})(中报|一季报|三季报|年报)", label)
        if match is None:
            return None
        year = int(match.group(1))
        month_day = {"一季报": (3, 31), "中报": (6, 30), "三季报": (9, 30), "年报": (12, 31)}[match.group(2)]
        return date(year, *month_day)

    def _period_type(self, label: str) -> str:
        if label.endswith("年报"):
            return "annual"
        if label.endswith(("一季报", "中报", "三季报")):
            return "interim"
        return "unknown"

    def _source_time(self, value: Any) -> datetime | None:
        if value in (None, "", "--", "-"):
            return None
        if not isinstance(value, str):
            self._fail("Tencent jiankuang create_time must be source text")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            self._fail(f"Tencent jiankuang create_time is not parseable: {value!r}")
        return parsed.replace(tzinfo=timezone(timedelta(hours=8)))

    def _optional_date(self, value: Any, label: str) -> date | None:
        if value in (None, "", "--", "-"):
            return None
        if not isinstance(value, str):
            self._fail(f"Tencent jiankuang {label} must be an ISO date text")
        try:
            return date.fromisoformat(value)
        except ValueError:
            self._fail(f"Tencent jiankuang {label} is not an ISO date")

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            self._fail("Tencent jiankuang text field must be text")
        return value.strip() or None

    def _required_text(self, value: Any, label: str) -> str:
        result = self._optional_text(value)
        if result is None:
            self._fail(f"Tencent jiankuang {label} must be non-empty text")
        return result

    def _fail(self, reason: str) -> NoReturn:
        raise ProviderError(self.source, reason)


__all__ = [
    "F10_FIELD_INVENTORY",
    "F10_SECTION_NAMES",
    "TencentF10Provider",
    "TENCENT_F10_ENDPOINT",
    "_ProviderF10Payload",
    "iter_f10_leaf_paths",
]
