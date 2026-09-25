import json

import pytest

from finchx import FinchX
from finchx.datasets import (
    IWENCAI_SEARCH_DATASET,
    IWENCAI_SELECTION_DATASET,
    IwencaiReportDetailRequest,
    IwencaiSearchRequest,
    IwencaiSelectionRequest,
)
from finchx.providers.iwencai import (
    IWENCAI_RENDER_URL,
    IWENCAI_STREAM_URL,
    IwencaiProvider,
    IwencaiResponse,
)
from finchx.contracts import StandardRecord


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, *, json_payload, headers, timeout_seconds):
        self.calls.append((url, json_payload, headers, timeout_seconds))
        return self.responses.pop(0)


def _component(records, row_count):
    return {
        "chart_type": "jgyXuanguTable1",
        "data": {
            "meta": {"extra": {"row_count": row_count, "model_sql": "{}", "token": "secret"}},
            "datas": records,
        },
    }


def test_selection_reuses_stockx_two_step_protocol_and_keeps_cookie_private():
    stream = {
        "section": {"result_page": {"components": [_component([], 1)]}}
    }
    page = {"answer": {"components": [_component([
        {"股票代码": "600001.SH", "股票简称": "样本", "最新价": "12.30", "成交额": 100000000},
    ], 1)]}}
    transport = FakeTransport([
        IwencaiResponse(200, "data:" + json.dumps(stream, ensure_ascii=False)),
        IwencaiResponse(200, json.dumps(page, ensure_ascii=False)),
    ])

    result = IwencaiProvider(transport=transport).select(
        IwencaiSelectionRequest(query="成交额排名前500，非ST", cookies="session=owned", pageSize=100)
    )

    assert isinstance(result, tuple)
    assert isinstance(result[0], StandardRecord)
    assert result[0].data["instrumentId"]["code"] == "600001"
    assert result[0].data["amount"] == "100000000"
    assert transport.calls[0][0] == IWENCAI_STREAM_URL
    assert transport.calls[1][0] == IWENCAI_RENDER_URL
    assert transport.calls[0][2]["Cookie"] == "session=owned"
    assert transport.calls[0][1]["question"].startswith("成交额")
    assert "token" not in transport.calls[1][1]


def test_selection_normalizes_core_quote_fields_and_is_not_a_raw_source_dump():
    row = IwencaiProvider._normalize_selection_rows([{
        "股票代码": "688825.SH",
        "股票简称": " 长鑫科技 ",
        "最新价": "58.21",
        "成交量[20260923]": "156306484",
        "振幅[20260923]": 2.817145,
        "最新涨跌幅": 0.604908,
        "换手率[20260923]": 3.4709999999999996,
        "成交额[20260923]": 9214016142.08,
        "自定义指标": " 42.00 ",
    }])[0]

    payload = row.model_dump(mode="json", by_alias=True)
    assert payload["instrumentId"] == {
        "code": "688825",
        "market": "cn_a",
        "kind": "equity",
        "exchange": "sse",
    }
    assert payload["changeRate"] == "0.00604908"
    assert payload["amplitude"] == "0.02817145"
    assert payload["turnoverRate"] == "0.03471"
    assert payload["amount"] == "9214016142.08"
    assert payload["extraFields"] == {"自定义指标": "42.00"}
    assert "sourceFields" not in payload


def test_semantic_search_sends_api_key_claw_headers_and_optional_cookie(monkeypatch):
    monkeypatch.setenv("IWENCAI_API_KEY", "env-key")
    transport = FakeTransport([IwencaiResponse(200, json.dumps({
        "status_code": 0,
        "data": [
            {"uid": "a", "title": "旧", "publish_date": "2026-01-01", "score": 0.2},
            {"uid": "a", "title": "新", "publish_date": "2026-02-01", "score": 0.9},
        ],
    }, ensure_ascii=False))])
    result = IwencaiProvider(transport=transport).search(
        IwencaiSearchRequest(query="人形机器人", cookies={"sid": "owned"})
    )

    assert [item.data["title"] for item in result] == ["新"]
    headers = transport.calls[0][2]
    assert headers["Authorization"] == "Bearer env-key"
    assert headers["Cookie"] == "sid=owned"
    assert headers["X-Claw-Skill-Id"] == "report-search"
    assert len(headers["X-Claw-Trace-Id"]) == 64


def test_public_namespace_builds_two_explicit_dataset_requests():
    class SpyCollector:
        def __init__(self):
            self.calls = []

        def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
            self.calls.append((dataset, provider, use_cache, kwargs))
            return "ok"

    collector = SpyCollector()
    client = FinchX(collector=collector)
    assert client.iwencai.select("非ST", cookies="sid=owned") == "ok"
    assert client.iwencai.search("机器人", cookies="sid=owned", api_key="key") == "ok"
    assert collector.calls[0][0] is IWENCAI_SELECTION_DATASET
    assert collector.calls[0][3]["request"].cookies == "sid=owned"
    assert collector.calls[1][0] is IWENCAI_SEARCH_DATASET
    assert collector.calls[1][3]["request"].api_key == "key"


def test_selection_request_requires_a_non_empty_cookie():
    with pytest.raises(ValueError, match="cookies"):
        FinchX().iwencai.select("非ST", cookies=" ")


def test_report_detail_uses_shared_document_fields_and_standard_record_envelope():
    report_url = (
        "https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html"
        "?duid=d9924066929303a3"
    )

    class ReportTransport:
        def __init__(self):
            self.call = None

        def post_form(self, url, *, form_payload, headers, timeout_seconds):
            self.call = (url, dict(form_payload), dict(headers), timeout_seconds)
            return IwencaiResponse(200, json.dumps({
                "status_code": 0,
                "data": {
                    "site_url": "https://research.example/report.pdf",
                    "wordData": {
                        "UID": "d9924066929303a3",
                        "title": "业绩持续高增，全球光互连龙头地位稳固",
                        "content": "投资评级\n买入（维持评级）",
                        "organize": "天风证券",
                        "researcher": "王奕红",
                        "pubtime": "2026-09-09",
                        "ctime": "1788883200",
                        "ext": "pdf",
                        "click": 123,
                        "custom_metadata": "kept",
                    },
                },
            }, ensure_ascii=False))

    transport = ReportTransport()
    provider = IwencaiProvider(transport=transport)
    records = provider.report_detail(IwencaiReportDetailRequest(
        url=report_url,
        cookies="sid=private",
    ))

    assert len(records) == 1
    record = records[0]
    shared_document_fields = {
        "documentId", "sourceDocumentId", "title", "contentText", "publishedAt",
        "contentAvailable", "relatedInstruments", "url",
    }
    assert shared_document_fields <= record.data.keys()
    assert record.data["documentId"] == "iwencai:report:d9924066929303a3"
    assert record.data["sourceDocumentId"] == "d9924066929303a3"
    assert record.data["contentText"] == "投资评级\n买入（维持评级）"
    assert record.data["contentAvailable"] is True
    assert record.data["organization"] == "天风证券"
    assert record.data["analyst"] == "王奕红"
    assert record.data["extraFields"] == {"custom_metadata": "kept"}
    assert record.record_id == record.data["documentId"]
    assert record.source.source_record_id == "d9924066929303a3"
    assert record.published_at.isoformat() == "2026-09-09T00:00:00+00:00"
    assert transport.call[1] == {
        "type": "report",
        "duid": "d9924066929303a3",
        "query_source": "guide",
        "query": "*:*",
    }
    assert transport.call[2]["Cookie"] == "sid=private"
