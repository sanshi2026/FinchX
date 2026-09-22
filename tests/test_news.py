from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from finchx import FinchX
from finchx.collector import Collector
from finchx.datasets import NewsSearchRequest
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.eastmoney_documents import EastmoneyNewsProvider
from finchx.providers.errors import ProviderError


class FakeTransport:
    def __init__(self, document: dict[str, object]) -> None:
        self.document = document

    def get(self, _url, *, params, headers, timeout_seconds):
        return SimpleNamespace(status_code=200, text=json.dumps(self.document))


def _instrument() -> InstrumentId:
    return InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )


def _row(document_id: str, *, extra: bool = False) -> dict[str, str]:
    row = {
        "Art_ShowTime": "2026-09-22 10:00:00",
        "Art_Code": document_id,
        "Np_dst": "0",
        "Art_Title": f"News {document_id}",
        "Art_SortStart": "20260922100000",
        "Art_OriginUrl": f"https://finance.eastmoney.com/a/{document_id}.html",
        "Art_Url": f"https://finance.eastmoney.com/a/{document_id}.html",
    }
    if extra:
        row["New_Optional_Field"] = "forward-compatible"
    return row


def _document(rows: list[object], **updates: object) -> dict[str, object]:
    data: dict[str, object] = {
        "page_index": 1,
        "totle_hits": len(rows),
        "list": rows,
        "page_size": 20,
    }
    data.update(updates.pop("data", {}))
    document: dict[str, object] = {
        "code": 1,
        "message": "ok",
        "data": data,
    }
    document.update(updates)
    return document


def _provider(rows: list[object], **updates: object) -> EastmoneyNewsProvider:
    return EastmoneyNewsProvider(
        FakeTransport(_document(rows, **updates)),
        clock=lambda: datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
    )


def test_one_drifted_row_is_skipped_and_warning_reaches_fetch_result():
    drifted = {"Art_Code": "202609221234"}
    forward_compatible = _row("202609221235", extra=True)
    for optional_field in ("Np_dst", "Art_SortStart", "Art_OriginUrl"):
        forward_compatible.pop(optional_field)
    provider = _provider([forward_compatible, drifted, _row("202609221236")])
    client = FinchX(collector=Collector(provider_instances={"eastmoney.news": provider}))

    result = client.news.search("600519", provider="eastmoney.news")

    assert len(result.data) == 2
    assert [item.source_document_id for item in result.data] == [
        "202609221235",
        "202609221236",
    ]
    assert len(result.warnings) == 1
    assert "row 1" in result.warnings[0]
    assert "required fields missing" in result.warnings[0]


def test_multiple_drifted_rows_still_return_the_parseable_rows():
    provider = _provider([
        {"Art_Code": "202609221234"},
        _row("202609221235"),
        {"Art_ShowTime": "bad"},
        _row("202609221236"),
    ])
    client = FinchX(collector=Collector(provider_instances={"eastmoney.news": provider}))

    result = client.news.search("600519", provider="eastmoney.news")

    assert len(result.data) == 2
    assert len(result.warnings) == 2
    assert all("Skipped EastMoney news row" in warning for warning in result.warnings)


def test_top_level_schema_drift_remains_provider_error():
    provider = _provider([_row("202609221235")], unexpected="top-level")
    request = NewsSearchRequest(instrumentId=_instrument())

    with pytest.raises(ProviderError, match="news list root fields drifted"):
        provider.fetch_raw_news_page(request)


def test_all_rows_drifted_remains_provider_error():
    provider = _provider([{"Art_Code": "202609221234"}, "not-a-row"])
    request = NewsSearchRequest(instrumentId=_instrument())

    with pytest.raises(ProviderError, match="no parseable rows"):
        provider.fetch_raw_news_page(request)
