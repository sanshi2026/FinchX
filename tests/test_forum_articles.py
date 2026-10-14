"""构造 R/T 混合动态回归；不代表联网认证成功样例。"""

import inspect
from urllib.parse import urlsplit

import pytest

from finchx import FinchX
from finchx._common.errors import SourceError
from finchx.sources.taoguba import forum
from test_forum_source import comment, feed_cursors, fetch, full_reply_ids, payload, row, transport


def article(action="1", topic="900", post="abc123", **extra):
    return row(**{**dict(action=action, actionName="T", otherID=0, objectID=topic,
                        newTopicID=post, objectName="正式标题"), **extra})


def article_page(body="正文第一段<br>正文第二段", title="正式标题", topic="900", author="88", replies=""):
    return (f'<script>var topicTopicID2={topic};var topicUserID={author};var topicUserID={author};</script>'
            f'<div id="stockTitle" class="article-tittle">\n {title}\n </div>'
            f'<div id="first" class="article-text p_coten">{body}</div>{replies}')


def page_paths(calls):
    return [urlsplit(url).path for url, _ in calls if not url.startswith((forum._FEED, forum._FULL))]


def test_article_real_shape_zero_other_id_and_fixed_contract(monkeypatch):
    calls = transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page()})
    result = fetch(limit=1)[0]
    assert list(result) == ["reply_id", "user_id", "username", "reply_time", "content", "image_urls",
                            "post_url", "url", "parent_reply_id", "parent_username", "parent_content", "parent_image_urls"]
    assert result == dict(reply_id="topic:900", user_id="88", username="作者", reply_time="2026-10-08T11:32:58+08:00",
                          content="正式标题\n\n正文第一段\n正文第二段", image_urls=[],
                          post_url="https://www.tgb.cn/a/abc123", url="https://www.tgb.cn/a/abc123",
                          parent_reply_id=None, parent_username=None, parent_content=None, parent_image_urls=None)
    assert not full_reply_ids(calls)
    assert page_paths(calls) == ["/a/abc123"]


def test_mixed_limit_source_order_and_numeric_namespace(monkeypatch):
    feeds = [payload([row("900", "1"), article("2"), row("102", "3")])]
    calls = transport(monkeypatch, feeds, pages={"/a/abc123": article_page(replies=comment("900", "页面回复"))})
    result = fetch(limit=2)
    assert [item["reply_id"] for item in result] == ["900", "topic:900"]
    # 单个 R 沿用精确全文路径，T 不把无关回复验证提升为批量必要校验。
    assert result[0]["content"] == "全文900"
    assert full_reply_ids(calls) == ["900"]
    assert page_paths(calls) == ["/a/abc123"]


def test_mixed_cross_page_overlap_updates_row_and_keeps_first_position(monkeypatch):
    feeds = [payload([article("831567993"), {"actionID": "831567978", "actionName": "W"}]),
             payload([row("101", "831567950"), article("831567944", userName="后读作者", objectName="更新标题")]),
             payload([])]
    calls = transport(monkeypatch, feeds, pages={"/a/abc123": article_page(title="更新标题")})
    result = fetch(limit=None)
    assert [item["reply_id"] for item in result] == ["topic:900", "101"]
    assert result[0]["username"] == "后读作者" and result[0]["content"].startswith("更新标题\n\n")
    assert feed_cursors(calls) == ["0", "831567978", "831567944"]
    assert page_paths(calls) == ["/a/abc123"]


@pytest.mark.parametrize("bound", ["2026-10-08 11:32:58", "20261008 11:32:58", "2026/10/08 11:32:58"])
def test_article_inclusive_time_boundary_and_nonchronological_pages(monkeypatch, bound):
    feeds = [payload([article("1", actionDate="2026-10-07 23:59:59")]),
             payload([article("2")]), payload([])]
    calls = transport(monkeypatch, feeds, pages={"/a/abc123": article_page()})
    assert [item["reply_id"] for item in fetch(limit=None, since=bound, until=bound)] == ["topic:900"]
    assert feed_cursors(calls) == ["0", "1", "2"]


def test_excluded_articles_are_validated_but_do_not_fetch_fulltext(monkeypatch):
    calls = transport(monkeypatch, [payload([article(actionDate="2026-10-07 23:59:59"), row("101", "2")]), payload([])])
    assert [item["reply_id"] for item in fetch(since="2026-10-08")] == ["101"]
    assert not page_paths(calls)


@pytest.mark.parametrize("body, expected, images", [
    ('<p>正文</p><img data-original="//img.tgb.cn/a.jpg" src="/lazy.png"><img src="/b.jpg">',
     "正式标题\n\n正文", ["https://img.tgb.cn/a.jpg", "https://www.tgb.cn/b.jpg"]),
    ('<img data-original="/a.jpg" src="/lazy.png">', "正式标题", ["https://www.tgb.cn/a.jpg"]),
])
def test_article_full_body_images_and_pure_image(monkeypatch, body, expected, images):
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page(body)})
    result = fetch(limit=1)[0]
    assert result["content"] == expected and result["image_urls"] == images


@pytest.mark.parametrize("extra", [dict(objectID="bad"), dict(newTopicID="bad/path"),
                                    dict(userID=True), dict(objectName=123),
                                    dict(actionDate="2026-13-08 11:32:58"), dict(body=123)])
def test_article_damage_after_valid_reply_cannot_hide_behind_limit(monkeypatch, extra):
    calls = transport(monkeypatch, [payload([row(), article("2", **extra)])])
    with pytest.raises(SourceError):
        fetch(limit=1)
    assert len(calls) == 1


@pytest.mark.parametrize("html", ["<html>登录页</html>", article_page(topic="901"), article_page(author="99"),
                                   article_page(title=""), article_page(body=""),
                                   article_page(body="登录后查看全文"),
                                   article_page() + '<div id="first" class="article-text p_coten">歧义</div>',
                                   article_page() + '<script>var topicUserID=99;</script>',
                                   article_page(body='<img src="javascript:bad">')])
def test_necessary_article_page_failure_never_returns_partial(monkeypatch, html):
    calls = transport(monkeypatch, [payload([row(), article("2")])], pages={"/a/abc123": html})
    with pytest.raises(SourceError):
        fetch(limit=2)
    assert full_reply_ids(calls) == ["101"]
    assert page_paths(calls) == ["/a/abc123"]


def test_article_only_ignores_unrelated_bad_reply_candidates(monkeypatch):
    html = article_page(replies='<div class="comment-data-text">未知身份坏回复</div>')
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": html})
    assert fetch(limit=1)[0]["content"].startswith("正式标题\n\n")


def test_two_replies_and_article_share_one_page_and_parent_body(monkeypatch):
    html = article_page(replies=comment("101", "回复101", "102") + comment("102", "父回复102"))
    calls = transport(monkeypatch, [payload([article(), row("101", "2", quoteContent="摘要"), row("102", "3")])],
                      pages={"/a/abc123": html})
    result = fetch(limit=3)
    assert [item["reply_id"] for item in result] == ["topic:900", "101", "102"]
    assert result[1]["parent_reply_id"] == "102" and result[1]["parent_content"] == "父回复102"
    assert result[1]["content"] == "回复101" and result[2]["content"] == "父回复102"
    assert page_paths(calls) == ["/a/abc123"] and not full_reply_ids(calls)


def test_w_and_p_actions_remain_excluded(monkeypatch):
    calls = transport(monkeypatch, [payload([{"actionID": "1", "actionName": "W"},
                                             {"actionID": "2", "actionName": "P"}]), payload([])])
    assert fetch(limit=None) == [] and feed_cursors(calls) == ["0", "2"]


def test_public_signature_remains_unchanged():
    method = FinchX().forum.tgb_replies
    signature = inspect.signature(method)
    assert list(signature.parameters) == ["limit", "since", "until", "cookies"]
    assert signature.parameters["cookies"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["limit"].default == 20


@pytest.mark.parametrize("extra", [dict(userID=None), dict(objectName=None), dict(objectName="旧标题"),
                                    dict(userName=None, actionDate=None)])
def test_article_optional_metadata_does_not_override_formal_title(monkeypatch, extra):
    transport(monkeypatch, [payload([article(**extra)])], pages={"/a/abc123": article_page(title="当前正式标题")})
    result = fetch(limit=1)[0]
    assert result["content"].startswith("当前正式标题\n\n")
    if "userID" in extra:
        assert result["user_id"] is None
    if "userName" in extra:
        assert result["username"] is None and result["reply_time"] is None


def test_article_missing_page_optional_author_is_not_invented(monkeypatch):
    html = article_page().replace('var topicUserID=88;', '')
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": html})
    assert fetch(limit=1)[0]["user_id"] == "88"


def test_article_missing_time_cannot_be_filtered(monkeypatch):
    calls = transport(monkeypatch, [payload([article(actionDate=None)])])
    with pytest.raises(SourceError):
        fetch(limit=1, since="2026-10-08")
    assert len(calls) == 1


def test_article_template_removal_preserves_user_hidden_and_div_content(monkeypatch):
    body = ('\n<span style="display:none; padding: 10px 0;">[淘股吧]</span>'
            '<div>正文段落</div><span style="display:none">用户隐藏正文</span>'
            '<div style="width: 100%;">用户普通div</div>'
            '<font>用户声明必须保留</font><div id="videoImg"> \n </div>'
            '<div style="width: 100%;"> \n </div><div class="clear"> \n </div>')
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page(body)})
    content = fetch(limit=1)[0]["content"]
    assert "[淘股吧]" not in content
    for text in ("正文段落", "用户隐藏正文", "用户普通div", "用户声明必须保留"):
        assert text in content


@pytest.mark.parametrize("body", ['<span style="display:none; padding: 10px 0;">用户隐藏文本</span>',
                                  '<p>用户正文</p><span style="display:none; padding: 10px 0;">[淘股吧]</span>'])
def test_article_source_marker_requires_exact_signature_and_position(monkeypatch, body):
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page(body)})
    result = fetch(limit=1)[0]
    assert ("用户隐藏文本" if "用户隐藏文本" in body else "[淘股吧]") in result["content"]


@pytest.mark.parametrize("body", ['<span style="display:none; padding: 10px 0;">[淘股吧]</span>',
                                  '<div id="videoImg">未核正文</div>',
                                  '<img src="https://css.tgb.cn/images/2022/newpc/placeHolder.png">'])
def test_article_auxiliary_marker_or_placeholder_cannot_be_body(monkeypatch, body):
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page(body)})
    with pytest.raises(SourceError):
        fetch(limit=1)


def test_article_real_image_is_preferred_over_exact_official_placeholder(monkeypatch):
    body = '<img src="https://css.tgb.cn/images/2022/newpc/placeHolder.png" data-original="//img.tgb.cn/real.jpg">'
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page(body)})
    assert fetch(limit=1)[0]["image_urls"] == ["https://img.tgb.cn/real.jpg"]


def test_article_known_source_identity_mapping_conflict_rejected_before_details(monkeypatch):
    calls = transport(monkeypatch, [payload([article(), article("2", post="other123")])])
    with pytest.raises(SourceError):
        fetch(limit=1)
    assert len(calls) == 1


def test_article_user_discussion_of_login_is_valid_body(monkeypatch):
    body = '<p>用户讨论页面提示“登录后查看全文”，这是正文而非登录限制。</p>'
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page(body)})
    assert '用户讨论页面提示“登录后查看全文”' in fetch(limit=1)[0]["content"]


@pytest.mark.parametrize("script", ['var topicTopicID2="bad";', 'var topicTopicID2=0;', 'var topicUserID=true;',
                                    'var topicTopicID2=;', 'var topicTopicID2="bad"'])
def test_article_invalid_duplicate_page_identity_cannot_hide_behind_valid_id(monkeypatch, script):
    transport(monkeypatch, [payload([article()])], pages={"/a/abc123": article_page() + f'<script>{script}</script>'})
    with pytest.raises(SourceError):
        fetch(limit=1)
