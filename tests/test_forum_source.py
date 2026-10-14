"""构造来源验证接口边界；不代表有效 Cookie 的认证成功样例。"""

from datetime import date, datetime
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import FinchX
from finchx._common.errors import SourceError
from finchx.sources.taoguba import forum


def row(reply="101", action="1", **extra):
    return {**dict(actionID=action, actionName="R", otherID=reply, objectID="900",
                newTopicID="abc123", userID="88", userName="作者",
                actionDate="2026-10-08 11:32:58", body="摘要"), **extra}


def payload(rows):
    return {"status": True, "dto": {"record": rows}}


def comment(reply, body, parent=None):
    quote = (f'<div class="comment-data-quote"><a href="/blog/99">引用作者</a>'
             f'<p class="quote-content">引用摘要</p><a data-quote-id="{parent}">展开</a></div>') if parent else ""
    return (f'<div class="comment-data"><div class="comment-data-text" id="reply{reply}">{body}</div>'
            f'{quote}<a data-topic-id="900" data-reply-id="{reply}"></a></div>')


def page(*comments):
    return '<script>var topicTopicID2=900;var topicPageNo=1;var topicPageNum=10;</script>' + "".join(comments)


def transport(monkeypatch, feeds, full=None, pages=None):
    calls = []
    feed_pages = iter(feeds)
    def read(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs["follow_redirects"] is False
        assert kwargs["headers"]["Cookie"] == "sid=test"
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if url.startswith(forum._FEED):
            value = next(feed_pages)
        elif url.startswith(forum._FULL):
            identity = query["replyID"][0]
            value = (full or {}).get(identity, {"status": True, "dto": "全文" + identity})
        else:
            value = (pages or {}).get(parsed.path, "<html>可选页面没有回复业务结构</html>")
        if isinstance(value, Exception):
            raise value
        return json.dumps(value) if isinstance(value, dict) else value
    monkeypatch.setattr(forum, "get_text", read)
    return calls


def fetch(**kwargs):
    return forum.tgb_replies(cookies="sid=test", timeout=5, **kwargs)


def test_default_full_and_fixed_fields(monkeypatch):
    calls = transport(monkeypatch, [payload([row()]), payload([])])
    result = fetch()
    assert list(result[0]) == ["reply_id", "user_id", "username", "reply_time", "content", "image_urls",
                               "post_url", "url", "parent_reply_id", "parent_username", "parent_content", "parent_image_urls"]
    assert result[0]["content"] == "全文101"
    assert result[0]["reply_time"] == "2026-10-08T11:32:58+08:00"
    assert result[0]["parent_image_urls"] is None
    assert len(calls) == 3


def test_short_page_and_old_time_do_not_end_paging(monkeypatch):
    calls = transport(monkeypatch, [payload([row(action="1", actionDate="2026-10-01 09:00:00")]),
                                   payload([row("102", "2")]), payload([])])
    result = fetch(since="2026-10-08", limit=1)
    assert [item["reply_id"] for item in result] == ["102"]
    assert len(calls) == 3


def test_same_reply_different_activities_merges_after_full_page(monkeypatch):
    calls = transport(monkeypatch, [payload([row(), row(action="2", userName="更新作者"), row("102", "3")])],
                      pages={"/a/abc123": page(comment("101", "全文101"), comment("102", "全文102"))})
    result = fetch(limit=2)
    assert [item["reply_id"] for item in result] == ["101", "102"]
    assert result[0]["username"] == "更新作者"
    assert len(calls) == 2


def test_cross_page_overlap_updates_whole_business_row(monkeypatch):
    transport(monkeypatch, [payload([row()]), payload([row(action="2", userName="更新"), row("102", "3")]), payload([])])
    assert fetch(limit=None)[0]["username"] == "更新"


@pytest.mark.parametrize("bad", [row("bad", "2"), row("102", "2", actionDate="2026-13-08 11:00:00"),
                                     row("102", "2", userID=True)])
def test_limit_cannot_hide_later_source_damage(monkeypatch, bad):
    calls = transport(monkeypatch, [payload([row(), bad])])
    with pytest.raises(SourceError):
        fetch(limit=1)
    assert len(calls) == 1


def test_filtered_invalid_time_cannot_be_hidden(monkeypatch):
    transport(monkeypatch, [payload([row(actionDate="wrong")])])
    with pytest.raises(SourceError):
        fetch(since="2026-10-08")


@pytest.mark.parametrize("bound", ["2026-10-08", "20261008", "2026/10/08", "2026-10-08 11:32:58",
                                    "20261008 11:32:58", "2026/10/08 11:32:58", date(2026, 10, 8)])
def test_six_time_inputs_and_date_objects(monkeypatch, bound):
    transport(monkeypatch, [payload([row()])])
    assert len(fetch(limit=1, since=bound, until=bound)) == 1


@pytest.mark.parametrize("bound", [datetime(2026, 10, 8), "2026-10-08 11:32", " 20261008", "２０２６１００８"])
def test_invalid_public_time_before_request(monkeypatch, bound):
    monkeypatch.setattr(forum, "get_text", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError):
        fetch(since=bound)


def test_source_minute_precision_preserved(monkeypatch):
    transport(monkeypatch, [payload([row(actionDate="2026-10-08 11:32")])])
    assert fetch(limit=1)[0]["reply_time"] == "2026-10-08T11:32+08:00"


def test_html_paragraphs_table_images_and_pure_image(monkeypatch):
    full = {"101": {"status": True, "dto": '<p>第一段<br>下一行</p><p>第二段</p><table><tr><td>甲</td></tr><tr><td>乙</td></tr></table><img data-original="//image.tgb.cn/a.jpg?q=1"><a href="unknown:link">业务文字</a>'},
            "102": {"status": True, "dto": '<img src="https://image.tgb.cn/b.jpg">'}}
    transport(monkeypatch, [payload([row(), row("102", "2")])], full)
    result = fetch(limit=2)
    assert "第一段\n下一行\n\n第二段" in result[0]["content"]
    assert "甲\n\n乙" in result[0]["content"]
    assert result[0]["image_urls"] == ["https://image.tgb.cn/a.jpg?q=1"]
    assert result[1]["content"] is None and result[1]["image_urls"] == ["https://image.tgb.cn/b.jpg"]


def test_shared_page_parent_full_reused_without_expand(monkeypatch):
    rows = [row("102", "1", quoteContent="摘要"), row("103", "2", quoteContent="摘要")]
    markup = page(comment("101", "完整父回复<br>段落"), comment("102", "回复二", "101"), comment("103", "回复三", "101"))
    calls = transport(monkeypatch, [payload(rows)], pages={"/a/abc123": markup})
    result = fetch(limit=2)
    assert result[0]["parent_reply_id"] == "101"
    assert result[0]["parent_content"] == "完整父回复\n段落"
    assert result[1]["parent_content"] == result[0]["parent_content"]
    assert len(calls) == 2


@pytest.mark.parametrize("body", ["登录可查看全文", "", "摘要<a onclick=\"moreReplyContent()\">展开</a>"])
def test_selected_gated_or_empty_page_body_uses_exact_full(monkeypatch, body):
    markup = page(comment("100", "该回复已删除"), comment("102", body, "101"))
    calls = transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])],
                      pages={"/a/abc123": markup})
    result = fetch(limit=1)
    assert result[0]["content"] == "全文102"
    assert len(calls) == 4


def test_unrelated_short_quote_does_not_block_exact_target(monkeypatch):
    short = '<div class="comment-data-quote"><p class="quote-content">短引用</p></div>'
    markup = page(comment("100", "无关回复").replace('</div><a data-topic', '</div>' + short + '<a data-topic'),
                  comment("102", "当前全文", "101"))
    transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])], pages={"/a/abc123": markup})
    assert fetch(limit=1)[0]["content"] == "当前全文"


def test_real_public_dom_long_parent_and_distinct_reply(monkeypatch):
    markup = (Path(__file__).parent / "fixtures/forum/public-replies-103521741-103521904.html").read_text(encoding="utf-8")
    record = row("103521904", "1", objectID="8794268", newTopicID="2vIcb0QPJZz",
                 userID="12160110", userName="阿乳在看", actionDate="2026-10-08 11:37", quoteContent="引用摘要")
    # 构造动态明确标记；真实证据只来自公开HTML，不代表账户认证成功。
    calls = transport(monkeypatch, [payload([record])], pages={"/a/2vIcb0QPJZz": markup})
    result = fetch(limit=1)[0]
    assert result["content"] == "真的学到了很多，谢谢飞哥"
    assert result["parent_reply_id"] == "103521741"
    assert result["parent_username"] == "洛飞超短笔记"
    assert len(result["parent_content"]) == 359
    assert result["parent_content"].endswith("毕竟后面小票行情也不适合大仓位参与。")
    assert result["reply_time"] == "2026-10-08T11:37+08:00"
    assert result["parent_image_urls"] == [] and len(calls) == 2


def test_missing_parent_on_page_expands_each_unique_id_once(monkeypatch):
    markup = page(comment("102", "当前摘要<a onclick=\"moreReplyContent()\">展开</a>", "101"), comment("103", "回复三", "101"))
    calls = transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要"), row("103", "2", quoteContent="摘要")])],
                      pages={"/a/abc123": markup})
    result = fetch(limit=2)
    assert result[0]["content"] == "全文102" and result[0]["parent_content"] == "全文101"
    assert len([url for url, _ in calls if "replyID=101" in url]) == 1


def test_locator_is_exact_and_does_not_scan_all_pages(monkeypatch):
    calls = transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])],
                      pages={"/a/abc123": page(comment("101", "父全文")),
                             "/a/abc123/102": page(comment("102", "目标全文", "101"))})
    result = fetch(limit=1)
    assert result[0]["content"] == "目标全文" and result[0]["parent_content"] == "父全文"
    assert len(calls) == 3


@pytest.mark.parametrize("bad", [{"status": False, "dto": None}, {"status": True, "dto": "登录后查看全文"},
                                 {"status": True, "dto": "该回复已删除"}, {"status": True, "dto": ""},
                                 {"status": True, "dto": []}])
def test_detail_failure_never_returns_feed_excerpt(monkeypatch, bad):
    transport(monkeypatch, [payload([row()])], {"101": bad})
    with pytest.raises(SourceError):
        fetch(limit=1)


def test_failure_after_prior_full_reply_never_partial(monkeypatch):
    transport(monkeypatch, [payload([row(), row("102", "2")])], {"102": {"status": False}})
    with pytest.raises(SourceError):
        fetch(limit=2)


@pytest.mark.parametrize("feeds", [[payload([row()]), payload([row()])],
                                   [payload([row()]), {"dto": {}}],
                                   [{"status": False, "dto": {"record": []}}],
                                   [payload([row(), row()])]])
def test_stall_unknown_terminal_failure_and_duplicate_activity(monkeypatch, feeds):
    transport(monkeypatch, feeds)
    with pytest.raises(SourceError):
        fetch(limit=None)


def test_source_identity_conflict(monkeypatch):
    transport(monkeypatch, [payload([row(), row(action="2", objectID="901")])])
    with pytest.raises(SourceError):
        fetch(limit=1)


@pytest.mark.parametrize("extra", [{"objectID": "901"}, {"newTopicID": "other"}])
def test_topic_and_url_mapping_conflict_across_distinct_replies(monkeypatch, extra):
    calls = transport(monkeypatch, [payload([row(), row("102", "2", **extra)])])
    with pytest.raises(SourceError):
        fetch(limit=1)
    assert len(calls) == 1


def test_required_page_is_prepared_before_earlier_unquoted_reply(monkeypatch):
    markup = page(comment("101", "完整父回复"), comment("102", "当前回复", "101"))
    calls = transport(monkeypatch, [payload([row(), row("102", "2", quoteContent="摘要")])],
                      pages={"/a/abc123": markup})
    result = fetch(limit=2)
    assert [item["reply_id"] for item in result] == ["101", "102"]
    assert result[1]["parent_content"] == result[0]["content"]
    assert len(calls) == 2


def test_page_observed_quote_preserved_when_feed_quote_metadata_missing(monkeypatch):
    markup = page(comment("101", "完整父回复"), comment("102", "当前回复", "101"))
    calls = transport(monkeypatch, [payload([row(), row("102", "2")])], pages={"/a/abc123": markup})
    result = fetch(limit=2)
    assert result[0]["parent_reply_id"] is None
    assert result[1]["parent_reply_id"] == "101"
    assert result[1]["parent_username"] == "引用作者"
    assert result[1]["parent_content"] == "完整父回复"
    assert result[1]["parent_image_urls"] == []
    assert len(calls) == 2


def test_single_direct_read_does_not_guess_or_fetch_unobserved_quote(monkeypatch):
    calls = transport(monkeypatch, [payload([row()])])
    result = fetch(limit=1)[0]
    assert result["parent_reply_id"] is None and result["parent_content"] is None
    assert all("/a/" not in url for url, _ in calls)
    assert len(calls) == 2


def test_page_observed_quote_without_identity_fails_even_if_feed_quote_missing(monkeypatch):
    markup = page(comment("101", "父回复"), comment("102", "当前回复", "101").replace('data-quote-id="101"', 'data-unknown="101"'))
    transport(monkeypatch, [payload([row(), row("102", "2")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=2)


def test_parent_pure_image_and_display_blog_links(monkeypatch):
    markup = page(comment("101", '<img src="https://image.tgb.cn/parent.jpg">'),
                  comment("102", "当前回复", "101").replace('引用摘要</p>', '<a href="/blog/123">无关显示文字</a>引用摘要</p>'))
    transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])], pages={"/a/abc123": markup})
    result = fetch(limit=1)[0]
    assert result["parent_content"] is None
    assert result["parent_image_urls"] == ["https://image.tgb.cn/parent.jpg"]
    assert result["parent_username"] == "引用作者"


def test_ambiguous_optional_page_author_keeps_same_response_feed_name(monkeypatch):
    markup = page(comment("101", "父全文"), comment("102", "当前回复", "101").replace('引用作者</a>', '引用作者</a><a href="/blog/123">额外显示链接</a>'))
    transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要", quoteUserName="源引用作者")])],
              pages={"/a/abc123": markup})
    assert fetch(limit=1)[0]["parent_username"] == "源引用作者"


def test_matched_page_without_parent_identity_cannot_return_quote_excerpt(monkeypatch):
    markup = page(comment("102", "当前回复", "101").replace('data-quote-id="101"', 'data-unknown="101"'))
    transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=1)


@pytest.mark.parametrize("function", ["moreQuoteContent", "lessQuoteContent"])
def test_official_numeric_quote_callback_preserves_exact_parent(monkeypatch, function):
    markup = page(comment("101", "完整父回复"), comment("102", "当前回复", "101").replace(
        'data-quote-id="101"', f'onclick="{function}(this, 900, 101)"'))
    calls = transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])],
                      pages={"/a/abc123": markup})
    result = fetch(limit=1)[0]
    assert result["parent_reply_id"] == "101"
    assert result["parent_content"] == "完整父回复"
    assert len(calls) == 2


@pytest.mark.parametrize("callback", ["moreQuoteContent(this,901,101)", "moreQuoteContent(this,900,103)"])
def test_numeric_quote_callback_conflict_fails(monkeypatch, callback):
    markup = page(comment("102", "当前回复", "101").replace(
        'data-quote-id="101"', f'data-quote-id="101" onclick="{callback}"'))
    transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=1)


@pytest.mark.parametrize("body,content,images", [
    ("完整引用<br>第二行", "完整引用\n第二行", []),
    ('<img src="https://image.tgb.cn/parent.jpg">', None, ["https://image.tgb.cn/parent.jpg"]),
])
def test_native_unexpanded_quote_preserves_body_without_inventing_parent_id(monkeypatch, body, content, images):
    markup = page(comment("102", "当前回复", "101").replace(
        '<p class="quote-content">引用摘要</p><a data-quote-id="101">展开</a>',
        f'<p class="quote-content data-quote-text">{body}</p>'))
    calls = transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])],
                      pages={"/a/abc123": markup})
    result = fetch(limit=1)[0]
    assert result["parent_reply_id"] is None
    assert result["parent_username"] == "引用作者"
    assert result["parent_content"] == content and result["parent_image_urls"] == images
    assert len(calls) == 2


def test_real_fault_short_quote_dom_preserves_full_text_without_parent_id(monkeypatch):
    quote = (Path(__file__).parent / "fixtures/forum/short-quote-103543436.html").read_text(encoding="utf-8")
    # 引用节点是实际故障证据；动态、当前正文和最小页面包装明确构造。
    markup = ('<script>var topicTopicID2=8794268;</script>'
              '<div class="comment-data"><div class="comment-data-text" id="reply103543436">构造当前正文</div>'
              + quote + '<a data-topic-id="8794268" data-reply-id="103543436"></a></div>')
    record = row("103543436", objectID="8794268", newTopicID="2vIcb0QPJZz", quoteContent="构造动态引用标记")
    calls = transport(monkeypatch, [payload([record])], pages={"/a/2vIcb0QPJZz": markup})
    result = fetch(limit=1)[0]
    assert result["content"] == "构造当前正文"
    assert result["parent_reply_id"] is None
    assert result["parent_username"] == "独智行者"
    assert result["parent_content"] == "创业板3个月-30%跌幅，牛市幻想破灭了"
    assert result["parent_image_urls"] == []
    assert len(calls) == 2


@pytest.mark.parametrize("control", [
    '<span class="data-quote-zk"></span>', '<a onclick="moreQuoteContent(this,unknown,unknown)">展开</a>',
    '<a>[展开]</a>',
])
def test_unidentified_quote_with_expand_control_still_fails(monkeypatch, control):
    markup = page(comment("102", "当前回复", "101").replace(
        '<p class="quote-content">引用摘要</p><a data-quote-id="101">展开</a>',
        f'<p class="quote-content data-quote-text">摘要</p>{control}'))
    transport(monkeypatch, [payload([row("102", "1", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=1)


def test_optional_page_without_identity_uses_exact_full(monkeypatch):
    calls = transport(monkeypatch, [payload([row(), row("102", "2")])])
    assert [item["content"] for item in fetch(limit=2)] == ["全文101", "全文102"]
    assert len(calls) == 4


def test_exact_full_that_is_still_expandable_fails(monkeypatch):
    transport(monkeypatch, [payload([row()])], {"101": {"status": True, "dto": '<p>摘要</p><a onclick="moreReplyContent()">展开</a>'}})
    with pytest.raises(SourceError):
        fetch(limit=1)


def test_budget_failure(monkeypatch):
    monkeypatch.setattr(forum, "_MAX_PAGES", 1)
    transport(monkeypatch, [payload([row()])])
    with pytest.raises(SourceError):
        fetch(limit=None)


@pytest.mark.parametrize("cookie", ["", "x=a\r\nOther: b", {"x": "a\nb"}, {"bad name": "x"}, {"x": 2}, True])
def test_cookie_validation_precedes_network(monkeypatch, cookie):
    monkeypatch.setattr(forum, "get_text", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError):
        forum.tgb_replies(cookies=cookie, timeout=5)


@pytest.mark.parametrize("limit", [True, 0, -1, 1.2])
def test_limit_validation(monkeypatch, limit):
    with pytest.raises(ValueError):
        fetch(limit=limit)


def test_cookie_mapping(monkeypatch):
    transport(monkeypatch, [payload([])])
    assert forum.tgb_replies(cookies={"sid": "test"}, timeout=5) == []


def feed_cursors(calls):
    return [parse_qs(urlsplit(url).query)["actionID"][0]
            for url, _ in calls if url.startswith(forum._FEED)]


@pytest.mark.parametrize("size", [0, "0"])
@pytest.mark.parametrize("record_form", ["omitted", "null", "empty-array"])
def test_official_size_zero_terminal_variants_require_explicit_success(monkeypatch, size, record_form):
    # 当前官方 JS 的成功 size=0 终点协议；这是构造回归，并非用户登录 JSON 重放。
    dto = {"size": size}
    if record_form != "omitted":
        dto["record"] = None if record_form == "null" else []
    calls = transport(monkeypatch, [{"status": True, "dto": dto}])
    assert fetch(limit=100, since="20260930", until="20261009") == []
    assert feed_cursors(calls) == ["0"]


@pytest.mark.parametrize("empty", [payload([]), {"status": True, "dto": {"record": [], "size": 1000}}])
def test_successful_explicit_empty_array_retains_exhaustion_without_guessing_size(monkeypatch, empty):
    transport(monkeypatch, [empty])
    assert fetch(limit=100) == []


def test_limit100_date_window_ends_legally_and_reads_full_reply_and_parent(monkeypatch):
    feeds = [
        payload([row("101", "930017781", actionDate="2026-09-30 10:00:00"),
                 row("103", "930017764", actionDate="2026-09-29 23:59:59")]),
        payload([row("102", "930017713", actionDate="2026-10-09 11:32:58", quoteContent="引用摘要"),
                 {"actionID": "930017705", "actionName": "P"}]),
        {"status": True, "dto": {"size": "0"}},
    ]
    markup = page(comment("101", "完整父回复第一段<p>完整父回复第二段</p>"),
                  comment("102", "完整目标回复", "101"))
    calls = transport(monkeypatch, feeds, pages={"/a/abc123": markup})
    result = FinchX(timeout=5).forum.tgb_replies(
        limit=100, cookies="sid=test", since="20260930", until="20261009")
    assert feed_cursors(calls) == ["0", "930017764", "930017705"]
    assert [item["reply_id"] for item in result] == ["101", "102"]
    assert result[0]["content"] == "完整父回复第一段\n完整父回复第二段"
    assert result[1]["content"] == "完整目标回复"
    assert result[1]["parent_reply_id"] == "101" and result[1]["parent_content"] == result[0]["content"]
    assert all(len(item) == 12 for item in result)
    assert len(calls) == 4  # 三份完整动态及一份主题页复用，无摘要回填。


def test_cursor_uses_complete_source_tail_including_non_reply_and_cross_page_overlap(monkeypatch):
    feeds = [
        payload([row("101", "831567993"), {"actionID": "831567978", "actionName": "P"}]),
        payload([row("101", "831567993", userName="后读更新"),
                 row("102", "831567950"), {"actionID": "831567944", "actionName": "P"}]),
        {"status": True, "dto": {"size": 0, "record": None}},
    ]
    markup = page(comment("101", "完整回复101"), comment("102", "完整回复102"))
    calls = transport(monkeypatch, feeds, pages={"/a/abc123": markup})
    result = fetch(limit=None)
    assert feed_cursors(calls) == ["0", "831567978", "831567944"]
    assert [item["reply_id"] for item in result] == ["101", "102"]
    assert result[0]["username"] == "后读更新" and result[0]["content"] == "完整回复101"


def test_cursor_progresses_through_all_non_reply_or_time_excluded_pages(monkeypatch):
    feeds = [
        payload([{"actionID": "731555999", "actionName": "P"}]),
        payload([row("101", "731555801", actionDate="2026-09-29 23:59:59")]),
        payload([row("102", "731555719", actionDate="2026-10-08 11:32:58")]),
    ]
    calls = transport(monkeypatch, feeds)
    assert [item["reply_id"] for item in fetch(limit=1, since="20260930", until="20261009")] == ["102"]
    assert feed_cursors(calls) == ["0", "731555999", "731555801"]


def test_new_activity_does_not_hide_repeated_source_cursor(monkeypatch):
    feeds = [
        payload([row("101", "631510005"), {"actionID": "631510001", "actionName": "P"}]),
        payload([row("102", "631509997"), {"actionID": "631510001", "actionName": "P"}]),
    ]
    calls = transport(monkeypatch, feeds)
    with pytest.raises(SourceError, match="停滞"):
        fetch(limit=100)
    assert feed_cursors(calls) == ["0", "631510001"]
    assert all(url.startswith(forum._FEED) for url, _ in calls)


@pytest.mark.parametrize("size", [None, False, True, "", "00", "0.0", "error", "wrong", -1, 0.0, [], {}])
def test_known_invalid_size_fails_even_with_empty_array(monkeypatch, size):
    transport(monkeypatch, [{"status": True, "dto": {"size": size, "record": []}}])
    with pytest.raises(SourceError, match="size"):
        fetch(limit=100)


@pytest.mark.parametrize("record", [{}, "", 0, False, "[]", "broken-array"])
def test_size_zero_does_not_hide_damaged_record_type(monkeypatch, record):
    transport(monkeypatch, [{"status": True, "dto": {"size": 0, "record": record}}])
    with pytest.raises(SourceError):
        fetch(limit=100)


@pytest.mark.parametrize("size", [0, "0"])
def test_size_zero_nonempty_record_is_a_conflict_before_limit(monkeypatch, size):
    transport(monkeypatch, [{"status": True, "dto": {"size": size, "record": [row()]}}])
    with pytest.raises(SourceError, match="冲突"):
        fetch(limit=1)


@pytest.mark.parametrize("terminal", [
    {"status": True, "dto": {}}, {"status": True, "dto": {"record": None}},
    {"status": True, "dto": {"size": 1}}, {"status": True, "dto": {"size": "1", "record": None}},
    {"status": False, "dto": {"size": 0}}, {"status": "false", "dto": {"size": "0"}},
    {"dto": {"size": 0}}, {"status": None, "dto": {"size": 0}},
    {"status": "success", "dto": {"size": "0"}},
    {"status": True, "code": 403, "dto": {"size": "0"}},
    {"status": True, "dto": {"size": 0, "success": False}},
    {"status": True, "dto": {"size": 0, "code": 401}},
    {"status": True, "dto": None},
])
def test_unknown_or_failed_terminal_never_returns_prior_partial(monkeypatch, terminal):
    calls = transport(monkeypatch, [payload([row("101", "531599923")]), terminal])
    with pytest.raises(SourceError):
        fetch(limit=100, since="20260930", until="20261009")
    assert feed_cursors(calls) == ["0", "531599923"]
    assert all(url.startswith(forum._FEED) for url, _ in calls)


@pytest.mark.parametrize("size", [1, "1", 99999, "99999"])
def test_positive_size_is_not_guessed_as_page_length_or_full_count(monkeypatch, size):
    transport(monkeypatch, [{"status": True, "dto": {"size": size, "record": [row()]}}])
    assert fetch(limit=1)[0]["content"] == "全文101"


# 以下重复容器与异常边界均用合成正文；sid=test 不是有效认证。
def full_reply_ids(calls):
    return [parse_qs(urlsplit(url).query)["replyID"][0]
            for url, _ in calls if url.startswith(forum._FULL)]


def test_observed_double_container_structure_with_synthetic_business_body(monkeypatch):
    # 真实故障结构有reply_13186975_1与reply_13186975_16，内层同一reply103631002；
    # 正文和图片明确合成，未把去正文结构证据称为真实全文fixture。
    def observed_container(position):
        return (f'<div class="comment-data user_13186975" id="reply_13186975_{position}">'
                '<div class="comment-data-text" id="reply103631002">合成完整正文'
                '<img src="https://image.tgb.cn/synthetic-a.jpg">'
                '<img src="https://image.tgb.cn/synthetic-b.jpg"></div>'
                '<a data-reply-id="103631002"></a>'
                '<a data-topic-id="8805325" data-reply-id="103631002"></a>'
                '<a data-reply-id="103631002"></a><a data-reply-id="103631002"></a>'
                '<a class="topic_jb" data-topic-id="8805325" data-reply-id="103631002"></a></div>')
    markup = '<script>var topicTopicID2=8805325;</script>' + observed_container(1) + observed_container(16)
    second = comment("103631003", "合成另一正文").replace('data-topic-id="900"', 'data-topic-id="8805325"')
    markup += second
    records = [row("103631002", objectID="8805325", newTopicID="2vPJ8gIXa63"),
               row("103631003", "2", objectID="8805325", newTopicID="2vPJ8gIXa63")]
    calls = transport(monkeypatch, [payload(records), payload([])], pages={"/a/2vPJ8gIXa63": markup})
    result = fetch(limit=None)
    assert [item["reply_id"] for item in result] == ["103631002", "103631003"]
    assert result[0]["content"] == "合成完整正文"
    assert result[0]["image_urls"] == ["https://image.tgb.cn/synthetic-a.jpg", "https://image.tgb.cn/synthetic-b.jpg"]
    assert len(calls) == 3 and full_reply_ids(calls) == []


@pytest.mark.parametrize("duplicate", ["parent", "target", "both"])
def test_equivalent_target_or_necessary_parent_duplicates_merge_without_requests(monkeypatch, duplicate):
    parent = comment("101", "父全文")
    target = comment("102", "目标全文", "101")
    markup = page(parent, target, parent if duplicate in ("parent", "both") else "",
                  target if duplicate in ("target", "both") else "")
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    result = fetch(limit=1)[0]
    assert result["content"] == "目标全文" and result["parent_content"] == "父全文"
    assert len(calls) == 2 and full_reply_ids(calls) == []


@pytest.mark.parametrize("first,second", [
    ("冲突正文一", "冲突正文二"),
    ('摘要<a onclick="moreReplyContent()">展开</a>', "看似完整页面正文"),
    ("相同正文", '相同正文<a onclick="moreReplyContent()"></a>'),
    ('相同正文<img src="https://image.tgb.cn/a.jpg">', '相同正文<img src="https://image.tgb.cn/b.jpg">'),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_body_image_or_expand_state_requires_one_exact_full(monkeypatch, first, second, reverse):
    candidates = [comment("102", first, "101"), comment("102", second, "101")]
    if reverse:
        candidates.reverse()
    markup = page(comment("101", "父全文"), *candidates)
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])],
                      full={"102": {"status": True, "dto": '官方确定正文<img src="https://image.tgb.cn/exact.jpg">'}},
                      pages={"/a/abc123": markup})
    result = fetch(limit=1)[0]
    assert result["content"] == "官方确定正文"
    assert result["image_urls"] == ["https://image.tgb.cn/exact.jpg"]
    assert result["parent_content"] == "父全文"
    assert len(calls) == 3 and full_reply_ids(calls) == ["102"]
    assert all(urlsplit(url).hostname == "www.tgb.cn" for url, _ in calls)
    assert all(kwargs["follow_redirects"] is False and kwargs["headers"]["Cookie"] == "sid=test"
               for _, kwargs in calls)
    assert "sid=test" not in json.dumps(result)


def test_conflicting_necessary_parent_body_uses_exact_full_once_for_shared_quotes(monkeypatch):
    markup = page(comment("101", "父正文一"), comment("101", "父正文二"),
                  comment("102", "回复二", "101"), comment("103", "回复三", "101"))
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要"), row("103", "2", quoteContent="摘要")])],
                      pages={"/a/abc123": markup})
    result = fetch(limit=2)
    assert [item["parent_content"] for item in result] == ["全文101", "全文101"]
    assert full_reply_ids(calls) == ["101"]


@pytest.mark.parametrize("conflict", [
    comment("102", "相同正文", "103"),
    comment("102", "相同正文"),
    comment("102", "相同正文", "101").replace('data-topic-id="900"', 'data-topic-id="901"'),
    comment("102", "相同正文", "101").replace('data-quote-id="101"', 'data-quote-id="101" onclick="moreQuoteContent(this,901,101)"'),
])
def test_duplicate_reference_or_topic_conflict_never_discards_quote(monkeypatch, conflict):
    markup = page(comment("102", "相同正文", "101"), conflict)
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=1)
    assert full_reply_ids(calls) == []


@pytest.mark.parametrize("needed", ["target", "parent"])
@pytest.mark.parametrize("control", [
    '<a data-topic-id="901" data-reply-id="102"></a>',
    '<a data-topic-id="900" data-reply-id="104"></a>',
])
def test_additional_conflicting_controls_reject_needed_candidate(monkeypatch, needed, control):
    identity = "102" if needed == "target" else "101"
    bad = comment(identity, "页面全文", "101" if needed == "target" else None)
    bad = bad.replace('</div><a data-topic', '</div>' + control.replace('reply-id="102"', f'reply-id="{identity}"') + '<a data-topic')
    markup = page(bad, comment("102", "目标全文", "101") if needed == "parent" else "")
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError, match="冲突"):
        fetch(limit=1)
    assert full_reply_ids(calls) == []


@pytest.mark.parametrize("bad", [
    '<div class="comment-data-text" id="reply104">缺容器</div>',
    comment("104", "无关正文", "101").replace('data-quote-id="101"', 'data-quote-id="bad"'),
    comment("104", "无关正文", "101") + comment("104", "无关正文", "103"),
    comment("104", "无关正文").replace('data-topic-id="900"', 'data-topic-id="901"'),
])
def test_confirmed_unrelated_candidate_damage_is_local(monkeypatch, bad):
    markup = page(bad, comment("101", "父全文"), comment("102", "目标全文", "101"))
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    result = fetch(limit=1)[0]
    assert result["content"] == "目标全文" and result["parent_content"] == "父全文"
    assert len(calls) == 2


@pytest.mark.parametrize("identity", ["101", "102"])
@pytest.mark.parametrize("bad", [
    '<div class="comment-data-text" id="replyIDENTITY">缺容器</div>',
    comment("IDENTITY", "正文", "103").replace('data-quote-id="103"', 'data-quote-id="bad"'),
])
def test_required_target_or_parent_damage_cannot_be_treated_as_unrelated(monkeypatch, identity, bad):
    markup = page(bad.replace("IDENTITY", identity), comment("102", "目标全文", "101"))
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=1)
    assert full_reply_ids(calls) == []


@pytest.mark.parametrize("bad", [
    '<div class="comment-data-text">无身份候选</div>',
    '<div class="comment-data-text" id="replybad">坏身份候选</div>',
    comment("104", "无关候选").replace('data-reply-id="104"', 'data-reply-id="bad"'),
    comment("104", "无法证明无关").replace('data-reply-id="104"', 'data-reply-id="102"'),
])
def test_uncertain_candidate_relevance_cannot_be_silently_skipped(monkeypatch, bad):
    markup = page(bad, comment("101", "父全文"), comment("102", "目标全文", "101"))
    transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=1)


@pytest.mark.parametrize("same", [True, False])
def test_duplicate_complete_native_quote_without_parent_identity(monkeypatch, same):
    def native(body):
        return comment("102", "当前全文", "101").replace(
            '<p class="quote-content">引用摘要</p><a data-quote-id="101">展开</a>',
            f'<p class="quote-content data-quote-text">{body}</p>')
    markup = page(native("完整短引用"), native("完整短引用" if same else "冲突短引用"))
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    if same:
        result = fetch(limit=1)[0]
        assert result["parent_reply_id"] is None and result["parent_content"] == "完整短引用"
        assert len(calls) == 2
    else:
        with pytest.raises(SourceError, match="冲突"):
            fetch(limit=1)
    assert full_reply_ids(calls) == []


def test_exact_reply_page_merge_retains_parent_conflict_and_requires_one_full(monkeypatch):
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])],
                      pages={"/a/abc123": page(comment("101", "父正文一")),
                             "/a/abc123/102": page(comment("101", "父正文二"), comment("102", "目标全文", "101"))})
    result = fetch(limit=1)[0]
    assert result["parent_content"] == "全文101" and result["content"] == "目标全文"
    assert full_reply_ids(calls) == ["101"] and len(calls) == 4


def test_conflicting_full_failure_after_valid_row_never_returns_partial(monkeypatch):
    markup = page(comment("101", "有效第一回复"), comment("102", "冲突一"), comment("102", "冲突二"))
    calls = transport(monkeypatch, [payload([row(), row("102", "2")]), payload([])],
                      full={"102": {"status": False}}, pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=None)
    assert full_reply_ids(calls) == ["102"]


def test_global_topic_conflict_still_rejects_even_with_unrelated_bad_candidate(monkeypatch):
    markup = page('<div class="comment-data-text" id="reply104">无关坏候选</div>').replace('topicTopicID2=900', 'topicTopicID2=901')
    transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError, match="主题页面身份"):
        fetch(limit=1)


@pytest.mark.parametrize("identity", ["101", "102"])
def test_malformed_explicit_quote_callback_cannot_be_hidden_by_valid_data_id(monkeypatch, identity):
    bad = comment(identity, "页面正文", "103").replace(
        'data-quote-id="103"', 'data-quote-id="103" onclick="moreQuoteContent(this,900,unknown)"')
    markup = page(bad, comment("102", "目标全文", "101") if identity == "101" else "")
    transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError, match="引用展开控件"):
        fetch(limit=1)


def test_later_equivalent_duplicate_cannot_restore_conflicting_cached_body(monkeypatch):
    markup = page(comment("101", "第一正文"), comment("101", "冲突正文"), comment("101", "第一正文"),
                  comment("102", "目标全文", "101"))
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    assert fetch(limit=1)[0]["parent_content"] == "全文101"
    assert full_reply_ids(calls) == ["101"]


def test_leading_whitespace_expand_marker_requires_exact_full(monkeypatch):
    markup = page(comment("101", '摘要<a onclick="  moreReplyContent()">展开</a>'), comment("102", "回复二"))
    calls = transport(monkeypatch, [payload([row(), row("102", "2")])], pages={"/a/abc123": markup})
    assert fetch(limit=2)[0]["content"] == "全文101"
    assert full_reply_ids(calls) == ["101"]


def test_exact_full_with_whitespace_expand_marker_still_fails(monkeypatch):
    transport(monkeypatch, [payload([row()])], {"101": {"status": True, "dto": '<p>摘要</p><a onclick=" moreReplyContent()">展开</a>'}})
    with pytest.raises(SourceError, match="未展开正文"):
        fetch(limit=1)


@pytest.mark.parametrize("topic,quote", [("901", "101"), ("900", "bad")])
def test_static_dataset_quote_callback_requires_valid_exact_data_identity(monkeypatch, topic, quote):
    markup = page(comment("102", "当前全文", "101").replace(
        'data-quote-id="101"', f'data-topic-id="{topic}" data-quote-id="{quote}" onclick="moreQuoteContent(this,this.dataset.topicId,this.dataset.quoteId)"'))
    transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    with pytest.raises(SourceError):
        fetch(limit=1)


@pytest.mark.parametrize("identity,required", [("102", True), ("101", True), ("104", False)])
def test_explicit_quote_topic_is_checked_without_callback(monkeypatch, identity, required):
    bad = comment(identity, "候选正文", "103").replace(
        'data-quote-id="103"', 'data-topic-id="901" data-quote-id="103"')
    markup = page(bad, comment("102", "目标全文", "101") if identity != "102" else "",
                  comment("101", "父全文") if identity == "104" else "")
    calls = transport(monkeypatch, [payload([row("102", quoteContent="摘要")])], pages={"/a/abc123": markup})
    if required:
        with pytest.raises(SourceError, match="引用主题身份"):
            fetch(limit=1)
    else:
        result = fetch(limit=1)[0]
        assert result["content"] == "目标全文" and result["parent_content"] == "父全文"
    assert len(calls) == 2 and full_reply_ids(calls) == []
