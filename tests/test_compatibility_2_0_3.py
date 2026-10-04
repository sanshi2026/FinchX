"""Released 2.0.2 boundaries, historical data and the StockX extension seam."""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import inspect
import json
from pathlib import Path
import re
from typing import get_type_hints

from schema_compat import canonical_schema

from finchx import FinchX
from finchx.client import CLIENT_ENDPOINTS
from finchx.collectors import (
    CachePolicy, Collector, CollectorRoute, FetchAttempt, FetchResult, RoutingPolicy,
)
from finchx.contracts import Source
from finchx.datasets import FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET, FinancialSummaryRequest
from finchx.datasets.fundamental_financial_summary import normalize_financial_summary
from finchx.providers import PROVIDER_REGISTRY, ProviderRegistry, ProviderSpec
from finchx.providers.iwencai import IwencaiProvider
from finchx.providers.tencent_f10 import (
    TencentF10Provider, _CapitalSnapshot, _CompanyProfile, _FinancialPeriod,
    _HolderSummarySnapshot, _ProviderF10Payload,
)
from finchx.storage.serialization import _model_registry, loads


FIXTURES = Path(__file__).parent / "fixtures" / "compatibility"
BASELINE = json.loads((FIXTURES / "v2_0_2_contract.json").read_text(encoding="utf-8"))


def _qualified(model):
    return model.__module__ + ":" + model.__qualname__


def _signature(value):
    text = re.sub(r" at 0x[0-9a-f]+", " at <address>", str(inspect.signature(value)))
    return re.sub(
        r"frozenset\(\{([^}]+)\}\)",
        lambda match: "frozenset({" + ", ".join(sorted(match[1].split(", "))) + "})",
        text,
    )


def _schema_digest(schema):
    return hashlib.sha256(
        json.dumps(canonical_schema(schema), sort_keys=True, ensure_ascii=True).encode()
    ).hexdigest()


def test_released_public_methods_and_constructor_contracts():
    client = FinchX()
    for key, signature in BASELINE["methods"].items():
        namespace, method = key.split(".")
        actual = getattr(getattr(client, namespace), method)
        assert _signature(actual) == signature
        get_type_hints(actual)  # Moved methods must still resolve their annotations.
    for cls in (FinchX, Collector, CollectorRoute, FetchResult, FetchAttempt, RoutingPolicy, CachePolicy):
        assert _signature(cls) == BASELINE["constructors"][cls.__name__]


def test_released_models_and_registry_identities():
    registry = _model_registry()
    for model_id, expected_digest in BASELINE["models"].items():
        schema = registry[model_id].model_json_schema(by_alias=True)
        actual = _schema_digest(schema)
        assert actual == expected_digest, model_id
    assert [
        [e.namespace, e.method, e.dataset.name, e.dataset.schema_version,
         _qualified(e.request_type), _qualified(e.dataset.data_type)]
        for e in CLIENT_ENDPOINTS
    ] == BASELINE["endpoints"]
    assert [
        [s.provider_id, [[x.name, x.schema_version] for x in s.supported_datasets],
         s.requires_auth, list(s.optional_dependencies), repr(s.routing_semantics), s.auto_selectable]
        for s in PROVIDER_REGISTRY.list_providers()
    ] == BASELINE["providers"]


def test_old_import_paths_and_query_instances():
    from finchx import collector
    from finchx.collectors import core, results, runtime
    from finchx.client import MarketNamespace
    from finchx.api.market import MarketNamespace as Implementation
    from finchx.datasets import TradingCalendarService
    from finchx.datasets.trading_calendar_service import TradingCalendarService as Legacy
    from finchx.query.trading_calendar import TradingCalendarService as Query
    from finchx import query
    from finchx.client import _Namespace

    assert collector.Collector is core.Collector is runtime.Collector is Collector
    assert core.FetchResult is results.FetchResult is FetchResult
    assert core._RouteResult is results._RouteResult
    assert MarketNamespace is Implementation
    assert TradingCalendarService is Legacy is Query
    assert get_type_hints(_Namespace.__init__)["client"] is FinchX
    assert isinstance(query.market_news, query.MarketNewsService)
    assert isinstance(query.forum, query.ForumService)
    assert isinstance(query.news, query.NewsService)


def test_serialized_2_0_2_models_remain_readable():
    objects = loads((FIXTURES / "v2_0_2_storage.json").read_text(encoding="utf-8"))
    assert objects["record"].entity_id.code == "300308"
    assert objects["record"].data == {"price": "0", "unknown": None}
    assert _qualified(type(objects["financial"])) == "finchx.datasets.financial_statement:FinancialStatementData"
    assert objects["news"].source_document_id == "1"
    assert objects["scalars"]["zero"] == Decimal("0")
    assert objects["scalars"]["missing"] is None
    assert isinstance(objects["scalars"]["values"], tuple)


def test_stockx_style_provider_subclass_preserves_native_dynamic_fields():
    class ConsumerProvider(IwencaiProvider):
        @classmethod
        def _normalize_selection_rows(cls, records):
            data = super()._normalize_selection_rows(records)
            raw = cls._clean_mapping(records[0])
            assert cls._match_code(raw["股票代码"]).group(1) == "300308"
            return [data[0].model_copy(update={
                "price": cls._decimal_field(raw["最新价"]),
                "change_rate": cls._percentage_field(raw["涨跌幅"]),
                "amount": cls._decimal_field(raw["成交额"], amount=True),
                "volume": cls._integer_field(raw["成交量"]),
                "extra_fields": dict(records[0]),
            })]

    raw = {"股票代码": "300308.SZ", "股票简称": "样本", "最新价": "12.30",
           "涨跌幅": "0", "成交额": "0", "成交量": 0,
           "预测列[20261231]": "42.00", "未知列": None}
    record = ConsumerProvider._normalize_selection_rows([raw])[0]
    payload = record.model_dump(mode="json", by_alias=True)
    assert payload["instrumentId"]["code"] == "300308"
    assert payload["changeRate"] == "0"
    assert payload["amount"] == "0"
    assert payload["volume"] == 0
    assert payload["extraFields"] == raw


def test_financial_summary_audit_keeps_periods_and_zero_missing_semantics():
    request = FinancialSummaryRequest(instrumentId={
        "code": "300308", "market": "cn_a", "kind": "equity", "exchange": "szse",
    })
    first = _FinancialPeriod("2026中报", None, "interim",
                             {"eps": Decimal("0"), "net_profit": None},
                             {"eps": "hydb.stock.mgsy", "net_profit": "zyzb.detail.jlr"})
    revised = _FinancialPeriod("2026中报", None, "interim", {"eps": Decimal("1")},
                               {"eps": "hytrend.f_mgsy"})
    row = _ProviderF10Payload(
        instrument_id=request.instrument_id,
        raw_payload={}, company_profile=_CompanyProfile(None, None, None, None),
        capital_snapshot=_CapitalSnapshot(None, None),
        holder_summary=_HolderSummarySnapshot(None, None, None, None, None),
        executive_snapshots=(), executive_share_changes=(), dividends=(), repurchases=(),
        revenue_rows=(), industry_comparison=None,
        captured_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
        source_record_id="synthetic-summary", source_url="https://example.invalid/summary",
        current_financial=first, historical_financial=(revised,),
    )
    result = normalize_financial_summary(request, row, source=Source(providerId="synthetic"))
    periods = result.data["periods"]
    assert periods[0]["eps"] == "0" and periods[0]["netProfit"] is None
    assert len(periods) == 2  # Duplicate native periods remain separate observations.
    context = result.provenance.adjustments[0].details
    assert [p["reportedPeriodLabel"] for p in context["periods"]] == ["2026中报", "2026中报"]
    assert context["periods"][0]["sourceFields"]["eps"] == "hydb.stock.mgsy"
    assert context["periodBasis"] == context["netProfitAttribution"] == context["epsBasis"] == "unspecified"
    assert not result.quality.issues

    class FixtureProvider:
        source = Source(providerId="synthetic")

        def fetch_bundle(self, request):
            return row

    registry = ProviderRegistry([ProviderSpec(
        provider_id="synthetic", provider=FixtureProvider,
        supported_datasets=(FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET,),
    )])
    fetched = FinchX(registry=registry).fundamental.financial_summary("300308", use_cache=False)
    assert fetched.to_dicts() == [result.data]
    assert fetched.data.provenance == result.provenance
    assert fetched.warnings == () and not fetched.fallback_used and not fetched.cache_hit


def test_financial_source_mapping_matches_existing_fallback_and_null_precedence():
    provider = TencentF10Provider()
    parsed = provider._parse_current_financial(
        {"date": "2026中报", "detail": {"yyzsr": None, "yysr": "1亿元", "srzzl": "0%"}}, {},
    )
    assert parsed.metrics["revenue"] is None  # Retain the old numeric behavior.
    assert parsed.metrics["revenue_growth"] == Decimal("0")
    assert parsed.source_fields["revenue"] == "zyzb.detail.yyzsr"
    assert parsed.source_fields["revenue_growth"] == "zyzb.detail.srzzl"


def test_schema_comparison_accepts_only_documented_upstream_spelling_changes():
    schema = {"type": "object", "additionalProperties": True,
              "properties": {"kind": {"const": "equity", "enum": ["equity"]}}}
    expected = {"type": "object", "properties": {"kind": {"const": "equity"}}}
    assert canonical_schema(schema) == expected
    assert schema["additionalProperties"] is True  # Do not mutate generated schemas.
    assert canonical_schema({"enum": ["equity"]}) == {"const": "equity"}


def test_schema_comparison_keeps_application_constraints_and_conflicting_values():
    schema = {"additionalProperties": False, "pattern": "^custom$", "minimum": 0,
              "required": ["price"], "enum": ["equity", "index"],
              "properties": {"kind": {"const": "index", "enum": ["equity"]}}}
    assert canonical_schema(schema) == schema
