"""易观独立入口的日期口径、原生分页和正式详情契约。"""

from datetime import date
import json
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import pytest

from finchx import SourceError
from finchx.sources.analysys import reports_single as source


def native(identity=1, **kwargs):
    return dict(id=identity, maintitle=f"标题{identity}", source="研究机构", publishdate="2026-10-10 12:34:56",
                content=f"<p>正文{identity}</p>", summary="原生摘要", columnid=8, **kwargs)


def detail_html(row):
    return "<script>window.__INITIAL_STATE__=" + json.dumps({"article": quote(json.dumps(row, ensure_ascii=False))}) + ";</script>"


def record(identity=1, **kwargs):
    row = native(identity)
    row.update(kwargs)
    return source._record(row)


def test_real_official_catalog_fixture_and_publishdate_not_newsdate(monkeypatch):
    fixture = Path(__file__).parent / "fixtures/reports_fetch/analysys-catalog.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    calls = []
    monkeypatch.setattr(source.http, "get_json", lambda url, **kw: calls.append((url, kw)) or payload)
    rows, cursor = source._page(None, 1, timeout=3)
    assert len(rows) == 10 and cursor == 2
    assert parse_qs(urlsplit(calls[0][0]).query) == {"p": ["1"], "columnId": ["8,22"]}
    assert calls[0][1]["timeout"] == 3
    assert rows[0]["publication_date"] == "2026-10-10"
    assert rows[0]["published_at"] == "2026-10-10T18:23:38+08:00"
    assert rows[0]["column_id"] == 22 and rows[0]["institute"] == "易观"
    assert rows[0]["author"] == "易观分析" and rows[0]["classify"] == "数字化分析"
    assert len(rows[0]) == 16 and list(rows[0]) == list(source._FIELDS)
    assert payload["list"][0]["newsdate"].startswith("2026-10-09")


@pytest.mark.parametrize("stamp,day,expected", [
    ("2026-10-10", "2026-10-10", "2026-10-10"),
    ("2026-10-10 01:02:03", "2026-10-10", "2026-10-10T01:02:03+08:00"),
    (None, None, None), ("", None, None),
])
def test_publication_preserves_source_precision_and_never_falls_back(stamp, day, expected):
    row = native()
    row.update(publishdate=stamp, newsdate="2099-01-01 00:00:00")
    result = source._record(row)
    assert result["publication_date"] == day and result["published_at"] == expected


@pytest.mark.parametrize("stamp", [True, 123, "2026-02-30", "2026-10-10 25:00:00", "10-10", " 2026-10-10"])
def test_invalid_present_publishdate_fails(stamp):
    with pytest.raises(SourceError):
        record(publishdate=stamp)


def test_search_native_keyword_and_short_page_needs_empty_end(monkeypatch):
    calls = []
    payload = {"keyword": "标题无此词", "list": [native()]}
    monkeypatch.setattr(source.http, "get_json", lambda url, **kw: calls.append(url) or payload)
    rows, cursor = source._page("标题无此词", 2, timeout=1)
    assert rows[0]["title"] == "标题1" and cursor == 3
    assert parse_qs(urlsplit(calls[0]).query) == {"keyword": ["标题无此词"], "page": ["2"]}
    payload["list"] = []
    assert source._page("标题无此词", 3, timeout=1) == ([], None)
    payload["keyword"] = "别的词"
    with pytest.raises(SourceError):
        source._page("标题无此词", 1, timeout=1)


@pytest.mark.parametrize("patch", [
    {"total": True}, {"total": -1}, {"pages": 2}, {"list": []},
    {"list": [native(), native()], "total": 2}, {"list": {}},
])
def test_catalog_rejects_objective_structure_or_count_damage(monkeypatch, patch):
    payload = {"list": [native()], "total": 1, "pages": 1}
    payload.update(patch)
    monkeypatch.setattr(source.http, "get_json", lambda *a, **k: payload)
    with pytest.raises(SourceError):
        source._page(None, 1, timeout=1)


def test_catalog_empty_and_last_page_do_not_include_hotdata(monkeypatch):
    payload = {"list": [], "total": 0, "pages": 0, "hotData": [native(99)]}
    monkeypatch.setattr(source.http, "get_json", lambda *a, **k: payload)
    assert source._page(None, 1, timeout=1) == ([], None)
    payload.update(list=[native()], total=1, pages=1)
    assert source._page(None, 1, timeout=1)[1] is None


def test_formal_detail_authority_missing_fallback_and_independent_summary(monkeypatch):
    candidate = record(publishdate="2026-10-09", author="作者", keywords="关键词", field="领域", firstField="一级")
    row = native()
    row.update(publishdate="2026-10-11 00:01:02", maintitle="正式标题", source="正式机构", summary="正式摘要", newsdate=True)
    monkeypatch.setattr(source.http, "get_text", lambda *a, **k: detail_html(row))
    result = source._detail(candidate, timeout=1)
    assert result["title"] == "正式标题" and result["institute"] == "正式机构"
    assert result["published_at"] == "2026-10-11T00:01:02+08:00"
    assert result["summary"] == "正式摘要" and result["content"] == "正文1"
    assert "正式摘要" not in result["content"]
    assert result["author"] == "作者" and result["keywords"] == "关键词"
    row.update(publishdate=None, maintitle=None, source=None)
    result = source._detail(candidate, timeout=1)
    assert result["title"] == candidate["title"] and result["published_at"] == "2026-10-09"


def test_legacy_images_and_same_article_pdf_are_actual_resources(monkeypatch):
    row = native()
    row.update(content=None, images=[{"path": "/pages/中文 图.jpg"}, {"path": "/pages/中文 图.jpg"}],
               articleext1=[{"articleid": 1, "ename": "pdf", "text": "/files/中文 报告.pdf"}])
    monkeypatch.setattr(source.http, "get_text", lambda *a, **k: detail_html(row))
    result = source._detail(record(), timeout=1)
    assert result["summary"] == "原生摘要"
    assert result["content"].count("![](") == 1
    assert "https://www.analysys.cn/pages/中文%20图.jpg" in result["content"]
    assert result["pdf_urls"] == ["https://www.analysys.cn/files/中文%20报告.pdf"]
    row["articleext1"][0]["articleid"] = 2
    with pytest.raises(SourceError):
        source._detail(record(), timeout=1)


def test_pure_image_and_pure_pdf_are_valid_without_ocr(monkeypatch):
    row = native()
    row.update(content="<img src='/body.jpg'>", summary=None)
    monkeypatch.setattr(source.http, "get_text", lambda *a, **k: detail_html(row))
    result = source._detail(record(), timeout=1)
    assert result["content"] == "![](https://www.analysys.cn/body.jpg)" and result["pdf_urls"] == []
    row.update(content=None, summary=None, articleext1=[{"articleid": 1, "ename": "pdf", "text": "/real.pdf"}])
    result = source._detail(record(), timeout=1)
    assert result["content"] is None and result["pdf_urls"] == ["https://www.analysys.cn/real.pdf"]


@pytest.mark.parametrize("body", ["<html>无正式状态</html>", "window.__INITIAL_STATE__={}",
                                   'window.__INITIAL_STATE__={"isError":true,"article":"%7B%7D"}',
                                   detail_html(native(2))])
def test_formal_identity_or_state_failure_is_strict(monkeypatch, body):
    monkeypatch.setattr(source.http, "get_text", lambda *a, **k: body)
    with pytest.raises(SourceError):
        source._detail(record(), timeout=1)


def install_pages(monkeypatch, pages, transform=None):
    calls, reads = [], []
    def page(keyword, cursor, *, timeout):
        calls.append((keyword, cursor))
        return pages[cursor]
    def detail(row, *, timeout):
        reads.append(row["report_id"])
        return transform(dict(row)) if transform else dict(row)
    monkeypatch.setattr(source, "_page", page)
    monkeypatch.setattr(source, "_detail", detail)
    return calls, reads


@pytest.mark.parametrize("keyword", [None, "", "   ", "  官方搜索词  "])
def test_two_modes_fixed_fields_and_limit_one_reads_only_selected(monkeypatch, keyword):
    calls, reads = install_pages(monkeypatch, {1: ([record(1), record(2, publishdate="2020-01-01")], 2)})
    result = source.analysys_fetch(1, keyword, timeout=2)
    assert calls == [("官方搜索词" if keyword and keyword.strip() else None, 1)]
    assert reads == ["1"] and len(result[0]) == 16


def test_group_all_copies_confirmed_before_return_and_regrouped(monkeypatch):
    def transform(row):
        if row["report_id"] == "2":
            row.update(content="更完整正文", pdf_urls=["https://example.org/real.pdf"])
        return row
    calls, reads = install_pages(monkeypatch, {1: ([record(1, maintitle="相同"), record(2, maintitle="相同"), record(3, maintitle="无关")], None)}, transform)
    rows = source.analysys_fetch(1, timeout=2)
    assert set(reads) == {"1", "2"} and rows[0]["report_id"] == "2"
    assert rows[0]["url"].endswith("/2") and len(rows[0]["pdf_urls"]) == 1


def test_selected_copy_formal_metadata_changes_business_key(monkeypatch):
    def transform(row):
        if row["report_id"] == "2":row["title"] = "正式独立标题"
        return row
    _, reads = install_pages(monkeypatch, {1: ([record(1, maintitle="相同"), record(2, maintitle="相同")], None)}, transform)
    rows = source.analysys_fetch(2, timeout=2)
    assert len(rows) == 2 and set(reads) == {"1", "2"}


def test_formal_date_refilter_then_resume_next_page_not_restart(monkeypatch):
    def transform(row):
        if row["report_id"] == "1":row.update(publication_date="2020-01-01", published_at="2020-01-01")
        return row
    calls, reads = install_pages(monkeypatch, {1: ([record(1)], 2), 2: ([record(2)], None)}, transform)
    result = source.analysys_fetch(1, start_date="2026-10-01", timeout=2)
    assert calls == [(None, 1), (None, 2)] and set(reads) == {"1", "2"}
    assert result[0]["report_id"] == "2"


def test_directory_old_list_date_can_be_corrected_in_detail(monkeypatch):
    def transform(row):row.update(publication_date="2026-10-10", published_at="2026-10-10");return row
    install_pages(monkeypatch, {1: ([record(1, publishdate="2020-01-01")], None)}, transform)
    assert len(source.analysys_fetch(1, start_date="2026-01-01", timeout=2)) == 1


@pytest.mark.parametrize("start,end", [(None, None), ("20261010", "2026/10/10 23:59:59")])
def test_unknown_publishdate_preserved_or_excluded_by_range(monkeypatch, start, end):
    install_pages(monkeypatch, {1: ([record(1, publishdate=None)], None)})
    rows = source.analysys_fetch(1, start_date=start, end_date=end, timeout=2)
    assert len(rows) == (1 if start is None else 0)


@pytest.mark.parametrize("day", ["2026-10-10", "20261010", "2026/10/10", "2026-10-10 00:00:01", "20261010 00:00:01", "2026/10/10 00:00:01"])
def test_six_date_formats_and_day_inclusive(monkeypatch, day):
    install_pages(monkeypatch, {1: ([record(1)], None)})
    assert len(source.analysys_fetch(1, start_date=day, end_date=day, timeout=2)) == 1


def test_missing_business_metadata_never_merges_unknown(monkeypatch):
    install_pages(monkeypatch, {1: ([record(1, source=None), record(2, source=None)], None)})
    assert len(source.analysys_fetch(2, timeout=2)) == 2


def test_repeated_ids_reuse_detail_and_three_stagnant_pages_fail(monkeypatch):
    calls, reads = install_pages(monkeypatch, {1: ([record(1)], 2), 2: ([record(1)], 3), 3: ([record(1)], 4), 4: ([record(1)], 5)})
    with pytest.raises(SourceError, match="停滞"):
        source.analysys_fetch(2, timeout=2)
    assert reads == ["1"] and [c[1] for c in calls] == [1, 2, 3, 4]


def test_no_partial_when_selected_detail_or_search_fails(monkeypatch):
    install_pages(monkeypatch, {1: ([record(1), record(2)], None)})
    def fail(row, *, timeout):
        if row["report_id"] == "2":raise SourceError("analysys", "必要详情失败")
        return row
    monkeypatch.setattr(source, "_detail", fail)
    with pytest.raises(SourceError, match="必要详情"):
        source.analysys_fetch(2, timeout=2)


def test_cumulative_work_can_exceed_timeout_and_each_operation_gets_full_timeout(monkeypatch):
    from time import monotonic, sleep
    calls = []
    def page(keyword, cursor, *, timeout):
        calls.append(("page", timeout))
        sleep(.025)
        return [record(cursor)], cursor + 1 if cursor == 1 else None
    def detail(row, *, timeout):
        calls.append(("detail", timeout))
        sleep(.025)
        return row
    monkeypatch.setattr(source, "_page", page)
    monkeypatch.setattr(source, "_detail", detail)
    started = monotonic()
    assert len(source.analysys_fetch(2, timeout=.06)) == 2
    assert monotonic() - started > .06
    assert calls == [("page", .06), ("detail", .06), ("page", .06), ("detail", .06)]


def test_real_http_helpers_get_original_timeout_on_every_search_and_detail(monkeypatch):
    calls = []
    def get_json(url, *, timeout, **kwargs):
        calls.append(("search", timeout))
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        return {"keyword": "词", "list": [native(page)]}
    def get_text(url, *, timeout, **kwargs):
        calls.append(("detail", timeout))
        return detail_html(native(int(url.rsplit("/", 1)[-1])))
    monkeypatch.setattr(source.http, "get_json", get_json)
    monkeypatch.setattr(source.http, "get_text", get_text)
    assert len(source.analysys_fetch(2, "词", timeout=7)) == 2
    assert calls == [("search", 7), ("detail", 7), ("search", 7), ("detail", 7)]


@pytest.mark.parametrize("kwargs", [{"limit": True}, {"limit": 0}, {"keyword": 3}, {"keyword": "a\nb"},
                                     {"start_date": date(2026, 1, 1)}, {"start_date": "2026-11-01", "end_date": "2026-10-01"}])
def test_invalid_parameters_fail_before_io(monkeypatch, kwargs):
    monkeypatch.setattr(source, "_page", lambda *a, **k: pytest.fail("参数错误不应请求"))
    with pytest.raises(ValueError):
        source.analysys_fetch(timeout=2, **kwargs)


def test_summary_only_without_pdf_is_valid_and_marked_as_summary(monkeypatch):
    row = native()
    row.update(content=None, summary="<p>明确来源摘要</p>")
    monkeypatch.setattr(source.http, "get_text", lambda *a, **k: detail_html(row))
    result = source._detail(record(), timeout=1)
    assert result["content"] == "明确来源摘要"
    assert result["summary"] == "明确来源摘要"
    assert result["content_type"] == "summary" and result["pdf_urls"] == []


def test_detail_without_body_summary_image_or_real_attachment_fails(monkeypatch):
    row = native()
    row.update(content=None, summary=None, images=[], articleext1=[{"articleid": 1, "ename": "pdf", "text": "/login"}])
    monkeypatch.setattr(source.http, "get_text", lambda *a, **k: detail_html(row))
    with pytest.raises(SourceError, match="缺失"):
        source._detail(record(), timeout=1)


def test_search_missing_publishdate_gets_only_same_detail_date(monkeypatch):
    candidate = record(publishdate=None, newsdate="2099-01-01 01:02:03")
    row = native()
    row.update(publishdate=None, newsdate="2099-01-01 01:02:03")
    monkeypatch.setattr(source.http, "get_text", lambda *a, **k: detail_html(row))
    result = source._detail(candidate, timeout=1)
    assert result["publication_date"] is None and result["published_at"] is None
    row["publishdate"] = "2026-10-11 10:00:00"
    assert source._detail(candidate, timeout=1)["published_at"] == "2026-10-11T10:00:00+08:00"


def test_catalog_count_may_change_between_successive_pages(monkeypatch):
    payloads = {1: {"list": [native(i) for i in range(1, 11)], "total": 11, "pages": 2},
                2: {"list": [native(11), native(12)], "total": 12, "pages": 2}}
    monkeypatch.setattr(source.http, "get_json", lambda url, **k: payloads[int(parse_qs(urlsplit(url).query)["p"][0])])
    calls = []
    monkeypatch.setattr(source, "_detail", lambda row, **k: calls.append(row["report_id"]) or dict(row))
    rows = source.analysys_fetch(12, timeout=2)
    assert len(rows) == 12 and len(calls) == 12 and len(set(calls)) == 12


def test_unknown_date_sorts_after_confirmed_date(monkeypatch):
    install_pages(monkeypatch, {1: ([record(1, publishdate=None), record(2)], None)})
    assert [r["report_id"] for r in source.analysys_fetch(2, timeout=2)] == ["2", "1"]


def test_unselected_unrelated_detail_failure_not_requested(monkeypatch):
    install_pages(monkeypatch, {1: ([record(1), record(2, publishdate="2020-01-01")], None)})
    def detail(row, *, timeout):
        if row["report_id"] == "2":raise SourceError("analysys", "无关坏详情")
        return row
    monkeypatch.setattr(source, "_detail", detail)
    assert source.analysys_fetch(1, timeout=2)[0]["report_id"] == "1"


def test_required_details_run_concurrently_with_at_most_four_workers(monkeypatch):
    from threading import Lock
    from time import sleep
    state = {"active": 0, "peak": 0}
    lock = Lock()
    install_pages(monkeypatch, {1: ([record(i) for i in range(1, 9)], None)})
    def detail(row, *, timeout):
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        sleep(.015)
        with lock:
            state["active"] -= 1
        return row
    monkeypatch.setattr(source, "_detail", detail)
    assert len(source.analysys_fetch(8, timeout=2)) == 8
    assert 1 < state["peak"] <= 4 and state["active"] == 0


@pytest.mark.parametrize("formal_title", [None, "正式标题"])
def test_same_id_later_list_updates_only_fields_missing_from_formal_detail(monkeypatch, formal_title):
    pages = {1: ([record(1, maintitle="旧目录标题")], 2),
             2: ([record(1, maintitle="新目录标题"), record(2)], None)}
    calls = []
    monkeypatch.setattr(source, "_page", lambda keyword, cursor, **k: pages[cursor])
    def get_text(url, **kwargs):
        identity = int(url.rsplit("/", 1)[-1])
        row = native(identity)
        if identity == 1:row.update(maintitle=formal_title, publishdate=None, source=None)
        calls.append(identity)
        return detail_html(row)
    monkeypatch.setattr(source.http, "get_text", get_text)
    rows = source.analysys_fetch(2, timeout=2)
    first = next(r for r in rows if r["report_id"] == "1")
    assert first["title"] == (formal_title or "新目录标题")
    assert calls.count(1) == 1 and set(calls) == {1, 2}
    assert all(len(row) == 16 for row in rows)


def test_full_catalog_page_formally_all_before_start_stops_after_confirmation(monkeypatch):
    old_rows = [record(i, publishdate="2020-01-01") for i in range(1, 11)]
    calls, reads = install_pages(monkeypatch, {1: (old_rows, 2)})
    assert source.analysys_fetch(20, start_date="2026-01-01", timeout=2) == []
    assert calls == [(None, 1)] and set(reads) == {str(i) for i in range(1, 11)}


@pytest.mark.parametrize("special_date", [None, "2026-10-10", "2027-01-01"])
def test_catalog_mixed_or_missing_formal_date_does_not_stop_early(monkeypatch, special_date):
    rows = [record(i, publishdate="2020-01-01") for i in range(1, 10)] + [record(10, publishdate=special_date)]
    calls, _ = install_pages(monkeypatch, {1: (rows, 2), 2: ([record(11)], None)})
    result = source.analysys_fetch(20, start_date="2026-01-01", end_date="2026-12-31", timeout=2)
    assert calls == [(None, 1), (None, 2)]
    assert any(row["report_id"] == "11" for row in result)


def test_keyword_search_never_uses_catalog_lower_date_stop(monkeypatch):
    rows = [record(i, publishdate="2020-01-01") for i in range(1, 11)]
    calls, _ = install_pages(monkeypatch, {1: (rows, 2), 2: ([record(11)], None)})
    result = source.analysys_fetch(20, "关键词", start_date="2026-01-01", timeout=2)
    assert calls == [("关键词", 1), ("关键词", 2)]
    assert [row["report_id"] for row in result] == ["11"]


def test_formal_date_corrected_into_range_prevents_directory_early_stop(monkeypatch):
    rows = [record(i, publishdate="2020-01-01") for i in range(1, 11)]
    def correct(row):
        if row["report_id"] == "5":row.update(publication_date="2026-10-10", published_at="2026-10-10")
        return row
    calls, reads = install_pages(monkeypatch, {1: (rows, 2), 2: ([record(11)], None)}, correct)
    result = source.analysys_fetch(20, start_date="2026-01-01", timeout=2)
    assert calls == [(None, 1), (None, 2)] and set(reads) == {str(i) for i in range(1, 12)}
    assert {row["report_id"] for row in result} == {"5", "11"}


def test_short_catalog_page_does_not_trigger_lower_date_stop(monkeypatch):
    calls, _ = install_pages(monkeypatch, {1: ([record(1, publishdate="2020-01-01")], 2), 2: ([record(2)], None)})
    assert len(source.analysys_fetch(20, start_date="2026-01-01", timeout=2)) == 1
    assert calls == [(None, 1), (None, 2)]


@pytest.mark.parametrize("failing_phase", ["search", "detail"])
def test_actual_http_source_error_still_fails_entire_list(monkeypatch, failing_phase):
    failure = SourceError("analysys", "网络请求实际超时")
    def get_json(url, **kwargs):
        if failing_phase == "search":raise failure
        return {"keyword": "词", "list": [native()]}
    def get_text(url, **kwargs):
        raise failure
    monkeypatch.setattr(source.http, "get_json", get_json)
    monkeypatch.setattr(source.http, "get_text", get_text)
    with pytest.raises(SourceError) as caught:
        source.analysys_fetch(1, "词", timeout=7)
    assert caught.value is failure


@pytest.mark.parametrize("missing", ["title", "institute", "publication_date"])
def test_three_part_key_missing_field_keeps_native_ids(monkeypatch, missing):
    records = [dict(record(i, maintitle="同名"), **{missing: None}) for i in (1, 2)]
    _, reads = install_pages(monkeypatch, {1: (records, None)})
    result = source.analysys_fetch(3, timeout=2)
    assert len(result) == 2 and sorted(reads) == ["1", "2"]
    assert all(r[missing] is None for r in result)


@pytest.mark.parametrize("split", [False, True])
def test_formal_date_regroups_and_refills_without_repeating_details(monkeypatch, split):
    def transform(row):
        row["publication_date"] = "2026-10-09" if split and row["report_id"] == "2" else "2026-10-10"
        return row
    first = [record(1, maintitle="同名"), record(2, maintitle="同名", publishdate="2026-10-10" if split else "2026-10-09")]
    calls, reads = install_pages(monkeypatch, {1: (first, 2), 2: ([record(2, maintitle="同名"), record(3)], None)}, transform)
    result = source.analysys_fetch(2, timeout=2)
    assert calls == ([(None, 1)] if split else [(None, 1), (None, 2)])
    assert sorted(reads) == (["1", "2"] if split else ["1", "2", "3"])
    assert [r["report_id"] for r in result] == (["1", "2"] if split else ["1", "3"])


def test_same_title_and_institute_different_days_are_separate(monkeypatch):
    install_pages(monkeypatch, {1: ([record(1, maintitle="每日分析"),
        record(2, maintitle="每日分析", publishdate="2026-10-09")], None)})
    result = source.analysys_fetch(2, timeout=2)
    assert [(r["report_id"], r["publication_date"]) for r in result] == [("1", "2026-10-10"), ("2", "2026-10-09")]
