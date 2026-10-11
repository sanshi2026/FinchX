"""热门话题/文章的真实来源字段与完整批次、窗口失败语义。"""

from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.tonghuashun import hot_content as source

FIXTURES = Path(__file__).parent / "fixtures" / "articles_ths"
TOPIC_FIELDS = {"rank", "title", "summary", "subtitle", "heat", "url", "target_type", "related_securities"}
ARTICLE_FIELDS = {"rank", "title", "heat", "tag", "url", "related_entities"}


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def topic(code="Tv47iqu", **changes):
    row = deepcopy(load("hot_topics.json")["data"]["topic_list"][0])
    row.update(code=code, jump_url=f"//t.10jqka.com.cn/m/topic/index.html?code={code}")
    row.update(changes)
    return row


def page(*rows):
    return {"status_code": 0, "data": {"topic_list": list(rows)}}


def article_payload(*rows):
    return {"status_code": "0", "answer": {"components": [{"data": {
        "datas": list(rows), "meta": {"total": len(rows), "extra": {"status_code": 0}},
    }}]}}


def article(identity="680496918", rank=1, **changes):
    row = deepcopy(load("hot_articles.json")["answer"]["components"][0]["data"]["datas"][-1])
    row.update(newsId=identity, rank=rank, contentUrl=[f"https://stock.10jqka.com.cn/20261009/c{identity}.shtml"])
    row.update(changes)
    return row


def responses(monkeypatch, values):
    calls = []
    iterator = iter(values)
    def fetch(url, **kwargs):
        calls.append((url, kwargs))
        return next(iterator)
    monkeypatch.setattr(source, "get_json", fetch)
    return calls


def test_real_topics_and_genuine_empty_confirm_exhaustion(monkeypatch):
    calls = responses(monkeypatch, [load("hot_topics.json"), load("hot_topics_empty.json")])
    result = source.hot_content(timeout=7)
    assert len(result) == 15
    assert all(set(row) == TOPIC_FIELDS for row in result)
    assert result[0]["title"] == "固态电池板块再度走强"
    assert result[0]["heat"] == 901231
    assert result[0]["related_securities"] == [{"code": "002074", "exchange": "sz", "name": "国轩高科", "change_percent": None}]
    assert result[0]["url"].startswith("https://")
    deep = next(row for row in result if row["target_type"] == "content")
    assert "/deep-topic/topic/dt_" in deep["url"]
    assert deep["related_securities"] is None
    assert result[-1]["subtitle"] == "金豆奖励+专属勋章等你来拿！"
    assert [parse_qs(urlsplit(url).query) for url, _ in calls] == [
        {"page": ["1"], "page_size": ["30"]}, {"page": ["2"], "page_size": ["30"]}]
    assert all(kwargs["timeout"] == 7 for _, kwargs in calls)


def test_short_topic_pages_continue_and_later_overlap_updates_whole_row(monkeypatch):
    first = topic(hot_value=9)
    second = topic(title="后读标题", description=None, hot_value=0, attach_info={"att_stock": []})
    calls = responses(monkeypatch, [page(first), page(second, topic("Tabc123", title="新话题"))])
    result = source.hot_content(limit=2, timeout=3)
    assert len(calls) == 2
    assert [row["rank"] for row in result] == [1, 2]
    assert result[0]["title"] == "后读标题"
    assert result[0]["heat"] == 0
    assert result[0]["summary"] is None
    assert result[0]["related_securities"] == []


def test_source_empty_is_empty_list(monkeypatch):
    responses(monkeypatch, [page()])
    assert source.hot_content(timeout=3) == []


def test_topics_limit_cannot_hide_malformed_last_row(monkeypatch):
    responses(monkeypatch, [page(topic(), {"type": "topic", "code": "Tbad"})])
    with pytest.raises(SourceError):
        source.hot_content(limit=1, timeout=3)


@pytest.mark.parametrize("patch", [
    {"type": "unknown"}, {"code": "Tbad"}, {"hot_value": True}, {"hot_value": float("inf")},
    {"hot_value": -1}, {"title": []}, {"attach_info": []}, {"attach_info": {"att_stock": {}}},
    {"attach_info": {"att_stock": [{"code": "002074", "name": "国轩高科", "rise_and_fall": False}]}},
    {"jump_url": "https://t.10jqka.com.cn/m/topic/index.html?code=Tother1"},
    {"jump_url": "https://example.com/m/topic/index.html?code=Tv47iqu"},
    {"jump_url": "https://t.10jqka.com.cn/m/topic/index.html?code=Tv47iqu&code=Tv47iqu"},
])
def test_invalid_topic_business_row_fails(monkeypatch, patch):
    responses(monkeypatch, [page(topic(**patch))])
    with pytest.raises(SourceError):
        source.hot_content(limit=1, timeout=3)


@pytest.mark.parametrize("payload", [
    None, {}, {"status_code": True, "data": {"topic_list": []}},
    {"status_code": 1, "data": {"topic_list": []}}, {"status_code": 0},
    {"status_code": 0, "data": {"topic_list": None}},
])
def test_missing_or_failed_topic_structure_is_not_empty_success(monkeypatch, payload):
    responses(monkeypatch, [payload])
    with pytest.raises(SourceError):
        source.hot_content(timeout=3)


def test_duplicate_same_page_and_repeated_page_fail(monkeypatch):
    responses(monkeypatch, [page(topic(), topic())])
    with pytest.raises(SourceError, match="同页"):
        source.hot_content(timeout=3)
    responses(monkeypatch, [page(topic()), page(topic())])
    with pytest.raises(SourceError, match="重复整批"):
        source.hot_content(timeout=3)


def test_topic_budget_stop_is_error(monkeypatch):
    monkeypatch.setattr(source, "_MAX_PAGES", 1)
    responses(monkeypatch, [page(topic())])
    with pytest.raises(SourceError, match="预算"):
        source.hot_content(timeout=3)


def test_real_articles_entire_window_uses_source_rank_and_keeps_boards(monkeypatch):
    calls = responses(monkeypatch, [load("hot_articles.json")])
    result = source.hot_content("article", 101, timeout=5)
    assert len(result) == 100 and len(calls) == 1
    assert [row["rank"] for row in result] == list(range(1, 101))
    assert all(set(row) == ARTICLE_FIELDS for row in result)
    assert result[0]["title"] == "美股半导体、光通信板块，集体下跌"
    assert result[0]["url"].endswith("c680496918.shtml")
    assert result[0]["related_entities"][0] == {"code": "881129", "name": "通信设备", "market": "48", "change_percent": None}
    assert result[0]["related_entities"][2]["market"] == "49"
    assert result[3]["url"].endswith("pid_701153354.shtml")
    query = parse_qs(urlsplit(calls[0][0]).query)
    assert query == {"tag": ["同花顺热榜_新热文"], "appName": ["thsHotList"]}


@pytest.mark.parametrize("comment,likes,expected", [(30, 1, "评论火爆"), (0, 15, "点赞激增"), (31, 16, None), (0, 0, None), (-1, -1, None), (None, None, None)])
def test_tags_only_follow_official_display_rule_and_zero_survives(monkeypatch, comment, likes, expected):
    value = article(commentRatio=comment, zanRatio=likes, score=0, stockInfo=[
        {"stockCode": "HK0666", "stockName": "来源海外对象", "stockMarket": 177, "stockZdf": -2},
        {"stockCode": "885806", "stockName": "华为概念", "stockMarket": "48", "stockZdf": 0},
    ])
    responses(monkeypatch, [article_payload(value)])
    result = source.hot_content("article", timeout=3)[0]
    assert result["tag"] == expected and result["heat"] == 0
    assert result["related_entities"][0]["code"] == "HK0666"
    assert result["related_entities"][0]["change_percent"] == -2
    assert result["related_entities"][1]["change_percent"] == 0


@pytest.mark.parametrize("related", [None, []])
def test_article_relation_missing_and_explicit_empty_remain_distinct(monkeypatch, related):
    responses(monkeypatch, [article_payload(article(stockInfo=related, title=None, score=None))])
    result = source.hot_content("article", timeout=3)[0]
    assert result["related_entities"] == related
    assert result["title"] is None and result["heat"] is None


@pytest.mark.parametrize("patch", [
    {"newsId": "ABC"}, {"rank": 0}, {"rank": False}, {"rank": 1.5}, {"score": True},
    {"score": float("nan")}, {"commentRatio": []}, {"zanRatio": True}, {"newsType": "comment"},
    {"contentUrl": []}, {"contentUrl": ["https://stock.10jqka.com.cn/20261009/c111111111.shtml"]},
    {"contentUrl": ["https://t.10jqka.com.cn/pid_680496918.shtml"]},
    {"stockInfo": [{"stockCode": "600000", "stockName": "来源", "stockMarket": True}]},
    {"stockInfo": [{"stockCode": "600000", "stockName": "来源", "stockZdf": float("inf")}]},
])
def test_invalid_articles_even_beyond_limit_fail(monkeypatch, patch):
    broken = article("680496919", rank=2)
    broken.update(patch)
    responses(monkeypatch, [article_payload(article(), broken)])
    with pytest.raises(SourceError):
        source.hot_content("article", limit=1, timeout=3)


def test_article_duplicate_identity_rank_total_and_nested_status_fail(monkeypatch):
    samples = [article_payload(article(), article(rank=2)),
               article_payload(article(), article("680496919")),
               article_payload(article()), article_payload(article())]
    samples[2]["answer"]["components"][0]["data"]["meta"]["total"] = 2
    samples[3]["answer"]["components"][0]["data"]["meta"]["extra"]["status_code"] = 1
    for payload in samples:
        responses(monkeypatch, [payload])
        with pytest.raises(SourceError):
            source.hot_content("article", timeout=3)


@pytest.mark.parametrize("content_type", ["comment", "all", None, [], True])
def test_no_comment_or_unknown_type(monkeypatch, content_type):
    calls = responses(monkeypatch, [])
    with pytest.raises(ValueError):
        source.hot_content(content_type, timeout=3)
    assert calls == []


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "1", None])
def test_invalid_limit_before_network(monkeypatch, limit):
    calls = responses(monkeypatch, [])
    with pytest.raises(ValueError):
        source.hot_content(limit=limit, timeout=3)
    assert calls == []


@pytest.mark.parametrize("timeout", [0, True, float("inf"), "3"])
def test_invalid_timeout_before_network(monkeypatch, timeout):
    calls = responses(monkeypatch, [])
    with pytest.raises(ValueError):
        source.hot_content(timeout=timeout)
    assert calls == []
