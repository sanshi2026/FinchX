"""公告两个公开入口及客户端原有能力的接线。"""

from datetime import date
import inspect

import pytest

from finchx import FinchX, SourceError
from finchx.api import disclosure


def test_disclosure_has_exactly_two_public_methods_and_fixed_signatures():
    fx = FinchX()
    api = fx.disclosure
    assert [name for name, value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)] == ["em_list", "em_get"]
    signature = inspect.signature(api.em_list)
    assert list(signature.parameters) == ["code", "limit", "since", "until", "categories"]
    assert signature.parameters["code"].default is inspect.Parameter.empty
    assert signature.parameters["limit"].default == 20
    for name in ["since", "until", "categories"]:
        assert signature.parameters[name].default is None
    assert list(inspect.signature(api.em_get).parameters) == ["url"]
    for name in ["list", "get", "get_many", "em_get_many", "notice_list", "notice_get"]:
        assert not hasattr(api, name)


def test_disclosure_addition_preserves_all_existing_client_namespaces_and_methods():
    fx = FinchX(timeout=2.5)
    expected = {
        "reference": "trading_calendar", "market": "all_quotes", "fund_flow": "stock",
        "sector": "ths_concept_list", "company": "info", "financial": "statements",
        "regulation": "deviation", "fupan": "jygs_replay", "news": "em_list",
        "articles": "hot_content", "disclosure": "em_list", "reports": "agp_list", "hotlist": "stocks", "forum": "tgb_replies", "iwencai": "select",
    }
    assert set(vars(fx)) == set(expected)
    for namespace, method in expected.items():
        assert callable(getattr(getattr(fx, namespace), method))
        assert getattr(fx, namespace)._timeout == 2.5
    for api in [fx.market, fx.news, fx.articles]:
        for name in ["disclosure", "notice_list", "notice_get", "em_get_many"]:
            assert not hasattr(api, name)


@pytest.mark.parametrize("name,args,expected", [
    ("em_list", ("300308",), ("300308", 20, None, None, None)),
    ("em_list", ("300308", 120, "2026/09/01", "2026-10-08 15:00:00", ["重大合同", "业绩预告"]),
     ("300308", 120, "2026/09/01", "2026-10-08 15:00:00", ["重大合同", "业绩预告"])),
    ("em_list", ("000001", 2, date(2026, 9, 1), date(2026, 10, 8), ("财务报告",)),
     ("000001", 2, date(2026, 9, 1), date(2026, 10, 8), ("财务报告",))),
    ("em_get", ("https://data.eastmoney.com/notices/detail/300308/AN202610081830198767.html",),
     ("https://data.eastmoney.com/notices/detail/300308/AN202610081830198767.html",)),
])
def test_entries_forward_all_inputs_and_timeout_without_wrapping_or_caching(monkeypatch, name, args, expected):
    sentinel = {"content": "来源正文"} if name == "em_get" else [{"title": "来源标题"}]
    calls = []

    def source(*source_args, timeout):
        calls.append((source_args, timeout))
        return sentinel

    monkeypatch.setattr(disclosure.em_disclosure, name, source)
    api = FinchX(timeout=2.5).disclosure
    assert getattr(api, name)(*args) is sentinel
    assert getattr(api, name)(*args) is sentinel
    assert calls == [(expected, 2.5), (expected, 2.5)]


@pytest.mark.parametrize("name,args", [
    ("em_list", ("300308",)),
    ("em_get", ("https://data.eastmoney.com/notices/detail/AN202610081830198767.html",)),
])
@pytest.mark.parametrize("error", [SourceError("eastmoney", "公告来源失败"), ValueError("参数无效")])
def test_source_failures_propagate_unchanged(monkeypatch, name, args, error):
    def source(*args, **kwargs):
        raise error

    monkeypatch.setattr(disclosure.em_disclosure, name, source)
    with pytest.raises(type(error)) as caught:
        getattr(FinchX().disclosure, name)(*args)
    assert caught.value is error
