"""问财公开签名、显式认证参数及来源薄转发。"""

import inspect

import pytest

from finchx import FinchX, SourceError
from finchx.api import iwencai


def test_iwencai_has_exact_public_methods_and_signatures():
    api = FinchX().iwencai
    assert [name for name, value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)] == ["select", "search", "get_report"]
    expected = {
        "select": (["query", "limit", "cookies"], [inspect.Parameter.empty, 100, inspect.Parameter.empty]),
        "search": (["query", "channel", "limit", "api_key"],
                   [inspect.Parameter.empty, "report", 50, inspect.Parameter.empty]),
        "get_report": (["url", "uid", "channel"], [inspect.Parameter.empty, None, None]),
    }
    for name, (parameters, defaults) in expected.items():
        signature = inspect.signature(getattr(api, name))
        assert list(signature.parameters) == parameters
        assert [p.default for p in signature.parameters.values()] == defaults
    for method, credential in [(api.select, "cookies"), (api.search, "api_key")]:
        assert inspect.signature(method).parameters[credential].kind is inspect.Parameter.KEYWORD_ONLY
    for hint in ("uid", "channel"):
        assert inspect.signature(api.get_report).parameters[hint].kind is inspect.Parameter.KEYWORD_ONLY
    for name in ["list", "get", "get_many", "query", "report", "screen", "search_reports"]:
        assert not hasattr(api, name)


def test_iwencai_preserves_all_namespaces_and_category_order():
    fx = FinchX(timeout=2.5)
    expected = {
        "reference": "trading_calendar", "market": "all_quotes", "fund_flow": "stock",
        "sector": "ths_concept_list", "company": "info", "financial": "statements",
        "regulation": "deviation", "hotlist": "stocks", "fupan": "jygs_replay",
        "news": "em_list", "articles": "hot_content", "disclosure": "em_list",
        "reports": "agp_fetch", "forum": "tgb_replies", "iwencai": "select",
    }
    assert list(vars(fx)) == list(expected)
    for namespace, method in expected.items():
        api = getattr(fx, namespace)
        assert callable(getattr(api, method)) and api._timeout == 2.5


@pytest.mark.parametrize("name,module,args,kwargs,expected", [
    ("select", "wc_selection", ("涨幅大于0",), {"cookies": "invalid-test-cookie=1"}, ("涨幅大于0", 100)),
    ("select", "wc_selection", (), {"query": " 保留原条件 ", "limit": 3,
                                    "cookies": {"invalid_test_cookie": "1"}}, (" 保留原条件 ", 3)),
    ("search", "wc_search", ("汽车行业",), {"api_key": "invalid-test-key"}, ("汽车行业", "report", 50)),
    ("search", "wc_search", ("汽车", "announcement", 1), {"api_key": "invalid-test-key"}, ("汽车", "announcement", 1)),
    ("search", "wc_search", (), {"query": "汽车", "channel": "news", "limit": 2,
                                 "api_key": "invalid-test-key"}, ("汽车", "news", 2)),
    ("get_report", "wc_report", ("https://example.invalid/not-used-in-delegation",), {},
     ("https://example.invalid/not-used-in-delegation",)),
    ("get_report", "wc_report", ("https://example.invalid/a.PDF",), {"uid": "27762db27c5968f2", "channel": "announcement"},
     ("https://example.invalid/a.PDF",)),
])
def test_iwencai_forwards_all_inputs_without_wrapping_caching_or_retaining_credentials(
    monkeypatch, name, module, args, kwargs, expected,
):
    sentinel = {"content": "来源文字"} if name == "get_report" else [{"来源业务列": 0}]
    calls = []

    def source(*source_args, **source_kwargs):
        calls.append((source_args, source_kwargs))
        return sentinel

    monkeypatch.setattr(getattr(iwencai, module), name, source)
    api = FinchX(timeout=2.5).iwencai
    for _ in range(2):
        assert getattr(api, name)(*args, **kwargs) is sentinel
    expected_kwargs = {key: value for key, value in kwargs.items() if key in ("cookies", "api_key")}
    expected_kwargs["timeout"] = 2.5
    if name == "get_report":
        expected_kwargs.update(uid=kwargs.get("uid"), channel=kwargs.get("channel"))
    assert calls == [(expected, expected_kwargs)] * 2
    for credential in ["cookies", "api_key"]:
        if credential in kwargs:
            assert calls[0][1][credential] is kwargs[credential]
    assert vars(api) == {"_timeout": 2.5}


@pytest.mark.parametrize("name,args,kwargs", [
    ("select", ("条件",), {}),
    ("select", ("条件", 20, "invalid-test-cookie=1"), {}),
    ("search", ("条件",), {}),
    ("search", ("条件", "report", 1, "invalid-test-key"), {}),
    ("select", ("条件",), {"cookies": "invalid-test-cookie=1", "backend": "test"}),
    ("search", ("条件",), {"api_key": "invalid-test-key", "page": 1}),
    ("get_report", ("https://example.invalid",), {"cookies": "invalid-test-cookie=1"}),
    ("get_report", ("https://example.invalid",), {"api_key": "invalid-test-key"}),
])
def test_iwencai_requires_explicit_credentials_and_rejects_extra_parameters_before_source(monkeypatch, name, args, kwargs):
    def source(*args, **kwargs):
        pytest.fail("无效公开签名不应读取来源")

    for module, function in [(iwencai.wc_selection, "select"), (iwencai.wc_search, "search"), (iwencai.wc_report, "get_report")]:
        monkeypatch.setattr(module, function, source)
    monkeypatch.setenv("IWENCAI_COOKIES", "invalid-environment-cookie")
    monkeypatch.setenv("IWENCAI_API_KEY", "invalid-environment-key")
    with pytest.raises(TypeError):
        getattr(FinchX().iwencai, name)(*args, **kwargs)


@pytest.mark.parametrize("name,module,args,kwargs", [
    ("select", "wc_selection", ("条件",), {"cookies": "invalid-test-cookie=1"}),
    ("search", "wc_search", ("条件",), {"api_key": "invalid-test-key"}),
    ("get_report", "wc_report", ("https://example.invalid",), {}),
])
@pytest.mark.parametrize("error", [SourceError("iwencai", "来源拒绝访问"), ValueError("参数无效")])
def test_iwencai_propagates_source_and_parameter_errors(monkeypatch, name, module, args, kwargs, error):
    def source(*args, **kwargs):
        raise error

    monkeypatch.setattr(getattr(iwencai, module), name, source)
    with pytest.raises(type(error)) as caught:
        getattr(FinchX().iwencai, name)(*args, **kwargs)
    assert caught.value is error
