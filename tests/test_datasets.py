from dataclasses import FrozenInstanceError

import pytest
from pydantic import TypeAdapter, ValidationError

from finchx.contracts import StandardRecord
from finchx.datasets import DatasetDefinition, DatasetId


class SyntheticRequest:
    pass


class SyntheticData:
    pass


@pytest.mark.parametrize(
    "name",
    ["instrument", "trading_calendar", "market.quote", "market.klines"],
)
def test_initial_dataset_names_are_valid(name):
    assert TypeAdapter(DatasetId).validate_python(name) == name


def test_dataset_identity_is_open_to_future_names():
    assert TypeAdapter(DatasetId).validate_python("fundamental.balance_sheet") == (
        "fundamental.balance_sheet"
    )


@pytest.mark.parametrize(
    "name",
    [
        "Market Quote",
        "market..quote",
        ".market",
        "market.",
        "market/quote",
        "",
        "market.quote/",
        " market.quote",
        "market.quote ",
        "market. quote",
        "market.quote\n",
    ],
)
def test_invalid_dataset_names_are_rejected(name):
    with pytest.raises(ValidationError):
        TypeAdapter(DatasetId).validate_python(name)
    with pytest.raises(ValueError, match="invalid dataset name"):
        DatasetDefinition(
            name=name,
            schema_version="1.0",
            request_type=SyntheticRequest,
            data_type=SyntheticData,
        )


def test_synthetic_definition_exposes_identity_schema_and_types():
    definition = DatasetDefinition[SyntheticRequest, SyntheticData](
        name="fundamental.balance_sheet",
        schema_version="1.0",
        request_type=SyntheticRequest,
        data_type=SyntheticData,
    )
    assert definition.name == "fundamental.balance_sheet"
    assert definition.schema_version == "1.0"
    assert definition.request_type is SyntheticRequest
    assert definition.data_type is SyntheticData
    assert not hasattr(definition, "fetch")
    with pytest.raises(FrozenInstanceError):
        definition.name = "market.quote"


def test_dataset_name_is_compatible_with_standard_record():
    definition = DatasetDefinition(
        name="market.quote",
        schema_version="1.0",
        request_type=SyntheticRequest,
        data_type=SyntheticData,
    )
    record = StandardRecord.model_validate(
        {
            "dataset": definition.name,
            "schemaVersion": "1.0",
            "recordId": "synthetic-1",
            "entityId": "synthetic-entity",
            "capturedAt": "2026-09-17T09:30:00+08:00",
            "source": {"providerId": "synthetic"},
            "status": "live",
            "quality": {},
            "provenance": {"recordClass": "standardized"},
            "data": {},
        }
    )
    assert record.dataset == definition.name
