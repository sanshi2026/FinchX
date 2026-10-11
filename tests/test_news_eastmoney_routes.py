"""个股目录真实 money/insurance CMS 地址的路由与身份边界。"""

from urllib.request import Request

import pytest

from finchx._common.errors import SourceError
from finchx.sources.eastmoney import news

# 两行取自 300308 目录第 5 页公开返回。
_ROWS = [
    {"Art_ShowTime": "2026-09-28 19:59:10", "Art_Code": "202609283885360032", "Np_dst": "CMS",
     "Art_Title": "拟每10股派12元！光模块龙头A股中期分红超13亿元",
     "Art_SortStart": "1790596750060032",
     "Art_OriginUrl": "http://stock.eastmoney.com/news/11215,202609283885360032.html",
     "Art_Url": "http://money.eastmoney.com/a/202609283885360032.html"},
    {"Art_ShowTime": "2026-09-28 17:25:51", "Art_Code": "202609283885549753", "Np_dst": "CMS",
     "Art_Title": "【焦点复盘】深成指四连阴创年内新低，算力硬件股大面积退潮，“易中天”三巨头均大跌超8%",
     "Art_SortStart": "1790587551049753",
     "Art_OriginUrl": "http://finance.eastmoney.com/news/1354,202609283885549753.html",
     "Art_Url": "http://insurance.eastmoney.com/a/202609283885549753.html"},
]


@pytest.mark.parametrize("raw", _ROWS)
def test_source_directory_preserves_real_cms_url_and_source_precision(raw):
    row, stamp = news._parse_row(raw)
    assert row == {"id": raw["Art_Code"], "title": raw["Art_Title"],
                   "published_at": raw["Art_ShowTime"].replace(" ", "T") + "+08:00",
                   "url": raw["Art_Url"], "author": None}


def test_real_routes_pass_public_list_entrypoint_without_skipping(monkeypatch):
    payload = {"code": 1, "data": {"page_index": 1, "page_size": 20, "totle_hits": 2, "list": _ROWS}}
    monkeypatch.setattr(news, "get_json", lambda *a, **k: payload)
    result = news.em_list("300308", limit=100, since="2026-09-01", until="2026-10-08", timeout=5)
    assert [row["url"] for row in result] == [row["Art_Url"] for row in _ROWS]


@pytest.mark.parametrize("raw", _ROWS)
def test_confirmed_cms_route_normalizes_only_http_scheme(raw):
    assert news._article_url(raw["Art_Url"]) == (raw["Art_Code"], raw["Art_Url"].replace("http:", "https:"))


@pytest.mark.parametrize("raw", _ROWS)
def test_official_redirect_to_finance_keeps_identity(raw):
    request = Request(raw["Art_Url"].replace("http:", "https:"))
    redirected = news._Redirect(raw["Art_Code"]).redirect_request(
        request, None, 302, "Found", {}, f'https://finance.eastmoney.com/a/{raw["Art_Code"]}.html')
    assert redirected.full_url == f'https://finance.eastmoney.com/a/{raw["Art_Code"]}.html'
    with pytest.raises(SourceError, match="身份"):
        news._Redirect(raw["Art_Code"]).redirect_request(request, None, 302, "Found", {},
            'https://finance.eastmoney.com/a/1.html')


@pytest.mark.parametrize("host", ["money.eastmoney.com", "insurance.eastmoney.com"])
@pytest.mark.parametrize("suffix", ["?url=https://evil.example", "#fragment", "/", ".php"])
def test_new_hosts_do_not_relax_article_path_query_or_fragment(host, suffix):
    with pytest.raises(ValueError):
        news._article_url(f"https://{host}/a/202609283885360032.html{suffix}")


@pytest.mark.parametrize("url", ["https://money.eastmoney.com.evil/a/202609283885360032.html",
    "https://evil.money.eastmoney.com/a/202609283885360032.html",
    "https://money.eastmoney.com:443/a/202609283885360032.html",
    "https://user@insurance.eastmoney.com/a/202609283885549753.html",
    "https://other.eastmoney.com/a/202609283885360032.html"])
def test_new_hosts_keep_exact_whitelist_and_authority_boundary(url):
    with pytest.raises(ValueError):
        news._article_url(url)


@pytest.mark.parametrize("raw", _ROWS)
def test_directory_still_rejects_url_identity_conflict(raw):
    conflicting = {**raw, "Art_Url": raw["Art_Url"].replace(raw["Art_Code"], "1")}
    with pytest.raises(SourceError, match="身份冲突"):
        news._parse_row(conflicting)


@pytest.mark.parametrize("raw", _ROWS)
def test_new_route_get_keeps_page_identity_and_minute_precision(monkeypatch, raw):
    # 必要公开页面结构与真实头部字段的精简回归，不保存整篇正文。
    source = "每日经济新闻" if "money.eastmoney" in raw["Art_Url"] else "财联社"
    author = None if source == "每日经济新闻" else "财联社 金皓明"
    clock = raw["Art_ShowTime"][:16]
    head_time = clock[:4] + "年" + clock[5:7] + "月" + clock[8:10] + "日 " + clock[11:]
    author_html = '' if author is None else f'<div class="item">作者：{author}</div>'
    html = f'''<script>var _NewsId='{raw["Art_Code"]}'</script>
    <div id="topbox"><div class="title">{raw["Art_Title"]}</div><div class="infos">
    <div class="item">{head_time}</div><div class="item">来源：{source}</div>{author_html}</div></div>
    <div id="ContentBody"><p>来源正文片段</p></div>'''
    calls = []
    def get(checked, identity, timeout):
        calls.append((checked, identity))
        return html
    monkeypatch.setattr(news, "_get_html", get)
    result = news.em_get(raw["Art_Url"], timeout=3)
    assert result["id"] == raw["Art_Code"] and result["title"] == raw["Art_Title"]
    assert result["published_at"] == clock.replace(" ", "T") + "+08:00"
    assert result["source_name"] == source and result["author"] == author
    assert calls == [(raw["Art_Url"].replace("http:", "https:"), raw["Art_Code"])]
    monkeypatch.setattr(news, "_get_html", lambda *a: html.replace(raw["Art_Code"], "1"))
    with pytest.raises(SourceError, match="身份"):
        news.em_get(raw["Art_Url"], timeout=3)


def test_full_five_pages_with_captured_failure_page_return_requested_100(monkeypatch):
    from datetime import datetime, timedelta
    import json
    from pathlib import Path
    real_fifth = json.loads((Path(__file__).parent / "fixtures/news_eastmoney/routes_page_5.json").read_text(encoding="utf-8"))
    pages = []
    for page in range(1, 5):
        raw_rows = []
        for index in range((page - 1) * 20, page * 20):
            identity = str(100000000000000000 + index)
            raw_rows.append({"Art_Code": identity, "Art_Title": "分页回归记录",
                "Art_ShowTime": (datetime(2026, 10, 8, 20) - timedelta(minutes=index)).strftime("%Y-%m-%d %H:%M:%S"),
                "Art_Url": f"https://finance.eastmoney.com/a/{identity}.html"})
        pages.append({"code": 1, "data": {"page_index": page, "page_size": 20,
            "totle_hits": real_fifth["data"]["totle_hits"], "list": raw_rows}})
    pages.append(real_fifth)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return pages[len(calls) - 1]
    monkeypatch.setattr(news, "get_json", get)
    result = news.em_list("300308", limit=100, since="2026-09-01", until="2026-10-08", timeout=3)
    assert len(result) == 100 and len(calls) == 5
    assert [row["id"] for row in result[80:]] == [row["Art_Code"] for row in real_fifth["data"]["list"]]
    assert all(row["url"] == raw["Art_Url"] for row, raw in zip(result[80:], real_fifth["data"]["list"]))
    assert {raw["Art_Url"] for raw in _ROWS}.issubset({row["url"] for row in result})


@pytest.mark.parametrize("raw", _ROWS)
def test_get_http_reader_tracks_confirmed_redirect_and_final_page_identity(monkeypatch, raw):
    from email.message import Message
    final = f'https://finance.eastmoney.com/a/{raw["Art_Code"]}.html'
    html = f'''<script>var _NewsId='{raw["Art_Code"]}'</script>
    <div id="topbox"><div class="title">{raw["Art_Title"]}</div><div class="infos">
    <div class="item">2026年09月28日 19:59</div></div></div>
    <div id="ContentBody"><p>构造的正文结构回归</p></div>'''
    calls = []
    class Response:
        status = 200
        headers = Message()
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return final
        def read(self): return html.encode()
    class Opener:
        def __init__(self, handler): self.handler = handler
        def open(self, request, timeout):
            redirected = self.handler.redirect_request(request, None, 302, "Found", {}, final)
            calls.append((request.full_url, redirected.full_url))
            return Response()
    monkeypatch.setattr(news, "build_opener", lambda handler: Opener(handler))
    result = news.em_get(raw["Art_Url"], timeout=3)
    assert result["id"] == raw["Art_Code"]
    assert calls == [(raw["Art_Url"].replace("http:", "https:"), final)]
    final = 'https://finance.eastmoney.com/a/1.html'
    with pytest.raises(SourceError, match="身份"):
        news.em_get(raw["Art_Url"], timeout=3)
