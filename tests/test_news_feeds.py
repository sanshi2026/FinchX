"""新闻来源真实短文、媒体结构与完整分页异常的业务验证。"""

from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import SourceError
from finchx._common.news import BEIJING_TZ
from finchx.sources.aigupiao import news as agp
from finchx.sources.baidu import news as bd

_FIXTURES = Path(__file__).parent / "fixtures"
_AGP = json.loads((_FIXTURES / "news_agp_rows.json").read_text(encoding="utf-8"))
_BD = json.loads((_FIXTURES / "news_bd_rows.json").read_text(encoding="utf-8"))
_AGP_FIELDS = {"id", "title", "published_at", "content", "important", "url", "related_securities", "related_themes", "related_topics", "image_urls", "video", "attachments"}
_BD_FIELDS = {"id", "title", "published_at", "content", "important", "url", "provider", "tag", "related_securities"}
_START = datetime(2026, 10, 8, 20, 0, tzinfo=BEIJING_TZ)


def response(source, rows):
    if source is agp:
        return {"rslt": "succ", "data": {"2026-10-08-4": {"data": rows}}}
    return {"ResultCode": "0", "Result": {"type": "expressnews", "content": {"list": rows}}}


def generated(source, start, count):
    rows = []
    for i in range(start, start + count):
        moment = str(int((_START - timedelta(seconds=i)).timestamp()))
        if source is agp:
            rows.append({"id": str(i), "rec_time": moment, "web_content": "【来源标题】正文", "important": "no"})
        else:
            rows.append({"loc": f"opaque-{i}", "publish_time": moment, "content": {"items": [{"type": "text", "data": "文字正文"}]}, "important": "0"})
    return rows


def serve(monkeypatch, source, pages):
    calls, iterator = [], iter(pages)
    def request(url, **kwargs):
        calls.append((parse_qs(urlsplit(url).query, keep_blank_values=True), kwargs))
        return deepcopy(next(iterator))
    monkeypatch.setattr(source, "get_json", request)
    return calls


def invoke(source, **kwargs):
    return (agp.agp_list if source is agp else bd.bd_list)(timeout=17, **kwargs)


def test_agp_real_short_text_title_and_video_units(monkeypatch):
    calls = serve(monkeypatch, agp, [response(agp, _AGP)])
    rows = invoke(agp, limit=2)
    assert all(set(row) == _AGP_FIELDS for row in rows)
    assert rows[0]["title"] == "伊朗原子能机构负责人称不会在铀浓缩问题上让步"
    assert rows[0]["content"] == _AGP[0]["web_content"]
    assert rows[0]["published_at"] == "2026-10-08T19:40:47+08:00"
    assert rows[0]["important"] is False and rows[0]["related_securities"] == []
    media = rows[1]
    assert media["video"]["duration_seconds"] == 1150
    assert set(media["video"]) == {"url", "thumbnail_url", "cover_url", "duration_seconds"}
    assert len(media["image_urls"]) == 2 and media["attachments"] == []
    assert media["related_topics"] == [{"id": "8674", "name": "#尊界被曝测试中刹车踏板支架断裂#"}]
    assert media["related_themes"][0] == {"id": "221", "name": "传感器"}
    assert calls[0][0]["number"] == ["20"] and "u_id" not in calls[0][0]
    assert calls[0][1]["timeout"] == 17


def test_bd_real_missing_title_and_cross_market_identity(monkeypatch):
    calls = serve(monkeypatch, bd, [response(bd, _BD)])
    row = invoke(bd, limit=1)[0]
    assert set(row) == _BD_FIELDS
    assert row["id"] == _BD[0]["loc"] and row["title"] is None
    assert row["published_at"] == "2026-10-08T20:15:19+08:00"
    assert row["related_securities"] == [{"code": "TSM", "name": "台积电", "market": "us"}]
    assert row["content"] == _BD[0]["content"]["items"][0]["data"]
    assert row["provider"] == "Finscope" and row["tag"] == "快讯$美股"
    assert calls[0][0]["rn"] == ["20"] and calls[0][0]["pn"] == ["0"]


def test_agp_oversized_source_page_retained_and_cursor_uses_last_source_row(monkeypatch):
    first, second = generated(agp, 0, 23), generated(agp, 23, 20)
    calls = serve(monkeypatch, agp, [response(agp, first), response(agp, second)])
    rows = invoke(agp, limit=40)
    assert [r["id"] for r in rows] == [str(i) for i in range(40)]
    assert calls[1][0]["before"] == [first[-1]["rec_time"]]
    assert calls[0][0]["before"] == ["0"]


def test_bd_overlap_updates_row_without_changing_order_or_offset(monkeypatch):
    first, second = generated(bd, 0, 20), generated(bd, 18, 20)
    second[0]["provider"] = "后读真实值"
    calls = serve(monkeypatch, bd, [response(bd, first), response(bd, second), response(bd, [])])
    rows = invoke(bd, limit=40)
    assert len(rows) == 38 and rows[18]["provider"] == "后读真实值"
    assert [r["id"] for r in rows] == [f"opaque-{i}" for i in range(38)]
    assert [call[0]["pn"] for call in calls] == [["0"], ["20"], ["40"]]


def test_bd_updated_news_enters_window_in_first_source_identity_order(monkeypatch):
    first, second = generated(bd, 0, 20), generated(bd, 20, 20)
    second[0]["loc"] = first[0]["loc"]
    second[0]["provider"] = "后读真实值"
    serve(monkeypatch, bd, [response(bd, first), response(bd, second)])
    rows = invoke(bd, limit=20, until="2026-10-08 19:59:50")
    assert rows[0]["id"] == "opaque-0" and rows[0]["provider"] == "后读真实值"
    assert rows[0]["published_at"] == "2026-10-08T19:59:40+08:00"
    assert rows[1]["id"] == "opaque-10"


@pytest.mark.parametrize("source", [agp, bd])
def test_updated_news_leaves_window_without_retaining_old_row(monkeypatch, source):
    first, second = generated(source, 0, 20), generated(source, 20, 20)
    identity, clock = ("id", "rec_time") if source is agp else ("loc", "publish_time")
    second[0][identity] = first[0][identity]
    second[0][clock] = second[1][clock]
    serve(monkeypatch, source, [response(source, first), response(source, second)])
    rows = invoke(source, limit=50, since="2026-10-08 19:59:40")
    assert len(rows) == 19 and first[0][identity] not in {row["id"] for row in rows}
    assert rows[0]["id"] == ("1" if source is agp else "opaque-1")


@pytest.mark.parametrize("source", [agp, bd])
def test_filters_before_limit_and_full_page_crosses_since(monkeypatch, source):
    first, second = generated(source, 0, 20), generated(source, 20, 20)
    calls = serve(monkeypatch, source, [response(source, first), response(source, second), response(source, generated(source, 40, 20))])
    until = "2026-10-08 19:59:40"
    # AGP 原生 until 跳转，因此其首个模拟页也须遵守排他上界。
    if source is agp:
        calls = serve(monkeypatch, source, [response(source, second), response(source, generated(source, 40, 20))])
    rows = invoke(source, limit=50, since="2026-10-08 19:59:30", until=until)
    assert len(rows) == 11
    assert rows[0]["published_at"] == "2026-10-08T19:59:40+08:00"
    assert rows[-1]["published_at"] == "2026-10-08T19:59:30+08:00"
    assert len(calls) == (2 if source is agp else 3)
    if source is agp:
        assert calls[0][0]["before"] == [str(int(_START.timestamp()) - 19)]


@pytest.mark.parametrize("source", [agp, bd])
def test_source_empty_and_valid_lower_bound_return_less_or_empty(monkeypatch, source):
    serve(monkeypatch, source, [response(source, [])])
    assert invoke(source, limit=40) == []
    serve(monkeypatch, source, [response(source, generated(source, 100, 2)), response(source, [])])
    assert len(invoke(source, limit=40)) == 2
    serve(monkeypatch, source, [response(source, generated(source, 100, 2))])
    assert invoke(source, since="2026-10-08 20:01:00") == []


def test_bd_official_empty_state_and_conflicting_empty_status(monkeypatch):
    serve(monkeypatch, bd, [{"ResultCode": "3402"}])
    assert invoke(bd) == []
    serve(monkeypatch, bd, [{"ResultCode": "3402", "Result": {"content": {"list": _BD}}}])
    with pytest.raises(SourceError):
        invoke(bd)


@pytest.mark.parametrize("source", [agp, bd])
@pytest.mark.parametrize("failure", ["duplicate", "tail_type", "tail_time", "order", "bad_status"])
def test_full_source_page_validated_even_after_limit(monkeypatch, source, failure):
    rows = generated(source, 0, 23)
    payload = response(source, rows)
    if failure == "duplicate": rows[-1] = deepcopy(rows[0])
    elif failure == "tail_type": rows[-1] = None
    elif failure == "tail_time": rows[-1]["rec_time" if source is agp else "publish_time"] = True
    elif failure == "order": rows[-2], rows[-1] = rows[-1], rows[-2]
    else: payload["rslt" if source is agp else "ResultCode"] = "fail"
    serve(monkeypatch, source, [payload])
    with pytest.raises(SourceError):
        invoke(source, limit=1)


@pytest.mark.parametrize("source", [agp, bd])
def test_stalled_page_and_budget_never_return_partial(monkeypatch, source):
    page = response(source, generated(source, 0, 20))
    serve(monkeypatch, source, [page, page])
    with pytest.raises(SourceError):
        invoke(source, limit=40)
    monkeypatch.setattr(source, "_MAX_PAGES", 1)
    serve(monkeypatch, source, [page])
    with pytest.raises(SourceError, match="防护上限"):
        invoke(source, limit=40)


def test_missing_relations_media_and_unmarked_title_are_not_fabricated(monkeypatch):
    raw = generated(agp, 0, 1)[0]
    raw["web_content"] = "普通首句，不制造标题。\r\n来源下一段。"
    serve(monkeypatch, agp, [response(agp, [raw])])
    row = invoke(agp, limit=1)[0]
    assert row["title"] is None and row["content"].endswith("\n来源下一段。")
    assert all(row[field] is None for field in ["related_securities", "related_themes", "related_topics", "image_urls", "video", "attachments"])


def test_agp_cross_market_symbols_and_explicit_media_zero(monkeypatch):
    raw = generated(agp, 0, 1)[0]
    raw["stock_infos"] = [{"kind": "stock", "code": code, "name": code} for code in ["USMETA", "SI", "bj920275"]]
    raw["video"] = {"kind": "small_video", "video": "https://example.org/video.mp4", "video_len": "0"}
    raw["file"] = [{"file_name": "测试附件", "file_type": "pdf", "file_link": "https://example.org/file.pdf"}]
    serve(monkeypatch, agp, [response(agp, [raw])])
    row = invoke(agp, limit=1)[0]
    assert [item["symbol"] for item in row["related_securities"]] == ["USMETA", "SI", "bj920275"]
    assert row["video"]["duration_seconds"] == 0 and row["video"]["cover_url"] is None
    assert row["attachments"] == [{"name": "测试附件", "type": "pdf", "url": "https://example.org/file.pdf"}]


@pytest.mark.parametrize("field,value", [("video", {"kind": "other"}), ("video", {"kind": "small_video", "video": "url", "video_len": "NaN"}), ("image", [0]), ("stock_infos", [{"kind": "new"}]), ("file", [False])])
def test_agp_known_business_damage_fails(monkeypatch, field, value):
    row = generated(agp, 0, 1)[0]
    row[field] = value
    serve(monkeypatch, agp, [response(agp, [row])])
    with pytest.raises(SourceError): invoke(agp, limit=1)


def test_bd_unknown_content_type_and_boolean_importance_fail(monkeypatch):
    for changes in [{"content": {"items": [{"type": "video", "data": "url"}]}}, {"important": True}]:
        raw = generated(bd, 0, 1)[0]
        raw.update(changes)
        serve(monkeypatch, bd, [response(bd, [raw])])
        with pytest.raises(SourceError): invoke(bd, limit=1)


@pytest.mark.parametrize("source", [agp, bd])
def test_new_cross_page_record_must_not_reverse_time_order(monkeypatch, source):
    first = generated(source, 0, 20)
    second = generated(source, 1, 20)
    second[0]["id" if source is agp else "loc"] = "previously-unseen"
    serve(monkeypatch, source, [response(source, first), response(source, second)])
    with pytest.raises(SourceError):
        invoke(source, limit=40)


def test_agp_date_upper_bound_initializes_next_beijing_midnight(monkeypatch):
    calls = serve(monkeypatch, agp, [response(agp, [])])
    assert invoke(agp, until="2026-10-08") == []
    assert calls[0][0]["before"] == [str(int(datetime(2026, 10, 9, tzinfo=BEIJING_TZ).timestamp()))]


def test_bd_title_is_source_text_or_explicit_leading_marker(monkeypatch):
    rows = generated(bd, 0, 3)
    rows[0]["title"] = "原始标题"
    rows[0]["content"]["items"] = [{"type": "text", "data": "【正文内标记】正文"}]
    rows[1]["content"]["items"] = [{"type": "text", "data": "【来源明确标题】正文"}]
    rows[2]["content"]["items"] = [{"type": "text", "data": "没有标记的首句。"}]
    serve(monkeypatch, bd, [response(bd, rows)])
    assert [row["title"] for row in invoke(bd, limit=3)] == ["原始标题", "来源明确标题", None]


@pytest.mark.parametrize("source", [agp, bd])
def test_independent_calls_do_not_cache_source_results(monkeypatch, source):
    calls = serve(monkeypatch, source, [response(source, generated(source, 0, 1)), response(source, generated(source, 1, 1))])
    first, second = invoke(source, limit=1), invoke(source, limit=1)
    assert first[0]["id"] != second[0]["id"] and len(calls) == 2


@pytest.mark.parametrize("source", [agp, bd])
@pytest.mark.parametrize("params", [{"limit": True}, {"limit": 0}, {"limit": None}, {"since": "2026-02-30"}, {"until": "2026-10-08T20:00:00+08:00"}, {"since": "2026-10-09", "until": "2026-10-08"}])
def test_invalid_parameters_fail_before_request(monkeypatch, source, params):
    calls = serve(monkeypatch, source, [])
    with pytest.raises(ValueError): invoke(source, **params)
    assert calls == []
