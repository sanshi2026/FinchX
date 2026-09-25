"""Offline contract and routing tests for Tonghuashun topic news discovery."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import FinchX
from finchx.collectors import CachePolicy, Collector
from finchx.contracts import Source
from finchx.datasets import (
    ARTICLE_TOPIC_DATASET,
    ArticleDetailRequest,
    TopicArticlesRequest,
    UnsupportedTopicURL,
    classify_topic_url,
)
from finchx.datasets.topic_articles import normalize_topic_articles
from finchx.providers import (
    ProviderRegistry,
    PROVIDER_REGISTRY,
    THSTopicArticlesProvider,
    encode_news_seq,
)
from finchx.storage import Cache, MemoryStorage


CAPTURED_AT = datetime(2026, 9, 24, 4, 0, tzinfo=timezone.utc)
T_TOPIC_URL = "https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=T4dryo6"
T_TOPIC_MOBILE_URL = "https://t.10jqka.com.cn/m/topic/index.html?code=T4dryo6"
DEEP_TOPIC_URL = "https://news.10jqka.com.cn/deep-topic/topic/dt_01M38FJCPYEXWZ9Q34YN8DXJ9N"


class FakeResponse(BytesIO):
    status = 200

    def getcode(self) -> int:
        return 200


def _feed_item(content_id: str, *, item_type: int = 8, title: str | None = None, time_ms: int = 1790211580000):
    encoded = encode_news_seq(content_id) if content_id.isdigit() else "bad"
    return {
        "info": {
            "id": content_id,
            "type": item_type,
            "time": time_ms,
            "jump_url": f"https://news.10jqka.com.cn/mobile/news/article/v1/encoded/{encoded}",
        },
        "title": {"content": title or f"新闻 {content_id}"},
        "news": {"source": "来源上海证券报·中国证券网", "time": time_ms},
    }


def _payload(rows: list[dict[str, object]], *, key: str, has_next: bool) -> bytes:
    return json.dumps(
        {"status_code": 0, "status_msg": "success", "data": {key: rows, "has_next": has_next}},
        ensure_ascii=False,
    ).encode("utf-8")


class FixtureOpener:
    def __init__(self, pages: dict[tuple[str, int], tuple[list[dict[str, object]], bool]]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        parsed = urlsplit(request.full_url)
        query = parse_qs(parsed.query)
        query_type = query.get("queryType", [""])[0]
        page = int(query.get("page", ["1"])[0])
        rows, has_next = self.pages[(query_type, page)]
        key = "list_recommend" if query_type == "recommend" else "list_feed"
        return FakeResponse(_payload(rows, key=key, has_next=has_next))


def _provider(opener: FixtureOpener) -> THSTopicArticlesProvider:
    return THSTopicArticlesProvider(opener, clock=lambda: CAPTURED_AT)


def _base_pages() -> dict[tuple[str, int], tuple[list[dict[str, object]], bool]]:
    first_id = "680237611"
    second_id = "680237612"
    third_id = "680237613"
    return {
        ("recommend", 1): (
            [
                _feed_item(first_id, title="美债再遭抛售 美联储官员持续释放偏鹰信号"),
                _feed_item("2407591527", item_type=1),
                _feed_item("698394446", item_type=2),
            ],
            False,
        ),
        ("feed", 1): (
            [
                _feed_item(first_id, title="duplicate"),
                _feed_item("698400000", item_type=18),
                _feed_item(second_id, time_ms=1790212180000),
            ],
            True,
        ),
        ("feed", 2): (
            [
                _feed_item("698348634", item_type=2, title="长文条目", time_ms=1790212780000),
                _feed_item(third_id, time_ms=1790212780000),
            ],
            False,
        ),
    }


def test_topic_urls_are_strictly_classified_and_normalized_to_code_identity():
    assert classify_topic_url(T_TOPIC_URL) == ("t_code", "T4dryo6")
    assert classify_topic_url(T_TOPIC_MOBILE_URL) == ("t_code", "T4dryo6")
    assert classify_topic_url(DEEP_TOPIC_URL) == (
        "deep_topic",
        "dt_01M38FJCPYEXWZ9Q34YN8DXJ9N",
    )

    for url in (
        "http://t.10jqka.com.cn/m/topic/index.html?code=T4dryo6",
        "https://evil.example/m/topic/index.html?code=T4dryo6",
        "https://t.10jqka.com.cn/other?code=T4dryo6",
        "https://t.10jqka.com.cn/m/topic/index.html?code=T4dryo6&code=Tkojw02",
        "https://t.10jqka.com.cn/m/topic/index.html?code=javascript%3Aalert(1)",
        "https://t.10jqka.com.cn:444/m/topic/index.html?code=T4dryo6",
    ):
        with pytest.raises(ValueError):
            classify_topic_url(url)


def test_topic_request_is_code_keyed_and_recommend_is_the_only_supported_sort():
    request = TopicArticlesRequest(topicCode="T4dryo6", limit=3)
    assert request.topic_code == "T4dryo6"
    assert request.sort == "recommend"
    assert request.limit == 3
    for invalid in (0, 101, True):
        with pytest.raises(ValueError):
            TopicArticlesRequest(topicCode="T4dryo6", limit=invalid)
    with pytest.raises(ValueError):
        TopicArticlesRequest(topicCode="T4dryo6", sort="latest")


def test_recommend_then_feed_filters_supported_types_deduplicates_and_builds_get_compatible_urls():
    opener = FixtureOpener(_base_pages())
    provider = _provider(opener)
    request = TopicArticlesRequest(topicCode="T4dryo6", limit=4)
    raw = provider.fetch_raw_topic_articles(request)
    records = normalize_topic_articles(request, raw, source=provider.source)

    assert [record.data["contentId"] for record in records] == [
        "680237611",
        "698394446",
        "680237612",
        "698348634",
    ]
    assert [record.data["rank"] for record in records] == [1, 2, 3, 4]
    assert [record.data["contentType"] for record in records] == ["news", "zhibo", "news", "zhibo"]
    assert records[0].data["sourceName"] == "上海证券报·中国证券网"
    assert records[1].data["sourceName"] is None
    assert records[1].record_id == "tonghuashun:topic-article:T4dryo6:zhibo:698394446"
    assert records[1].entity_id == "tonghuashun:article:698394446"
    for record in records:
        article_request = ArticleDetailRequest(url=record.data["url"])
        assert article_request.content_id == record.data["contentId"]
        assert article_request.content_type == record.data["contentType"]
        assert record.quality.issues[0].kind.value == "partial"
        assert record.provenance.source_references

    assert [
        (parse_qs(urlsplit(url).query)["queryType"][0], parse_qs(urlsplit(url).query)["page"][0])
        for url in opener.urls
    ] == [("recommend", "1"), ("feed", "1"), ("feed", "2")]
    assert "type 1: 1" in raw["partialDetail"]
    assert "type 18: 1" in raw["partialDetail"]


def test_limit_applies_after_type_filter_and_network_scan_has_a_hard_page_bound():
    pages = {("recommend", page): ([_feed_item(str(2400000000 + page), item_type=1)], True) for page in range(1, 9)}
    opener = FixtureOpener(pages)
    raw = _provider(opener).fetch_raw_topic_articles(TopicArticlesRequest(topicCode="T4dryo6", limit=1))

    assert raw["rows"] == []
    assert len(opener.urls) == 8
    assert any("8-page safety bound" in warning for warning in raw["warnings"])
    assert "type 1: 8" in raw["partialDetail"]


def test_articles_from_topic_rejects_deep_topic_and_uses_t_code_for_cache_identity():
    opener = FixtureOpener(_base_pages())
    topic_provider = _provider(opener)
    registry = ProviderRegistry((PROVIDER_REGISTRY.get_provider("tonghuashun.topic"),))
    collector = Collector(
        registry=registry,
        provider_instances={"tonghuashun.topic": topic_provider},
        cache=Cache(MemoryStorage()),
        cache_policy=CachePolicy(enabled=True, ttl=300),
    )
    client = FinchX(collector=collector)

    with pytest.raises(UnsupportedTopicURL, match="global report index"):
        client.articles.from_topic(DEEP_TOPIC_URL)
    first = client.articles.from_topic(T_TOPIC_URL, limit=4)
    second = client.articles.from_topic(T_TOPIC_MOBILE_URL, limit=4)
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(opener.urls) == 3


class FakeArticleDetailProvider:
    provider_id = "tonghuashun.articles"

    def __init__(self) -> None:
        self.source = Source(providerId=self.provider_id)
        self.received_urls: list[str] = []

    def fetch_raw_article_detail(self, request: ArticleDetailRequest) -> dict[str, object]:
        self.received_urls.append(request.url)
        return {
            "contentId": request.content_id,
            "contentType": request.content_type,
            "title": "Offline detail fixture",
            "contentHtml": "<p>Offline body.</p>",
            "contentText": "Offline body.",
            "pageUrl": request.url,
            "capturedAt": CAPTURED_AT,
        }


def test_topic_item_url_flows_directly_into_the_existing_articles_get_contract():
    topic_provider = _provider(FixtureOpener(_base_pages()))
    article_provider = FakeArticleDetailProvider()
    registry = ProviderRegistry(
        (
            PROVIDER_REGISTRY.get_provider("tonghuashun.topic"),
            PROVIDER_REGISTRY.get_provider("tonghuashun.articles"),
        )
    )
    collector = Collector(
        registry=registry,
        provider_instances={
            "tonghuashun.topic": topic_provider,
            "tonghuashun.articles": article_provider,
        },
    )
    client = FinchX(collector=collector)

    refs = client.articles.from_topic(T_TOPIC_URL, limit=1, use_cache=False)
    url = refs.data[0].data["url"]
    detail = client.articles.get(url, use_cache=False)

    assert article_provider.received_urls == [url]
    assert detail.data.data["contentId"] == refs.data[0].data["contentId"]
    assert detail.data.data["title"] == "Offline detail fixture"
    assert ARTICLE_TOPIC_DATASET.name == refs.dataset.name


def _tkojw02_recommend_rows() -> list[dict[str, object]]:
    news = _feed_item(
        "680209278",
        title="被爆供货紧张，矢量网络分析仪(VNA)概念股集体大涨，多股涨停",
        time_ms=1790147045000,
    )
    long_articles = [
        ("697978628", "AI算力如何驱动矢量网络分析仪需求大增？", 1790150616000),
        (
            "697861623",
            "调研解读|未来光模块散热或迎重要性升级，石墨烯等新技术有望加速导入，关于MLCP、陶瓷基板、石墨烯、矢量网络分析仪的一些信息更新",
            1790140005000,
        ),
        ("697624209", "华泰证券：AI算力建设驱动矢量网络分析仪需求", 1790121295000),
        ("698348634", "新概念，突然火了！龙头暴涨近70%（附股）", 1790206160000),
    ]
    return [
        news,
        *[
            {
                "info": {
                    "id": content_id,
                    "type": 2,
                    "time": time_ms,
                    "jump_url": (
                        "https://mp.10jqka.com.cn/lgt/article_detail/index.html?contentId=opaque"
                    ),
                },
                "title": {"content": title},
                "news": None,
                "share": None,
            }
            for content_id, title, time_ms in long_articles
        ],
    ]


def test_tkojw02_first_recommend_page_contains_news_and_four_get_compatible_long_articles():
    pages = {("recommend", 1): (_tkojw02_recommend_rows(), False)}
    topic_provider = _provider(FixtureOpener(pages))
    article_provider = FakeArticleDetailProvider()
    registry = ProviderRegistry(
        (
            PROVIDER_REGISTRY.get_provider("tonghuashun.topic"),
            PROVIDER_REGISTRY.get_provider("tonghuashun.articles"),
        )
    )
    client = FinchX(
        collector=Collector(
            registry=registry,
            provider_instances={
                "tonghuashun.topic": topic_provider,
                "tonghuashun.articles": article_provider,
            },
        )
    )

    refs = client.articles.from_topic(
        "https://t.10jqka.com.cn/m/topic/index.html?code=Tkojw02",
        limit=5,
        use_cache=False,
    )
    assert [record.data["contentId"] for record in refs.data] == [
        "680209278",
        "697978628",
        "697861623",
        "697624209",
        "698348634",
    ]
    assert [record.data["contentType"] for record in refs.data] == ["news", "zhibo", "zhibo", "zhibo", "zhibo"]
    assert [record.data["rank"] for record in refs.data] == [1, 2, 3, 4, 5]
    assert refs.data[1].data["title"] == "AI算力如何驱动矢量网络分析仪需求大增？"
    assert refs.data[1].data["publishedAt"] == "2026-09-23T16:03:36+08:00"
    assert all(record.data["sourceName"] is None for record in refs.data[1:])

    details = [client.articles.get(record.data["url"], use_cache=False) for record in refs.data]
    assert [detail.data.data["contentId"] for detail in details] == [
        record.data["contentId"] for record in refs.data
    ]
    assert [detail.data.data["contentType"] for detail in details] == [
        record.data["contentType"] for record in refs.data
    ]
    assert article_provider.received_urls == [record.data["url"] for record in refs.data]


def test_invalid_type2_id_is_skipped_and_marks_remaining_records_partial():
    invalid = {
        "info": {"id": "not-a-pid", "type": 2, "time": 1790206160000},
        "title": {"content": "不可用 PID"},
        "news": None,
    }
    pages = {
        ("recommend", 1): ([_feed_item("680209278"), invalid, _feed_item("2407591527", item_type=1)], False),
        ("feed", 1): ([], False),
    }
    opener = FixtureOpener(pages)
    provider = _provider(opener)
    request = TopicArticlesRequest(topicCode="Tkojw02", limit=5)
    raw = provider.fetch_raw_topic_articles(request)
    records = normalize_topic_articles(request, raw, source=provider.source)

    assert [record.data["contentId"] for record in records] == ["680209278"]
    assert "Skipped 1 type=2 feed items" in raw["partialDetail"]
    assert "type 1: 1" in raw["partialDetail"]
    assert records[0].quality.issues[0].kind.value == "partial"
