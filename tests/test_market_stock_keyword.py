from datetime import datetime, timezone
import json
from pathlib import Path

import jsonschema
import pytest
from jsonschema import Draft202012Validator

from finchx import FinchX
from finchx.collector import CachePolicy, Collector
from finchx.contracts import Source
from finchx.datasets import (
    MARKET_STOCK_KEYWORD_DATASET,
    MarketStockKeywordData,
    MarketStockKeywordRequest,
    StockKeywordEntry,
)
from finchx.datasets.market_stock_keyword import normalize_stock_keyword
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers import EastMoneyStockKeywordProvider, ProviderError, PROVIDER_REGISTRY
from finchx.quality import QualityIssueKind, QualityStatus
import finchx.providers.eastmoney_stock_keyword as stock_keyword
from finchx.schemas import read_schema
from finchx.storage import Cache, MemoryStorage


FIXTURES = Path(__file__).parent / "fixtures" / "eastmoney"
CAPTURED_AT = datetime(2026, 9, 21, 5, 30, tzinfo=timezone.utc)


def instrument(code: str, exchange: Exchange) -> InstrumentId:
    return InstrumentId(
        code=code,
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=exchange,
    )


def request_for(code: str, exchange: Exchange) -> MarketStockKeywordRequest:
    return MarketStockKeywordRequest(instrumentId=instrument(code, exchange))


class FixtureTransport:
    def __init__(self, body: str, *, status_code: int = 200):
        self.body = body
        self.status_code = status_code
        self.calls = []

    def post(self, url, *, json_payload, headers, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "json_payload": dict(json_payload),
                "headers": dict(headers),
                "timeout_seconds": timeout_seconds,
            }
        )
        return stock_keyword._StockKeywordHttpResponse(self.status_code, self.body)


def provider_for(filename: str, *, status_code: int = 200):
    transport = FixtureTransport((FIXTURES / filename).read_text(encoding="utf-8"), status_code=status_code)
    provider = EastMoneyStockKeywordProvider(transport, clock=lambda: CAPTURED_AT)
    return provider, transport


def test_sse_parsing_normalization_and_minimal_request_contract():
    provider, transport = provider_for("stock_keyword_sh600519.json")
    request = request_for("600519", Exchange.SSE)

    raw = provider.fetch_raw_stock_keyword(request)
    record = normalize_stock_keyword(request, raw, source=provider.source)

    assert transport.calls[0]["json_payload"] == {"srcSecurityCode": "SH600519"}
    assert transport.calls[0]["headers"] == {"Content-Type": "application/json"}
    assert record.dataset == "market.stock_keyword"
    assert record.source.provider_id == "eastmoney.stockrank"
    assert record.source.source_record_id == "SH600519:stockrank:2026-09-21T13:00:00+08:00"
    assert record.captured_at == CAPTURED_AT
    assert record.data["instrumentId"]["exchange"] == "sse"
    assert record.data["keywords"][0] == {
        "keywordName": "白酒",
        "providerNamespace": "eastmoney_stockrank",
        "providerKeywordId": "BK0896",
        "hitCount": 5854,
        "calculatedAt": "2026-09-21T13:00:00+08:00",
    }
    assert MarketStockKeywordData.model_validate(record.data).keywords[0].hit_count == 5854


def test_szse_uses_explicit_sz_symbol_and_keeps_multiple_source_pairs():
    provider, transport = provider_for("stock_keyword_sz000001.json")
    request = request_for("000001", Exchange.SZSE)
    raw = provider.fetch_raw_stock_keyword(request)
    record = normalize_stock_keyword(request, raw, source=provider.source)

    assert transport.calls[0]["json_payload"] == {"srcSecurityCode": "SZ000001"}
    assert [row["providerKeywordId"] for row in record.data["keywords"]] == [
        "BK0637",
        "BK1071",
        "BK0821",
    ]
    assert [row["hitCount"] for row in record.data["keywords"]] == [574, 53, 11]


def test_bse_is_explicitly_mapped_and_legal_empty_data_is_preserved():
    provider, transport = provider_for("stock_keyword_bj920298_empty.json")
    request = request_for("920298", Exchange.BSE)
    record = normalize_stock_keyword(
        request,
        provider.fetch_raw_stock_keyword(request),
        source=provider.source,
    )

    assert transport.calls[0]["json_payload"] == {"srcSecurityCode": "BJ920298"}
    assert record.data["keywords"] == []


def test_bse_legal_empty_data_is_runtime_success_and_quality_no_data():
    provider, _ = provider_for("stock_keyword_bj920298_empty.json")
    collector = Collector(
        provider_instances={provider.source.provider_id: provider},
        clock=lambda: CAPTURED_AT,
    )

    result = collector.fetch(
        MARKET_STOCK_KEYWORD_DATASET,
        provider=provider.source.provider_id,
        request=request_for("920298", Exchange.BSE),
    )

    assert result.data.data["keywords"] == []
    assert collector.health.snapshot().dataset("market.stock_keyword").successes == 1
    quality = collector.quality.dataset("market.stock_keyword")
    assert quality is not None
    assert quality.latest.status is QualityStatus.NO_DATA
    assert quality.latest.issues[0].kind is QualityIssueKind.NO_DATA


def test_optional_source_fields_may_be_missing_but_public_extra_fields_are_forbidden():
    document = json.loads((FIXTURES / "stock_keyword_sh600519.json").read_text())
    for row in document["data"]:
        row.pop("flag")
    provider = EastMoneyStockKeywordProvider(
        FixtureTransport(json.dumps(document)),
        clock=lambda: CAPTURED_AT,
    )
    request = request_for("600519", Exchange.SSE)
    raw = provider.fetch_raw_stock_keyword(request)
    assert len(raw.entries) == 3

    with pytest.raises(ValueError):
        StockKeywordEntry.model_validate(
            {
                "keywordName": "白酒",
                "providerNamespace": "eastmoney_stockrank",
                "providerKeywordId": "BK0896",
                "hitCount": 1,
                "calculatedAt": "2026-09-21T13:00:00+08:00",
                "vendorField": "not public",
            }
        )


@pytest.mark.parametrize(
    "body,reason",
    [
        ('{"code":0,"status":0,"message":"OK","data":null}', "schema drift"),
        ("{broken", "malformed JSON"),
        ('{"code":0,"status":0,"message":"OK","data":[{"conceptName":"白酒"}]}', "omitted fields"),
        ('{"code":0,"status":0,"message":"OK","data":[{"calcTime":"2026-09-21 13:00:00","srcSecurityCode":"SH600519","conceptName":"白酒","conceptId":"BK0896","hitCount":"1"}]}', "hitCount"),
        ('{"code":0,"status":0,"message":"OK","data":[{"calcTime":"bad","srcSecurityCode":"SH600519","conceptName":"白酒","conceptId":"BK0896","hitCount":1}]}', "calcTime"),
        ('{"code":0,"status":0,"message":"OK","data":[{"calcTime":"2026-09-21 13:00:00","srcSecurityCode":"SH600519","conceptName":"白酒","conceptId":"BK0896","hitCount":1,"newField":1}]}', "unexpected fields"),
    ],
)
def test_schema_and_value_failures_are_provider_errors(body, reason):
    provider = EastMoneyStockKeywordProvider(FixtureTransport(body), clock=lambda: CAPTURED_AT)
    with pytest.raises(ProviderError, match=reason):
        provider.fetch_raw_stock_keyword(request_for("600519", Exchange.SSE))


def test_source_error_and_identity_exchange_validation_are_distinct():
    provider, _ = provider_for("stock_keyword_source_error.json")
    with pytest.raises(ProviderError, match="source error"):
        provider.fetch_raw_stock_keyword(request_for("600519", Exchange.SSE))

    with pytest.raises(ValueError, match="explicit SSE/SZSE/BSE"):
        request_for("600519", Exchange.BSE)
    with pytest.raises(ValueError, match="explicit SSE/SZSE/BSE"):
        MarketStockKeywordRequest(
            instrumentId=InstrumentId(
                code="600519",
                market=Market.CN_A,
                kind=InstrumentKind.EQUITY,
                exchange=None,
            )
        )


def test_registry_collector_route_client_fetchresult_and_cache_identity():
    provider, transport = provider_for("stock_keyword_sh600519.json")
    request = request_for("600519", Exchange.SSE)
    cache = Cache(MemoryStorage())
    collector = Collector(
        cache=cache,
        cache_policy={"market.stock_keyword": CachePolicy(enabled=True)},
        provider_instances={"eastmoney.stockrank": provider},
        clock=lambda: CAPTURED_AT,
    )

    first = collector.fetch(MARKET_STOCK_KEYWORD_DATASET, request=request)
    assert first.data.data["keywords"][0]["keywordName"] == "白酒"
    second = collector.fetch(MARKET_STOCK_KEYWORD_DATASET, request=request)
    assert second.cache_hit is True
    assert len(transport.calls) == 1

    client = FinchX(collector=collector)
    result = client.market.stock_keyword("600519", provider="eastmoney.stockrank")
    assert result.dataset is MARKET_STOCK_KEYWORD_DATASET
    assert result.provider == "eastmoney.stockrank"
    assert len(transport.calls) == 2
    assert PROVIDER_REGISTRY.providers_for(MARKET_STOCK_KEYWORD_DATASET)[0].provider is EastMoneyStockKeywordProvider


def test_stock_keyword_payload_matches_packaged_schema():
    provider, _ = provider_for("stock_keyword_sh600519.json")
    request = request_for("600519", Exchange.SSE)
    record = normalize_stock_keyword(
        request,
        provider.fetch_raw_stock_keyword(request),
        source=provider.source,
    )
    schema = read_schema("market-stock-keyword.schema.json")
    Draft202012Validator.check_schema(schema)
    from referencing import Registry, Resource
    from finchx.schemas import iter_schema_resources

    registry = Registry()
    for path in iter_schema_resources():
        resource = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(resource["$id"], Resource.from_contents(resource))
    Draft202012Validator(schema, registry=registry).validate(record.data)
