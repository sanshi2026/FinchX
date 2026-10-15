"""研报公开入口、薄转发及客户端既有能力保留。"""

import inspect

import pytest

from finchx import FinchX, SourceError
from finchx.api import reports


def test_reports_exact_public_methods_and_signatures():
    api = FinchX().reports
    assert [name for name, value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)] == ["fetch", "agp_fetch", "em_fetch", "analysys_fetch"]
    expected = {
        "fetch": (["keyword", "limit", "start_date", "end_date"], [inspect.Parameter.empty, 20, None, None]),
        "agp_fetch": (["limit", "kind", "keyword", "industry", "start_date", "end_date"], [20, "all", None, None, None, None]),
        "em_fetch": (["limit", "keyword", "start_date", "end_date"], [20, None, None, None]),
        "analysys_fetch": (["limit", "keyword", "start_date", "end_date"], [20, None, None, None]),
    }
    for name, (names, defaults) in expected.items():
        parameters = inspect.signature(getattr(api, name)).parameters
        assert list(parameters) == names
        assert [p.default for p in parameters.values()] == defaults
        for parameter in parameters.values():
            assert parameter.kind == (inspect.Parameter.KEYWORD_ONLY
                                      if name == "agp_fetch" and parameter.name in {"start_date", "end_date"}
                                      else inspect.Parameter.POSITIONAL_OR_KEYWORD)
    for name in ["agp_list", "agp_get", "list", "get", "get_many", "agp_get_many", "report_list", "report_get"]:
        assert not hasattr(api, name)


def test_reports_keeps_all_existing_client_namespaces_and_shared_timeout():
    fx = FinchX(timeout=2.5)
    expected = {
        "reference": "trading_calendar", "market": "all_quotes", "fund_flow": "stock",
        "sector": "ths_concept_list", "company": "info", "financial": "statements",
        "regulation": "deviation", "fupan": "jygs_replay", "news": "em_list",
        "articles": "hot_content", "disclosure": "em_list", "reports": "agp_fetch",
        "hotlist": "stocks", "forum": "tgb_replies", "iwencai": "select",
    }
    assert set(vars(fx)) == set(expected)
    for namespace, method in expected.items():
        api = getattr(fx, namespace)
        assert callable(getattr(api, method)) and api._timeout == 2.5
    assert callable(fx.news.agp_list) and callable(fx.articles.agp_get)
    for api in [fx.market, fx.news, fx.articles, fx.disclosure]:
        assert not hasattr(api, "reports")
        assert not hasattr(api, "report_list")
        assert not hasattr(api, "report_get")


@pytest.mark.parametrize("name,args,kwargs,expected_args,expected_kwargs", [
    ("agp_fetch", (), {}, (20, "all", None, None), {"start_date": None, "end_date": None}),
    ("agp_fetch", (40, "stock", " 包装 ", None), {}, (40, "stock", " 包装 ", None), {"start_date": None, "end_date": None}),
    ("agp_fetch", (), {"limit": 2, "kind": "industry", "industry": "汽车行业", "start_date": "20261001", "end_date": "2026/10/14"},
     (2, "industry", None, "汽车行业"), {"start_date": "20261001", "end_date": "2026/10/14"}),
    ("em_fetch", (), {}, (20, None, None, None), {}),
    ("em_fetch", (7, " 汽车 ", "20261001", "2026/10/14"), {}, (7, " 汽车 ", "20261001", "2026/10/14"), {}),
    ("analysys_fetch", (), {}, (20, None, None, None), {}),
    ("analysys_fetch", (3, " 数字经济 ", "20261001", "2026/10/14"), {}, (3, " 数字经济 ", "20261001", "2026/10/14"), {}),
    ("fetch", (" 汽车 ", 7, "20261001", "2026/10/14"), {}, (" 汽车 ", 7, "20261001", "2026/10/14"), {}),
])
def test_reports_forwards_inputs_timeout_and_unwrapped_result_without_cache(
        monkeypatch, name, args, kwargs, expected_args, expected_kwargs):
    sentinel = {"reports": [], "errors": []} if name == "fetch" else [{"title": "来源标题"}]
    calls = []
    def source(*source_args, **source_kwargs):
        calls.append((source_args, source_kwargs))
        return sentinel
    module = {"agp_fetch": reports.agp_reports, "em_fetch": reports.em_reports, "analysys_fetch": reports.analysys_reports, "fetch": reports.reports_fetch}[name]
    monkeypatch.setattr(module, name, source)
    api = FinchX(timeout=2.5).reports
    assert getattr(api, name)(*args, **kwargs) is sentinel
    assert getattr(api, name)(*args, **kwargs) is sentinel
    assert calls == [(expected_args, dict(expected_kwargs, timeout=2.5))] * 2


@pytest.mark.parametrize("name,args", [("agp_fetch", ()), ("em_fetch", ()), ("analysys_fetch", ()), ("fetch", ("汽车",))])
@pytest.mark.parametrize("error", [SourceError("aigupiao", "研报来源失败"), ValueError("参数无效")])
def test_reports_propagates_source_errors_without_fallback_or_wrapping(monkeypatch, name, args, error):
    def source(*args, **kwargs):
        raise error
    module = {"agp_fetch": reports.agp_reports, "em_fetch": reports.em_reports, "analysys_fetch": reports.analysys_reports, "fetch": reports.reports_fetch}[name]
    monkeypatch.setattr(module, name, source)
    with pytest.raises(type(error)) as caught:
        getattr(FinchX().reports, name)(*args)
    assert caught.value is error


@pytest.mark.parametrize("name,kwargs", [("agp_fetch", {"url": "https://example.org"}),
                                         ("em_fetch", {"url": "https://example.org"}),
                                         ("em_fetch", {"kind": "stock"}),
                                         ("analysys_fetch", {"kind": "industry"}),
                                         ("analysys_fetch", {"url": "https://example.org"})])
def test_new_reports_methods_reject_unprovided_parameters(name, kwargs):
    with pytest.raises(TypeError):
        getattr(FinchX().reports, name)(**kwargs)
