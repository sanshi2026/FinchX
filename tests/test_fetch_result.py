from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from finchx.computed import DeviationData, DeviationWindowConvention, DeviationWindowData
from finchx.collectors import FetchResult
from finchx.contracts import (
    DataStatus,
    Provenance,
    ProvenanceClass,
    Quality,
    Source,
    StandardRecord,
)
from finchx.datasets import (
    DISCLOSURE_DOCUMENT_DATASET,
    NEWS_DOCUMENT_DATASET,
    DisclosureCategory,
    DisclosureDocumentRef,
    NewsDocumentRef,
)
from finchx.datasets.definition import DatasetDefinition
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.query.documents import DisclosureService, NewsService


class _Request:
    pass


class _Data:
    pass


DATASET = DatasetDefinition(
    name="test.fetch_result",
    schema_version="1.0",
    request_type=_Request,
    data_type=_Data,
)
CAPTURED_AT = datetime(2026, 9, 22, 1, 0, tzinfo=timezone.utc)


def _record(index: int, **data: object) -> StandardRecord:
    return StandardRecord(
        dataset=DATASET.name,
        schemaVersion="1.0",
        recordId=f"record-{index}",
        entityId=f"entity-{index}",
        capturedAt=CAPTURED_AT,
        source=Source(providerId="test.provider", sourceRecordId=f"source-{index}"),
        status=DataStatus.LIVE,
        quality=Quality(),
        provenance=Provenance(
            recordClass=ProvenanceClass.STANDARDIZED,
            transformationVersion="test/1",
        ),
        data=dict(data),
    )


def _result(data: object) -> FetchResult[object]:
    return FetchResult(
        data=data,
        dataset=DATASET,
        provider="test.provider",
        captured_at=CAPTURED_AT,
        provenance=(Source(providerId="test.provider"),),
    )


def test_single_and_multiple_standard_records_share_the_same_dict_export_api():
    single = _result(_record(1, symbol="600519", price=1500))
    multiple = _result((_record(1, symbol="600519"), _record(2, symbol="000001")))

    assert single.to_dicts() == [{"symbol": "600519", "price": 1500}]
    assert multiple.to_dicts() == [{"symbol": "600519"}, {"symbol": "000001"}]
    assert single.data.source.provider_id == "test.provider"
    assert single.provenance[0].provider_id == "test.provider"
    assert single.attempts == ()
    assert single.warnings == ()
    assert single.cache_hit is False
    assert not hasattr(single, "to_pandas")


def test_news_and_disclosure_detail_services_return_fetch_results(monkeypatch):
    record = _record(1, title="detail", contentText="body")

    for service, dataset in (
        (NewsService(provider=object()), NEWS_DOCUMENT_DATASET),
        (DisclosureService(provider=object()), DISCLOSURE_DOCUMENT_DATASET),
    ):
        monkeypatch.setattr(service, "_get_document_record", lambda ref: record)

        single = service.get_document("ref")
        multiple = service.get_documents(("ref-1", "ref-2"))

        assert isinstance(single, FetchResult)
        assert single.dataset_id == dataset.name
        assert single.provider_id == "test.provider"
        assert single.data is record
        assert single.to_dicts() == [{"title": "detail", "contentText": "body"}]
        assert multiple.dataset_id == dataset.name
        assert multiple.data == (record, record)
        assert multiple.to_dicts() == [
            {"title": "detail", "contentText": "body"},
            {"title": "detail", "contentText": "body"},
        ]


def test_standard_record_dict_export_preserves_nested_data_and_is_deep_copied():
    record = _record(
        1,
        distribution=[{"bucket": "up", "count": 1}],
        nested={"items": [{"value": 2}]},
    )
    result = _result(record)

    rows = result.to_dicts()
    rows[0]["distribution"][0]["count"] = 999
    rows[0]["nested"]["items"][0]["value"] = 888

    assert record.data == {
        "distribution": [{"bucket": "up", "count": 1}],
        "nested": {"items": [{"value": 2}]},
    }


def _instrument(code: str = "600519", exchange: Exchange = Exchange.SSE) -> InstrumentId:
    return InstrumentId(
        code=code,
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=exchange,
    )


def _news_ref() -> NewsDocumentRef:
    return NewsDocumentRef(
        documentId="news-1",
        sourceDocumentId="source-news-1",
        title="News",
        publishedAt=datetime(2026, 9, 22, 1, tzinfo=timezone.utc),
        sourceUrl="https://example.com/news-search",
        documentUrl="https://example.com/news-1",
        relatedInstruments=[_instrument()],
        source=Source(providerId="eastmoney.news"),
        capturedAt=CAPTURED_AT,
        provenance=Provenance(recordClass=ProvenanceClass.STANDARDIZED),
    )


def _disclosure_ref() -> DisclosureDocumentRef:
    return DisclosureDocumentRef(
        documentId="disclosure-1",
        sourceDocumentId="source-disclosure-1",
        title="Disclosure",
        publishedAt=datetime(2026, 9, 22, 1, tzinfo=timezone.utc),
        noticeDate=date(2026, 9, 22),
        categories=[DisclosureCategory(code="annual", name="Annual")],
        relatedInstruments=[_instrument()],
        sourceUrl="https://example.com/disclosure-1",
        originalDocumentUrl="https://example.com/disclosure-1.pdf",
        source=Source(providerId="eastmoney.disclosure"),
        capturedAt=CAPTURED_AT,
        provenance=Provenance(recordClass=ProvenanceClass.STANDARDIZED),
    )


def _deviation_data() -> DeviationData:
    return DeviationData(
        instrumentId=_instrument(),
        board="main",
        effectiveAsOf=date(2026, 9, 22),
        calculationMode="official_close",
        priceBasis="qfq_stock__raw_index",
        ruleVersion="test/1",
        windows=[
            DeviationWindowData(
                windowDays=10,
                windowConvention=DeviationWindowConvention.MAX_DEVIATION_SCAN,
                tradingSessions=11,
                startDate=date(2026, 9, 8),
                baselineDate=date(2026, 9, 8),
                endDate=date(2026, 9, 22),
                startPrice=Decimal("10"),
                windowStartPrice=Decimal("10"),
                currentPrice=Decimal("11"),
                benchmarkInstrument=InstrumentId(
                    code="000300",
                    market=Market.CN_A,
                    kind=InstrumentKind.INDEX,
                    exchange=Exchange.SSE,
                ),
                benchmarkName="CSI 300",
                benchmarkStart=Decimal("4000"),
                benchmarkCurrent=Decimal("4100"),
                stockReturn=Decimal("0.1"),
                benchmarkReturn=Decimal("0.025"),
                deviation=Decimal("0.075"),
                upperThreshold=Decimal("0.2"),
                lowerThreshold=Decimal("-0.2"),
                remainingToUpper=Decimal("0.125"),
                remainingToLower=Decimal("0.275"),
                upperTriggerPrice=Decimal("12.25"),
                lowerTriggerPrice=Decimal("8.25"),
                remainingPricePctToUpper=Decimal("0.1136"),
                remainingPricePctToLower=Decimal("-0.25"),
            )
        ],
    )


def test_pydantic_model_results_export_as_json_dicts():
    data = _deviation_data()
    result = _result(data)

    assert result.to_dicts() == [data.model_dump(mode="json", by_alias=True)]
    assert result.to_dicts()[0]["windows"][0]["windowDays"] == 10


def test_pydantic_model_lists_export_one_dict_per_model():
    news = _news_ref()
    disclosures = [_disclosure_ref(), _disclosure_ref().model_copy(update={"document_id": "disclosure-2"})]

    assert _result([news, _news_ref()]).to_dicts() == [
        news.model_dump(mode="json", by_alias=True),
        news.model_dump(mode="json", by_alias=True),
    ]
    assert _result(disclosures).to_dicts() == [
        item.model_dump(mode="json", by_alias=True) for item in disclosures
    ]


def test_to_dicts_does_not_inject_fetch_result_audit_fields():
    result = _result(_record(1, symbol="600519"))

    assert set(result.to_dicts()[0]).isdisjoint(
        {"provider", "provenance", "attempts", "warnings", "fallback_used", "cache_hit"}
    )


def test_empty_standard_record_result_converts_to_empty_rows():
    result = _result(())

    assert result.to_dicts() == []


def test_fetch_result_is_not_a_sequence():
    result = _result(())

    with pytest.raises(TypeError):
        result[0]  # type: ignore[index]


def test_default_display_is_a_short_business_data_preview_without_audit_details():
    result = _result(
        tuple(_record(index, symbol=f"6005{index:02d}", price=index) for index in range(1, 6))
    )

    rendered = str(result)

    assert rendered == repr(result)
    assert "FetchResult(dataset='test.fetch_result', rows=5" in rendered
    assert "600501" in rendered
    assert "more rows" in rendered
    assert "provenance" not in rendered
    assert "attempts" not in rendered
    assert "test.provider" not in rendered


def test_unsupported_result_data_is_not_misrepresented_as_business_rows():
    result = _result({"computed": 1})

    try:
        result.to_dicts()
    except TypeError as exc:
        assert "Pydantic model" in str(exc)
    else:
        raise AssertionError("to_dicts must reject non-StandardRecord data")
