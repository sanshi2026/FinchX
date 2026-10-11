"""目录业务链接与单篇正文支持范围独立，未知编号空间不臆断。"""

import pytest
from urllib.parse import SplitResult

from finchx._common.errors import SourceError
from finchx.sources.eastmoney import news

# 全量审计中第27/41页的真实失败目录行，保留来源标题/时间/编号。
_ROWS = [
    {"Art_ShowTime": "2026-09-07 09:08:43", "Art_Code": "202609073866214095", "Np_dst": "CMS",
     "Art_Title": "高盛：首次覆盖中际旭创H股并给予目标价3267港元 业绩预测超市场预期",
     "Art_Url": "http://hk.eastmoney.com/a/202609073866214095.html"},
    {"Art_ShowTime": "2026-08-31 07:59:12", "Art_Code": "202608303859519160", "Np_dst": "CMS",
     "Art_Title": "莫把牛散神化", "Art_Url": "http://biz.eastmoney.com/a/202608303859519160.html"},
]


@pytest.mark.parametrize("raw", _ROWS)
def test_verified_hk_biz_directory_and_detail_routes(raw):
    row, _ = news._parse_row(raw)
    assert row["id"] == raw["Art_Code"] and row["url"] == raw["Art_Url"]
    assert news._article_url(raw["Art_Url"]) == (raw["Art_Code"], raw["Art_Url"].replace("http:", "https:"))


@pytest.mark.parametrize("url", [
    "https://news.example.org/story/another-number-7?from=source#body",
    "https://finance.eastmoney.com/news/11791,7.html",
    "https://finance.eastmoney.com/mobile/another-id?origin=1#read",
    "https://unknown.eastmoney.com/a/7.html", "https://news.example.org:8443/story/7",
    "https://finance.eastmoney.com:443/a/202609073866214095.html?from=feed#content",
    "http://[::1]:8080/story/7", "https://news.example.org",
])
def test_directory_keeps_valid_business_url_without_get_or_number_guess(monkeypatch, url):
    raw = {**_ROWS[0], "Art_Url": url}
    payload = {"code": 1, "data": {"page_index": 1, "page_size": 20, "totle_hits": 1, "list": [raw]}}
    monkeypatch.setattr(news, "get_json", lambda *a, **k: payload)
    monkeypatch.setattr(news, "_get_html", lambda *a, **k: pytest.fail("目录不可抓正文"))
    result = news.em_list("300308", limit=1000, since="2026-09-01", until="2026-10-08", timeout=1)
    assert result[0]["id"] == raw["Art_Code"] and result[0]["url"] == url
    with pytest.raises(ValueError):
        news.em_get(url, timeout=1)


@pytest.mark.parametrize("host,path", [("finance.eastmoney.com", "/a/1.html"),
    ("stock.eastmoney.com", "/a/1.html"), ("money.eastmoney.com", "/a/1.html"),
    ("insurance.eastmoney.com", "/a/1.html"), ("hk.eastmoney.com", "/a/1.html"),
    ("biz.eastmoney.com", "/a/1.html"), ("caifuhao.eastmoney.com", "/news/1")])
def test_known_route_mismatched_id_still_fails_with_port_query_fragment(host, path):
    raw = {**_ROWS[0], "Art_Url": f"https://{host}:443{path}?from=source#body"}
    with pytest.raises(SourceError, match="身份冲突"):
        news._parse_row(raw)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://news.example.org/story/1",
    "//news.example.org/story/1", "https:///story/1", "https://news.example.org:bad/story/1",
    "https://news.example.org:70000/story/1", "https://news.example.org:/story/1",
    "https://user:password@news.example.org/story/1", "https://user@news.example.org/story/1",
    "https://news.example.org/story/1\n", "https://news.example.org/with space", "https://news.example.org/with\u00a0space",
    "https://news.example.org/with\x7fcontrol", "https://news.example.org/\\story", "https://[invalid]/story/1",
    "https://news..example.org/story/1", "https://news%2eexample.org/story/1", False])
def test_invalid_directory_business_url_still_fails(url):
    with pytest.raises(SourceError):
        news._parse_row({**_ROWS[0], "Art_Url": url})


@pytest.mark.parametrize("authority", ["[invalid]", "[127.0.0.1]", "[::gg]", "[v1.]", "[vQ.future]",
    "[V1.future]", "prefix[::1]", "[::1]suffix", "[::1]:80:90", "[invalid]:8080", "[v1.a:b]"])
def test_invalid_bracketed_directory_host_without_urlsplit_checks(monkeypatch, authority):
    # 包括已核不支持的含冒号 IPvFuture；不扩大目录原有接受范围。
    monkeypatch.setattr(news, "urlsplit", lambda value: SplitResult("https", authority, "/story/1", "source=0", ""))
    with pytest.raises(SourceError):
        news._parse_row({**_ROWS[0], "Art_Url": f"https://{authority}/story/1?source=0"})


@pytest.mark.parametrize("authority", ["[::1]", "[2001:db8::1]:443", "[::ffff:192.0.2.1]:08080",
    "[fe80::1%eth0]:8080", "[v1.future]", "[vf.future]:8080"])
def test_legal_bracketed_directory_host_without_urlsplit_checks(monkeypatch, authority):
    monkeypatch.setattr(news, "urlsplit", lambda value: SplitResult("https", authority, "/story/1", "source=0", ""))
    url = f"https://{authority}/story/1?source=0"
    result, _ = news._parse_row({**_ROWS[0], "Art_Url": url})
    assert result["url"] == url


@pytest.mark.parametrize("raw", _ROWS)
def test_hk_biz_get_still_enforces_redirect_and_page_identity(monkeypatch, raw):
    from urllib.request import Request
    request = Request(raw["Art_Url"].replace("http:", "https:"))
    handler = news._Redirect(raw["Art_Code"])
    target = f'https://finance.eastmoney.com/a/{raw["Art_Code"]}.html'
    assert handler.redirect_request(request, None, 302, "Found", {}, target).full_url == target
    with pytest.raises(SourceError, match="身份"):
        handler.redirect_request(request, None, 302, "Found", {}, 'https://finance.eastmoney.com/a/1.html')
    monkeypatch.setattr(news, "_get_html", lambda *a: '<script>var _NewsId="1"</script>')
    with pytest.raises(SourceError, match="身份"):
        news.em_get(raw["Art_Url"], timeout=1)
