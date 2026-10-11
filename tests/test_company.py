"""公司业务契约；fixtures 为官方完整原响应，变异场景明确模拟。"""

import inspect
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import FinchX, SourceError
from finchx.sources.tencent import company

_FIXTURES = Path(__file__).parent / "fixtures"
_TOP = {"code", "exchange", "profile", "executives", "executive_share_changes", "share_capital", "shareholder_summary", "dividends", "repurchases", "financial_summary", "revenue_breakdown", "industry_comparison"}
_FIELDS = {
    "profile": {"company_name", "business_description", "issue_price", "listing_date"},
    "executives": {"name", "roles", "shares", "compensation"},
    "executive_share_changes": {"announcement_date", "person_name", "share_change", "average_price"},
    "share_capital": {"total_shares", "float_shares"},
    "shareholder_summary": {"shareholder_count", "average_shares_per_holder", "shareholder_count_change_percent", "top10_holder_percent", "top10_float_holder_percent"},
    "dividends": {"period", "announcement_date", "stock_dividend_per_10", "capitalization_per_10", "cash_dividend_per_10", "rights_issue_per_10", "record_date", "ex_date", "description"},
    "repurchases": {"date", "quantity", "average_price", "currency", "fund_amount", "market"},
}
_HOLDER_FIELDS = {"period_end", "holder_name", "shares", "share_type", "holding_percent", "previous_shares"}


def raw(symbol="sh600519", block="f10"):
    return (_FIXTURES / f"company_{symbol}_{block}.txt").read_text(encoding="utf-8")


def payload(symbol="sh600519", block="f10"):
    text = raw(symbol, block)
    return json.loads(text.split("=", 1)[1] if block == "holders" else text)


def serve(monkeypatch, *, info_text=None, holders_text=None):
    calls = []

    def request(url, **kwargs):
        query = parse_qs(urlsplit(url).query)
        calls.append((url, kwargs, query))
        symbol = query["code"][0]
        if query.get("type") == ["ltgd"]:
            if holders_text is not None:
                return holders_text
            year = query.get("year", [None])[0]
            return (_FIXTURES / f"company_holders_{year}.txt").read_text(encoding="utf-8") if year else raw(symbol, "holders")
        assert query.get("app") == ["official_website"]
        return info_text if info_text is not None else raw(symbol)

    monkeypatch.setattr(company, "get_text", request)
    return calls


def set_leaf(data, path, value):
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


@pytest.mark.parametrize("symbol,total,floating,holders", [
    ("sh600519", 1250081601, 1250000000, 296400),
    ("sz000001", 19405918198, 19406000000, 450700),
    ("sz000333", 7629933870, 6886000000, 271000),
])
def test_real_info_schema_exact_shares_units_and_fresh_single_request(monkeypatch, symbol, total, floating, holders):
    calls = serve(monkeypatch)
    api = FinchX(timeout=20).company
    result = api.info(symbol[2:])
    assert set(result) == _TOP and result["code"] == symbol[2:] and result["exchange"] == symbol[:2]
    for block, fields in _FIELDS.items():
        rows = result[block] if isinstance(result[block], list) else [result[block]]
        assert all(set(row) == fields for row in rows)
    assert result["share_capital"] == {"total_shares": total, "float_shares": floating}
    assert type(result["share_capital"]["total_shares"]) is int
    assert result["shareholder_summary"]["shareholder_count"] == holders
    assert type(result["shareholder_summary"]["shareholder_count"]) is int
    assert len(result["dividends"]) == 10 and len(result["executives"]) == 3
    assert api.info(symbol[2:]) == result and len(calls) == 2
    assert all(kwargs["timeout"] == 20 for _, kwargs, _ in calls)


def test_real_info_business_periods_announcements_and_per_ten_dividend_units(monkeypatch):
    serve(monkeypatch)
    row = FinchX().company.info("600519")
    assert row["profile"]["issue_price"] == 31.39 and row["profile"]["listing_date"] == "2001-08-27"
    assert row["executives"][0]["roles"] == ["党委书记", "董事长", "董事"]
    assert row["executives"][0]["shares"] is None
    assert row["executives"][2]["compensation"] == 200000
    assert row["executive_share_changes"][0] == {"announcement_date": "2018-09-26", "person_name": "万波", "share_change": -700, "average_price": 725.92}
    assert row["shareholder_summary"]["average_shares_per_holder"] == 4217.49
    assert row["dividends"][0] == {"period": "2026", "announcement_date": "2026-08-15", "stock_dividend_per_10": 0.0, "capitalization_per_10": 0.0, "cash_dividend_per_10": 0.0, "rights_issue_per_10": 0.0, "record_date": None, "ex_date": None, "description": "不分配不转增"}
    assert row["dividends"][1]["cash_dividend_per_10"] == 280.242
    assert row["dividends"][1]["period"] == "2025"  # 不是公告年份 2026。
    assert row["repurchases"][0] == {"date": "2026-05-27", "quantity": 1105300, "average_price": 1338.1, "currency": "CNY", "fund_amount": 1479000000.0, "market": None}
    assert row["repurchases"][7]["fund_amount"] == 99931700


def test_real_midea_exec_billions_and_bank_shares_not_float_capital_equation(monkeypatch):
    serve(monkeypatch)
    midea = FinchX().company.info("000333")
    assert midea["executives"][0]["shares"] == 117000000 and midea["executives"][0]["compensation"] == 12670000
    assert midea["executive_share_changes"][-1]["share_change"] == -20000000
    assert midea["dividends"][0]["record_date"] is None and midea["dividends"][0]["cash_dividend_per_10"] == 5
    bank = FinchX().company.info("000001")
    assert bank["executives"][0]["shares"] == 26700
    assert bank["shareholder_summary"]["average_shares_per_holder"] == 43100
    assert bank["shareholder_summary"]["shareholder_count_change_percent"] == -1.51
    assert bank["repurchases"] == []
    assert bank["share_capital"]["float_shares"] > bank["share_capital"]["total_shares"]  # 来源展示精度，不加跨块推断。


@pytest.mark.parametrize("missing", [None, "--"])
def test_exact_total_shares_fallback_only_when_actually_missing(monkeypatch, missing):
    data = payload(); data["data"]["gdgb"]["zgb_r"] = missing
    serve(monkeypatch, info_text=json.dumps(data))
    assert FinchX().company.info("600519")["share_capital"]["total_shares"] == 1250000000


@pytest.mark.parametrize("bad", [True, [], "not-number", float("inf")])
def test_invalid_exact_total_never_hidden_by_display_fallback(monkeypatch, bad):
    data = payload(); data["data"]["gdgb"]["zgb_r"] = bad
    serve(monkeypatch, info_text=json.dumps(data))
    with pytest.raises(SourceError):
        FinchX().company.info("600519")


def test_optional_leaves_zero_period_text_currency_and_unknown_extras(monkeypatch):
    data = payload()
    data["data"]["gdgb"].update({"zgb_r":"0", "ltgb":None, "gdrs":"0户", "rjcg":None})
    data["data"]["ggjj"][0].update({"cgs":"0", "xc":"0"})
    data["data"]["fhsp"][0]["nd"] = "2026中期"
    data["data"]["huigou"][0].update({"CURRENCY":"HKD", "FUND":"13万", "REDEMPTION_QUANTITY":"13万"})
    for block in ["pxmzb", "unknown_financial_block"]:
        data["data"][block] = {"未知财务": []}
    data["data"]["hydb"]["stock"]["unknown_metric"] = []
    serve(monkeypatch, info_text=json.dumps(data))
    row = FinchX().company.info("600519")
    assert row["share_capital"] == {"total_shares":0,"float_shares":None}
    assert row["shareholder_summary"]["shareholder_count"] == 0 and row["shareholder_summary"]["average_shares_per_holder"] is None
    assert row["executives"][0]["shares"] == row["executives"][0]["compensation"] == 0
    assert row["dividends"][0]["period"] == "2026中期"
    assert row["repurchases"][0]["currency"] == "HKD" and row["repurchases"][0]["fund_amount"] == 130000
    assert row["repurchases"][0]["quantity"] == 130000


@pytest.mark.parametrize("path,bad", [
    (("data","ggjj",0,"cgs"),"-1"), (("data","ggjj",0,"xc"),"-1万"),
    (("data","gdgb","gdrs"),"1.5户"), (("data","gdgb","ltgb"),"-1亿股"),
    (("data","gsjj","jg"),"31,39元"), (("data","huigou",0,"REDEEN_AVG_PRICE"),"1,33.10"),
    (("data","huigou",0,"FUND"),"-1亿"), (("data","ggzjc",0,"date"),"2026-02-29"),
    (("data","fhsp",0,"djr"),"2026-13-01"), (("data","gsjj","riqi"),True),
])
def test_invalid_known_units_dates_and_types_fail_whole_info(monkeypatch, path, bad):
    data = payload(); set_leaf(data,path,bad)
    serve(monkeypatch, info_text=json.dumps(data))
    with pytest.raises(SourceError):
        FinchX().company.info("600519")


@pytest.mark.parametrize("block", ["gsjj", "gdgb", "ggjj", "ggzjc", "fhsp", "huigou"])
def test_missing_required_info_block_is_not_normal_empty_result(monkeypatch, block):
    data=payload(); data["data"].pop(block)
    serve(monkeypatch,info_text=json.dumps(data))
    with pytest.raises(SourceError):
        FinchX().company.info("600519")


@pytest.mark.parametrize("field,bad", [("stockcode","000001"),("stockcode",600519),("sc","sz"),("sc",True)])
def test_provided_info_stock_identity_must_match(monkeypatch,field,bad):
    data=payload(); data["data"]["hydb"]["stock"][field]=bad
    serve(monkeypatch,info_text=json.dumps(data))
    with pytest.raises(SourceError):
        FinchX().company.info("600519")


def test_absent_optional_identity_and_valid_jsonp_are_supported(monkeypatch):
    data=payload(); data["data"]["hydb"]["stock"].pop("stockcode"); data["data"]["hydb"]["stock"].pop("sc")
    serve(monkeypatch,info_text="finchx_callback("+json.dumps(data)+");")
    assert FinchX().company.info("600519")["share_capital"]["total_shares"] == 1250081601


@pytest.mark.parametrize("symbol,first_name,shares,percent", [
    ("sh600519","中国贵州茅台酒厂(集团)有限责任公司",681283000,54.4991),
    ("sz000001","中国平安保险(集团)股份有限公司-集团本级-自有资金",9618540000,49.565),
    ("sz000333","美的控股有限公司",2169180000,28.4914),
])
def test_real_float_shareholders_complete_four_periods_and_fresh_single_request(monkeypatch,symbol,first_name,shares,percent):
    calls=serve(monkeypatch)
    api=FinchX(timeout=20).company
    rows=api.float_shareholders(symbol[2:])
    assert len(rows)==40 and all(set(row)==_HOLDER_FIELDS for row in rows)
    assert len({row["period_end"] for row in rows})==4
    assert rows[0]["period_end"] == "2026-06-30"
    assert rows[0]["holder_name"] == first_name and rows[0]["shares"] == shares and rows[0]["holding_percent"] == percent
    assert api.float_shareholders(symbol[2:]) == rows and len(calls)==2
    assert all("year" not in query and query["_var"]==["v_liutonggd"] for _,_,query in calls)


@pytest.mark.parametrize("year,periods,count", [(2024,["2024-12-31","2024-09-30","2024-06-30","2024-03-31"],40),(2013,["2013-12-31","2013-09-30"],20)])
def test_explicit_historical_year_is_sent_and_only_actual_periods_returned(monkeypatch,year,periods,count):
    calls=serve(monkeypatch)
    rows=FinchX(timeout=20).company.float_shareholders("000333",year=year)
    assert len(rows)==count and list(dict.fromkeys(row["period_end"] for row in rows))==periods
    assert len(calls)==1 and calls[0][2]["year"]==[str(year)]
    assert rows[0]["holding_percent"] == (28.3332 if year==2024 else 1.28616)


def test_unsupported_year_real_empty_source_must_fail_not_masquerade_as_empty(monkeypatch):
    calls=serve(monkeypatch)
    with pytest.raises(ValueError):
        FinchX().company.float_shareholders("000333",year=1990)
    assert len(calls)==1 and calls[0][2]["year"]==["1990"]


def test_float_missing_leaves_zero_and_source_percent_not_recomputed(monkeypatch):
    data=payload("sz000333","holders")
    data["data"]["data"][0]["rows"][0].update({"cgsl":"0","sqcgsl":None,"gfxz":None,"ltbl":"0","unknown":[]})
    serve(monkeypatch,holders_text="v_liutonggd="+json.dumps(data))
    rows=FinchX().company.float_shareholders("000333")
    assert len(rows)==40 and rows[0]=={"period_end":"2026-06-30","holder_name":"美的控股有限公司","shares":0,"share_type":None,"holding_percent":0.0,"previous_shares":None}
    assert rows[1]["holding_percent"]==11.7355


@pytest.mark.parametrize("mode", ["duplicate_period","duplicate_holder","invalid_period","negative_shares","fractional_shares","boolean_percent","negative_previous","empty_name","missing_rows","bad_data"])
def test_float_known_source_corruption_fails_without_partial(monkeypatch,mode):
    data=payload("sz000333","holders"); periods=data["data"]["data"]; first=periods[0]; row=first["rows"][0]
    if mode=="duplicate_period": periods.append(first)
    elif mode=="duplicate_holder": first["rows"].append(row)
    elif mode=="invalid_period": first["pdt"]="2026-02-29"
    elif mode=="negative_shares": row["cgsl"]="-1"
    elif mode=="fractional_shares": row["cgsl"]="1.5"
    elif mode=="boolean_percent": row["ltbl"]=True
    elif mode=="negative_previous": row["sqcgsl"]="-1"
    elif mode=="empty_name": row["gdmc"]=""
    elif mode=="missing_rows": first.pop("rows")
    elif mode=="bad_data": data["data"]["data"]={}
    serve(monkeypatch,holders_text="v_liutonggd="+json.dumps(data))
    with pytest.raises(SourceError):
        FinchX().company.float_shareholders("000333")


def test_explicit_year_cannot_ignore_year_or_same_response_history(monkeypatch):
    calls=serve(monkeypatch,holders_text=raw("sz000333","holders"))
    with pytest.raises(SourceError):
        FinchX().company.float_shareholders("000333",year=2024)
    assert len(calls)==1


def test_invalid_arguments_fail_before_network(monkeypatch):
    calls=serve(monkeypatch)
    for code in [None,True,600519,"60051","６００５１９"," 600519","430047"]:
        for invoke in [lambda:company.info(code,timeout=20),lambda:company.float_shareholders(code,timeout=20)]:
            with pytest.raises(ValueError): invoke()
    for year in [True,"2024",2024.0,999,10000]:
        with pytest.raises(ValueError): company.float_shareholders("600519",year,timeout=20)
    for timeout in [True,0,float("inf"),"20"]:
        with pytest.raises(ValueError): company.info("600519",timeout=timeout)
        with pytest.raises(ValueError): company.float_shareholders("600519",timeout=timeout)
    assert calls==[]


@pytest.mark.parametrize("response", ['callback({});alert(1)', '{"code":true,"data":{}}', '{"code":1,"msg":"error","data":{}}'])
def test_invalid_wrappers_or_explicit_source_status_fail(monkeypatch,response):
    serve(monkeypatch,info_text=response,holders_text=response)
    with pytest.raises(SourceError): FinchX().company.info("600519")
    with pytest.raises(SourceError): FinchX().company.float_shareholders("600519")


def test_transport_error_is_not_retried_or_returned_as_partial(monkeypatch):
    calls=[]; error=SourceError("tencent.company","模拟来源不可达")
    def fail(*args,**kwargs): calls.append(args); raise error
    monkeypatch.setattr(company,"get_text",fail)
    for invoke in [lambda:FinchX().company.info("600519"),lambda:FinchX().company.float_shareholders("600519")]:
        with pytest.raises(SourceError) as caught: invoke()
        assert caught.value is error
    assert len(calls)==2


def test_public_signatures_and_no_old_company_aliases():
    client=FinchX(timeout=20); api=client.company
    assert list(inspect.signature(api.info).parameters)==["code"]
    assert list(inspect.signature(api.float_shareholders).parameters)==["code","year"]
    assert inspect.signature(api.float_shareholders).parameters["year"].default is None
    for name in ["company_profile","executive_snapshot","executive_share_change","share_capital","shareholder_summary","dividend","repurchase","float_shareholder"]:
        assert not hasattr(api,name) and not hasattr(client.market,name)
