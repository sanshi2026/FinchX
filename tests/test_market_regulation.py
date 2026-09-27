"""EastMoney regulation endpoints retain source evidence and bounded-page state."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest

from finchx import FinchX
from finchx.collectors import CachePolicy, Collector, InvalidRequest
from finchx.datasets.market_regulation import (
    AbnormalCountsRequest,
    AbnormalRecordsRequest,
    RegulationWatchlistRequest,
    SeverePredictionsRequest,
    normalize_abnormal_counts,
    normalize_severe_predictions,
    normalize_watchlist,
)
from finchx.contracts import Source
from finchx.providers.eastmoney_regulation import (
    EASTMONEY_ABNORMAL_COUNTS_URL,
    EASTMONEY_PREDICTION_LIST_URL,
    EASTMONEY_WATCHLIST_URL,
    EastmoneyRegulationProvider,
    _HttpResponse,
)
from finchx.storage import Cache, MemoryStorage

_CAPTURED = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)
_SOURCE = Source(providerId="eastmoney.regulation")


class _ScriptedTransport:
    def __init__(self, respond):
        self.respond = respond
        self.calls: list[tuple[str, dict[str, str | int]]] = []

    def get(self, url, *, params, headers, timeout_seconds):
        copied = dict(params)
        self.calls.append((url, copied))
        value = self.respond(url, copied)
        body = value if isinstance(value, str) else json.dumps(value)
        return _HttpResponse(200, body)


def _datacenter_response(rows, *, pages=1, count=None, code=0, success=True):
    return {
        "success": success,
        "code": code,
        "message": "ok" if code == 0 else "business failure",
        "result": {"count": len(rows) if count is None else count, "pages": pages, "data": rows},
    }


def _record(**values):
    return {
        "SECUCODE": "600127.SH",
        "SECURITY_CODE": "600127",
        "SECURITY_NAME_ABBR": "金健米业",
        "TRADE_DATE": "2026-09-24 00:00:00",
        "IS_SYSDATE": "0",
        "IS_HAPPEN": "1",
        "IS_POSITIVE": "1",
        "CHANGE_RATE": 3.0,
        "MAX_DAYS": 10,
        "DEVUATION_VALUE": 2.54,
        "CHANGE_RATE_TARGET": 2.0,
        "UNUSUAL_TYPE": "涨幅偏离值达到7%",
        "RANK_TYPE": "2",
        **values,
    }


def _prediction(**values):
    return {"c": "000993", "n": "闽东电力", "s": 6, "e": 4, "m": 0, "o": 2, "a": 2.54, "t": 7, "x": 95.69, "d": 10, **values}


def test_watchlist_market_codes_preserve_raw_values_without_forging_identity():
    rows = [
        {"STKCODE": "600001", "STKNAME": "甲", "MARKET": "1", "VALIDATESTARTDATE": "20260901", "VALIDATEENDDATE": "20261231"},
        {"STKCODE": "430001", "STKNAME": "乙", "MARKET": "B"},
        {"STKCODE": "999999", "STKNAME": "丙", "MARKET": "X"},
    ]
    records = normalize_watchlist(
        RegulationWatchlistRequest(),
        rows,
        captured_at=_CAPTURED,
        source=_SOURCE,
        source_url=EASTMONEY_WATCHLIST_URL,
    )

    assert len(records) == 3
    assert [record.data["exchange"] for record in records] == ["sse", "bse", None]
    assert all(record.data["instrumentId"] is None for record in records)
    assert all("securityType" not in record.data for record in records)
    assert all("providerMarketCode" not in record.data for record in records)
    assert records[1].entity_id == "eastmoney.watchlist:B:430001"
    assert records[0].data["providerValues"]["MARKET"] == "1"
    assert records[2].data["providerValues"]["MARKET"] == "X"


def test_watchlist_rejects_invalid_compact_source_date():
    with pytest.raises(ValueError, match="VALIDATESTARTDATE is not an ISO date"):
        normalize_watchlist(
            RegulationWatchlistRequest(),
            [{"STKCODE": "600001", "STKNAME": "甲", "MARKET": "1", "VALIDATESTARTDATE": "20261301"}],
            captured_at=_CAPTURED,
            source=_SOURCE,
            source_url=EASTMONEY_WATCHLIST_URL,
        )


def test_watchlist_returns_complete_source_rows_without_invented_security_kind():
    transport = _ScriptedTransport(
        lambda url, params: [
            {"STKCODE": "600001", "STKNAME": "甲", "MARKET": "1"},
            {"STKCODE": "430001", "STKNAME": "乙", "MARKET": "B"},
        ]
    )
    provider = EastmoneyRegulationProvider(transport)
    result = FinchX(collector=Collector(provider_instances={provider.provider_id: provider})).market.regulation_watchlist(
        provider=provider.provider_id,
    )
    assert len(result.data) == 2
    assert all("securityType" not in record.data for record in result.data)
    assert all("providerMarketCode" not in record.data for record in result.data)
    assert all(record.data["instrumentId"] is None for record in result.data)
    assert [record.data["exchange"] for record in result.data] == ["sse", "bse"]
    assert result.data[0].data["providerValues"]["MARKET"] == "1"
    assert result.data[1].data["providerValues"]["MARKET"] == "B"
    assert result.metadata["collection_complete"] is True
    assert result.metadata["classification_complete"] is False
    assert result.metadata["unclassified_count"] == 2
    assert result.metadata["returned_count"] == 2
    assert result.warnings == ()
    assert transport.calls[0][1] == {}


def test_ratio_values_flags_rule_mapping_and_provider_originals_are_stable():
    predictions = normalize_severe_predictions(
        SeverePredictionsRequest(),
        [
            _prediction(),
            _prediction(c="000001", n="未知状态", s=1, e=999, o=9, x=None),
            _prediction(c="000002", n="当前未触发", s=4, e=2, o=0),
            _prediction(c="000003", n="当前已触发", s=5, e=3, o=1),
            _prediction(c="000004", n="未知字符串状态", s="future-board", e="future-rule", o="pending"),
        ],
        captured_at=_CAPTURED,
        source=_SOURCE,
        source_url=EASTMONEY_PREDICTION_LIST_URL,
    )
    current = predictions[0].data
    unknown = predictions[1].data
    current_not_triggered = predictions[2].data
    current_triggered = predictions[3].data
    unknown_text = predictions[4].data

    assert current["exchange"] == "bse"  # s=6, not m=0, identifies the BSE board
    assert current["providerMarketCode"] == 0
    assert current["deviation"] == "0.9569"
    assert current["triggerChangeRatio"] == "0.07"
    assert current["changeRatio"] == "0.0254"
    assert current["horizon"] == "next_session" and current["isTriggered"] is None
    assert Decimal(str(current["providerValues"]["x"])) == Decimal("95.69")
    assert current["ruleSemanticId"] == "bse_10d_up_1p5_percent_deviation"
    assert unknown["horizon"] == "unknown" and unknown["isTriggered"] is None
    assert unknown["providerRuleCode"] == 999 and unknown["ruleSemanticId"] is None
    assert unknown["deviation"] is None
    assert current_not_triggered["horizon"] == "current_session" and current_not_triggered["isTriggered"] is False
    assert current_triggered["horizon"] == "current_session" and current_triggered["isTriggered"] is True
    assert unknown_text["horizon"] == "unknown" and unknown_text["isTriggered"] is None
    assert unknown_text["providerBoardCode"] == "future-board"
    assert unknown_text["providerRuleCode"] == "future-rule"
    assert unknown_text["providerSignalState"] == "pending"
    assert unknown_text["instrumentId"] is None

    counts = normalize_abnormal_counts(
        AbnormalCountsRequest(),
        [
            {"c": "000993", "n": "闽东电力", "s": 1, "m": 0, "p": 4.2, "a": 2.54, "t": 3, "x": 95.69, "d": 7},
            {"c": "000994", "n": "未知板块", "s": "future-board", "m": 0, "t": 2},
        ],
        captured_at=_CAPTURED,
        source=_SOURCE,
        source_url=EASTMONEY_ABNORMAL_COUNTS_URL,
    )
    count = counts[0].data
    assert count["changeRatio"] == "0.0254"
    assert count["maxDeviation10d"] == "0.9569"
    assert count["providerValues"]["d"] == 7
    assert count["abnormalCount"] == 3
    assert "providerWindowDays" not in count
    assert counts[1].data["providerBoardCode"] == "future-board"
    assert counts[1].data["exchange"] is None


def test_severe_predictions_returns_all_horizons_and_preserves_unknown_states():
    rows = [
        _prediction(c="000101", o=0),
        _prediction(c="000102", o=1),
        _prediction(c="000103", o=2),
        _prediction(c="000104", o=9),
    ]
    transport = _ScriptedTransport(
        lambda url, params: {
            "result": 0,
            "pages": 1,
            "date": 20260924,
            "open": 0,
            "count": len(rows),
            "data": rows,
        }
    )
    provider = EastmoneyRegulationProvider(transport)
    result = FinchX(
        collector=Collector(provider_instances={provider.provider_id: provider})
    ).market.severe_predictions(provider=provider.provider_id)

    assert [row.data["horizon"] for row in result.data] == [
        "current_session",
        "current_session",
        "next_session",
        "unknown",
    ]
    assert [row.data["providerSignalState"] for row in result.data] == [0, 1, 2, 9]
    assert len(transport.calls) == 1
    assert "horizon" not in transport.calls[0][1]
    assert not hasattr(SeverePredictionsRequest(), "horizon")


def test_prediction_history_local_filters_preserve_unknown_flags_and_page_state():
    transport = _ScriptedTransport(
        lambda url, params: _datacenter_response(
            [
                _record(IS_SYSDATE="1"),
                _record(SECURITY_CODE="000001", SECUCODE="000001.SZ", IS_SYSDATE="0", IS_HAPPEN="unknown", IS_POSITIVE=None),
                _record(SECURITY_CODE="000002", SECUCODE="000002.SZ", IS_SYSDATE="unknown", IS_HAPPEN="0", IS_POSITIVE="0"),
            ],
            pages=3,
            count=5,
        )
    )
    provider = EastmoneyRegulationProvider(transport)
    result = FinchX(collector=Collector(provider_instances={provider.provider_id: provider})).market.abnormal_records(
        dataset="prediction_history",
        include_current=False,
        page=2,
        page_size=3,
        provider=provider.provider_id,
    )

    assert len(result.data) == 2
    assert result.data[0].data["isTriggered"] is None
    assert result.data[0].data["providerPositiveFlag"] is None
    assert result.data[0].data["providerCurrentSessionFlag"] is False
    assert result.data[1].data["isTriggered"] is False
    assert result.data[1].data["providerPositiveFlag"] is False
    assert result.data[1].data["providerCurrentSessionFlag"] is None
    assert result.metadata["upstream_page"] == 2
    assert result.metadata["upstream_pages"] == 3
    assert result.metadata["upstream_page_rows"] == 3
    assert result.metadata["returned_count"] == 2
    assert result.metadata["has_more"] is True
    assert result.metadata["page_complete"] is True
    assert result.metadata["collection_complete"] is False
    assert transport.calls[0][1]["pageNumber"] == 2
    assert transport.calls[0][1]["pageSize"] == 3
    assert transport.calls[0][1]["filter"] == ""
    assert "local_filters" not in result.metadata
    assert not {"instrument", "startDate", "endDate"}.intersection(transport.calls[0][1])


def test_server_filters_are_only_sent_when_validated_and_invalid_dataset_uses_finchi_error():
    transport = _ScriptedTransport(lambda url, params: _datacenter_response([_record()]))
    provider = EastmoneyRegulationProvider(transport)
    fx = FinchX(collector=Collector(provider_instances={provider.provider_id: provider}))
    fx.market.abnormal_records(
        dataset="prediction_history",
        triggered="yes",
        rise_only=True,
        provider=provider.provider_id,
    )
    assert transport.calls[0][1]["filter"] == '(IS_HAPPEN="1")(IS_POSITIVE="1")'
    with pytest.raises(InvalidRequest, match="invalid AbnormalRecordsRequest"):
        fx.market.abnormal_records(dataset="other", provider=provider.provider_id)


def test_event_type_and_severe_history_flags_are_normalized_without_losing_raw_values():
    def respond(url, params):
        if params["reportName"] == "RPT_APP_UNUSUALBASIC":
            if params["filter"] == '(UNUSUAL_TYPE="001")':
                return _datacenter_response(
                    [{
                        "SECUCODE": "000993.SZ", "SECURITY_CODE": "000993", "SECURITY_NAME_ABBR": "闽东电力",
                        "UNUSUAL_TYPE": "001", "START_DATE": "2026-09-18", "END_DATE": "2026-09-24",
                        "NOTICE_DATE": "2026-09-24", "INFO_CODE": "A123", "UNUSUAL_REASON": "偏离值",
                    }]
                )
            return _datacenter_response(
                [{
                    "SECUCODE": "000993.SZ", "SECURITY_CODE": "000993", "SECURITY_NAME_ABBR": "闽东电力",
                    "UNUSUAL_TYPE": "002", "IS_HIS": "0", "PREDICT_START_DATE": "2026-09-24",
                    "PREDICT_END_DATE": "2026-10-01",
                }]
            )
        raise AssertionError(url)

    transport = _ScriptedTransport(respond)
    provider = EastmoneyRegulationProvider(transport)
    fx = FinchX(collector=Collector(provider_instances={provider.provider_id: provider}))
    ordinary = fx.market.abnormal_records(dataset="abnormal_events", provider=provider.provider_id)
    history = fx.market.abnormal_records(
        dataset="severe_events", status="history", provider=provider.provider_id
    )
    assert ordinary.data[0].data["providerEventType"] == "001"
    assert ordinary.data[0].data["eventType"] == "ordinary"
    assert ordinary.data[0].data["announcementUrl"].endswith("infocode=A123")
    assert history.data[0].data["providerEventType"] == "002"
    assert history.data[0].data["providerMonitorStatus"] == "history"
    assert history.data[0].data["providerValues"]["IS_HIS"] == "0"
    assert transport.calls[1][1]["filter"] == '(UNUSUAL_TYPE="002")(IS_HIS="0")'


def test_prediction_pool_paginates_to_completion_and_cache_retains_empty_or_nonempty_metadata():
    def respond(url, params):
        if url == EASTMONEY_PREDICTION_LIST_URL:
            page = params["pageNo"]
            row = _prediction(c=f"00099{page}")
            return {"result": 0, "pages": 2, "date": 20260924, "open": 0, "count": 1, "data": [row]}
        raise AssertionError(url)

    transport = _ScriptedTransport(respond)
    provider = EastmoneyRegulationProvider(transport)
    cache = Cache(MemoryStorage(), clock=lambda: _CAPTURED)
    collector = Collector(
        provider_instances={provider.provider_id: provider},
        cache=cache,
        cache_policy={"market.severe_predictions": CachePolicy(enabled=True, ttl=60)},
        clock=lambda: _CAPTURED,
    )
    fx = FinchX(collector=collector)
    first = fx.market.severe_predictions(provider=provider.provider_id)
    second = fx.market.severe_predictions()

    assert len(first.data) == 2
    assert first.metadata["collection_complete"] is True
    assert first.metadata["upstream_pages_requested"] == 2
    assert first.metadata["provider_count_raw"] == 1
    assert second.cache_hit is True
    assert dict(second.metadata) == dict(first.metadata)
    assert len(transport.calls) == 2


def test_dy_pool_safety_cap_and_repeated_pages_never_claim_full_collection():
    transport = _ScriptedTransport(
        lambda url, params: {
            "result": 0,
            "pages": 12,
            "date": 20260924,
            "open": 0,
            "count": 1,
            "data": [_prediction(c=f"00099{params['pageNo']}")],
        }
    )
    provider = EastmoneyRegulationProvider(transport)
    response = provider.fetch_severe_predictions(
        SeverePredictionsRequest()
    )
    assert len(response.rows) == 10
    assert len(transport.calls) == 10
    assert response.metadata["collection_complete"] is False
    assert response.metadata["has_more"] is True

    repeated = _ScriptedTransport(
        lambda url, params: {
            "result": 0,
            "pages": 3,
            "date": 20260924,
            "open": 0,
            "count": 1,
            "data": [_prediction()],
        }
    )
    duplicate_response = EastmoneyRegulationProvider(repeated).fetch_severe_predictions(
        SeverePredictionsRequest()
    )
    assert len(duplicate_response.rows) == 1
    assert duplicate_response.metadata["collection_complete"] is False
    assert duplicate_response.metadata["upstream_pages_requested"] == 1


def test_pool_pagination_does_not_stop_on_repeated_empty_intermediate_pages():
    def respond(url, params):
        rows = [] if params["pageNo"] < 3 else [_prediction(c="000993")]
        return {"result": 0, "pages": 3, "date": 20260924, "open": 0, "count": 1, "data": rows}

    transport = _ScriptedTransport(respond)
    provider = EastmoneyRegulationProvider(transport)
    response = provider.fetch_severe_predictions(SeverePredictionsRequest())

    assert len(response.rows) == 1
    assert response.metadata["upstream_pages_requested"] == 3
    assert response.metadata["collection_complete"] is True
    assert response.metadata["has_more"] is False


def test_regulation_provider_retries_transient_http_failure_once():
    class _FlakyTransport:
        def __init__(self):
            self.calls = 0

        def get(self, url, *, params, headers, timeout_seconds):
            self.calls += 1
            if self.calls == 1:
                return _HttpResponse(503, "")
            payload = {
                "result": 0,
                "pages": 1,
                "date": 20260924,
                "open": 0,
                "count": 1,
                "data": [{"c": "000993", "n": "闽东电力", "s": 6, "t": 3}],
            }
            return _HttpResponse(200, json.dumps(payload))

    transport = _FlakyTransport()
    provider = EastmoneyRegulationProvider(transport)
    response = provider.fetch_abnormal_counts(AbnormalCountsRequest())

    assert transport.calls == 2
    assert response.metadata["collection_complete"] is True


def test_empty_pool_is_a_complete_empty_snapshot_and_upstream_count_is_not_promoted_to_total():
    transport = _ScriptedTransport(
        lambda url, params: {"result": 0, "pages": 0, "date": 20260924, "open": None, "count": 0, "data": []}
    )
    provider = EastmoneyRegulationProvider(transport)
    cache = Cache(MemoryStorage(), clock=lambda: _CAPTURED)
    collector = Collector(
        provider_instances={provider.provider_id: provider},
        cache=cache,
        cache_policy={"market.abnormal_counts": CachePolicy(enabled=True, ttl=60)},
        clock=lambda: _CAPTURED,
    )
    fx = FinchX(collector=collector)
    result = fx.market.abnormal_counts()
    cached = fx.market.abnormal_counts()
    assert result.data == ()
    assert result.metadata["collection_complete"] is True
    assert result.metadata["upstream_pages"] == 0
    assert result.metadata["provider_count_raw"] == 0
    assert "total_count" not in result.metadata
    assert cached.cache_hit is True
    assert dict(cached.metadata) == dict(result.metadata)
    assert len(transport.calls) == 1


def test_http_200_with_upstream_business_error_is_rejected():
    transport = _ScriptedTransport(lambda url, params: _datacenter_response([], code=9501, success=False))
    provider = EastmoneyRegulationProvider(transport)
    with pytest.raises(Exception, match="DataCenter business failure"):
        provider.fetch_abnormal_records(AbnormalRecordsRequest(dataset="prediction_history"))
