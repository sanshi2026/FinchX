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


def mock_pages(monkeypatch, pages):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        value = pages.pop(0)
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    monkeypatch.setattr(reports, "post_form_json", post)
    return calls


def test_real_list_preserves_business_fields_source_order_and_date_precision(monkeypatch):
    calls = mock_pages(monkeypatch, [listing()])
    result = reports.agp_list(timeout=4)
    assert len(result) == 20 and all(set(item) == LIST_FIELDS for item in result)
    assert result[0] == {"url": reports._DETAIL + "2477185",
                         "title": "汽车行业周报：“金九”车企销量分化，关注出海进展",
                         "kind": "industry", "ref_code": "000039", "name": "汽车行业",
                         "institute": "华龙证券", "rating": "推荐", "publication_date_text": "10-09",
                         "recorded_at": "2026-10-09T08:40:02.000+08:00", "symbol": "in000039", "theme_id": 950}
    assert result[3]["url"].endswith("2477179")  # 列表 id 实际为868297。
    assert result[3]["symbol"] == "sh603499" and result[3]["theme_id"] == 0
    assert result[6]["publication_date_text"] == "2026-10-08"
    assert result[7]["rating"] == ""
    assert calls[0][1]["data"] == {"before": 0, "kind": "all", "u_id": 0,
                                    "symbol": "", "limit": 20, "keyword": ""}
    assert calls[0][1]["timeout"] == 4 and "Cookie" not in calls[0][1]["headers"]


def test_complete_batch_then_limit_and_cross_page_replacement_keeps_first_position(monkeypatch):
    first = [row(1, 100), row(2, 100), row(3, 90)]
    second = [row(2, 80, title="后读更新"), row(4, 79), row(5, 79)]
    calls = mock_pages(monkeypatch, [envelope(first, total=20), envelope(second, total=9)])
    result = reports.agp_list(limit=5, timeout=3)
    assert [item["url"] for item in result] == [reports._DETAIL + str(i) for i in range(1, 6)]
    assert result[1]["title"] == "后读更新"
    assert [call[1]["data"]["before"] for call in calls] == [0, 90]


def test_short_page_is_not_exhaustion_and_empty_page_is(monkeypatch):
    calls = mock_pages(monkeypatch, [envelope([row(1, 100)]), envelope([row(2, 99)]), envelope([])])
    assert len(reports.agp_list(limit=20, timeout=2)) == 2
    assert [call[1]["data"]["before"] for call in calls] == [0, 100, 99]


def test_success_empty_page_does_not_need_an_unused_detail_url_template(monkeypatch):
    page = envelope([])
    page.pop("inv_url")
    mock_pages(monkeypatch, [page])
    assert reports.agp_list(timeout=1) == []


@pytest.mark.parametrize("template", [None, "", "absent"])
def test_nonempty_page_uses_verified_official_template_when_optional_inv_url_missing(monkeypatch, template):
    page = envelope([row(1, 100)], inv_url=template)
    if template == "absent":
        page.pop("inv_url")
    mock_pages(monkeypatch, [page])
    assert reports.agp_list(limit=1, timeout=1)[0]["url"] == reports._DETAIL + "1"


def test_extra_source_rows_not_trimmed_before_page_validation(monkeypatch):
    rows = [row(i + 1, 1000 - i) for i in range(23)]
    rows[-1]["rating"] = False
    mock_pages(monkeypatch, [envelope(rows)])
    with pytest.raises(SourceError, match="rating"):
        reports.agp_list(limit=1, timeout=1)


@pytest.mark.parametrize("values", [{"limit": True}, {"limit": 0}, {"limit": None}, {"limit": 1.5},
                                     {"kind": []}, {"kind": "user"}, {"keyword": 3},
                                     {"keyword": "a\x00b"}, {"keyword": "\ud800"},
                                     {"industry": 39}, {"kind": "stock", "industry": "汽车行业"}])
def test_invalid_parameters_fail_before_io(monkeypatch, values):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid parameter performed source I/O")
    monkeypatch.setattr(reports, "post_form_json", forbidden)
    monkeypatch.setattr(reports, "get_json", forbidden)
    with pytest.raises(ValueError):
        reports.agp_list(timeout=2, **values)


@pytest.mark.parametrize("industry", ["汽车行业", "000039", "  汽车行业  "])
def test_each_industry_call_reads_real_dictionary_then_exact_symbol(monkeypatch, industry):
    dictionary = json.loads((FIXTURES / "industry-dictionary.json").read_text(encoding="utf-8"))
    dictionaries = []
    def get(url, **kwargs):
        dictionaries.append((url, kwargs))
        return dictionary
    monkeypatch.setattr(reports, "get_json", get)
    calls = mock_pages(monkeypatch, [envelope([row(1, 100)]), envelope([row(2, 99)])])
    for _ in range(2):
        reports.agp_list(limit=1, keyword=" 汽车 ", industry=industry, timeout=7)
    assert len(dictionaries) == 2 and all(call[0] == reports._INDUSTRIES for call in dictionaries)
    assert all(call[1]["data"]["symbol"] == "000039" and call[1]["data"]["kind"] == "industry"
               and call[1]["data"]["keyword"] == "汽车" for call in calls)


@pytest.mark.parametrize("dictionary,industry", [
    ({"code": 0, "status": "succ", "list": [{"symbol": "000039", "name": "汽车行业"}]}, "39"),
    ({"code": 0, "status": "succ", "list": [{"symbol": "000039", "name": "同名"}, {"symbol": "000040", "name": "同名"}]}, "同名")])
def test_unknown_or_ambiguous_industry_stops_before_post(monkeypatch, dictionary, industry):
    monkeypatch.setattr(reports, "get_json", lambda *args, **kwargs: dictionary)
    calls = mock_pages(monkeypatch, [])
    with pytest.raises(ValueError):
        reports.agp_list(industry=industry, timeout=1)
    assert calls == []


@pytest.mark.parametrize("dictionary", [{"code": False, "status": "succ", "list": []},
                                          {"code": 0, "status": "succ", "list": []},
                                          {"code": 0, "status": "succ", "list": [{"symbol": 39, "name": "汽车行业"}]},
                                          {"code": 0, "status": "succ", "list": [{"symbol": "000039", "name": ""}]}])
def test_bad_industry_dictionary_is_source_failure(monkeypatch, dictionary):
    monkeypatch.setattr(reports, "get_json", lambda *args, **kwargs: dictionary)
    with pytest.raises(SourceError):
        reports.agp_list(industry="汽车行业", timeout=1)


@pytest.mark.parametrize("change", [{"code": False}, {"code": "0"}, {"status": "success"},
                                     {"inv_url": "https://example.org/?id="}, {"total": None},
                                     {"last_page": False}, {"data": {}}, {"data": [None]}])
def test_bad_envelope_is_failure_not_empty(monkeypatch, change):
    mock_pages(monkeypatch, [envelope([row(1, 100)], **change)])
    with pytest.raises(SourceError):
        reports.agp_list(limit=1, timeout=1)


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
    mock_pages(monkeypatch, [envelope([item])])
    with pytest.raises(SourceError):
        reports.agp_list(limit=1, timeout=1)


def test_missing_zero_empty_and_unknown_fields_are_distinct(monkeypatch):
    item = row(1, 100, rating=0, theme_id=0, title="", pub_time=None, rec_time=None,
               unknown={"future": False})
    item.pop("name")
    mock_pages(monkeypatch, [envelope([item])])
    result = reports.agp_list(limit=1, timeout=1)[0]
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


@pytest.mark.parametrize("pages", [
    [envelope([row(1, 100), row(1, 99)])],
    [envelope([row(1, 99), row(2, 100)])],
    [envelope([row(1, 100)]), envelope([row(2, 100)])],
    [envelope([row(1, 100)]), envelope([row(1, 99)])],
    [envelope([row(1, 0)])],
    [envelope([row(1, 100)]), SourceError("aigupiao", "拒绝访问")],
    [envelope([row(i + 1, 1000 - i) for i in range(101)])]])
def test_pagination_anomalies_never_return_partial(monkeypatch, pages):
    mock_pages(monkeypatch, pages)
    with pytest.raises(SourceError):
        reports.agp_list(limit=50, timeout=1)


def test_budget_is_failure(monkeypatch):
    monkeypatch.setattr(reports, "_MAX_PAGES", 1)
    mock_pages(monkeypatch, [envelope([row(1, 100)])])
    with pytest.raises(SourceError, match="防护"):
        reports.agp_list(limit=2, timeout=1)


@pytest.mark.parametrize("kind,industry", [("stock", None), ("industry", None), ("all", "汽车行业")])
def test_requested_filter_must_be_honored_by_source(monkeypatch, kind, industry):
    item = row(1, 100)
    if kind != "stock":
        item.update(ref_kind="stock", ref_symbol="603499")
    monkeypatch.setattr(reports, "get_json", lambda *args, **kwargs: json.loads((FIXTURES / "industry-dictionary.json").read_text(encoding="utf-8")))
    mock_pages(monkeypatch, [envelope([item])])
    with pytest.raises(SourceError):
        reports.agp_list(limit=1, kind=kind, industry=industry, timeout=1)


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
    result = reports.agp_get(reports._DETAIL + identity, timeout=9)
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
        reports.agp_get(url, timeout=1)


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
