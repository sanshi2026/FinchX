"""SkillHub 检索离线构造业务测试；无真实 API key 认证成功声明。"""

import pytest

from finchx import SourceError
from finchx.sources.iwencai import search as source


def replay(monkeypatch, payload):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return payload
    monkeypatch.setattr(source.http, "post_json", request)
    return calls


def search(query="汽车行业", channel="report", limit=50, key="invalid-test-key"):
    return source.search(query, channel, limit, api_key=key, timeout=2)


@pytest.mark.parametrize("channel", ["report", "announcement", "news"])
def test_explicit_key_single_size_request_source_order_and_five_fields(monkeypatch, channel):
    payload = {"status_code": 0, "data": [
        {"uid": "first", "title": "第一项", "publish_date": "2026-10-08", "score": 0, "extra": '{"url":"https://example.com/a?x=1#b","unknown":9}'},
        {"uid": "second", "title": None, "publish_date": "2026-10-09 12:30", "extra": {}},
        {"uid": "first", "title": "后读整行", "score": "0.5", "unnecessary": []},
    ]}
    calls = replay(monkeypatch, payload)
    result = search(channel=channel, limit=2)
    assert result == [{"uid": "first", "title": "后读整行", "published_at": None, "url": None, "score": 0.5},
                      {"uid": "second", "title": None, "published_at": "2026-10-09T12:30+08:00", "url": None, "score": None}]
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://openapi.iwencai.com/v1/comprehensive/search"
    assert kwargs["data"] == {"channels": [channel], "app_id": "AIME_SKILL", "query": "汽车行业", "size": 2}
    assert kwargs["headers"]["Authorization"] == "Bearer invalid-test-key"
    assert kwargs["headers"]["X-Claw-Skill-Id"] == f"{channel}-search" and kwargs["follow_redirects"] is False


def test_missing_score_and_valid_zero_distinct_and_empty_success(monkeypatch):
    replay(monkeypatch, {"status_code": 0, "data": [{"uid": "a", "score": 0}, {"uid": "b"}]})
    assert [r["score"] for r in search()] == [0.0, None]
    replay(monkeypatch, {"status_code": 0, "data": []})
    assert search() == []


@pytest.mark.parametrize("limit", [0, True, 51, None, 1.5, "1"])
def test_limit_is_one_request_size_1_to_50(monkeypatch, limit):
    calls = replay(monkeypatch, None)
    with pytest.raises(ValueError):
        search(limit=limit)
    assert calls == []


@pytest.mark.parametrize("key", [None, "", " ", "bad\r\nCookie: leak", 0, "中文"])
def test_key_invalid_and_environment_never_used(monkeypatch, key):
    monkeypatch.setenv("IWENCAI_API_KEY", "not-to-be-used")
    calls = replay(monkeypatch, None)
    with pytest.raises(ValueError):
        search(key=key)
    assert calls == []


@pytest.mark.parametrize("payload", [
    {}, {"status_code": 0}, {"status_code": 0, "data": None}, {"status_code": False, "data": []},
    {"status_code": 1, "data": []}, {"status_code": 0, "data": ["broken"]},
    {"status_code": 0, "data": [{"uid": None}]}, {"status_code": 0, "data": [{"title": "不猜身份"}]},
])
def test_required_identity_status_and_shape_fail(monkeypatch, payload):
    replay(monkeypatch, payload)
    with pytest.raises(SourceError):
        search()


@pytest.mark.parametrize("bad", [{"uid": "b", "score": True}, {"uid": "b", "score": "NaN"},
                                  {"uid": "b", "publish_date": "2026-02-30"},
                                  {"uid": "b", "extra": "not-json"}, {"uid": "b", "url": "javascript:x"},
                                  {"uid": "b", "title": 0}])
def test_limit_cannot_hide_known_bad_later_item(monkeypatch, bad):
    replay(monkeypatch, {"status_code": 0, "data": [{"uid": "a"}, bad]})
    with pytest.raises(SourceError):
        search(limit=1)


def test_unknown_added_fields_ignore_and_original_url_preserve(monkeypatch):
    replay(monkeypatch, {"status_code": 0, "new_envelope": "ignored", "data": [{"uid": "a", "extra": {"report_url": "https://example.com/report?x=1#f", "new": []}}]})
    assert search()[0]["url"] == "https://example.com/report?x=1#f"


def test_search_transport_failure_has_no_secret_context(monkeypatch):
    secret = "invalid-secret-offline-test"
    def broken(*args, **kwargs):
        raise SourceError("mock", secret)
    monkeypatch.setattr(source.http, "post_json", broken)
    with pytest.raises(SourceError) as caught:
        search(key=secret)
    assert secret not in str(caught.value) and caught.value.__context__ is None
