"""研报真实响应复放与分页、独立摘要的必要失败边界。"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from finchx._common.errors import SourceError
from finchx.sources.aigupiao import reports

FIXTURES = Path(__file__).parent / "fixtures" / "reports"
LIST_FIELDS = {"url", "title", "kind", "ref_code", "name", "institute", "rating",
               "publication_date_text", "recorded_at", "symbol", "theme_id"}
DETAIL_FIELDS = {"title", "publication_date", "institute", "researcher", "summary", "pdf_urls"}
PDF = "https://pdf.dfcfw.com/pdf/H3_AP202610091830233038_1.pdf?1791532375000.pdf"


def listing():
    return json.loads((FIXTURES / "list-all.json").read_text(encoding="utf-8"))


def row(identity, position, **changes):
    value = deepcopy(listing()["data"][0])
    value.update(inv_id=identity, sort_time=position, **changes)
    return value


def envelope(rows, **changes):
    value = {"code": 0, "status": "succ", "inv_url": reports._DETAIL,
             "total": len(rows), "last_page": 1, "data": rows}
    value.update(changes)
    return value


@pytest.mark.parametrize("change", [{"code": False}, {"code": "0"}, {"status": "success"},
                                     {"inv_url": "https://example.org/?id="}, {"total": None},
                                     {"last_page": False}, {"data": {}}, {"data": [None]}])
def test_bad_envelope_is_failure_not_empty(monkeypatch, change):
    payload = envelope([row(1, 100)], **change)
    with pytest.raises(SourceError):
        reports._page(payload, before=0, kind="all", industry=None)


@pytest.mark.parametrize("changes", [{"inv_id": True}, {"inv_id": "１２"}, {"inv_id": None},
                                      {"sort_time": False}, {"sort_time": -1},
                                      {"rating": float("nan")}, {"rating": []}, {"rating": True},
                                      {"theme_id": False}, {"theme_id": -1}, {"theme_id": {}},
                                      {"pub_time": "2026-02-30"}, {"pub_time": "13-09"},
                                      {"pub_time": 0}, {"rec_time": "2026-10-09T00:40Z"},
                                      {"rec_time": "2026-02-30T00:40:02.000Z"},
                                      {"rec_time": "2026-10-09T00:40:02"},
                                      {"ref_symbol": False}, {"stock_code": []}])
def test_bad_known_leaf_fails_entire_page(monkeypatch, changes):
    item = row(1, 100)
    item.update(changes)
    payload = envelope([item])
    with pytest.raises(SourceError):
        reports._page(payload, before=0, kind="all", industry=None)


def test_missing_zero_empty_and_unknown_fields_are_distinct(monkeypatch):
    item = row(1, 100, rating=0, theme_id=0, title="", pub_time=None, rec_time=None,
               unknown={"future": False})
    item.pop("name")
    payload = envelope([item])
    result = reports._page(payload, before=0, kind="all", industry=None)[0][2]
    assert result["rating"] == 0 and result["theme_id"] == 0 and result["title"] == ""
    assert result["name"] is result["publication_date_text"] is result["recorded_at"] is None
    assert set(result) == LIST_FIELDS


@pytest.mark.parametrize("time,expected", [
    ("2026-10-09T00:40:02Z", "2026-10-09T08:40:02+08:00"),
    ("2026-10-09T00:40:02.0Z", "2026-10-09T08:40:02.0+08:00"),
    ("2026-10-09T00:40:02.123456789Z", "2026-10-09T08:40:02.123456789+08:00"),
    ("2026-12-31T20:40:02.000Z", "2027-01-01T04:40:02.000+08:00")])
def test_recorded_time_retains_exact_fraction_precision(time, expected):
    assert reports._recorded(time) == expected


@pytest.mark.parametrize("identity,institute,researcher,publication", [
    ("2477185", "华龙证券", "李浩洋", "2026-10-09"),
    ("2477179", "华鑫证券", "任春阳", "2026-10-09"),
    ("2477158", "开源证券", "齐东,胡耀文", "2026-10-08")])
def test_three_real_html_details_independent_metadata_summary_and_original_pdf(monkeypatch, identity, institute, researcher, publication):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return (FIXTURES / f"detail-{identity}.html").read_text(encoding="utf-8")
    monkeypatch.setattr(reports, "get_text", get)
    result = reports._get_detail(reports._DETAIL + identity, timeout=9)
    assert set(result) == DETAIL_FIELDS
    assert (result["institute"], result["researcher"], result["publication_date"]) == (institute, researcher, publication)
    assert result["summary"] and "研究机构：" not in result["summary"]
    assert "查看研报原文" not in result["summary"]
    assert len(result["pdf_urls"]) == 1 and result["pdf_urls"][0].endswith(".pdf")
    assert "?" in result["pdf_urls"][0]
    assert calls == [(reports._DETAIL + identity, {"timeout": 9.0,
                     "headers": {**reports._HEADERS, "Accept": "text/html,application/xhtml+xml"},
                     "source": "aigupiao", "follow_redirects": False})]
    if identity == "2477179":
        assert result["pdf_urls"] == [PDF]


@pytest.mark.parametrize("url", ["2477185", None, {}, " " + reports._DETAIL + "1",
                                 reports._DETAIL + "1\n", reports._DETAIL + "1#fragment",
                                 reports._DETAIL + "1#", reports._DETAIL + "1&",
                                 reports._DETAIL + "%31", reports._DETAIL.replace("id=", "%69d=") + "1",
                                 reports._DETAIL + "1&id=2", reports._DETAIL + "1&redirect=other",
                                 reports._DETAIL + "１２", reports._DETAIL.replace("http:", "https:") + "1",
                                 reports._DETAIL.replace(":82", "") + "1",
                                 reports._DETAIL.replace("101.35.29.159", "user@101.35.29.159") + "1",
                                 "https://pdf.dfcfw.com/pdf/H3_AP20261009_1.pdf",
                                 reports._DETAIL.replace("detail_m", "detail") + "1",
                                 reports._DETAIL + "1\\other", reports._DETAIL.replace("report", "rep\tort") + "1"])
def test_unsafe_or_unverified_detail_input_stops_before_io(monkeypatch, url):
    monkeypatch.setattr(reports, "get_text", lambda *args, **kwargs: pytest.fail("unsafe URL was accessed"))
    with pytest.raises(ValueError):
        reports._get_detail(url, timeout=1)


def html_detail(body, views="", head=""):
    return f"<html><head>{head}</head><body><div class='text01'>{body}</div>{views}<div class='column01'>推荐不应入正文</div></body></html>"


def test_metadata_separate_from_sections_and_table_text():
    page = html_detail("<h2>报告标题</h2><span>研究机构：机构 研究员：甲、乙 发布时间：2026-10-09</span>"
                       "<h2>2026-10-08章节</h2><p>第一段<br>第二行</p><script>坏正文</script>"
                       "<table><tr><th>科目</th><th>值</th></tr><tr><td>收入</td><td>0</td></tr></table>")
    result = reports._detail(page, url=reports._DETAIL + "1", identity="1")
    assert result["title"] == "报告标题" and result["researcher"] == "甲、乙"
    assert result["summary"] == "2026-10-08章节\n第一段\n第二行\n科目\t值\n收入\t0"
    assert result["pdf_urls"] == []


def test_pdf_only_without_nonbusiness_script_is_valid_and_relative_pdf_resolved():
    views = f"<div class='View_tex'><a href='{PDF}'>原文</a><a href='{PDF}'>重复</a><a href='/pdf/relative.pdf?q=0'>其他</a></div>"
    page = "<html><title>独立页面标题</title>" + views + "</html>"
    result = reports._detail(page, url=reports._DETAIL + "1", identity="1")
    assert result == {"title": "独立页面标题", "publication_date": None, "institute": None,
                      "researcher": None, "summary": None,
                      "pdf_urls": [PDF, "http://101.35.29.159:82/pdf/relative.pdf?q=0"]}


@pytest.mark.parametrize("page", ["<html>访问受限</html>", html_detail(""),
                                    html_detail("<h2>标题</h2><span>机构：机构</span>"),
                                    html_detail("摘要", "<div class='View_tex'><a href='javascript:alert(1)'>PDF</a></div>"),
                                    html_detail("摘要", "<div class='View_tex'><a href='https://u:p@example.org/a.pdf'>PDF</a></div>"),
                                    html_detail("<p>日期：2026-02-30</p><p>摘要</p>"),
                                    html_detail("<span>机构：甲</span><span>研究机构：乙</span><p>摘要</p>"),
                                    html_detail("摘要", head="<script src='https://app.aigupiao.com/goapi/report/add_read_records?inv_id=2'></script>")])
def test_broken_or_conflicting_detail_is_visible_failure(page):
    with pytest.raises(SourceError):
        reports._detail(page, url=reports._DETAIL + "1", identity="1")


def test_detail_metadata_never_borrows_list_values():
    result = reports._detail(html_detail("<p>只提供摘要</p>"), url=reports._DETAIL + "1", identity="1")
    assert result == {"title": None, "publication_date": None, "institute": None,
                      "researcher": None, "summary": "只提供摘要", "pdf_urls": []}


@pytest.mark.parametrize("text", ["20240229", "20261009", "2024-02-29", "02-29"])
def test_catalog_full_or_partial_date_preserves_source_text(text):
    result = reports._page(envelope([row(1, 100, pub_time=text)]),
                           before=0, kind="all", industry=None)[0][2]
    assert result["publication_date_text"] == text


@pytest.mark.parametrize("text", ["20230229", "20240230", "20261301", "00000229"])
def test_catalog_compact_invalid_calendar_day_is_source_error(text):
    with pytest.raises(SourceError, match="pub_time"):
        reports._page(envelope([row(1, 100, pub_time=text)]),
                      before=0, kind="all", industry=None)
