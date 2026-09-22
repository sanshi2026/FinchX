from datetime import datetime, timezone

from finchx.collectors import FetchResult
from finchx.contracts import DataStatus, Provenance, ProvenanceClass, Quality, Source, StandardRecord
from finchx.datasets.definition import DatasetDefinition


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


def test_single_and_multiple_standard_records_share_the_same_business_data_api():
    single = _result(_record(1, symbol="600519", price=1500))
    multiple = _result((_record(1, symbol="600519"), _record(2, symbol="000001")))

    assert single.to_dicts() == [{"symbol": "600519", "price": 1500}]
    assert multiple.to_dicts() == [{"symbol": "600519"}, {"symbol": "000001"}]
    frame = multiple.to_pandas()
    assert list(frame.columns) == ["symbol"]
    assert frame.to_dict(orient="records") == [{"symbol": "600519"}, {"symbol": "000001"}]
    assert single.data.source.provider_id == "test.provider"
    assert single.provenance[0].provider_id == "test.provider"


def test_empty_standard_record_result_converts_to_empty_rows_and_dataframe():
    result = _result(())

    assert result.to_dicts() == []
    frame = result.to_pandas()
    assert frame.empty
    assert list(frame.columns) == []


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


def test_non_standard_result_data_is_not_misrepresented_as_business_rows():
    result = _result({"computed": 1})

    try:
        result.to_dicts()
    except TypeError as exc:
        assert "StandardRecord" in str(exc)
    else:
        raise AssertionError("to_dicts must reject non-StandardRecord data")
