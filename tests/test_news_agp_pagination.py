"""按 before 实际过滤及容量截断的 AGP 秒边界业务回归。"""

from copy import deepcopy
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import SourceError
from finchx._common.news import BEIJING_TZ
from finchx.sources.aigupiao import news as agp


_MIDNIGHT = datetime(2026, 10, 13, tzinfo=BEIJING_TZ)


def article(identity, moment, **changes):
    row = {"id": identity, "rec_time": str(int(moment.timestamp())),
           "web_content": f"【{identity}】正文", "important": "no"}
    row.update(changes)
    return row


def sequence(count, *, start=_MIDNIGHT):
    return [article(f"news-{index}", start - timedelta(seconds=index)) for index in range(count)]


def grouped(rows, *, unordered=False):
    # 组名和展示标题有意不同于实际时间；页面选中记录再按源分组呈现。
    if unordered:
        halves = [rows[len(rows) // 2:], rows[:len(rows) // 2]]
    else:
        halves = [rows]
    return {"rslt": "succ", "last_time": max((str(row["rec_time"]) for row in rows), default="0"),
            "date_time": "2026-10-13 12:34:56",
            "data": {f"2020-01-01-{index}": {"title": "展示分组", "data": part}
                     for index, part in enumerate(halves)}}


def server(monkeypatch, data, *, unordered=False, fixed_cap=None, transform=None):
    """模拟按秒排他过滤后截 number，再以来源分组顺序呈现。"""
    calls, source_pages = [], []

    def request(url, **kwargs):
        params = parse_qs(urlsplit(url).query, keep_blank_values=True)
        before, number = int(params["before"][0]), int(params["number"][0])
        calls.append((before, number, kwargs))
        eligible = [row for row in data if not before or int(row["rec_time"]) < before]
        eligible.sort(key=lambda row: -int(row["rec_time"]))
        selected = deepcopy(eligible[:number if fixed_cap is None else min(number, fixed_cap)])
        if transform:
            selected = transform(selected, len(calls))
        payload = grouped(selected, unordered=unordered)
        source_pages.append([row for group in payload["data"].values() for row in group["data"]])
        return payload

    monkeypatch.setattr(agp, "get_json", request)
    return calls, source_pages


def request(**kwargs):
    return agp.agp_list(timeout=17, **kwargs)


def first_identity_order(pages):
    return list(dict.fromkeys(row["id"] for page in pages for row in page))


def test_group_order_uses_real_min_and_preserves_first_identity_order(monkeypatch):
    data = sequence(61)
    calls, pages = server(monkeypatch, data, unordered=True)
    rows = request(limit=61)
    assert [row["id"] for row in rows] == first_identity_order(pages)
    assert len({row["id"] for row in rows}) == 61
    assert calls[1][:2] == (int(data[19]["rec_time"]) + 1, 20)
    assert {row["id"] for row in rows} == {row["id"] for row in data}
    assert all(len(row) == 12 for row in rows)


def test_group_tail_above_since_does_not_change_whole_page_stop(monkeypatch):
    data = sequence(60)
    calls, _ = server(monkeypatch, data, unordered=True)
    rows = request(limit=100, since="2026-10-12 23:59:50")
    assert {row["id"] for row in rows} == {row["id"] for row in data[:11]}
    assert len(calls) == 2


@pytest.mark.parametrize("bucket_size", [1, 7, 19])
def test_same_second_bucket_has_no_missing_ids_across_pages(monkeypatch, bucket_size):
    boundary = [article(f"same-{index}", _MIDNIGHT) for index in range(bucket_size)]
    older = sequence(30, start=_MIDNIGHT - timedelta(seconds=1))
    calls, pages = server(monkeypatch, boundary + older)
    rows = request(limit=bucket_size + 10)
    assert [row["id"] for row in rows] == first_identity_order(pages)[:bucket_size + 10]
    assert [row["id"] for row in rows[:bucket_size]] == [row["id"] for row in boundary]
    assert len({row["id"] for row in rows}) == bucket_size + 10
    assert all(number == 20 for _, number, _ in calls)
    assert all(kwargs["timeout"] == 17 for _, _, kwargs in calls)


def test_cross_midnight_same_second_and_inclusive_both_bounds(monkeypatch):
    newest = [article(f"upper-{index}", _MIDNIGHT + timedelta(seconds=1)) for index in range(7)]
    boundary = [article(f"midnight-{index}", _MIDNIGHT) for index in range(15)]
    lower = [article(f"lower-{index}", _MIDNIGHT - timedelta(seconds=1)) for index in range(13)]
    outside = [article("too-new", _MIDNIGHT + timedelta(seconds=2)),
               article("too-old", _MIDNIGHT - timedelta(seconds=2))]
    calls, _ = server(monkeypatch, outside + newest + boundary + lower, unordered=True)
    rows = request(limit=100, since="2026-10-12 23:59:59", until="2026-10-13 00:00:01")
    assert {row["id"] for row in rows} == {row["id"] for row in newest + boundary + lower}
    assert len(rows) == 35 and len({row["id"] for row in rows}) == 35
    assert calls[0][0] == int(_MIDNIGHT.timestamp()) + 2
    assert all(number == 20 for _, number, _ in calls)


def test_same_second_since_until_still_finishes_bucket(monkeypatch):
    boundary = [article(f"same-{index}", _MIDNIGHT) for index in range(19)]
    calls, _ = server(monkeypatch, boundary + [article("older", _MIDNIGHT - timedelta(seconds=1))])
    rows = request(limit=100, since="2026-10-13 00:00:00", until="2026-10-13 00:00:00")
    assert {row["id"] for row in rows} == {row["id"] for row in boundary}
    assert [number for _, number, _ in calls] == [20, 20]


def test_boundary_overlap_later_row_replaces_all_fields_at_first_position(monkeypatch):
    data = sequence(60)

    def update(selected, call):
        if call == 2:
            selected[0].update(web_content="更新后的完整正文", title="后读标题", important="yes")
        return selected

    calls, _ = server(monkeypatch, data, transform=update)
    rows = request(limit=40)
    assert len(rows) == 40 and [row["id"] for row in rows] == [row["id"] for row in data[:40]]
    assert rows[19]["content"] == "更新后的完整正文"
    assert rows[19]["title"] == "后读标题" and rows[19]["important"] is True
    assert len(calls) == 3


@pytest.mark.parametrize("damage", ["id", "time", "body", "duplicate", "relations"])
def test_older_filtered_rows_are_validated_before_lower_stop(monkeypatch, damage):
    data = sequence(60)

    def corrupt(selected, call):
        if call == 2:
            if damage == "id": selected[-1]["id"] = ""
            elif damage == "time": selected[-1]["rec_time"] = True
            elif damage == "body": selected[-1]["web_content"] = None
            elif damage == "duplicate": selected[-1] = deepcopy(selected[0])
            else: selected[-1]["stock_infos"] = [{"kind": "unknown"}]
        return selected

    server(monkeypatch, data, transform=corrupt)
    with pytest.raises(SourceError):
        request(limit=100, since="2026-10-12 23:59:50")


@pytest.mark.parametrize("bucket_size", [20, 21, 40, 79, 150])
def test_fixed_source_batch_never_skips_unconfirmed_boundary_records(monkeypatch, bucket_size):
    data = [article(f"same-{index}", _MIDNIGHT) for index in range(bucket_size)] + sequence(30, start=_MIDNIGHT - timedelta(seconds=1))
    calls, _ = server(monkeypatch, data, fixed_cap=20)
    with pytest.raises(SourceError, match="边界秒未推进.*固定批次.*同秒新闻完整"):
        request(limit=bucket_size + 10)
    assert [number for _, number, _ in calls] == [20, 20]
    assert len({before for before, _, _ in calls[1:]}) == 1


def test_boundary_bucket_above_capacity_fails_without_partial(monkeypatch):
    server(monkeypatch, [article(f"same-{index}", _MIDNIGHT) for index in range(400)])
    with pytest.raises(SourceError, match="边界秒未推进"):
        request(limit=500)


def test_page_budget_never_returns_partial(monkeypatch):
    server(monkeypatch, sequence(100))
    monkeypatch.setattr(agp, "_MAX_PAGES", 2)
    with pytest.raises(SourceError, match="分页达到防护上限"):
        request(limit=100)


def test_initial_upper_bound_same_second_allows_first_boundary_probe(monkeypatch):
    calls, _ = server(monkeypatch, [article(f"same-{index}", _MIDNIGHT) for index in range(7)])
    with pytest.raises(SourceError, match="边界秒未推进"):
        request(limit=100, until="2026-10-13 00:00:00")
    assert len(calls) == 2 and calls[0][:2] == calls[1][:2]


def test_empty_boundary_probe_is_not_source_exhaustion(monkeypatch):
    def empty_overlap(selected, call):
        return [] if call == 2 else selected

    calls, _ = server(monkeypatch, sequence(60), transform=empty_overlap)
    with pytest.raises(SourceError, match="边界秒重叠页为空.*同秒新闻完整"):
        request(limit=40)
    assert len(calls) == 2


def test_initial_valid_empty_page_remains_legal_exhaustion(monkeypatch):
    calls, _ = server(monkeypatch, [])
    assert request(limit=100, until="2026-10-13") == []
    assert len(calls) == 1


def test_explicit_before_violation_is_not_tolerated_as_overlap(monkeypatch):
    data = sequence(60)

    def corrupt(selected, call):
        if call == 2:
            selected[-1] = deepcopy(data[0])
        return selected

    server(monkeypatch, data, transform=corrupt)
    with pytest.raises(SourceError, match="before 排他上界"):
        request(limit=40)


def test_normal_first_page_retains_published_fields_and_order(monkeypatch):
    data = sequence(30)
    calls, _ = server(monkeypatch, data)
    rows = request(limit=20)
    expected = [agp._row(row, agp._moment(row["rec_time"])) for row in data[:20]]
    assert rows == expected
    assert len(calls) == 1 and calls[0][:2] == (0, 20)
