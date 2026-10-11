"""新闻四个公开入口的客户端接线。"""

import inspect

import pytest

from finchx import FinchX, SourceError
from finchx.api import news


def test_news_has_exactly_four_public_methods_and_no_legacy_aliases():
    api = FinchX().news
    assert [name for name, value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)] == ["agp_list", "bd_list", "em_list", "em_get"]
    assert list(inspect.signature(api.agp_list).parameters) == ["limit", "since", "until"]
    assert list(inspect.signature(api.bd_list).parameters) == ["limit", "since", "until"]
    assert list(inspect.signature(api.em_list).parameters) == ["code", "limit", "since", "until"]
    assert list(inspect.signature(api.em_get).parameters) == ["url"]
    assert inspect.signature(api.agp_list).parameters["limit"].default == 20
    assert inspect.signature(api.bd_list).parameters["limit"].default == 20
    assert inspect.signature(api.em_list).parameters["limit"].default == 20
    for name in ["get", "get_many", "agp", "bd", "em", "news"]:
        assert not hasattr(api, name)
    for name in ["agp_list", "bd_list", "em_list", "em_get", "get_many"]:
        assert not hasattr(FinchX().market, name)


@pytest.mark.parametrize("name,module,args,expected", [
    ("agp_list", news.agp_news, (), (20, None, None)),
    ("agp_list", news.agp_news, (50, "2026-10-08", "2026-10-08 12:00:00"),
     (50, "2026-10-08", "2026-10-08 12:00:00")),
    ("bd_list", news.bd_news, (), (20, None, None)),
    ("bd_list", news.bd_news, (50, "2026-10-08", "2026-10-08 12:00:00"),
     (50, "2026-10-08", "2026-10-08 12:00:00")),
    ("em_list", news.em_news, ("600519",), ("600519", 20, None, None)),
    ("em_list", news.em_news, ("000001", 50, "2026-10-08", "2026-10-08 12:00:00"),
     ("000001", 50, "2026-10-08", "2026-10-08 12:00:00")),
    ("em_get", news.em_news, ("https://finance.eastmoney.com/a/202610081234.html",),
     ("https://finance.eastmoney.com/a/202610081234.html",)),
])
def test_each_entry_forwards_parameters_and_timeout_without_wrapping(monkeypatch, name, module, args, expected):
    sentinel = {"content": "来源正文"} if name == "em_get" else [{"title": "来源标题"}]
    calls = []

    def source(*source_args, timeout):
        calls.append((source_args, timeout))
        return sentinel

    monkeypatch.setattr(module, name, source)
    api = FinchX(timeout=2.5).news
    assert getattr(api, name)(*args) is sentinel
    assert calls == [(expected, 2.5)]
    assert getattr(api, name)(*args) is sentinel
    assert len(calls) == 2


def test_source_error_propagates_with_its_context(monkeypatch):
    error = SourceError("aigupiao", "来源分页损坏")

    def source(*args, **kwargs):
        raise error

    monkeypatch.setattr(news.agp_news, "agp_list", source)
    with pytest.raises(SourceError) as caught:
        FinchX().news.agp_list()
    assert caught.value is error
