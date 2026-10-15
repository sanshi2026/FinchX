"""聚合研报的筛选、调度、容错和 HTML 业务契约。"""

from datetime import date
import time

import pytest

from finchx import FinchX, FinchXError, SourceError
from finchx._common import reports as core
from finchx._common.report_text import plain_text, to_markdown
from finchx.sources.aigupiao import reports_fetch as agp


def row(source, identity, day="2026-10-14", **extra):
    return dict(source=source, title="标题无需含搜索词", institute=None, publication_date=day,
                url=f"https://example.com/{source}/{identity}", content=None, content_type=None,
                pdf_urls=None, _id=str(identity), **extra)


@pytest.fixture
def sources(monkeypatch):
    modules = {"aigupiao": core.aigupiao, "eastmoney": core.eastmoney, "analysys": core.analysys}
    for module in modules.values():
        monkeypatch.setattr(module, "search_page", lambda *a, **k: ([], None))
        monkeypatch.setattr(module, "get_detail", lambda candidate, **k: dict(candidate, content="来源摘要", content_type="summary", pdf_urls=[]))
    return modules


def report(source, identity, title="同一研报", institute="同一机构", day="2026-10-14", **extra):
    return row(source, identity, day) | {"title": title, "institute": institute} | extra


@pytest.mark.parametrize("title,institute", [
    ("NPO产业发展加速，光模块产业持续受益", "群益证券"),
    ("公司事件点评报告：全年业绩预增，深度绑定核心客户，1.6T光模块放量在即", "华鑫证券"),
    ("成功向国内光通信龙头批量交付光模块AOI设备，平台化布局稳步落地", "东吴证券"),
])
def test_same_exact_title_and_institute_merge_cross_source(sources, monkeypatch, title, institute):
    for identity, source in enumerate(("aigupiao", "eastmoney")):
        candidate = report(source, identity, title, institute, content="原生摘要",
                           content_type="summary", pdf_urls=["https://example.com/report.pdf"])
        monkeypatch.setattr(sources[source], "search_page", lambda *a, candidate=candidate, **k: ([candidate], None))
    result = core.fetch("光模块", 1000, "20260101", "20261101", timeout=2)
    assert len(result["reports"]) == 1
    assert result["reports"][0]["source"] == "aigupiao"
    assert result["errors"] == []


def test_same_title_institute_different_dates_keep_whole_records(sources, monkeypatch):
    older = report("aigupiao", 1, day="2026-10-13", content="旧来源完整正文",
                   content_type="summary", pdf_urls=["https://example.com/old.pdf"])
    newer = report("eastmoney", 2, content="新来源正文", content_type="webpage",
                   pdf_urls=["https://example.com/new.pdf"])
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([older], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([newer], None))
    result = core.fetch("光模块", timeout=2)
    assert result["reports"] == [{key: candidate[key] for key in core._FIELDS} for candidate in (newer, older)]
    assert result["errors"] == []


@pytest.mark.parametrize("other_title,other_institute", [
    ("同一研报", "不同机构"), ("另一研报", "同一机构"),
    ("同一研报。", "同一机构"), ("同一研报", "同一机构。"),
    ("Report", "同一机构"), ("Ｒｅｐｏｒｔ", "同一机构"),
])
def test_exact_key_does_not_merge_other_titles_or_institutes(sources, monkeypatch, other_title, other_institute):
    first = report("aigupiao", 1, title="report" if other_title in ("Report", "Ｒｅｐｏｒｔ") else "同一研报")
    second = report("eastmoney", 2, title=other_title, institute=other_institute)
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([first], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([second], None))
    assert len(core.fetch("光模块", timeout=2)["reports"]) == 2


@pytest.mark.parametrize("title,institute", [(None, "机构"), ("", "机构"), ("标题", None), ("标题", "")])
def test_missing_key_fields_keep_native_records(sources, monkeypatch, title, institute):
    candidates = [report("aigupiao", i, title, institute) for i in (1, 2)]
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: (candidates, None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([report("eastmoney", 1, title, institute)], None))
    assert len(core.fetch("光模块", timeout=2)["reports"]) == 3


@pytest.mark.parametrize("body,pdfs", [("正文", []), (None, ["https://example.com/only.pdf"]),
                                      ("正文", ["https://example.com/both.pdf"])])
def test_same_day_prefers_confirmed_content_or_pdf_whole_record(sources, monkeypatch, body, pdfs):
    first = report("aigupiao", 1, content=None, content_type=None, pdf_urls=[])
    second = report("eastmoney", 2, content=body, content_type="summary" if body else None, pdf_urls=pdfs)
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([first], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([second], None))
    result = core.fetch("光模块", timeout=2)
    assert result["reports"] == [{key: second[key] for key in core._FIELDS}]


def test_both_content_and_pdf_preferred_over_content_only(sources, monkeypatch):
    first = report("aigupiao", 1, content="很长正文" * 100, content_type="summary", pdf_urls=[])
    second = report("eastmoney", 2, content="短正文", content_type="summary", pdf_urls=["https://example.com/both.pdf"])
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([first], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([second], None))
    assert core.fetch("光模块", timeout=2)["reports"][0]["url"] == second["url"]


def test_same_day_failed_detail_keeps_successful_copy_and_error(sources, monkeypatch):
    reads = []
    for source in ("aigupiao", "eastmoney"):
        candidate = report(source, 1)
        monkeypatch.setattr(sources[source], "search_page", lambda *a, candidate=candidate, **k: ([candidate], None))
    def failed(candidate, **kwargs):
        reads.append(candidate["source"])
        raise SourceError("aigupiao", "正文不可读")
    def successful(candidate, **kwargs):
        reads.append(candidate["source"])
        return dict(candidate, content="正常正文", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "get_detail", failed)
    monkeypatch.setattr(core.eastmoney, "get_detail", successful)
    result = core.fetch("光模块", 1, timeout=2)
    assert sorted(reads) == ["aigupiao", "eastmoney"]
    assert result["reports"][0]["source"] == "eastmoney"
    assert result["reports"][0]["content"] == "正常正文"
    assert result["errors"] == [{"source": "aigupiao", "url": "https://example.com/aigupiao/1", "reason": "正文不可读"}]


def test_dedup_limit_uses_remaining_same_page_candidates(sources, monkeypatch):
    candidates = [report("aigupiao", 1), report("aigupiao", 2), report("aigupiao", 3, title="另一篇")]
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: (candidates, None))
    result = core.fetch("光模块", 2, timeout=2)
    assert [r["title"] for r in result["reports"]] == ["同一研报", "另一篇"]
    assert result["errors"] == []


@pytest.mark.parametrize("duplicate_pages", [1, 5])
def test_dedup_limit_continues_pages_with_new_ids_same_business_key(sources, monkeypatch, duplicate_pages):
    calls = []
    cursors = [0] + list(range(100, 100 - duplicate_pages, -1))
    pages = {cursor: ([report("aigupiao", i * 2 + 1), report("aigupiao", i * 2 + 2)],
                       cursors[i + 1] if i + 1 < len(cursors) else 1)
             for i, cursor in enumerate(cursors)}
    pages[1] = ([report("aigupiao", 999, title="新研报")], None)
    def search(keyword, cursor, **kwargs):
        calls.append(cursor)
        return pages[cursor]
    monkeypatch.setattr(core.aigupiao, "search_page", search)
    result = core.fetch("光模块", 2, timeout=2)
    assert calls == cursors + [1]
    assert [r["title"] for r in result["reports"]] == ["同一研报", "新研报"]
    assert result["errors"] == []


@pytest.mark.parametrize("ending", ["exhausted", "failure", "budget"])
def test_dedup_supplement_ends_with_explicit_source_status(sources, monkeypatch, ending):
    calls = []
    def search(keyword, cursor, **kwargs):
        calls.append(cursor)
        if cursor == 0:
            return [report("aigupiao", 1), report("aigupiao", 2)], 10
        if ending == "failure":
            raise SourceError("aigupiao", "补页失败")
        if ending == "budget":
            time.sleep(.1)
        return [report("aigupiao", 3)], None
    monkeypatch.setattr(core.aigupiao, "search_page", search)
    result = core.fetch("光模块", 2, timeout=.03 if ending == "budget" else 2)
    assert calls == [0, 10]
    assert len(result["reports"]) == 1
    assert bool(result["errors"]) == (ending != "exhausted")
    if ending == "budget":
        time.sleep(.11)


@pytest.mark.parametrize("changed_field", ["title", "institute", "publication_date"])
def test_detail_key_change_merges_and_refills_next_page(sources, monkeypatch, changed_field):
    calls, reads = [], []
    first = report("aigupiao", 1)
    second = report("aigupiao", 2) | {changed_field: "2026-10-13" if changed_field == "publication_date" else "列表旧值"}
    pages = {0: ([first, second], 10), 10: ([report("aigupiao", 3, title="补位报告")], None)}
    def search(keyword, cursor, **kwargs):
        calls.append(cursor)
        return pages[cursor]
    def detail(candidate, **kwargs):
        reads.append(candidate["_id"])
        fields = {changed_field: first[changed_field]} if candidate["_id"] == "2" else {}
        return dict(candidate, **fields, content="正文", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "search_page", search)
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("光模块", 2, timeout=2)
    assert calls == [0, 10]
    assert sorted(reads) == ["1", "2", "3"]
    assert len(result["reports"]) == 2 and result["errors"] == []


@pytest.mark.parametrize("changed_field", ["title", "publication_date"])
def test_detail_splits_initial_duplicate_group_before_limit(sources, monkeypatch, changed_field):
    candidates = [report("aigupiao", 1), report("aigupiao", 2)]
    reads = []
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: (candidates, None))
    def detail(candidate, **kwargs):
        reads.append(candidate["_id"])
        return dict(candidate, **{changed_field: "2026-10-1" + candidate["_id"] if changed_field == "publication_date"
                                 else "正式标题" + candidate["_id"]},
                    content="正文", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("光模块", 2, timeout=2)
    assert sorted(reads) == ["1", "2"]
    assert len(result["reports"]) == 2 and result["errors"] == []


def test_detail_new_date_reselects_whole_representative(sources, monkeypatch):
    for source in ("aigupiao", "eastmoney"):
        candidate = report(source, 1)
        monkeypatch.setattr(sources[source], "search_page", lambda *a, candidate=candidate, **k: ([candidate], None))
    def detail(candidate, **kwargs):
        return dict(candidate, publication_date="2026-10-15" if candidate["source"] == "eastmoney" else "2026-10-14",
                    content=candidate["source"], content_type="summary", pdf_urls=[])
    for module in sources.values():
        monkeypatch.setattr(module, "get_detail", detail)
    result = core.fetch("光模块", 1, timeout=2)
    assert result["reports"][0]["source"] == result["reports"][0]["content"] == "eastmoney"
    assert result["reports"][0]["publication_date"] == "2026-10-15"


def test_unknown_dates_keep_native_records_in_source_order(sources, monkeypatch):
    first = report("aigupiao", 1, day=None, content="首条", content_type="summary", pdf_urls=[])
    second = report("aigupiao", 2, day=None, content="第二条更长正文" * 100, content_type="summary", pdf_urls=[])
    other_source = report("eastmoney", 1, day=None, content="其他来源", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([first, second], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([other_source], None))
    result = core.fetch("光模块", timeout=2)
    assert result["reports"] == [{key: candidate[key] for key in core._FIELDS}
                                 for candidate in (first, second, other_source)]


def test_newer_failed_record_keeps_older_different_day_and_error(sources, monkeypatch):
    older = report("aigupiao", 1, day="2026-10-13", content="旧正文", content_type="summary", pdf_urls=[])
    newer = report("eastmoney", 1)
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([older], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([newer], None))
    def failed(candidate, **kwargs):
        raise SourceError("eastmoney", "新稿详情失败")
    monkeypatch.setattr(core.eastmoney, "get_detail", failed)
    result = core.fetch("光模块", timeout=2)
    assert result["reports"] == [{key: candidate[key] for key in core._FIELDS} for candidate in (newer, older)]
    assert result["errors"][0]["reason"] == "新稿详情失败"


def test_confirmed_duplicate_does_not_skip_other_copy_detail(sources, monkeypatch):
    confirmed = report("aigupiao", 1, content="确认正文", content_type="summary", pdf_urls=[])
    unconfirmed = report("eastmoney", 1, content="列表摘要", content_type="summary")
    reads = []
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([confirmed], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([unconfirmed], None))
    def detail(candidate, **kwargs):
        reads.append(candidate["source"])
        return dict(candidate, content="完整新正文", pdf_urls=["https://example.com/confirmed.pdf"])
    monkeypatch.setattr(core.eastmoney, "get_detail", detail)
    result = core.fetch("光模块", 1, timeout=2)
    assert reads == ["eastmoney"]
    assert result["reports"][0]["source"] == "eastmoney"
    assert result["reports"][0]["content"] == "完整新正文"


def test_duplicate_detail_date_exclusion_reselects_existing_copy(sources, monkeypatch):
    older = report("aigupiao", 1, day="2026-10-13", content="较早正文", content_type="summary", pdf_urls=[])
    newer = report("eastmoney", 1)
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([older], None))
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([newer], None))
    monkeypatch.setattr(core.eastmoney, "get_detail", lambda candidate, **k: dict(
        candidate, publication_date="2026-11-02", content="超范围正文", content_type="summary", pdf_urls=[]))
    result = core.fetch("光模块", 1, "2026-01-01", "2026-11-01", timeout=2)
    assert result["reports"] == [{key: older[key] for key in core._FIELDS}]
    assert result["errors"] == []


def test_fetch_thin_forward_and_signature(monkeypatch):
    sentinel = object()
    calls = []
    def fetch(*args, **kwargs):
        calls.append((args, kwargs))
        return sentinel
    monkeypatch.setattr(core, "fetch", fetch)
    assert FinchX(timeout=3).reports.fetch(" 汽车 ", 7, "20261001", "2026/10/14") is sentinel
    assert calls == [((" 汽车 ", 7, "20261001", "2026/10/14"), {"timeout": 3})]


@pytest.mark.parametrize("kwargs", [
    {"keyword": ""}, {"keyword": 1}, {"keyword": "\n"}, {"keyword": "\ud800"},
    {"limit": True}, {"limit": 0}, {"limit": None}, {"start_date": date(2026, 1, 1)},
    {"start_date": "2026-02-30"}, {"end_date": "2026-10-14 24:00:00"},
    {"start_date": "20261014", "end_date": "20261013"},
])
def test_invalid_parameters_do_not_call_sources(sources, monkeypatch, kwargs):
    def forbidden(*a, **k):
        pytest.fail("参数错误不能联网")
    for module in sources.values():
        monkeypatch.setattr(module, "search_page", forbidden)
    with pytest.raises(ValueError):
        core.fetch(**({"keyword": "汽车"} | kwargs), timeout=2)


def test_native_keyword_date_before_limit_stable_sort_final_details(sources, monkeypatch):
    searches, reads = [], []
    pages = {
        0: ([row("aigupiao", 1, "2025-01-01"), row("aigupiao", 2, "2026-10-12")], 10),
        10: ([row("aigupiao", 3, "2026-10-14")], None),
    }
    def search(keyword, cursor, *, timeout):
        searches.append((keyword, cursor))
        assert 0 < timeout <= 2
        return pages[cursor]
    monkeypatch.setattr(core.aigupiao, "search_page", search)
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: ([row("eastmoney", 4, "2026-10-14")], None))
    def detail(candidate, *, timeout):
        reads.append(candidate["_id"])
        return dict(candidate, content="全文", content_type="summary", pdf_urls=[])
    for module in sources.values():
        monkeypatch.setattr(module, "get_detail", detail)
    result = core.fetch("来源原生词", 2, "2026/10/01 12:34:56", timeout=2)
    assert searches == [("来源原生词", 0), ("来源原生词", 10)]
    assert [r["source"] for r in result["reports"]] == ["aigupiao", "eastmoney"]
    assert sorted(reads) == ["3", "4"]
    assert all(len(r) == 8 and r["content"] == "全文" for r in result["reports"])
    assert result["errors"] == []


def test_unknown_date_resolved_once_and_existing_body_reused(sources, monkeypatch):
    candidate = row("aigupiao", 1, None, _date_text="10-14")
    reads = []
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([candidate], None))
    def detail(candidate, **kwargs):
        reads.append(candidate["_id"])
        return dict(candidate, publication_date="2026-10-14", content="摘要", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    monkeypatch.setattr(core.analysys, "search_page", lambda *a, **k: ([row("analysys", 2, content_type_unused=None) | {"content": "原生正文", "content_type": "webpage", "pdf_urls": []}], None))
    result = core.fetch("汽车", 2, "20261014", timeout=2)
    assert reads == ["1"]
    assert [r["content"] for r in result["reports"]] == ["摘要", "原生正文"]


def test_duplicate_updates_first_position_single_overlap_allowed(sources, monkeypatch):
    pages = {
        0: ([row("aigupiao", 1)], 10),
        10: ([row("aigupiao", 1) | {"title": "更新标题"}], 9),
        9: ([row("aigupiao", 2)], None),
    }
    monkeypatch.setattr(core.aigupiao, "search_page", lambda keyword, cursor, **k: pages[cursor])
    result = core.fetch("汽车", 2, timeout=2)
    assert [r["title"] for r in result["reports"]] == ["更新标题", "标题无需含搜索词"]


def test_partial_search_detail_errors_and_empty_success(sources, monkeypatch):
    def broken(*a, **k):
        raise SourceError("eastmoney", "来源网络失败")
    monkeypatch.setattr(core.eastmoney, "search_page", broken)
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([row("aigupiao", 1)], None))
    def detail(*a, **k):
        raise SourceError("aigupiao", "来源详情不可读")
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("汽车", timeout=2)
    assert len(result["reports"]) == 1
    assert result["reports"][0]["pdf_urls"] is None
    assert {e["reason"] for e in result["errors"]} == {"来源网络失败", "来源详情不可读"}
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([], None))
    result = core.fetch("汽车", timeout=2)
    assert result["reports"] == [] and len(result["errors"]) == 1


def test_all_fail_raises_with_sources_and_programming_error_not_swallowed(sources, monkeypatch):
    def broken(*a, **k):
        raise SourceError("来源", "来源失败")
    for module in sources.values():
        monkeypatch.setattr(module, "search_page", broken)
    with pytest.raises(FinchXError) as caught:
        core.fetch("汽车", timeout=2)
    assert len(caught.value.errors) == 3
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        core.fetch("汽车", timeout=2)


def test_budget_preserves_confirmed_records_and_passes_remaining(sources, monkeypatch):
    remaining = []
    def search(keyword, cursor, *, timeout):
        remaining.append(timeout)
        if cursor == 0:
            return [row("aigupiao", 1)], 1
        time.sleep(0.10)
        return [], None
    monkeypatch.setattr(core.aigupiao, "search_page", search)
    started = time.monotonic()
    result = core.fetch("汽车", 2, timeout=.04)
    assert time.monotonic() - started < .09
    assert len(result["reports"]) == 1 and result["errors"]
    # 单调时钟浮点减法在不同平台允许 1e-9 秒舍入误差。
    assert 0 < remaining[1] <= remaining[0] <= .04 + 1e-9
    time.sleep(.11)  # 故意超时的模拟请求结束，避免泄漏测试工作线程。


def test_markdown_keeps_image_position_paragraph_heading_list_and_skips_scripts():
    html = '<h2>标题</h2><p>首段<img src="blank.gif" data-original="/真实.png">尾句</p><ul><li>项目</li></ul><script>secret</script>'
    text = to_markdown(html, base_url="https://example.com/a", source="analysys")
    assert "## 标题" in text and "- 项目" in text
    assert text.index("首段") < text.index("![") < text.index("尾句")
    assert "https://example.com/真实.png" in text and "secret" not in text and "blank" not in text
    assert plain_text("<em>汽车</em>报告") == "汽车报告"
    assert to_markdown('<img src="/图.jpg">', base_url="https://example.com", source="aigupiao")


def test_same_page_unsorted_candidates_are_ranked_before_limit(sources, monkeypatch):
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: (
        [row("aigupiao", 1, "2020-01-01"), row("aigupiao", 2, "2026-10-14")], None))
    result = core.fetch("汽车", 1, timeout=2)
    assert result["reports"][0]["url"].endswith("/2")


def test_detail_date_changes_refilter_resort_and_fill_from_existing_candidates(sources, monkeypatch):
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: (
        [row("aigupiao", 1, "2026-10-14"), row("aigupiao", 2, "2026-10-13"), row("aigupiao", 3, "2026-10-12")], None))
    reads = []
    def detail(candidate, **kwargs):
        reads.append(candidate["_id"])
        day = "2025-01-01" if candidate["_id"] == "1" else "2026-10-11" if candidate["_id"] == "2" else "2026-10-12"
        return dict(candidate, publication_date=day, content="全文", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("汽车", 1, "2026-10-01", timeout=2)
    assert reads == ["1", "2", "3"]
    assert result["reports"][0]["url"].endswith("/3")


def test_slow_source_does_not_exhaust_successful_source_detail_budget(sources, monkeypatch):
    def slow(*a, **k):
        time.sleep(.12)
        return [], None
    monkeypatch.setattr(core.eastmoney, "search_page", slow)
    monkeypatch.setattr(core.aigupiao, "search_page", lambda *a, **k: ([row("aigupiao", 1)], None))
    budgets = []
    def detail(candidate, *, timeout):
        budgets.append(timeout)
        return dict(candidate, content="成功摘要", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("汽车", 1, timeout=.04)
    assert result["reports"][0]["content"] == "成功摘要"
    # 单调时钟浮点减法在不同平台允许 1e-9 秒舍入误差。
    assert 0 < budgets[0] <= .04 + 1e-9
    assert result["errors"][0]["source"] == "eastmoney"
    time.sleep(.13)


def test_agp_native_search_duplicate_rows_and_real_keyword(monkeypatch):
    item = {"inv_id": 1, "sort_time": 100, "title": "不含词", "pub_time": "10-14"}
    calls = []
    def post(url, *, data, **kwargs):
        calls.append(data)
        return {"code": 0, "status": "succ", "total": 2, "last_page": 1, "data": [item, item | {"title": "更新"}]}
    monkeypatch.setattr(agp.old, "post_form_json", post)
    rows, cursor = agp.search_page("汽车", 0, timeout=2)
    assert cursor == 100 and len(rows) == 2
    assert rows[0]["publication_date"] is None
    assert calls[0]["keyword"] == "汽车" and calls[0]["kind"] == "all"


def test_agp_pure_image_content_and_one_html_request(monkeypatch):
    page = '''<div class="text01"><h1>图文报告</h1><p>研究机构：测试机构</p><p>发布日期：2026-10-14</p><img data-original="/image.png"></div>'''
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return page
    monkeypatch.setattr(agp.old, "get_text", get)
    candidate = row("aigupiao", 1, None) | {"url": agp.old._DETAIL + "1"}
    result = agp.get_detail(candidate, timeout=2)
    assert result["content"] == "![](http://101.35.29.159:82/image.png)"
    assert result["content_type"] == "summary" and result["pdf_urls"] == []
    assert result["publication_date"] == "2026-10-14" and result["institute"] == "测试机构"
    assert len(calls) == 1


def test_agp_fetch_ignores_fields_outside_business_contract(monkeypatch):
    item = {"inv_id": 1, "sort_time": 1, "title": "报告", "pub_time": "2026-10-14",
            "rec_time": object(), "rating": [], "theme_id": {}, "ref_kind": 123, "stock_code": []}
    monkeypatch.setattr(agp.old, "post_form_json", lambda *a, **k: {"code": 0, "status": "succ", "data": [item]})
    rows, cursor = agp.search_page("汽车", 0, timeout=2)
    assert rows[0]["title"] == "报告" and cursor == 1


def test_agp_preserves_business_section_headings(monkeypatch):
    page = '<div class="text01"><h1>报告标题</h1><h2>行业趋势</h2><p>保留正文</p></div>'
    monkeypatch.setattr(agp.old, "get_text", lambda *a, **k: page)
    result = agp.get_detail(row("aigupiao", 1) | {"url": agp.old._DETAIL + "1"}, timeout=2)
    assert result["content"] == "## 行业趋势\n\n保留正文"
    assert result["title"] == "报告标题"


def test_duplicate_after_early_detail_keeps_later_search_metadata_if_not_in_detail(sources, monkeypatch):
    pages = {
        0: ([row("aigupiao", 1, None, _date_text="10-14") | {"title": "初次搜索标题", "institute": "初次机构"}], 10),
        10: ([row("aigupiao", 1, None, _date_text="10-14") | {"title": "后读搜索标题", "institute": "后读机构"}], 9),
        9: ([row("aigupiao", 2, "2026-10-13")], None),
    }
    monkeypatch.setattr(core.aigupiao, "search_page", lambda keyword, cursor, **kwargs: pages[cursor])
    reads = []
    def detail(candidate, **kwargs):
        reads.append(candidate["_id"])
        return dict(candidate, publication_date="2026-10-14", content="正文", content_type="summary", pdf_urls=[],
                    _detail_fields=("publication_date",))
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("汽车", 2, "20261001", timeout=2)
    assert reads.count("1") == 1
    assert result["reports"][0]["title"] == "后读搜索标题"
    assert result["reports"][0]["institute"] == "后读机构"


def test_exception_stops_late_source_from_starting_more_requests(sources, monkeypatch):
    calls = []
    def slow(keyword, cursor, **kwargs):
        calls.append(("search", cursor))
        time.sleep(.06)
        return [row("aigupiao", 1, None, _date_text="10-14")], 10
    def detail(*a, **k):
        calls.append(("detail", None))
        pytest.fail("退出后不应再启动请求")
    monkeypatch.setattr(core.aigupiao, "search_page", slow)
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    monkeypatch.setattr(core.eastmoney, "search_page", lambda *a, **k: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        core.fetch("汽车", 2, timeout=.03)
    time.sleep(.07)
    assert calls == [("search", 0)]


@pytest.mark.parametrize("excluded_count", [1, 2])
def test_detail_exclusion_continues_real_next_pages(sources, monkeypatch, excluded_count):
    calls, reads = [], []
    def search(keyword, cursor, **kwargs):
        calls.append(cursor)
        identity = 1 if cursor == 0 else 2 if cursor == 10 else 3
        return [row("aigupiao", identity)], 10 if cursor == 0 else 9 if cursor == 10 else None
    def detail(candidate, **kwargs):
        reads.append(candidate["_id"])
        return dict(candidate, publication_date="2025-01-01" if int(candidate["_id"]) <= excluded_count else "2026-10-14",
                    content="全文", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "search_page", search)
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("汽车", 1, "20261001", timeout=2)
    assert calls == [0, 10] if excluded_count == 1 else calls == [0, 10, 9]
    assert len(reads) == excluded_count + 1
    assert result["reports"][0]["url"].endswith(f"/{excluded_count + 1}")
    assert result["errors"] == []


@pytest.mark.parametrize("ending", ["empty", "error", "timeout"])
def test_detail_exclusion_followup_exhaustion_failure_and_budget(sources, monkeypatch, ending):
    calls = []
    def search(keyword, cursor, **kwargs):
        calls.append(cursor)
        if cursor == 0:
            return [row("aigupiao", 1)], 10
        if ending == "error":
            raise SourceError("aigupiao", "补页网络失败")
        if ending == "timeout":
            time.sleep(.10)
        return [], None
    def detail(candidate, **kwargs):
        return dict(candidate, publication_date="2025-01-01", content="全文", content_type="summary", pdf_urls=[])
    monkeypatch.setattr(core.aigupiao, "search_page", search)
    monkeypatch.setattr(core.aigupiao, "get_detail", detail)
    result = core.fetch("汽车", 1, "20261001", timeout=.03 if ending == "timeout" else 2)
    assert calls == [0, 10]
    assert result["reports"] == []
    assert bool(result["errors"]) == (ending != "empty")
    if ending == "timeout":
        time.sleep(.11)
