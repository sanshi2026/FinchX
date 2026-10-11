"""文章五个公开入口的客户端接线。"""

import inspect

import pytest

from finchx import FinchX, SourceError
from finchx.api import articles


def test_articles_has_exactly_five_public_methods_and_no_legacy_aliases():
    api = FinchX().articles
    assert [name for name, value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)] == [
                "hot_content", "ths_list", "ths_get", "agp_topic_articles", "agp_get",
            ]
    signature = inspect.signature(api.agp_topic_articles)
    assert list(signature.parameters) == ["limit", "sort"]
    assert signature.parameters["limit"].default == 20
    assert signature.parameters["sort"].default == "newest"
    assert list(inspect.signature(api.agp_get).parameters) == ["url"]
    assert list(inspect.signature(api.hot_content).parameters) == ["content_type", "limit"]
    assert inspect.signature(api.hot_content).parameters["content_type"].default == "topic"
    assert inspect.signature(api.hot_content).parameters["limit"].default == 20
    assert list(inspect.signature(api.ths_list).parameters) == ["topic_url", "limit"]
    assert inspect.signature(api.ths_list).parameters["limit"].default == 20
    assert list(inspect.signature(api.ths_get).parameters) == ["url"]
    for name in ["list", "get", "get_many", "agp_list", "agp_get_many",
                 "ths_get_many", "hotlist", "comment"]:
        assert not hasattr(api, name)
    fx = FinchX()
    for api in [fx.market, fx.news]:
        for name in ["hot_content", "ths_list", "ths_get", "agp_topic_articles", "agp_get", "get_many"]:
            assert not hasattr(api, name)


@pytest.mark.parametrize("name,args,expected", [
    ("hot_content", (), ("topic", 20)),
    ("hot_content", ("article", 40), ("article", 40)),
    ("ths_list", ("https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu",),
     ("https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu", 20)),
    ("ths_list", ("https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu", 40),
     ("https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu", 40)),
    ("ths_get", ("https://t.10jqka.com.cn/pid_700648219.shtml",),
     ("https://t.10jqka.com.cn/pid_700648219.shtml",)),
    ("agp_topic_articles", (), (20, "newest")),
    ("agp_topic_articles", (40, "hot"), (40, "hot")),
    ("agp_get", ("https://www.aigupiao.com/dynamic/detail/5792378",),
     ("https://www.aigupiao.com/dynamic/detail/5792378",)),
])
def test_each_entry_forwards_parameters_and_timeout_without_wrapping(
    monkeypatch, name, args, expected,
):
    sentinel = {"content": "来源正文"} if name.endswith("get") else [{"title": "来源标题"}]
    calls = []

    def source(*source_args, timeout):
        calls.append((source_args, timeout))
        return sentinel

    module = {"hot_content": articles.ths_hot_content, "ths_list": articles.ths_topic_articles,
              "ths_get": articles.ths_articles}.get(name, articles.agp_articles)
    monkeypatch.setattr(module, name, source)
    api = FinchX(timeout=2.5).articles
    assert getattr(api, name)(*args) is sentinel
    assert getattr(api, name)(*args) is sentinel
    assert calls == [(expected, 2.5), (expected, 2.5)]


@pytest.mark.parametrize("name,args", [
    ("hot_content", ()),
    ("ths_list", ("https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu",)),
    ("ths_get", ("https://t.10jqka.com.cn/pid_700648219.shtml",)),
    ("agp_topic_articles", ()),
    ("agp_get", ("https://www.aigupiao.com/view/detail/4141992",)),
])
def test_source_error_propagates_with_its_context(monkeypatch, name, args):
    error = SourceError("aigupiao", "来源文章结构损坏")

    def source(*args, **kwargs):
        raise error

    module = {"hot_content": articles.ths_hot_content, "ths_list": articles.ths_topic_articles,
              "ths_get": articles.ths_articles}.get(name, articles.agp_articles)
    monkeypatch.setattr(module, name, source)
    with pytest.raises(SourceError) as caught:
        getattr(FinchX().articles, name)(*args)
    assert caught.value is error
