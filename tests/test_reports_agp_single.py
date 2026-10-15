"""单来源研报批量的身份、同秒、日期与失败契约。"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from finchx import SourceError
from finchx.sources.aigupiao import reports as old
from finchx.sources.aigupiao import reports_single as single

FIXTURES = Path(__file__).parent / "fixtures" / "reports"
BASE = json.loads((FIXTURES / "list-all.json").read_text(encoding="utf-8"))["data"][0]
FIELDS = {"url", "title", "kind", "ref_code", "name", "institute", "rating",
          "publication_date_text", "recorded_at", "symbol", "theme_id",
          "publication_date", "researcher", "summary", "pdf_urls"}


def row(identity, stamp, **changes):
    return dict(deepcopy(BASE), inv_id=identity, sort_time=stamp, title=f"标题{identity}", **changes)


def source(monkeypatch, rows, *, details=None, cap=None, total=None):
    calls, reads = [], []
    def post(url, **kwargs):
        f = kwargs["data"]
        calls.append(dict(f))
        selected = [r for r in rows if not f["before"] or r["sort_time"] < f["before"]]
        count = len(selected) if total is None else total
        return dict(code=0, status="succ", total=count, last_page=count // f["limit"],
                    inv_url=old._DETAIL, data=selected[:min(f["limit"], cap or f["limit"])])
    def get(url, **kwargs):
        identity = int(url.rsplit("=", 1)[1]); reads.append(identity)
        value = dict(title=None, institute=None, publication_date="2026-10-09",
                     researcher="甲", summary=f"摘要{identity}", pdf_urls=[f"https://example.com/{identity}.pdf"])
        change = (details or {}).get(identity, {})
        if isinstance(change, Exception):
            raise change
        value.update(change)
        return value
    monkeypatch.setattr(old, "post_form_json", post)
    monkeypatch.setattr(old, "_get_detail", get)
    return calls, reads


def test_finite_limit_does_not_read_unselected_bad_detail(monkeypatch):
    calls, reads = source(monkeypatch, [row(1, 100), row(2, 99)], details={2: SourceError("aigupiao", "坏详情")})
    result = single.agp_fetch(limit=1, timeout=5)
    assert reads == [1] and len(calls) == 1 and calls[0]["limit"] == 1
    assert set(result[0]) == FIELDS
    assert result[0]["summary"] == "摘要1" and result[0]["theme_id"] == BASE["theme_id"]


def test_real_fixture_metadata_and_plain_summary(monkeypatch):
    payload = json.loads((FIXTURES / "list-all.json").read_text(encoding="utf-8"))
    candidate = dict(payload["data"][0], inv_id=2477185)
    source(monkeypatch, [candidate])
    monkeypatch.setattr(old, "_get_detail", lambda url, **kw: old._detail(
        (FIXTURES / "detail-2477185.html").read_text(encoding="utf-8"), url=url, identity="2477185"))
    result = single.agp_fetch(limit=1, timeout=5)[0]
    assert set(result) == FIELDS and result["researcher"] == "李浩洋"
    assert result["institute"] == "华龙证券" and result["publication_date"] == "2026-10-09"
    assert result["summary"] and result["pdf_urls"]


@pytest.mark.parametrize("count", [9, 20, 51, 101])
def test_full_second_expands_and_never_skips_native_ids(monkeypatch, count):
    rows = [row(i, 100) for i in range(1, count + 1)] + [row(count + 1, 99)]
    calls, reads = source(monkeypatch, rows)
    result = single.agp_fetch(limit=count + 2, timeout=5)
    assert len(result) == count + 1 and sorted(reads) == list(range(1, count + 2))
    assert all(f["before"] in {0, 101} for f in calls)
    assert len({r["url"] for r in result}) == len(result)


def test_hidden_cap_without_matching_total_fails_not_partial(monkeypatch):
    source(monkeypatch, [row(i, 100) for i in range(1, 80)], cap=20)
    with pytest.raises(SourceError, match="同秒分页无法确认完整"):
        single.agp_fetch(limit=100, timeout=5)


def test_tail_group_can_end_using_request_relative_total(monkeypatch):
    calls, reads = source(monkeypatch, [row(i, 100) for i in range(1, 10)])
    assert len(single.agp_fetch(limit=20, timeout=5)) == 9
    assert len(calls) == 1 and sorted(reads) == list(range(1, 10))


def test_different_days_count_separately_toward_limit(monkeypatch):
    rows = [row(1, 100), row(2, 99), row(3, 98)]
    details = {1: dict(title="相同", institute="机构", publication_date="2026-10-08"),
               2: dict(title="相同", institute="机构", publication_date="2026-10-09")}
    calls, reads = source(monkeypatch, rows, details=details)
    result = single.agp_fetch(limit=2, timeout=5)
    assert len(result) == 2 and sorted(reads) == [1, 2]
    assert [r["publication_date"] for r in result] == ["2026-10-09", "2026-10-08"]
    representative = result[0]
    assert representative["url"].endswith("=2") and representative["summary"] == "摘要2"
    assert representative["pdf_urls"] == ["https://example.com/2.pdf"]


def test_missing_metadata_not_merged(monkeypatch):
    source(monkeypatch, [row(1, 100, institute=None), row(2, 99, institute=None)],
           details={1: dict(title="同名"), 2: dict(title="同名")})
    assert len(single.agp_fetch(limit=2, timeout=5)) == 2


@pytest.mark.parametrize("text", ["2026-10-09", "20261009", "2026/10/09",
                                  "2026-10-09 23:59:59", "20261009 00:00:00", "2026/10/09 12:30:01"])
def test_dates_are_inclusive_and_formal_detail_rechecks_list(monkeypatch, text):
    rows = [row(1, 100, pub_time="2026-10-09"), row(2, 99, pub_time="2026-10-01")]
    source(monkeypatch, rows, details={1: dict(publication_date="2026-10-08")})
    result = single.agp_fetch(limit=1, start_date=text, end_date=text, timeout=5)
    assert len(result) == 1 and result[0]["url"].endswith("=2")


def test_unknown_year_not_inferred_from_recorded_time(monkeypatch):
    source(monkeypatch, [row(1, 100, pub_time="10-09")], details={1: dict(publication_date=None)})
    assert single.agp_fetch(start_date="2026-10-09", timeout=5) == []


def test_full_catalog_date_fallback_and_optional_missing_values(monkeypatch):
    source(monkeypatch, [row(1, 100, pub_time="20261009", institute=None)],
           details={1: dict(publication_date=None, researcher=None, summary=None, pdf_urls=[])})
    result = single.agp_fetch(limit=1, timeout=5)[0]
    assert result["publication_date"] == "2026-10-09"
    assert result["institute"] is None and result["pdf_urls"] == []


@pytest.mark.parametrize("values", [{"limit": True}, {"limit": None}, {"limit": 0},
    {"kind": "user"}, {"keyword": 1}, {"keyword": "\ud800"}, {"keyword": "a\x00b"},
    {"industry": 3}, {"kind": "stock", "industry": "汽车行业"},
    {"start_date": date(2026, 10, 9)}, {"start_date": "2026-02-30"},
    {"start_date": "2026-10-10", "end_date": "2026-10-09"}])
def test_invalid_inputs_fail_before_network(monkeypatch, values):
    monkeypatch.setattr(old, "post_form_json", lambda *a, **k: pytest.fail("network"))
    monkeypatch.setattr(old, "get_json", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError):
        single.agp_fetch(timeout=5, **values)


@pytest.mark.parametrize("industry", ["汽车行业", "000039", "  汽车行业  "])
def test_industry_dictionary_exact_filter_and_keyword_trim(monkeypatch, industry):
    dictionary = json.loads((FIXTURES / "industry-dictionary.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(old, "get_json", lambda *a, **k: dictionary)
    calls, _ = source(monkeypatch, [row(1, 100)])
    single.agp_fetch(limit=1, industry=industry, keyword=" 汽车 ", timeout=5)
    assert calls[0]["kind"] == "industry" and calls[0]["symbol"] == "000039" and calls[0]["keyword"] == "汽车"


def test_detail_failure_and_programming_error_are_not_partial(monkeypatch):
    source(monkeypatch, [row(1, 100), row(2, 99)], details={2: SourceError("aigupiao", "详情失败")})
    with pytest.raises(SourceError, match="详情失败"):
        single.agp_fetch(limit=2, timeout=5)
    monkeypatch.setattr(old, "_get_detail", lambda *a, **k: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        single.agp_fetch(limit=1, timeout=5)


def test_empty_page_is_normal(monkeypatch):
    source(monkeypatch, [])
    assert single.agp_fetch(timeout=5) == []


def test_later_native_catalog_update_keeps_detail_cache_and_first_position(monkeypatch):
    calls, reads = source(monkeypatch, [], details={1: dict(title="相同", institute="机构"),
                                                  2: dict(title="相同", institute="机构")})
    first = old._page(dict(code=0, status="succ", total=2, last_page=1,
                          data=[row(1, 100), row(2, 99)]), before=0, kind="all", industry=None)
    second = old._page(dict(code=0, status="succ", total=2, last_page=1,
                           data=[row(1, 98, rating="已更新"), row(3, 97)]),
                       before=0, kind="all", industry=None)
    monkeypatch.setattr(single, "_pages", lambda *a: iter([first, second]))
    result = single.agp_fetch(limit=3, timeout=5)
    assert sorted(reads) == [1, 2, 3]
    assert next(r for r in result if r["url"].endswith("=1"))["rating"] == "已更新"


@pytest.mark.parametrize("dictionary, value, error", [
    ({"code": 0, "status": "succ", "list": [{"symbol": "000039", "name": "汽车行业"}]}, "39", ValueError),
    ({"code": 0, "status": "succ", "list": [{"symbol": "000039", "name": "同名"}, {"symbol": "000040", "name": "同名"}]}, "同名", ValueError),
    ({"code": 0, "status": "succ", "list": []}, "汽车行业", SourceError),
    ({"code": 0, "status": "succ", "list": [{"symbol": 39, "name": "汽车行业"}]}, "汽车行业", SourceError),
])
def test_unknown_ambiguous_or_broken_industry_never_searches(monkeypatch, dictionary, value, error):
    monkeypatch.setattr(old, "get_json", lambda *a, **k: dictionary)
    monkeypatch.setattr(old, "post_form_json", lambda *a, **k: pytest.fail("unexpected search"))
    with pytest.raises(error):
        single.agp_fetch(industry=value, timeout=5)


@pytest.mark.parametrize("kind, changes", [("stock", {"ref_kind": "industry"}),
                                           ("industry", {"ref_kind": "stock"})])
def test_source_must_honor_requested_kind(monkeypatch, kind, changes):
    source(monkeypatch, [row(1, 100, **changes)])
    with pytest.raises(SourceError, match="类别筛选"):
        single.agp_fetch(kind=kind, timeout=5)


def test_large_page_validates_across_100_row_parser_chunks(monkeypatch):
    rows = [row(i, 2000 - i) for i in range(1, 103)]
    rows[-1] = dict(rows[-1], inv_id=rows[0]["inv_id"])
    source(monkeypatch, rows)
    with pytest.raises(SourceError, match="身份重复"):
        single._page(0, 200, "all", None, None, 5)


def test_short_page_with_inconsistent_total_is_not_exhaustion(monkeypatch):
    source(monkeypatch, [row(1, 100)], total=10000)
    with pytest.raises(SourceError, match="同秒分页无法确认完整"):
        single.agp_fetch(limit=2, timeout=5)


@pytest.mark.parametrize("keyword", [None, "", "   "])
def test_optional_keyword_is_native_unfiltered_request(monkeypatch, keyword):
    calls, _ = source(monkeypatch, [row(1, 100)])
    single.agp_fetch(limit=1, keyword=keyword, timeout=5)
    assert calls[0]["keyword"] == ""


def test_similar_unicode_metadata_is_not_fuzzy_deduplicated(monkeypatch):
    source(monkeypatch, [row(1, 100), row(2, 99)],
           details={1: dict(title="ＡI", institute="机构"), 2: dict(title="AI", institute="机构")})
    assert len(single.agp_fetch(limit=2, timeout=5)) == 2


def test_known_duplicate_same_day_prefers_whole_more_complete_record(monkeypatch):
    source(monkeypatch, [row(1, 100), row(2, 99), row(3, 98)],
           details={1: dict(title="相同", institute="机构", summary=None),
                    2: dict(title="相同", institute="机构")})
    result = single.agp_fetch(limit=2, timeout=5)
    representative = next(r for r in result if r["title"] == "相同")
    assert representative["url"].endswith("=2") and representative["summary"] == "摘要2"


def test_bad_unselected_source_leaf_is_not_silently_trimmed(monkeypatch):
    source(monkeypatch, [row(1, 100), row(2, 99, rating=True)])
    with pytest.raises(SourceError, match="rating"):
        single.agp_fetch(limit=2, timeout=5)


def test_search_failure_after_collected_report_does_not_return_partial(monkeypatch):
    calls, _ = source(monkeypatch, [row(1, 100)], total=1000)
    post = old.post_form_json
    def fail_second(*a, **kw):
        if calls:
            raise SourceError("aigupiao", "后页失败")
        return post(*a, **kw)
    monkeypatch.setattr(old, "post_form_json", fail_second)
    with pytest.raises(SourceError, match="后页失败"):
        single.agp_fetch(limit=2, timeout=5)


def test_missing_confirmed_boundary_identity_is_source_error(monkeypatch):
    calls, _ = source(monkeypatch, [row(1, 100)], total=1000)
    post = old.post_form_json
    def changed(*a, **kw):
        value = post(*a, **kw)
        if len(calls) > 1:
            value["data"] = [row(2, 99)]
        return value
    monkeypatch.setattr(old, "post_form_json", changed)
    with pytest.raises(SourceError, match="未保留已确认身份"):
        single.agp_fetch(limit=2, timeout=5)


def test_consecutive_dense_seconds_do_not_shrink_recovery_batch(monkeypatch):
    rows = ([row(i, 100) for i in range(1, 701)]
            + [row(i, 99) for i in range(701, 1301)] + [row(1301, 98)])
    calls, reads = source(monkeypatch, rows)
    result = single.agp_fetch(limit=1400, timeout=15)
    assert len(result) == 1301 and len(reads) == len(set(reads)) == 1301
    second_boundary = [f["limit"] for f in calls if f["before"] == 100]
    assert second_boundary == [1000]


def test_expanding_overlap_cannot_forget_previously_seen_identities(monkeypatch):
    rows = [row(i, 100) for i in range(1, 90)] + [row(90, 99)]
    calls, _ = source(monkeypatch, rows)
    post = old.post_form_json
    def lose_identity(*a, **kw):
        result = post(*a, **kw)
        if kw["data"]["limit"] >= 100:
            result["data"] = [r for r in result["data"] if r["inv_id"] != 30]
        return result
    monkeypatch.setattr(old, "post_form_json", lose_identity)
    with pytest.raises(SourceError, match="未保留已确认身份"):
        single.agp_fetch(limit=100, timeout=5)


def candidate_page(rows):
    return old._page(dict(code=0, status="succ", total=len(rows), last_page=0, data=rows),
                     before=0, kind="all", industry=None)


def test_later_selected_group_copy_is_confirmed_before_finite_return(monkeypatch):
    details = {i: dict(title="同稿", institute="机构", summary=None) for i in (1, 2, 4)}
    details[4]["summary"] = "完整摘要"
    details[3] = dict(title="另一稿", institute="机构")
    _, reads = source(monkeypatch, [], details=details)
    first = candidate_page([row(1, 100, institute="机构"), row(2, 100, institute="机构")])
    # 首批正式标题合并；恢复页已知同组副本位于另一稿之后。
    later = candidate_page([row(1, 100, institute="机构"), row(2, 100, institute="机构"),
                            row(3, 99, institute="机构"), row(4, 98, institute="机构")])
    for page in (first, later):
        for identity, _, candidate in page:
            candidate["title"] = "另一稿" if identity == "3" else "同稿"
            candidate["publication_date_text"] = "2026-10-09"
    monkeypatch.setattr(single, "_pages", lambda *a: iter([first, later]))
    result = single.agp_fetch(limit=2, timeout=5)
    assert set(reads) == {1, 2, 3, 4}
    representative = next(r for r in result if r["title"] == "同稿")
    assert representative["summary"] == "完整摘要" and representative["url"].endswith("=4")
    assert representative["pdf_urls"] == ["https://example.com/4.pdf"]


@pytest.mark.parametrize("correction", [dict(title="正式另稿"), dict(publication_date="2026-10-08")])
def test_selected_group_copy_formal_metadata_reselects_and_supplements(monkeypatch, correction):
    details = {1: dict(title="同稿", institute="机构"), 2: dict(title="同稿", institute="机构")}
    details[2].update(correction)
    _, reads = source(monkeypatch, [], details=details)
    first = candidate_page([row(1, 100), row(2, 100)])
    for _, _, candidate in first:
        candidate.update(title="同稿", institute="机构")
    second = candidate_page([row(3, 99)])
    monkeypatch.setattr(single, "_pages", lambda *a: iter([first, second]))
    result = single.agp_fetch(limit=2, start_date="2026-10-09", timeout=5)
    if "title" in correction:
        assert len(result) == 2 and set(reads) == {1, 2}
        assert {r["title"] for r in result} == {"同稿", "正式另稿"}
    else:
        assert len(result) == 2 and set(reads) == {1, 2, 3}
        assert all(r["publication_date"] == "2026-10-09" for r in result)


def test_recovery_page_does_not_read_unselected_unrelated_bad_detail(monkeypatch):
    _, reads = source(monkeypatch, [], details={3: SourceError("aigupiao", "不需要的坏详情")})
    first = candidate_page([row(1, 100), row(2, 99), row(3, 98)])
    monkeypatch.setattr(single, "_pages", lambda *a: iter([first]))
    assert len(single.agp_fetch(limit=2, timeout=5)) == 2 and set(reads) == {1, 2}


def test_empty_page_cannot_contradict_same_request_remaining_count(monkeypatch):
    source(monkeypatch, [], total=1)
    with pytest.raises(SourceError, match="相互矛盾"):
        single.agp_fetch(timeout=5)


def test_source_ascii_numeric_counts_are_normalized(monkeypatch):
    source(monkeypatch, [row(1, 100)])
    post = old.post_form_json
    def as_text(*a, **k):
        result = post(*a, **k)
        result.update(total=str(result["total"]), last_page=str(result["last_page"]))
        return result
    monkeypatch.setattr(old, "post_form_json", as_text)
    assert len(single.agp_fetch(limit=2, timeout=5)) == 1


def test_each_http_keeps_full_timeout_when_cumulative_work_exceeds_it(monkeypatch):
    from threading import Lock
    rows = [row(i, 1000 - i) for i in range(1, 26)]
    calls, reads = source(monkeypatch, rows)
    dictionary = json.loads((FIXTURES / "industry-dictionary.json").read_text(encoding="utf-8"))
    total = [0.0]
    timeouts = []
    lock = Lock()
    def observe(kwargs):
        with lock:
            timeouts.append(kwargs["timeout"])
            total[0] += 10  # 每次成功请求耗时均小于12.5，累计可任意超过12.5。
    post, get = old.post_form_json, old._get_detail
    def observed_post(*a, **kw):
        observe(kw)
        return post(*a, **kw)
    def observed_get(*a, **kw):
        observe(kw)
        return get(*a, **kw)
    def industry(*a, **kw):
        observe(kw)
        return dictionary
    monkeypatch.setattr(old, "post_form_json", observed_post)
    monkeypatch.setattr(old, "_get_detail", observed_get)
    monkeypatch.setattr(old, "get_json", industry)
    result = single.agp_fetch(limit=30, industry="汽车行业", timeout=12.5)
    assert len(result) == 25 and total[0] > 12.5
    assert set(timeouts) == {12.5}
    assert len(reads) == len(set(reads)) == 25
    assert len(calls) >= 2


def test_detail_concurrency_is_bounded_and_result_ignores_completion_order(monkeypatch):
    from threading import Barrier, Condition, Lock
    source(monkeypatch, [row(i, 1000 - i) for i in range(1, 9)])
    barrier, condition, lock = Barrier(4), Condition(), Lock()
    active, peak, turn, finished = [0], [0], [4], []
    def detail(url, **kwargs):
        identity = int(url.rsplit("=", 1)[1])
        assert kwargs["timeout"] == 5
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        barrier.wait(timeout=2)
        with condition:
            assert condition.wait_for(lambda: turn[0] == identity, timeout=2)
            finished.append(identity)
            turn[0] = 8 if identity == 1 else identity - 1
            condition.notify_all()
        with lock:
            active[0] -= 1
        return dict(title=None, institute=None, publication_date="2026-10-09",
                    researcher=None, summary=str(identity), pdf_urls=[])
    monkeypatch.setattr(old, "_get_detail", detail)
    result = single.agp_fetch(limit=8, timeout=5)
    assert peak[0] == 4 and active[0] == 0
    assert finished == [4, 3, 2, 1, 8, 7, 6, 5]
    assert [r["summary"] for r in result] == [str(i) for i in range(1, 9)]


def test_request_timeout_failure_still_aborts_whole_list(monkeypatch):
    calls, _ = source(monkeypatch, [row(1, 100)])
    def timeout(*a, **kw):
        assert kw["timeout"] == 15
        raise SourceError("aigupiao", "网络请求失败（TimeoutError）")
    monkeypatch.setattr(old, "_get_detail", timeout)
    with pytest.raises(SourceError, match="TimeoutError"):
        single.agp_fetch(limit=1, timeout=15)


@pytest.mark.parametrize("missing", ["title", "institute", "publication_date"])
def test_three_part_key_missing_field_keeps_native_ids(monkeypatch, missing):
    _, reads = source(monkeypatch, [], details={i: {missing: None} for i in (1, 2)})
    page = candidate_page([row(1, 100), row(2, 99)])
    for _, _, candidate in page:
        candidate.update(title="同名", institute="同机构", publication_date="2026-10-09")
        candidate[missing] = None
        if missing == "publication_date":
            candidate["publication_date_text"] = None
    monkeypatch.setattr(single, "_pages", lambda *a: iter([page]))
    result = single.agp_fetch(limit=3, timeout=5)
    assert len(result) == 2 and sorted(reads) == [1, 2]
    assert all(r[missing] is None for r in result)


@pytest.mark.parametrize("split", [False, True])
def test_formal_date_regroups_without_repeating_details(monkeypatch, split):
    _, reads = source(monkeypatch, [], details={1: dict(publication_date="2026-10-09"),
        2: dict(publication_date="2026-10-08" if split else "2026-10-09")})
    first = candidate_page([row(1, 100), row(2, 99)])
    for identity, _, candidate in first:
        candidate.update(title="同名", institute="同机构",
                         publication_date_text="2026-10-09" if split or identity == "1" else "2026-10-08")
    second = candidate_page([row(2, 99), row(3, 98)])
    second[0][2].update(title="同名", institute="同机构")
    monkeypatch.setattr(single, "_pages", lambda *a: iter([first, second]))
    result = single.agp_fetch(limit=2, timeout=5)
    assert sorted(reads) == ([1, 2] if split else [1, 2, 3])
    assert len(result) == 2
    assert {r["publication_date"] for r in result} == ({"2026-10-09", "2026-10-08"} if split else {"2026-10-09"})


@pytest.mark.parametrize("text", ["20240229", "2024-02-29"])
def test_leap_day_catalog_fallback_keeps_raw_text_and_normalizes_day(monkeypatch, text):
    source(monkeypatch, [row(1, 100, pub_time=text)], details={1: dict(publication_date=None)})
    result = single.agp_fetch(limit=1, start_date="2024-02-29", end_date="2024-02-29", timeout=5)[0]
    assert result["publication_date"] == "2024-02-29"
    assert result["publication_date_text"] == text
