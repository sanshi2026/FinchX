"""上市公司财务业务契约；复用完整真实腾讯响应，变异场景明确模拟。"""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import FinchX, SourceError
from finchx.sources.tencent import company

_FIXTURES = Path(__file__).parent / "fixtures"
_CURRENT = {"period", "eps", "revenue", "revenue_change_percent", "net_profit", "net_profit_change_percent", "book_value_per_share", "net_assets", "goodwill", "goodwill_to_net_assets_percent", "roe_percent", "debt_ratio_percent", "pe_ttm", "pb"}
_HISTORY = {"period", "revenue", "revenue_change_percent", "net_profit", "net_profit_change_percent", "eps", "eps_change_percent"}
_GROUP = {"period", "dimension", "items", "other_items"}
_ITEM = {"name", "unit", "revenue", "revenue_share_percent"}
_METRIC = {"metric", "unit", "company_value", "industry_average", "industry_max", "industry_min"}


def payload(symbol="sh600519"):
    return json.loads((_FIXTURES / f"company_{symbol}_f10.txt").read_text(encoding="utf-8"))


def serve(monkeypatch, data=None):
    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        symbol = parse_qs(urlsplit(url).query)["code"][0]
        return json.dumps(data, ensure_ascii=False) if data is not None else (_FIXTURES / f"company_{symbol}_f10.txt").read_text(encoding="utf-8")

    monkeypatch.setattr(company, "get_text", request)
    return calls


def set_leaf(data, path, value):
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


@pytest.mark.parametrize("code,current,history,eps_comparison,group_count", [
    ("600519", {"period":"2026中报", "eps":35.57, "revenue":92278000000.0, "revenue_change_percent":1.30, "net_profit":44517000000.0, "net_profit_change_percent":-1.95, "book_value_per_share":200.99, "net_assets":251254000000.0, "goodwill":None, "goodwill_to_net_assets_percent":None, "roe_percent":16.75, "debt_ratio_percent":15.19, "pe_ttm":19.28, "pb":6.25},
     {"period":"2025", "revenue":172054000000.0, "revenue_change_percent":-1.20, "net_profit":82320000000.0, "net_profit_change_percent":-4.53, "eps":65.66, "eps_change_percent":-4.34},
     [35.57, 2.9911, 35.57, -0.10], 14),
    ("000001", {"period":"2026中报", "eps":1.24, "revenue":70617000000.0, "revenue_change_percent":1.78, "net_profit":25696000000.0, "net_profit_change_percent":3.32, "book_value_per_share":24.13, "net_assets":None, "goodwill":7568000000.0, "goodwill_to_net_assets_percent":None, "roe_percent":5.22, "debt_ratio_percent":90.91, "pe_ttm":5.26, "pb":0.49},
     {"period":"2025", "revenue":131442000000.0, "revenue_change_percent":-10.40, "net_profit":42633000000.0, "net_profit_change_percent":-4.21, "eps":2.07, "eps_change_percent":-3.72},
     [1.24, 1.0122, 2.98, 0.28], 18),
    ("000333", {"period":"2026中报", "eps":3.52, "revenue":261052000000.0, "revenue_change_percent":3.46, "net_profit":26446000000.0, "net_profit_change_percent":1.66, "book_value_per_share":27.82, "net_assets":212861000000.0, "goodwill":31577000000.0, "goodwill_to_net_assets_percent":14.83, "roe_percent":11.33, "debt_ratio_percent":64.89, "pe_ttm":14.05, "pb":2.94},
     {"period":"2025", "revenue":458502000000.0, "revenue_change_percent":12.08, "net_profit":43945000000.0, "net_profit_change_percent":14.03, "eps":5.80, "eps_change_percent":6.62},
     [3.52, 0.8291, 3.52, -0.07], 18),
])
def test_real_financial_values_units_periods_and_single_fresh_request(monkeypatch, code, current, history, eps_comparison, group_count):
    calls = serve(monkeypatch)
    api = FinchX(timeout=20).company
    result = api.info(code)
    summary = result["financial_summary"]
    assert set(result) == {"code", "exchange", "profile", "executives", "executive_share_changes", "share_capital", "shareholder_summary", "dividends", "repurchases", "financial_summary", "revenue_breakdown", "industry_comparison"}
    assert set(summary) == {"current", "history"} and summary["current"] == current
    assert set(summary["current"]) == _CURRENT
    assert summary["history"][0] == history and len(summary["history"]) == 4
    assert [row["period"] for row in summary["history"]] == ["2025", "2024", "2023", "2022"]
    assert all(set(row) == _HISTORY for row in summary["history"])
    groups = result["revenue_breakdown"]
    assert len(groups) == group_count and all(set(group) == _GROUP for group in groups)
    assert all(set(item) == _ITEM for group in groups for key in ["items", "other_items"] for item in group[key])
    comparison = result["industry_comparison"]
    assert set(comparison) == {"period", "period_end", "industry_name", "metrics"}
    assert comparison["period"] == "2026中报" and comparison["period_end"] == "2026-06-30"
    assert [row["metric"] for row in comparison["metrics"]] == ["eps", "revenue", "net_profit", "book_value_per_share", "roe_percent"]
    assert [row["unit"] for row in comparison["metrics"]] == ["元/股", "元", "元", "元/股", "%"]
    assert all(set(row) == _METRIC for row in comparison["metrics"])
    assert [comparison["metrics"][0][key] for key in ["company_value", "industry_average", "industry_max", "industry_min"]] == eps_comparison
    assert len(calls) == 1 and calls[0][1]["timeout"] == 20
    assert api.info(code) == result and len(calls) == 2


def test_summary_display_precision_not_replaced_by_industry_raw_values(monkeypatch):
    serve(monkeypatch)
    result = FinchX().company.info("600519")
    assert result["financial_summary"]["current"]["revenue"] == 92278000000.0
    assert result["financial_summary"]["current"]["net_profit"] == 44517000000.0
    metrics = result["industry_comparison"]["metrics"]
    assert metrics[1]["company_value"] == 92278072083.21
    assert metrics[2]["company_value"] == 44516880421.86
    assert metrics[1]["industry_average"] == 10415473737.34
    assert result["financial_summary"]["current"]["pe_ttm"] == 19.28  # 不用 hydb 中 19.32 覆盖。
    assert result["financial_summary"]["current"]["goodwill"] is None


def test_income_dimensions_and_other_items_preserve_source_grouping(monkeypatch):
    serve(monkeypatch)
    bank = FinchX().company.info("000001")["revenue_breakdown"]
    assert [row["dimension"] for row in bank[:3]] == ["industry", "region", "product"]
    assert bank[0]["items"][0] == {"name":"批发金融业务", "unit":"元", "revenue":32559000000.0, "revenue_share_percent":46.11}
    assert bank[1]["items"][-1] == {"name":"其他收入之和", "unit":"元", "revenue":11025000000.0, "revenue_share_percent":15.61}
    assert bank[1]["other_items"][0] == {"name":"北区", "unit":"元", "revenue":7141000000.0, "revenue_share_percent":10.11}
    assert len(bank[1]["other_items"]) == 3 and bank[0]["other_items"] == []
    midea = FinchX().company.info("000333")["revenue_breakdown"]
    group = next(row for row in midea if row["period"] == "2025年报" and row["dimension"] == "product")
    assert group["items"][-1]["revenue"] == 120734000000.0
    assert [item["name"] for item in group["other_items"]] == ["其他", "商业及工业解决方案:机器人与自动化", "商业及工业解决方案:工业技术", "其他收入之和"]
    assert group["other_items"][-1]["revenue"] == 28719000000.0


def test_negative_financials_decimal_magnitudes_and_uninvented_periods(monkeypatch):
    data = payload(); detail = data["data"]["zyzb"]["detail"]
    detail.update({"mgsy":"-0.0001元", "jlr":"-1.23456789万亿元", "jzc":"-1亿元", "jzcsyl":"-3%", "zsrzzl":"-4.5%", "syl":"-2.25"})
    data["data"]["hytrend"][0].update({"f_jlr":"-7654321.09", "f_mgsy":"-0.04", "t_jlr":"-123.45"})
    data["data"]["hydb"]["stock"].pop("date")
    serve(monkeypatch, data)
    result = FinchX().company.info("600519"); current = result["financial_summary"]["current"]
    assert current["net_profit"] == -1234567890000.0 and current["net_assets"] == -100000000.0
    assert current["eps"] == -0.0001 and current["roe_percent"] == -3 and current["revenue_change_percent"] == -4.5
    assert current["pe_ttm"] == -2.25
    assert result["financial_summary"]["history"][0]["net_profit"] == -7654321.09
    assert result["financial_summary"]["history"][0]["eps"] == -0.04
    assert result["financial_summary"]["history"][0]["net_profit_change_percent"] == -123.45
    assert current["period"] == "2026中报" and result["financial_summary"]["history"][0]["period"] == "2025"
    assert result["industry_comparison"]["period_end"] is None  # 不由“中报”补造 6 月 30 日。


def test_missing_and_zero_are_independent_without_cross_block_fallback(monkeypatch):
    data = payload("sz000001"); detail = data["data"]["zyzb"]["detail"]
    detail.update({"mgsy":None, "sy":"0元", "sy_jzc":"0%", "jzc":None})
    data["data"]["hytrend"][0]["f_mgsy"] = None  # 显示 mgsy 仍有效，不能补值。
    data["data"]["hydb"]["stock"]["mgsy"] = None
    data["data"]["hydb"]["hy"]["mgsy"] = "0"
    data["data"]["hydb"]["hymax"]["mgsy"] = "--"
    data["data"]["hydb"]["hymin"]["mgsy"] = "-1"
    serve(monkeypatch, data)
    result = FinchX().company.info("000001"); current = result["financial_summary"]["current"]
    assert current["eps"] is None and current["net_assets"] is None
    assert current["goodwill"] == current["goodwill_to_net_assets_percent"] == 0.0
    assert result["financial_summary"]["history"][0]["eps"] is None
    metric = result["industry_comparison"]["metrics"][0]
    assert [metric[key] for key in ["company_value", "industry_average", "industry_max", "industry_min"]] == [None, 0.0, None, -1.0]


@pytest.mark.parametrize("unit,income,expected", [("万元", "1.23456789", 12345.6789), ("万亿元", "0.123456789", 123456789000.0), ("亿元", "1.25万元", 12500.0), (None, "2.5亿元", 250000000.0)])
def test_income_declared_unit_scales_once_and_amount_suffix_has_precedence(monkeypatch, unit, income, expected):
    data = payload(); row = data["data"]["zysr"][0]["detail"][0]["detail"][0]
    row.update({"unit":unit, "income":income})
    serve(monkeypatch, data)
    result = FinchX().company.info("600519")["revenue_breakdown"][0]["items"][0]
    assert result["unit"] == unit and result["revenue"] == expected


@pytest.mark.parametrize("path,value", [
    (("zyzb",), None), (("zyzb","detail"), []), (("zyzb","date"), None),
    (("hytrend",), {}), (("zysr",), {}), (("zysr",0,"detail"), None),
    (("zysr",0,"detail",0,"detail"), {}), (("zysr",0,"detail",0,"others"), None),
    (("zysr",0,"detail",0,"type"), "unknown"), (("hydb",), None),
    (("hydb","stock"), []), (("hydb","hymax"), None), (("hydb","stock","date"), "2026-02-29"),
])
def test_required_financial_structure_and_source_date_corruption_fail_whole_info(monkeypatch, path, value):
    data = payload(); set_leaf(data["data"], path, value); serve(monkeypatch, data)
    with pytest.raises(SourceError):
        FinchX().company.info("600519")


@pytest.mark.parametrize("path,value", [
    (("zyzb","detail","mgsy"), False), (("hytrend",0,"f_mgsy"), True),
    (("hydb","hy","mgsy"), False), (("zyzb","detail","jlr"), "nan"),
    (("zyzb","detail","jlr"), float("inf")), (("zyzb","detail","mgsy"), []),
    (("zyzb","detail","yyzsr"), "1亿股"), (("zyzb","detail","zsrzzl"), "1亿元"),
    (("zysr",0,"detail",0,"detail",0,"unit"), "美元"),
    (("zysr",0,"detail",0,"detail",0,"name"), ""),
    (("zysr",0,"detail",0,"detail",0,"income"), "-1亿元"),
    (("hydb","hymax","mgsy"), "not-number"),
])
def test_illegal_known_financial_numbers_units_and_identity_fail(monkeypatch, path, value):
    data = payload(); set_leaf(data["data"], path, value); serve(monkeypatch, data)
    with pytest.raises(SourceError):
        FinchX().company.info("600519")


def test_duplicate_source_periods_or_dimensions_cannot_masquerade_as_complete(monkeypatch):
    for block in ["hytrend", "zysr"]:
        data = payload(); data["data"][block].append(data["data"][block][0]); serve(monkeypatch, data)
        with pytest.raises(SourceError): FinchX().company.info("600519")
    data = payload(); groups = data["data"]["zysr"][0]["detail"]; groups.append(groups[0]); serve(monkeypatch, data)
    with pytest.raises(SourceError): FinchX().company.info("600519")


def test_unknown_financial_extras_and_unconfirmed_industry_metrics_are_ignored(monkeypatch):
    calls = serve(monkeypatch); expected = FinchX().company.info("600519")
    data = payload(); data["data"]["zyzb"]["detail"]["unknown"] = []
    data["data"]["hytrend"][0]["unknown"] = {}
    data["data"]["zysr"][0]["detail"][0]["unknown"] = False
    data["data"]["hydb"]["stock"].update({"zsz":[], "Fmll":False, "create_time":"invalid", "Fzcfzl":{}, "f_yysr":True})
    serve(monkeypatch, data)
    result = FinchX().company.info("600519")
    assert result == expected
    assert len(calls) == 1 and "updated_at" not in result["industry_comparison"]
