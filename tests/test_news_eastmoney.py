"""东方财富新闻：真实来源样本与分页/正文损坏回归。"""

from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.eastmoney import news

FIXTURES = Path(__file__).parent / "fixtures" / "news_eastmoney"
CMS_ID = "202610083889572316"
CFH_ID = "20261003092348071215620"
CMS_URL = f"http://finance.eastmoney.com/a/{CMS_ID}.html"
CFH_URL = f"http://caifuhao.eastmoney.com/news/{CFH_ID}"


def payload(rows, page=1, total=None):
    return {"code": 1, "message": "success", "data": {
        "page_index": page, "page_size": 20, "totle_hits": len(rows) if total is None else total, "list": rows}}


def rows(count=20, start=0):
    # 构造分页故障数据；真实返回断言独立使用官方原始样本。
    return [{"Art_Code": str(100000000000000000 + index), "Art_Title": f"文{index}",
             "Art_ShowTime": (datetime(2026, 10, 8, 20) - timedelta(minutes=index)).strftime("%Y-%m-%d %H:%M:%S"),
             "Art_Url": f"http://finance.eastmoney.com/a/{100000000000000000 + index}.html"}
            for index in range(start, start + count)]


def mock_pages(monkeypatch, pages):
    calls = []
    def get(url, **kwargs):
        calls.append((parse_qs(urlsplit(url).query), kwargs))
        return deepcopy(pages[len(calls) - 1])
    monkeypatch.setattr(news, "get_json", get)
    return calls


def test_real_mixed_cms_cfh_directory(monkeypatch):
    raw = json.loads((FIXTURES / "list.json").read_text(encoding="utf-8"))
    calls = mock_pages(monkeypatch, [raw])
    result = news.em_list("600519", timeout=9)
    assert len(result) == 20
    assert result[0] == {"id": CMS_ID, "title": "节庆文旅场景，成酒企动销新主场",
                         "published_at": "2026-10-08T14:46:00+08:00", "url": CMS_URL, "author": None}
    assert result[3]["id"] == CFH_ID
    assert result[3]["author"] == "格隆汇"
    assert result[3]["url"] == CFH_URL
    assert result[10]["url"].startswith("http://stock.eastmoney.com/")
    assert all(set(row) == {"id", "title", "published_at", "url", "author"} for row in result)
    assert calls[0][0] == {"cfh": ["1"], "client": ["web"], "mTypeAndCode": ["1.600519"],
                          "type": ["1"], "pageSize": ["20"], "pageIndex": ["1"]}
    assert calls[0][1]["timeout"] == 9


@pytest.mark.parametrize("code", [600519, "６００５１９", "sh600519", "60051", "920001", "399001", True])
def test_invalid_stock_before_network(monkeypatch, code):
    calls = mock_pages(monkeypatch, [])
    with pytest.raises(ValueError):
        news.em_list(code, timeout=1)
    assert not calls


@pytest.mark.parametrize("limit", [False, True, 0, -1, None, "20", 2.5])
def test_invalid_limit_before_network(monkeypatch, limit):
    calls = mock_pages(monkeypatch, [])
    with pytest.raises(ValueError):
        news.em_list("000001", limit=limit, timeout=1)
    assert not calls


def test_multi_page_filtered_limit_and_overlap_latest_row(monkeypatch):
    first = rows()
    second = [deepcopy(first[-1])] + rows(19, 20)
    second[0]["Art_Title"] = "来源后读更新"
    third = rows(20, 39)
    calls = mock_pages(monkeypatch, [payload(first, total=60), payload(second, 2, 60), payload(third, 3, 60)])
    result = news.em_list("000001", limit=40, until="2026-10-08 19:50:00", timeout=1)
    assert len(result) == 40
    assert result[0]["published_at"] == "2026-10-08T19:50:00+08:00"
    assert result[9]["title"] == "来源后读更新"
    assert result[-1]["id"] == str(100000000000000049)
    assert [call[0]["pageIndex"] for call in calls] == [["1"], ["2"], ["3"]]
    assert calls[0][0]["mTypeAndCode"] == ["0.000001"]


def test_date_window_closed_both_ends(monkeypatch):
    items = rows(4)
    for item, stamp in zip(items, ["2026-10-09 00:00:00", "2026-10-08 23:59:59", "2026-10-08 00:00:00", "2026-10-07 23:59:59"]):
        item["Art_ShowTime"] = stamp
    mock_pages(monkeypatch, [payload(items)])
    result = news.em_list("600519", since="2026-10-08", until="2026-10-08", timeout=1)
    assert [item["id"] for item in result] == [items[1]["Art_Code"], items[2]["Art_Code"]]


def test_whole_page_before_since_can_stop_after_validation(monkeypatch):
    first, second = rows(), rows(start=20)
    calls = mock_pages(monkeypatch, [payload(first, total=60), payload(second, 2, 60)])
    result = news.em_list("600519", limit=50, since="2026-10-08 19:55:00", timeout=1)
    assert len(result) == 6
    assert len(calls) == 2


def test_out_of_order_disables_early_stop(monkeypatch):
    first = rows()
    first[1]["Art_ShowTime"] = "2026-10-08 21:00:00"
    second = rows(start=20)
    calls = mock_pages(monkeypatch, [payload(first, total=40), payload(second, 2, 40)])
    result = news.em_list("600519", limit=100, since="2026-10-09", timeout=1)
    assert result == []
    assert len(calls) == 2


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(code=True), lambda p: p.update(code=0),
    lambda p: p["data"].update(page_index=0), lambda p: p["data"].update(page_size=10),
    lambda p: p["data"].update(totle_hits=True), lambda p: p["data"].update(list=None),
    lambda p: p["data"]["list"][-1].update(Art_ShowTime="2026-02-30 13:00:00"),
    lambda p: p["data"]["list"][-1].update(Art_Code="１２３"),
    lambda p: p["data"]["list"][-1].update(Author=3),
    lambda p: p["data"]["list"][-1].update(Art_Title=False),
    lambda p: p["data"]["list"][-1].update(Art_Url=f"https://finance.eastmoney.com/a/{CMS_ID}.html"),
    lambda p: p["data"]["list"].__setitem__(-1, deepcopy(p["data"]["list"][0])),
])
def test_entire_page_validated_before_limit(monkeypatch, mutation):
    source = payload(rows())
    mutation(source)
    mock_pages(monkeypatch, [source])
    with pytest.raises(SourceError):
        news.em_list("600519", limit=1, timeout=1)


def test_short_page_with_more_declared_is_failure(monkeypatch):
    mock_pages(monkeypatch, [payload(rows(19), total=21)])
    with pytest.raises(SourceError, match="页长度"):
        news.em_list("600519", timeout=1)


def test_pagination_stagnation_is_failure(monkeypatch):
    first = rows()
    mock_pages(monkeypatch, [payload(first, total=60), payload(first, 2, 60)])
    with pytest.raises(SourceError, match="停滞"):
        news.em_list("600519", limit=40, timeout=1)


def test_total_drift_is_failure(monkeypatch):
    mock_pages(monkeypatch, [payload(rows(), total=40), payload(rows(start=20), 2, 41)])
    with pytest.raises(SourceError, match="变化"):
        news.em_list("600519", limit=40, timeout=1)


def test_explicit_exhaustion_empty_and_fewer_than_limit(monkeypatch):
    calls = mock_pages(monkeypatch, [payload([], total=0), payload(rows(2))])
    assert news.em_list("600519", limit=50, timeout=1) == []
    assert len(news.em_list("600519", limit=50, timeout=1)) == 2
    assert len(calls) == 2


def test_budget_does_not_return_partial(monkeypatch):
    monkeypatch.setattr(news, "_MAX_PAGES", 1)
    mock_pages(monkeypatch, [payload(rows(), total=40)])
    with pytest.raises(SourceError, match="预算"):
        news.em_list("600519", limit=40, timeout=1)


@pytest.mark.parametrize("filename,url,author,published,source", [
    ("cms.html", CMS_URL, None, "2026-10-08T14:46+08:00", "21世纪经济报道"),
    ("cfh.html", CFH_URL, "格隆汇", "2026-10-03T09:23+08:00", None),
])
def test_real_article_webpages(monkeypatch, filename, url, author, published, source):
    calls = []
    def get_html(checked, identity, timeout):
        calls.append((checked, identity, timeout))
        return (FIXTURES / filename).read_text(encoding="utf-8")
    monkeypatch.setattr(news, "_get_html", get_html)
    result = news.em_get(url, timeout=7)
    assert result["author"] == author
    assert result["published_at"] == published
    assert result["source_name"] == source
    assert set(result) == {"id", "title", "published_at", "source_name", "author", "content", "image_urls"}
    assert result["image_urls"] == []
    assert "本文作者可以追加内容" not in result["content"]
    assert "郑重声明" not in result["content"]
    assert "推荐" not in result["content"]
    assert calls == [(url.replace("http:", "https:"), result["id"], 7)]
    if author is None:
        assert result["content"].startswith("21世纪经济报道记者肖夏\n\n这个国庆长假")


@pytest.mark.parametrize("url", ["https://evil.example/a/123.html", "https://finance.eastmoney.com.evil/a/123.html",
    "https://a@finance.eastmoney.com/a/123.html", "ftp://finance.eastmoney.com/a/123.html",
    "https://finance.eastmoney.com:8080/a/123.html", "https://finance.eastmoney.com/a/１２３.html",
    "https://finance.eastmoney.com/a/123.html?url=https://evil.example", "https://finance.eastmoney.com/a/123.html#x",
    "https://caifuhao.eastmoney.com/news/abc", None])
def test_unsupported_url_before_network(monkeypatch, url):
    monkeypatch.setattr(news, "_get_html", lambda *args: pytest.fail("不应发请求"))
    with pytest.raises(ValueError):
        news.em_get(url, timeout=1)


@pytest.mark.parametrize("mutation", [
    lambda html: html.replace(f"var _NewsId = '{CMS_ID}'", "var _NewsId = '123'"),
    lambda html: html.replace('id="ContentBody"', 'id="UnknownBody"'),
    lambda html: html.replace("2026年10月08日 14:46", "2026年02月30日 14:46"),
    lambda html: html.replace("2026年10月08日 14:46", "not a time"),
    lambda html: html[:html.index("<!--文章主体-->")],
])
def test_detail_missing_or_invalid_necessary_structure(monkeypatch, mutation):
    raw = mutation((FIXTURES / "cms.html").read_text(encoding="utf-8"))
    monkeypatch.setattr(news, "_get_html", lambda *args: raw)
    with pytest.raises(SourceError):
        news.em_get(CMS_URL, timeout=1)


def test_cfh_identity_conflict(monkeypatch):
    raw = (FIXTURES / "cfh.html").read_text(encoding="utf-8").replace(f'articleid:"{CFH_ID}"', 'articleid:"1"')
    monkeypatch.setattr(news, "_get_html", lambda *args: raw)
    with pytest.raises(SourceError, match="身份"):
        news.em_get(CFH_URL, timeout=1)


def test_content_paragraph_table_images_exclude_ad_and_outside(monkeypatch):
    raw = f'''<script>var _NewsId='{CMS_ID}'</script>
    <div id="topbox"><div class="title">来源标题</div><div class="infos"><div class="item">2026年10月08日 14:46:20</div></div></div>
    <div id="ContentBody"><p>第一段<strong>原文</strong></p><p>第二段<br>换行</p>
    <table><tr><th>指标</th><th>数值</th></tr><tr><td>收入</td><td>0</td></tr></table>
    <img src="//example.com/body.png"><div id="ad_context3"><p>广告文字</p><img src="//example.com/ad.png"></div></div>
    <div><p>推荐</p><img src="https://example.com/recommended.png"></div>'''
    monkeypatch.setattr(news, "_get_html", lambda *args: raw)
    result = news.em_get(CMS_URL, timeout=1)
    assert result["content"] == "第一段原文\n\n第二段\n换行\n\n指标 | 数值\n收入 | 0"
    assert result["image_urls"] == ["https://example.com/body.png"]
    assert result["published_at"] == "2026-10-08T14:46:20+08:00"


def test_article_redirect_must_keep_supported_source_identity():
    from urllib.request import Request
    handler = news._Redirect(CMS_ID)
    request = Request(CMS_URL.replace("http:", "https:"))
    for url in [f"https://evil.example/a/{CMS_ID}.html", "https://finance.eastmoney.com/a/1.html"]:
        with pytest.raises(SourceError):
            handler.redirect_request(request, None, 302, "Found", {}, url)
    target = handler.redirect_request(request, None, 302, "Found", {}, f"http://stock.eastmoney.com/a/{CMS_ID}.html")
    assert target.full_url == f"https://stock.eastmoney.com/a/{CMS_ID}.html"


def test_overlap_update_preserves_first_source_identity_order(monkeypatch):
    first = rows()
    second = [deepcopy(first[0])] + rows(19, 21)
    second[0]["Art_ShowTime"] = "2026-10-08 19:40:00"
    second[0]["Art_Title"] = "来源更新后进入区间"
    mock_pages(monkeypatch, [payload(first, total=40), payload(second, 2, 40)])
    result = news.em_list("600519", limit=20, until="2026-10-08 19:50:00", timeout=1)
    assert result[0]["id"] == first[0]["Art_Code"]
    assert result[0]["title"] == "来源更新后进入区间"
    assert result[1]["id"] == first[10]["Art_Code"]


def test_cfh_unrelated_account_field_before_identity_is_ignored(monkeypatch):
    raw = (FIXTURES / "cfh.html").read_text(encoding="utf-8").replace('var accountInfo = {', 'var accountInfo = { unknownNewField: 0,')
    monkeypatch.setattr(news, "_get_html", lambda *args: raw)
    result = news.em_get(CFH_URL, timeout=1)
    assert result["id"] == CFH_ID
    assert result["author"] == "格隆汇"


@pytest.mark.parametrize("image_url", ["http://[", "javascript:alert(1)"])
def test_malformed_article_image_is_source_error(monkeypatch, image_url):
    raw = (FIXTURES / "cms.html").read_text(encoding="utf-8").replace('<div class="ad_context3"', f'<img src="{image_url}"><div class="ad_context3"')
    monkeypatch.setattr(news, "_get_html", lambda *args: raw)
    with pytest.raises(SourceError, match="图片"):
        news.em_get(CMS_URL, timeout=1)


def test_overlap_at_window_end_without_target_is_failure(monkeypatch):
    first = rows()
    second = [deepcopy(first[-1])] + rows(19, 20)
    mock_pages(monkeypatch, [payload(first, total=40), payload(second, 2, 40)])
    with pytest.raises(SourceError, match="窗口未完整取齐"):
        news.em_list("600519", limit=50, timeout=1)


@pytest.mark.parametrize("until,expected", [(None, 40), ("2026-10-08 19:50:00", 30)])
def test_complete_window_allows_fewer_than_filtered_target(monkeypatch, until, expected):
    calls = mock_pages(monkeypatch, [payload(rows(), total=40), payload(rows(start=20), 2, 40)])
    result = news.em_list("600519", limit=50, until=until, timeout=1)
    assert len(result) == expected
    assert len(calls) == 2
