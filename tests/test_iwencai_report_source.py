"""匿名研报来源契约测试；构造数据与真实短节选明确区分。"""

import json
from pathlib import Path

import pytest

from finchx import SourceError
from finchx.sources.iwencai import report as source

BASE = "https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html"
UID = "d9924066929303a3"


def document():
    return {"status_code": 0, "data": {"site_url": None, "wordData": {
        "UID": UID, "title": "构造标题", "content": "第一段\r\n\r\n第二段", "pubtime": "2026-09-09",
        "organize": "构造机构", "researcher": "构造研究员", "ext": "pdf", "path": "不组装PDF",
    }}}


def replay(monkeypatch, payload):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return payload
    monkeypatch.setattr(source.http, "post_form_json", request)
    return calls


def report(url=BASE + "?duid=" + UID):
    return source.get_report(url, timeout=2)


@pytest.mark.parametrize("url", [BASE + "?duid=" + UID, BASE + "?from=search&duid=" + UID,
                               BASE + "?duid=" + UID + "#section",
                               BASE + "#/?duid=" + UID, BASE + "?from=search#/report?duid=" + UID,
                               BASE.replace("https:", "http:") + "?duid=" + UID])
def test_supported_query_and_fragment_url_same_identity_seven_fields(monkeypatch, url):
    calls = replay(monkeypatch, document())
    assert report(url) == {"title": "构造标题", "publication_date": "2026-09-09", "institute": "构造机构",
                           "researcher": "构造研究员", "content": "第一段\n\n第二段", "original_url": None, "file_type": "pdf"}
    endpoint, kwargs = calls[0]
    assert endpoint.endswith("/notice-detail") and len(calls) == 1
    assert kwargs["data"] == {"type": "report", "duid": UID, "query_source": "guide", "query": "*:*"}
    assert "Cookie" not in kwargs["headers"] and "Authorization" not in kwargs["headers"]
    assert kwargs["follow_redirects"] is False


def test_real_public_response_metadata_and_short_excerpt_replay(monkeypatch):
    # 来自 manifest 中匿名官方成功响应，仅保留公开短节选；不冒称 SDK 现场成功。
    data = {"status_code": 0, "status_msg": "ok", "data": {"site_url": None, "wordData": {
        "UID": UID, "title": "业绩持续高增，全球光互连龙头地位稳固", "pubtime": "2026-09-09",
        "organize": "天风证券", "researcher": "王奕红", "ext": "pdf",
        "content": "　　事件：公司发布2026年半年度报告，实现营业收入417.78亿元（YoY+182.49%），归母净利润136.51亿元（YoY+241.70%）。Q2实现营收222.81亿元，",
    }}}
    replay(monkeypatch, data)
    result = report()
    assert result["publication_date"] == "2026-09-09" and result["institute"] == "天风证券"
    assert result["original_url"] is None and result["file_type"] == "pdf"


@pytest.mark.parametrize("date,expected", [("2026-09-09", "2026-09-09"), ("2026-09-09 10:30", "2026-09-09T10:30+08:00"),
                                          ("2026-09-09 10:30:00", "2026-09-09T10:30:00+08:00"), (None, None)])
def test_source_date_and_time_precision_no_fallback(monkeypatch, date, expected):
    payload = document(); payload["data"]["wordData"]["pubtime"] = date
    payload["data"]["wordData"]["ctime"] = "2025-01-01"
    replay(monkeypatch, payload)
    assert report()["publication_date"] == expected


def test_optional_fields_missing_unknown_added_fields_and_native_link(monkeypatch):
    payload = {"errorCode": 0, "data": {"site_url": "https://example.com/source?x=1#f", "future": [],
               "wordData": {"UID": UID, "content": "来源文本", "ext": "doc", "new": []}}}
    replay(monkeypatch, payload)
    assert report() == {"title": None, "publication_date": None, "institute": None, "researcher": None,
                        "content": "来源文本", "original_url": "https://example.com/source?x=1#f", "file_type": "doc"}


@pytest.mark.parametrize("url", [UID, BASE+"?duid=",
                               BASE+"?duid="+UID+"&duid="+UID, BASE+"?duid="+UID+"#/?duid=other",
                               BASE+"?duid=a%0ab", BASE+"?duid=a%5Cb",
                               BASE+"?duid=a%ZZ", BASE+"?duid="+UID+"\n", BASE.replace("ms.", "x@ms.")+"?duid="+UID,
                               "https://example.com:bad/a"])
def test_reject_bad_urls_before_network(monkeypatch, url):
    calls = replay(monkeypatch, document())
    with pytest.raises(ValueError):
        report(url)
    assert calls == []


@pytest.mark.parametrize("value", ["another", UID+" ", None])
def test_snapshot_identity_conflict_never_falls_back(monkeypatch, value):
    payload = document(); payload["data"]["wordData"]["UID"] = value
    replay(monkeypatch, payload)
    monkeypatch.setattr(source, "_read_url", lambda *args: pytest.fail("不得读另一身份"))
    with pytest.raises(SourceError, match="身份"):
        report()


@pytest.mark.parametrize("field,value", [("title", 0), ("pubtime", "2026-02-30"),
                                         ("organize", []), ("researcher", False), ("ext", 0)])
def test_optional_metadata_damage_does_not_block_body(monkeypatch, field, value):
    payload = document(); payload["data"]["wordData"][field] = value
    replay(monkeypatch, payload)
    result = report()
    assert result["content"] == "第一段\n\n第二段"
    key = {"pubtime": "publication_date", "organize": "institute", "ext": "file_type"}.get(field, field)
    assert result[key] is None


@pytest.mark.parametrize("payload", [{}, {"status_code": 0, "data": None}, {"status_code": 0, "data": {"wordData": []}},
                                    {"status_code": 1, "data": {}}, {"status_code": False, "data": {}}])
def test_unavailable_snapshot_reads_source_url(monkeypatch, payload):
    replay(monkeypatch, payload)
    marker = {"content": "实际源网页正文"}
    calls = []
    monkeypatch.setattr(source, "_read_url", lambda url, seconds: calls.append((url, seconds)) or marker)
    assert report() is marker
    assert calls == [(BASE + "?duid=" + UID, 2)]


@pytest.mark.parametrize("content", [None, " ", [], False])
def test_snapshot_without_body_reads_true_original_link(monkeypatch, content):
    payload = document(); payload["data"]["wordData"]["content"] = content
    payload["data"]["site_url"] = "https://example.com/source.PDF"
    replay(monkeypatch, payload)
    calls = []
    marker = {"content": None, "file_type": "pdf"}
    monkeypatch.setattr(source, "_read_url", lambda url, seconds: calls.append(url) or marker)
    assert report() is marker
    assert calls == ["https://example.com/source.PDF"]


@pytest.mark.parametrize("channel", [None, "news", "announcement", "report"])
def test_native_report_route_overrides_search_channel_hint(monkeypatch, channel):
    calls = replay(monkeypatch, document())
    assert source.get_report(BASE + "?duid=" + UID, uid=UID, channel=channel, timeout=2)["content"]
    assert calls[0][1]["data"]["type"] == "report"


@pytest.mark.parametrize("hints", [{"uid": ""}, {"uid": 5}, {"uid": "中文"}, {"uid": "a b"},
                                  {"channel": "notice"}, {"channel": []}, {"uid": "different"}])
def test_invalid_hints_before_network(monkeypatch, hints):
    calls = replay(monkeypatch, document())
    with pytest.raises(ValueError):
        source.get_report(BASE + "?duid=" + UID, timeout=2, **hints)
    assert calls == []


@pytest.mark.parametrize("hints", [{}, {"uid": UID}, {"channel": "news"}, {"uid": UID, "channel": "news"},
                                  {"channel": "announcement"}])
def test_external_news_or_insufficient_hints_do_not_guess_native_type(monkeypatch, hints):
    calls = replay(monkeypatch, document())
    marker = {"content": "网页正文"}
    monkeypatch.setattr(source, "_read_url", lambda *args: marker)
    assert source.get_report("https://example.com/article?duid=" + UID, timeout=2, **hints) is marker
    assert calls == []


def test_real_public_notice_response_replay_prefers_text_snapshot_without_pdf(monkeypatch):
    payload = json.loads((Path(__file__).parent / "fixtures/iwencai_notice_detail.json").read_text(encoding="utf-8"))
    calls = replay(monkeypatch, payload)
    monkeypatch.setattr(source, "_read_url", lambda *args: pytest.fail("已有真实文字快照不读PDF"))
    word = payload["data"]["wordData"]
    result = source.get_report(word["URL"], uid=word["UID"], channel="announcement", timeout=2)
    assert result == {"title": word["title"], "publication_date": "2026-10-08", "institute": None,
                      "researcher": None, "content": word["content"].strip().replace("\r\n", "\n").replace("\r", "\n"),
                      "original_url": word["URL"], "file_type": None}
    assert calls[0][1]["data"]["type"] == "notice"
    assert len(result["content"]) > 1400


def test_official_findnote_link_identifies_notice_without_channel_guess(monkeypatch):
    payload = json.loads((Path(__file__).parent / "fixtures/iwencai_notice_detail.json").read_text(encoding="utf-8"))
    identity = payload["data"]["wordData"]["UID"]
    calls = replay(monkeypatch, payload)
    assert source.get_report("http://www.iwencai.com/viewswf/findnote/" + identity + ".html", channel="news", timeout=2)["content"]
    assert calls[0][1]["data"]["type"] == "notice"


def test_known_eastmoney_pdf_prefers_existing_notice_text(monkeypatch):
    from finchx.sources.eastmoney import disclosure
    from finchx.sources.iwencai import _document
    url = "https://pdf.dfcfw.com/pdf/H2_AN202610091234567890_1.pdf"
    calls = []
    monkeypatch.setattr(disclosure, "em_get", lambda url, **kw: calls.append((url, kw)) or
                        {"title": "来源标题", "notice_date": "2026-10-09", "content": "来源实际公告正文"})
    monkeypatch.setattr(_document, "read_document", lambda *args, **kw: pytest.fail("文字已取得，无需PDF后备"))
    result = source.get_report(url, timeout=2)
    assert result == {"title": "来源标题", "publication_date": "2026-10-09", "institute": None,
                      "researcher": None, "content": "来源实际公告正文", "original_url": url, "file_type": None}
    assert calls == [(url, {"timeout": 2})]


def test_sina_unsupported_legal_route_is_read_as_generic_html(monkeypatch):
    from finchx.sources.sina import report as sina
    from finchx.sources.iwencai import _document
    url = "https://stock.finance.sina.com.cn:8443/stock/go.php/vReport_Show/new-page"
    marker = {"content": "实际短正文"}
    monkeypatch.setattr(sina, "get_report", lambda *args, **kw: (_ for _ in ()).throw(ValueError("专用路由未知")))
    monkeypatch.setattr(_document, "read_document", lambda *args, **kw: marker)
    assert source.get_report(url, timeout=2) is marker


def test_sina_unreadable_body_error_remains_explicit(monkeypatch):
    from finchx.sources.sina import report as sina
    error = SourceError("sina", "没有可读正文")
    monkeypatch.setattr(sina, "get_report", lambda *args, **kw: (_ for _ in ()).throw(error))
    with pytest.raises(SourceError) as caught:
        source.get_report("https://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/search/rptid/123/index.phtml", timeout=2)
    assert caught.value is error


def test_external_pdf_url_only_returns_link_without_network(monkeypatch):
    from finchx.sources.iwencai import _document
    monkeypatch.setattr(_document, "_fetch", lambda *args: pytest.fail("已知PDF不下载"))
    url = "https://static.cninfo.com.cn/finalpage/2026-10-08/1225590407.PDF"
    assert source.get_report(url, timeout=2) == {
        "title": None, "publication_date": None, "institute": None, "researcher": None,
        "content": None, "original_url": url, "file_type": "pdf"}


@pytest.mark.parametrize("url", [BASE, BASE + "#section", BASE + "#duid=" + UID,
                               BASE + "?from=search#section"])
def test_native_path_without_explicit_duid_reads_actual_html_body(monkeypatch, url):
    from finchx.sources.iwencai import _document
    calls = replay(monkeypatch, document())
    monkeypatch.setattr(_document, "_fetch", lambda target, seconds:
                        ("<article><h1>来源标题</h1><p>来源实际正文</p></article>".encode(), "text/html;charset=utf-8", target))
    result = source.get_report(url, timeout=2)
    assert result["content"] == "来源标题\n来源实际正文"
    assert calls == []
