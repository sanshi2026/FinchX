from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal

import pytest
from pydantic import ValidationError, TypeAdapter

from finchx.contracts import (
    DataStatus,
    Percentage,
    ProvenanceClass,
    Quality,
    QualityIssue,
    QualityIssueKind,
    Source,
    StandardRecord,
    ValuationMultiple,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


def record_payload(**overrides):
    value = {
        "dataset": "market.quote",
        "schemaVersion": "1.0",
        "recordId": "finchx-test-record-001",
        "entityId": {
            "code": "TEST-000001",
            "market": "cn_a",
            "kind": "equity",
            "exchange": "sse",
        },
        "capturedAt": datetime(2026, 1, 2, 9, 30, 1, tzinfo=timezone(timedelta(hours=8))),
        "source": {"providerId": "synthetic"},
        "status": "live",
        "quality": {},
        "provenance": {"recordClass": "standardized"},
        "data": {"changeRatio": "0.0424"},
    }
    value.update(overrides)
    return value


def test_status_values_are_explicit_and_distinct():
    assert {item.value for item in DataStatus} == {
        "live",
        "delayed",
        "reused",
        "missing",
        "failed",
        "estimated",
    }
    assert DataStatus.MISSING is not DataStatus.FAILED
    assert DataStatus.REUSED is not DataStatus.LIVE


@pytest.mark.parametrize("status", ["unknown", "", None, []])
def test_invalid_status_is_rejected(status):
    with pytest.raises(ValidationError):
        StandardRecord.model_validate(record_payload(status=status))


@pytest.mark.parametrize(
    ("status", "record_class"),
    [
        ("live", "standardized"),
        ("delayed", "standardized"),
        ("reused", "standardized"),
        ("live", "derived"),
        ("delayed", "derived"),
        ("reused", "derived"),
        ("estimated", "standardized"),
        ("estimated", "derived"),
    ],
)
def test_status_and_record_class_are_independent(status, record_class):
    record = StandardRecord.model_validate(
        record_payload(
            status=status,
            provenance={"recordClass": record_class},
        )
    )
    assert record.status.value == status
    assert record.provenance.record_class.value == record_class


def test_time_fields_are_separate_optional_and_captured_at_is_required():
    record = StandardRecord.model_validate(record_payload())
    assert record.event_at is None
    assert record.published_at is None
    assert record.updated_at is None
    assert record.as_of is None
    assert record.captured_at.tzinfo is not None

    payload = record_payload()
    del payload["capturedAt"]
    with pytest.raises(ValidationError):
        StandardRecord.model_validate(payload)


def test_naive_datetime_is_rejected_and_offset_is_preserved():
    payload = record_payload(capturedAt=datetime(2026, 1, 2, 9, 30))
    with pytest.raises(ValidationError, match="timezone offset"):
        StandardRecord.model_validate(payload)

    subminute_offset = datetime(
        2026,
        1,
        2,
        9,
        30,
        tzinfo=timezone(timedelta(seconds=30)),
    )
    with pytest.raises(ValidationError, match="whole-minute precision"):
        StandardRecord.model_validate(record_payload(capturedAt=subminute_offset))

    payload = record_payload(
        eventAt="2026-01-02T09:30:00+08:00",
        publishedAt="2026-01-02T01:29:00Z",
        updatedAt="2026-01-02T09:29:30+08:00",
        asOf="2026-01-02T09:30:00+08:00",
    )
    record = StandardRecord.model_validate(payload)
    dumped = record.model_dump(mode="json", by_alias=True)
    assert dumped["capturedAt"] == "2026-01-02T09:30:01+08:00"
    assert dumped["eventAt"] == "2026-01-02T09:30:00+08:00"
    assert dumped["publishedAt"] == "2026-01-02T01:29:00Z"
    assert dumped["updatedAt"] == "2026-01-02T09:29:30+08:00"
    assert dumped["asOf"] == "2026-01-02T09:30:00+08:00"


def test_equivalent_timezone_offsets_represent_the_same_instant():
    local = StandardRecord.model_validate(
        record_payload(
            capturedAt=datetime(2026, 9, 17, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        )
    )
    utc = StandardRecord.model_validate(
        record_payload(capturedAt=datetime(2026, 9, 17, 1, 30, tzinfo=timezone.utc))
    )
    assert local.captured_at == utc.captured_at
    assert local.model_dump(mode="json", by_alias=True)["capturedAt"] == "2026-09-17T09:30:00+08:00"
    assert utc.model_dump(mode="json", by_alias=True)["capturedAt"] == "2026-09-17T01:30:00Z"


def test_source_identity_and_optional_references():
    source = Source.model_validate(
        {
            "providerId": "eastmoney",
            "sourceRecordId": "source-123",
            "sourceUrl": "https://example.invalid/item/123",
        }
    )
    assert source.provider_id == "eastmoney"
    assert source.source_record_id == "source-123"
    assert source.source_url is not None
    assert Source(providerId="synthetic").source_record_id is None

    with pytest.raises(ValidationError):
        Source(providerId="Provider With Spaces")


def test_quality_is_independent_and_accepts_quality_observations():
    assert Quality().issues == []
    issue = QualityIssue(kind=QualityIssueKind.WARNING, detail="Synthetic check.")
    quality = Quality(issues=[issue])
    assert quality.issues[0].kind is QualityIssueKind.WARNING

    all_kinds = {"warning", "validation_concern", "stale", "partial", "estimated"}
    assert {item.value for item in QualityIssueKind} == all_kinds
    with pytest.raises(ValidationError):
        Quality(issues=[{"kind": "not-a-quality-kind"}])


def test_quality_stale_is_independent_from_delayed_status():
    record = StandardRecord.model_validate(
        record_payload(
            status="delayed",
            quality={"issues": [{"kind": "stale", "detail": "Beyond freshness threshold."}]},
        )
    )
    assert record.status is DataStatus.DELAYED
    assert record.quality.issues[0].kind is QualityIssueKind.STALE


def test_provenance_captures_transform_version_sources_and_adjustments():
    record = StandardRecord.model_validate(
        record_payload(
            status="estimated",
            source={"providerId": "finchx.derived"},
            provenance={
                "recordClass": "derived",
                "transformationVersion": "sample-estimator/1",
                "sourceReferences": [
                    {"providerId": "synthetic", "sourceRecordId": "fixture-001"}
                ],
                "adjustments": [{"name": "sample-estimator", "version": "1"}],
            },
        )
    )
    assert record.provenance.record_class is ProvenanceClass.DERIVED
    assert record.provenance.transformation_version == "sample-estimator/1"
    assert record.provenance.source_references[0].source_record_id == "fixture-001"
    assert record.provenance.adjustments[0].name == "sample-estimator"


def test_instrument_identity_is_explicit_and_does_not_parse_symbols():
    identity = InstrumentId(
        code="TEST-000001",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )
    assert identity.code == "TEST-000001"

    with pytest.raises(ValidationError):
        InstrumentId(code="600519", market="unknown", kind="equity")
    with pytest.raises(ValidationError):
        InstrumentId(code="600519", market="cn_a", kind="warrant")
    with pytest.raises(ValidationError):
        InstrumentId(code="", market="cn_a", kind="equity")
    with pytest.raises(ValidationError):
        InstrumentId(code="   ", market="cn_a", kind="equity")


def test_decimal_percentage_is_a_fraction_and_serializes_without_float():
    adapter = TypeAdapter(Percentage)
    value = adapter.validate_python("0.0424")
    assert value == Decimal("0.0424")
    assert adapter.dump_python(value, mode="json") == "0.0424"
    assert Decimal(adapter.dump_python(value, mode="json")) * Decimal("100") == Decimal("4.24")
    for invalid_value in (0.0424, 1, "1e-3", "01.2", "NaN", Decimal("Infinity")):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid_value)
    with pytest.raises(ValidationError):
        adapter.validate_json(b"0.0424")
    with pytest.raises(ValidationError):
        adapter.validate_json(b'"1e-3"')


def test_valuation_multiple_is_decimal_times_and_allows_negative_and_zero():
    adapter = TypeAdapter(ValuationMultiple)
    assert adapter.validate_python(Decimal("-5.25")) == Decimal("-5.25")
    assert adapter.dump_python(Decimal("0"), mode="json") == "0"
    for invalid in (5.25, 1, "1e2", "NaN"):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def test_json_round_trip_preserves_contract_values():
    record = StandardRecord.model_validate(record_payload(eventAt="2026-01-02T09:30:00+08:00"))
    encoded = record.model_dump_json(by_alias=True)
    decoded = StandardRecord.model_validate_json(encoded)
    assert decoded == record
