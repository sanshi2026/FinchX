from __future__ import annotations
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import FinchX
from finchx.collector import Collector, FetchResult
from finchx.collectors.errors import AllProvidersFailed
from finchx.contracts import QualityIssueKind, Source, StandardRecord
from finchx.datasets import (
    HOT_CONTENT_DATASET, HOT_CONVERTIBLE_BONDS_DATASET, HOT_ETFS_DATASET,
    HOT_SECTORS_DATASET, HOT_STOCKS_DATASET, HotContentRequest, HotStocksRequest,
    HotEtfsRequest,
)
from finchx.entities import Exchange, InstrumentKind
from finchx.providers import (
    DatasetRoutingSemantics, PROVIDER_REGISTRY, ProviderError, THSHotListProvider,
)
from finchx.schemas import iter_schema_resources, read_schema
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

FIXTURES = Path(__file__).parent / "fixtures" / "ths_hotlist"
CAPTURED = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)

class Response:
    status = 200
    def __init__(self, body: bytes): self.body = body
    def read(self): return self.body

class FixtureOpener:
    def __init__(self, *, fail_tags=False, fail_comment=False, fail_metrics=False, fail_index_enrichment=False, unknown_etf_market=False):
        self.calls=[]; self.fail_tags=fail_tags; self.fail_comment=fail_comment; self.fail_metrics=fail_metrics
        self.fail_index_enrichment=fail_index_enrichment; self.unknown_etf_market=unknown_etf_market
    def __call__(self, request, timeout):
        url=request.full_url; self.calls.append((request.get_method(), url, request.data, dict(request.header_items())))
        path=urlsplit(url).path
        if path.endswith("/stock"): name="stocks.json"
        elif path.endswith("new_stock.txt"): name="new_stocks.json"
        elif path.endswith("/plate"): name="sectors.json"
        elif path.endswith("/index_sector"): name="index_sectors.json"
        elif path.endswith("recommend/v1/batch/single"):
            if self.fail_index_enrichment: raise OSError("fixture index ETF recommendation failure")
            name="index_recommendations.json"
        elif path.endswith("outer/v1/specific_data"):
            if self.fail_index_enrichment: raise OSError("fixture index ETF quote failure")
            name="index_etf_quotes.json"
        elif path.endswith("/bond"): name="bonds.json"
        elif path.endswith("fund_pool/v2/query"): name="etf_pool_unknown_market.json" if self.unknown_etf_market else "etf_pool.json"
        elif path.endswith("specific_data"):
            if self.fail_metrics: raise OSError("fixture metric failure")
            name="etf_metrics_unknown_market.json" if self.unknown_etf_market else "etf_metrics.json"
        elif path.endswith("tag_data"):
            if self.fail_tags == "status": name="etf_tag_error.json"
            elif self.fail_tags: raise OSError("fixture tag failure")
            else: name="etf_tags.json"
        elif path.endswith("/topic"): name="topics.json"
        elif path.endswith("/comment"): name="comments.json"
        elif path.endswith("/basic"):
            query=parse_qs(urlsplit(url).query)
            if query.get("tag",[""])[0].endswith("新热文"): name="articles.json"
            else:
                if self.fail_comment: raise OSError("fixture comment detail failure")
                name="comment_details.json"
        else: raise AssertionError(f"unexpected URL {url}")
        return Response((FIXTURES/name).read_bytes())

def client(opener=None):
    provider=THSHotListProvider(opener or FixtureOpener(),clock=lambda:CAPTURED)
    collector=Collector(provider_instances={"tonghuashun.hotlist":provider})
    return FinchX(collector=collector),provider

def test_registry_and_client_contracts_are_five_single_source_datasets():
    spec=PROVIDER_REGISTRY.get_provider("tonghuashun.hotlist")
    assert {d.name for d in spec.supported_datasets}=={
        HOT_STOCKS_DATASET.name,HOT_SECTORS_DATASET.name,HOT_CONVERTIBLE_BONDS_DATASET.name,
        HOT_ETFS_DATASET.name,HOT_CONTENT_DATASET.name}
    assert all(spec.semantics_for(d)==DatasetRoutingSemantics.SINGLE_SOURCE for d in spec.supported_datasets)
    fx,_=client()
    assert callable(fx.hotlist.stocks) and callable(fx.hotlist.sectors)
    assert callable(fx.hotlist.convertible_bonds) and callable(fx.hotlist.etfs) and callable(fx.hotlist.content)

def test_actual_hotlist_envelope_keys_and_nonzero_status_are_handled():
    success = Response(b'{"status_code":0,"status_msg":"success","data":{"stock_list":[{"code":"600001","name":"A","order":1}]}}')
    provider = THSHotListProvider(lambda request, timeout: success, clock=lambda: CAPTURED)
    [row] = provider.fetch_raw_hotlist(HotStocksRequest(limit=1))
    assert row["data"]["symbol"] == "600001"

    failure = Response(b'{"status_code":17,"status_msg":"denied","data":{"stock_list":[]}}')
    provider = THSHotListProvider(lambda request, timeout: failure, clock=lambda: CAPTURED)
    with pytest.raises(ProviderError, match="status_code=17"):
        provider.fetch_raw_hotlist(HotStocksRequest(limit=1))

def test_stock_rank_decimal_units_and_optional_fields_are_standard_records():
    fx,provider=client()
    result=fx.hotlist.stocks(limit=2)
    assert isinstance(result,FetchResult) and result.dataset.name==HOT_STOCKS_DATASET.name
    assert all(isinstance(row,StandardRecord) for row in result.data)
    first=result.data[0]
    assert first.data["rank"]==1 and first.data["symbol"]=="600001"
    assert first.data["changePct"]=="0.099688" and first.data["heat"]=="623617.0"
    assert first.data["instrumentId"]["kind"]=="equity"
    assert first.data["conceptTags"]==["半导体","AI"] and first.data["popularityTag"]=="主力关注"
    assert result.to_dicts()[0]["changePct"]=="0.099688"
    assert all("status" not in row for row in result.to_dicts())
    assert first.source.provider_id=="tonghuashun.hotlist"
    assert first.provenance.transformation_version=="ths-hotlist-normalizer/1"
    assert str(first.source.source_url)=="https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock"
    request_url=provider._open.calls[0][1]
    assert parse_qs(urlsplit(request_url).query)=={"stock_type":["a"],"list_type":["normal"],"type":["hour"]}
    assert result.data[1].data["popularityTag"] is None and result.data[1].data["conceptTags"]==[]

def test_stock_category_period_and_new_stock_pe_contract():
    fx,provider=client()
    fx.hotlist.stocks(category="popular",period="24h")
    query=parse_qs(urlsplit(provider._open.calls[-1][1]).query)
    assert query=={"stock_type":["a"],"list_type":["normal"],"type":["day"]}
    fx.hotlist.stocks(category="rising",period="1h")
    query=parse_qs(urlsplit(provider._open.calls[-1][1]).query)
    assert query["list_type"]==["skyrocket"] and query["type"]==["hour"]
    fx.hotlist.stocks(category="rising",period="24h")
    query=parse_qs(urlsplit(provider._open.calls[-1][1]).query)
    assert query["list_type"]==["skyrocket"] and query["type"]==["day"]
    fx.hotlist.stocks(category="new")
    assert urlsplit(provider._open.calls[-1][1]).path.endswith("new_stock.txt")
    assert parse_qs(urlsplit(provider._open.calls[-1][1]).query)=={}
    data=fx.hotlist.stocks(category="new").data[0].data
    assert data["pe"]=="18.75" and data["changePct"] is None
    for category,list_type in (("technical","tech"),("value","value"),("trend","trend")):
        request=HotStocksRequest(category=category)
        assert request.period is None
        fx.hotlist.stocks(category=category)
        query=parse_qs(urlsplit(provider._open.calls[-1][1]).query)
        assert query["stock_type"]==["a"] and query["list_type"]==[list_type] and query["type"]==["day"]
    with pytest.raises(ValueError): HotStocksRequest(category="technical",period="1h")

def test_sector_types_bond_null_change_and_identity():
    fx,_=client()
    sector=fx.hotlist.sectors().data[0].data
    assert sector["tag"]=="3家涨停" and sector["hotTag"]=="连续上榜"
    assert sector["relatedEtfSymbol"]=="512480" and sector["changePct"]=="0.0125"
    assert fx.hotlist.sectors("industry").data[0].data["sectorType"]=="industry"
    index_records=fx.hotlist.sectors("index",limit=2).data
    index=index_records[0].data
    assert index["name"]=="科创50" and index["heat"]=="88" and index["changePct"]=="0.025"
    assert index["relatedEtfSymbol"]=="510050" and index["relatedEtfChangePct"]=="0.0075"
    assert index_records[1].data["relatedEtfSymbol"]=="159915"
    assert len(index_records[0].provenance.source_references)>=2
    failed_fx,_=client(FixtureOpener(fail_index_enrichment=True))
    failed=failed_fx.hotlist.sectors("index").data[0]
    assert failed.data["relatedEtfSymbol"] is None
    assert any(issue.kind is QualityIssueKind.PARTIAL for issue in failed.quality.issues)
    bonds=fx.hotlist.convertible_bonds(limit=2).data
    assert bonds[1].data["changePct"] is None and bonds[0].data["heat"]=="12345.7"
    assert bonds[0].entity_id=="CN_CONVERTIBLE_BOND:123001"
    assert not isinstance(bonds[0].entity_id,dict)

def test_etf_pool_metric_sort_tags_and_correct_instrument_kind():
    fx,provider=client()
    result=fx.hotlist.etfs(limit=2)
    rows=result.data
    assert [r.data["symbol"] for r in rows]==["510300","159915"]
    assert [r.data["heat"] for r in rows]==["20067.1","900"]
    assert rows[0].provenance.source_references
    assert rows[0].data["changePct"]=="0.00483092"
    assert rows[0].data["tags"]==["T+0","历史高位"]
    assert rows[0].entity_id.kind is InstrumentKind.ETF
    assert rows[0].entity_id.exchange is Exchange.SSE
    assert rows[1].entity_id.exchange is Exchange.SZSE
    assert [urlsplit(call[1]).path.rsplit("/",1)[-1] for call in provider._open.calls]==["query","specific_data","tag_data"]
    assert b"347c9f28-8a67-48a7-8c05-380ff8e595c7" in provider._open.calls[0][2]

@pytest.mark.parametrize(("category","pool_key"),[
    ("t0","fa2c6ba4-c243-4057-af9a-3dfe2d98d73b"),
    ("cross_border","8c2b110c-8913-4fc0-bd31-0d298e9d2ff2"),
])
def test_etf_market_code_20_resolves_520920_as_sse_for_pool_categories(category,pool_key):
    fx,provider=client()
    result=fx.hotlist.etfs(category=category,limit=3)
    record=next(row for row in result.data if row.data["symbol"]=="520920")
    assert isinstance(result,FetchResult) and isinstance(record,StandardRecord)
    assert record.entity_id.kind is InstrumentKind.ETF
    assert record.entity_id.exchange is Exchange.SSE
    assert record.data["instrumentId"]["kind"]=="etf"
    assert record.data["instrumentId"]["exchange"]=="sse"
    pool_request=json.loads(provider._open.calls[0][2])
    assert pool_request["businessPoolKey"]==pool_key
    metric_request=json.loads(provider._open.calls[1][2])
    assert "20:520920" in metric_request["code_selectors"]["include"][0]["values"]

def test_unknown_etf_source_market_does_not_guess_exchange_from_code_prefix():
    fx,_=client(FixtureOpener(unknown_etf_market=True))
    record=next(row for row in fx.hotlist.etfs(limit=3).data if row.data["symbol"]=="520920")
    assert record.entity_id.exchange is None
    assert any(issue.kind is QualityIssueKind.PARTIAL for issue in record.quality.issues)
    assert "market id '99' is unrecognized" in record.quality.issues[0].detail

def test_etf_tag_failure_is_partial_and_metric_failure_is_not_hidden():
    fx,_=client(FixtureOpener(fail_tags=True))
    record=fx.hotlist.etfs().data[0]
    assert record.data["tags"]==[]
    assert any(issue.kind is QualityIssueKind.PARTIAL for issue in record.quality.issues)
    fx,_=client(FixtureOpener(fail_tags="status"))
    record=fx.hotlist.etfs().data[0]
    assert record.data["tags"]==[]
    assert any("without tags" in issue.detail for issue in record.quality.issues)
    fx,_=client(FixtureOpener(fail_metrics=True))
    with pytest.raises(AllProvidersFailed):
        fx.hotlist.etfs()

def test_topic_comment_and_article_use_distinct_shapes_and_partial_ratio_quality():
    fx,_=client()
    topic=fx.hotlist.content("topic").data[0]
    assert topic.data["contentType"]=="topic" and topic.data["relatedStocks"][0]["changePct"]=="0.025"
    assert "sourceMarket" not in topic.data["relatedStocks"][0]
    assert topic.data["url"]=="https://example.test/topic"
    comment=fx.hotlist.content("comment").data[0]
    assert comment.data["text"]=="市场怎么看？" and comment.data["likes"]==5 and comment.data["contentId"]=="p-1"
    opener=FixtureOpener(fail_comment=True); fx,_=client(opener)
    comment=fx.hotlist.content("comment").data[0]
    assert comment.data["text"] is None and any(i.kind is QualityIssueKind.PARTIAL for i in comment.quality.issues)
    article=fx.hotlist.content("article",limit=2).data
    assert [r.data["rank"] for r in article]==[1,2]
    assert article[0].data["url"]=="https://example.test/a1"
    assert article[1].data["relatedStocks"][0]["changePct"]=="0.035"
    assert article[0].data["likeRatio"] is None and article[0].data["commentRatio"] is None
    assert any(i.kind is QualityIssueKind.PARTIAL for i in article[0].quality.issues)
    related=article[1].data["relatedStocks"]
    assert related[0]["instrumentId"]["exchange"]=="sse" and related[0]["sourceMarket"]=="17"
    market_etf=next(item for item in related if item["symbol"]=="510300")
    assert market_etf["instrumentId"]["kind"]=="etf" and market_etf["instrumentId"]["exchange"]=="sse"
    market_etf=next(item for item in related if item["symbol"]=="159915")
    assert market_etf["instrumentId"]["kind"]=="etf" and market_etf["instrumentId"]["exchange"]=="szse"
    b_share=next(item for item in related if item["symbol"]=="200002")
    assert b_share["name"]=="万科B" and b_share["sourceMarket"]=="35"
    assert b_share["instrumentId"] is None
    assert any(item["symbol"]=="09927" and item["sourceMarket"]=="177" and item["instrumentId"] is None for item in related)
    assert any(item["symbol"]=="META" and item["sourceMarket"]=="185" and item["instrumentId"] is None for item in related)
    assert any(item["symbol"]=="885728" and item["sourceMarket"]=="48" and item["instrumentId"] is None for item in related)
    assert any(item["symbol"]=="920012" and item["sourceMarket"]=="151" and item["instrumentId"] is None for item in related)
    assert any("non-CN_A" in i.detail and "stockMarket" in i.detail for i in article[1].quality.issues)

def test_unverified_article_ratios_are_discarded_and_partial_even_without_provider_flag():
    from finchx.datasets.hotlist import normalize_hotlist

    [record] = normalize_hotlist(
        HotContentRequest(contentType="article", limit=1),
        [{
            "data": {
                "contentType": "article", "rank": 1, "title": "Article",
                "likeRatio": "65", "commentRatio": "25",
            },
            "__finchx": {
                "sourceRecordId": "article:1", "recordId": "hotlist.content:article:1",
                "capturedAt": CAPTURED, "partial": False,
                "sourceUrl": "https://example.test/articles",
            },
        }],
        source=Source(providerId="test.fixture", sourceUrl="https://example.test"),
    )
    assert record.data["likeRatio"] is None and record.data["commentRatio"] is None
    assert any(issue.kind is QualityIssueKind.PARTIAL for issue in record.quality.issues)
    assert "units are unverified" in record.quality.issues[0].detail

def test_hotlist_schemas_match_model_and_standard_decimal_wire_values():
    models={"hotlist-stocks.schema.json":__import__("finchx.datasets.hotlist",fromlist=["HotStockData"]).HotStockData,
        "hotlist-sectors.schema.json":__import__("finchx.datasets.hotlist",fromlist=["HotSectorData"]).HotSectorData,
        "hotlist-convertible-bonds.schema.json":__import__("finchx.datasets.hotlist",fromlist=["HotConvertibleBondData"]).HotConvertibleBondData,
        "hotlist-etfs.schema.json":__import__("finchx.datasets.hotlist",fromlist=["HotEtfData"]).HotEtfData,
        "hotlist-content.schema.json":__import__("finchx.datasets.hotlist",fromlist=["HotContentData"]).HotContentData}
    schemas={r.name:read_schema(r.name) for r in iter_schema_resources()}
    registry=Registry()
    for schema in schemas.values(): registry=registry.with_resource(schema["$id"],Resource.from_contents(schema))
    for filename,model in models.items():
        expected=model.model_json_schema(by_alias=True,mode="serialization")
        schema=schemas[filename]
        if "properties" in expected:
            assert schema["properties"]==expected["properties"]
        else:
            assert schema["oneOf"]==expected["oneOf"]
            assert schema["discriminator"]==expected["discriminator"]
        Draft202012Validator.check_schema(schema)
    fx,_=client()
    record=fx.hotlist.stocks().data[0]
    schema=schemas["standard-record.schema.json"]
    Draft202012Validator(schema,registry=registry,format_checker=FormatChecker()).validate(record.model_dump(mode="json",by_alias=True))
