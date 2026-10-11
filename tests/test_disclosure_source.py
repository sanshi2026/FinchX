"""公告来源真实结构与必要损坏回归；构造分页仅用于边界测试。"""

import copy
from datetime import date, datetime
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.eastmoney import disclosure as ds

FIXTURES = Path(__file__).parent / "fixtures" / "disclosure"
MIXED = "AN202609281829961300"
OLD = "AN201202240003357565"
ANNUAL = "AN201708160804547103"
CURRENT = f"https://data.eastmoney.com/notices/detail/300308/{MIXED}.html"


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text(encoding="utf-8"))


def install(monkeypatch, callback):
    calls = []
    def get(url, **kwargs):
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        calls.append(query)
        return copy.deepcopy(callback(query))
    monkeypatch.setattr(ds, "get_json", get)
    return calls


def row(number, *, day="2026-10-09", stamp="2026-10-09 10:00:00:000"):
    return {"art_code": f"AN20261009{number:012}", "title": f"公告{number}", "notice_date": day,
            "eiTime": stamp, "codes": [{"stock_code": "300308", "market_code": "0", "short_name": "中际旭创"}],
            "columns": [{"column_code": "column", "column_name": "类别"}]}


def page(index, rows, total, size=2):
    return {"success": 1, "error": "", "data": {"page_index": index, "page_size": size, "total_hits": total, "list": rows}}


def small(monkeypatch, callback):
    monkeypatch.setattr(ds, "_PAGE_SIZE", 2)
    return install(monkeypatch, callback)


def test_real_list_batch_and_fixed_business_fields(monkeypatch):
    calls = install(monkeypatch, lambda q: fixture("review_exact100"))
    result = ds.em_list("300308", 2, timeout=3)
    assert len(result) == 2 and len(calls) == 1 and calls[0]["page_size"] == "100"
    assert set(result[0]) == {"id", "title", "notice_date", "source_time", "url", "categories", "related_securities"}
    assert result[0]["source_time"] == "2026-10-08T07:56:41.000+08:00"
    assert result[1]["notice_date"] == "2026-10-01" and result[1]["source_time"].startswith("2026-09-30")
    assert result[0]["related_securities"] == [{"code": "300308", "market": "0", "name": "中际旭创"}]


@pytest.mark.parametrize("formats", ["2026-10-09", "20261009", "2026/10/09", "2026-10-09 10:00:00", "20261009 10:00:00", "2026/10/09 10:00:00", date(2026, 10, 9)])
def test_all_public_date_formats_and_date_object(monkeypatch, formats):
    small(monkeypatch, lambda q: page(1, [row(1, stamp="2026-10-09 10:00:00:123")], 1))
    assert len(ds.em_list("300308", since=formats, until=formats, timeout=3)) == 1


@pytest.mark.parametrize("bound", [datetime(2026, 10, 9), "2026-10-09 10:00", "2026-10-09 10:00:00.1", " 2026-10-09", "2026-10-09Z", "２０２６１００９", False, 0])
def test_bad_window_rejected_before_request(monkeypatch, bound):
    calls = install(monkeypatch, lambda q: pytest.fail("network must not run"))
    with pytest.raises(ValueError): ds.em_list("300308", since=bound, timeout=3)
    assert calls == []


def test_second_boundary_inclusive_and_next_second_excluded(monkeypatch):
    small(monkeypatch, lambda q: page(1, [row(1, stamp="2026-10-09 10:00:00:999"), row(2, stamp="2026-10-09 10:00:01")], 2))
    assert len(ds.em_list("300308", until="2026-10-09 10:00:00", timeout=3)) == 1


def test_date_fallback_compares_day_without_inventing_time(monkeypatch):
    small(monkeypatch, lambda q: page(1, [row(1, stamp=None)], 1))
    r = ds.em_list("300308", since="2026-10-09 23:00:00", until="2026-10-09 23:00:00", timeout=3)
    assert r[0]["source_time"] is None


def test_no_lower_bound_early_stop_for_migrated_records(monkeypatch):
    def response(q):
        if q["page_index"] == "1": return page(1, [row(1, day="1994-06-30", stamp="2013-03-14 15:14:45"), row(2, day="2001-04-14", stamp="2017-08-16 18:03:17")], 3)
        return page(2, [row(3, day="2001-04-14", stamp="2026-10-09 10:00:00")], 3)
    calls = small(monkeypatch, response)
    assert ds.em_list("300308", since="2026-10-09", timeout=3)[0]["id"] == row(3)["art_code"]
    assert len(calls) == 2


def test_unknown_date_unfiltered_retained_bounded_fails(monkeypatch):
    small(monkeypatch, lambda q: page(1, [row(1, day=None, stamp=None)], 1))
    assert len(ds.em_list("300308", timeout=3)) == 1
    with pytest.raises(SourceError): ds.em_list("300308", since="2026-10-09", timeout=3)


@pytest.mark.parametrize("categories", [[], (), "财务报告", ["未知"], [False], [" 财务报告"]])
def test_invalid_categories_before_network(monkeypatch, categories):
    calls = install(monkeypatch, lambda q: pytest.fail("network must not run"))
    with pytest.raises(ValueError): ds.em_list("300308", categories=categories, timeout=3)
    assert not calls


def test_parent_child_or_collapses_single_native_branch(monkeypatch):
    calls = small(monkeypatch, lambda q: page(1, [row(1), row(2)], 100))
    result = ds.em_list("300308", 1, categories=["利润分配", "财务报告", "财务报告"], timeout=3)
    assert len(result) == 1 and len(calls) == 1
    assert calls[0]["f_node"] == "1" and "s_node" not in calls[0]


def test_all_twenty_category_mappings_have_expected_native_nodes():
    assert len(ds._CATEGORY_NODES) == 20
    assert ds._categories(["重大合同", "利润分配", "回购"]) == [(5, 7), (1, 13), (6, 12)]


def test_multiple_categories_full_union_date_sort_and_null_last(monkeypatch):
    first = [row(1, day=None, stamp=None), row(2, day="2026-10-07")]
    second = [row(3), row(2, day="2026-10-07")]
    calls = small(monkeypatch, lambda q: page(1, first if q["f_node"] == "1" else second, 2))
    result = ds.em_list("300308", 3, categories=["财务报告", "重大事项"], timeout=3)
    assert [r["id"] for r in result] == [row(i)["art_code"] for i in [3, 2, 1]] and len(calls) == 2


def test_independent_branches_cannot_mask_conflicting_same_id(monkeypatch):
    def response(q):
        r = row(1)
        if q["f_node"] == "5": r["title"] = "不同公告标题"
        return page(1, [r], 1)
    small(monkeypatch, response)
    with pytest.raises(SourceError, match="业务身份冲突"): ds.em_list("300308", categories=["财务报告", "重大事项"], timeout=3)


def test_cross_page_overlap_later_whole_row_updates_and_second_round_fills(monkeypatch):
    scripted = [page(1, [row(1), row(2)], 4), page(2, [row(2), row(3)], 4), page(1, [row(1), row(4)], 4), page(2, [row(3), {**row(2), "title": "后读真实行"}], 4)]
    calls = small(monkeypatch, lambda q: scripted.pop(0))
    result = ds.em_list("300308", 20, timeout=3)
    assert len(result) == 4 and len(calls) == 4 and result[1]["title"] == "后读真实行"


def test_three_rounds_incomplete_fail(monkeypatch):
    calls = small(monkeypatch, lambda q: page(int(q["page_index"]), [row(1), row(2)] if q["page_index"] == "1" else [row(2), row(3)], 4))
    with pytest.raises(SourceError, match="三轮"): ds.em_list("300308", timeout=3)
    assert len(calls) == 6


@pytest.mark.parametrize("case", ["duplicate", "short", "drift", "repeat", "budget", "bad_identity", "bad_last_numeric_time", "bad_page_size", "bool_success"])
def test_necessary_page_damage_fails_not_partial(monkeypatch, case):
    def response(q):
        number = int(q["page_index"])
        value = page(number, [row(1), row(2)] if number == 1 else [row(3)], 3)
        if case == "duplicate": value["data"]["list"] = [row(1), row(1)]
        if case == "short": value["data"]["list"] = [row(1)]
        if case == "drift" and number == 2: value["data"]["total_hits"] = 4
        if case == "repeat": value = page(number, [row(1), row(2)], 4)
        if case == "bad_identity": value["data"]["list"][0]["codes"][0]["stock_code"] = "600519"
        if case == "bad_last_numeric_time": value["data"]["list"][-1]["eiTime"] = False
        if case == "bad_page_size": value["data"]["page_size"] = 200
        if case == "bool_success": value["success"] = True
        return value
    small(monkeypatch, response)
    if case == "budget": monkeypatch.setattr(ds, "_MAX_REQUESTS", 1)
    with pytest.raises(SourceError): ds.em_list("300308", timeout=3)


def test_complete_page_validation_before_limit(monkeypatch):
    payload = fixture("review_exact100");payload["data"]["list"][-1]["eiTime"] = "bad"
    install(monkeypatch, lambda q: payload)
    with pytest.raises(SourceError): ds.em_list("300308", 1, timeout=3)


def test_unrelated_extra_fields_and_ignored_sort_date(monkeypatch):
    r = row(1);r.update(sort_date=False, display_time="unparsed", future={"a": [1]})
    small(monkeypatch, lambda q: page(1, [r], 1))
    assert len(ds.em_list("300308", timeout=3)) == 1


def test_real_detail_mixed_securities_and_deduplicated_pdf(monkeypatch):
    calls = install(monkeypatch, lambda q: fixture("detail_mixed"))
    result = ds.em_get(CURRENT, timeout=3)
    assert set(result) == {"title", "notice_date", "source_time", "content", "related_securities", "attachments"}
    assert result["related_securities"][0] == {"code": "03308", "market": "116", "name": "中际旭创"}
    assert len(result["attachments"]) == 1 and result["attachments"][0]["type"] == "pdf" and result["attachments"][0]["size_kb"] == 147
    assert len(calls) == 1 and "stock_list" not in calls[0]


def test_real_five_page_historical_report(monkeypatch):
    calls = install(monkeypatch, lambda q: fixture("detail_annual" if q["page_index"] == "1" else "annual_" + q["page_index"]))
    result = ds.em_get(f"https://data.eastmoney.com/notices/detail/000001/{ANNUAL}.html", timeout=3)
    assert len(calls) == 5 and len(result["content"]) == 23958
    assert result["notice_date"] == "2001-04-14" and result["source_time"] == "2017-08-16T18:03:17+08:00"


@pytest.mark.parametrize("url", [CURRENT, CURRENT.replace("https:", "http:"), f"https://data.eastmoney.com/notices/detail/{MIXED}.html", f"https://np-info.eastmoney.com/wap/notice/?infocode={MIXED}", f"https://pdf.dfcfw.com/pdf/H2_{MIXED}_1.pdf", f"https://pdf.dfcfw.com/pdf/H2_{MIXED}_1.pdf?1790617393000.pdf"])
def test_supported_url_routes_independently_fetch_same_id(monkeypatch, url):
    calls = install(monkeypatch, lambda q: fixture("detail_mixed"))
    assert ds.em_get(url, timeout=3)["content"] and calls[0]["art_code"] == MIXED


def test_h22_historical_attachment_route(monkeypatch):
    install(monkeypatch, lambda q: fixture("detail_old"))
    assert ds.em_get(f"https://pdf.dfcfw.com/pdf/H22_{OLD}_1.pdf?1671031346000.pdf", timeout=3)["notice_date"] == "1994-06-30"


@pytest.mark.parametrize("url", [CURRENT + "#a", CURRENT + "?x=1", CURRENT.replace(".com/", ".com:443/"), CURRENT.replace("https://", "https://user:password@"), CURRENT.replace("300308/", "300308,"), CURRENT + "\n", CURRENT.replace("https:", "file:"), f"https://guba.eastmoney.com/news,300308,123.html", f"https://pdf.dfcfw.com/pdf/H3_{MIXED}_1.pdf", f"https://pdf.dfcfw.com/pdf/H2_{MIXED}_1.pdf?x=1", f"https://np-info.eastmoney.com/wap/notice/?infocode={MIXED}&x=1"])
def test_unverified_input_urls_rejected_before_request(monkeypatch, url):
    calls = install(monkeypatch, lambda q: pytest.fail("network must not run"))
    with pytest.raises(ValueError): ds.em_get(url, timeout=3)
    assert not calls


@pytest.mark.parametrize("path", [f"H22_{MIXED}_1.pdf", f"H2_{MIXED}_2.pdf"])
def test_pdf_path_family_or_sequence_not_guessed(monkeypatch, path):
    install(monkeypatch, lambda q: fixture("detail_mixed"))
    with pytest.raises(SourceError, match="PDF路径"): ds.em_get("https://pdf.dfcfw.com/pdf/" + path, timeout=3)


def test_url_code_must_be_a_source_security(monkeypatch):
    install(monkeypatch, lambda q: fixture("detail_mixed"))
    with pytest.raises(SourceError, match="URL代码"): ds.em_get(CURRENT.replace("300308/", "600519/"), timeout=3)


def test_legal_distinct_web_link_not_lost_or_given_unfounded_size(monkeypatch):
    payload = fixture("detail_mixed");payload["data"]["attach_url_web"] = "https://pdf.dfcfw.com/alternate.pdf?different=1"
    install(monkeypatch, lambda q: payload)
    result = ds.em_get(CURRENT, timeout=3)
    assert len(result["attachments"]) == 2
    assert result["attachments"][1] == {"url": payload["data"]["attach_url_web"], "size_kb": None, "type": "pdf"}


def test_zero_size_unknown_legal_type_and_no_fake_name(monkeypatch):
    payload = fixture("detail_mixed");data = payload["data"]
    data["attach_size"] = "0";data["attach_type"] = "7";data["attach_list"][0].update(attach_size=0, attach_type="7")
    install(monkeypatch, lambda q: payload)
    assert ds.em_get(CURRENT, timeout=3)["attachments"][0] == {"url": data["attach_url"], "size_kb": 0, "type": None}


def test_pdf_only_explicit_missing_body_is_honest_none(monkeypatch):
    payload = fixture("detail_mixed");payload["data"]["notice_content"] = None
    install(monkeypatch, lambda q: payload)
    result = ds.em_get(CURRENT, timeout=3)
    assert result["content"] is None and result["attachments"]


@pytest.mark.parametrize("field,value", [("notice_date", "bad"), ("eitime", "bad"), ("security", "bad"), ("attach_list", "bad"), ("notice_content", False), ("page_size", 0), ("art_code", OLD), ("attach_size", -1), ("attach_size", True), ("attach_size", float("inf")), ("attach_type", True), ("attach_type", "wrong"), ("attach_url", "javascript:alert(1)")])
def test_bad_detail_necessary_fields_fail(monkeypatch, field, value):
    payload = fixture("detail_mixed");payload["data"][field] = value
    install(monkeypatch, lambda q: payload)
    with pytest.raises(SourceError): ds.em_get(CURRENT, timeout=3)


def test_attachment_metadata_conflict_fails(monkeypatch):
    payload = fixture("detail_mixed");payload["data"]["attach_size"] = "999"
    install(monkeypatch, lambda q: payload)
    with pytest.raises(SourceError, match="冲突"): ds.em_get(CURRENT, timeout=3)


@pytest.mark.parametrize("case", ["metadata", "page_count", "duplicate_text", "partial_text"])
def test_multi_page_integrity_not_partial(monkeypatch, case):
    def response(q):
        value = fixture("detail_annual" if q["page_index"] == "1" else "annual_" + q["page_index"])
        if q["page_index"] == "2":
            if case == "metadata": value["data"]["notice_date"] = "2001-04-15"
            if case == "page_count": value["data"]["page_size"] = 4
            if case == "duplicate_text": value["data"]["notice_content"] = fixture("detail_annual")["data"]["notice_content"]
            if case == "partial_text": value["data"]["notice_content"] = None
        return value
    install(monkeypatch, response)
    with pytest.raises(SourceError): ds.em_get(f"https://data.eastmoney.com/notices/detail/{ANNUAL}.html", timeout=3)


def test_missing_optional_fields_legacy_does_not_require_list(monkeypatch):
    payload = fixture("detail_mixed")
    for key in ["notice_title", "notice_date", "eitime", "security", "attach_list", "attach_url", "attach_url_web", "attach_size", "attach_type"]: payload["data"].pop(key)
    payload["data"]["unknown"] = True
    install(monkeypatch, lambda q: payload)
    result = ds.em_get(f"https://data.eastmoney.com/notices/detail/{MIXED}.html", timeout=3)
    assert result["content"] and result["related_securities"] is None and result["attachments"] is None


def test_detail_security_order_has_no_false_identity_conflict(monkeypatch):
    def response(q):
        value = fixture("detail_mixed");value["data"]["page_size"] = 2
        if q["page_index"] == "2":
            value["data"]["security"].reverse();value["data"]["notice_content"] = "另一页真实源文字"
        return value
    install(monkeypatch, response)
    result = ds.em_get(CURRENT, timeout=3)
    assert result["related_securities"][0]["code"] == "03308"
    assert result["content"].endswith("另一页真实源文字")


def test_missing_optional_metadata_between_pages_uses_actual_provided_value(monkeypatch):
    def response(q):
        value = fixture("detail_mixed");value["data"]["page_size"] = 2
        if q["page_index"] == "1": value["data"].pop("security")
        else: value["data"]["notice_content"] = "来源第二页"
        return value
    install(monkeypatch, response)
    assert ds.em_get(CURRENT, timeout=3)["related_securities"][1]["code"] == "300308"


def test_source_attachment_legitimate_port_fragment_kept_without_fetch(monkeypatch):
    payload = fixture("detail_mixed");payload["data"]["attach_url_web"] = "https://pdf.dfcfw.com:8443/alternate.pdf?x=1#page=2"
    calls = install(monkeypatch, lambda q: payload)
    assert ds.em_get(CURRENT, timeout=3)["attachments"][-1]["url"] == payload["data"]["attach_url_web"]
    assert len(calls) == 1


@pytest.mark.parametrize("suffix", ["?", "#"])
def test_empty_input_query_or_fragment_rejected(monkeypatch, suffix):
    calls = install(monkeypatch, lambda q: pytest.fail("network must not run"))
    with pytest.raises(ValueError): ds.em_get(CURRENT + suffix, timeout=3)
    assert not calls


def test_lists_missing_and_explicit_empty_arrays_distinguished(monkeypatch):
    first = row(1);first.pop("codes");first.pop("columns")
    second = row(2);second.update(codes=[], columns=[])
    small(monkeypatch, lambda q: page(1, [first, second], 2))
    result = ds.em_list("300308", timeout=3)
    assert result[0]["related_securities"] is None and result[0]["categories"] is None
    assert result[1]["related_securities"] == [] and result[1]["categories"] == []


def test_detail_explicit_empty_arrays_kept_and_current_unknown_identity_fails(monkeypatch):
    payload = fixture("detail_mixed")
    payload["data"].update(security=[], attach_list=[], attach_url=None, attach_url_web=None)
    install(monkeypatch, lambda q: payload)
    result = ds.em_get(f"https://data.eastmoney.com/notices/detail/{MIXED}.html", timeout=3)
    assert result["related_securities"] == [] and result["attachments"] == []
    with pytest.raises(SourceError, match="URL代码"): ds.em_get(CURRENT, timeout=3)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_explicit_attachment_row_requires_its_url_identity(monkeypatch, value):
    payload = fixture("detail_mixed")
    payload["data"]["attach_list"][0]["attach_url"] = value
    install(monkeypatch, lambda q: payload)
    with pytest.raises(SourceError, match="attach_url"): ds.em_get(CURRENT, timeout=3)


def test_irrelevant_attachment_sequence_cannot_reject_valid_business_data(monkeypatch):
    payload = fixture("detail_mixed")
    install(monkeypatch, lambda q: payload)
    before = ds.em_get(CURRENT, timeout=3)
    payload["data"]["attach_list"][0]["seq"] = {"future_internal_sequence": False}
    install(monkeypatch, lambda q: payload)
    assert ds.em_get(CURRENT, timeout=3) == before
