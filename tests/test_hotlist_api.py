"""热榜公开签名、来源薄转发与客户端既有能力。"""

import inspect
import json
from pathlib import Path

import pytest

from finchx import FinchX, SourceError
from finchx.api import hotlist
from finchx.sources.tonghuashun import hotlist as ths_hotlist

FIXTURES = Path(__file__).parent / "fixtures" / "hotlist"


def test_hotlist_has_exact_public_methods_signatures_defaults_and_order():
    api=FinchX().hotlist
    expected={
        "stocks":(["category","period","limit"],["popular",None,20]),
        "sectors":(["sector_type","limit"],["concept",20]),
        "convertible_bonds":(["limit"],[20]),
        "etfs":(["category","limit"],["popular",20]),
    }
    assert [name for name,value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)]==list(expected)
    for name,(parameters,defaults) in expected.items():
        signature=inspect.signature(getattr(api,name))
        assert list(signature.parameters)==parameters
        assert [p.default for p in signature.parameters.values()]==defaults
    for name in ["list","get","hot_content","content","stock_list","etf_list","get_many"]:
        assert not hasattr(api,name)


def test_hotlist_preserves_all_existing_namespaces_and_timeout():
    fx=FinchX(timeout=2.5)
    expected={
        "reference":"trading_calendar","market":"all_quotes","fund_flow":"stock",
        "sector":"ths_concept_list","company":"info","financial":"statements",
        "regulation":"deviation","fupan":"jygs_replay","news":"em_list",
        "articles":"hot_content","disclosure":"em_list","reports":"agp_fetch","hotlist":"stocks","forum":"tgb_replies","iwencai":"select",
    }
    assert set(vars(fx))==set(expected)
    names=list(vars(fx))
    assert names[names.index("regulation"):names.index("fupan")+1]==["regulation","hotlist","fupan"]
    assert names[-2:]==["forum","iwencai"]
    for namespace,method in expected.items():
        api=getattr(fx,namespace)
        assert callable(getattr(api,method)) and api._timeout==2.5


@pytest.mark.parametrize("name,args,kwargs,expected",[
    ("stocks",(),{},("popular",None,20)),
    ("stocks",("rising","24h",None),{},("rising","24h",None)),
    ("stocks",(),{"category":"new","limit":1},("new",None,1)),
    ("sectors",(),{},("concept",20)),
    ("sectors",(),{"sector_type":"index","limit":None},("index",None)),
    ("convertible_bonds",(),{},(20,)),
    ("convertible_bonds",(None,),{},(None,)),
    ("etfs",(),{},("popular",20)),
    ("etfs",(),{"category":"cross_border","limit":None},("cross_border",None)),
])
def test_hotlist_forwards_all_inputs_and_unwrapped_result_without_cache(monkeypatch,name,args,kwargs,expected):
    sentinel=[{"code":"000001","heat":0}]
    calls=[]
    def source(*source_args,timeout):
        calls.append((source_args,timeout))
        return sentinel
    monkeypatch.setattr(hotlist.ths_hotlist,name,source)
    api=FinchX(timeout=2.5).hotlist
    assert getattr(api,name)(*args,**kwargs) is sentinel
    assert getattr(api,name)(*args,**kwargs) is sentinel
    assert calls==[(expected,2.5),(expected,2.5)]


def test_public_hotlist_stock_fixture_has_fixed_fields_without_market_or_exchange(monkeypatch):
    payload = json.loads((FIXTURES / "stock_technical_day.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(ths_hotlist, "get_json", lambda *args, **kwargs: payload)

    rows = FinchX().hotlist.stocks(category="technical", limit=1)

    assert rows == [{
        "rank": 1,
        "code": "603906",
        "name": "龙蟠科技",
        "change_percent": 6.0172,
        "heat": 29240.0,
        "rank_change": 2,
        "concept_tags": ["钠离子电池", "固态电池"],
        "popularity_tag": "热搜",
        "analysis_title": None,
        "analysis": None,
        "search_count": 1190,
        "updated_at": "2026-10-09T09:48:29+08:00",
        "issue_pe": None,
    }]
    assert set(rows[0]) == {
        "rank", "code", "name", "change_percent", "heat", "rank_change",
        "concept_tags", "popularity_tag", "analysis_title", "analysis",
        "search_count", "updated_at", "issue_pe",
    }
    assert "market" not in rows[0] and "exchange" not in rows[0]


@pytest.mark.parametrize("name",["stocks","sectors","convertible_bonds","etfs"])
@pytest.mark.parametrize("error",[SourceError("tonghuashun","热榜来源失败"),ValueError("参数无效")])
def test_hotlist_propagates_parameter_and_source_errors(monkeypatch,name,error):
    def source(*args,**kwargs):raise error
    monkeypatch.setattr(hotlist.ths_hotlist,name,source)
    with pytest.raises(type(error)) as caught:
        getattr(FinchX().hotlist,name)()
    assert caught.value is error
