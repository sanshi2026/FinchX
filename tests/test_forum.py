from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from finchx.collectors import FetchResult
from finchx.contracts import Source
from finchx.datasets.forum import ForumReply, ForumRepliesRequest
from finchx.providers.errors import ProviderError
from finchx.providers.taoguba_forum import (
    TAOGUBA_REPLIES_ENDPOINT,
    TaogubaForumProvider,
)
from finchx.query.forum import ForumService


REPLY_RECORD = {
    "actionDate": "2026-09-23 00:19:12",
    "actionID": "900001",
    "actionName": "R",
    "activeFlag": "1",
    "body": "回复正文甲",
    "newTopicID": "2t06UnHyXz8",
    "objectID": "103241636",
    "objectName": "节点是短线的灵魂",
    "quoteContent": "今日的金安国纪 老师认可吗",
    "quoteUserName": "提问者甲",
    "userID": "8808042",
    "userName": "作者甲",
    "otherID": "1001",
}

SECOND_REPLY_RECORD = {
    **REPLY_RECORD,
    "actionDate": "2026-09-22 10:00:00",
    "actionID": "900000",
    "body": "回复正文乙",
    "objectID": "103241635",
    "objectName": "另一篇帖子",
    "quoteContent": "引用提问者说：被回复的完整提问乙",
    "quoteUserName": "提问者乙",
    "userID": "8808043",
    "userName": "作者乙",
}

FIXTURE_PAYLOAD = {
    "dto": {
        "record": [
            REPLY_RECORD,
            SECOND_REPLY_RECORD,
            {**REPLY_RECORD, "actionName": "T", "objectID": "103241634"},
            {**REPLY_RECORD, "quoteContent": "", "objectID": "103241633"},
        ]
    }
}


class StubTransport:
    def __init__(self, payload: object = FIXTURE_PAYLOAD, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.calls: list[tuple[str, dict, dict, float]] = []

    def get(self, url, *, params, headers, timeout_seconds):
        self.calls.append((url, dict(params), dict(headers), timeout_seconds))
        if len(self.calls) > 1 and self.status_code == 200 and not isinstance(self.payload, str):
            text = json.dumps({"dto": {"record": []}})
        elif isinstance(self.payload, str):
            text = self.payload
        else:
            text = json.dumps(self.payload, ensure_ascii=False)
        return type("Response", (), {"status_code": self.status_code, "text": text})()


class PagedStubTransport:
    def __init__(self):
        self.calls: list[tuple[str, dict, dict, float]] = []

    def get(self, url, *, params, headers, timeout_seconds):
        self.calls.append((url, dict(params), dict(headers), timeout_seconds))
        offset = params["actionID"]
        if offset == 0:
            records = [
                {**REPLY_RECORD, "objectID": str(200000 + index), "actionID": str(800000 + index)}
                for index in range(20)
            ]
        elif offset == 20:
            records = [{**SECOND_REPLY_RECORD, "objectID": "200020"}]
        else:
            records = []
        payload = json.dumps({"dto": {"record": records}}, ensure_ascii=False)
        return type("Response", (), {"status_code": 200, "text": payload})()


def _service(transport: StubTransport) -> ForumService:
    provider = TaogubaForumProvider(
        transport=transport,
        clock=lambda: datetime(2026, 9, 23, 1, 0, tzinfo=timezone.utc),
    )
    return ForumService(provider)


def test_replies_uses_following_json_and_separates_reply_and_parent_content():
    transport = StubTransport()
    result = _service(transport).replies(cookies="sid=owned")

    assert isinstance(result, FetchResult)
    assert result.dataset_id == "forum.replies"
    assert result.provider_id == "taoguba.forum"
    assert [record.reply_id for record in result.data] == ["900001", "900000"]
    first = result.data[0]
    assert first.reply_content == "回复正文甲"
    assert first.parent_username == "提问者甲"
    assert first.parent_content == "今日的金安国纪 老师认可吗"
    assert first.reply_content != first.parent_content
    assert first.reply_id == "900001"
    assert str(first.reply_url) == "https://www.tgb.cn/a/2t06UnHyXz8/900001#900001"
    assert first.post_id == "2t06UnHyXz8"
    assert first.post_title == "节点是短线的灵魂"
    assert first.user_id == "8808042"
    assert first.reply_time.tzinfo is not None
    assert first.captured_at.tzinfo is not None
    assert first.source.source_record_id == first.reply_id
    assert str(first.source.source_url) == TAOGUBA_REPLIES_ENDPOINT
    assert transport.calls[0][0] == TAOGUBA_REPLIES_ENDPOINT
    assert transport.calls[0][1] == {"perPageNum": 20, "actionID": 0, "type": "A"}
    assert transport.calls[0][2]["X-Requested-With"] == "XMLHttpRequest"


def test_replies_paginates_using_action_offset_until_max_results():
    transport = PagedStubTransport()
    result = _service(transport).replies(cookies="sid=owned", max_results=21)

    assert len(result.data) == 21
    assert [call[1]["actionID"] for call in transport.calls] == [0, 20]


def test_replies_does_not_treat_a_short_page_as_the_end_of_the_feed():
    class ShortPageTransport:
        def __init__(self):
            self.calls = []

        def get(self, url, *, params, headers, timeout_seconds):
            self.calls.append(dict(params))
            if params["actionID"] == 0:
                records = [REPLY_RECORD]
            elif params["actionID"] == 20:
                records = [SECOND_REPLY_RECORD]
            else:
                records = []
            payload = json.dumps({"dto": {"record": records}}, ensure_ascii=False)
            return type("Response", (), {"status_code": 200, "text": payload})()

    transport = ShortPageTransport()
    records = _service(transport).replies(cookies="sid=owned").data

    assert [record.reply_id for record in records] == ["900001", "900000"]
    assert [call["actionID"] for call in transport.calls] == [0, 20, 40]


def test_replies_filters_only_reply_activity_with_complete_quote():
    records = _service(StubTransport()).replies(cookies="sid=owned").data
    assert all(record.parent_content for record in records)
    assert all(record.parent_username for record in records)
    assert all(record.reply_content for record in records)


def test_post_title_action_text_is_not_returned_as_title():
    payload = {"dto": {"record": [{**REPLY_RECORD, "objectName": "查看原文"}]}}
    record = _service(StubTransport(payload)).replies(cookies="sid=owned").data[0]
    assert record.post_title is None


def test_exact_user_filter_dates_and_max_results():
    transport = StubTransport()
    result = _service(transport).replies(
        cookies={"sid": "owned"},
        user_names=[" 作者乙 ", "作者乙"],
        since="2026-09-20",
        until=date(2026, 9, 22),
        max_results=1,
    )
    assert [record.username for record in result.data] == ["作者乙"]
    assert transport.calls[0][2]["Cookie"] == "sid=owned"


def test_forum_reply_model_cross_checks_post_and_reply_urls():
    values = {
        "replyId": "103241636",
        "userId": "8808042",
        "username": "作者甲",
        "replyContent": "回复正文甲",
        "parentUsername": "提问者甲",
        "parentContent": "被回复的完整提问甲",
        "postId": "2t06UnHyXz8",
        "postUrl": "https://www.tgb.cn/a/2t06UnHyXz8",
        "replyUrl": "https://www.tgb.cn/a/2t06UnHyXz8/103241636#103241636",
        "source": Source(
            providerId="taoguba.forum",
            sourceRecordId="103241636",
            sourceUrl=TAOGUBA_REPLIES_ENDPOINT,
        ),
        "capturedAt": datetime(2026, 9, 23, tzinfo=timezone.utc),
    }
    ForumReply(**values)
    with pytest.raises(ValueError, match="postId"):
        ForumReply(**{**values, "postId": "other-post"})
    with pytest.raises(ValueError, match="postUrl"):
        ForumReply(**{**values, "postUrl": "https://www.tgb.cn/a/other-post"})
    with pytest.raises(ValueError, match="replyId"):
        ForumReply(**{**values, "replyUrl": "https://www.tgb.cn/a/2t06UnHyXz8/999#999"})


@pytest.mark.parametrize("value", [[], [""], ["a", 1], "a", b"a"])
def test_replies_rejects_invalid_user_name_filters(value):
    with pytest.raises((TypeError, ValueError)):
        _service(StubTransport()).replies(cookies="sid=owned", user_names=value)


@pytest.mark.parametrize("value", [True, 1.0, 0, -1])
def test_replies_rejects_invalid_max_results(value):
    with pytest.raises((TypeError, ValueError)):
        _service(StubTransport()).replies(cookies="sid=owned", max_results=value)


def test_replies_requires_cookies_and_ordered_dates():
    with pytest.raises(ValueError, match="since"):
        _service(StubTransport()).replies(
            cookies="sid=owned", since="2026-09-23", until="2026-09-20"
        )
    with pytest.raises((TypeError, ValueError)):
        _service(StubTransport()).replies()


@pytest.mark.parametrize("bound", ["since", "until"])
def test_replies_rejects_naive_datetime_bounds(bound):
    with pytest.raises(ValueError, match="timezone offset"):
        _service(StubTransport()).replies(
            cookies="sid=owned",
            **{bound: datetime(2026, 9, 23, 9, 30)},
        )


@pytest.mark.parametrize(
    "payload, message",
    [
        ("not json", "valid JSON"),
        ({"dto": "bad"}, "dto is not an object"),
        ({"dto": {"record": ["bad"]}}, "list of objects"),
    ],
)
def test_malformed_following_responses_fail(payload, message):
    with pytest.raises(ProviderError, match=message):
            _service(StubTransport(payload)).replies(cookies="sid=owned")


def test_missing_terminal_record_is_an_empty_page():
    class TerminalStubTransport(StubTransport):
        def get(self, url, *, params, headers, timeout_seconds):
            self.calls.append((url, dict(params), dict(headers), timeout_seconds))
            if len(self.calls) == 1:
                text = json.dumps(FIXTURE_PAYLOAD, ensure_ascii=False)
            else:
                text = json.dumps({"dto": {}}, ensure_ascii=False)
            return type("Response", (), {"status_code": 200, "text": text})()

    records = _service(TerminalStubTransport()).replies(cookies="sid=owned").data
    assert [record.reply_id for record in records] == ["900001", "900000"]


def test_auth_empty_and_http_errors_are_not_silent_empty_results():
    for transport in (
        StubTransport(""),
        StubTransport({"dto": {"record": []}}, status_code=503),
    ):
        with pytest.raises(ProviderError):
            _service(transport).replies(cookies="sid=owned")


def test_cookie_never_enters_request_model_result_source_provenance_or_repr():
    secret = "sid=do-not-leak"
    result = _service(StubTransport()).replies(cookies=secret)
    assert "cookies" not in ForumRepliesRequest.model_fields
    assert secret not in repr(result)
    assert secret not in repr(result.data)
    assert secret not in repr(result.provenance)
    assert all(secret not in repr(row) for row in result.to_dicts())
