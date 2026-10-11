"""新浪公开页面节选与独立来源边界；不冒称现场 SDK 成功。"""

from pathlib import Path

import pytest

from finchx import SourceError
from finchx.sources.sina import report

URL = "https://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/search/rptid/843913684309/index.phtml"
FIXTURE = Path(__file__).parent / "fixtures" / "iwencai" / "sina-report-excerpt.html"
FIELDS = {"title", "publication_date", "institute", "researcher", "content", "original_url", "file_type"}


def mock_page(monkeypatch, markup):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if isinstance(markup, Exception):
            raise markup
        return markup
    monkeypatch.setattr(report, "get_text", get)
    return calls


def get(url=URL):
    return report.get_report(url, timeout=3)


def html(body="<p>第一段<br>下一行</p><p>第二段</p>", title="来源标题", metadata=""):
    heading = f"<h1>{title}</h1>" if title is not None else ""
    return f'<div class="content">{heading}{metadata}<div class="blk_container">{body}</div></div>'


def test_public_sina_excerpt_and_seven_fields_without_pdf_assumption(monkeypatch):
    calls = mock_page(monkeypatch, FIXTURE.read_text(encoding="utf-8"))
    result = get()
    assert set(result) == FIELDS
    assert result["title"] == "汽车行业：2026年上半年汽车行业运行态势、竞争格局及发展展望"
    assert result["publication_date"] == "2026-09-28"
    assert result["institute"] == "大公国际资信评估有限公司" and result["researcher"] == "许晨晨"
    assert result["content"].startswith("2026 年上半年，我国汽车行业整体呈现")
    assert "\n\n关键词：汽车；动能转换" in result["content"]
    assert result["original_url"] is None and result["file_type"] is None
    assert len(calls) == 1 and calls[0][0] == URL
    request = calls[0][1]
    assert request["encoding"] == "gbk" and request["follow_redirects"] is False
    assert request["timeout"] == 3 and "Cookie" not in request["headers"] and "Authorization" not in request["headers"]


def test_content_keeps_paragraphs_and_excludes_other_page_regions(monkeypatch):
    markup = ('<title>编辑过的网页标题</title><nav>导航</nav>' +
              html('<p>第一段<br />下一行</p><p>第二段<script>广告脚本</script></p>') +
              '<div class="share">分享</div><aside>数据推荐</aside><div class="content"><p>推荐研报</p></div>')
    mock_page(monkeypatch, markup)
    result = get()
    assert result["content"] == "第一段\n下一行\n\n第二段"
    assert result["title"] == "来源标题" and result["publication_date"] is None


@pytest.mark.parametrize("metadata", ["", '<div class="creab"><span>日期：</span><span>机构：</span></div>',
                                      '<div class="creab"><span>未知标签：新元信息</span></div>',
                                      '<div class="creab"><span>日期：2026-02-30</span></div>',
                                      '<div class="creab"><span>日期：09-28</span></div>'])
def test_optional_metadata_does_not_block_valid_body_or_forge_date(monkeypatch, metadata):
    mock_page(monkeypatch, html(metadata=metadata))
    result = get()
    assert result["content"] == "第一段\n下一行\n\n第二段"
    assert result["publication_date"] is None and result["institute"] is None and result["researcher"] is None


def test_optional_conflicting_metadata_becomes_none_without_blocking_content(monkeypatch):
    metadata = '<div class="creab"><span>机构：甲</span><span>机构：乙</span><span>研究员：来源研究员</span></div>'
    mock_page(monkeypatch, html(metadata=metadata))
    result = get()
    assert result["institute"] is None and result["researcher"] == "来源研究员"
    assert result["content"] is not None


def test_valid_body_does_not_require_optional_title_or_head_consistency(monkeypatch):
    mock_page(monkeypatch, '<title>无关页面标题</title>' + html(title=None))
    result = get()
    assert result["title"] is None and result["content"] is not None


@pytest.mark.parametrize("url", [URL.replace("https:", "http:"), URL.replace("/search/", "/industry/"),
                               URL.replace("/search/", "/future_kind/"), URL+"?from=search#report",
                               URL.replace("/search/", "/future.kind/"),
                               URL.replace(".cn/", ".cn:443/")])
def test_same_report_template_not_restricted_by_display_params_or_new_kind(monkeypatch, url):
    calls = mock_page(monkeypatch, html())
    assert get(url)["content"] is not None
    assert calls[0][0] == url


@pytest.mark.parametrize("url", [None, "", "843913684309", URL.replace("https:", "ftp:"),
                               URL.replace("stock.finance.sina.com.cn", "example.com"),
                               URL.replace("stock.finance.sina.com.cn", "u@stock.finance.sina.com.cn"),
                               URL.replace(".cn/", ".cn:8443/"), URL.replace("vReport_Show", "vReport_List"),
                               URL.replace("843913684309", "８４３９１３６８４３０９"), URL+"\n", URL+"?a=%00",
                               URL+"?a=%ZZ", URL.replace("/rptid/", "\\rptid/")])
def test_bad_input_route_or_transport_identity_rejected_before_fetch(monkeypatch, url):
    calls = mock_page(monkeypatch, html())
    with pytest.raises(ValueError):
        get(url)
    assert calls == []


@pytest.mark.parametrize("marker", ['<link rel="canonical" href="{url}">', '<meta property="og:url" content="{url}">'])
def test_verifiable_page_identity_conflict_fails(monkeypatch, marker):
    mock_page(monkeypatch, marker.format(url=URL.replace("843913684309", "123456789")) + html())
    with pytest.raises(SourceError, match="身份"):
        get()


def test_optional_same_identity_and_unverifiable_extra_meta_do_not_block_body(monkeypatch):
    mock_page(monkeypatch, '<link rel="canonical" href="'+URL.replace("/search/", "/industry/")+'">' +
              '<meta property="og:url" content="https://finance.sina.com.cn/">' + html())
    assert get()["content"] is not None


@pytest.mark.parametrize("markup", ["", '<html><h1>访问异常</h1>请稍后重试</html>',
                                  '<div class="blk_container"><p>缺少正确主体</p></div>',
                                  html(body=" "), html(body="<p>该研报已删除</p>"),
                                  html()+html(), html(body="<script>脚本内容</script>")])
def test_error_empty_or_ambiguous_page_not_mistaken_for_report(monkeypatch, markup):
    mock_page(monkeypatch, markup)
    with pytest.raises(SourceError):
        get()


def test_source_http_failure_propagates_without_retry_or_fallback(monkeypatch):
    failure = SourceError("sina", "HTTP 请求失败（状态码 302）")
    calls = mock_page(monkeypatch, failure)
    with pytest.raises(SourceError) as caught:
        get()
    assert caught.value is failure and len(calls) == 1
