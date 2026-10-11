"""热榜真实官方响应复放；失败和分页边界使用明确构造变体。"""

from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.tonghuashun import hotlist

FIXTURES = Path(__file__).parent / "fixtures" / "hotlist"
STOCK_FIELDS = {"rank", "code", "exchange", "name", "change_percent", "heat", "rank_change",
                "concept_tags", "popularity_tag", "analysis_title", "analysis", "search_count", "updated_at", "issue_pe"}
SECTOR_FIELDS = {"rank", "sector_code", "name", "change_percent", "heat", "rank_change", "tag", "hot_tag",
                 "related_etf_code", "related_etf_exchange", "related_etf_name", "related_etf_change_percent"}
BOND_FIELDS = {"rank", "code", "exchange", "name", "change_percent", "heat"}
ETF_FIELDS = BOND_FIELDS | {"tags"}


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text(encoding="utf-8"))


@pytest.fixture
def replay(monkeypatch):
    """按真实请求选择完整捕获，标签子集仅选取捕获中的原始行。"""
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        path = urlsplit(url).path
        query = parse_qs(urlsplit(url).query)
        if path.endswith("new_stock.txt"):
            return fixture("new_stock")
        if path.endswith("/stock"):
            category = {value: key for key, value in hotlist._STOCK_TYPES.items()}[query["list_type"][0]]
            return fixture("stock_" + category + "_" + query["type"][0])
        if path.endswith("/plate"):
            return fixture("plate_" + query["type"][0])
        if path.endswith("/bond"):
            return fixture("bond")
        pytest.fail("unexpected GET " + url)
    def post(url, **kwargs):
        calls.append((url, kwargs))
        data = kwargs["data"]
        if url == hotlist._INDEX:
            return fixture("index_sector")
        if url == hotlist._RECOMMEND:
            return fixture("index_etf_recommend")
        if url == hotlist._INDEX_ETF_QUOTES:
            return fixture("index_etf_quotes")
        if url == hotlist._POOL:
            category = {value: key for key, value in hotlist._POOL_KEYS.items()}[data["businessPoolKey"]]
            return fixture("etf_pool_" + category)
        if url == hotlist._METRICS:
            requested = set(data["code_selectors"]["include"][0]["values"])
            for category in hotlist._POOL_KEYS:
                value = fixture("etf_metrics_all" if category == "popular" else "etf_metrics_" + category)
                if {row["code"] for row in value["data"]["data"]} == requested:
                    return value
            pytest.fail("unexpected ETF identity selection")
        if url == hotlist._TAGS:
            value = fixture("etf_tags_all_correct")
            requested = set(data["code_selectors"]["include"][0]["values"])
            value["data"]["data"] = [row for row in value["data"]["data"] if row["code"] in requested]
            return value
        pytest.fail("unexpected POST " + url)
    monkeypatch.setattr(hotlist, "get_json", get)
    monkeypatch.setattr(hotlist, "post_json", post)
    return calls


def test_real_technical_fixed_fourteen_fields_and_source_rank(replay):
    rows = hotlist.stocks(category="technical", limit=None, timeout=4)
    assert len(rows) == 100 and all(set(row) == STOCK_FIELDS for row in rows)
    assert rows[0] == {"rank": 1, "code": "603906", "exchange": "sh", "name": "龙蟠科技",
                       "change_percent": 6.0172, "heat": 29240.0, "rank_change": 2,
                       "concept_tags": ["钠离子电池", "固态电池"], "popularity_tag": "热搜",
                       "analysis_title": None, "analysis": None, "search_count": 1190,
                       "updated_at": "2026-10-09T09:48:29+08:00", "issue_pe": None}
    assert rows[-1]["rank"] == 100  # 原order=536，display_order=100。
    assert parse_qs(urlsplit(replay[0][0]).query) == {"stock_type": ["a"], "list_type": ["tech"], "type": ["day"]}
    assert replay[0][1]["timeout"] == 4


@pytest.mark.parametrize("category,period,count", [("popular", None, 100), ("popular", "24h", 100),
                                                    ("rising", None, 100), ("rising", "24h", 100),
                                                    ("value", None, 100), ("trend", None, 40), ("new", None, 4)])
def test_real_stock_categories_source_windows_north_and_missing_price(replay, category, period, count):
    rows = hotlist.stocks(category=category, period=period, limit=None, timeout=2)
    assert len(rows) == count and all(set(row) == STOCK_FIELDS for row in rows)
    if category == "popular" and period == "24h":
        assert rows[-1]["change_percent"] == 0
    if category == "new":
        assert rows[0]["updated_at"] is rows[0]["change_percent"] is rows[0]["issue_pe"] is None
        assert rows[1]["issue_pe"] == 27.99 and rows[2]["exchange"] == "bj" and rows[2]["code"] == "920196"
        assert all(row["updated_at"] is None for row in rows)


def test_real_plate_and_bonds_fixed_fields(replay):
    sectors = hotlist.sectors(limit=None, timeout=1)
    assert len(sectors) == 20 and all(set(row) == SECTOR_FIELDS for row in sectors)
    assert sectors[0] == {"rank": 1, "sector_code": "886032", "name": "固态电池",
                          "change_percent": -1.4903, "heat": 213391.5, "rank_change": 0,
                          "tag": "5家涨停", "hot_tag": "5天5次上榜", "related_etf_code": "159156",
                          "related_etf_exchange": "sz", "related_etf_name": "电池ETF",
                          "related_etf_change_percent": -0.7538}
    industry = hotlist.sectors("industry", limit=1, timeout=1)[0]
    assert industry["sector_code"] == "881281" and industry["related_etf_code"] == "159147"
    bonds = hotlist.convertible_bonds(None, timeout=1)
    assert len(bonds) == 100 and all(set(row) == BOND_FIELDS for row in bonds)
    assert bonds[0] == {"rank": 1, "code": "123268", "exchange": "sz", "name": "本川转债",
                        "change_percent": 7.6939, "heat": 109634.5}
    assert any(row["exchange"] == "sh" for row in bonds)


def test_real_index_window_full_source_identity_and_nineteen_unique_etfs(replay):
    rows = hotlist.sectors("index", None, timeout=3)
    assert len(rows) == 20 and all(set(row) == SECTOR_FIELDS for row in rows)
    assert rows[0] == {"rank": 1, "sector_code": "120:931743", "name": "半导体材料设备",
                       "change_percent": -4.0217, "heat": 20001.0, "rank_change": None, "tag": None,
                       "hot_tag": None, "related_etf_code": "159327", "related_etf_exchange": "sz",
                       "related_etf_name": "半导体设备ETF万家", "related_etf_change_percent": -4.191617}
    assert rows[4]["sector_code"] == "120:H30184"
    assert replay[0][1]["data"] == {"page_info": {"page_begin": 0, "page_size": 20}}
    assert replay[1][1]["data"] == {"stockCodeList": [row["sector_code"] for row in rows], "uniqueId": ""}
    assert len(replay[2][1]["data"]["code_selectors"]["include"][0]["values"]) == 19
    assert all(row["rank_change"] is row["tag"] is row["hot_tag"] is None for row in rows)


@pytest.mark.parametrize("category,count", [("popular", 1693), ("t0", 345), ("price_limit_20", 247),
                                            ("cross_border", 248), ("commodity", 17)])
def test_real_all_etf_pools_complete_then_metrics_sort_and_selected_tags(replay, category, count):
    rows = hotlist.etfs(category, limit=None, timeout=5)
    assert len(rows) == count and all(set(row) == ETF_FIELDS for row in rows)
    assert [row["rank"] for row in rows] == list(range(1, count + 1))
    assert all(rows[index]["heat"] >= rows[index+1]["heat"] for index in range(count-1))
    if category == "popular":
        assert rows[0] == {"rank": 1, "code": "588060", "exchange": "sh", "name": "科创50ETF广发",
                           "change_percent": -2.810811, "heat": 15337193.4, "tags": ["连跌3天", "存储芯片"]}
        assert len([row for row in rows if row["change_percent"] is None]) == 9
        assert len([row for row in rows if row["change_percent"] == 0]) == 56
        missing_name = next(row for row in rows if row["code"] == "158030")
        assert missing_name["name"] is None and missing_name["exchange"] == "sz"
    assert len(replay) == 3
    assert replay[1][1]["data"]["page_info"]["page_size"] == count
    assert replay[2][1]["data"]["tag_infos"] == [{"tag_key": key} for key in hotlist._TAG_KEYS]
    assert replay[1][1]["headers"]["Source-Id"] == replay[2][1]["headers"]["Source-Id"] == "ths-hot-list"


def test_tags_only_requested_after_full_metrics_and_limit(replay):
    rows = hotlist.etfs(limit=1, timeout=1)
    assert len(rows) == 1
    assert len(replay[1][1]["data"]["code_selectors"]["include"][0]["values"]) == 1693
    assert replay[2][1]["data"]["code_selectors"]["include"][0]["values"] == ["20:588060"]


@pytest.mark.parametrize("function,kwargs", [
    (hotlist.stocks, {"category": []}), (hotlist.stocks, {"period": []}),
    (hotlist.stocks, {"category": "new", "period": "1h"}), (hotlist.stocks, {"category": "other"}),
    (hotlist.sectors, {"sector_type": "other"}), (hotlist.etfs, {"category": None}),
    (hotlist.stocks, {"limit": True}), (hotlist.sectors, {"limit": 0}),
    (hotlist.convertible_bonds, {"limit": -1}), (hotlist.etfs, {"limit": 1.1}),
    (hotlist.stocks, {"timeout": False})])
def test_bad_public_parameters_fail_before_http(monkeypatch, function, kwargs):
    monkeypatch.setattr(hotlist, "get_json", lambda *args, **kwargs: pytest.fail("invalid input performed HTTP"))
    monkeypatch.setattr(hotlist, "post_json", lambda *args, **kwargs: pytest.fail("invalid input performed HTTP"))
    with pytest.raises(ValueError):
        function(**({"timeout": 1} | kwargs))


@pytest.mark.parametrize("field,bad", [("market", 999), ("market", False), ("code", "１２３４５６"),
                                      ("code", "123"), ("display_order", 0), ("display_order", True),
                                      ("rate", True), ("rate", float("nan")), ("rate", -1),
                                      ("rise_and_fall", {}), ("search_cnt", 1.5),
                                      ("update_time", "2026-02-30 01:02:03"), ("update_time", "20261009 01:02:03"),
                                      ("tag", []), ("analyse", {})])
def test_constructed_bad_business_in_last_stock_row_fails_before_limit(monkeypatch, field, bad):
    payload = fixture("stock_technical_day")
    payload["data"]["stock_list"][-1][field] = bad
    monkeypatch.setattr(hotlist, "get_json", lambda *args, **kwargs: payload)
    with pytest.raises(SourceError):
        hotlist.stocks(category="technical", limit=1, timeout=1)


def test_constructed_unknown_and_unverified_new_fields_do_not_change_contract(monkeypatch):
    payload = fixture("new_stock")
    first = payload["data"]["stock_list"][0]
    first.update(time={}, orderDate=False, topic=["unknown"], unknown_new={"bad": object()}, pe=0)
    first["tag"]["concept_tag"] = []
    monkeypatch.setattr(hotlist, "get_json", lambda *args, **kwargs: payload)
    row = hotlist.stocks("new", limit=1, timeout=1)[0]
    assert row["issue_pe"] == 0 and row["updated_at"] is None and row["concept_tags"] == []
    assert set(row) == STOCK_FIELDS


def test_constructed_duplicates_rank_order_and_empty_current_bonds(monkeypatch):
    payload = fixture("bond")
    payload["data"] = [payload["data"][1], payload["data"][0]]
    monkeypatch.setattr(hotlist, "get_json", lambda *args, **kwargs: payload)
    assert [row["rank"] for row in hotlist.convertible_bonds(None, timeout=1)] == [1, 2]
    payload["data"].append(deepcopy(payload["data"][0]))
    with pytest.raises(SourceError):
        hotlist.convertible_bonds(1, timeout=1)
    payload["data"] = []
    assert hotlist.convertible_bonds(timeout=1) == []


def small_pool(codes, total, offset=0, limit=2):
    """构造池分页，不冒称真实全量响应。"""
    rows = [[code, code.split(":")[0], code.split(":")[1], code, code] for code in codes]
    definitions = [{"type": name} for name in ["etfName", "subMarket", "tradeCode", "simpleName", "code"]]
    return {"status_code": 0, "data": {"total": total, "offset": offset, "limit": limit,
                                      "indexes": definitions, "itemList": rows}}


def post_sequence(monkeypatch, pages):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        payload = pages.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return deepcopy(payload)
    monkeypatch.setattr(hotlist, "post_json", post)
    return calls


def test_constructed_pool_overlap_retries_complete_identity_and_later_row_update(monkeypatch):
    monkeypatch.setattr(hotlist, "_POOL_PAGE_SIZE", 2)
    pages = [small_pool(["20:518850", "20:518680"], 3), small_pool(["20:518680"], 3, 2),
             small_pool(["20:518600", "20:518850"], 3), small_pool(["20:518680"], 3, 2)]
    pages[3]["data"]["itemList"][0][0] = "后读名称"
    calls = post_sequence(monkeypatch, pages)
    result = hotlist._fund_pool("commodity", 1)
    assert set(result) == {"20:518850", "20:518680", "20:518600"}
    assert result["20:518680"]["name"] == "后读名称"
    assert [call[1]["data"]["custom"]["offset"] for call in calls] == [0, 2, 0, 2]


@pytest.mark.parametrize("pages", [
    [small_pool(["20:518850"], 3)],  # 提前短页。
    [small_pool(["20:518850", "20:518850"], 2)],  # 同页重复。
    [small_pool(["20:518850", "20:518680"], 3), small_pool(["20:518600"], 4, 2)],  # 漂移。
    [small_pool(["20:518850", "20:518680"], 3), small_pool(["20:518680"], 3, 2)] * 3,
    [small_pool(["20:518850", "20:518680"], 3), SourceError("tonghuashun", "request failed")],
])
def test_constructed_pool_failures_never_partial(monkeypatch, pages):
    monkeypatch.setattr(hotlist, "_POOL_PAGE_SIZE", 2)
    post_sequence(monkeypatch, pages)
    with pytest.raises(SourceError):
        hotlist._fund_pool("commodity", 1)


def test_constructed_pool_empty_and_budget(monkeypatch):
    post_sequence(monkeypatch, [small_pool([], 0)])
    assert hotlist.etfs(timeout=1) == []
    monkeypatch.setattr(hotlist, "_POOL_PAGE_SIZE", 2)
    monkeypatch.setattr(hotlist, "_MAX_POOL_PAGES", 1)
    post_sequence(monkeypatch, [small_pool(["20:518850", "20:518680"], 3)])
    with pytest.raises(SourceError, match="防护"):
        hotlist._fund_pool("popular", 1)


def test_constructed_dynamic_indexes_heat_missing_and_zero_keep_identity(monkeypatch):
    payload = fixture("etf_metrics_commodity")
    rows = payload["data"]["data"][:3]
    payload["data"]["total"] = 3
    payload["data"]["data"] = rows
    # 真实值的构造边界：定义重排，不带metadata.idx时数组位置即values.idx。
    payload["data"]["indexes"].reverse()
    for row in rows:
        for value in row["values"]:
            value["idx"] = 1 - value["idx"]
    rows[0]["values"][1]["value"] = None
    rows[1]["values"][1]["value"] = 0
    rows[2]["values"][1]["value"] = 0
    pool = {row["code"]: {"code": row["code"].split(":")[1], "exchange": "sh", "name": None} for row in rows}
    post_sequence(monkeypatch, [payload])
    result = hotlist._fund_metrics(pool, 1)
    assert [row[1]["code"] for row in result] == ["518600", "518680", "518850"]
    assert [row[1]["heat"] for row in result] == [0, 0, None]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unexpected", "nonfinite", "badstatus", "badtotal"])
def test_constructed_metrics_failure_after_full_pool(monkeypatch, mutation):
    payload = fixture("etf_metrics_commodity")
    pool_payload = fixture("etf_pool_commodity")
    pool = dict(hotlist._pool_page(pool_payload, 0)[1])
    if mutation == "missing":
        payload["data"]["data"].pop()
    elif mutation == "duplicate":
        payload["data"]["data"].append(deepcopy(payload["data"]["data"][0]))
    elif mutation == "unexpected":
        payload["data"]["data"][0]["code"] = "20:588060"
    elif mutation == "nonfinite":
        payload["data"]["data"][-1]["values"][0]["value"] = float("inf")
    elif mutation == "badstatus":
        payload["status_code"] = False
    else:
        payload["data"]["total"] = 18
    post_sequence(monkeypatch, [payload])
    with pytest.raises(SourceError):
        hotlist._fund_metrics(pool, 1)


def test_constructed_tags_all_empty_missing_and_unknown_groups(monkeypatch):
    payload = fixture("etf_tags_all_correct")
    payload["data"]["data"] = payload["data"]["data"][:3]
    identities = [row["code"] for row in payload["data"]["data"]]
    for group in payload["data"]["data"][0]["values"]:
        group["show_tag"] = []
    payload["data"]["data"][0]["values"].append({"tag_key": "future_tag", "show_tag": {"ignored": True}})
    payload["data"]["data"][1]["values"][0].pop("show_tag")
    payload["data"]["data"][2]["values"] = None
    post_sequence(monkeypatch, [payload])
    assert hotlist._fund_tags(identities, 1) == {identities[0]: [], identities[1]: ["连涨3天", "重仓英伟达"], identities[2]: None}


def test_constructed_tag_index_only_reordering_partial_and_explicit_empty(monkeypatch):
    payload = fixture("etf_tags_all_correct")
    payload["data"]["data"] = payload["data"]["data"][:1]
    raw = payload["data"]["data"][0]
    identity = raw["code"]
    payload["data"]["tag_infos"] = [
        {"tag_key": hotlist._TAG_KEYS[2], "idx": 4},
        {"tag_key": hotlist._TAG_KEYS[1], "idx": 8},
    ]
    raw["values"] = [{"idx": 8, "show_tag": ["连跌3天"]}, {"idx": 4, "show_tag": []},
                     {"idx": 99, "show_tag": {"future": "ignored"}}]
    post_sequence(monkeypatch, [payload])
    assert hotlist._fund_tags([identity], 1)[identity] == ["连跌3天"]
    raw["values"] = []
    post_sequence(monkeypatch, [payload])
    assert hotlist._fund_tags([identity], 1)[identity] == []
    raw["values"] = [{"tag_key": hotlist._TAG_KEYS[1], "show_tag": None}]
    post_sequence(monkeypatch, [payload])
    assert hotlist._fund_tags([identity], 1)[identity] is None
    raw["values"] = [{"idx": 8, "tag_key": hotlist._TAG_KEYS[2], "show_tag": []}]
    post_sequence(monkeypatch, [payload])
    with pytest.raises(SourceError, match="冲突"):
        hotlist._fund_tags([identity], 1)


@pytest.mark.parametrize("market", [{"invalid": True}, [], False])
def test_constructed_missing_related_code_and_bad_market_is_source_error(monkeypatch, market):
    payload = fixture("plate_concept")
    payload["data"]["plate_list"][0].update(etf_product_id=None, etf_market_id=market)
    monkeypatch.setattr(hotlist, "get_json", lambda *args, **kwargs: payload)
    with pytest.raises(SourceError):
        hotlist.sectors(limit=1, timeout=1)
    payload = fixture("index_sector")
    rec = fixture("index_etf_recommend")
    rec["data"][0].update(etfCode=None, etfMarket=market)
    post_sequence(monkeypatch, [payload, rec])
    with pytest.raises(SourceError):
        hotlist.sectors("index", limit=1, timeout=1)


def test_constructed_index_extra_internal_id_does_not_reject_valid_business(monkeypatch):
    payload = fixture("index_sector")
    payload["data"]["data"][0].update(id={"unknown": True}, unique_id=[], extra=False)
    calls = post_sequence(monkeypatch, [payload, fixture("index_etf_recommend"), fixture("index_etf_quotes")])
    assert hotlist.sectors("index", limit=1, timeout=1)[0]["sector_code"] == "120:931743"
    assert calls[1][1]["data"]["uniqueId"] == ""


@pytest.mark.parametrize("mutation", ["badstatus", "missingidentity", "duplicate", "badknown"])
def test_constructed_tags_failure_not_fake_empty(monkeypatch, mutation):
    payload = fixture("etf_tags_all_correct")
    payload["data"]["data"] = payload["data"]["data"][:1]
    identity = payload["data"]["data"][0]["code"]
    if mutation == "badstatus":
        payload["status_code"] = 10003
    elif mutation == "missingidentity":
        payload["data"]["data"] = []
    elif mutation == "duplicate":
        payload["data"]["data"] *= 2
    else:
        payload["data"]["data"][0]["values"][0]["show_tag"] = False
    post_sequence(monkeypatch, [payload])
    with pytest.raises(SourceError):
        hotlist._fund_tags([identity], 1)


def test_constructed_index_total_not_ranked_count_and_missing_optional_etf_leaves(monkeypatch):
    payload = fixture("index_sector")
    payload["data"]["total"] = {"unverified meaning": True}
    rec = fixture("index_etf_recommend")
    rec["data"][0].pop("etfName")
    quotes = fixture("index_etf_quotes")
    quotes["data"]["data"][0]["values"][1]["value"] = None
    calls = post_sequence(monkeypatch, [payload, rec, quotes])
    rows = hotlist.sectors("index", limit=1, timeout=1)
    assert rows[0]["related_etf_code"] == "159327"
    assert rows[0]["related_etf_name"] is rows[0]["related_etf_change_percent"] is None
    assert len(calls) == 3


@pytest.mark.parametrize("mutation", ["indexduplicate", "badindexcode", "recommendduplicate", "recommendconflict", "missingquote", "badquote"])
def test_constructed_index_related_business_damage_fails_whole_request(monkeypatch, mutation):
    payload = fixture("index_sector")
    rec = fixture("index_etf_recommend")
    quotes = fixture("index_etf_quotes")
    if mutation == "indexduplicate":
        payload["data"]["data"].append(deepcopy(payload["data"]["data"][0]))
    elif mutation == "badindexcode":
        payload["data"]["data"][0]["code"] = "931743"
    elif mutation == "recommendduplicate":
        rec["data"].append(deepcopy(rec["data"][0]))
    elif mutation == "recommendconflict":
        rec["data"][0]["stockCode"] = "120:other"
    elif mutation == "missingquote":
        quotes["data"]["data"].pop()
    else:
        quotes["data"]["data"][-1]["values"][1]["value"] = True
    post_sequence(monkeypatch, [payload, rec, quotes])
    with pytest.raises(SourceError):
        hotlist.sectors("index", limit=1, timeout=1)
