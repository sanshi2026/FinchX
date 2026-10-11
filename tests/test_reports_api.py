"""研报两个公开入口、薄转发及客户端既有能力保留。"""

import inspect

import pytest

from finchx import FinchX, SourceError
from finchx.api import reports


def test_reports_exact_public_methods_and_signatures():
    api=FinchX().reports
    assert [name for name,value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)]==["agp_list","agp_get"]
    signature=inspect.signature(api.agp_list)
    assert list(signature.parameters)==["limit","kind","keyword","industry"]
    assert [p.default for p in signature.parameters.values()]==[20,"all",None,None]
    getter=inspect.signature(api.agp_get)
    assert list(getter.parameters)==["url"]
    assert getter.parameters["url"].default is inspect.Parameter.empty
    for name in ["list","get","get_many","agp_get_many","report_list","report_get"]:
        assert not hasattr(api,name)


def test_reports_keeps_all_existing_client_namespaces_and_shared_timeout():
    fx=FinchX(timeout=2.5)
    expected={
        "reference":"trading_calendar","market":"all_quotes","fund_flow":"stock",
        "sector":"ths_concept_list","company":"info","financial":"statements",
        "regulation":"deviation","fupan":"jygs_replay","news":"em_list",
        "articles":"hot_content","disclosure":"em_list","reports":"agp_list","hotlist":"stocks","forum":"tgb_replies","iwencai":"select",
    }
    assert set(vars(fx))==set(expected)
    for namespace,method in expected.items():
        api=getattr(fx,namespace)
        assert callable(getattr(api,method)) and api._timeout==2.5
    for api in [fx.market,fx.news,fx.articles,fx.disclosure]:
        assert not hasattr(api,"reports")
        assert not hasattr(api,"report_list")
        assert not hasattr(api,"report_get")


@pytest.mark.parametrize("name,args,kwargs,expected",[
    ("agp_list",(),{},(20,"all",None,None)),
    ("agp_list",(40,"stock"," 包装 ",None),{},(40,"stock"," 包装 ",None)),
    ("agp_list",(),{"limit":2,"kind":"industry","industry":"汽车行业"},(2,"industry",None,"汽车行业")),
    ("agp_list",(),{"industry":"000039"},(20,"all",None,"000039")),
    ("agp_get",("http://101.35.29.159:82/report/detail_m.php?id=2477185",),{},("http://101.35.29.159:82/report/detail_m.php?id=2477185",)),
])
def test_reports_forwards_inputs_timeout_and_unwrapped_result_without_cache(monkeypatch,name,args,kwargs,expected):
    sentinel={"summary":"来源摘要"} if name=="agp_get" else [{"title":"来源标题"}]
    calls=[]
    def source(*source_args,timeout):
        calls.append((source_args,timeout))
        return sentinel
    monkeypatch.setattr(reports.agp_reports,name,source)
    api=FinchX(timeout=2.5).reports
    assert getattr(api,name)(*args,**kwargs) is sentinel
    assert getattr(api,name)(*args,**kwargs) is sentinel
    assert calls==[(expected,2.5),(expected,2.5)]


@pytest.mark.parametrize("name,args",[
    ("agp_list",()),
    ("agp_get",("http://101.35.29.159:82/report/detail_m.php?id=2477185",)),
])
@pytest.mark.parametrize("error",[SourceError("aigupiao","研报来源失败"),ValueError("参数无效")])
def test_reports_propagates_source_errors_without_fallback_or_wrapping(monkeypatch,name,args,error):
    def source(*args,**kwargs):raise error
    monkeypatch.setattr(reports.agp_reports,name,source)
    with pytest.raises(type(error)) as caught:
        getattr(FinchX().reports,name)(*args)
    assert caught.value is error
