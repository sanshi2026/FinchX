"""同花顺话题目录的完整分页、身份与七字段契约。"""

from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import SourceError
from finchx.sources.tonghuashun import topic_articles as source
from finchx.sources.tonghuashun._article_url import classify_article_url, encode_news_seq

TOPIC = "https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu"
FIELDS = {"url", "content_type", "title", "published_at", "source_name", "author", "summary"}


def test_saved_real_recommend_and_feed_preserve_directory_and_pid_mapping(monkeypatch):
    folder = Path(__file__).parent / "fixtures" / "articles_ths"
    pages = [json.loads((folder / name).read_text(encoding="utf-8")) for name in ["topic_recommend.json", "topic_feed.json"]]
    calls = install_pages(monkeypatch, pages)
    rows = source.ths_list(TOPIC, 5, timeout=1)
    assert len(rows) == 5
    assert all(set(row) == FIELDS for row in rows)
    assert rows[0]["url"] == "https://news.10jqka.com.cn/mobile/news/article/v1/encoded/a0e38678246048836a5"
    assert rows[1]["url"] == "https://t.10jqka.com.cn/pid_700648219.shtml"
    assert rows[1]["author"] == "每经ETF风向标"
    assert rows[4]["url"] == "https://t.10jqka.com.cn/pid_701155659.shtml"
    assert [call[0]["queryType"] for call in calls] == [["recommend"], ["feed"]]


def topic_news(identity="680459704", title="来源新闻", **info):
    return {"info": {"id": identity, "type": 8, "subject": "news", "like_key": f"seq_{identity}",
                     "jump_url": "https://news.10jqka.com.cn/mobile/news/article/v1/encoded/" + encode_news_seq(identity),
                     "time": 1791426060000, "unique": f"{identity}_8", **info},
            "title": {"content": title}, "news": {"source": "来源财闻", "content": "原始摘要"}}


def topic_article(identity="700648219", title="来源长文", **info):
    return {"info": {"id": identity, "type": 2, "subject": "snslivepost", "like_key": f"sns_post_{identity}",
                     "jump_url": "https://mp.10jqka.com.cn/lgt/article_detail/index.html?contentId=opaque123",
                     "time": 1791426938000, "unique": f"{identity}_2", **info},
            "title": {"content": title}, "author": {"name": "发布账号"},
            "abstract": {"content": "摘要第一行<br>第二行"}}


def topic_discussion(identity="2410013808"):
    return {"info": {"id": identity, "type": 1, "subject": "state", "like_key": f"group_post_{identity}"}}


def topic_view(identity="701123319"):
    row = topic_article(identity)
    row["info"].update(type=3, subject="snsview", unique=f"{identity}_3",
        jump_url="https://t.10jqka.com.cn/lgt/short_view/index.html?contentId=opaque123")
    row.pop("title")
    return row


def topic_page(rows, more=False, segment="recommend"):
    return {"status_code": 0, "data": {f"list_{segment}": rows, "has_next": more}}


def install_pages(monkeypatch, pages):
    calls = []
    iterator = iter(pages)

    def get(url, **kwargs):
        calls.append((parse_qs(urlsplit(url).query), kwargs))
        return deepcopy(next(iterator))

    monkeypatch.setattr(source, "get_json", get)
    return calls


def test_news_and_long_article_contract_and_recommend_to_feed(monkeypatch):
    calls = install_pages(monkeypatch, [topic_page([topic_news(), topic_discussion()]),
        topic_page([topic_article()], segment="feed")])
    rows = source.ths_list(TOPIC, timeout=2.5)
    assert len(rows) == 2
    assert all(set(row) == FIELDS for row in rows)
    assert rows[0] == {"url": topic_news()["info"]["jump_url"], "content_type": "news", "title": "来源新闻",
        "published_at": "2026-10-08T10:21:00+08:00", "source_name": "财闻", "author": None, "summary": "原始摘要"}
    assert rows[1] == {"url": "https://t.10jqka.com.cn/pid_700648219.shtml", "content_type": "article",
        "title": "来源长文", "published_at": "2026-10-08T10:35:38+08:00", "source_name": None,
        "author": "发布账号", "summary": "摘要第一行\n第二行"}
    assert [call[0]["queryType"] for call in calls] == [["recommend"], ["feed"]]
    assert all(call[1]["timeout"] == 2.5 for call in calls)


def test_full_page_validated_before_limit(monkeypatch):
    install_pages(monkeypatch, [topic_page([topic_news(), {"info": {"type": 18}}])])
    with pytest.raises(SourceError):
        source.ths_list(TOPIC, 1, timeout=1)


def test_real_snsview_is_article_with_missing_title_not_excluded_discussion(monkeypatch):
    path = Path(__file__).parent / "fixtures" / "articles_ths" / "topic_snsview_feed.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    install_pages(monkeypatch, [topic_page([]), payload])
    rows = source.ths_list(TOPIC, 1, timeout=1)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == FIELDS
    assert row["url"] == "https://t.10jqka.com.cn/lgt/short_view/index.html?pid=701123319"
    kind, canonical, identity, _ = classify_article_url(row["url"])
    assert (kind, canonical, identity) == ("article_short", row["url"], "701123319")
    assert row["content_type"] == "article"
    assert row["title"] is None
    assert row["source_name"] is None
    assert row["author"] == "大同证券徐强"
    assert row["published_at"] == "2026-10-08T21:39:01+08:00"
    assert row["summary"].startswith("$上海洗霸(603200)两个交易日累计涨超25%")


def test_same_sns_post_long_and_view_in_one_page_is_duplicate_business_identity(monkeypatch):
    install_pages(monkeypatch, [topic_page([topic_article("701123319"), topic_view()])])
    with pytest.raises(SourceError, match="身份重复"):
        source.ths_list(TOPIC, 1, timeout=1)


def test_cross_page_sns_post_type_change_updates_one_business_row_at_first_position(monkeypatch):
    install_pages(monkeypatch, [topic_page([topic_article("701123319")], True),
        topic_page([topic_view(), topic_news()])])
    rows = source.ths_list(TOPIC, 2, timeout=1)
    assert len(rows) == 2
    assert rows[0]["url"] == "https://t.10jqka.com.cn/lgt/short_view/index.html?pid=701123319"
    assert rows[0]["title"] is None
    assert rows[1]["content_type"] == "news"


@pytest.mark.parametrize("field,value", [("subject", "state"), ("subject", "snslivepost"),
    ("like_key", "group_post_701123319"), ("like_key", "sns_post_701123320"),
    ("unique", "701123319_2"), ("type", "3")])
def test_snsview_corrupt_type_subject_or_identity_still_fails_full_batch(monkeypatch, field, value):
    row = topic_view()
    row["info"][field] = value
    install_pages(monkeypatch, [topic_page([topic_news(), row])])
    with pytest.raises(SourceError):
        source.ths_list(TOPIC, 1, timeout=1)


def test_cross_page_updates_real_row_at_first_position(monkeypatch):
    calls = install_pages(monkeypatch, [topic_page([topic_news()], more=True),
        topic_page([topic_news(title="更新标题"), topic_article()], more=False)])
    rows = source.ths_list(TOPIC, 2, timeout=1)
    assert [row["title"] for row in rows] == ["更新标题", "来源长文"]
    assert [call[0]["page"] for call in calls] == [["1"], ["2"]]


def test_discussions_consume_real_pages_without_counting_towards_limit(monkeypatch):
    calls = install_pages(monkeypatch, [topic_page([topic_discussion()]),
        topic_page([topic_discussion("2410013809")], True, "feed"),
        topic_page([topic_news(), topic_article()], False, "feed")])
    rows = source.ths_list(TOPIC, 2, timeout=1)
    assert len(rows) == 2
    assert [call[0]["page"] for call in calls] == [["1"], ["1"], ["2"]]


def test_success_exhaustion_can_omit_empty_array(monkeypatch):
    install_pages(monkeypatch, [topic_page([topic_news()]), {"status_code": 0, "data": {"has_next": False}}])
    assert len(source.ths_list(TOPIC, 20, timeout=1)) == 1


def test_unknown_type_not_silently_skipped(monkeypatch):
    install_pages(monkeypatch, [topic_page([{"info": {"id": "680459704", "type": 18}}])])
    with pytest.raises(SourceError, match="type=18"):
        source.ths_list(TOPIC, timeout=1)


@pytest.mark.parametrize("field,value", [("subject", "snsview"), ("like_key", "sns_post_2410013808")])
def test_excluded_discussion_must_have_verified_subject_and_group_post_identity(monkeypatch, field, value):
    row = topic_discussion()
    row["info"][field] = value
    install_pages(monkeypatch, [topic_page([row])])
    with pytest.raises(SourceError, match="讨论类型"):
        source.ths_list(TOPIC, timeout=1)


def test_non_integer_type_is_distinct_damage_without_echoing_source_content(monkeypatch):
    install_pages(monkeypatch, [topic_page([{"info": {"type": {"private": "不输出原数据"}}}])])
    with pytest.raises(SourceError, match="必须是来源整数") as error:
        source.ths_list(TOPIC, timeout=1)
    assert "不输出原数据" not in str(error.value)


@pytest.mark.parametrize("rows", [[topic_news(), topic_news()], [topic_discussion(), topic_discussion()]])
def test_same_page_duplicates_fail_including_excluded_discussions(monkeypatch, rows):
    install_pages(monkeypatch, [topic_page(rows)])
    with pytest.raises(SourceError):
        source.ths_list(TOPIC, timeout=1)


@pytest.mark.parametrize("payload", [None, [], {}, {"status_code": True}, {"status_code": 1},
    {"status_code": 0, "data": []}, {"status_code": 0, "data": {"has_next": 0, "list_recommend": []}},
    {"status_code": 0, "data": {"has_next": True}},
    {"status_code": 0, "data": {"has_next": False, "list_recommend": None}},
    topic_page([None]), topic_page([{}])])
def test_bad_status_or_structure_fails(monkeypatch, payload):
    install_pages(monkeypatch, [payload])
    with pytest.raises(SourceError):
        source.ths_list(TOPIC, timeout=1)


@pytest.mark.parametrize("field,value", [("id", "６８０４５９７０４"), ("id", 680459704), ("id", ""),
    ("type", True), ("subject", "snslivepost"), ("like_key", "seq_123456"), ("unique", "123456_8"),
    ("time", True), ("time", 1.5), ("time", "NaN"), ("time", -1), ("time", 10**99),
    ("jump_url", "https://example.com/680459704"),
    ("jump_url", "https://news.10jqka.com.cn/mobile/news/article/v1/encoded/" + encode_news_seq("680459705"))])
def test_bad_known_news_identity_or_time_fails(monkeypatch, field, value):
    row = topic_news()
    row["info"][field] = value
    install_pages(monkeypatch, [topic_page([row])])
    with pytest.raises(SourceError):
        source.ths_list(TOPIC, 1, timeout=1)


@pytest.mark.parametrize("change", [lambda r: r["info"].pop("subject"), lambda r: r["info"].pop("like_key"),
    lambda r: r["info"].update(like_key="sns_post_700648220"),
    lambda r: r.update(title=[]), lambda r: r.update(author=True), lambda r: r.update(abstract=[]),
    lambda r: r["abstract"].update(content=0), lambda r: r["title"].update(content=False)])
def test_bad_long_article_required_identity_and_optional_types_fail(monkeypatch, change):
    row = topic_article()
    change(row)
    install_pages(monkeypatch, [topic_page([row])])
    with pytest.raises(SourceError):
        source.ths_list(TOPIC, 1, timeout=1)


def test_optional_missing_and_valid_epoch_zero_are_not_fabricated(monkeypatch):
    row = topic_article(time=0)
    row.pop("title")
    row.pop("author")
    row.pop("abstract")
    install_pages(monkeypatch, [topic_page([row])])
    result = source.ths_list(TOPIC, 1, timeout=1)[0]
    assert result["title"] is result["author"] is result["summary"] is result["source_name"] is None
    assert result["published_at"] == "1970-01-01T08:00:00+08:00"


def test_millisecond_time_precision_is_preserved(monkeypatch):
    install_pages(monkeypatch, [topic_page([topic_article(time=1791426938123)])])
    assert source.ths_list(TOPIC, 1, timeout=1)[0]["published_at"].endswith("10:35:38.123+08:00")


def test_missing_time_returns_none_without_clock_or_news_time(monkeypatch):
    row = topic_news()
    row["info"].pop("time")
    row["news"]["time"] = 1791426060000
    install_pages(monkeypatch, [topic_page([row])])
    assert source.ths_list(TOPIC, 1, timeout=1)[0]["published_at"] is None


def test_stalled_source_is_error_not_partial(monkeypatch):
    install_pages(monkeypatch, [topic_page([topic_news()], True)] * 4)
    with pytest.raises(SourceError, match="无进展"):
        source.ths_list(TOPIC, 20, timeout=1)


def test_discussion_only_progress_reaches_budget_not_fake_exhaustion(monkeypatch):
    monkeypatch.setattr(source, "_MAX_PAGES", 2)
    install_pages(monkeypatch, [topic_page([topic_discussion()], True),
        topic_page([topic_discussion("2410013809")], True)])
    with pytest.raises(SourceError, match="防护预算"):
        source.ths_list(TOPIC, timeout=1)


@pytest.mark.parametrize("url", [None, 885976, "885976", "Tv47iqu", "https://example.com/m/topic/index.html?code=Tv47iqu",
    "https://t.10jqka.com.cn/m/topic/index.html?code=885976", "https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu&code=Tv47iqu",
    TOPIC + " ", TOPIC + "\x7f", TOPIC.replace("https://", "https://u:p@"),
    TOPIC.replace(".cn/", ".cn:444/"), TOPIC.replace("Tv47iqu", "T１２３"),
    TOPIC.replace("Tv47iqu", "T12345"), TOPIC.replace("Tv47iqu", "T1234567"),
    "https://news.10jqka.com.cn/deep-topic/topic/dt_01M3QZJ7BMT2BRZXP301DK9A1H"])
def test_invalid_topic_input_rejected_before_request(monkeypatch, url):
    monkeypatch.setattr(source, "get_json", lambda *a, **k: pytest.fail("不能访问来源"))
    with pytest.raises(ValueError):
        source.ths_list(url, timeout=1)


@pytest.mark.parametrize("limit", [True, False, 0, -1, None, 1.5, "2"])
def test_bad_limit_is_rejected_before_request(monkeypatch, limit):
    monkeypatch.setattr(source, "get_json", lambda *a, **k: pytest.fail("不能访问来源"))
    with pytest.raises(ValueError):
        source.ths_list(TOPIC, limit, timeout=1)


def test_desktop_topic_route(monkeypatch):
    install_pages(monkeypatch, [topic_page([topic_news()])])
    assert len(source.ths_list(TOPIC.replace("/m/topic/", "/lgt/main/frontend-main-service/topic/"), 1, timeout=1)) == 1


@pytest.mark.parametrize("url", [TOPIC + "#x", TOPIC + "&track=1", TOPIC.replace(".cn/", ".cn:443/"),
    TOPIC.replace("https://", "http://").replace(".cn/", ".cn:80/")])
def test_verified_equivalent_topic_url_tracking_anchor_and_default_port(monkeypatch, url):
    calls = install_pages(monkeypatch, [topic_page([topic_news()])])
    assert len(source.ths_list(url, 1, timeout=1)) == 1
    assert calls[0][0]["code"] == ["Tv47iqu"]
