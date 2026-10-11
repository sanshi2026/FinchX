"""公开文章业务契约与分页失败语义；样本结构取自已核公开来源。"""

from copy import deepcopy
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.aigupiao import articles as source

LIST_FIELDS = {"url", "title", "published_at", "author", "summary", "content", "image_urls",
               "category", "topics", "related_securities", "audio_url"}
DETAIL_FIELDS = LIST_FIELDS - {"url"} | {"ai_summary", "disclaimer"}


def row(identity="5792378", kind="user_msg"):
    return {"live": {"title": "主线纪要", "image": "https://img.example/avatar.jpg"}, "msg": {
        "id": identity, "kind": kind, "title": "油运暴涨，轮到造船？", "rec_time": "1791463920",
        "brief_pc": "", "brief": "主线纪要｜美银研报发布于10月6日", "content_pc":
        "<p>主线纪要｜美银研报发布于10月6日</p><p>油运再次走到行情前排。</p>",
        "content": "主线纪要｜美银研报发布于10月6日油运再次走到行情前排。",
        "image": ["https://img.example/body.png"], "article_category_name": "题材行业",
        "topic": [{"id": "8662", "title": "#光遗传学研究获26年诺奖#"}], "stock_info": [
            {"kind": "stock", "code": "sh600026", "name": "中远海能"},
            {"kind": "stock", "code": "bj920522", "name": "梓橦宫"},
            {"kind": "stock", "code": "CL", "name": "WTI原油"},
            {"kind": "stock", "code": "USQCOM", "name": "高通"},
            {"kind": "theme", "code": "", "name": "脑机接口"}],
        "pay_type": "1", "not_vip_show": "yes", "unknown_extra": {"any": True}}}


def page(*rows):
    return {"rslt": "succ", "code": "x0000", "data_list": list(rows)}


def user_detail():
    raw = deepcopy(row()["msg"])
    raw.update(nickname="主线纪要", content_edit='<p>首段包含 ; } 和 &amp; 字符。</p><p>第二段。</p>',
               image=[], image_1="https://img.example/body.png", ai_summary="来源平台摘要",
               disclaimer="来源免责声明", source="浙江")
    raw.pop("brief_pc")
    raw.pop("brief")
    return raw


def html(raw, libs=None):
    scripts = '<script>var rslt_content = ' + json.dumps(raw, ensure_ascii=False) + ';\n'
    if libs is not None:
        scripts += 'var _Libs = ' + json.dumps(libs) + ';\n'
    return '<html><script src="unrelated.js"></script>' + scripts + '</script></html>'


def pages(monkeypatch, values):
    calls = []
    iterator = iter(values)
    def fetch(url, **kwargs):
        calls.append((url, kwargs))
        return next(iterator)
    monkeypatch.setattr(source, "get_json", fetch)
    return calls


@pytest.mark.parametrize("sort", ["newest", "hot"])
def test_native_sort_twelve_rows_consumed_then_overlap_updates_first_position(monkeypatch, sort):
    first = [row(str(100 + i)) for i in range(12)]
    update = row("100")
    update["msg"]["title"] = "后读真实标题"
    calls = pages(monkeypatch, [page(*first), page(update, row("112"))])
    result = source.agp_topic_articles(13, sort, timeout=7)
    assert len(result) == 13
    assert result[0]["title"] == "后读真实标题"
    assert result[11]["url"].endswith("/111")
    assert result[-1]["url"].endswith("/112")
    assert set(result[0]) == LIST_FIELDS
    assert result[0]["published_at"] == "2026-10-08T20:52:00+08:00"
    assert result[0]["author"] == "主线纪要"
    assert result[0]["topics"] == ["#光遗传学研究获26年诺奖#"]
    assert [item["symbol"] for item in result[0]["related_securities"]] == ["sh600026", "bj920522", "CL", "USQCOM"]
    assert len(calls) == 2
    for index, (url, kwargs) in enumerate(calls, 1):
        query = parse_qs(urlsplit(url).query)
        assert query == {"number": ["10"], "division": ["1"], "page": [str(index)],
                         "article_type": ["1"], "article_order_by": [sort]}
        assert kwargs["timeout"] == 7


def test_short_pages_continue_until_genuine_empty(monkeypatch):
    calls = pages(monkeypatch, [page(row("1")), page(row("2", "free")), page()])
    result = source.agp_topic_articles(20, timeout=3)
    assert len(result) == 2 and len(calls) == 3
    assert result[1]["url"] == "https://www.aigupiao.com/view/detail/2"


def test_empty_first_page_is_empty_list(monkeypatch):
    pages(monkeypatch, [page()])
    assert source.agp_topic_articles(timeout=3) == []


def test_full_source_page_validated_even_beyond_output_limit(monkeypatch):
    bad = row("2")
    bad["msg"]["stock_info"] = False
    pages(monkeypatch, [page(row("1"), bad)])
    with pytest.raises(SourceError):
        source.agp_topic_articles(1, timeout=3)


def test_duplicate_page_identity_fails(monkeypatch):
    pages(monkeypatch, [page(row(), row())])
    with pytest.raises(SourceError, match="同页"):
        source.agp_topic_articles(timeout=3)


def test_stagnation_fails_without_partial(monkeypatch):
    pages(monkeypatch, [page(row()), page(row())])
    with pytest.raises(SourceError, match="停滞"):
        source.agp_topic_articles(timeout=3)


def test_page_budget_fails_without_partial(monkeypatch):
    monkeypatch.setattr(source, "_MAX_PAGES", 2)
    pages(monkeypatch, [page(row("1")), page(row("2"))])
    with pytest.raises(SourceError, match="防护上限"):
        source.agp_topic_articles(timeout=3)


@pytest.mark.parametrize("limit", [True, False, 0, -1, 1.5, "1", None])
def test_bad_limit_before_network(monkeypatch, limit):
    monkeypatch.setattr(source, "get_json", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(ValueError):
        source.agp_topic_articles(limit, timeout=3)


@pytest.mark.parametrize("sort", [None, True, [], "latest", "HOT"])
def test_bad_sort_before_network(monkeypatch, sort):
    monkeypatch.setattr(source, "get_json", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(ValueError):
        source.agp_topic_articles(sort=sort, timeout=3)


@pytest.mark.parametrize("payload", [{}, {"rslt": "fail", "code": "x0000", "data_list": []},
                                     {"rslt": "succ", "code": "x0000"},
                                     {"rslt": "succ", "code": "x0000", "data_list": None}, page({})])
def test_broken_page_is_not_empty_success(monkeypatch, payload):
    pages(monkeypatch, [payload])
    with pytest.raises(SourceError):
        source.agp_topic_articles(timeout=3)


@pytest.mark.parametrize("field,value", [("id", True), ("id", "中文"), ("kind", {}),
    ("kind", "unknown"), ("title", 0), ("brief", {}), ("content", False),
    ("content_pc", 7), ("rec_time", True), ("rec_time", "2026-02-30 11:00:00"),
    ("rec_time", float("nan")), ("image", "url"), ("image", [False]),
    ("article_category_name", []), ("topic", [{}]), ("stock_info", [{"kind": "other"}])])
def test_known_field_corruption_fails(monkeypatch, field, value):
    raw = row()
    raw["msg"][field] = value
    pages(monkeypatch, [page(raw)])
    with pytest.raises(SourceError):
        source.agp_topic_articles(timeout=3)


def test_empty_title_and_explicit_body_missing_keep_valid_paid_row(monkeypatch):
    raw = row(kind="charge")
    raw["msg"].update(title="", content_pc=None, content="", image=[], brief="", brief_pc="")
    pages(monkeypatch, [page(raw)])
    result = source.agp_topic_articles(1, timeout=3)[0]
    assert result["title"] is None and result["content"] is None and result["summary"] is None
    assert result["image_urls"] == []


def test_missing_relations_and_zero_timestamp_are_distinct(monkeypatch):
    raw = row()
    raw["msg"].update(rec_time=0, topic=None, stock_info=None, article_category_name=None)
    pages(monkeypatch, [page(raw)])
    result = source.agp_topic_articles(1, timeout=3)[0]
    assert result["published_at"] == "1970-01-01T08:00:00+08:00"
    assert result["topics"] is None and result["related_securities"] is None and result["category"] is None


def test_user_detail_robust_json_text_tables_images_and_no_cross_request_fill(monkeypatch):
    raw = user_detail()
    raw["content_edit"] += '<table><tr><th>指标</th><th>数值</th></tr><tr><td>利润</td><td>0</td></tr></table><p><img src="https://img.example/body.png"></p>'
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return html(raw)
    monkeypatch.setattr(source, "get_text", fetch)
    monkeypatch.setattr(source, "get_json", lambda *a, **k: pytest.fail("unexpected extra request"))
    result = source.agp_get('http://www.aigupiao.com/Dynamic/user_dynamic_detail?o_id=5792378', timeout=3)
    assert set(result) == DETAIL_FIELDS
    assert result["content"] == "首段包含 ; } 和 & 字符。\n第二段。\n指标\t数值\n利润\t0"
    assert result["summary"] is None
    assert result["image_urls"] == ["https://img.example/body.png"]
    assert result["ai_summary"] == "来源平台摘要"
    assert result["disclaimer"] == "来源免责声明"
    assert "source_name" not in result
    assert calls == ["https://www.aigupiao.com/dynamic/detail/5792378"]


def test_live_detail_uses_page_public_parameters_and_author_not_biaoti(monkeypatch):
    raw = row("4141992", "charge")["msg"]
    raw.update(live_id="280", title="题材君", biaoti="固态电池提速！", rec_time="2026-10-08 20:18", content_edit="<p>公开正文</p>",
               image="https://img.example/avatar.jpg", image_url=[], brief="来源摘要", brief_pc="")
    monkeypatch.setattr(source, "get_text", lambda *a, **k: html({"id": "4141992", "l_id": "280", "kind": "charge"}, {"md": "公开值"}))
    calls = pages(monkeypatch, [{"rslt": "succ", "show_detail": [raw]}])
    result = source.agp_get("https://www.aigupiao.com/view/detail/4141992", timeout=3)
    assert set(result) == DETAIL_FIELDS
    assert result["title"] == "固态电池提速！" and result["author"] == "题材君"
    assert result["published_at"] == "2026-10-08T20:18+08:00"
    assert result["image_urls"] == []
    assert result["ai_summary"] is None
    query = parse_qs(urlsplit(calls[0][0]).query)
    assert query == {"act": ["load_detail"], "id": ["280"], "oid": ["4141992"], "source": ["pc"], "md": ["公开值"]}
    assert "md" not in result


@pytest.mark.parametrize("url", [None, {}, "https://evil.com/dynamic/detail/1", "https://www.aigupiao.com.evil/dynamic/detail/1",
    "https://www.aigupiao.com:443/dynamic/detail/1", "https://user@www.aigupiao.com/dynamic/detail/1",
    "https://www.aigupiao.com/dynamic/detail/1?q=x", "https://www.aigupiao.com/dynamic/detail/1#x",
    "https://www.aigupiao.com/dynamic/detail/１２", "https://www.aigupiao.com/dynamic/detail/0",
    "https://www.aigupiao.com/Dynamic/user_dynamic_detail?o_id=1&o_id=2"])
def test_bad_url_before_network(monkeypatch, url):
    monkeypatch.setattr(source, "get_text", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(ValueError):
        source.agp_get(url, timeout=3)


@pytest.mark.parametrize("body", ["<h1>登录或错误页</h1>", '<script>var rslt_content = {broken};</script>',
    '<script>var rslt_content = [];</script>', html({"id": "2", "kind": "user_msg", "content": "text"}),
    html({"id": "5792378", "kind": "user_msg"}), html({"id": "5792378", "kind": "other", "content": "text"}),
    html(user_detail()) + html(user_detail())])
def test_broken_web_page_fails(monkeypatch, body):
    monkeypatch.setattr(source, "get_text", lambda *a, **k: body)
    with pytest.raises(SourceError):
        source.agp_get("https://www.aigupiao.com/dynamic/detail/5792378", timeout=3)


@pytest.mark.parametrize("payload", [{"rslt": "fail", "show_detail": []}, {"rslt": "succ", "show_detail": []},
    {"rslt": "succ", "show_detail": [{"id": "999", "live_id": "280", "kind": "charge", "content": "text"}]},
    {"rslt": "succ", "show_detail": [{"id": "4141992", "live_id": "281", "kind": "charge", "content": "text"}]}])
def test_live_wrong_event_or_error_fails(monkeypatch, payload):
    monkeypatch.setattr(source, "get_text", lambda *a, **k: html({"id": "4141992", "l_id": "280", "kind": "charge"}, {"md": "public"}))
    pages(monkeypatch, [payload])
    with pytest.raises(SourceError):
        source.agp_get("https://www.aigupiao.com/view/detail/4141992", timeout=3)


def test_detail_preserves_public_voice_url_without_duration(monkeypatch):
    raw = user_detail()
    raw["voice"] = json.dumps({"duration": "594.864000", "url": "https://media.example/article.mp3"})
    monkeypatch.setattr(source, "get_text", lambda *a, **k: html(raw))
    result = source.agp_get("https://www.aigupiao.com/dynamic/detail/5792378", timeout=3)
    assert result["audio_url"] == "https://media.example/article.mp3"
    assert set(result) == DETAIL_FIELDS
    assert "duration" not in result


@pytest.mark.parametrize("voice", [False, "{broken", "[]", '{}', '{"url": false}'])
def test_malformed_known_voice_fails(monkeypatch, voice):
    raw = user_detail()
    raw["voice"] = voice
    monkeypatch.setattr(source, "get_text", lambda *a, **k: html(raw))
    with pytest.raises(SourceError):
        source.agp_get("https://www.aigupiao.com/dynamic/detail/5792378", timeout=3)


def test_list_preserves_audio_link_or_explicit_empty(monkeypatch):
    first, second = row("1"), row("2")
    first["msg"]["audio"] = "https://media.example/message.mp3"
    second["msg"]["audio"] = ""
    pages(monkeypatch, [page(first, second)])
    result = source.agp_topic_articles(2, timeout=3)
    assert result[0]["audio_url"] == "https://media.example/message.mp3"
    assert result[1]["audio_url"] is None


@pytest.mark.parametrize("kind", [[], {}, False])
def test_live_bad_kind_is_source_error(monkeypatch, kind):
    monkeypatch.setattr(source, "get_text", lambda *a, **k: html({"id": "4141992", "l_id": "280", "kind": kind}, {"md": "public"}))
    with pytest.raises(SourceError):
        source.agp_get("https://www.aigupiao.com/view/detail/4141992", timeout=3)


def test_embedded_article_code_does_not_become_second_json_assignment(monkeypatch):
    raw = user_detail()
    raw["content_edit"] = '<p>代码说明 var rslt_content = {not_json};</p>'
    monkeypatch.setattr(source, "get_text", lambda *a, **k: html(raw))
    result = source.agp_get("https://www.aigupiao.com/dynamic/detail/5792378", timeout=3)
    assert result["content"] == '代码说明 var rslt_content = {not_json};'


def test_verified_live_account_mentions_are_not_securities(monkeypatch):
    # 真实详情 4141257/4141077 的账号项与正文 live/detail_new.php 链接对应。
    raw = user_detail()
    raw["stock_info"] = [
        {"kind": "stock", "code": "CL", "name": "原油"},
        {"l_id": 67, "name": "行者"},
        {"l_id": 221, "name": "星辰"},
        {"kind": "theme", "code": "", "name": "脑机接口"},
    ]
    raw["content_edit"] = (
        '<p>先<a href="https://www.aigupiao.com/live/detail_new.php?id=67&amp;act=msg">行者</a></p>'
        '<p>宇宙<a href="https://www.aigupiao.com/live/detail_new.php?id=221&amp;act=msg">星辰</a></p>'
    )
    monkeypatch.setattr(source, "get_text", lambda *args, **kwargs: html(raw))
    result = source.agp_get("https://www.aigupiao.com/dynamic/detail/5792378", timeout=3)
    assert result["related_securities"] == [{"symbol": "CL", "name": "原油"}]
    assert result["content"] == "先行者\n宇宙星辰"
    assert set(result) == DETAIL_FIELDS


@pytest.mark.parametrize("relation", [
    {"l_id": 0, "name": "行者"}, {"l_id": -1, "name": "行者"},
    {"l_id": True, "name": "行者"}, {"l_id": None, "name": "行者"},
    {"l_id": [], "name": "行者"}, {"l_id": "67.0", "name": "行者"},
    {"l_id": 67, "name": ""}, {"l_id": 67, "name": None},
    {"l_id": 67, "name": False}, {"l_id": 67},
    {"name": "行者"}, {"code": "sh600026", "name": "中远海能"},
    {"l_id": 67, "code": "sh600026", "name": "中远海能"},
    {"l_id": 67, "kind": None, "name": "行者"},
    {"l_id": 67, "kind": "unconfirmed", "name": "行者"},
    {"l_id": 67, "kind": "stock", "code": False, "name": "中远海能"},
])
def test_account_relation_does_not_hide_malformed_or_unconfirmed_identity(monkeypatch, relation):
    raw = user_detail()
    raw["stock_info"] = [relation]
    monkeypatch.setattr(source, "get_text", lambda *args, **kwargs: html(raw))
    with pytest.raises(SourceError):
        source.agp_get("https://www.aigupiao.com/dynamic/detail/5792378", timeout=3)


def test_explicit_account_only_relations_are_empty_not_unknown(monkeypatch):
    raw = row()
    raw["msg"]["stock_info"] = [{"l_id": 67, "name": "行者"}]
    pages(monkeypatch, [page(raw)])
    assert source.agp_topic_articles(1, timeout=3)[0]["related_securities"] == []


def test_same_public_dynamic_article_can_have_verified_express_kind(monkeypatch):
    # 真实目录 5789405 为 user_msg，同 ID 公共详情为 express。
    raw = user_detail()
    raw.update(id="5789405", kind="express", title="", content_edit="<p>来源公开正文</p>")
    monkeypatch.setattr(source, "get_text", lambda *args, **kwargs: html(raw))
    result = source.agp_get("https://www.aigupiao.com/dynamic/detail/5789405", timeout=3)
    assert set(result) == DETAIL_FIELDS
    assert result["title"] is None and result["content"] == "来源公开正文"


@pytest.mark.parametrize("url", [
    "https://www.aigupiao.com/vi\new/detail/123",
    "https://www.aigupiao.com/vi\rew/detail/123",
    "https://www.aigu\tpiao.com/view/detail/123",
    "https://www.aigupiao.com/view/detail/12\x003",
    "https://www.aigupiao.com/view/detail/123\x7f",
    "https://www.aigupiao.com/view/detail/123\\",
    "https://www.aigupiao.com/view/detail/123 ",
    "https://www.aigupiao.com/view/detail/123\u00a0",
])
def test_url_control_whitespace_and_backslash_fail_before_network(monkeypatch, url):
    monkeypatch.setattr(source, "get_text", lambda *args, **kwargs: pytest.fail("unexpected network"))
    with pytest.raises(ValueError):
        source.agp_get(url, timeout=3)

