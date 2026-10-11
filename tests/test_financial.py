"""财务报表业务契约；fixtures 是真实响应 title/report 的完整业务节选。"""

import inspect
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from finchx import FinchX, SourceError
from finchx.sources.tonghuashun import financial

_FIXTURES = Path(__file__).parent / "fixtures"
_RESOURCES = {"balance_sheet":"debt", "income_statement":"benefit", "cash_flow_statement":"cash"}
# 名称来自九份真实报表中的纯显示标题，不从粗体或曲线标记推测。
_HEADINGS = {"资产", "负债", "流动资产", "非流动资产", "流动负债", "非流动负债", "所有者权益（或股东权益", "所有者权益（或股东权益）", "六、每股收益", "一、经营活动产生的现金流量", "二、投资活动产生的现金流量", "三、筹资活动产生的现金流量", "补充资料：", "1、将净利润调节为经营活动现金流量：", "2、不涉及现金收支的重大投资和筹资活动：", "3、现金及现金等价物净变动情况："}


def payload(code="600519", resource="benefit"):
    outer = json.loads((_FIXTURES / f"financial_ths_{code}_{resource}.json").read_text(encoding="utf-8"))
    return json.loads(outer["flashData"])


def serve(monkeypatch, modified=None):
    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        code_resource = Path(urlsplit(url).path).stem
        if modified is not None:
            return json.dumps({"flashData":json.dumps(modified, ensure_ascii=False)}, ensure_ascii=False)
        return (_FIXTURES / f"financial_ths_{code_resource}.json").read_text(encoding="utf-8")

    monkeypatch.setattr(financial, "get_text", request)
    return calls


def body_index(data, name):
    return next(i for i,t in enumerate(data["title"]) if isinstance(t,list) and t[0] == name)


def values(row):
    return {item["name"]:item["value"] for item in row["items"]}


@pytest.mark.parametrize("code,statement,periods,items,last_period,first_name,first_value", [
    ("600519","balance_sheet",103,64,"1998-12-31","货币资金",53519000000.0),
    ("600519","income_statement",103,38,"1998-12-31","一、营业总收入",92278000000.0),
    ("600519","cash_flow_statement",99,57,"2000-12-31","销售商品、提供劳务收到的现金",98422000000.0),
    ("000001","balance_sheet",119,48,"1989-12-31","现金及存放中央银行款项",277326000000.0),
    ("000001","income_statement",122,34,"1989-12-31","一、营业总收入",70617000000.0),
    ("000001","cash_flow_statement",104,58,"1998-06-30","客户存款和同业存放款项净增加额",214713000000.0),
    ("000333","balance_sheet",75,69,"2006-12-31","货币资金",90643000000.0),
    ("000333","income_statement",75,37,"2006-12-31","一、营业总收入",261052000000.0),
    ("000333","cash_flow_statement",75,58,"2006-12-31","销售商品、提供劳务收到的现金",229262000000.0),
])
def test_all_nine_real_tables_keep_complete_business_subjects_and_periods(monkeypatch, code, statement, periods, items, last_period, first_name, first_value):
    calls = serve(monkeypatch)
    result = FinchX(timeout=20).financial.statements(code, statement)
    assert len(calls) == 1 and calls[0][1]["timeout"] == 20
    assert urlsplit(calls[0][0]).path.endswith(f"/{code}_{_RESOURCES[statement]}.json")
    assert len(result) == periods and result[0]["period_end"] == "2026-06-30" and result[-1]["period_end"] == last_period
    assert [row["period_end"] for row in result] == sorted({row["period_end"] for row in result}, reverse=True)
    source = payload(code, _RESOURCES[statement]); begin = body_index(source, "报表全部指标") + 1
    expected_names = [source["title"][i][0] for i in range(begin,len(source["title"])) if source["title"][i][0] not in _HEADINGS]
    assert len(expected_names) == items
    for row in result:
        assert set(row) == {"period_end", "items"}
        assert [item["name"] for item in row["items"]] == expected_names
        assert all(set(item) == {"name", "unit", "value"} and item["unit"] == "元" for item in row["items"])
    assert result[0]["items"][0] == {"name":first_name, "unit":"元", "value":first_value}


def test_bank_specific_subjects_and_basic_diluted_eps_group_parent_profit_are_not_merged(monkeypatch):
    serve(monkeypatch)
    api = FinchX().financial
    bank = values(api.statements("000001","income_statement",max_periods=1)[0])
    assert bank["利息净收入"] == 44288000000.0 and bank["利息收入"] == 79281000000.0
    balance = values(api.statements("000001","balance_sheet",max_periods=1)[0])
    assert balance["资产合计"] == 6030000000000.0
    maotai = values(api.statements("600519","income_statement",max_periods=1)[0])
    assert maotai["五、净利润"] == 46033000000.0
    assert maotai["归属于母公司所有者的净利润"] == 44517000000.0
    midea = values(api.statements("000333","income_statement",max_periods=1)[0])
    assert midea["（一）基本每股收益"] == 3.52 and midea["（二）稀释每股收益"] == 3.50
    assert midea["五、净利润"] == 26583000000.0 and midea["归属于母公司所有者的净利润"] == 26446000000.0
    cash = values(api.statements("000001","cash_flow_statement",max_periods=1)[0])
    assert cash["五、现金及现金等价物净增加额"] == -53384000000.0


def test_period_sorting_exact_selection_and_limit_do_not_use_nearest_report(monkeypatch):
    data = payload()
    for row in data["report"]:
        row.reverse()
    calls = serve(monkeypatch,data); api = FinchX().financial
    recent = api.statements("600519","income_statement",max_periods=2)
    assert [row["period_end"] for row in recent] == ["2026-06-30","2026-03-31"]
    old = api.statements("600519","income_statement",period_end="1998-12-31",max_periods=1)
    assert len(old) == 1 and old[0]["period_end"] == "1998-12-31"
    with pytest.raises(ValueError): api.statements("600519","income_statement",period_end="2026-04-30")
    assert len(calls) == 3


def test_missing_false_and_zero_negative_values_and_fresh_calls(monkeypatch):
    data = payload(); index = body_index(data,"其中：营业收入")
    data["report"][index][:5] = [False,"0","-1.2345亿",None,"--"]
    calls = serve(monkeypatch,data); api = FinchX().financial
    rows = api.statements("600519","income_statement",max_periods=5)
    assert [values(row)["其中：营业收入"] for row in rows] == [None,0.0,-123450000.0,None,None]
    assert api.statements("600519","income_statement",max_periods=5) == rows and len(calls) == 2


@pytest.mark.parametrize("unit,value,expected_unit,expected", [
    ("万元","1.23456789","元",12345.6789),
    ("亿元","1.25万元","元",12500.0),
    ("万亿元","0.123456789","元",123456789000.0),
    ("元","-1.23456789万亿","元",-1234567890000.0),
    (None,"35.57",None,35.57),
    ("","2.5亿元",None,250000000.0),
])
def test_units_and_decimal_precision_scale_once_without_inventing_missing_unit(monkeypatch, unit, value, expected_unit, expected):
    data = payload(); index = body_index(data,"其中：营业收入")
    data["title"][index][1] = unit; data["report"][index][0] = value
    serve(monkeypatch,data)
    item = next(item for item in FinchX().financial.statements("600519","income_statement",max_periods=1)[0]["items"] if item["name"] == "其中：营业收入")
    assert item == {"name":"其中：营业收入", "unit":expected_unit, "value":expected}


def test_business_rows_are_not_filtered_by_chart_or_bold_and_unknown_empty_subjects_are_kept(monkeypatch):
    data = payload(); index = body_index(data,"其中：营业收入")
    data["title"][index][3:] = [False,False]
    data["title"].append(["新增业务科目","元",0,True,False]); data["report"].append([""]*len(data["report"][0]))
    header = body_index(data,"六、每股收益"); data["report"][header][0] = "0"
    serve(monkeypatch,data)
    items = FinchX().financial.statements("600519","income_statement",max_periods=1)[0]["items"]
    assert "其中：营业收入" in [item["name"] for item in items]
    assert items[-1] == {"name":"新增业务科目", "unit":"元", "value":None}
    assert next(item for item in items if item["name"] == "六、每股收益")["value"] == 0.0


@pytest.mark.parametrize("mode", ["bad_matrix", "short_row", "duplicate_period", "invalid_period", "bad_title", "missing_name", "missing_whole_marker", "duplicate_whole_marker"])
def test_required_matrix_subject_identity_and_report_dates_fail_instead_of_partial(monkeypatch,mode):
    data = payload()
    if mode == "bad_matrix": data["report"] = {}
    elif mode == "short_row": data["report"][-1].pop()
    elif mode == "duplicate_period": data["report"][0][-1] = data["report"][0][0]
    elif mode == "invalid_period": data["report"][0][-1] = "2026-02-29"
    elif mode == "bad_title": data["title"][-1] = {}
    elif mode == "missing_name": data["title"][-1][0] = ""
    elif mode == "missing_whole_marker": data["title"][body_index(data,"报表全部指标")][0] = "未知分组"
    elif mode == "duplicate_whole_marker": data["title"].append(["报表全部指标","元",0,True,False]); data["report"].append([""]*len(data["report"][0]))
    serve(monkeypatch,data)
    with pytest.raises(SourceError): FinchX().financial.statements("600519","income_statement",max_periods=1)


@pytest.mark.parametrize("bad", [True,"nan","1亿美元",[],float("inf")])
def test_bad_known_number_even_in_unselected_period_fails_whole_response(monkeypatch,bad):
    data = payload(); data["report"][body_index(data,"其中：营业收入")][-1] = bad
    serve(monkeypatch,data)
    with pytest.raises(SourceError): FinchX().financial.statements("600519","income_statement",period_end="2026-06-30")


def test_unknown_nonempty_unit_fails_and_unrelated_matrices_are_ignored(monkeypatch):
    data = payload(); data["title"][body_index(data,"其中：营业收入")][1] = "美元";serve(monkeypatch,data)
    with pytest.raises(SourceError): FinchX().financial.statements("600519","income_statement")
    data = payload(); data.update({"simple":{},"year":False,"report_yoy":"corrupt unrelated matrix","unknown":[]})
    calls=[]
    def request(url,**kwargs):
        calls.append(url);return json.dumps({"flashData":json.dumps(data),"fieldflashData":{},"unknown":True})
    monkeypatch.setattr(financial,"get_text",request)
    rows = FinchX().financial.statements("600519","income_statement",max_periods=1)
    assert values(rows[0])["一、营业总收入"] == 92278000000.0 and len(calls) == 1


def test_invalid_arguments_fail_before_network_and_public_contract_has_no_aliases(monkeypatch):
    calls = serve(monkeypatch); api = FinchX().financial
    assert list(inspect.signature(api.statements).parameters) == ["code","statement","period_end","max_periods"]
    for kwargs in [
        {"code":600519}, {"code":"６００５１９"}, {"code":"430047"},
        {"statement":None}, {"statement":"income"}, {"period_end":"2026-6-30"}, {"period_end":"2026-02-29"},
        {"max_periods":True}, {"max_periods":0}, {"max_periods":1.5},
    ]:
        params={"code":"600519","statement":"income_statement"};params.update(kwargs)
        with pytest.raises(ValueError): api.statements(**params)
    assert calls == []
    for name in ["balance_sheet","income_statement","cash_flow_statement","summary","revenue_breakdown","industry_comparison"]:
        assert not hasattr(api,name)


@pytest.mark.parametrize("mode", ["missing_core_marker", "core_marker_value", "non_summary_before_full", "core_after_full"])
def test_malformed_core_partition_cannot_silently_discard_business_rows(monkeypatch, mode):
    data = payload()
    core = body_index(data,"报表核心指标")
    if mode == "missing_core_marker": data["title"][core][0] = "未知前置业务"
    elif mode == "core_marker_value": data["report"][core][0] = "0"
    elif mode == "non_summary_before_full": data["title"][core+1][0] = "前置新增业务科目"
    else:
        data["title"].append(data["title"][core]); data["report"].append(data["report"][core])
    serve(monkeypatch,data)
    with pytest.raises(SourceError): FinchX().financial.statements("600519","income_statement")


def test_complete_report_without_core_summary_is_valid(monkeypatch):
    data = payload(); full = body_index(data,"报表全部指标")
    data["title"] = [data["title"][0]] + data["title"][full:]
    data["report"] = [data["report"][0]] + data["report"][full:]
    serve(monkeypatch,data)
    rows = FinchX().financial.statements("600519","income_statement",max_periods=1)
    assert len(rows[0]["items"]) == 38 and values(rows[0])["五、净利润"] == 46033000000.0


@pytest.mark.parametrize("value", ['2026-06-30', '20260630', '2026/06/30', '2026-06-30 15:30:00', '20260630 15:30:00', '2026/06/30 15:30:00'])
def test_all_date_string_formats_match_exact_source_report(monkeypatch, value):
    serve(monkeypatch)
    rows = FinchX().financial.statements("600519", "income_statement", period_end=value)
    assert len(rows) == 1 and rows[0]["period_end"] == "2026-06-30"
