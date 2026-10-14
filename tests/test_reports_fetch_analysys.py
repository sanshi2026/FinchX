"""易观原生搜索协议及自造正文边界，不将 fixture 当真实全文样本。"""

import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.analysys import reports

_FIXTURE = Path(__file__).parent / "fixtures/reports_fetch/analysys-search-shape.json"


@pytest.fixture
def payload():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _search(monkeypatch, payload, keyword="具身", cursor=1):
    calls = []

    def get_json(url, **kwargs):
        calls.append((url, kwargs))
        return payload

    monkeypatch.setattr(reports.http, "get_json", get_json)
    result = reports.search_page(keyword, cursor, timeout=12)
    return result, calls


def test_native_keyword_and_page_pass_through(monkeypatch, payload):
    keyword = "汽车 AI &增长"
    payload["keyword"] = keyword
    (rows, cursor), calls = _search(monkeypatch, payload, keyword, 2)
    assert parse_qs(urlsplit(calls[0][0]).query) == {"keyword": [keyword], "page": ["2"]}
    assert calls[0][1]["timeout"] == 12
    assert rows[0]["title"].startswith("破解具身")  # 搜索范围不限于标题。
    assert cursor == 3


def test_actual_newsdate_uses_beijing_not_publishdate(monkeypatch, payload):
    (rows, cursor), _ = _search(monkeypatch, payload)
    assert rows[0]["publication_date"] == "2026-10-09"
    payload["list"][0]["newsdate"] = 1791563400000  # UTC 10-09 16:30，即北京时间次日。
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["publication_date"] == "2026-10-10"
    assert cursor == 2  # 非空短页不假定耗尽。


def test_body_reused_and_copy_returned(monkeypatch, payload):
    (rows, _), _ = _search(monkeypatch, payload)
    row = rows[0]
    snapshot = copy.deepcopy(row)
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: pytest.fail("不应重复读取已有正文"))
    detail = reports.get_detail(row, timeout=3)
    assert detail == snapshot and detail is not row and row == snapshot
    assert detail["content_type"] == "webpage"
    assert "自造测试正文" in detail["content"]
    assert "https://www.analysys.cn/test/report.png" in detail["content"]
    assert "placeholder.gif" not in detail["content"]
    assert detail["pdf_urls"] == []
    assert detail["institute"] == "易观"


@pytest.mark.parametrize("body", [
    '<img data-src="/report/page1.jpg"><img src="//file1.analysys.cn/page2.jpg">',
    '<p>原文许可声明：转载须注明出处。</p><img src="images/page.jpg">',
])
def test_images_and_permission_text(monkeypatch, payload, body):
    payload["list"][0]["content"] = body
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["content_type"] == "webpage"
    assert "https://" in rows[0]["content"]
    if "许可" in body:
        assert "原文许可声明：转载须注明出处。" in rows[0]["content"]
    else:
        assert "https://file1.analysys.cn/page2.jpg" in rows[0]["content"]


def test_pdf_only_actual_body_anchors(monkeypatch, payload):
    payload["list"][0]["content"] = '''<p>正文</p>
      <a href="/files/report.PDF?download=1">实际附件</a>
      <a href="/files/report.PDF?download=1">重复</a>
      <a href="javascript:downloadPdf()">下载报告</a>
      <a href="https://boyue.analysys.cn/#/list">博阅</a>
      <script><a href="/fake.pdf">脚本中假附件</a></script>
      <img src="data:image/png;base64,aaa"><img><a href="/unknown">未知链接</a>'''
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["pdf_urls"] == ["https://www.analysys.cn/files/report.PDF?download=1"]
    assert "data:image" not in rows[0]["content"]
    assert "/fake.pdf" not in rows[0]["content"]


def test_missing_metadata_does_not_fabricate_from_author_or_publishdate(monkeypatch, payload):
    row = payload["list"][0]
    row.pop("source")
    row.pop("newsdate")
    row["author"] = "某分析师"
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["institute"] is None
    assert rows[0]["publication_date"] is None
    assert rows[0]["content"]


@pytest.mark.parametrize("title", [None, "", "   "])
def test_missing_or_empty_title_keeps_confirmed_identity_and_body(monkeypatch, payload, title):
    row = payload["list"][0]
    if title is None:
        row.pop("maintitle")
    else:
        row["maintitle"] = title
    (rows, cursor), _ = _search(monkeypatch, payload)
    assert rows[0]["title"] is None
    assert rows[0]["_id"] == "20021521"
    assert rows[0]["content"] and rows[0]["content_type"] == "webpage"
    assert cursor == 2


def test_empty_exhaustion_and_normal_duplicates(monkeypatch, payload):
    (rows, cursor), _ = _search(monkeypatch, {"list": [], "keyword": "具身"})
    assert rows == [] and cursor is None
    payload["list"] *= 2
    (rows, cursor), _ = _search(monkeypatch, payload)
    assert len(rows) == 2 and rows[0] == rows[1] and cursor == 2


@pytest.mark.parametrize("value", [None, [], {"keyword": "具身"}, {"list": {}, "keyword": "具身"}, {"list": [], "keyword": "其他"}])
def test_bad_search_response(monkeypatch, value):
    with pytest.raises(SourceError):
        _search(monkeypatch, value)


@pytest.mark.parametrize("field,value", [("id", None), ("id", True), ("id", "12x"), ("maintitle", []), ("content", []), ("newsdate", True), ("newsdate", float("nan")), ("newsdate", "2026-02-30 12:00:00"), ("source", {})])
def test_bad_necessary_or_present_fields(monkeypatch, payload, field, value):
    payload["list"][0][field] = value
    with pytest.raises(SourceError):
        _search(monkeypatch, payload)


def _detail_html(row):
    # 与已核正式页面一致的原生 JSON 初始状态，不执行脚本。
    state = {"article": quote(json.dumps(row, ensure_ascii=False)), "isError": False,
             "hotData": [{"id": 12, "maintitle": "推荐文章不作正文"}]}
    return '<nav>导航文字</nav><script>window.__INITIAL_STATE__= ' + json.dumps(state) + ';</script><footer>页脚</footer>'


def test_missing_search_body_reads_verified_same_id_detail(monkeypatch, payload):
    row = payload["list"][0]
    row["content"] = None
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["content"] is None and rows[0]["pdf_urls"] is None
    detail_row = {**row, "id": 20021521, "source": None,
                  "newsdate": "2026-10-09 18:18:50", "content": '<h2>标题</h2><p>正文</p><img src="/page.jpg">'}
    calls = []
    monkeypatch.setattr(reports.http, "get_text", lambda url, **kwargs: calls.append(url) or _detail_html(detail_row))
    detail = reports.get_detail(rows[0], timeout=5)
    assert calls == ["https://www.analysys.cn/article/detail/20021521"]
    assert detail["publication_date"] == "2026-10-09" and detail["institute"] == "易观"
    assert detail["content_type"] == "webpage" and "正文" in detail["content"]
    assert all(text not in detail["content"] for text in ("导航文字", "页脚", "推荐文章"))
    assert rows[0]["content"] is None


@pytest.mark.parametrize("html", ["<p>登录</p>", '<script>window.__INITIAL_STATE__= null;</script>', '<script>window.__INITIAL_STATE__= {"article":"bad"};</script>', _detail_html({"id": "99", "maintitle": "错目标", "content": "<p>正文</p>"}), _detail_html({"id": "20021521", "maintitle": "目标", "content": ""})])
def test_missing_or_conflicting_detail_fails(monkeypatch, payload, html):
    payload["list"][0]["content"] = None
    (rows, _), _ = _search(monkeypatch, payload)
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: html)
    with pytest.raises(SourceError):
        reports.get_detail(rows[0], timeout=5)


def _legacy_row(count=22):
    return {"id": 20021521, "maintitle": "自造旧版纯图报告", "content": "",
            "summary": "<p>来源原有摘要，不能当作图片内文字。</p>",
            "images": [{"path": f"/uploadcmsimages/2015/中文报告_{i}.jpg", "objectId": 3719,
                        "unused": {"管理字段": "不校验"}} for i in range(count)],
            "articleext1": [{"articleid": 20021521, "ename": "pdf", "text": "/uploadcmsimages/中文报告.pdf?download=1"},
                            {"articleid": 99, "ename": "swf", "text": "/unknown.swf"}]}


def _legacy_detail(monkeypatch, payload, row):
    payload["list"][0]["content"] = ""
    payload["list"][0].pop("summary", None)
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["pdf_urls"] is None
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: _detail_html(row))
    return reports.get_detail(rows[0], timeout=5)


@pytest.mark.parametrize("count", [22, 23])
def test_legacy_images_in_source_order_and_actual_same_id_pdf(monkeypatch, payload, count):
    detail = _legacy_detail(monkeypatch, payload, _legacy_row(count))
    expected = [f"![](https://www.analysys.cn/uploadcmsimages/2015/中文报告_{i}.jpg)" for i in range(count)]
    assert detail["content"].split("\n\n")[1:] == expected
    assert detail["content"].startswith("来源原有摘要")
    assert detail["content_type"] == "webpage"
    assert detail["pdf_urls"] == ["https://www.analysys.cn/uploadcmsimages/中文报告.pdf?download=1"]
    assert detail["_detail_read"] is True


def test_legacy_image_duplicates_not_repeated_and_missing_optional_fields(monkeypatch, payload):
    row = _legacy_row(1)
    row["images"] *= 2
    row.pop("summary")
    row.pop("articleext1")
    detail = _legacy_detail(monkeypatch, payload, row)
    assert detail["content"] == "![](https://www.analysys.cn/uploadcmsimages/2015/中文报告_0.jpg)"
    assert detail["pdf_urls"] == []


@pytest.mark.parametrize("value", [None, []])
def test_summary_only_has_summary_type(monkeypatch, payload, value):
    row = _legacy_row()
    row["images"] = value
    row.pop("articleext1")
    detail = _legacy_detail(monkeypatch, payload, row)
    assert detail["content"] == "来源原有摘要，不能当作图片内文字。"
    assert detail["content_type"] == "summary" and detail["pdf_urls"] == []


def test_pdf_only_is_confirmed_without_body(monkeypatch, payload):
    row = _legacy_row(0)
    row.pop("summary")
    detail = _legacy_detail(monkeypatch, payload, row)
    assert detail["content"] is None and detail["content_type"] is None
    assert len(detail["pdf_urls"]) == 1
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: pytest.fail("已确认附件不重复读详情"))
    assert reports.get_detail(detail, timeout=5) == detail


@pytest.mark.parametrize("field,value", [
    ("images", {}), ("images", [None]), ("images", [{"path": "javascript:fake()"}]),
    ("images", [{"path": ""}]), ("images", [{"path": "https://user:password@example.org/a.jpg"}]),
    ("images", [{"path": "https://example.org:bad/a.jpg"}]),
    ("articleext1", {}), ("articleext1", [None]),
    ("articleext1", [{"ename": "pdf", "articleid": 99, "text": "/a.pdf"}]),
    ("articleext1", [{"ename": "pdf", "articleid": 20021521, "text": None}]),
    ("summary", []),
])
def test_legacy_present_necessary_path_or_identity_damage_fails(monkeypatch, payload, field, value):
    row = _legacy_row(1)
    row[field] = value
    with pytest.raises(SourceError):
        _legacy_detail(monkeypatch, payload, row)


def test_legacy_absolute_and_page_relative_resources_and_nonpdf_not_guessed(monkeypatch, payload):
    row = _legacy_row(0)
    row["images"] = [{"path": "images/a.jpg?x=1"}, {"path": "//file1.analysys.cn/中文.jpg"}]
    row["articleext1"] = [{"ename": "pdf", "articleid": 20021521, "text": "https://example.org/中文.PDF?x=1&y=2"},
                         {"ename": "pdf", "articleid": 20021521, "text": "/login?file=a.pdf"},
                         {"ename": "other", "articleid": 99, "text": "/fake.pdf"},
                         {"ename": "swf", "text": "/fake.pdf"}]
    detail = _legacy_detail(monkeypatch, payload, row)
    assert "https://www.analysys.cn/article/detail/images/a.jpg?x=1" in detail["content"]
    assert "https://file1.analysys.cn/中文.jpg" in detail["content"]
    assert detail["pdf_urls"] == ["https://example.org/中文.PDF?x=1&y=2"]


def test_new_body_does_not_append_legacy_images_or_summary(monkeypatch, payload):
    row = payload["list"][0]
    row.update(images=[{"path": "/test/report.png"}, {"path": "/unused.jpg"}], summary="不追加摘要")
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["content"].count("/test/report.png") == 1
    assert "/unused.jpg" not in rows[0]["content"] and "不追加摘要" not in rows[0]["content"]
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: pytest.fail("既有新正文不加请求"))
    assert reports.get_detail(rows[0], timeout=3) == rows[0]


def test_legacy_search_images_without_attachment_field_still_reads_detail(monkeypatch, payload):
    row = _legacy_row(1)
    row.pop("articleext1")
    payload["list"] = [row]
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["content"] and rows[0]["pdf_urls"] is None and rows[0]["_detail_read"] is False
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: _detail_html(_legacy_row(1)))
    assert len(reports.get_detail(rows[0], timeout=5)["pdf_urls"]) == 1


def test_source_resource_spaces_are_encoded_without_filename_guess(monkeypatch, payload):
    row = _legacy_row(1)
    row["images"][0]["path"] = "/uploadcmsimages/中文 报告.jpg?x=a b"
    row["articleext1"][0]["text"] = "/uploadcmsimages/中文 报告.pdf?x=a b"
    detail = _legacy_detail(monkeypatch, payload, row)
    assert "https://www.analysys.cn/uploadcmsimages/中文%20报告.jpg?x=a%20b" in detail["content"]
    assert detail["pdf_urls"] == ["https://www.analysys.cn/uploadcmsimages/中文%20报告.pdf?x=a%20b"]


def test_legacy_resource_invalid_unicode_is_safe_source_error(monkeypatch, payload):
    row = _legacy_row(1)
    row["images"][0]["path"] = "/uploadcmsimages/坏\ud800.jpg"
    payload["list"][0]["content"] = ""
    (rows, _), _ = _search(monkeypatch, payload)
    state = {"article": quote(json.dumps(row, ensure_ascii=True)), "isError": False}
    html = '<script>window.__INITIAL_STATE__=' + json.dumps(state) + ';</script>'
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: html)
    with pytest.raises(SourceError, match="研报资源路径无效") as caught:
        reports.get_detail(rows[0], timeout=5)
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("attachments", [None, []])
@pytest.mark.parametrize("summary", [None, "列表只给摘要"])
def test_empty_search_attachments_still_requires_official_body(monkeypatch, payload, attachments, summary):
    row = {"id": 20021521, "maintitle": "列表标题", "content": "",
           "articleext1": attachments, "summary": summary}
    payload["list"] = [row]
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["pdf_urls"] is None and rows[0]["_detail_read"] is False
    calls = []
    official = {**row, "content": "<p>正式完整正文</p>"}
    monkeypatch.setattr(reports.http, "get_text", lambda url, **k: calls.append(url) or _detail_html(official))
    detail = reports.get_detail(rows[0], timeout=5)
    assert len(calls) == 1
    assert detail["content"] == "正式完整正文" and detail["content_type"] == "webpage"
    assert detail["pdf_urls"] == [] and detail["_detail_read"] is True


def test_search_actual_pdf_only_is_confirmed_and_not_read_twice(monkeypatch, payload):
    row = _legacy_row(0)
    row.pop("summary")
    payload["list"] = [row]
    (rows, _), _ = _search(monkeypatch, payload)
    assert rows[0]["_detail_read"] is True and len(rows[0]["pdf_urls"]) == 1
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: pytest.fail("实际PDF已确认"))
    assert reports.get_detail(rows[0], timeout=5)["content"] is None


def test_official_metadata_fields_recorded_even_when_equal_to_search(monkeypatch, payload):
    row = payload["list"][0]
    row["content"] = ""
    (rows, _), _ = _search(monkeypatch, payload)
    official = {**row, "content": "<p>正文</p>"}
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: _detail_html(official))
    detail = reports.get_detail(rows[0], timeout=5)
    assert detail["_detail_fields"] == ("title", "institute", "publication_date")
    assert all(detail[key] == rows[0][key] for key in detail["_detail_fields"])


def test_optional_search_metadata_fallback_not_marked_as_official(monkeypatch, payload):
    row = payload["list"][0]
    row["content"] = ""
    (rows, _), _ = _search(monkeypatch, payload)
    official = {"id": row["id"], "content": "<p>正文</p>"}
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: _detail_html(official))
    detail = reports.get_detail(rows[0], timeout=5)
    assert detail["_detail_fields"] == ()
    assert detail["institute"] == rows[0]["institute"]
    assert detail["publication_date"] == rows[0]["publication_date"]


def test_official_metadata_fields_only_mark_supplied_values(monkeypatch, payload):
    row = payload["list"][0]
    row["content"] = ""
    (rows, _), _ = _search(monkeypatch, payload)
    official = {"id": row["id"], "maintitle": "正式标题", "newsdate": "2015-01-02 12:00:00", "content": "<p>正文</p>"}
    monkeypatch.setattr(reports.http, "get_text", lambda *a, **k: _detail_html(official))
    detail = reports.get_detail(rows[0], timeout=5)
    assert detail["_detail_fields"] == ("title", "publication_date")
    assert detail["title"] == "正式标题" and detail["publication_date"] == "2015-01-02"
