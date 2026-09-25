from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import inspect

from jsonschema import Draft202012Validator, FormatChecker
import pytest
from pydantic import ValidationError
from referencing import Registry, Resource

from finchx import FinchX
from finchx.collector import Collector, FetchResult
from finchx.contracts import QualityIssueKind
from finchx.datasets import (
    ConceptRef,
    MARKET_CONCEPT_LIST_DATASET,
    MARKET_CONCEPT_OHLCV_DATASET,
    MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET,
)
from finchx.datasets.market_concept import (
    ConceptListRequest,
    ConceptOhlcvData,
    ConceptOhlcvRequest,
    ConceptQuoteSnapshotRequest,
    normalize_concept,
)
from finchx.providers import (
    DatasetRoutingSemantics,
    ProviderError,
    PROVIDER_REGISTRY,
    TonghuashunConceptProvider,
)
from finchx.providers.tonghuashun_concept import (
    DETAIL_URL,
    KLINE_URL,
    LIST_URL,
    QUOTE_URL,
)
from finchx.schemas import iter_schema_resources, read_schema


FIXTURES = Path(__file__).parent / "fixtures" / "tonghuashun"
CAPTURED_AT = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)
CONCEPT = ConceptRef(
    sectorType="concept",
    sectorName="人工智能",
    providerNamespace="tonghuashun_concept",
    providerSectorId="302035",
)


class FixtureResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload


class FixtureOpener:
    def __init__(self, routes: dict[str, bytes | Exception]):
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, request, timeout: int):
        url = request.full_url
        self.calls.append(url)
        result = self.routes[url]
        if isinstance(result, Exception):
            raise result
        return FixtureResponse(result)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _routes() -> dict[str, bytes | Exception]:
    values: dict[str, bytes | Exception] = {
        LIST_URL: _fixture("concept_list.html"),
        DETAIL_URL.format("302035"): _fixture("concept_detail.html"),
        QUOTE_URL.format("885728"): _fixture("realhead.js"),
        KLINE_URL.format("885728", "2026"): _fixture("kline_2026.js"),
        KLINE_URL.format("885728", "last"): _fixture("kline_last.js"),
    }
    return values


def _provider(routes: dict[str, bytes | Exception] | None = None) -> tuple[TonghuashunConceptProvider, FixtureOpener]:
    opener = FixtureOpener(routes or _routes())
    provider = TonghuashunConceptProvider(opener, clock=lambda: CAPTURED_AT)
    return provider, opener


def test_concept_directory_fixture_and_id_mapping():
    provider, _ = _provider()
    raw = provider.fetch_raw_concept_list(ConceptListRequest())
    assert len(raw) >= 3
    assert len({row["providerSectorId"] for row in raw}) == len(raw)
    ai = next(row for row in raw if row["providerSectorId"] == "302035")
    assert ai["sectorName"] == "人工智能"

    ref, quote_id, detail = provider._resolve_ref(ConceptRef.model_validate(_business_fields(ai)))
    assert ref.provider_sector_id == "302035"
    assert quote_id == "885728"
    assert quote_id != ref.provider_sector_id
    assert "<h3>人工智能" in detail


def test_exact_concept_name_resolves_through_directory_and_ambiguous_names_fail():
    provider, _ = _provider()
    ref, quote_id, _ = provider._resolve("人工智能")
    assert ref.provider_sector_id == "302035"
    assert quote_id == "885728"

    duplicated_listing = _fixture("concept_list.html") + (
        '<a href="http://q.10jqka.com.cn/gn/detail/code/999999/">人工智能</a>'.encode("gb18030")
    )
    routes = _routes()
    routes[LIST_URL] = duplicated_listing
    provider, _ = _provider(routes)
    with pytest.raises(ProviderError, match="missing or ambiguous"):
        provider._resolve("人工智能")


def test_concept_quote_parse_units_percentages_and_source_time():
    provider, _ = _provider()
    raw = provider.fetch_raw_concept_quote_snapshot(ConceptQuoteSnapshotRequest(concept=CONCEPT))
    assert raw["indexLevel"] == Decimal("1310.131")
    assert raw["previousClose"] == Decimal("1321.425")
    assert raw["open"] == raw["high"] == Decimal("1320.026")
    assert raw["low"] == Decimal("1308.423")
    assert raw["levelChange"] == Decimal("-11.294")
    assert raw["changeRate"] == Decimal("-0.0085")
    assert raw["volume"] == 23_070_853_000
    assert raw["amount"] == Decimal("366682630000.000")
    assert raw["netMoneyFlow"] == Decimal("-25074000000.00")
    assert raw["riseCount"] == 297
    assert raw["fallCount"] == 771
    assert raw["sourceTimestamp"].isoformat() == "2026-09-23T15:00:00+08:00"


def test_kline_csv_fixture_has_inclusive_date_filter_and_verified_units():
    provider, opener = _provider()
    request = ConceptOhlcvRequest(
        concept=CONCEPT, startDate="2026-09-23", endDate="2026-09-23"
    )
    raw = provider.fetch_raw_concept_ohlcv(request)
    assert len(raw) == 1
    bar = ConceptOhlcvData.model_validate(_business_fields(raw[0]))
    assert bar.bar_date == date(2026, 9, 23)
    assert bar.open == bar.high == Decimal("1320.026")
    assert bar.low == Decimal("1308.423")
    assert bar.close == Decimal("1310.131")
    assert bar.volume == 23_070_853_000
    assert bar.amount == Decimal("366682630000.000")
    assert KLINE_URL.format("885728", "2026") in opener.calls
    assert KLINE_URL.format("885728", "last") in opener.calls

    outside = provider.fetch_raw_concept_ohlcv(
        ConceptOhlcvRequest(concept=CONCEPT, startDate="2026-09-24", endDate="2026-09-24")
    )
    assert outside == []


def test_recent_kline_merges_last_file_and_deduplicates_overlapping_dates():
    provider, _ = _provider()
    rows = provider.fetch_raw_concept_ohlcv(
        ConceptOhlcvRequest(concept=CONCEPT, startDate="2026-09-22", endDate="2026-09-23")
    )
    assert [row["barDate"] for row in rows] == [date(2026, 9, 22), date(2026, 9, 23)]
    assert str(rows[-1]["__finchx"]["sourceUrl"]) == KLINE_URL.format("885728", "last")


def test_recent_kline_rejects_conflicting_annual_and_last_values():
    year_fixture = _fixture("kline_2026.js")
    old_row = b"20260922,1315.882,1330.317,1314.906,1321.425,26538130000,480775930000.000,,,,0"
    conflicting_row = b"20260923,1320.026,1320.026,1308.423,1310.130,23070853000,366682630000.000,,,,0"
    routes = _routes()
    routes[KLINE_URL.format("885728", "2026")] = year_fixture.replace(
        old_row, old_row + b";" + conflicting_row
    )
    provider, _ = _provider(routes)
    with pytest.raises(ProviderError, match="sources conflict for 2026-09-23 close"):
        provider.fetch_raw_concept_ohlcv(
            ConceptOhlcvRequest(concept=CONCEPT, startDate="2026-09-23", endDate="2026-09-23")
        )


def test_client_and_registry_expose_typed_concept_endpoints():
    registry = PROVIDER_REGISTRY.get_provider("tonghuashun.concept")
    assert registry.supports_dataset(MARKET_CONCEPT_LIST_DATASET)
    assert registry.supports_dataset(MARKET_CONCEPT_QUOTE_SNAPSHOT_DATASET)
    assert registry.supports_dataset(MARKET_CONCEPT_OHLCV_DATASET)
    assert registry.semantics_for(MARKET_CONCEPT_LIST_DATASET) is DatasetRoutingSemantics.SINGLE_SOURCE

    for name in ("concept_quote_snapshot", "concept_ohlcv"):
        assert inspect.signature(getattr(FinchX().market, name)).parameters["concept"].annotation in {
            ConceptRef | str,
            "ConceptRef | str",
        }

    provider, _ = _provider()
    client = FinchX(collector=Collector(provider_instances={"tonghuashun.concept": provider}))
    result = client.market.concept_list(provider="tonghuashun.concept", use_cache=False)
    assert isinstance(result, FetchResult)
    assert len(result.data) == 3
    assert result.data[0].data["sectorType"] == "concept"
    assert str(result.data[0].source.source_url) == LIST_URL
    assert result.data[0].source.source_record_id


def test_normalization_keeps_stable_record_ids_capture_time_and_source_lineage():
    provider, _ = _provider()
    raw_quote = provider.fetch_raw_concept_quote_snapshot(ConceptQuoteSnapshotRequest(concept=CONCEPT))
    record = normalize_concept(
        ConceptQuoteSnapshotRequest(concept=CONCEPT),
        raw_quote,
        source=provider.source,
    )
    assert record.record_id == "302035:quote:2026-09-23T15:00:00+08:00"
    assert record.captured_at == CAPTURED_AT
    assert str(record.source.source_url) == QUOTE_URL.format("885728")
    assert record.source.source_record_id == "302035"
    assert str(record.provenance.source_references[0].source_url) == DETAIL_URL.format("302035")
    assert record.quality.issues == []
    assert record.data["changeRate"] == "-0.0085"

    partial_record = normalize_concept(
        ConceptQuoteSnapshotRequest(concept=CONCEPT),
        {**raw_quote, "netMoneyFlow": None},
        source=provider.source,
    )
    assert [issue.kind for issue in partial_record.quality.issues] == [QualityIssueKind.PARTIAL]

    later_quote = {**raw_quote, "sourceTimestamp": "2026-09-23T15:01:00+08:00"}
    later_record = normalize_concept(
        ConceptQuoteSnapshotRequest(concept=CONCEPT), later_quote, source=provider.source
    )
    assert later_record.record_id != record.record_id

    untimed_quote = {**raw_quote, "sourceTimestamp": None}
    untimed_record = normalize_concept(
        ConceptQuoteSnapshotRequest(concept=CONCEPT), untimed_quote, source=provider.source
    )
    assert untimed_record.record_id.endswith(CAPTURED_AT.isoformat())

    raw_bar = provider.fetch_raw_concept_ohlcv(
        ConceptOhlcvRequest(concept=CONCEPT, startDate="2026-09-23", endDate="2026-09-23")
    )
    bar_record = normalize_concept(
        ConceptOhlcvRequest(concept=CONCEPT, startDate="2026-09-23", endDate="2026-09-23"),
        raw_bar,
        source=provider.source,
    )[0]
    assert bar_record.record_id == "302035:2026-09-23"
    assert str(bar_record.source.source_url) == KLINE_URL.format("885728", "last")
    assert bar_record.data["volume"] == 23_070_853_000


def test_schema_contracts_match_concept_models_and_enforce_identity():
    cases = (
        ("market-concept-list.schema.json", {"sectorType": "concept", "sectorName": "人工智能", "providerNamespace": "tonghuashun_concept", "providerSectorId": "302035"}),
        ("market-concept-quote-snapshot.schema.json", {"concept": CONCEPT.model_dump(mode="json", by_alias=True), "indexLevel": "1310.131", "previousClose": "1321.425", "open": "1320.026", "high": "1320.026", "low": "1308.423", "levelChange": "-11.294", "changeRate": "-0.0085", "volume": 23070853000, "amount": "366682630000.000", "netMoneyFlow": None, "riseCount": 297, "fallCount": 771, "sourceTimestamp": "2026-09-23T15:00:00+08:00"}),
        ("market-concept-ohlcv.schema.json", {"concept": CONCEPT.model_dump(mode="json", by_alias=True), "barDate": "2026-09-23", "open": "1320.026", "high": "1320.026", "low": "1308.423", "close": "1310.131", "volume": 23070853000, "amount": "366682630000.000"}),
    )
    schemas = {resource.name: read_schema(resource.name) for resource in iter_schema_resources()}
    registry = Registry()
    for schema in schemas.values():
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    for filename, payload in cases:
        validator = Draft202012Validator(
            schemas[filename], registry=registry, format_checker=FormatChecker()
        )
        validator.validate(payload)
    with pytest.raises(ValidationError):
        ConceptRef(
            sectorType="concept", sectorName="bad", providerNamespace="tonghuashun_concept", providerSectorId="not-a-page-id"
        )


def _business_fields(value: dict[str, object]) -> dict[str, object]:
    return {key: item for key, item in value.items() if not key.startswith("__")}
