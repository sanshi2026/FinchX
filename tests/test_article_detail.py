from __future__ import annotations

from datetime import datetime, timezone
from http.client import HTTPMessage
from io import BytesIO
import hashlib
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest

from finchx import FinchX
from finchx.collector import Collector, FetchResult
from finchx.collectors.errors import AllProvidersFailed
from finchx.contracts import DataStatus, Source, StandardRecord
from finchx.datasets import ARTICLE_DETAIL_DATASET, ArticleDetailData, ArticleDetailRequest
from finchx.datasets.article_detail import classify_article_url, normalize_article_detail, normalize_http_url
from finchx.providers import ArticleDetailSourceError, THSArticleDetailProvider
from finchx.providers.ths_articles import (
    ARTICLE_PROVIDER_ID,
    NEWS_DETAIL_API,
    _content_markup,
    _extract_html_page,
    _parse_content_tree,
    _text_from_html,
    encode_news_seq,
)
from finchx.schemas import read_schema


FIXTURES = Path(__file__).parent / "fixtures" / "ths_articles"
CAPTURED = datetime(2026, 9, 24, 3, 30, tzinfo=timezone.utc)
NEWS_ID = "680236250"
ZHIBO_ID = "698348634"
NEWS_URL = f"https://stock.10jqka.com.cn/20260924/c{NEWS_ID}.shtml"
ZHIBO_URL = f"https://t.10jqka.com.cn/pid_{ZHIBO_ID}.shtml"
ZHIBO_MOBILE_URL = f"https://t.10jqka.com.cn/m/zhibo/pid_{ZHIBO_ID}.shtml"


class Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def read(self) -> bytes:
        return self.body


class FixtureOpener:
    """Offline synthetic responses for the public article routes."""

    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls: list[str] = []
        self.request_headers: list[dict[str, str]] = []
        self.lock = threading.Lock()

    def __call__(self, request, timeout):
        with self.lock:
            self.calls.append(request.full_url)
            self.request_headers.append(dict(request.header_items()))
        url = request.full_url
        path = urlsplit(url).path
        if self.mode == "network":
            raise OSError("fixture DNS/network failure")
        if self.mode == "zhibo_cookie_challenge" and path == f"/pid_{ZHIBO_ID}.shtml":
            if "Cookie" not in dict(request.header_items()):
                self._http_error(url, 401, set_cookie="vvvv=1; Path=/")
        if self.mode == "zhibo_all_unauthorized" and path.startswith(("/pid_", "/m/zhibo/pid_")):
            if path.startswith("/pid_"):
                self._http_error(
                    url,
                    401,
                    final_url="https://t.10jqka.com.cn/auth/required",
                    location="https://t.10jqka.com.cn/auth/required",
                )
            self._http_error(url, 401)
        if self.mode == "unauthorized" and "/WEB/" in path:
            self._http_error(url, 401)
        if self.mode == "missing":
            self._http_error(url, 404)
        if self.mode in {"api_unauthorized", "news_page_fallback"} and "/WEB/" in path:
            self._http_error(url, 401)
        if self.mode == "zhibo_desktop_missing" and path == f"/pid_{ZHIBO_ID}.shtml":
            self._http_error(url, 404)
        if self.mode == "zhibo_desktop_unauthorized" and path == f"/pid_{ZHIBO_ID}.shtml":
            self._http_error(url, 401)
        if self.mode == "zhibo_desktop_missing" and path == f"/m/zhibo/pid_{ZHIBO_ID}.shtml":
            self._http_error(url, 404)
        if path in {f"/pid_{ZHIBO_ID}.shtml", f"/m/zhibo/pid_{ZHIBO_ID}.shtml"}:
            html = (FIXTURES / "zhibo_article.html").read_text()
            return Response(html.replace("698346116", ZHIBO_ID).encode())
        if path.startswith("/m/zhibo/pid_"):
            self._http_error(url, 404)
        if path.startswith("/pid_"):
            self._http_error(url, 404)
        if path.startswith("/mobile_api/news/article/page/v2/WEB/"):
            if not path.endswith(encode_news_seq(NEWS_ID)):
                raise AssertionError(f"unexpected article ID encoding in: {url}")
            payload = json.loads((FIXTURES / "news_detail.json").read_text())
            article = payload["detailData"]["article"]
            article["seq"] = NEWS_ID
            if self.mode == "api_id_mismatch":
                article["seq"] = str(int(NEWS_ID) + 1)
            article["sourceUrl"] = (
                f"[https://stock.10jqka.com.cn/20260924/c{NEWS_ID}.shtml]"
                f"(https://stock.10jqka.com.cn/20260924/c{NEWS_ID}.shtml)"
            )
            # URL-valued attributes can arrive with a copied Markdown wrapper.
            article["content"] = article["content"].replace(
                'src="/images/chart.png" alt="走势图片"',
                'src="[chart](https://news.10jqka.com.cn/images/chart.png)" alt=""',
            )
            article["content"] = article["content"].replace("<p>第一段正文", "<p> 第一段正文")
            article["content"] += (
                '<strong></strong><p class="brokers_hidden"><a '
                'href="https://mams.10jqka.com.cn/new/server/html/113894.html?injectAdaptive=true">'
                '六张图复盘924两周年：近三成A股实现翻倍上涨&gt;&gt;</a></p><p></p>'
            )
            self.raw_news_content = article["content"]
            return Response(json.dumps(payload, ensure_ascii=False).encode())
        if self.mode in {"news_page_fallback", "api_unauthorized"} and path == "/20260924/c680236250.shtml":
            html = (FIXTURES / "news_embedded_state.html").read_text()
            html = html.replace("680232625", NEWS_ID)
            return Response(html.encode())
        raise AssertionError(f"unexpected request URL: {url}")

    @staticmethod
    def _http_error(url: str, status: int, *, final_url: str | None = None, location: str | None = None,
                    set_cookie: str | None = None) -> None:
        reason = {401: "Unauthorized", 404: "Not Found"}.get(status, "HTTP Error")
        headers = HTTPMessage()
        if location:
            headers.add_header("Location", location)
        if set_cookie:
            headers.add_header("Set-Cookie", set_cookie)
        raise HTTPError(final_url or url, status, reason, headers, BytesIO(b""))


def _client(opener: FixtureOpener, *, clock=CAPTURED):
    provider = THSArticleDetailProvider(opener, clock=lambda: clock)
    collector = Collector(provider_instances={ARTICLE_PROVIDER_ID: provider})
    return FinchX(collector=collector), provider


def test_article_request_derives_news_identity_and_date_from_url():
    request = ArticleDetailRequest(url=NEWS_URL)
    assert request.date.isoformat() == "2026-09-24"
    assert request.content_type == "news"
    assert request.content_id == NEWS_ID
    assert request.url == NEWS_URL


def test_url_normalizer_unwraps_markdown_urls_and_classifies_supported_pages():
    wrapped = f"[https://t.10jqka.com.cn/m/zhibo/pid_{ZHIBO_ID}.shtml](https://t.10jqka.com.cn/m/zhibo/pid_{ZHIBO_ID}.shtml)"
    assert normalize_http_url(wrapped) == f"https://t.10jqka.com.cn/m/zhibo/pid_{ZHIBO_ID}.shtml"
    assert classify_article_url(wrapped) == (
        "zhibo",
        f"https://t.10jqka.com.cn/pid_{ZHIBO_ID}.shtml",
        ZHIBO_ID,
    )
    assert classify_article_url(
        NEWS_URL
    ) == ("news", NEWS_URL, NEWS_ID)
    mobile = f"https://t.10jqka.com.cn/m/zhibo/pid_{ZHIBO_ID}.shtml?from=hotlist#share"
    assert ArticleDetailRequest(url=mobile).url == ZHIBO_URL
    long_news_id = "701842511656336177"
    long_news_url = f"https://news.10jqka.com.cn/20260924/c{long_news_id}.shtml"
    long_request = ArticleDetailRequest(url=long_news_url + "?from=article#share")
    assert long_request.content_id == long_news_id
    assert long_request.url == long_news_url


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/20260924/c680236250.shtml",
        "https://sub.stock.10jqka.com.cn/20260924/c680236250.shtml",
        "https://t.10jqka.com.cn/20260924/c680236250.shtml",
        "https://news.10jqka.com.cn/20260931/c680236250.shtml",
        "https://news.10jqka.com.cn/mobile_api/news/article/page/v2/WEB/123",
        "https://news.10jqka.com.cn:8443/20260924/c680236250.shtml",
        "javascript:alert(1)",
        "https://user:pass@news.10jqka.com.cn/20260924/c680236250.shtml",
    ],
)
def test_article_request_rejects_non_allowlisted_or_malformed_urls(url):
    with pytest.raises(ValueError):
        ArticleDetailRequest(url=url)


@pytest.mark.parametrize(
    ("fixture_name", "required_text", "image_count"),
    [
        ("real_long_form.html", "50万亿元", 0),
        ("real_short_brief.html", "上证指数", 0),
        ("real_image_article.html", "72.01亿元", 1),
    ],
)
def test_real_article_body_samples_keep_text_and_sanitize_market_links(
    fixture_name, required_text, image_count
):
    raw = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    html, text = _content_markup(_parse_content_tree(raw), base_url=NEWS_URL)
    assert required_text in text
    assert text == _text_from_html(html)
    assert "#*f:" not in html
    assert "width=" not in html and "height=" not in html
    assert "class=" not in html and "style=" not in html
    assert html.count("<img") == image_count
    assert "[图片]" not in text and "[图片:" not in text


def test_entity_encoded_market_anchor_is_unwrapped_without_losing_its_text():
    raw = (
        "<p>A股指数：&lt;a href=&quot;https://news.10jqka.com.cn/"
        "#*f:1A0001:sc*#&quot;&gt;上证指数&lt;/a&gt;上涨0.3%。</p>"
    )
    html, text = _content_markup(_parse_content_tree(raw), base_url=NEWS_URL)
    assert html == "<p>A股指数：上证指数上涨0.3%。</p>"
    assert text == "A股指数：上证指数上涨0.3%。"


def test_stock_page_market_jump_links_are_unwrapped():
    raw = (
        '<p><a href="https://stock.10jqka.com.cn/20260924/c680248326.shtml#*f:1A0001:sc*#">'
        '上证指数</a>跌幅扩大至1%，'
        '<a href="https://stock.10jqka.com.cn/20260924/c680248326.shtml#*f:399001:sc*#">'
        '深证成指</a>跌1.85%。</p>'
    )
    html, text = _content_markup(_parse_content_tree(raw), base_url=NEWS_URL)
    assert html == "<p>上证指数跌幅扩大至1%，深证成指跌1.85%。</p>"
    assert text == "上证指数跌幅扩大至1%，深证成指跌1.85%。"


def test_editorial_structure_survives_while_presentational_attributes_are_removed():
    raw = (
        '<div class="article-body" style="display:block"><p class="x" width="99" '
        'height="88" style="color:red">段落<span class="empty"></span></p>'
        '<blockquote><p>引用正文</p></blockquote><ol><li>列表正文</li></ol>'
        '<table class="data-table" width="300"><tr><th>指标</th><td>1.23%</td></tr></table>'
        '<script>tracking()</script></div>'
    )
    html, text = _content_markup(_parse_content_tree(raw), base_url=NEWS_URL)
    assert "<blockquote><p>引用正文</p></blockquote>" in html
    assert "<ol><li>列表正文</li></ol>" in html
    assert "<table><tr><th>指标</th><td>1.23%</td></tr></table>" in html
    assert all(value in text for value in ("段落", "引用正文", "列表正文", "指标", "1.23%"))
    assert "class=" not in html and "style=" not in html
    assert "width=" not in html and "height=" not in html
    assert "tracking" not in html and "<span" not in html


def test_image_only_body_is_available_without_a_mechanical_image_placeholder():
    raw_image = "<p><img src=\"https://u.thsi.cn/article/image.png\" width=320 height=180></p>"
    html, text = _content_markup(_parse_content_tree(raw_image), base_url=NEWS_URL)
    record = normalize_article_detail(
        ArticleDetailRequest(url=NEWS_URL),
        {
            "contentId": NEWS_ID,
            "contentType": "news",
            "title": "图文文章",
            "contentHtml": html,
            "contentText": text,
            "capturedAt": CAPTURED,
        },
        source=Source(providerId=ARTICLE_PROVIDER_ID),
    )
    detail = ArticleDetailData.model_validate(record.data)
    assert detail.content_available
    assert detail.content_html == '<p><img src="https://u.thsi.cn/article/image.png"></p>'
    assert detail.content_text == ""
    assert "[图片]" not in detail.content_text


def test_news_url_uses_encoded_detail_api_and_normalizes_body():
    opener = FixtureOpener()
    fx, _ = _client(opener)
    result = fx.articles.get(NEWS_URL)

    assert isinstance(result, FetchResult)
    assert result.dataset.name == ARTICLE_DETAIL_DATASET.name == "articles.detail"
    assert isinstance(result.data, StandardRecord)
    assert result.data.status is DataStatus.LIVE
    detail = ArticleDetailData.model_validate(result.data.data)
    assert detail.content_type == "news"
    assert detail.title == "普通新闻样例标题"
    assert "第一段正文" in detail.content_text and "第二段正文" in detail.content_text
    assert "免责声明不得进入正文" not in detail.content_text
    assert "评论不得进入正文" not in detail.content_text
    assert "六张图复盘924两周年" not in detail.content_text
    assert "走势图片" not in detail.content_text
    assert "[图片]" not in detail.content_text
    assert "[chart](" not in (detail.content_html or "")
    assert "brokers_hidden" not in (detail.content_html or "")
    assert "六张图复盘924两周年" not in (detail.content_html or "")
    assert "<p> 第一段正文" not in (detail.content_html or "")
    assert "<strong></strong>" not in (detail.content_html or "")
    assert "<p></p>" not in (detail.content_html or "")
    assert "https://news.10jqka.com.cn/images/chart.png" in (detail.content_html or "")
    assert f"c{NEWS_ID}.shtml" in str(detail.page_url)
    assert detail.source_url is not None
    assert "[https://" not in str(detail.source_url)
    assert detail.fetch_method == "detail_api"
    assert detail.author == "财经编辑" and detail.source_name == "同花顺财经"
    assert detail.ai_summary == "新闻摘要"
    assert detail.disclaimer == "投资有风险，入市需谨慎。"
    assert len(detail.raw_hash or "") == 64
    assert detail.raw_hash == hashlib.sha256(opener.raw_news_content.encode("utf-8")).hexdigest()
    assert len(opener.calls) == 1
    assert opener.calls[0] == NEWS_DETAIL_API.format(encode_news_seq(NEWS_ID))
    assert str(detail.page_url) == NEWS_URL
    assert str(detail.source_url) == opener.calls[0]


@pytest.mark.parametrize("url", [ZHIBO_URL, ZHIBO_MOBILE_URL])
def test_zhibo_url_never_calls_news_api_and_separates_comments(url):
    opener = FixtureOpener()
    fx, _ = _client(opener)
    result = fx.articles.get(url)
    detail = ArticleDetailData.model_validate(result.data.data)
    assert detail.content_type == "zhibo"
    assert str(detail.page_url) == f"https://t.10jqka.com.cn/pid_{ZHIBO_ID}.shtml"
    assert str(detail.source_url) == f"https://t.10jqka.com.cn/pid_{ZHIBO_ID}.shtml"
    assert detail.fetch_method == "zhibo_html"
    assert detail.title == "社区文章标题"
    assert "第一段社区正文" in detail.content_text
    assert "行业趋势图" in detail.content_text
    assert "免责声明" not in detail.content_text
    assert "评论甲" not in detail.content_text
    assert detail.disclaimer == "免责声明：本文仅供参考。"
    assert detail.comments == ["评论甲：内容仅为用户讨论。", "评论乙：不应并入正文。"]
    assert len(opener.calls) == 1
    assert opener.calls[0] == ZHIBO_URL
    headers = {key.casefold(): value for key, value in opener.request_headers[0].items()}
    assert "chrome/140.0.0.0" in headers["user-agent"].casefold()
    assert "image/avif,image/webp" in headers["accept"]
    assert "/mobile_api/news/article/page/v2/WEB/" not in opener.calls[0]


def test_mobile_and_desktop_zhibo_urls_share_cache_identity():
    opener = FixtureOpener()
    fx, _ = _client(opener)
    first = fx.articles.get(ZHIBO_MOBILE_URL)
    second = fx.articles.get(ZHIBO_URL)
    assert not first.cache_hit
    assert second.cache_hit
    assert opener.calls == [ZHIBO_URL]


def test_zhibo_uses_mobile_page_only_when_desktop_page_fails():
    opener = FixtureOpener("zhibo_desktop_unauthorized")
    fx, _ = _client(opener)
    result = fx.articles.get(ZHIBO_URL, use_cache=False)
    detail = ArticleDetailData.model_validate(result.data.data)
    assert detail.content_type == "zhibo"
    assert str(detail.page_url) == f"https://t.10jqka.com.cn/pid_{ZHIBO_ID}.shtml"
    assert str(detail.source_url) == f"https://t.10jqka.com.cn/m/zhibo/pid_{ZHIBO_ID}.shtml"
    assert opener.calls == [ZHIBO_URL, ZHIBO_MOBILE_URL]


def test_zhibo_401_is_reported_after_both_routes_fail():
    opener = FixtureOpener("zhibo_all_unauthorized")
    fx, _ = _client(opener)
    with pytest.raises(ArticleDetailSourceError) as raised:
        fx.articles.get(ZHIBO_URL, use_cache=False)
    assert raised.value.error_code == "unauthorized"
    assert ZHIBO_URL in str(raised.value)
    assert ZHIBO_MOBILE_URL in str(raised.value)
    assert "https://t.10jqka.com.cn/auth/required" in str(raised.value)
    assert "redirect Location" in str(raised.value)
    assert opener.calls == [ZHIBO_URL, ZHIBO_MOBILE_URL]


def test_zhibo_401_cookie_challenge_is_retried_once_for_complete_body():
    opener = FixtureOpener("zhibo_cookie_challenge")
    fx, _ = _client(opener)
    detail = ArticleDetailData.model_validate(fx.articles.get(ZHIBO_URL).data.data)
    assert detail.fetch_method == "zhibo_html"
    assert "第一段社区正文" in detail.content_text
    assert "评论甲" not in detail.content_text
    assert detail.comments == ["评论甲：内容仅为用户讨论。", "评论乙：不应并入正文。"]
    assert opener.calls == [ZHIBO_URL, ZHIBO_URL]
    assert dict(opener.request_headers[1])["Cookie"] == "vvvv=1"


def test_zhibo_real_page_classes_separate_metadata_body_and_comments():
    html = (
        f'<html><head><title>真实文章标题</title></head><body data-pid="{ZHIBO_ID}">'
        '<h1>同顺号-创作平台</h1><a class="post-author">数据宝</a>'
        '<div class="detail-title">真实文章标题</div>'
        '<span class="detail-date">2026-09-24</span><span class="detail-time">07:29</span>'
        '<div class="wdwrap post-text-main c444 ql-editor"><p>完整正文第一段。</p></div>'
        '<ul class="comment-list"><li class="single-comment">'
        '<div class="commenter-name">用户甲</div><div class="comment-text">评论内容</div>'
        '</li></ul><div class="post-detail-qshint">'
        '<div>本文纯属作者个人观点，仅供您参考。</div>'
        '<div>请勿相信推广信息。</div></div></body></html>'
    )
    page = _extract_html_page(html, page_url=ZHIBO_URL, zhibo=True)
    assert page is not None
    assert page["title"] == "真实文章标题"
    assert page["author"] == "数据宝"
    assert page["publishedAt"].isoformat() == "2026-09-24T07:29:00+08:00"
    assert page["contentText"] == "完整正文第一段。"
    assert page["comments"] == ["评论内容"]
    assert page["disclaimer"] == "本文纯属作者个人观点，仅供您参考。\n\n请勿相信推广信息。"


def test_news_page_url_from_input_is_used_for_html_fallback():
    opener = FixtureOpener("api_unauthorized")
    fx, _ = _client(opener)
    result = fx.articles.get(NEWS_URL, use_cache=False)
    detail = ArticleDetailData.model_validate(result.data.data)
    assert detail.fetch_method == "embedded_state"
    assert str(detail.page_url) == NEWS_URL
    assert len(opener.calls) == 2
    assert opener.calls[1] == NEWS_URL


def test_news_api_response_id_must_match_id_in_url():
    opener = FixtureOpener("api_id_mismatch")
    fx, _ = _client(opener)
    with pytest.raises(ArticleDetailSourceError) as raised:
        fx.articles.get(NEWS_URL, use_cache=False)
    assert raised.value.error_code == "id_mismatch"
    assert len(opener.calls) == 1
    assert "/WEB/" in opener.calls[0]


def test_network_failures_are_not_cached_and_404s_use_short_negative_cache():
    missing_opener = FixtureOpener("missing")
    missing_fx, _ = _client(missing_opener)
    for _ in range(2):
        with pytest.raises(ArticleDetailSourceError):
            missing_fx.articles.get(NEWS_URL)
    assert len(missing_opener.calls) == 2

    network_opener = FixtureOpener("network")
    network_fx, _ = _client(network_opener)
    for _ in range(2):
        with pytest.raises(AllProvidersFailed):
            network_fx.articles.get(NEWS_URL)
    assert len(network_opener.calls) == 4


def test_related_security_codes_are_preserved_without_false_equity_identity():
    from finchx.datasets.article_detail import normalize_article_detail
    from finchx.contracts import Source

    request = ArticleDetailRequest(url=NEWS_URL)
    record = normalize_article_detail(
        request,
        {
            "contentId": NEWS_ID,
            "contentType": "news",
            "title": "测试文章",
            "contentHtml": "<p>正文</p>",
            "contentText": "正文",
            "capturedAt": CAPTURED,
            "relatedStocks": [
                {"symbol": "399300", "name": "沪深300", "sourceMarket": "33"},
                {"symbol": "551500", "name": "ETF样例", "sourceMarket": "21"},
            ],
            "sourceUrl": f"https://stock.10jqka.com.cn/20260924/c{NEWS_ID}.shtml",
        },
        source=Source(providerId=ARTICLE_PROVIDER_ID),
    )
    data = ArticleDetailData.model_validate(record.data)
    by_code = {stock.symbol: stock for stock in data.related_stocks}
    assert set(by_code) == {"399300", "551500"}
    assert all(stock.instrument_id is None for stock in by_code.values())
    assert all(stock.sources == ["detail"] for stock in by_code.values())


def test_article_schema_matches_model():
    schema = read_schema("article-detail.schema.json")
    generated = ArticleDetailData.model_json_schema(by_alias=True)
    assert set(schema["properties"]) == set(generated["properties"])
