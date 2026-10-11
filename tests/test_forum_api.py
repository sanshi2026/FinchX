"""论坛唯一入口、必填认证参数与来源薄转发。"""

from datetime import date
import inspect

import pytest

from finchx import FinchX, SourceError
from finchx.api import forum


def test_forum_exact_public_method_and_keyword_only_required_cookies():
    api = FinchX().forum
    assert [name for name, value in vars(type(api)).items()
            if not name.startswith("_") and callable(value)] == ["tgb_replies"]
    signature = inspect.signature(api.tgb_replies)
    assert list(signature.parameters) == ["limit", "since", "until", "cookies"]
    assert [signature.parameters[name].default for name in ["limit", "since", "until"]] == [20, None, None]
    assert signature.parameters["cookies"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["cookies"].default is inspect.Parameter.empty
    for name in ["list", "get", "replies", "get_many", "tgb_get", "user_names"]:
        assert not hasattr(api, name)


def test_forum_preserves_namespaces_timeout_and_requested_category_order():
    fx = FinchX(timeout=2.5)
    expected = {
        "reference": "trading_calendar", "market": "all_quotes", "fund_flow": "stock",
        "sector": "ths_concept_list", "company": "info", "financial": "statements",
        "regulation": "deviation", "hotlist": "stocks", "fupan": "jygs_replay",
        "news": "em_list", "articles": "hot_content", "disclosure": "em_list",
        "reports": "agp_list", "forum": "tgb_replies", "iwencai": "select",
    }
    assert list(vars(fx)) == list(expected)
    for namespace, method in expected.items():
        api = getattr(fx, namespace)
        assert callable(getattr(api, method)) and api._timeout == 2.5
        if namespace != "forum":
            assert not hasattr(api, "tgb_replies")


@pytest.mark.parametrize("args,kwargs,expected", [
    ((), {"cookies": "invalid-test-cookie=1"}, (20, None, None)),
    ((None, "2026/10/08 12:00:00", "20261009"),
     {"cookies": {"invalid_test_cookie": "1"}}, (None, "2026/10/08 12:00:00", "20261009")),
    ((), {"limit": 40, "since": date(2026, 10, 8), "until": date(2026, 10, 9),
          "cookies": "invalid-test-cookie=1"}, (40, date(2026, 10, 8), date(2026, 10, 9))),
])
def test_forum_forwards_inputs_and_timeout_without_wrapping_or_retaining_cookies(monkeypatch, args, kwargs, expected):
    sentinel = [{"reply_id": "103521904"}]
    calls = []

    def source(*source_args, cookies, timeout):
        calls.append((source_args, cookies, timeout))
        return sentinel

    monkeypatch.setattr(forum.tgb_forum, "tgb_replies", source)
    api = FinchX(timeout=2.5).forum
    for _ in range(2):
        assert api.tgb_replies(*args, **kwargs) is sentinel
    assert calls == [(expected, kwargs["cookies"], 2.5)] * 2
    assert all(cookie is kwargs["cookies"] for _, cookie, _ in calls)
    assert vars(api) == {"_timeout": 2.5}


@pytest.mark.parametrize("args,kwargs", [
    ((), {}),
    ((20, None, None, "invalid-test-cookie=1"), {}),
    ((), {"cookies": "invalid-test-cookie=1", "user_names": ["账户名"]}),
])
def test_forum_rejects_missing_or_positional_cookies_and_removed_user_names_before_source(monkeypatch, args, kwargs):
    def source(*args, **kwargs):
        pytest.fail("无效公开签名不应调用来源")

    monkeypatch.setattr(forum.tgb_forum, "tgb_replies", source)
    with pytest.raises(TypeError):
        FinchX().forum.tgb_replies(*args, **kwargs)


@pytest.mark.parametrize("error", [SourceError("taoguba", "来源拒绝认证"), ValueError("参数无效")])
def test_forum_propagates_source_and_parameter_errors(monkeypatch, error):
    def source(*args, **kwargs):
        raise error

    monkeypatch.setattr(forum.tgb_forum, "tgb_replies", source)
    with pytest.raises(type(error)) as caught:
        FinchX().forum.tgb_replies(cookies="invalid-test-cookie=1")
    assert caught.value is error
