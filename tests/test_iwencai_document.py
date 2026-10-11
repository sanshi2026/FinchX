"""通用正文行为回归；HTML 为明确的离线样本，不冒充联网返回。"""

from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from finchx._common.errors import SourceError
from finchx.sources.iwencai import _document as doc

FIELDS = {"title", "publication_date", "institute", "researcher", "content", "original_url", "file_type"}


def serve(monkeypatch, html, *, url="https://new-publisher.example/entry", content_type="text/html; charset=utf-8", encoding="utf-8"):
    calls = []
    def fetch(request_url, timeout):
        calls.append((request_url, timeout))
        return html.encode(encoding), content_type, url
    monkeypatch.setattr(doc, "_fetch", fetch)
    return calls


def test_wechat_final_verification_route_without_body_has_specific_error(monkeypatch):
    html = '<script>var PAGE_MID="mmbizwap:secitptpage/verify.html";</script><script src="https://captcha.gtimg.com/TCaptcha.js"></script><div>视频 小程序 赞 在看</div>'
    calls = serve(monkeypatch, html, url="https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?target_url=example")
    with pytest.raises(SourceError) as error:
        doc.read_document("https://mp.weixin.qq.com/s?mid=1", timeout=7)
    assert error.value.reason == "微信返回了访问验证页面，当前请求未取得文章正文"
    assert error.value.__suppress_context__ is True
    assert calls == [("https://mp.weixin.qq.com/s?mid=1", 7)]


@pytest.mark.parametrize("final_url", ["https://mp.weixin.qq.com/s?mid=1", "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha"])
def test_wechat_real_body_has_priority_even_with_verification_script(monkeypatch, final_url):
    html = '<script src="https://captcha.gtimg.com/TCaptcha.js"></script><div id="js_content"><p>这是真实正文。</p><p>最后一段完整保留。</p></div>'
    serve(monkeypatch, html, url=final_url)
    result = doc.read_document("https://mp.weixin.qq.com/s?mid=1", timeout=7)
    assert result["content"] == "这是真实正文。\n最后一段完整保留。"
    assert set(result) == FIELDS


@pytest.mark.parametrize("final_url", ["https://other.example/mp/wappoc_appmsgcaptcha", "https://mp.weixin.qq.com/s?mid=1", "https://mp.weixin.qq.com/mp/othercaptcha"])
def test_other_empty_routes_retain_generic_no_body_error(monkeypatch, final_url):
    serve(monkeypatch, '<script src="https://captcha.gtimg.com/TCaptcha.js"></script><div id="app"></div>', url=final_url)
    with pytest.raises(SourceError) as error:
        doc.read_document("https://new-publisher.example/entry", timeout=7)
    assert error.value.reason == doc._NO_BODY


@pytest.mark.parametrize("container", ["article", "main", 'div role="main"', 'div itemprop="articleBody"', 'div class="entry-content"', 'div id="unfamiliar-body"'])
def test_unknown_hosts_and_short_bodies_have_no_length_floor(monkeypatch, container):
    tag = container.split()[0]
    calls = serve(monkeypatch, f'<title>短公告</title><{container}><p>已完成签约。</p></{tag}>')
    result = doc.read_document("https://new-publisher.example/entry", timeout=7)
    assert result == dict(title="短公告", publication_date=None, institute=None, researcher=None,
                          content="已完成签约。", original_url=None, file_type=None)
    assert calls == [("https://new-publisher.example/entry", 7)]


def test_all_body_paragraphs_tables_inline_words_and_source_zero_are_preserved(monkeypatch):
    serve(monkeypatch, '<article><h1>报告</h1><p>第一<span>段</span>：0</p><p>第二段<br>后半段</p><table><tr><th>项目</th><th>值</th></tr><tr><td>收入</td><td>0</td></tr></table><p>末段完整。</p></article>')
    result = doc.read_document("https://unlisted.example/report", timeout=5)
    assert result["content"] == "报告\n第一段：0\n第二段\n后半段\n项目\t值\n收入\t0\n末段完整。"
    assert set(result) == FIELDS


def test_body_container_takes_priority_over_page_navigation_and_summary(monkeypatch):
    html = '<h1>真实标题</h1><nav><p>导航正文</p></nav><div class="article-content"><p>摘要...</p><div class="content_article"><p>公司代码：603982 公司简称：泉峰汽车</p><p>完整正文最后一段(下转516版)</p></div></div><aside>其他推荐</aside>'
    serve(monkeypatch, html)
    # The explicit inner body outranks its article wrapper, rather than clipping text.
    result = doc.read_document("http://paper.cnstock.com/html/a.htm", timeout=5)
    assert result["content"] == "公司代码：603982 公司简称：泉峰汽车\n完整正文最后一段(下转516版)"


def test_hexun_quick_body_not_truncated_abstract_comments_or_app_download(monkeypatch):
    html = '<h1>福田汽车与卓驭科技签署战略合作协议</h1><meta property="bytedance:published_time" content="2026-10-08T22:26:00+08:00"><div class="quick_abstract"><p>摘要...</p></div><div class="quick_content"><h2>快讯正文</h2><p>双方将在商用车高阶智能驾驶领域开展全方位、深度战略合作。</p><div class="quick_content_download">下载和讯APP查看快讯</div></div><div class="comments"><p>评论</p></div>'
    serve(monkeypatch, html, encoding="gb18030", content_type="text/html")
    result = doc.read_document("https://stock.hexun.com/a.html", timeout=5)
    assert result["content"] == "快讯正文\n双方将在商用车高阶智能驾驶领域开展全方位、深度战略合作。"
    assert result["publication_date"] == "2026-10-08T22:26:00+08:00"


def test_wechat_initial_hidden_content_is_read_without_js_or_image_download(monkeypatch):
    html = '<meta property="og:title" content="真实微信标题"><div id="js_content" style="visibility:hidden;opacity:0"><p>行业定义。</p><section><span>保留</span><strong>全部文字。</strong></section><img data-src="https://media.example/report-page.png"></div><div class="share"><p>分享</p></div>'
    serve(monkeypatch, html)
    result = doc.read_document("https://mp.weixin.qq.com/s?sn=public", timeout=5)
    assert result["title"] == "真实微信标题"
    assert result["content"] == "行业定义。\n保留全部文字。"
    assert result["original_url"] is None


def test_page_level_comment_feature_flag_does_not_hide_wechat_article(monkeypatch):
    serve(monkeypatch, '<body id="activity-detail" class="mm_appmsg comment_feature"><h1>真实文章</h1><div id="js_content"><p>真实正文。</p></div><div class="comment"><p>评论文本</p></div></body>')
    assert doc.read_document("https://mp.weixin.qq.com/s?sn=public", timeout=5)["content"] == "真实正文。"


@pytest.mark.parametrize("metadata", ['<meta property="article:published_time" content="无效日期">', '<time datetime="2026-10-09">修改时间</time>', '<meta itemprop="dateModified" content="2026-10-09">', '<meta name="date" content="2026-10-09">', '<meta name="dc.date" content="2026-10-09">'])
def test_optional_bad_or_modification_time_does_not_block_or_invent_publication(monkeypatch, metadata):
    serve(monkeypatch, metadata + '<article><p>仍可读取真实正文。</p></article>')
    result = doc.read_document("https://any-site.example/a", timeout=5)
    assert result["content"] == "仍可读取真实正文。"
    assert result["publication_date"] is None


@pytest.mark.parametrize("value,expected", [("2026-09-09", "2026-09-09"), ("2026-10-08 22:26", "2026-10-08T22:26+08:00"), ("2026-10-08T14:26:00Z", "2026-10-08T22:26:00+08:00")])
def test_explicit_publication_preserves_day_or_time_precision(monkeypatch, value, expected):
    serve(monkeypatch, f'<meta property="article:published_time" content="{value}"><article><p>正文。</p></article>')
    assert doc.read_document("https://new.example/a", timeout=5)["publication_date"] == expected


def test_sina_explicit_report_metadata_and_whole_body(monkeypatch):
    serve(monkeypatch, '<h1>真实研报标题</h1><div class="creab"><span>机构：国投证券股份有限公司</span><span>研究员：王华炳/王友舜</span><span>日期：2026-10-09</span></div><div class="blk_container"><p>完整段落。</p><p>最后段落。</p></div>')
    result = doc.read_document("https://stock.finance.sina.com.cn/any-real-page", timeout=5)
    assert (result["title"], result["institute"], result["researcher"], result["publication_date"]) == ("真实研报标题", "国投证券股份有限公司", "王华炳/王友舜", "2026-10-09")
    assert result["content"] == "完整段落。\n最后段落。"


@pytest.mark.parametrize("encoding,declaration", [("utf-8", '<meta charset="utf-8">'), ("gb18030", '<meta http-equiv="Content-Type" content="text/html; charset=gb2312">')])
def test_response_encoding_header_or_meta_is_respected(monkeypatch, encoding, declaration):
    serve(monkeypatch, declaration + '<article><p>中文完整：经营分析𠮷。</p></article>', encoding=encoding, content_type="text/html")
    assert doc.read_document("https://public.example/a", timeout=5)["content"] == "中文完整：经营分析𠮷。"


@pytest.mark.parametrize("html", [
    '<html><div id="app"></div><script>window.data="伪造正文"</script></html>',
    '<nav><p>新闻</p><p>研报</p></nav><aside><p>推荐</p></aside>',
    '<main><h1>用户登录</h1><form><input type="password"></form></main>',
    '<article><p>请登录后查看正文</p></article>',
    '<main><h1>安全验证</h1><p>请输入验证码</p></main>',
    '<main><p>点击下载报告</p><a href="report.exe">下载</a></main>',
    '<main><a href="news1">新闻一</a><a href="news2">新闻二</a></main>',
])
def test_login_verification_download_navigation_and_spa_are_not_body(monkeypatch, html):
    serve(monkeypatch, html)
    with pytest.raises(SourceError, match="可确认的可读正文"):
        doc.read_document("https://any-host.example/page", timeout=5)


@pytest.mark.parametrize("url", ["https://files.example/report.PDF", "https://files.example/get?fileName=report.pdf", 'https://files.example/get?bo=%7B%22fileName%22%3A%22%E5%85%AC%E5%91%8A.pdf%22%7D'])
def test_explicit_pdf_link_needs_no_request_or_download(monkeypatch, url):
    monkeypatch.setattr(doc, "_fetch", lambda *args: pytest.fail("PDF链接不应联网下载"))
    assert doc.read_document(url, timeout=5) == dict(title=None, publication_date=None, institute=None, researcher=None, content=None, original_url=url, file_type="pdf")


class Response:
    def __init__(self, body, *, url="https://redirected.example/article", content_type="text/html; charset=utf-8"):
        self.body = BytesIO(body)
        self.status = 200
        self.headers = {"Content-Type": content_type}
        self.url = url
        self.reads = []
        self.closed = False
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.closed = True
    def geturl(self):
        return self.url
    def read(self, size=-1):
        self.reads.append(size)
        return self.body.read(size)


def test_regular_redirect_result_on_another_public_host_is_allowed(monkeypatch):
    response = Response('<article><p>最终页面正文。</p></article>'.encode())
    calls = []
    def request(req, timeout):
        calls.append((req.full_url, timeout, dict(req.header_items())))
        return response
    monkeypatch.setattr(doc, "urlopen", request)
    result = doc.read_document("https://unknown.example/start?track=1#anchor", timeout=6)
    assert result["content"] == "最终页面正文。"
    assert response.closed
    assert calls[0][0:2] == ("https://unknown.example/start?track=1", 6)
    assert not any(k.lower() in {"cookie", "authorization"} for k in calls[0][2])


def test_pdf_content_type_is_closed_without_reading_bytes(monkeypatch):
    response = Response(b"%PDF-1.7", url="https://files.example/download/123", content_type="application/pdf")
    monkeypatch.setattr(doc, "urlopen", lambda *args, **kwargs: response)
    result = doc.read_document("https://new.example/download", timeout=5)
    assert result["original_url"] == response.url
    assert result["content"] is None and result["file_type"] == "pdf"
    assert response.reads == [] and response.closed


def test_pdf_magic_does_not_read_the_remaining_document(monkeypatch):
    response = Response(b"%PDF-1.7\n" + b"x" * 9000, content_type="application/octet-stream")
    monkeypatch.setattr(doc, "urlopen", lambda *args, **kwargs: response)
    assert doc.read_document("https://unknown.example/download", timeout=5)["file_type"] == "pdf"
    assert response.reads == [4096]


@pytest.mark.parametrize("exc", [URLError("network"), TimeoutError(), HTTPError("https://x.example", 403, "forbidden", {}, None)])
def test_native_http_failures_are_source_errors(monkeypatch, exc):
    def request(*args, **kwargs):
        raise exc
    monkeypatch.setattr(doc, "urlopen", request)
    with pytest.raises(SourceError):
        doc.read_document("https://public.example/a", timeout=5)


@pytest.mark.parametrize("url", [None, "", "ftp://example.com/a", "file:///tmp/a", "https://", "https://example.com/a b", "https://example.com/%broken", "https://example.com:70000/a"])
def test_invalid_url_is_input_error(url):
    with pytest.raises(ValueError):
        doc.read_document(url, timeout=5)


def test_explicit_body_pdf_link_is_returned_without_fetching_attachment(monkeypatch):
    calls = serve(monkeypatch, '<article><p>真实摘要全文。</p><a href="../files/report.pdf">原文</a></article>', url="https://publisher.example/news/article.html")
    result = doc.read_document("https://publisher.example/news/article.html", timeout=5)
    assert result["original_url"] == "https://publisher.example/files/report.pdf"
    assert len(calls) == 1


OPERATE = '''<title>泉峰汽车(603982) 经营分析_F10_同花顺金融服务网</title>
<input id="stockCode" value="603982"><input id="marketId" value="17">
<div stat="operate_intro"><h2>主营介绍</h2><p>汽车关键零部件的研发、生产、销售。</p></div>
<div stat="operate_observe"><h2>董事会经营评述</h2><div class="m_tab">2026-06-30</div>
<div class="m_tab_content"><p>截断摘要...<a class="more">查看全部▼</a></p>
<p class="none">第一段完整。<br>真实最后一段。<a class="less">收起▲</a></p></div>
<div class="m_tab_content" style="display:none"><p>旧期间文本。</p></div></div>
<nav>股票行情导航</nav>'''
SPA = 'https://basic.10jqka.com.cn/astockpc/astockmain/index.html#/operate?code=603982&marketid=17&code_name=%E6%B3%89%E5%B3%B0%E6%B1%BD%E8%BD%A6'


def test_verified_operate_spa_maps_to_same_stock_full_public_business(monkeypatch):
    calls = []
    def fetch(url, timeout):
        calls.append(url)
        return ('<div id="app"></div>' if len(calls) == 1 else OPERATE).encode(), "text/html", url
    monkeypatch.setattr(doc, "_fetch", fetch)
    result = doc.read_document(SPA, timeout=5)
    assert calls == [SPA, "https://basic.10jqka.com.cn/603982/operate.html"]
    assert result["content"] == "主营介绍\n汽车关键零部件的研发、生产、销售。\n董事会经营评述\n第一段完整。\n真实最后一段。"
    assert result["publication_date"] is None
    assert set(result) == FIELDS


@pytest.mark.parametrize("bad", [OPERATE.replace('value="603982"', 'value="600000"'), OPERATE.replace('value="17"', 'value="33"')])
def test_mapped_operate_identity_conflict_is_not_another_company_body(monkeypatch, bad):
    monkeypatch.setattr(doc, "_fetch", lambda url, timeout: (('<div id="app"></div>' if url == SPA else bad).encode(), "text/html", url))
    with pytest.raises(SourceError, match="身份不一致"):
        doc.read_document(SPA, timeout=5)


def test_native_spa_body_takes_priority_over_old_mapping(monkeypatch):
    calls = serve(monkeypatch, '<main><p>当前原页面已提供正文。</p></main>', url=SPA)
    assert doc.read_document(SPA, timeout=5)["content"] == "当前原页面已提供正文。"
    assert len(calls) == 1


@pytest.mark.parametrize("container", ['article', 'div itemprop="articleBody"', 'div class="entry-content"'])
def test_explicit_body_may_consist_entirely_of_real_linked_text(monkeypatch, container):
    tag = container.split()[0]
    serve(monkeypatch, f'<{container}><a href="/reference">协议已签署，订单已生效。</a></{tag}>')
    assert doc.read_document("https://unlisted.example/a", timeout=5)["content"] == "协议已签署，订单已生效。"


@pytest.mark.parametrize("wrapper", [
    '<main><h1>报告下载</h1><a class="download" href="../report.pdf">点击下载PDF</a></main>',
    '<article><object type="application/pdf" data="../report.pdf"></object></article>',
    '<iframe src="../report.pdf"></iframe>',
    '<main><embed type="application/pdf" src="../report.pdf"></main>',
    '<main><p>点击下载报告</p><a href="../report.pdf">下载</a></main>',
])
def test_pdf_only_html_wrapper_returns_actual_link_without_attachment_request(monkeypatch, wrapper):
    calls = serve(monkeypatch, wrapper, url="https://publisher.example/news/wrapper.html")
    result = doc.read_document("https://publisher.example/news/wrapper.html", timeout=5)
    assert result == doc._pdf_result("https://publisher.example/report.pdf")
    assert len(calls) == 1


def test_multiple_pdf_downloads_or_recommended_document_is_not_arbitrarily_selected(monkeypatch):
    serve(monkeypatch, '<main><a href="one.pdf">下载</a><a href="two.pdf">下载</a></main><aside><article><p>推荐文章。</p></article><iframe src="recommended.pdf"></iframe></aside>')
    with pytest.raises(SourceError, match="可确认的可读正文"):
        doc.read_document("https://publisher.example/downloads", timeout=5)


def test_jsonld_actual_article_body_is_a_text_source_not_executable_js(monkeypatch):
    serve(monkeypatch, '<div id="app"></div><script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"NewsArticle","headline":"短新闻","datePublished":"2026-10-09","articleBody":"正文第一句。\\n正文末句。"}]}</script><script>document.write("不能执行")</script>')
    result = doc.read_document("https://unlisted.example/news", timeout=5)
    assert result["title"] == "短新闻"
    assert result["publication_date"] == "2026-10-09"
    assert result["content"] == "正文第一句。\n正文末句。"


def test_jsonld_description_alone_is_not_full_article_body(monkeypatch):
    serve(monkeypatch, '<div id="app"></div><script type="application/ld+json">{"@type":"Article","description":"仅有摘要"}</script>')
    with pytest.raises(SourceError, match="可确认的可读正文"):
        doc.read_document("https://unlisted.example/news", timeout=5)


def test_pdf_download_child_cannot_replace_actual_parent_article_body(monkeypatch):
    serve(monkeypatch, '<article><p>这是文章真实正文，应优先保留。</p><div class="entry-content"><a href="report.pdf">下载</a></div></article>', url="https://publisher.example/news")
    result = doc.read_document("https://publisher.example/news", timeout=5)
    assert result["content"] == "这是文章真实正文，应优先保留。\n下载"
    assert result["original_url"] == "https://publisher.example/report.pdf"


@pytest.mark.parametrize("code,market", [("920510", "151"), ("603922", "22")])
def test_operate_mapping_retains_beijing_and_st_markets_without_prefix_filter(monkeypatch, code, market):
    url = f'https://basic.10jqka.com.cn/astockpc/astockmain/index.html#/operate?code={code}&marketid={market}'
    html = OPERATE.replace('value="603982"', f'value="{code}"').replace('value="17"', f'value="{market}"')
    monkeypatch.setattr(doc, "_fetch", lambda u, timeout: (('<div id="app"></div>' if u == url else html).encode(), "text/html", u))
    assert doc.read_document(url, timeout=5)["content"].endswith("真实最后一段。")
